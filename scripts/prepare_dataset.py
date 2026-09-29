from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from ultralytics import YOLO


# ============================================================
# 项目路径
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

YOLO_MODEL_PATH = (
    ROOT
    / "runs"
    / "license_plate"
    / "weights"
    / "best.pt"
)

LPR_MODEL_PATH = (
    ROOT
    / "models"
    / "Final_LPRNet_model.pth"
)


# ============================================================
# LPRNet 字符集
# ============================================================

CHARS = [
    "京", "沪", "津", "渝", "冀", "晋", "蒙", "辽",
    "吉", "黑", "苏", "浙", "皖", "闽", "赣", "鲁",
    "豫", "鄂", "湘", "粤", "桂", "琼", "川", "贵",
    "云", "藏", "陕", "甘", "青", "宁", "新",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "A", "B", "C", "D", "E", "F", "G", "H", "J",
    "K", "L", "M", "N", "P", "Q", "R", "S", "T",
    "U", "V", "W", "X", "Y", "Z",
    "I", "O",
    "-"
]

CHARS_DICT = {
    char: index
    for index, char in enumerate(CHARS)
}


# ============================================================
# LPRNet 基础模块
# ============================================================

class SmallBasicBlock(nn.Module):

    def __init__(
        self,
        ch_in,
        ch_out,
    ):
        super().__init__()

        self.block = nn.Sequential(
            nn.Conv2d(
                ch_in,
                ch_out // 2,
                kernel_size=1,
            ),
            nn.BatchNorm2d(
                ch_out // 2
            ),
            nn.ReLU(),

            nn.Conv2d(
                ch_out // 2,
                ch_out // 2,
                kernel_size=(3, 1),
                padding=(1, 0),
            ),
            nn.BatchNorm2d(
                ch_out // 2
            ),
            nn.ReLU(),

            nn.Conv2d(
                ch_out // 2,
                ch_out,
                kernel_size=(1, 3),
                padding=(0, 1),
            ),
            nn.BatchNorm2d(
                ch_out
            ),
            nn.ReLU(),
        )

    def forward(self, x):
        return self.block(x)


# ============================================================
# LPRNet
# ============================================================

class LPRNet(nn.Module):

    def __init__(
        self,
        class_num,
        dropout_rate=0,
        lpr_max_len=8,
    ):
        super().__init__()

        self.class_num = class_num
        self.lpr_max_len = lpr_max_len

        self.backbone = nn.Sequential(

            nn.Conv2d(
                3,
                64,
                kernel_size=3,
                stride=1,
                padding=1,
            ),

            nn.BatchNorm2d(64),
            nn.ReLU(),

            nn.MaxPool3d(
                kernel_size=(1, 3, 3),
                stride=(1, 2, 2),
            ),

            SmallBasicBlock(
                64,
                128,
            ),

            nn.MaxPool3d(
                kernel_size=(1, 3, 3),
                stride=(1, 2, 2),
            ),

            SmallBasicBlock(
                128,
                256,
            ),

            SmallBasicBlock(
                256,
                256,
            ),

            nn.MaxPool3d(
                kernel_size=(1, 3, 3),
                stride=(1, 2, 2),
            ),

            nn.Dropout(
                dropout_rate
            ),

            nn.Conv2d(
                256,
                256,
                kernel_size=(4, 1),
            ),

            nn.BatchNorm2d(256),
            nn.ReLU(),

            nn.Dropout(
                dropout_rate
            ),

            nn.Conv2d(
                256,
                class_num,
                kernel_size=(1, 13),
                padding=(0, 6),
            ),
        )

    def forward(self, x):

        x = self.backbone(x)

        # 去掉高度维度
        x = x.squeeze(2)

        # [B, C, W]
        x = x.permute(
            0,
            2,
            1,
        )

        return x


# ============================================================
# 加载 LPRNet
# ============================================================

def load_lprnet():

    if not LPR_MODEL_PATH.exists():

        raise FileNotFoundError(
            f"LPRNet 权重不存在:\n"
            f"{LPR_MODEL_PATH}"
        )

    model = LPRNet(
        class_num=len(CHARS),
        dropout_rate=0,
        lpr_max_len=8,
    )

    checkpoint = torch.load(
        LPR_MODEL_PATH,
        map_location="cpu",
    )

    # 兼容不同 checkpoint 保存方式
    if isinstance(checkpoint, dict):

        if "state_dict" in checkpoint:
            checkpoint = checkpoint["state_dict"]

        elif "model_state_dict" in checkpoint:
            checkpoint = checkpoint["model_state_dict"]

    # 去掉 DataParallel 产生的 module. 前缀
    new_state_dict = {}

    for key, value in checkpoint.items():

        if key.startswith("module."):
            key = key[7:]

        new_state_dict[key] = value

    model.load_state_dict(
        new_state_dict,
        strict=True,
    )

    model.eval()

    return model


