import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

RUNTIME_DIR = Path(
    os.getenv(
        "PARKING_RUNTIME_DIR",
        str(Path(tempfile.gettempdir()) / "parking_management_system"),
    )
)

APP_NAME = "停车场管理系统"
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-before-production")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "Paking_Car_Sysetem")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:1.5b")


def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


DETECTION_MODEL_PATH = project_path(os.getenv("DETECTION_MODEL_PATH", "runs/license_plate/weights/best.pt"))
RECOGNITION_MODEL_PATH = project_path(os.getenv("RECOGNITION_MODEL_PATH", "recognize/plate_rec_color.pth"))
INFERENCE_DEVICE = os.getenv("INFERENCE_DEVICE", "auto")
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.25"))
DETECTION_IMAGE_SIZE = int(os.getenv("DETECTION_IMAGE_SIZE", "1024"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
