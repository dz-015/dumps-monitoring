"""Export a trained YOLOv8 model to ONNX for CPU inference in the backend service.

    python -m ml.scripts.export_onnx --weights ml/runs/level1_baseline/fold_0/seed_0/weights/best.pt

The ONNX file is copied into backend/app/models_pt/ so the FastAPI worker can
load it via onnxruntime-cpu for the defense-laptop demo.
"""

from __future__ import annotations

from pathlib import Path

import click


@click.command()
@click.option("--weights", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--out-dir", type=click.Path(path_type=Path), default=Path("backend/app/models_pt"))
@click.option("--imgsz", type=int, default=640)
def main(weights: Path, out_dir: Path, imgsz: int) -> None:
    # TODO(week3-fri):
    #   from ultralytics import YOLO
    #   YOLO(weights).export(format="onnx", imgsz=imgsz, simplify=True, opset=17)
    # then copy the resulting .onnx next to weights into out_dir.
    raise NotImplementedError(
        "Wire once Level-1 baseline produces a best.pt. "
        "Smoke-test with onnxruntime afterwards."
    )


if __name__ == "__main__":
    main()
