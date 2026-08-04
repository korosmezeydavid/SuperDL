#!/usr/bin/env python3
"""Prepare a YOLO detection dataset from Super DL banknote source folders.

Source layout (classifier-style, already used by build_huf_banknote_model.py):

  tools/banknote_dataset/
    huf_500/     *.jpg
    huf_1000/    *.jpg
    ...
    huf_20000/   *.jpg
    none/        *.jpg   (hard negatives – no banknote)

Output layout (Ultralytics YOLO):

  tools/banknote_yolo/
    data.yaml
    images/{train,val,test}/
    labels/{train,val,test}/

Bounding-box modes:
  opencv   – detect largest note-like contour (recommended for phone photos)
  margin   – shrink full frame by margin (good for Wikimedia scan crops)
  full     – nearly full-frame box (legacy / flat scans only)
  existing – read YOLO .txt from --labels-dir (same stem as image)

Examples:
  python tools/prepare_banknote_yolo_dataset.py
  python tools/prepare_banknote_yolo_dataset.py --bbox-mode opencv --train-ratio 0.7
  python tools/prepare_banknote_yolo_dataset.py --source-dir tools/banknote_dataset --dry-run
  python tools/prepare_banknote_yolo_dataset.py --labels-dir tools/banknote_dataset_labels
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow required: pip install pillow") from exc

try:
    import cv2
    import numpy as np

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = TOOLS_DIR / "banknote_dataset"
DEFAULT_OUTPUT = TOOLS_DIR / "banknote_yolo"
NEGATIVE_FOLDER = "none"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# Must match BanknoteDenomination.labelKey in the Android app.
CLASS_NAMES = [
    "huf_500",
    "huf_1000",
    "huf_2000",
    "huf_5000",
    "huf_10000",
    "huf_20000",
]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
DENOMINATIONS_HUF = [500, 1000, 2000, 5000, 10000, 20000]


@dataclass
class Sample:
    source_path: Path
    class_name: str | None  # None = hard negative
    split: str = ""
    dest_stem: str = ""
    bbox_mode: str = "opencv"
    bbox: tuple[float, float, float, float] | None = None  # x,y,w,h normalized
    label_source: str = ""
    notes: str = ""


@dataclass
class BuildReport:
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build YOLO HUF banknote dataset for Super DL.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=None,
        help="Optional folder with pre-made YOLO labels (mirrors source tree or flat).",
    )
    parser.add_argument(
        "--bbox-mode",
        choices=["opencv", "margin", "full", "existing"],
        default="opencv",
        help="How to create boxes when no manual label exists.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--margin", type=float, default=0.04, help="Margin bbox inset (0-0.2).")
    parser.add_argument("--min-box-area", type=float, default=0.08, help="Min box area fraction.")
    parser.add_argument("--copy-mode", choices=["copy", "hardlink", "symlink"], default="copy")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite output images/labels.")
    return parser.parse_args()


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    return sorted(files, key=lambda p: p.name.lower())


def load_image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        return img.size  # width, height


def clamp_box(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    w = max(0.01, min(w, 1.0))
    h = max(0.01, min(h, 1.0))
    x = max(w / 2, min(x, 1.0 - w / 2))
    y = max(h / 2, min(y, 1.0 - h / 2))
    return x, y, w, h


def bbox_full_frame(margin: float) -> tuple[float, float, float, float]:
    inset = margin
    w = 1.0 - 2 * inset
    h = 1.0 - 2 * inset
    return clamp_box(0.5, 0.5, w, h)


def bbox_margin_frame(margin: float) -> tuple[float, float, float, float]:
    return bbox_full_frame(margin)


def bbox_opencv(image_path: Path, min_area: float) -> tuple[float, float, float, float] | None:
    if not HAS_CV2:
        return None
    data = np.fromfile(str(image_path), dtype=np.uint8)
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    h_img, w_img = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 140)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    best = None
    best_score = 0.0
    img_area = float(w_img * h_img)
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = float(bw * bh)
        if area < img_area * min_area or area > img_area * 0.98:
            continue
        aspect = bw / max(bh, 1)
        if aspect < 0.35 or aspect > 3.2:
            continue
        rectangularity = area / max(cv2.contourArea(cnt), 1.0)
        score = area * min(rectangularity, 2.0)
        if score > best_score:
            best_score = score
            best = (x, y, bw, bh)

    if best is None:
        return None
    x, y, bw, bh = best
    xc = (x + bw / 2) / w_img
    yc = (y + bh / 2) / h_img
    return clamp_box(xc, yc, bw / w_img, bh / h_img)


def read_existing_label(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    if not label_path.is_file():
        return []
    rows: list[tuple[int, float, float, float, float]] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(parts[0])
        coords = tuple(float(v) for v in parts[1:])
        rows.append((cls, *coords))  # type: ignore[arg-type]
    return rows


def find_existing_label(labels_dir: Path, source_root: Path, image_path: Path) -> Path | None:
    rel = image_path.relative_to(source_root)
    candidates = [
        labels_dir / rel.with_suffix(".txt"),
        labels_dir / f"{rel.parent.name}_{image_path.stem}.txt",
        labels_dir / f"{image_path.stem}.txt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def choose_primary_box(
    rows: list[tuple[int, float, float, float, float]],
    expected_class: int | None,
) -> tuple[float, float, float, float] | None:
    if not rows:
        return None
    if expected_class is not None:
        matching = [r for r in rows if r[0] == expected_class]
        if matching:
            rows = matching
    _, x, y, w, h = max(rows, key=lambda r: r[3] * r[4])
    return clamp_box(x, y, w, h)


def make_dest_stem(class_name: str | None, source_path: Path) -> str:
    prefix = class_name or NEGATIVE_FOLDER
    digest = hashlib.md5(str(source_path.resolve()).encode("utf-8")).hexdigest()[:8]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in source_path.stem)
    return f"{prefix}__{safe}__{digest}"


def stratified_split(
    items: list[Sample],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> None:
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Split ratios must sum to 1.0, got {total}")
    rng = random.Random(seed)
    buckets: dict[str | None, list[Sample]] = {}
    for item in items:
        buckets.setdefault(item.class_name, []).append(item)

    for group in buckets.values():
        rng.shuffle(group)
        n = len(group)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        if n_train + n_val > n:
            n_val = max(0, n - n_train)
        n_test = n - n_train - n_val
        if n >= 3 and n_test == 0:
            n_test = 1
            if n_train > n_val:
                n_train -= 1
            else:
                n_val = max(0, n_val - 1)
        for idx, sample in enumerate(group):
            if idx < n_train:
                sample.split = "train"
            elif idx < n_train + n_val:
                sample.split = "val"
            else:
                sample.split = "test"


def collect_samples(args: argparse.Namespace, report: BuildReport) -> list[Sample]:
    source_dir: Path = args.source_dir
    if not source_dir.is_dir():
        raise SystemExit(f"Source directory not found: {source_dir}")

    samples: list[Sample] = []
    seen_hashes: set[str] = set()

    class_folders = [f for f in CLASS_NAMES if (source_dir / f).is_dir()]
    if not class_folders:
        report.warnings.append(f"No denomination folders found under {source_dir}")

    for class_name in CLASS_NAMES:
        folder = source_dir / class_name
        for image_path in list_images(folder):
            digest = hashlib.md5(image_path.read_bytes()).hexdigest()
            if digest in seen_hashes:
                report.skipped.append(f"duplicate-bytes: {image_path}")
                continue
            seen_hashes.add(digest)
            samples.append(
                Sample(
                    source_path=image_path,
                    class_name=class_name,
                    bbox_mode=args.bbox_mode,
                    dest_stem=make_dest_stem(class_name, image_path),
                )
            )

    none_folder = source_dir / NEGATIVE_FOLDER
    for image_path in list_images(none_folder):
        digest = hashlib.md5(image_path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            report.skipped.append(f"duplicate-bytes: {image_path}")
            continue
        seen_hashes.add(digest)
        samples.append(
            Sample(
                source_path=image_path,
                class_name=None,
                bbox_mode=args.bbox_mode,
                dest_stem=make_dest_stem(None, image_path),
            )
        )

    if not samples:
        raise SystemExit(f"No images found in {source_dir}")

    stratified_split(samples, args.train_ratio, args.val_ratio, args.test_ratio, args.seed)
    resolve_bboxes(samples, args, report)
    return samples


def resolve_bboxes(samples: list[Sample], args: argparse.Namespace, report: BuildReport) -> None:
    labels_dir: Path | None = args.labels_dir
    for sample in samples:
        if sample.class_name is None:
            sample.bbox = None
            sample.label_source = "negative-empty"
            continue

        expected_id = CLASS_TO_ID[sample.class_name]
        if args.bbox_mode == "existing" and labels_dir is not None:
            label_path = find_existing_label(labels_dir, args.source_dir, sample.source_path)
            if label_path is None:
                report.warnings.append(f"missing label for {sample.source_path}")
                sample.bbox = bbox_margin_frame(args.margin)
                sample.label_source = "fallback-margin"
                continue
            rows = read_existing_label(label_path)
            box = choose_primary_box(rows, expected_id)
            if box is None:
                report.warnings.append(f"empty label file: {label_path}")
                sample.bbox = bbox_margin_frame(args.margin)
                sample.label_source = "fallback-margin"
            else:
                sample.bbox = box
                sample.label_source = "manual"
            continue

        if args.bbox_mode == "full":
            sample.bbox = bbox_full_frame(0.02)
            sample.label_source = "auto-full"
        elif args.bbox_mode == "margin":
            sample.bbox = bbox_margin_frame(args.margin)
            sample.label_source = "auto-margin"
        elif args.bbox_mode == "opencv":
            box = bbox_opencv(sample.source_path, args.min_box_area)
            if box is None:
                sample.bbox = bbox_margin_frame(args.margin)
                sample.label_source = "auto-margin-fallback"
                report.warnings.append(f"opencv bbox failed, margin fallback: {sample.source_path}")
            else:
                sample.bbox = box
                sample.label_source = "auto-opencv"
        else:
            raise ValueError(f"Unsupported bbox mode: {args.bbox_mode}")


def transfer_file(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    if mode == "copy":
        shutil.copy2(src, dst)
    elif mode == "hardlink":
        try:
            dst.hardlink_to(src)
        except OSError:
            shutil.copy2(src, dst)
    elif mode == "symlink":
        dst.symlink_to(src.resolve())
    else:
        raise ValueError(mode)


def write_label(path: Path, class_id: int, bbox: tuple[float, float, float, float]) -> None:
    x, y, w, h = bbox
    path.write_text(f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n", encoding="utf-8")


def write_data_yaml(output_dir: Path, path_style: str = "absolute") -> None:
    if path_style == "absolute":
        path_value = str(output_dir.resolve()).replace("\\", "/")
    else:
        path_value = output_dir.name

    yaml_text = f"""# Super DL – Hungarian Forint (HUF) YOLO detection dataset