# ============================================================
# LPRNet 解码
# ============================================================

def decode_plate(output):

    """
    LPRNet 输出使用 CTC 风格解码。

    连续重复字符只保留一次。
    '-' 作为 blank 字符忽略。
    """

    output = output.detach().cpu()

    # [B, T, C]
    prediction = torch.argmax(
        output,
        dim=2,
    )

    prediction = prediction[0].numpy()

    result = []

    last_index = -1

    for index in prediction:

        index = int(index)

        # blank
        if index == CHARS_DICT["-"]:
            last_index = index
            continue

        # CTC 去重
        if index == last_index:
            continue

        if 0 <= index < len(CHARS):

            result.append(
                CHARS[index]
            )

        last_index = index

    return "".join(result)


# ============================================================
# LPRNet 图片预处理
# ============================================================

def preprocess_plate(plate_image):

    # LPRNet 原始模型要求 94 × 24
    image = cv2.resize(
        plate_image,
        (94, 24),
        interpolation=cv2.INTER_CUBIC,
    )

    # BGR -> RGB
    image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB,
    )

    image = image.astype(
        np.float32
    )

    # 归一化到 [-1, 1]
    image = (image - 127.5) / 128.0

    # HWC -> CHW
    image = image.transpose(
        2,
        0,
        1,
    )

    # 增加 batch 维度
    image = np.expand_dims(
        image,
        axis=0,
    )

    return torch.from_numpy(
        image
    ).float()


# ============================================================
# 初始化模型
# ============================================================

print("正在加载 YOLO11...")

yolo_model = YOLO(
    str(YOLO_MODEL_PATH)
)

print("YOLO11 加载完成")

print("正在加载 LPRNet...")

lprnet_model = load_lprnet()

print("LPRNet 加载完成")


# ============================================================
# 车牌识别
# ============================================================

def recognize_plate(image_path):

    image = cv2.imread(
        str(image_path)
    )

    if image is None:

        raise FileNotFoundError(
            f"无法读取图片: {image_path}"
        )

    # --------------------------------------------------------
    # YOLO11 检测车牌
    # --------------------------------------------------------

    results = yolo_model.predict(
        source=image,
        imgsz=1024,
        conf=0.25,
        device="mps",
        verbose=False,
    )

    result = results[0]

    if (
        result.boxes is None
        or len(result.boxes) == 0
    ):
        return []

    plates = []

    # --------------------------------------------------------
    # 遍历检测到的车牌
    # --------------------------------------------------------

    for box in result.boxes:

        x1, y1, x2, y2 = (
            box.xyxy[0]
            .cpu()
            .numpy()
            .astype(int)
        )

        # 防止越界
        x1 = max(
            0,
            x1,
        )

        y1 = max(
            0,
            y1,
        )

        x2 = min(
            image.shape[1],
            x2,
        )

        y2 = min(
            image.shape[0],
            y2,
        )

        # ----------------------------------------------------
        # 裁剪车牌
        # ----------------------------------------------------

        plate_image = image[
            y1:y2,
            x1:x2
        ]

        if plate_image.size == 0:
            continue

        # ----------------------------------------------------
        # LPRNet 预处理
        # ----------------------------------------------------

        input_tensor = preprocess_plate(
            plate_image
        )

        # ----------------------------------------------------
        # LPRNet 推理
        # ----------------------------------------------------

        with torch.no_grad():

            output = lprnet_model(
                input_tensor
            )

        # ----------------------------------------------------
        # 解码
        # ----------------------------------------------------

        plate_number = decode_plate(
            output
        )

        plates.append(
            {
                "plate_number": plate_number,
                "box": [
                    int(x1),
                    int(y1),
                    int(x2),
                    int(y2),
                ],
            }
        )

    return plates


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":

    test_dir = (
        ROOT
        / "dataset"
        / "images"
        / "test"
    )

    images = list(
        test_dir.glob("*.jpg")
    )

    if not images:

        print(
            "没有找到测试图片"
        )

        exit()

    image_path = images[0]

    print("=" * 60)
    print(
        "YOLO11 + LPRNet "
        "中文车牌识别测试"
    )
    print("=" * 60)

    print(
        f"测试图片: {image_path}"
    )

    results = recognize_plate(
        image_path
    )

    print()

    if not results:

        print(
            "没有检测到车牌"
        )

    else:

        for i, result in enumerate(
            results,
            1,
        ):

            print(
                f"车牌 {i}: "
                f"{result['plate_number']}"
            )

            print(
                f"位置: "
                f"{result['box']}"
            )

    print("=" * 60)
