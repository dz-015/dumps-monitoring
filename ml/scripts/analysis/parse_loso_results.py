"""Parse LOSO results from multiple training runs and aggregate per-fold/per-config.

Usage:
    python parse_loso_results.py --runs-root /home/alex/dumps_monitoring/ml/runs/detect/runs

Outputs:
    - stdout: per-config table (mean ± std mAP50, mAP50-95, per-class P/R via best.pt val)
    - JSON dump: <runs-root>/parsed_results.json
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

import click


RUN_DIR_RE = re.compile(r"fold_(\d+)_seed_(\d+)$")


def parse_results_csv(csv_path: Path) -> dict | None:
    """Read results.csv and return best-epoch row by mAP50."""
    lines = csv_path.read_text().strip().split("\n")
    if len(lines) < 2:
        return None
    header = lines[0].split(",")
    rows = [line.split(",") for line in lines[1:]]

    try:
        map50_idx = header.index("metrics/mAP50(B)")
        map50_95_idx = header.index("metrics/mAP50-95(B)")
        prec_idx = header.index("metrics/precision(B)")
        rec_idx = header.index("metrics/recall(B)")
        epoch_idx = header.index("epoch")
    except ValueError:
        return None

    best_row = max(rows, key=lambda r: float(r[map50_idx]) if r[map50_idx] else 0.0)
    return {
        "epoch": int(float(best_row[epoch_idx])),
        "mAP50": float(best_row[map50_idx]),
        "mAP50_95": float(best_row[map50_95_idx]),
        "precision": float(best_row[prec_idx]),
        "recall": float(best_row[rec_idx]),
        "total_epochs": len(rows),
    }


def collect_runs(runs_root: Path) -> dict[str, dict[int, dict[int, dict]]]:
    """Walk runs_root and group runs by (config, fold, seed).

    Returns: {config_name: {fold: {seed: results_dict}}}
    """
    grouped: dict[str, dict[int, dict[int, dict]]] = {}
    for csv_path in runs_root.rglob("results.csv"):
        run_dir = csv_path.parent
        m = RUN_DIR_RE.search(run_dir.name)
        if not m:
            continue
        fold, seed = int(m.group(1)), int(m.group(2))
        config_name = run_dir.parent.name  # e.g. level1_baseline, level1_tuned, rtdetr_baseline
        results = parse_results_csv(csv_path)
        if results is None:
            continue
        results["run_dir"] = str(run_dir)
        grouped.setdefault(config_name, {}).setdefault(fold, {})[seed] = results
    return grouped


def aggregate(grouped: dict) -> dict:
    """Compute per-fold mean ± std and overall LOSO mean for each config."""
    summary = {}
    for config, fold_data in grouped.items():
        config_summary: dict = {"folds": {}, "loso_mean": {}}
        all_map50 = []
        all_map50_95 = []
        all_prec = []
        all_rec = []
        for fold in sorted(fold_data.keys()):
            seeds = fold_data[fold]
            map50s = [s["mAP50"] for s in seeds.values()]
            map50_95s = [s["mAP50_95"] for s in seeds.values()]
            precs = [s["precision"] for s in seeds.values()]
            recs = [s["recall"] for s in seeds.values()]
            config_summary["folds"][fold] = {
                "n_seeds": len(seeds),
                "mAP50_mean": statistics.mean(map50s),
                "mAP50_std": statistics.stdev(map50s) if len(map50s) > 1 else 0.0,
                "mAP50_95_mean": statistics.mean(map50_95s),
                "mAP50_95_std": statistics.stdev(map50_95s) if len(map50_95s) > 1 else 0.0,
                "precision_mean": statistics.mean(precs),
                "recall_mean": statistics.mean(recs),
                "best_epochs": [s["epoch"] for s in seeds.values()],
            }
            all_map50.extend(map50s)
            all_map50_95.extend(map50_95s)
            all_prec.extend(precs)
            all_rec.extend(recs)

        config_summary["loso_mean"] = {
            "n_folds": len(fold_data),
            "n_runs_total": len(all_map50),
            "mAP50_mean": statistics.mean(all_map50) if all_map50 else 0.0,
            "mAP50_std": statistics.stdev(all_map50) if len(all_map50) > 1 else 0.0,
            "mAP50_95_mean": statistics.mean(all_map50_95) if all_map50_95 else 0.0,
            "mAP50_95_std": statistics.stdev(all_map50_95) if len(all_map50_95) > 1 else 0.0,
            "precision_mean": statistics.mean(all_prec) if all_prec else 0.0,
            "recall_mean": statistics.mean(all_rec) if all_rec else 0.0,
        }
        summary[config] = config_summary
    return summary


CAM_BY_FOLD = {0: "cam_1", 1: "cam_2", 2: "cam_3", 3: "cam_5", 4: "cam_7"}


def print_table(summary: dict) -> None:
    for config, data in summary.items():
        click.secho(f"\n=== {config} ===", fg="cyan", bold=True)
        click.echo(
            f"{'fold':<6} {'cam':<8} {'n_seeds':<8} "
            f"{'mAP50':<16} {'mAP50-95':<16} {'P':<10} {'R':<10} {'best_epochs'}"
        )
        click.echo("-" * 110)
        for fold in sorted(data["folds"].keys()):
            f = data["folds"][fold]
            click.echo(
                f"{fold:<6} {CAM_BY_FOLD.get(fold, '?'):<8} {f['n_seeds']:<8} "
                f"{f['mAP50_mean']:.4f} ± {f['mAP50_std']:.4f}  "
                f"{f['mAP50_95_mean']:.4f} ± {f['mAP50_95_std']:.4f}  "
                f"{f['precision_mean']:.4f}    {f['recall_mean']:.4f}    "
                f"{f['best_epochs']}"
            )
        loso = data["loso_mean"]
        click.secho(
            f"{'LOSO':<6} {'mean':<8} {loso['n_runs_total']:<8} "
            f"{loso['mAP50_mean']:.4f} ± {loso['mAP50_std']:.4f}  "
            f"{loso['mAP50_95_mean']:.4f} ± {loso['mAP50_95_std']:.4f}  "
            f"{loso['precision_mean']:.4f}    {loso['recall_mean']:.4f}",
            fg="green",
            bold=True,
        )


@click.command()
@click.option(
    "--runs-root",
    type=click.Path(path_type=Path, exists=True),
    default=Path("runs/detect/runs"),
    help="Root directory containing per-config subdirectories with fold_X_seed_Y runs.",
)
@click.option("--out-json", type=click.Path(path_type=Path), default=None)
def main(runs_root: Path, out_json: Path | None) -> None:
    grouped = collect_runs(runs_root)
    if not grouped:
        click.echo(f"No runs found under {runs_root}")
        return
    summary = aggregate(grouped)
    print_table(summary)

    if out_json is None:
        out_json = runs_root / "parsed_results.json"
    out_json.write_text(json.dumps({"raw": grouped, "summary": summary}, indent=2))
    click.echo(f"\nSaved JSON: {out_json}")


if __name__ == "__main__":
    main()
