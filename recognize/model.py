"""Network compatible with plate_rec_color.pth.

Architecture and input contract reference:
https://github.com/we0091234/yolov8-plate/tree/master/plate_recognition
The checkpoint cfg determines the feature channels; state loading is strict.
"""
import cv2
import numpy as np
import torch
from torch import nn

CHARACTERS = "#京沪津渝冀晋蒙辽吉黑苏浙皖闽赣鲁豫鄂湘粤桂琼川贵云藏陕甘青宁新学警港澳挂使领民航危0123456789ABCDEFGHJKLMNPQRSTUVWXYZ险品"
COLORS = ("黑色", "蓝色", "绿色", "白色", "黄色")


class PlateRecognizer(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        layers = []
        channels = 3
        for index, width in enumerate(cfg):
            if width == "M":
                layers.append(nn.MaxPool2d(3, 2, ceil_mode=True))
            else:
                layers.extend([
                    nn.Conv2d(channels, width, 5 if index == 0 else 3,
                              padding=0 if index == 0 else 1),
                    nn.BatchNorm2d(width), nn.ReLU(inplace=True),
                ])
                channels = width
        self.feature = nn.Sequential(*layers)
        self.conv1 = nn.Conv2d(channels, 12, 3, stride=2)
        self.bn1 = nn.BatchNorm2d(12)
        self.relu1 = nn.ReLU(inplace=True)
        self.color_classifier = nn.Conv2d(12, len(COLORS), 1)
        self.color_bn = nn.BatchNorm2d(len(COLORS))
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.loc = nn.MaxPool2d((5, 2), stride=1, padding=(0, 1))
        self.newCnn = nn.Conv2d(channels, len(CHARACTERS), 1)

    def forward(self, image):
        features = self.feature(image)
        color = self.relu1(self.bn1(self.conv1(features)))
        color = self.gap(self.color_bn(self.color_classifier(color))).flatten(1)
        text = self.newCnn(self.loc(features)).squeeze(2).transpose(1, 2)
        return text, color


def preprocess_plate(image):
    """Keep OpenCV BGR order, as used to train this checkpoint."""
    resized = cv2.resize(image, (168, 48)).astype(np.float32)
    normalized = (resized / 255.0 - 0.588) / 0.193
    return torch.from_numpy(normalized.transpose(2, 0, 1).copy()).unsqueeze(0)


def decode_plate(logits):
    """CTC greedy decode: blank is index 0; blanks separate repeated chars."""
    probabilities, indices = logits.softmax(-1).max(-1)
    characters, confidences = [], []
    previous = 0
    for index, confidence in zip(indices[0].tolist(), probabilities[0].tolist()):
        if index and index != previous:
            characters.append(CHARACTERS[index])
            confidences.append(confidence)
        previous = index
    return "".join(characters), confidences
