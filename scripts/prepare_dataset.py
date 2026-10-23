"""Convert CLPD quadrilateral annotations into a reproducible YOLO split.

Usage: python scripts/prepare_dataset.py --output /path/to/new/dataset
Existing output directories are refused to protect hand-edited annotations.
"""
import argparse
import csv
import random
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def prepare_dataset(source, annotations, output, seed=42):
    source, annotations, output = Path(source), Path(annotations), Path(output)
    if output.exists():
        raise FileExistsError(f"输出目录已存在，请指定新目录：{output}")
    with annotations.open(encoding="gbk", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 3:
        raise ValueError("至少需要三张图片才能划分训练、验证和测试集")
    # Validate all inputs before copying anything.
    examples = []
    for row in rows:
        image = (source / row["path"]).resolve()
        if not image.is_relative_to(source.resolve()):
            raise ValueError(f"图片路径超出源目录：{row['path']}")
        with Image.open(image) as opened:
            width, height = opened.size
        xs = [max(0, min(width, float(row[f"x{i}"]))) for i in range(1, 5)]
        ys = [max(0, min(height, float(row[f"y{i}"]))) for i in range(1, 5)]
        x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"无效标注：{image.name}")
        label = f"0 {(x1+x2)/2/width:.8f} {(y1+y2)/2/height:.8f} {(x2-x1)/width:.8f} {(y2-y1)/height:.8f}\n"
        examples.append((image, label))
    random.Random(seed).shuffle(examples)
    train_end = max(1, min(len(examples) - 2, int(len(examples) * 0.7)))
    val_end = max(train_end + 1, min(len(examples) - 1, int(len(examples) * 0.9)))
    for split, items in (("train", examples[:train_end]), ("val", examples[train_end:val_end]), ("test", examples[val_end:])):
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)
        for index, (image, label) in enumerate(items):
            filename = f"{index:05d}_{image.name}"
            shutil.copy2(image, output / "images" / split / filename)
            (output / "labels" / split / Path(filename).with_suffix(".txt")).write_text(label)
    # Relative paths keep the generated dataset portable.
    (output / "data.yaml").write_text("train: images/train\nval: images/val\ntest: images/test\nnames:\n  0: license_plate\n")
    print(f"数据集已生成：{output.resolve()}（{len(examples)} 张）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "CLPD")
    parser.add_argument("--annotations", type=Path, default=ROOT / "CLPD" / "CLPD.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    prepare_dataset(args.source, args.annotations, args.output, args.seed)
