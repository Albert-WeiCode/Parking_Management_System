from pathlib import Path
import random

from PIL import Image, ImageDraw


# =========================
# 1. 项目路径
# =========================

ROOT = Path(__file__).resolve().parent.parent

IMAGE_DIR = ROOT / "dataset" / "images" / "train"
LABEL_DIR = ROOT / "dataset" / "labels" / "train"
OUTPUT_DIR = ROOT / "dataset" / "check"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# 2. 随机选择图片
# =========================

images = list(IMAGE_DIR.glob("*.jpg"))

random.seed(42)
random.shuffle(images)

images = images[:10]

print(f"随机检查 {len(images)} 张图片")


# =========================
# 3. 读取 YOLO 标签
# =========================

for image_path in images:

    label_path = LABEL_DIR / f"{image_path.stem}.txt"

    if not label_path.exists():
        print(f"标签不存在: {label_path}")
        continue

    # 打开图片
    image = Image.open(image_path).convert("RGB")

    width, height = image.size

    draw = ImageDraw.Draw(image)

    # 读取标签
    with open(label_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:

        parts = line.strip().split()

        if len(parts) != 5:
            continue

        class_id = int(parts[0])

        center_x = float(parts[1])
        center_y = float(parts[2])
        box_width = float(parts[3])
        box_height = float(parts[4])

        # YOLO 坐标 → 图片像素坐标
        center_x *= width
        center_y *= height
        box_width *= width
        box_height *= height

        xmin = center_x - box_width / 2
        ymin = center_y - box_height / 2
        xmax = center_x + box_width / 2
        ymax = center_y + box_height / 2

        # 绘制矩形框
        draw.rectangle(
            [xmin, ymin, xmax, ymax],
            width=3
        )

        # 绘制类别
        draw.text(
            (xmin, max(0, ymin - 15)),
            f"license_plate ({class_id})"
        )

    # 保存检查图片
    output_path = OUTPUT_DIR / image_path.name
    image.save(output_path)

    print(f"已生成: {output_path}")


print()
print("================================")
print("标注检查完成")
print("================================")
print(f"检查图片目录: {OUTPUT_DIR}")