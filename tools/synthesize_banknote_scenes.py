#!/usr/bin/env python3
"""Synthesize phone-like banknote photos from Wikimedia reference scans.

Cash Reader–style apps train on huge augmented datasets. Without your own photos,
we composite flat scans onto random backgrounds with lighting, blur, rotation,
perspective and finger-like occlusion — then feed YOLO + classifier pipeline.

Run:
  python tools/download_banknote_dataset.py
  python tools/synthesize_banknote_scenes.py
  python tools/train_banknote_full_pipeline.py
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
except ImportError as exc:
    raise SystemExit("pip install pillow numpy") from exc

TOOLS = Path(__file__).resolve().parent
SOURCE = TOOLS / "banknote_dataset"
OUT = TOOLS / "banknote_dataset_synth"
CLASS_NAMES = ["huf_500", "huf_1000", "huf_2000", "huf_5000", "huf_10000", "huf_20000"]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Synthesize in-the-wild banknote training images.")
    p.add_argument("--source-dir", type=Path, default=SOURCE)
    p.add_argument("--output-dir", type=Path, default=OUT)
    p.add_argument("--per-reference", type=int, default=24, help="Synthetic variants per source scan")
    p.add_argument("--none-count", type=int, default=120, help="Hard-negative background images")
    p.add_argument("--size", type=int, default=960, help="Output image longest side")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def list_refs(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES]


def random_background(rng: random.Random, w: int, h: int) -> Image.Image:
    np_rng = np.random.default_rng(rng.randint(0, 2**32 - 1))
    kind = rng.randint(0, 5)
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    if kind == 0:
        base = rng.randint(40, 200)
        arr[:] = (base, base - rng.randint(0, 15), base - rng.randint(0, 25))
    elif kind == 1:
        wood = (rng.randint(80, 140), rng.randint(55, 95), rng.randint(30, 60))
        arr[:] = wood
        arr = arr.astype(np.int16) + np_rng.integers(-18, 18, size=(h, w, 3), dtype=np.int16)
    elif kind == 2:
        arr[:] = (rng.randint(20, 90),) * 3
    elif kind == 3:
        arr[:] = (rng.randint(160, 240),) * 3
    elif kind == 4:
        for y in range(h):
            t = y / max(h - 1, 1)
            arr[y, :] = (
                int(60 + 80 * t),
                int(50 + 70 * t),
                int(40 + 50 * t),
            )
    else:
        arr = np_rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    if rng.random() < 0.4:
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.4, 1.8)))
    return img


def paste_note(bg: Image.Image, note: Image.Image, rng: random.Random) -> tuple[Image.Image, tuple[float, float, float, float]]:
    """Return composited image and normalized YOLO bbox (xc, yc, w, h)."""
    bw, bh = bg.size
    scale = rng.uniform(0.38, 0.78)
    target_w = int(bw * scale)
    aspect = note.width / max(note.height, 1)
    target_h = int(target_w / aspect)
    note = note.resize((target_w, target_h), Image.Resampling.BILINEAR)

    if rng.random() < 0.7:
        angle = rng.uniform(-22, 22)
        note = note.rotate(angle, resample=Image.Resampling.BILINEAR, expand=True, fillcolor=(0, 0, 0, 0))

    if note.mode != "RGBA":
        note = note.convert("RGBA")

    # Lighting on note
    if rng.random() < 0.85:
        enhancer = ImageEnhance.Brightness(note)
        note = enhancer.enhance(rng.uniform(0.55, 1.35))
    if rng.random() < 0.7:
        enhancer = ImageEnhance.Contrast(note)
        note = enhancer.enhance(rng.uniform(0.75, 1.25))
    if rng.random() < 0.5:
        enhancer = ImageEnhance.Color(note)
        note = enhancer.enhance(rng.uniform(0.7, 1.3))

    nw, nh = note.size
    max_x = max(bw - nw, 1)
    max_y = max(bh - nh, 1)
    x = rng.randint(int(bw * 0.05), int(bw * 0.05 + max_x * 0.9))
    y = rng.randint(int(bh * 0.08), int(bh * 0.08 + max_y * 0.85))

    layer = bg.convert("RGBA")
    layer.paste(note, (x, y), note)
    out = layer.convert("RGB")

    # Finger-like occlusion
    if rng.random() < 0.45:
        draw = ImageDraw.Draw(out)
        for _ in range(rng.randint(1, 2)):
            fx0 = x + rng.randint(0, max(nw // 2, 1))
            fy0 = y + rng.randint(0, max(nh // 2, 1))
            fx1 = min(bw, fx0 + rng.randint(nw // 6, nw // 3))
            fy1 = min(bh, fy0 + rng.randint(nh // 6, nh // 3))
            skin = (
                rng.randint(150, 220),
                rng.randint(110, 170),
                rng.randint(90, 140),
            )
            draw.rectangle([fx0, fy0, fx1, fy1], fill=skin)

    xc = (x + nw / 2) / bw
    yc = (y + nh / 2) / bh
    ww = nw / bw
    hh = nh / bh
    return out, (xc, yc, ww, hh)


def augment_note(path: Path) -> Image.Image:
    with Image.open(path) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
    return img


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    out = args.output_dir
    if args.force and out.exists():
        import shutil
        shutil.rmtree(out)

    w = h = args.size
    counts: dict[str, int] = {c: 0 for c in CLASS_NAMES}
    counts["none"] = 0

    for class_name in CLASS_NAMES:
        refs = list_refs(args.source_dir / class_name)
        if not refs:
            print(f"  skip {class_name}: no reference images")
            continue
        dest = out / class_name
        dest.mkdir(parents=True, exist_ok=True)
        for ref in refs:
            note = augment_note(ref)
            for i in range(args.per_reference):
                bg = random_background(rng, w, h)
                scene, _bbox = paste_note(bg, note.copy(), rng)
                if rng.random() < 0.25:
                    scene = scene.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 1.2)))
                fname = f"synth_{ref.stem}_{i:03d}.jpg"
                scene.save(dest / fname, quality=88)
                counts[class_name] += 1

    none_dir = out / "none"
    none_dir.mkdir(parents=True, exist_ok=True)
    clutter_kinds = ["table", "fabric", "dark", "bright", "noise"]
    for i in range(args.none_count):
        bg = random_background(rng, w, h)
        if rng.random() < 0.3:
            draw = ImageDraw.Draw(bg)
            for _ in range(rng.randint(2, 5)):
                x0, y0 = rng.randint(0, w - 80), rng.randint(0, h - 80)
                draw.rectangle(
                    [x0, y0, x0 + rng.randint(40, 160), y0 + rng.randint(20, 100)],
                    fill=(rng.randint(30, 200),) * 3,
                )
        bg.save(none_dir / f"none_{clutter_kinds[i % len(clutter_kinds)]}_{i:03d}.jpg", quality=85)
        counts["none"] += 1

    total = sum(counts.values())
    print("=" * 60)
    print("Synthetic dataset:", out)
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print(f"  TOTAL: {total}")
    print()
    print("Next:")
    print("  python tools/prepare_banknote_yolo_dataset.py --source-dir tools/banknote_dataset_synth --bbox-mode margin --force")
    print("  python tools/train_banknote_full_pipeline.py --skip-yolo  # or full pipeline")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())