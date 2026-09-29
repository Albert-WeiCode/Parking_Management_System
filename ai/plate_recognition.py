from pathlib import Path
import re

import cv2
import numpy as np
import torch
import torch.nn as nn
from ultralytics import YOLO


# ============================================================
# 项目根目录
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
    / "ai"
    / "Final_LPRNet_model.pth"
)


# ============================================================
# LPRNet 字符表
# 与经典 LPRNet_Pytorch 预训练模型保持一致
# ============================================================

CHARS = [
    "京", "沪", "津", "渝", "冀", "晋", "蒙", "辽",
    "吉", "黑", "苏", "浙", "皖", "闽", "赣", "鲁",
    "豫", "鄂", "湘", "粤", "桂", "琼", "川", "贵",
    "云", "藏", "陕", "甘", "青", "宁", "新",

    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",

    "A", "B", "C", "D", "E", "F", "G", "H", "J", "K",
    "L", "M", "N", "P", "Q", "R", "S", "T", "U", "V",
    "W", "X", "Y", "Z", "I", "O",

    "-"
]

BLANK_INDEX = len(CHARS) - 1


# ============================================================
# LPRNet Small Basic Block
# ============================================================

class SmallBasicBlock(nn.Module):
    def __init__(self, ch_in, ch_out):
        super().__init__()
        channels = ch_out // 4
        self.block = nn.Sequential(
            nn.Conv2d(ch_in, channels, 1),
            nn.ReLU(),
            nn.Conv2d(channels, channels, (3, 1), padding=(1, 0)),
            nn.ReLU(),
            nn.Conv2d(channels, channels, (1, 3), padding=(0, 1)),
            nn.ReLU(),
            nn.Conv2d(channels, ch_out, 1),
        )

    def forward(self, x):
        return self.block(x)


class LPRNet(nn.Module):
    """与 Final_LPRNet_model.pth 对应的标准 LPRNet，输出 [B, C, T]。

    网络及预处理参考 https://github.com/sirius-ai/LPRNet_Pytorch 。
    """

    def __init__(self, class_num=len(CHARS), dropout_rate=0):
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Conv2d(3, 64, 3),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool3d((1, 3, 3), (1, 1, 1)),
            SmallBasicBlock(64, 128),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool3d((1, 3, 3), (2, 1, 2)),
            SmallBasicBlock(64, 256),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            SmallBasicBlock(256, 256),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.MaxPool3d((1, 3, 3), (4, 1, 2)),
            nn.Dropout(dropout_rate),
            nn.Conv2d(64, 256, (1, 4)),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Conv2d(256, class_num, (13, 1)),
            nn.BatchNorm2d(class_num),
            nn.ReLU(),
        )
        self.container = nn.Sequential(nn.Conv2d(448 + class_num, class_num, 1))

    def forward(self, x):
        features = []
        for index, layer in enumerate(self.backbone):
            x = layer(x)
            if index in (2, 6, 13, 22):
                features.append(x)

        context = []
        for index, feature in enumerate(features):
            if index < 2:
                feature = nn.functional.avg_pool2d(feature, 5, 5)
            elif index == 2:
                feature = nn.functional.avg_pool2d(feature, (4, 10), (4, 2))
            scale = feature.square().mean().clamp_min(torch.finfo(feature.dtype).eps)
            context.append(feature / scale)
        return self.container(torch.cat(context, dim=1)).mean(dim=2)


# ============================================================
# 加载 YOLO11
# ============================================================

if not YOLO_MODEL_PATH.exists():

    raise FileNotFoundError(
        f"YOLO 模型不存在:\n{YOLO_MODEL_PATH}"
    )

yolo_model = YOLO(
    str(YOLO_MODEL_PATH)
)


# ============================================================
# 选择设备
# ============================================================

