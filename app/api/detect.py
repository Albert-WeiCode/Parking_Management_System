from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFont

from ai.plate_recognition import recognize_plate
from app.auth import is_authenticated
from app.config import RUNTIME_DIR


router = APIRouter(prefix="/api/detect", tags=["检测"])

ROOT = Path(__file__).resolve().parent.parent.parent

TEMP_DIR = RUNTIME_DIR / "uploads"
RESULT_DIR = RUNTIME_DIR / "results"

TEMP_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)


def draw_plate_labels(image, labels):
    font_paths = (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
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


@router.post("/image")
async def detect_image(request: Request, file: UploadFile = File(...)):

    if not is_authenticated(request):
        return JSONResponse(status_code=401, content={"success": False, "message": "请先登录"})

    # 检查文件类型
    if not file.content_type or not file.content_type.startswith("image/"):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "请上传图片文件",
            },
        )

    # 保存临时图片
    suffix = Path(file.filename or "image.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        suffix = ".jpg"
    token = uuid4().hex
    file_path = TEMP_DIR / f"{token}{suffix}"

    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        # YOLO11 + LPRNet
        results = recognize_plate(str(file_path))

        # 读取原图
        image = cv2.imread(str(file_path))

        if image is None:
            raise ValueError("无法读取图片")

        # 在原图上绘制检测框
        labels = []
        for item in results:

            x1, y1, x2, y2 = item["box"]

            plate_number = item["plate_number"]

            # 绘制车牌框
            cv2.rectangle(
                image,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                3,
            )

            labels.append((plate_number or "识别失败", x1, y1))

        image = draw_plate_labels(image, labels)

        # 保存结果图片
        result_filename = f"result_{token}.jpg"

        result_path = RESULT_DIR / result_filename

        cv2.imwrite(
            str(result_path),
            image,
        )

        return {
            "success": True,
            "filename": file.filename,
            "result_image": f"/results/{result_filename}",
            "results": results,
        }

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e),
            },
        )

    finally:

        # 删除临时图片
        if file_path.exists():
            file_path.unlink()
