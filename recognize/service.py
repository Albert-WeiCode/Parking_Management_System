"""Lazy, serialized YOLO detection and plate recognition, shared by all requests."""
from functools import lru_cache
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import torch

from app.config import (DETECTION_CONFIDENCE, DETECTION_IMAGE_SIZE,
                        DETECTION_MODEL_PATH, INFERENCE_DEVICE, RECOGNITION_MODEL_PATH)
from recognize.model import COLORS, PlateRecognizer, decode_plate, preprocess_plate


class ModelUnavailableError(RuntimeError):
    pass


def select_device():
    if INFERENCE_DEVICE != "auto":
        return INFERENCE_DEVICE
    if torch.cuda.is_available():
        return "cuda:0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class RecognitionService:
    def __init__(self):
        self._lock = Lock()
        self._detector = None
        self._recognizer = None
        self.device = select_device()

    def _load(self):
        if self._detector is not None:
            return
        for path in (DETECTION_MODEL_PATH, RECOGNITION_MODEL_PATH):
            if not path.is_file():
                raise ModelUnavailableError(f"模型文件不存在：{path.name}，请检查模型路径配置")
        try:
            from ultralytics import YOLO
            checkpoint = torch.load(RECOGNITION_MODEL_PATH, map_location="cpu", weights_only=True)
            recognizer = PlateRecognizer(checkpoint["cfg"])
            recognizer.load_state_dict(checkpoint["state_dict"], strict=True)
            recognizer.to(self.device).eval()
            detector = YOLO(str(DETECTION_MODEL_PATH))
        except Exception as exc:
            raise ModelUnavailableError("模型加载失败，请检查权重、推理设备和依赖版本") from exc
        self._recognizer = recognizer
        self._detector = detector

    def recognize(self, image):
        # Ultralytics predictor and accelerator memory are shared across worker threads.
        with self._lock, torch.inference_mode():
            self._load()
            predictions = self._detector.predict(
                source=image, imgsz=DETECTION_IMAGE_SIZE, conf=DETECTION_CONFIDENCE,
                device=self.device, verbose=False,
            )[0]
            if predictions.boxes is None:
                return []
            height, width = image.shape[:2]
            plates = []
            for box in predictions.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().tolist()
                x1, y1 = max(0, int(x1)), max(0, int(y1))
                x2, y2 = min(width, int(x2)), min(height, int(y2))
                if x2 <= x1 or y2 <= y1:
                    continue
                crop = image[y1:y2, x1:x2]
                logits, color_logits = self._recognizer(preprocess_plate(crop).to(self.device))
                plate, confidences = decode_plate(logits)
                color_confidence, color_index = color_logits.softmax(-1)[0].max(0)
                plates.append({
                    "plate_number": plate,
                    "box": [x1, y1, x2, y2],
                    "detection_confidence": float(box.conf[0].item()),
                    "ocr_confidence": float(np.mean(confidences)) if confidences else 0.0,
                    "character_confidences": confidences,
                    "plate_color": COLORS[color_index.item()],
                    "color_confidence": float(color_confidence.item()),
                })
            return plates


@lru_cache(maxsize=1)
def get_service():
    return RecognitionService()


def recognize_plate(image):
    """Accept a BGR array or a file path (including Chinese paths)."""
    if isinstance(image, (str, Path)):
        image = cv2.imdecode(np.fromfile(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or not image.size:
        raise ValueError("无法读取图片")
    return get_service().recognize(image)
