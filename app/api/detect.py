import logging
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from recognize.service import ModelUnavailableError, recognize_plate
from app.auth import is_authenticated
from app.config import MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES, RUNTIME_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/detect", tags=["检测"])
RESULT_DIR = RUNTIME_DIR / "results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)


def draw_plate_labels(image, labels):
    font_paths = (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    )
    font_path = next((path for path in font_paths if Path(path).exists()), None)
    if not font_path:
        return image
    canvas = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(font_path, 30)
    for label, x, y in labels:
        position = (x, max(y - 38, 2))
        bounds = draw.textbbox(position, label, font=font)
        draw.rectangle(bounds, fill=(30, 112, 80))
        draw.text(position, label, fill=(255, 255, 255), font=font)
    return cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)


def process_image(content):
    try:
        with Image.open(BytesIO(content)) as uploaded:
            if uploaded.width * uploaded.height > MAX_IMAGE_PIXELS:
                raise ValueError("图片分辨率过大，请缩小至 2000 万像素以内")
            if uploaded.format not in {"JPEG", "PNG", "WEBP", "BMP"}:
                raise ValueError("不支持该图片格式，请上传常见格式的图片")
            # Respect mobile-camera EXIF orientation before locating plates.
            image = cv2.cvtColor(np.asarray(ImageOps.exif_transpose(uploaded).convert("RGB")), cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("无法读取图片，请上传有效的图片文件") from exc

    results = recognize_plate(image)
    labels = []
    for item in results:
        x1, y1, x2, y2 = item["box"]
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 3)
        labels.append((f'{item["plate_number"] or "识别失败"} {item.get("plate_color", "")}', x1, y1))
    image = draw_plate_labels(image, labels)
    result_filename = f"result_{uuid4().hex}.jpg"
    success, encoded = cv2.imencode(".jpg", image)
    if not success:
        raise RuntimeError("结果图片编码失败")
    (RESULT_DIR / result_filename).write_bytes(encoded.tobytes())
    return {"success": True, "result_image": f"/results/{result_filename}", "results": results}


@router.post("/image")
async def detect_image(request: Request, file: UploadFile = File(...)):
    try:
        if not is_authenticated(request):
            return JSONResponse(status_code=401, content={"success": False, "message": "请先登录"})
        if not file.content_type or not file.content_type.startswith("image/"):
            return JSONResponse(status_code=400, content={"success": False, "message": "请上传图片文件"})
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={"success": False, "message": f"图片大小不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024} 兆"})
        if not content:
            return JSONResponse(status_code=400, content={"success": False, "message": "图片内容为空"})
        result = await run_in_threadpool(process_image, content)
        return {**result, "filename": file.filename}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})
    except ModelUnavailableError as exc:
        logger.exception("Plate model unavailable")
        return JSONResponse(status_code=503, content={"success": False, "message": str(exc)})
    except Exception:
        logger.exception("Plate inference failed")
        return JSONResponse(status_code=500, content={"success": False, "message": "识别服务异常，请检查服务日志后重试"})
    finally:
        await file.close()
