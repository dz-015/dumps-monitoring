# НЭКОБАК — ML subproject

Training code, experiment configs, and data-handling scripts. Kept separate from `backend/` because the training pipeline is a self-contained artifact — someone with only the `ml/` tree, the raw data, and a GPU should be able to reproduce every thesis number.

## Layout

```
ml/
├── configs/              # YAML per experiment (level0, level1, two_stage, ablations)
├── data/                 # NOT in git; managed via DVC
│   ├── raw/              # original frames, as pulled from Yandex Disk
│   ├── processed/        # after sampling + dedup
│   ├── public/           # TACO, etc.
│   └── splits/           # train/val/test YOLO-format txt files
├── notebooks/            # Exploratory only. No production logic here.
├── scripts/              # Runnable entry points (explore, sample, train, eval, export)
└── src/
    ├── datasets/         # PyTorch Dataset / Ultralytics YOLO data adapters
    ├── models/           # model wrappers, two-stage glue
    ├── training/         # loops, callbacks, custom losses/samplers
    ├── eval/             # LOSO driver, metric computation, scene-level aggregation
    └── export/           # ONNX export + inference smoke tests
```

## Setup

```bash
cd ml
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-ml.txt
dvc init --subdir      # first time only
```

Do NOT reuse `backend/venv` — ML deps pull in torch/cuda/ultralytics and bloat it. Two envs, two clean dependency surfaces.

## Reproducibility protocol

Every experiment run does three things:
1. Records the git SHA of the repo at training time in the W&B config.
2. Copies the exact YAML config used to the W&B artifacts bucket.
3. Fixes seeds (`seed=0`, `deterministic=True`) and disables `cache="ram"` (non-determinism bug in Ultralytics ≥ 8.1).

Main-table thesis numbers are reported as `mean ± std over 3 LOSO folds × 1 seed`. Seed variance is explicitly not ablated; the Limitations chapter cites typical YOLOv8 seed std ≈ 0.01–0.02 mAP. See `docs/ml_plan_deep_review.md` §11.1 and `project_decisions.md` (2026-04-23 · LOSO 3-fold) for rationale.

## Status (2026-04-23)

- Skeleton only. No working training yet.
- Blocking decisions live in `docs/ml_open_questions.md` (Q1–Q3 block week-3 start).
