#!/usr/bin/env python3
"""Finish banknote pipeline after YOLO training (copy detector → crops → classifier).

Finds the latest huf_detect* run automatically (handles huf_detect-2, etc.).

  python tools/finish_banknote_pipeline.py
  python tools/finish_banknote_pipeline.py --classifier-epochs 30 --augment-factor 8
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ASSETS = TOOLS.parent / "app" / "src" / "main" / "assets"
PROJECT = TOOLS / "runs" / "banknote"
DETECTOR_ASSET = ASSETS / "huf_banknote_detector.tflite"


def find_detector_tflite(project: Path = PROJECT) -> Path | None:
    if not project.is_dir():
        return None
    runs = sorted(
        (p for p in project.iterdir() if p.is_dir() and p.name.startswith("huf_detect")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for run in runs:
        for base in (run / "weights", run):
            if not base.is_dir():
                continue
            for pattern in ("best_saved_model/*.tflite", "best.tflite", "*.tflite"):
                hits = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
                if hits:
                    return hits[0]
    return None


def copy_detector() -> bool:
    src = find_detector_tflite()
    if not src:
        print("Warning: no detector TFLite found; export YOLO first.")
        return False
    DETECTOR_ASSET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DETECTOR_ASSET)
    print(f"Detector → {DETECTOR_ASSET}  (from {src})")
    return True


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Post-YOLO banknote pipeline steps.")
    p.add_argument("--copy-only", action="store_true", help="Only copy detector TFLite to assets")
    p.add_argument("--skip-copy", action="store_true")
    p.add_argument("--skip-crops", action="store_true")
    p.add_argument("--skip-classifier", action="store_true")
    p.add_argument("--classifier-epochs", type=int, default=30)
    p.add_argument("--augment-factor", type=int, default=8)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    py = sys.executable

    if not args.skip_copy:
        copy_detector()

    if args.copy_only:
        return 0

    if not args.skip_crops:
        run([py, str(TOOLS / "prepare_banknote_classifier_crops.py"), "--force"])

    if not args.skip_classifier:
        run([
            py, str(TOOLS / "build_huf_banknote_model.py"),
            "--dataset-dir", str(TOOLS / "banknote_dataset_crops"),
            "--epochs", str(args.classifier_epochs),
            "--augment-factor", str(args.augment_factor),
        ])

    print()
    print("Pipeline complete. Android assets:")
    print(f"  {DETECTOR_ASSET}")
    print(f"  {ASSETS / 'huf_banknote_classifier.tflite'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())