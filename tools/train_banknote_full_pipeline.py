#!/usr/bin/env python3
"""One-shot Super DL banknote training: YOLO detect → crop → classifier → assets.

  python tools/train_banknote_full_pipeline.py
  python tools/train_banknote_full_pipeline.py --skip-yolo   # crops + classifier only
  python tools/train_banknote_full_pipeline.py --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ASSETS = TOOLS.parent / "app" / "src" / "main" / "assets"
DETECTOR_ASSET = ASSETS / "huf_banknote_detector.tflite"


def run(cmd: list[str], dry: bool) -> None:
    print("$", " ".join(cmd))
    if dry:
        return
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Full banknote ML pipeline for Super DL.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-yolo", action="store_true", help="Skip YOLO train; use existing weights/crops source")
    p.add_argument("--no-synthesize", action="store_true", help="Skip synthetic scene generation")
    p.add_argument("--source-dir", type=Path, default=TOOLS / "banknote_dataset_synth")
    p.add_argument("--bbox-mode", default="margin", choices=["opencv", "margin", "full"])
    p.add_argument("--yolo-epochs", type=int, default=150)
    p.add_argument("--classifier-epochs", type=int, default=20)
    p.add_argument("--negative-boost", type=int, default=2)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    py = sys.executable

    # 0) Download Wikimedia references
    run([py, str(TOOLS / "download_banknote_dataset.py")], args.dry_run)

    # 0b) Synthesize phone-like scenes (no own photos needed)
    if not args.no_synthesize:
        run([
            py, str(TOOLS / "synthesize_banknote_scenes.py"),
            "--per-reference", "28", "--none-count", "140", "--force",
        ], args.dry_run)

    # 1) YOLO dataset
    run([
        py, str(TOOLS / "prepare_banknote_yolo_dataset.py"),
        "--source-dir", str(args.source_dir),
        "--bbox-mode", args.bbox_mode, "--force",
    ], args.dry_run)

    if not args.skip_yolo:
        # 2) YOLO train + TFLite export
        run([
            py, str(TOOLS / "train_banknote_yolo.py"),
            "--prepare", "--bbox-mode", args.bbox_mode,
            "--epochs", str(args.yolo_epochs),
            "--negative-boost", str(args.negative_boost),
            "--export-tflite",
        ], args.dry_run)

        if not args.dry_run:
            run([py, str(TOOLS / "finish_banknote_pipeline.py"), "--copy-only"], args.dry_run)

    # 3) Crop dataset for Stage 2
    run([py, str(TOOLS / "prepare_banknote_classifier_crops.py"), "--force"], args.dry_run)

    # 4) Classifier train → assets
    run([
        py, str(TOOLS / "build_huf_banknote_model.py"),
        "--dataset-dir", str(TOOLS / "banknote_dataset_crops"),
        "--epochs", str(args.classifier_epochs),
        "--augment-factor", "6",
    ], args.dry_run)

    print()
    print("Pipeline complete. Android two-stage assets:")
    print(f"  {ASSETS / 'huf_banknote_detector.tflite'}  (YOLO)")
    print(f"  {ASSETS / 'huf_banknote_classifier.tflite'} (classifier)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())