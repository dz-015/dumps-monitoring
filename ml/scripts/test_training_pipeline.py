"""End-to-end smoke test for training pipeline. Verifies GPU + ultralytics work together.

Generates synthetic YOLO-format labels from COCO predictions on audit frames, then runs a
5-epoch training. If this succeeds without errors, Day 5+ LOSO sweep on real labels will work.

Run on 4090 host after pip install:

    cd ~/dumps_monitoring/ml
    source venv/bin/activate
    python scripts/test_training_pipeline.py --raw-dir data/raw/audit_2026-05-04
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click

CLASS_NAMES = ["bin_ok", "bin_overflow", "ground_trash"]


def _coco_to_synthetic(cls_idx: int) -> int | None:
    """Map COCO class indices to our 3-class synthetic labels for the smoke test only.

    This is NOT real labeling — just any signal that training loop runs end-to-end.
    """
    coco_to_ours = {
        39: 0,  # bottle      → bin_ok
        72: 1,  # refrigerator → bin_overflow
        28: 2,  # suitcase    → ground_trash
        2: 0,   # car         → bin_ok (just to populate the class)
    }
    return coco_to_ours.get(cls_idx)


def generate_synthetic_labels(
    raw_dir: Path,
    out_dir: Path,
    yolo_model_path: str = "yolov8m.pt",
    conf: float = 0.30,
    imgsz: int = 1280,
) -> tuple[int, int]:
    """Run COCO YOLOv8m on raw frames, save synthetic YOLO labels. Returns (n_frames, n_labeled)."""
    from ultralytics import YOLO

    yolo = YOLO(yolo_model_path)
    images_out = out_dir / "images"
    labels_out = out_dir / "labels"
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    n_frames = 0
    n_labeled = 0
    for img_path in sorted(raw_dir.rglob("*.jpg")):
        n_frames += 1
        target_img = images_out / img_path.name
        if not target_img.exists():
            shutil.copy(img_path, target_img)
        result = yolo.predict(source=str(img_path), conf=conf, imgsz=imgsz, verbose=False)[0]
        h, w = result.orig_shape
        lines: list[str] = []
        if result.boxes is not None:
            for cls_idx, xywhn in zip(
                result.boxes.cls.int().tolist(), result.boxes.xywhn.tolist()
            ):
                mapped = _coco_to_synthetic(cls_idx)
                if mapped is None:
                    continue
                cx, cy, bw, bh = xywhn
                lines.append(f"{mapped} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        if lines:
            n_labeled += 1
            (labels_out / (img_path.stem + ".txt")).write_text("\n".join(lines))
        else:
            (labels_out / (img_path.stem + ".txt")).write_text("")

    return n_frames, n_labeled


def write_data_yaml(dataset_root: Path, out_yaml: Path) -> None:
    images = dataset_root / "images"
    files = sorted(images.glob("*.jpg"))
    n = len(files)
    train_split = int(n * 0.8)
    train_list = dataset_root / "train.txt"
    val_list = dataset_root / "val.txt"
    train_list.write_text("\n".join(str(f.resolve()) for f in files[:train_split]))
    val_list.write_text("\n".join(str(f.resolve()) for f in files[train_split:]))

    out_yaml.write_text(
        f"path: {dataset_root.resolve()}\n"
        f"train: {train_list.name}\n"
        f"val: {val_list.name}\n"
        f"nc: {len(CLASS_NAMES)}\n"
        f"names: {CLASS_NAMES}\n"
    )


@click.command()
@click.option(
    "--raw-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/raw/audit_2026-05-04"),
)
@click.option(
    "--work-dir",
    type=click.Path(path_type=Path),
    default=Path("data/processed/_test_pipeline"),
)
@click.option("--epochs", type=int, default=5)
@click.option("--imgsz", type=int, default=640)
@click.option("--batch", type=int, default=8)
def main(raw_dir: Path, work_dir: Path, epochs: int, imgsz: int, batch: int) -> None:
    import torch
    from ultralytics import YOLO

    click.echo(f"=== environment ===")
    click.echo(f"torch: {torch.__version__}")
    click.echo(f"cuda available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        click.echo(f"cuda device: {torch.cuda.get_device_name(0)}")
        click.echo(f"compute capability: {torch.cuda.get_device_capability(0)}")
        click.echo(f"VRAM total: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    click.echo()

    click.echo(f"=== Stage 1: generate synthetic labels from COCO predictions ===")
    n_frames, n_labeled = generate_synthetic_labels(raw_dir, work_dir)
    click.echo(f"frames: {n_frames}, with at least 1 mapped detection: {n_labeled}")
    if n_labeled < 10:
        raise click.ClickException(
            "Too few synthetic-labeled frames. Need at least 10 for a meaningful smoke test."
        )

    data_yaml = work_dir / "smoke.yaml"
    write_data_yaml(work_dir, data_yaml)
    click.echo(f"data.yaml at {data_yaml}")
    click.echo()

    click.echo(f"=== Stage 2: train YOLOv8m for {epochs} epochs ===")
    model = YOLO("yolov8m.pt")
    runs_root = work_dir / "runs"
    runs_root.mkdir(exist_ok=True)
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=0 if torch.cuda.is_available() else "cpu",
        project=str(runs_root),
        name="smoke",
        exist_ok=True,
        verbose=False,
        plots=False,
        save=True,
        seed=0,
        deterministic=True,
        cache=False,
    )
    click.echo()
    click.echo(f"=== Stage 3: training summary ===")
    click.echo(f"results.save_dir: {results.save_dir}")
    metrics = getattr(results, "results_dict", None) or {}
    for k in ("metrics/mAP50(B)", "metrics/mAP50-95(B)", "metrics/precision(B)", "metrics/recall(B)"):
        if k in metrics:
            click.echo(f"  {k}: {metrics[k]:.4f}")

    click.secho("\nSMOKE TEST PASSED. Training pipeline works end-to-end on this hardware.", fg="green")


if __name__ == "__main__":
    main()
