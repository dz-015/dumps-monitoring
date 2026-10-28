"""Re-validate all best.pt across runs to extract per-class P/R/mAP, save JSON.

Reading metrics from results.csv per-epoch is unreliable — Ultralytics' final
validation on best.pt may differ slightly (different aug/precision modes), and
results.csv has no per-class breakdown. This script runs `model.val()` on each
best.pt against its fold's data.yaml, captures per-class metrics.

Usage:
    python eval_all_runs.py --runs-root runs/detect/runs --folds-dir data/folds
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import click


RUN_DIR_RE = re.compile(r"fold_(\d+)_seed_(\d+)$")

CAM_BY_FOLD = {0: "cam_1", 1: "cam_2", 2: "cam_3", 3: "cam_5", 4: "cam_7"}


def find_runs(runs_root: Path) -> list[tuple[str, int, int, Path]]:
    """Yield (config_name, fold, seed, best_pt_path) for every completed run."""
    out = []
    for best_pt in runs_root.rglob("weights/best.pt"):
        run_dir = best_pt.parent.parent
        m = RUN_DIR_RE.search(run_dir.name)
        if not m:
            continue
        fold, seed = int(m.group(1)), int(m.group(2))
        config_name = run_dir.parent.name
        out.append((config_name, fold, seed, best_pt))
    return out


def run_val(weights: Path, data_yaml: Path, device: str = "0") -> dict:
    """Run Ultralytics validation, return overall + per-class metrics."""
    os.environ.setdefault("WANDB_MODE", "disabled")
    os.environ.setdefault("YOLO_VERBOSE", "False")
    from ultralytics import YOLO

    model = YOLO(str(weights))
    # Suppress Ultralytics chatter
    buf = StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        results = model.val(
            data=str(data_yaml),
            split="val",
            device=device,
            verbose=False,
            plots=False,
            save_json=False,
        )

    box = results.box
    overall = {
        "mAP50": float(box.map50),
        "mAP50_95": float(box.map),
        "precision": float(box.mp),
        "recall": float(box.mr),
    }
    per_class = {}
    names = results.names if hasattr(results, "names") else {}
    if hasattr(box, "ap50") and box.ap50 is not None and len(box.ap50) > 0:
        for i, ap50 in enumerate(box.ap50):
            class_name = names.get(i, f"class_{i}")
            entry = {"mAP50": float(ap50)}
            if hasattr(box, "ap") and box.ap is not None and i < len(box.ap):
                entry["mAP50_95"] = float(box.ap[i].mean())
            if hasattr(box, "p") and box.p is not None and i < len(box.p):
                entry["precision"] = float(box.p[i])
            if hasattr(box, "r") and box.r is not None and i < len(box.r):
                entry["recall"] = float(box.r[i])
            per_class[class_name] = entry
    return {"overall": overall, "per_class": per_class}


@click.command()
@click.option(
    "--runs-root",
    type=click.Path(path_type=Path, exists=True),
    default=Path("runs/detect/runs"),
)
@click.option(
    "--folds-dir",
    type=click.Path(path_type=Path, exists=True),
    default=Path("data/folds"),
)
@click.option("--device", default="0", help="GPU index or 'cpu'")
@click.option(
    "--filter-config",
    default=None,
    help="Only evaluate runs whose config_name starts with this prefix.",
)
@click.option("--out-json", type=click.Path(path_type=Path), default=Path("eval_all.json"))
def main(
    runs_root: Path, folds_dir: Path, device: str, filter_config: str | None, out_json: Path
) -> None:
    runs = find_runs(runs_root)
    if filter_config:
        runs = [r for r in runs if r[0].startswith(filter_config)]
    if not runs:
        click.echo(f"No runs found under {runs_root}")
        return
    click.echo(f"Evaluating {len(runs)} runs ...")

    by_config: dict = {}
    for config, fold, seed, best_pt in sorted(runs):
        data_yaml = folds_dir / f"fold_{fold}" / "data.yaml"
        if not data_yaml.exists():
            click.echo(f"  ✗ {config} fold={fold} seed={seed}: data.yaml missing ({data_yaml})")
            continue
        try:
            metrics = run_val(best_pt, data_yaml, device=device)
        except Exception as e:
            click.echo(f"  ✗ {config} fold={fold} seed={seed}: {type(e).__name__}: {e}")
            continue
        by_config.setdefault(config, {}).setdefault(fold, {})[seed] = metrics
        ov = metrics["overall"]
        click.echo(
            f"  ✓ {config} fold={fold} seed={seed}: "
            f"mAP50={ov['mAP50']:.4f} mAP50-95={ov['mAP50_95']:.4f} "
            f"P={ov['precision']:.4f} R={ov['recall']:.4f}"
        )

    summary = aggregate(by_config)
    print_summary(summary)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"raw": by_config, "summary": summary}, indent=2))
    click.echo(f"\nSaved: {out_json}")


def aggregate(by_config: dict) -> dict:
    summary: dict = {}
    for config, fold_data in by_config.items():
        cs: dict = {"folds": {}, "loso_mean": {}, "per_class_loso": {}}
        all_overall = {"mAP50": [], "mAP50_95": [], "precision": [], "recall": []}
        per_class_acc: dict[str, dict[str, list[float]]] = {}
        for fold in sorted(fold_data.keys()):
            seeds = fold_data[fold]
            fold_summary = {"n_seeds": len(seeds)}
            for k in ["mAP50", "mAP50_95", "precision", "recall"]:
                vals = [s["overall"][k] for s in seeds.values()]
                fold_summary[f"{k}_mean"] = statistics.mean(vals)
                fold_summary[f"{k}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
                all_overall[k].extend(vals)
            # per-class within fold
            classes = set()
            for s in seeds.values():
                classes.update(s["per_class"].keys())
            fold_pc = {}
            for cls in classes:
                cls_metrics: dict[str, list[float]] = {}
                for s in seeds.values():
                    if cls in s["per_class"]:
                        for k, v in s["per_class"][cls].items():
                            cls_metrics.setdefault(k, []).append(v)
                fold_pc[cls] = {
                    f"{k}_mean": statistics.mean(v) for k, v in cls_metrics.items()
                }
                # also accumulate for overall LOSO per-class
                for k, vals in cls_metrics.items():
                    per_class_acc.setdefault(cls, {}).setdefault(k, []).extend(vals)
            fold_summary["per_class"] = fold_pc
            cs["folds"][fold] = fold_summary

        for k in ["mAP50", "mAP50_95", "precision", "recall"]:
            vals = all_overall[k]
            cs["loso_mean"][f"{k}_mean"] = statistics.mean(vals) if vals else 0.0
            cs["loso_mean"][f"{k}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
        cs["loso_mean"]["n_runs_total"] = len(all_overall["mAP50"])
        cs["loso_mean"]["n_folds"] = len(fold_data)

        for cls, ms in per_class_acc.items():
            cs["per_class_loso"][cls] = {
                f"{k}_mean": statistics.mean(v) for k, v in ms.items() if v
            }
            for k, v in ms.items():
                if len(v) > 1:
                    cs["per_class_loso"][cls][f"{k}_std"] = statistics.stdev(v)
        summary[config] = cs
    return summary


def print_summary(summary: dict) -> None:
    for config, data in summary.items():
        click.secho(f"\n=== {config} ===", fg="cyan", bold=True)
        click.echo(
            f"{'fold':<5} {'cam':<7} {'n':<3} {'mAP50':<16} {'mAP50-95':<16} "
            f"{'P':<8} {'R':<8}"
        )
        click.echo("-" * 80)
        for fold in sorted(data["folds"].keys()):
            f = data["folds"][fold]
            click.echo(
                f"{fold:<5} {CAM_BY_FOLD.get(fold, '?'):<7} {f['n_seeds']:<3} "
                f"{f['mAP50_mean']:.4f} ± {f['mAP50_std']:.4f}  "
                f"{f['mAP50_95_mean']:.4f} ± {f['mAP50_95_std']:.4f}  "
                f"{f['precision_mean']:.4f}  {f['recall_mean']:.4f}"
            )
        loso = data["loso_mean"]
        click.secho(
            f"{'LOSO':<5} {'mean':<7} {loso['n_runs_total']:<3} "
            f"{loso['mAP50_mean']:.4f} ± {loso['mAP50_std']:.4f}  "
            f"{loso['mAP50_95_mean']:.4f} ± {loso['mAP50_95_std']:.4f}  "
            f"{loso['precision_mean']:.4f}  {loso['recall_mean']:.4f}",
            fg="green",
            bold=True,
        )

        if data["per_class_loso"]:
            click.echo("\nper-class LOSO:")
            click.echo(f"  {'class':<16} {'mAP50':<16} {'mAP50_95':<16} {'P':<8} {'R':<8}")
            for cls in sorted(data["per_class_loso"].keys()):
                pc = data["per_class_loso"][cls]
                click.echo(
                    f"  {cls:<16} "
                    f"{pc.get('mAP50_mean', 0):.4f} ± {pc.get('mAP50_std', 0):.4f}  "
                    f"{pc.get('mAP50_95_mean', 0):.4f} ± {pc.get('mAP50_95_std', 0):.4f}  "
                    f"{pc.get('precision_mean', 0):.4f}  {pc.get('recall_mean', 0):.4f}"
                )


if __name__ == "__main__":
    main()
