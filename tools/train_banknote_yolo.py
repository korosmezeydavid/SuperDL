#!/usr/bin/env python3
"""Train a YOLO banknote detector for Super DL (HUF denominations).

Wraps the Ultralytics training pipeline with banknote-safe defaults:
  - Lighting augmentation (HSV brightness / saturation / hue)
  - Rotation + perspective (no horizontal flip — notes are asymmetric)
  - Erasing / mosaic for partial occlusion robustness
  - Hard-negative handling (empty-label background images)

Prerequisites:
  pip install ultralytics pillow opencv-python-headless

Typical workflow:
  1. Add photos to tools/banknote_dataset/<class>/
  2. python tools/prepare_banknote_yolo_dataset.py --bbox-mode opencv --force
  3. python tools/train_banknote_yolo.py
  4. python tools/train_banknote_yolo.py --export-tflite --weights runs/banknote/huf_detect/weights/best.pt

Examples:
  python tools/train_banknote_yolo.py --prepare --bbox-mode opencv
  python tools/train_banknote_yolo.py --model yolo11s.pt --epochs 200 --negative-boost 3
  python tools/train_banknote_yolo.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_YAML = TOOLS_DIR / "banknote_yolo" / "data.yaml"
DEFAULT_SOURCE = TOOLS_DIR / "banknote_dataset"
DEFAULT_PROJECT = TOOLS_DIR / "runs" / "banknote"
DETECTOR_ASSET = TOOLS_DIR.parent / "app" / "src" / "main" / "assets" / "huf_banknote_detector.tflite"
NEGATIVE_FOLDER = "none"
CLASS_NAMES = [
    "huf_500",
    "huf_1000",
    "huf_2000",
    "huf_5000",
    "huf_10000",
    "huf_20000",
]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class DatasetStats:
    train_positives: int = 0
    train_negatives: int = 0
    val_positives: int = 0
    val_negatives: int = 0
    test_positives: int = 0
    test_negatives: int = 0
    per_class_train: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def train_total(self) -> int:
        return self.train_positives + self.train_negatives

    @property
    def negative_ratio(self) -> float:
        if self.train_positives == 0:
            return 0.0
        return self.train_negatives / self.train_positives


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Super DL HUF YOLO detector.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_YAML, help="data.yaml path")
    parser.add_argument("--model", default="yolo11n.pt", help="Base checkpoint (yolo11n.pt, yolo11s.pt, …)")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--patience", type=int, default=25, help="Early-stop patience")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="", help="cuda device id, cpu, or empty=auto")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--name", default="huf_detect", help="Run name under project/")
    parser.add_argument("--resume", action="store_true", help="Resume last run")
    parser.add_argument("--dry-run", action="store_true", help="Validate config only, do not train")

    # Dataset preparation
    parser.add_argument("--prepare", action="store_true", help="Run prepare_banknote_yolo_dataset.py first")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--bbox-mode", choices=["opencv", "margin", "full", "existing"], default="opencv")

    # Hard negatives
    parser.add_argument(
        "--negative-boost",
        type=int,
        default=2,
        metavar="N",
        help="Duplicate hard-negative train images N times (reduces false positives). 0=off.",
    )
    parser.add_argument(
        "--min-negative-ratio",
        type=float,
        default=0.5,
        help="Warn if train negatives:positives ratio is below this.",
    )

    # Augmentation overrides (banknote-safe defaults applied when left None)
    parser.add_argument("--degrees", type=float, default=None, help="Rotation ±degrees (default 15)")
    parser.add_argument("--mosaic", type=float, default=None, help="Mosaic probability (default auto)")
    parser.add_argument("--mixup", type=float, default=None, help="MixUp probability (default 0.08)")
    parser.add_argument("--erasing", type=float, default=None, help="Random erasing (occlusion sim, default 0.18)")

    # Export
    parser.add_argument("--export-tflite", action="store_true", help="Export best.pt to TFLite after training")
    parser.add_argument("--weights", type=Path, default=None, help="Weights for --export-tflite only mode")
    parser.add_argument("--int8", action="store_true", help="INT8 TFLite export (needs calibration data)")
    return parser.parse_args()


def label_path_for_image(image_path: Path) -> Path:
    parts = list(image_path.parts)
    if "images" in parts:
        idx = parts.index("images")
        parts[idx] = "labels"
        return Path(*parts).with_suffix(".txt")
    return image_path.with_suffix(".txt")


def is_negative_label(label_path: Path) -> bool:
    if not label_path.is_file():
        return True
    content = label_path.read_text(encoding="utf-8").strip()
    return content == ""


def count_split(data_root: Path, split: str, stats: DatasetStats) -> None:
    images_dir = data_root / "images" / split
    if not images_dir.is_dir():
        stats.warnings.append(f"Missing split folder: {images_dir}")
        return

    for image_path in sorted(images_dir.iterdir()):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        label_path = label_path_for_image(image_path)
        negative = is_negative_label(label_path)

        if split == "train":
            if negative:
                stats.train_negatives += 1
            else:
                stats.train_positives += 1
                cls = _class_from_label(label_path)
                if cls:
                    stats.per_class_train[cls] = stats.per_class_train.get(cls, 0) + 1
        elif split == "val":
            if negative:
                stats.val_negatives += 1
            else:
                stats.val_positives += 1
        elif split == "test":
            if negative:
                stats.test_negatives += 1
            else:
                stats.test_positives += 1


def _class_from_label(label_path: Path) -> str | None:
    if not label_path.is_file():
        return None
    first = label_path.read_text(encoding="utf-8").strip().splitlines()
    if not first:
        return None
    try:
        class_id = int(first[0].split()[0])
        if 0 <= class_id < len(CLASS_NAMES):
            return CLASS_NAMES[class_id]
    except (ValueError, IndexError):
        pass
    return None


def resolve_data_root(data_yaml: Path) -> Path:
    if not data_yaml.is_file():
        raise SystemExit(f"data.yaml not found: {data_yaml}")
    return data_yaml.parent


def analyze_dataset(data_root: Path, min_negative_ratio: float) -> DatasetStats:
    stats = DatasetStats()
    for split in ("train", "val", "test"):
        count_split(data_root, split, stats)

    if stats.train_negatives == 0:
        stats.warnings.append(
            "No hard negatives in train split. Add images to "
            f"{DEFAULT_SOURCE / NEGATIVE_FOLDER}/ and re-run prepare script."
        )
    elif stats.negative_ratio < min_negative_ratio:
        stats.warnings.append(
            f"Low negative ratio: {stats.negative_ratio:.2f} "
            f"(target ≥ {min_negative_ratio:.2f}). Use --negative-boost or add more none/ photos."
        )

    for cls in CLASS_NAMES:
        count = stats.per_class_train.get(cls, 0)
        if count < 30:
            stats.warnings.append(f"Low train count for {cls}: {count} (target ≥ 30 for production)")

    if stats.train_positives < 50:
        stats.warnings.append(
            f"Small dataset ({stats.train_positives} positive train images). "
            "Expect to rely on abstention thresholds in the Android app."
        )
    return stats


def boost_hard_negatives(data_root: Path, boost: int) -> int:
    """Duplicate empty-label train images to strengthen false-positive suppression."""
    if boost <= 1:
        return 0

    train_images = data_root / "images" / "train"
    train_labels = data_root / "labels" / "train"
    added = 0

    for image_path in sorted(train_images.iterdir()):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        label_path = train_labels / f"{image_path.stem}.txt"
        if not is_negative_label(label_path):
            continue

        for copy_idx in range(1, boost):
            stem = f"{image_path.stem}__negboost{copy_idx}"
            dst_img = train_images / f"{stem}{image_path.suffix.lower()}"
            dst_lbl = train_labels / f"{stem}.txt"
            if dst_img.exists():
                continue
            shutil.copy2(image_path, dst_img)
            dst_lbl.write_text("", encoding="utf-8")
            added += 1
    return added


def inject_source_negatives(data_root: Path, source_dir: Path, boost: int) -> int:
    """Pull none/ photos from source into train if missing from YOLO split."""
    none_dir = source_dir / NEGATIVE_FOLDER
    if not none_dir.is_dir():
        return 0

    train_images = data_root / "images" / "train"
    train_labels = data_root / "labels" / "train"
    train_images.mkdir(parents=True, exist_ok=True)
    train_labels.mkdir(parents=True, exist_ok=True)

    existing_stems = {p.stem for p in train_images.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES}
    added = 0

    for image_path in sorted(none_dir.iterdir()):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        base_stem = f"{NEGATIVE_FOLDER}__{image_path.stem}"
        for copy_idx in range(boost):
            stem = base_stem if copy_idx == 0 else f"{base_stem}__b{copy_idx}"
            if stem in existing_stems:
                continue
            dst_img = train_images / f"{stem}{image_path.suffix.lower()}"
            dst_lbl = train_labels / f"{stem}.txt"
            shutil.copy2(image_path, dst_img)
            dst_lbl.write_text("", encoding="utf-8")
            existing_stems.add(stem)
            added += 1
    return added


def auto_mosaic(train_positives: int) -> float:
    if train_positives < 80:
        return 0.55
    if train_positives < 200:
        return 0.70
    return 0.80


def build_train_kwargs(args: argparse.Namespace, stats: DatasetStats) -> dict:
    """Banknote-safe Ultralytics training configuration."""
    mosaic = args.mosaic if args.mosaic is not None else auto_mosaic(stats.train_positives)
    mixup = args.mixup if args.mixup is not None else 0.08
    erasing = args.erasing if args.erasing is not None else 0.18
    degrees = args.degrees if args.degrees is not None else 15.0

    return {
        # --- Core ---
        "data": str(args.data.resolve()),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "patience": args.patience,
        "seed": args.seed,
        "device": args.device or None,
        "workers": args.workers,
        "project": str(args.project.resolve()),
        "name": args.name,
        "resume": args.resume,
        "pretrained": True,
        "verbose": True,
        "plots": True,
        "save": True,
        "val": True,
        # --- Optimizer ---
        "optimizer": "AdamW",
        "lr0": 0.008,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_epochs": 3.0,
        "cos_lr": True,
        # --- Loss weights (denomination confusion is costly) ---
        "box": 7.5,
        "cls": 1.25,
        "dfl": 1.5,
        # --- Lighting augmentation (low light, yellow lamp, sunlight) ---
        "hsv_h": 0.012,   # small hue shift — color is a denomination cue
        "hsv_s": 0.55,    # saturation swings (faded vs vivid notes)
        "hsv_v": 0.45,    # brightness swings (shadow, low light, glare)
        # --- Geometry (no fliplr — Hungarian notes are asymmetric) ---
        "degrees": degrees,
        "translate": 0.12,
        "scale": 0.45,
        "shear": 2.0,
        "perspective": 0.0006,
        "flipud": 0.0,
        "fliplr": 0.0,
        # --- Composition augmentation ---
        "mosaic": mosaic,
        "mixup": mixup,
        "copy_paste": 0.06,
        # --- Occlusion simulation (fingers, corners) ---
        "erasing": erasing,
        # --- Mosaic schedule: less synthetic warp late in training ---
        "close_mosaic": max(15, args.epochs // 5),
        # --- Inference-aligned NMS (used during val) ---
        "iou": 0.55,
        "max_det": 3,
    }


def run_prepare(args: argparse.Namespace) -> None:
    script = TOOLS_DIR / "prepare_banknote_yolo_dataset.py"
    cmd = [
        sys.executable,
        str(script),
        "--source-dir",
        str(args.source_dir),
        "--output-dir",
        str(args.data.parent),
        "--bbox-mode",
        args.bbox_mode,
        "--force",
    ]
    print("Running dataset preparation...")
    subprocess.run(cmd, check=True)


def print_preflight(stats: DatasetStats, kwargs: dict, args: argparse.Namespace) -> None:
    print("=" * 72)
    print("Super DL – HUF YOLO training")
    print("=" * 72)
    print(f"data:       {args.data}")
    print(f"model:      {args.model}")
    print(f"epochs:     {args.epochs}  patience: {args.patience}")
    print(f"imgsz:      {args.imgsz}  batch: {args.batch}")
    print()
    print("Dataset:")
    print(f"  train:  {stats.train_positives} positives, {stats.train_negatives} hard negatives")
    print(f"  val:    {stats.val_positives} positives, {stats.val_negatives} hard negatives")
    print(f"  test:   {stats.test_positives} positives, {stats.test_negatives} hard negatives")
    print(f"  neg/pos ratio (train): {stats.negative_ratio:.2f}")
    if stats.per_class_train:
        print("  per-class train:", ", ".join(f"{k}={v}" for k, v in sorted(stats.per_class_train.items())))
    print()
    print("Augmentation (banknote-safe):")
    aug_keys = (
        "hsv_h", "hsv_s", "hsv_v", "degrees", "translate", "scale",
        "perspective", "flipud", "fliplr", "mosaic", "mixup", "copy_paste", "erasing", "close_mosaic",
    )
    for key in aug_keys:
        print(f"  {key}: {kwargs[key]}")
    print()
    if stats.warnings:
        print(f"Warnings ({len(stats.warnings)}):")
        for w in stats.warnings:
            print(f"  ! {w}")
        print()
    print("Hard-negative policy:")
    print("  - Empty .txt label = background (model learns NOT to fire)")
    print("  - Mosaic mixes negatives with positives → fewer false positives on tables/fabric")
    print("  - fliplr=0, flipud=0 → preserves obverse/reverse asymmetry")
    print("=" * 72)


def save_run_manifest(args: argparse.Namespace, stats: DatasetStats, kwargs: dict, extra: dict) -> None:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_yaml": str(args.data.resolve()),
        "model": args.model,
        "dataset_stats": {
            "train_positives": stats.train_positives,
            "train_negatives": stats.train_negatives,
            "negative_ratio": round(stats.negative_ratio, 4),
            "per_class_train": stats.per_class_train,
        },
        "train_kwargs": {k: v for k, v in kwargs.items() if v is not None},
        "extra": extra,
        "warnings": stats.warnings,
        "inference_defaults": {
            "conf": 0.55,
            "iou": 0.45,
            "multi_frame_agreement": 3,
            "multi_frame_window": 5,
        },
    }
    args.project.mkdir(parents=True, exist_ok=True)
    out = args.project / f"{args.name}_train_manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest: {out}")


def train_model(args: argparse.Namespace, kwargs: dict) -> Path:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("ultralytics required: pip install ultralytics") from exc

    model = YOLO(args.model)
    results = model.train(**kwargs)
    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.is_file():
        best = Path(kwargs["project"]) / kwargs["name"] / "weights" / "best.pt"
    print(f"Best weights: {best}")
    return best


def find_detector_tflite(weights_dir: Path | None = None, project: Path = DEFAULT_PROJECT) -> Path | None:
    search_roots: list[Path] = []
    if weights_dir and weights_dir.is_dir():
        search_roots.append(weights_dir)
        if weights_dir.parent.is_dir():
            search_roots.append(weights_dir.parent)
    if project.is_dir():
        for run in sorted(
            (p for p in project.iterdir() if p.is_dir() and p.name.startswith("huf_detect")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            search_roots.extend((run / "weights", run))
    for base in search_roots:
        for pattern in ("best_saved_model/*.tflite", "best.tflite", "*.tflite"):
            hits = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            if hits:
                return hits[0]
    return None


def copy_detector_to_assets(weights_dir: Path | None = None) -> Path | None:
    src = find_detector_tflite(weights_dir)
    if not src:
        print("Warning: no detector TFLite to copy into Android assets.")
        return None
    DETECTOR_ASSET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DETECTOR_ASSET)
    print(f"Detector → {DETECTOR_ASSET}  (from {src})")
    return DETECTOR_ASSET


def export_tflite(weights: Path, imgsz: int, int8: bool) -> Path | None:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("ultralytics required: pip install ultralytics") from exc

    model = YOLO(str(weights))
    export_kwargs = {"format": "tflite", "imgsz": imgsz}
    if int8:
        export_kwargs["int8"] = True
    out = model.export(**export_kwargs)
    print(f"TFLite export: {out}")
    return Path(out) if out else find_detector_tflite(weights.parent)


def main() -> int:
    args = parse_args()

    if args.prepare:
        run_prepare(args)

    data_root = resolve_data_root(args.data)
    stats = analyze_dataset(data_root, args.min_negative_ratio)

    injected = inject_source_negatives(data_root, args.source_dir, max(1, args.negative_boost))
    boosted = boost_hard_negatives(data_root, args.negative_boost)
    if injected or boosted:
        stats = analyze_dataset(data_root, args.min_negative_ratio)
        print(f"Hard negatives: injected {injected}, boosted {boosted}")

    kwargs = build_train_kwargs(args, stats)
    print_preflight(stats, kwargs, args)

    extra = {"injected_negatives": injected, "boosted_negatives": boosted}

    if args.dry_run:
        save_run_manifest(args, stats, kwargs, extra)
        print("DRY RUN – training skipped.")
        return 0

    save_run_manifest(args, stats, kwargs, extra)

    if args.export_tflite and args.weights:
        export_tflite(args.weights, args.imgsz, args.int8)
        copy_detector_to_assets(args.weights.parent)
        return 0

    best = train_model(args, kwargs)

    if args.export_tflite:
        export_tflite(best, args.imgsz, args.int8)
        copy_detector_to_assets(best.parent)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())