# Auto-generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
# Regenerate: python tools/prepare_banknote_yolo_dataset.py

path: {path_value}
train: images/train
val: images/val
test: images/test

nc: {len(CLASS_NAMES)}
names:
"""
    for idx, name in enumerate(CLASS_NAMES):
        yaml_text += f"  {idx}: {name}\n"

    yaml_text += f"""
# --- Super DL metadata ---
project: SuperDL-Android
task: detect
currency: HUF
denominations_huf: {DENOMINATIONS_HUF}
negative_class_folder: {NEGATIVE_FOLDER}
class_ids:
"""
    for name, idx in CLASS_TO_ID.items():
        yaml_text += f"  {name}: {idx}\n"

    yaml_text += """
recommended_inference:
  conf_threshold: 0.55
  iou_threshold: 0.45
  multi_frame_agreement: 3
  multi_frame_window: 5
safety_note: >
  Financial accessibility feature: abstain when uncertain.
  A wrong denomination is worse than silence.
"""
    (output_dir / "data.yaml").write_text(yaml_text, encoding="utf-8")


def materialize_dataset(samples: list[Sample], args: argparse.Namespace, report: BuildReport) -> None:
    output_dir: Path = args.output_dir
    splits = ("train", "val", "test")

    if args.force and not args.dry_run:
        for split in splits:
            shutil.rmtree(output_dir / "images" / split, ignore_errors=True)
            shutil.rmtree(output_dir / "labels" / split, ignore_errors=True)

    manifest: list[dict[str, object]] = []

    for sample in samples:
        split = sample.split
        ext = sample.source_path.suffix.lower()
        image_dst = output_dir / "images" / split / f"{sample.dest_stem}{ext}"
        label_dst = output_dir / "labels" / split / f"{sample.dest_stem}.txt"

        key = sample.class_name or NEGATIVE_FOLDER
        report.counts.setdefault(split, {})
        report.counts[split][key] = report.counts[split].get(key, 0) + 1

        manifest.append(
            {
                "split": split,
                "class": key,
                "source": str(sample.source_path),
                "image_dest": str(image_dst),
                "label_dest": str(label_dst),
                "bbox": sample.bbox,
                "label_source": sample.label_source,
            }
        )

        if args.dry_run:
            continue

        transfer_file(sample.source_path, image_dst, args.copy_mode)
        label_dst.parent.mkdir(parents=True, exist_ok=True)
        if sample.class_name is None:
            label_dst.write_text("", encoding="utf-8")
        else:
            assert sample.bbox is not None
            write_label(label_dst, CLASS_TO_ID[sample.class_name], sample.bbox)

    if not args.dry_run:
        write_data_yaml(output_dir, path_style="absolute")
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (output_dir / "README.txt").write_text(
            README_TEXT.format(
                generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                source=args.source_dir,
            ),
            encoding="utf-8",
        )


README_TEXT = """Super DL – HUF YOLO dataset
Generated: {generated}
Source: {source}

