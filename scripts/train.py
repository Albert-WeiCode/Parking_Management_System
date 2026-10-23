from pathlib import Path

import torch
from ultralytics import YOLO


# =========================
# 项目根目录
# =========================

ROOT = Path(__file__).resolve().parent.parent


# =========================
# 数据集
# =========================

DATA_YAML = ROOT / "dataset" / "data.yaml"


# =========================
# 模型
# =========================

MODEL_PATH = ROOT / "yolo11s.pt"


# =========================
# 训练参数
# =========================

EPOCHS = 150
IMAGE_SIZE = 1024
BATCH_SIZE = 32


def main():

    print("=" * 50)
    print("YOLO11s 车牌检测训练")
    print("=" * 50)

    print(f"数据集: {DATA_YAML}")
    print(f"模型: {MODEL_PATH}")
    print(f"Epochs: {EPOCHS}")
    print(f"Image Size: {IMAGE_SIZE}")
    print(f"Batch Size: {BATCH_SIZE}")

    # 加载预训练模型
    model = YOLO(MODEL_PATH)

    # 开始训练
    model.train(
        data=str(DATA_YAML),

        # 基本训练参数
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,

        # GPU
        device="cuda:0" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"),

        # 输出目录
        project=ROOT / "runs",
        name="license_plate",

        # 保存
        save=True,
        save_period=10,

        # 数据增强
        degrees=5.0,
        translate=0.1,
        scale=0.5,
        fliplr=0.0,  # 车牌字符不能水平镜像

        # 训练稳定性
        patience=20,

        # 工作进程
        workers=8,

        # 混合精度
        amp=True,
    )


if __name__ == "__main__":
    main()