# YOLO 可使用 MPS；LPRNet 的 MaxPool3d 在 Mac 上使用 CPU。
DETECTION_DEVICE = (
    "cuda:0" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

print(
    f"LPRNet 推理设备: {DEVICE}"
)


# ============================================================
# 加载 LPRNet
# ============================================================

def load_lprnet():

    if not LPR_MODEL_PATH.exists():

        raise FileNotFoundError(
            f"""
LPRNet 权重不存在：

{LPR_MODEL_PATH}

请把 Final_LPRNet_model.pth 放到：

ai/Final_LPRNet_model.pth
"""
        )

    model = LPRNet(
        class_num=len(CHARS),
        dropout_rate=0,
    )

    checkpoint = torch.load(
        LPR_MODEL_PATH,
        map_location="cpu",
        weights_only=True,
    )

    # 某些模型保存的是 state_dict
    if isinstance(
        checkpoint,
        dict
    ):

        if "state_dict" in checkpoint:

            checkpoint = checkpoint[
                "state_dict"
            ]

        elif "model_state_dict" in checkpoint:

            checkpoint = checkpoint[
                "model_state_dict"
            ]

    # 去除 DataParallel 的 module. 前缀
    cleaned_state_dict = {}

    for key, value in checkpoint.items():

        if key.startswith("module."):

            key = key[
                len("module.") :
            ]

        cleaned_state_dict[
            key
        ] = value

    try:

        model.load_state_dict(
            cleaned_state_dict,
            strict=True,
        )

    except RuntimeError as e:

        print()
        print("=" * 60)
        print("LPRNet 权重加载失败")
        print("=" * 60)
        print()
        print(
            "当前 Final_LPRNet_model.pth "
            "与代码中的 LPRNet 网络结构不完全匹配。"
        )
        print()
        print("具体错误：")
        print(e)
        print()

        raise

    model.to(DEVICE)

    model.eval()

    print(
        "LPRNet 权重加载成功"
    )

    return model


lpr_model = load_lprnet()


# ============================================================
# LPRNet 图像预处理
# ============================================================

def preprocess_lpr_image(
    plate_image
):

    if plate_image is None:

        return None

    if plate_image.size == 0:

        return None

    # LPRNet 输入：
    # 宽 94
    # 高 24

    image = cv2.resize(
        plate_image,
        (94, 24),
        interpolation=cv2.INTER_LINEAR,
    )

    # 保留 BGR 通道顺序，与标准 LPRNet 的训练预处理一致。

    image = image.astype(
        np.float32
    )

    # 原版 LPRNet 常用归一化：
    # (pixel - 127.5) / 128

    image = (
        image - 127.5
    ) / 128.0

    # HWC -> CHW

    image = np.transpose(
        image,
        (2, 0, 1),
    )

    image = np.ascontiguousarray(
        image
    )

    tensor = torch.from_numpy(
        image
    ).unsqueeze(0)

    return tensor.to(DEVICE)


# ============================================================
# LPRNet 解码
# ============================================================

def decode_lprnet(
    output
):

    # output:
    #
    # [batch, class_num, sequence]
    #

    output = (
        output
        .detach()
        .cpu()
        .numpy()
    )

    prediction = output[0]

    # 每个时间步取概率最大的字符

    indexes = np.argmax(
        prediction,
        axis=0,
    )

    result = []

    previous = BLANK_INDEX

    for index in indexes:

        index = int(index)

        # blank
        if index == BLANK_INDEX:

            previous = index

            continue

        # 去除连续重复字符

        if index == previous:

            continue

        if 0 <= index < len(CHARS):

            result.append(
                CHARS[index]
            )

        previous = index

    return "".join(result)


# ============================================================
# LPRNet 车牌识别
# ============================================================

@torch.no_grad()
def recognize_plate_number(
    plate_image
):

    tensor = preprocess_lpr_image(
        plate_image
    )

    if tensor is None:

        return "", 0.0

    output = lpr_model(
        tensor
    )

    plate_number = decode_lprnet(
        output
    )

    # 仅对 CTC 解码保留的字符统计概率，空结果置信度为 0。
    probability = output.softmax(dim=1)[0]
    scores, indexes = probability.max(dim=0)
    retained_scores = []
    previous = BLANK_INDEX
    for index, score in zip(indexes.tolist(), scores.tolist()):
        if index != BLANK_INDEX and index != previous:
            retained_scores.append(score)
        previous = index
    confidence = (
        sum(retained_scores) / len(retained_scores) if retained_scores else 0.0
    )

    return (
        plate_number,
        confidence,
    )


# ============================================================
# YOLO11 + LPRNet
# ============================================================

def recognize_plate(
    image_path
):

    image = cv2.imread(
        str(image_path)
    )

    if image is None:

        raise FileNotFoundError(
            f"无法读取图片：{image_path}"
        )

    # --------------------------------------------------------
    # YOLO11 检测
    # --------------------------------------------------------

    results = yolo_model.predict(
        source=image,
        imgsz=1024,
        conf=0.25,
        device=DETECTION_DEVICE,
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
    # 遍历所有车牌
    # --------------------------------------------------------

    for box in result.boxes:

        coordinates = (
            box.xyxy[0]
            .detach()
            .cpu()
            .numpy()
            .astype(int)
        )

        x1, y1, x2, y2 = coordinates

        # ----------------------------------------------------
        # LPRNet 使用紧贴车牌的裁剪，避免缩放后背景挤占字符空间。
        # ----------------------------------------------------
        x1, x2 = np.clip([x1, x2], 0, image.shape[1])
        y1, y2 = np.clip([y1, y2], 0, image.shape[0])

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
        # LPRNet
        # ----------------------------------------------------

        plate_number, confidence = (
            recognize_plate_number(
                plate_image
            )
        )

        plates.append(
            {
                "plate_number": plate_number,

                "ocr_confidence": confidence,

                "detection_confidence": float(box.conf[0].detach().cpu()),

                "box": [
                    int(x1),
                    int(y1),
                    int(x2),
                    int(y2),
                ],
            }
        )

        print()
        print(
            f"车牌识别结果: "
            f"{plate_number}"
        )

        print(
            f"LPRNet置信度: "
            f"{confidence:.4f}"
        )

        print(
            f"位置: "
            f"[{x1}, {y1}, {x2}, {y2}]"
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

    images = []

    for extension in (
        "*.jpg",
        "*.jpeg",
        "*.png",
    ):

        images.extend(
            test_dir.glob(extension)
        )

    if not images:

        print(
            "没有找到测试图片："
        )

        print(
            test_dir
        )

        raise SystemExit

    # 自然排序：1.jpg、2.jpg、10.jpg，避免依赖文件系统遍历顺序。
    images.sort(key=lambda path: [
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", path.name)
    ])
    image_path = images[0]

    print("=" * 60)
    print(
        "YOLO11 + LPRNet "
        "车牌识别测试"
    )
    print("=" * 60)

    print(
        f"测试图片：{image_path}"
    )

    print(
        f"YOLO模型："
        f"{YOLO_MODEL_PATH}"
    )

    print(
        f"LPRNet模型："
        f"{LPR_MODEL_PATH}"
    )

    print(
        f"设备：{DEVICE}"
    )

    print("=" * 60)

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
                f"LPRNet置信度: "
                f"{result['ocr_confidence']:.4f}"
            )

            print(
                f"位置: "
                f"{result['box']}"
            )

    print("=" * 60)
