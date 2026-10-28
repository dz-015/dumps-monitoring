"""Экспорт прод-модели rtdetr_temporal_640 (3 сида) в ONNX + сверка с PyTorch.

opset >= 16 обязателен: в RT-DETR есть grid_sampler, в 15-м опсете он не
экспортируется. После экспорта каждый ONNX прогоняется через onnxruntime и
сравнивается с torch-моделью — иначе можно молча получить битый граф.

Сверять надо на РЕАЛЬНОМ кадре, а не на шуме: на шуме все 300 запросов
получают почти одинаковую уверенность (~0.009), порядок сортировки на
тай-брейках у torch и onnxruntime разный, и построчное сравнение даёт
ложное расхождение. Поэтому сравниваем только уверенные детекции.
"""

import os
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from ultralytics import RTDETR

RUNS = Path(os.environ.get(
    "RTDETR_RUNS_DIR",
    "/mnt/c/Users/killh/Desktop/runs/detect/runs/rtdetr_temporal_640",
))
OUT = Path(__file__).resolve().parent / "models" / "rtdetr_temporal_640"
IMGSZ = 640
OPSET = 16
CONF = 0.25
# Допуски покомпонентные: геометрия обязана совпадать почти точно, а
# уверенность после onnxslim/constant-folding честно плывёт на ~4e-3
# (проверено 2026-07-29 на всех трёх сидах). Класс — строго.
TOL_BOX = 1e-3
TOL_CONF = 1e-2


def sample_input(run: Path) -> torch.Tensor:
    """Реальный кадр из артефактов обучения (мозаика train_batch), 0..1 BCHW."""
    src = next((run / n for n in ("train_batch0.jpg", "labels.jpg") if (run / n).is_file()), None)
    if src is None:
        raise FileNotFoundError(f"нет кадра для сверки в {run}")
    img = Image.open(src).convert("RGB").resize((IMGSZ, IMGSZ))
    arr = np.asarray(img, dtype=np.float32).transpose(2, 0, 1) / 255.0
    return torch.from_numpy(arr)[None]


def check(onnx_path: Path, weights: Path, x: torch.Tensor) -> tuple[int, np.ndarray]:
    """Возвращает (сколько уверенных детекций, максимум расхождения по столбцам)."""
    import onnxruntime as ort

    model = RTDETR(str(weights)).model.float().eval()
    with torch.inference_mode():
        ref = model(x)
    ref = (ref[0] if isinstance(ref, (list, tuple)) else ref).numpy()[0]

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    got = sess.run(None, {sess.get_inputs()[0].name: x.numpy()})[0][0]

    # порядок строк не гарантирован — сравниваем отсортированные уверенные детекции
    def confident(a):
        a = a[a[:, 4] >= CONF]
        return a[np.lexsort((a[:, 1], a[:, 0], -a[:, 4]))]

    ref, got = confident(ref), confident(got)
    if ref.shape != got.shape or len(ref) == 0:
        return len(ref), np.full(6, np.inf)
    return len(ref), np.abs(ref - got).max(axis=0)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = sorted(p for p in RUNS.iterdir() if (p / "weights" / "best.pt").is_file())
    if not runs:
        print(f"нет весов в {RUNS}", file=sys.stderr)
        return 1

    failed = []
    for run in runs:
        weights = run / "weights" / "best.pt"
        print(f"\n=== {run.name} ===", flush=True)

        target = OUT / f"{run.name}.onnx"
        if not target.is_file():
            exported = Path(RTDETR(str(weights)).export(
                format="onnx", opset=OPSET, imgsz=IMGSZ, dynamic=False, simplify=True, batch=1
            ))
            shutil.move(str(exported), target)

        n, diff = check(target, weights, sample_input(run))
        ok = bool(n > 0 and diff[:4].max() < TOL_BOX and diff[4] < TOL_CONF and diff[5] == 0)
        print(f"{run.name}: {target.name}, {target.stat().st_size / 1e6:.1f} МБ, "
              f"детекций ≥{CONF}: {n}, расхождение с torch — рамки {diff[:4].max():.1e}, "
              f"уверенность {diff[4]:.1e}, класс {diff[5]:.0f} "
              f"{'OK' if ok else 'РАСХОЖДЕНИЕ'}", flush=True)
        if not ok:
            failed.append(run.name)

    print(f"\nготово: {len(runs)} моделей в {OUT}")
    if failed:
        print(f"НЕ СОШЛОСЬ с torch: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
