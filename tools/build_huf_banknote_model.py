#!/usr/bin/env python3
"""Train and export the offline HUF banknote TFLite classifier.

Supports synthetic bootstrap data and optional real photos:

  tools/banknote_dataset/
    none/       *.jpg
    huf_500/    *.jpg
    huf_1000/   *.jpg
    ...

Run:
  python tools/build_huf_banknote_model.py
  python tools/build_huf_banknote_model.py --dataset-dir tools/banknote_dataset --epochs 20
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import tensorflow as tf

INPUT_SIZE = 224
NUM_CLASSES = 7
LABELS = [
    "none",
    "huf_500",
    "huf_1000",
    "huf_2000",
    "huf_5000",
    "huf_10000",
    "huf_20000",
]

DENOMINATION_COLORS = {
    1: (210, 145, 55),
    2: (55, 95, 175),
    3: (120, 70, 45),
    4: (175, 185, 55),
    5: (155, 55, 95),
    6: (55, 125, 115),
}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def make_none_sample(rng: np.random.Generator) -> np.ndarray:
    kind = int(rng.integers(0, 6))
    if kind == 0:
        base = rng.integers(18, 55, size=3).astype(np.float32)
        image = rng.normal(loc=base, scale=6.0, size=(INPUT_SIZE, INPUT_SIZE, 3))
    elif kind == 1:
        base = rng.integers(170, 235, size=3).astype(np.float32)
        image = rng.normal(loc=base, scale=8.0, size=(INPUT_SIZE, INPUT_SIZE, 3))
    elif kind == 2:
        wood = np.array([125, 88, 52], dtype=np.float32)
        image = rng.normal(loc=wood, scale=14.0, size=(INPUT_SIZE, INPUT_SIZE, 3))
    elif kind == 3:
        fabric = rng.integers(35, 110, size=3).astype(np.float32)
        image = rng.normal(loc=fabric, scale=18.0, size=(INPUT_SIZE, INPUT_SIZE, 3))
    elif kind == 4:
        base = rng.integers(0, 256, size=3).astype(np.float32)
        image = rng.normal(loc=base, scale=42.0, size=(INPUT_SIZE, INPUT_SIZE, 3))
    else:
        # Homályos, alacsony kontraszt – tipikus gyenge felismerés
        gray = float(rng.integers(80, 160))
        image = rng.normal(loc=gray, scale=10.0, size=(INPUT_SIZE, INPUT_SIZE, 3))

    noise = rng.uniform(-8, 8, size=(INPUT_SIZE, INPUT_SIZE, 3))
    image = np.clip(image + noise, 0, 255)
    return image.astype(np.float32)


def make_banknote_sample(class_id: int, rng: np.random.Generator) -> np.ndarray:
    color = np.array(DENOMINATION_COLORS[class_id], dtype=np.float32)
    image = rng.normal(loc=color, scale=rng.uniform(12.0, 22.0), size=(INPUT_SIZE, INPUT_SIZE, 3))
    margin_x = int(rng.integers(18, 52))
    margin_y = int(rng.integers(22, 62))
    image[:margin_y, :] *= rng.uniform(0.30, 0.68)
    image[-margin_y:, :] *= rng.uniform(0.30, 0.68)
    image[:, :margin_x] *= rng.uniform(0.30, 0.68)
    image[:, -margin_x:] *= rng.uniform(0.30, 0.68)
    gradient = np.linspace(rng.uniform(0.75, 0.90), rng.uniform(1.05, 1.22), INPUT_SIZE, dtype=np.float32)[:, None, None]
    image *= gradient
    strip_x = int(rng.integers(60, 160))
    image[:, strip_x : strip_x + int(rng.integers(6, 14)), :] *= rng.uniform(1.04, 1.30)
    noise = rng.uniform(-18, 18, size=(INPUT_SIZE, INPUT_SIZE, 3))
    image = np.clip(image + noise, 0, 255)
    tensor = tf.convert_to_tensor(image)
    if rng.random() < 0.35:
        tensor = tf.image.adjust_brightness(tensor, float(rng.uniform(-0.18, 0.18)))
    if rng.random() < 0.30:
        tensor = tf.image.adjust_contrast(tensor, float(rng.uniform(0.82, 1.18)))
    if rng.random() < 0.25:
        tensor = tf.image.adjust_saturation(tensor, float(rng.uniform(0.75, 1.25)))
    if rng.random() < 0.20:
        k = int(rng.integers(0, 4))
        if k > 0:
            tensor = tf.image.rot90(tensor, k=k)
    return tf.clip_by_value(tensor, 0.0, 255.0).numpy().astype(np.float32)


def make_sample(class_id: int, rng: np.random.Generator) -> np.ndarray:
    if class_id == 0:
        return make_none_sample(rng)
    return make_banknote_sample(class_id, rng)


def augment_image(image: np.ndarray, rng: np.random.Generator, crop_mode: bool = False) -> np.ndarray:
    tensor = tf.convert_to_tensor(image.astype(np.float32))
    # Banknotes are asymmetric – no horizontal flip (especially crop-mode Stage 2).
    if not crop_mode and rng.random() < 0.15:
        tensor = tf.image.flip_left_right(tensor)
    if rng.random() < 0.4:
        tensor = tf.image.adjust_brightness(tensor, float(rng.uniform(-0.15, 0.15)))
    if rng.random() < 0.4:
        tensor = tf.image.adjust_contrast(tensor, float(rng.uniform(0.85, 1.15)))
    if rng.random() < 0.35:
        tensor = tf.image.adjust_saturation(tensor, float(rng.uniform(0.8, 1.2)))
    if rng.random() < 0.25:
        k = int(rng.integers(0, 4))
        if k > 0:
            tensor = tf.image.rot90(tensor, k=k)
    if rng.random() < 0.20:
        scale = float(rng.uniform(0.92, 1.08))
        h = int(INPUT_SIZE * scale)
        w = int(INPUT_SIZE * scale)
        resized = tf.image.resize(tensor, [h, w], method="bilinear")
        tensor = tf.image.resize_with_crop_or_pad(resized, INPUT_SIZE, INPUT_SIZE)
    if rng.random() < 0.15:
        noise = rng.normal(0.0, 6.0, size=tensor.shape).astype(np.float32)
        tensor = tensor + noise
    return tf.clip_by_value(tensor, 0.0, 255.0).numpy().astype(np.float32)


def load_image_file(path: Path) -> np.ndarray | None:
    try:
        raw = tf.io.read_file(str(path))
        image = tf.image.decode_image(raw, channels=3, expand_animations=False)
        image = tf.image.resize(image, [INPUT_SIZE, INPUT_SIZE], method="bilinear")
        return image.numpy().astype(np.float32)
    except Exception:
        return None


def load_real_dataset(
    dataset_dir: Path,
    augment_factor: int,
    seed: int,
    crop_mode: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    images: list[np.ndarray] = []
    labels: list[int] = []

    for class_id, label in enumerate(LABELS):
        folder = dataset_dir / label
        if not folder.is_dir():
            continue
        files = [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES]
        for file_path in files:
            base = load_image_file(file_path)
            if base is None:
                continue
            images.append(base)
            labels.append(class_id)
            for _ in range(max(0, augment_factor - 1)):
                images.append(augment_image(base, rng, crop_mode=crop_mode))
                labels.append(class_id)

    if not images:
        return np.empty((0, INPUT_SIZE, INPUT_SIZE, 3), dtype=np.float32), np.empty((0, NUM_CLASSES), dtype=np.float32)

    x = np.stack(images).astype(np.float32)
    y = tf.keras.utils.to_categorical(labels, NUM_CLASSES).astype(np.float32)
    perm = rng.permutation(len(labels))
    return x[perm], y[perm]


def build_synthetic_dataset(samples_per_class: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    images: list[np.ndarray] = []
    labels: list[int] = []
    none_samples = int(samples_per_class * 1.8)
    for class_id in range(NUM_CLASSES):
        count = none_samples if class_id == 0 else samples_per_class
        for _ in range(count):
            images.append(make_sample(class_id, rng))
            labels.append(class_id)
    x = np.stack(images).astype(np.float32)
    y = tf.keras.utils.to_categorical(labels, NUM_CLASSES).astype(np.float32)
    perm = rng.permutation(len(labels))
    return x[perm], y[perm]


def build_model() -> tuple[tf.keras.Model, tf.keras.Model]:
    base = tf.keras.applications.MobileNetV3Small(
        input_shape=(INPUT_SIZE, INPUT_SIZE, 3),
        include_top=False,
        weights="imagenet",
        pooling="avg",
    )
    inputs = tf.keras.Input(shape=(INPUT_SIZE, INPUT_SIZE, 3), name="image")
    x = base(inputs)
    x = tf.keras.layers.Dropout(0.25)(x)
    outputs = tf.keras.layers.Dense(NUM_CLASSES, activation="softmax", name="denomination")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="huf_banknote_classifier")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model, base


def export_tflite(model: tf.keras.Model, output_path: Path) -> None:
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    tflite_model = converter.convert()
    output_path.write_bytes(tflite_model)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "app" / "src" / "main" / "assets",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "banknote_dataset",
    )
    parser.add_argument("--epochs", type=int, default=14)
    parser.add_argument("--samples-per-class", type=int, default=480)
    parser.add_argument("--augment-factor", type=int, default=4)
    parser.add_argument(
        "--crop-mode",
        action="store_true",
        help="Dataset is YOLO bbox crops (tools/banknote_dataset_crops). Heavier aug, no flips.",
    )
    args = parser.parse_args()

    crop_mode = args.crop_mode or "dataset_crops" in args.dataset_dir.name
    if crop_mode:
        print(f"Crop-mode Stage-2 training from {args.dataset_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    x_real, y_real = load_real_dataset(args.dataset_dir, args.augment_factor, seed=7, crop_mode=crop_mode)
    x_syn_train, y_syn_train = build_synthetic_dataset(args.samples_per_class, seed=42)
    x_syn_val, y_syn_val = build_synthetic_dataset(max(args.samples_per_class // 4, 80), seed=99)

    if len(x_real) > 0:
        print(f"Loaded {len(x_real)} real/augmented samples from {args.dataset_dir}")
        # Valódi fotók súlyozása – fontosabb, mint a szintetikus adat.
        real_weight = 4 if crop_mode else 3
        x_real_weighted = np.concatenate([x_real] * real_weight, axis=0)
        y_real_weighted = np.concatenate([y_real] * real_weight, axis=0)
        x_train = np.concatenate([x_real_weighted, x_syn_train], axis=0)
        y_train = np.concatenate([y_real_weighted, y_syn_train], axis=0)
    else:
        print(f"No real photos in {args.dataset_dir} – training on enhanced synthetic data only.")
        print("Add photos to tools/banknote_dataset/<label>/ for better accuracy.")
        x_train, y_train = x_syn_train, y_syn_train

    model, base = build_model()

    # 1. fázis: rögzített alapréteg
    base.trainable = False
    model.fit(
        x_train,
        y_train,
        validation_data=(x_syn_val, y_syn_val),
        epochs=max(3, args.epochs // 3),
        batch_size=32,
        verbose=1,
    )

    # 2. fázis: finomhangolás
    base.trainable = True
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=2e-4),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(
        x_train,
        y_train,
        validation_data=(x_syn_val, y_syn_val),
        epochs=args.epochs,
        batch_size=32,
        verbose=1,
    )

    model_path = args.output_dir / "huf_banknote_classifier.tflite"
    labels_path = args.output_dir / "huf_banknote_labels.txt"
    export_tflite(model, model_path)
    labels_path.write_text("\n".join(LABELS) + "\n", encoding="utf-8")

    print(f"Wrote {model_path} ({model_path.stat().st_size} bytes)")
    print(f"Wrote {labels_path}")


if __name__ == "__main__":
    main()