Train:
  cd tools
  yolo detect train data=banknote_yolo/data.yaml model=yolo11n.pt imgsz=640 epochs=150 patience=25

Validate:
  yolo detect val data=banknote_yolo/data.yaml model=runs/detect/train/weights/best.pt

Export TFLite (Android):
  yolo export model=runs/detect/train/weights/best.pt format=tflite imgsz=640 int8

Manual label correction:
  1. Fix boxes in LabelImg / CVAT / Roboflow
  2. Re-run with --bbox-mode existing --labels-dir <your_labels>
"""


def print_report(samples: list[Sample], report: BuildReport, args: argparse.Namespace) -> None:
    print("=" * 72)
    print("Super DL – HUF YOLO dataset preparation")
    print("=" * 72)
    print(f"Source:     {args.source_dir}")
    print(f"Output:     {args.output_dir}")
    print(f"Bbox mode:  {args.bbox_mode}" + ("" if HAS_CV2 or args.bbox_mode != "opencv" else " (OpenCV missing → margin fallback)"))
    print(f"Samples:    {len(samples)}")
    print(f"Splits:     train={args.train_ratio:.0%} val={args.val_ratio:.0%} test={args.test_ratio:.0%}")
    print()
    print("Per-split counts:")
    for split in ("train", "val", "test"):
        counts = report.counts.get(split, {})
        parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"  {split:5s}: {parts if parts else '(none)'}")
    if report.warnings:
        print()
        print(f"Warnings ({len(report.warnings)}):")
        for msg in report.warnings[:12]:
            print(f"  - {msg}")
        if len(report.warnings) > 12:
            print(f"  ... and {len(report.warnings) - 12} more")
    if report.skipped:
        print()
        print(f"Skipped ({len(report.skipped)}):")
        for msg in report.skipped[:8]:
            print(f"  - {msg}")
    print()
    if args.dry_run:
        print("DRY RUN – no files written.")
    else:
        print(f"Wrote: {args.output_dir / 'data.yaml'}")
        print(f"Wrote: {args.output_dir / 'manifest.json'}")
    print("=" * 72)


def main() -> int:
    args = parse_args()
    if args.bbox_mode == "opencv" and not HAS_CV2:
        print("Warning: opencv-python not installed; margin fallback will be used.", file=sys.stderr)
        print("Install: pip install opencv-python-headless", file=sys.stderr)

    report = BuildReport()
    samples = collect_samples(args, report)
    materialize_dataset(samples, args, report)
    print_report(samples, report, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())