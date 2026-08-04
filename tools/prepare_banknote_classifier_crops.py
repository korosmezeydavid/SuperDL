#!/usr/bin/env python3
"""Extract YOLO bbox crops for Stage-2 classifier training (224×224).

Reads:  tools/banknote_yolo/images/{split}/ + labels/
Writes: tools/banknote_dataset_crops/<class>/   (classifier folder layout)
        tools/banknote_dataset_crops/none/       (empty-label frames)

Run:
  python tools/prepare_banknote_classifier_crops.py
  python tools/build_huf_banknote_model.py --dataset-dir tools/banknote_dataset_crops
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit("pip install pillow") from exc

TOOLS = Path(__file__).resolve().parent
YOLO_ROOT = TOOLS / "banknote_yolo"
OUT_ROOT = TOOLS / "banknote_dataset_crops"
SPLITS = ("train", "val", "test")
CLASS_NAMES = ["huf_500", "huf_1000", "huf_2000", "huf_5000", "huf_10000", "huf_20000"]
CLASS_TO_ID = {n: i for i, n in enumerate(CLASS_NAMES)}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CROP_SIZE = 224
PAD = 0.06


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build crop classifier dataset from YOLO labels.")
    p.add_argument("--yolo-dir", type=Path, default=YOLO_ROOT)
    p.add_argument("--output-dir", type=Path, default=OUT_ROOT)
    p.add_argument("--crop-size", type=int, default=CROP_SIZE)
    p.add_argument("--padding", type=float, default=PAD)
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def yolo_box_to_pixels(w: int, h: int, xc: float, yc: float, bw: float, bh: float, pad: float) -> tuple[int, int, int, int]:
    px = (xc - bw / 2 - bw * pad) * w
    py = (yc - bh / 2 - bh * pad) * h
    pw = (bw * (1 + 2 * pad)) * w
    ph = (bh * (1 + 2 * pad)) * h
    left = max(0, int(px))
    top = max(0, int(py))
    right = min(w, int(px + pw))
    bottom = min(h, int(py + ph))
    if right - left < 32 or bottom - top < 32:
        return 0, 0, 0, 0
    return left, top, right, bottom


def read_label(path: Path) -> list[tuple[int, float, float, float, float]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        rows.append((int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])))
    return rows


def save_crop(img: Image.Image, box: tuple[int, int, int, int], out_path: Path, size: int) -> bool:
    l, t, r, b = box
    if r <= l or b <= t:
        return False
    crop = img.crop((l, t, r, b))
    crop = crop.resize((size, size), Image.Resampling.BILINEAR)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out_path, quality=92)
    return True


def main() -> int:
    args = parse_args()
    yolo = args.yolo_dir
    out = args.output_dir

    if args.force and out.exists():
        import shutil
        shutil.rmtree(out)

    counts: dict[str, int] = {c: 0 for c in CLASS_NAMES}
    counts["none"] = 0

    for split in SPLITS:
        img_dir = yolo / "images" / split
        lbl_dir = yolo / "labels" / split
        if not img_dir.is_dir():
            continue

        for img_path in sorted(img_dir.iterdir()):
            if img_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            rows = read_label(lbl_path)

            with Image.open(img_path) as raw:
                img = ImageOps.exif_transpose(raw).convert("RGB")
                w, h = img.size

                if not rows:
                    dest = out / "none" / f"{split}__{img_path.stem}{img_path.suffix.lower()}"
                    full = img.resize((args.crop_size, args.crop_size), Image.Resampling.BILINEAR)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    full.save(dest, quality=92)
                    counts["none"] += 1
                    continue

                for idx, (cls_id, xc, yc, bw, bh) in enumerate(rows):
                    if cls_id not in range(len(CLASS_NAMES)):
                        continue
                    class_name = CLASS_NAMES[cls_id]
                    box = yolo_box_to_pixels(w, h, xc, yc, bw, bh, args.padding)
                    dest = out / class_name / f"{split}__{img_path.stem}__{idx}{img_path.suffix.lower()}"
                    if save_crop(img, box, dest, args.crop_size):
                        counts[class_name] += 1

    print("=" * 60)
    print("Stage-2 crop dataset ready:", out)
    for name in CLASS_NAMES + ["none"]:
        print(f"  {name}: {counts[name]}")
    print()
    print("Train classifier:")
    print("  python tools/build_huf_banknote_model.py --dataset-dir tools/banknote_dataset_crops --epochs 20")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())