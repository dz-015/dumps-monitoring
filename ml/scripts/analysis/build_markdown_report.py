"""Build a single markdown report from parsed_results.json + eval_all.json + bootstrap_ci.json + confusion.

Output goes to docs/runs_report_YYYY-MM-DD.md and is suitable for sharing with
the supervisor or pasting into briefings.

Usage:
    python build_markdown_report.py \\
        --parsed runs/detect/runs/level1/parsed_results.json \\
        --parsed runs/detect/runs/level1_tuned/parsed_results.json \\
        --parsed runs/rtdetr/parsed_results.json \\
        --eval-all runs/analysis/eval_all.json \\
        --bootstrap runs/analysis/bootstrap_ci.json \\
        --confusion runs/analysis/confusion/level1_confusion.json \\
        --out-md docs/runs_report.md
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import click


CAM_BY_FOLD = {0: "cam_1", 1: "cam_2", 2: "cam_3", 3: "cam_5", 4: "cam_7"}


def fmt(mean: float | None, std: float | None = None, places: int = 3) -> str:
    if mean is None:
        return "n/a"
    if std is None or std == 0:
        return f"{mean:.{places}f}"
    return f"{mean:.{places}f} ± {std:.{places}f}"


def fmt_overall_table(summaries: dict[str, dict]) -> list[str]:
    out = ["| Configuration | N runs | mAP50 | mAP50-95 | P | R |", "|---|---|---|---|---|---|"]
    for cfg, s in summaries.items():
        loso = s["loso_mean"]
        out.append(
            f"| {cfg} | {loso.get('n_runs_total', '?')} | "
            f"{fmt(loso.get('mAP50_mean'), loso.get('mAP50_std'))} | "
            f"{fmt(loso.get('mAP50_95_mean'), loso.get('mAP50_95_std'))} | "
            f"{fmt(loso.get('precision_mean'))} | "
            f"{fmt(loso.get('recall_mean'))} |"
        )
    return out


def fmt_per_fold(cfg: str, summary: dict) -> list[str]:
    out = [
        f"### {cfg}",
        "",
        "| Fold | Cam | n_seeds | mAP50 | mAP50-95 | P | R | best epochs |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for fold_key in sorted(summary["folds"].keys(), key=lambda x: int(x)):
        f = summary["folds"][fold_key]
        fold = int(fold_key)
        be = "/".join(str(e) for e in f.get("best_epochs", []))
        out.append(
            f"| {fold} | {CAM_BY_FOLD.get(fold, '?')} | {f['n_seeds']} | "
            f"{fmt(f.get('mAP50_mean'), f.get('mAP50_std'))} | "
            f"{fmt(f.get('mAP50_95_mean'), f.get('mAP50_95_std'))} | "
            f"{fmt(f.get('precision_mean'))} | "
            f"{fmt(f.get('recall_mean'))} | {be} |"
        )
    loso = summary["loso_mean"]
    out.append(
        f"| **LOSO** | **mean** | {loso.get('n_runs_total', '?')} | "
        f"**{fmt(loso.get('mAP50_mean'), loso.get('mAP50_std'))}** | "
        f"**{fmt(loso.get('mAP50_95_mean'), loso.get('mAP50_95_std'))}** | "
        f"**{fmt(loso.get('precision_mean'))}** | "
        f"**{fmt(loso.get('recall_mean'))}** | --- |"
    )
    out.append("")
    return out


def fmt_per_class(eval_all: dict) -> list[str]:
    out = ["## Per-class breakdown", ""]
    for cfg, data in eval_all.get("summary", {}).items():
        if not data.get("per_class_loso"):
            continue
        out.append(f"### {cfg}")
        out.append("")
        out.append("| Class | mAP50 | mAP50-95 | P | R |")
        out.append("|---|---|---|---|---|")
        for cls in sorted(data["per_class_loso"].keys()):
            pc = data["per_class_loso"][cls]
            out.append(
                f"| {cls} | "
                f"{fmt(pc.get('mAP50_mean'), pc.get('mAP50_std'))} | "
                f"{fmt(pc.get('mAP50_95_mean'), pc.get('mAP50_95_std'))} | "
                f"{fmt(pc.get('precision_mean'))} | "
                f"{fmt(pc.get('recall_mean'))} |"
            )
        out.append("")
    return out


def fmt_bootstrap(bootstrap: dict) -> list[str]:
    out = ["## Bootstrap CIs (block, 95%)", ""]
    out.append("| Config / Fold | F1 (point) | F1 95% CI | P 95% CI | R 95% CI |")
    out.append("|---|---|---|---|---|")
    for key, items in bootstrap.items():
        for ci in items:
            out.append(
                f"| {key} (seed={ci.get('seed')}) | "
                f"{fmt(ci.get('F1_mean'))} | "
                f"[{fmt(ci.get('F1_ci_lo'))}, {fmt(ci.get('F1_ci_hi'))}] | "
                f"[{fmt(ci.get('P_ci_lo'))}, {fmt(ci.get('P_ci_hi'))}] | "
                f"[{fmt(ci.get('R_ci_lo'))}, {fmt(ci.get('R_ci_hi'))}] |"
            )
    out.append("")
    return out


def fmt_confusion(confusion: dict) -> list[str]:
    out = ["## Confusion matrices (LOSO total: sum across folds × seeds)", ""]
    class_names = ["bin_ok", "bin_overflow", "ground_trash", "background"]
    for cfg, data in confusion.items():
        loso_total = data.get("loso_total")
        if not loso_total:
            continue
        out.append(f"### {cfg}")
        out.append("")
        out.append(f"| true \\ pred | {' | '.join(class_names)} |")
        out.append(f"| {' | '.join(['---'] * (len(class_names) + 1))} |")
        for i, row in enumerate(loso_total):
            out.append(f"| {class_names[i]} | {' | '.join(str(v) for v in row)} |")
        out.append("")
    return out


@click.command()
@click.option("--parsed", "parsed_paths", multiple=True, type=click.Path(path_type=Path, exists=True))
@click.option("--eval-all", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--bootstrap", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--confusion", type=click.Path(path_type=Path, exists=True), default=None)
@click.option("--out-md", type=click.Path(path_type=Path), default=Path("docs/runs_report.md"))
def main(
    parsed_paths: tuple[Path, ...],
    eval_all: Path | None,
    bootstrap: Path | None,
    confusion: Path | None,
    out_md: Path,
) -> None:
    summaries: dict[str, dict] = {}
    for p in parsed_paths:
        data = json.loads(p.read_text())
        for cfg, s in data.get("summary", {}).items():
            summaries[cfg] = s

    today = dt.date.today().isoformat()
    lines: list[str] = [
        f"# Runs report — {today}",
        "",
        f"_Auto-generated from {len(parsed_paths)} parsed_results.json + "
        f"{int(eval_all is not None)} eval_all + {int(bootstrap is not None)} bootstrap + "
        f"{int(confusion is not None)} confusion files._",
        "",
        "## Overall LOSO comparison",
        "",
    ]
    if summaries:
        lines.extend(fmt_overall_table(summaries))
        lines.append("")
        lines.append("## Per-fold breakdown")
        lines.append("")
        for cfg, s in summaries.items():
            lines.extend(fmt_per_fold(cfg, s))
    if eval_all and eval_all.exists():
        lines.extend(fmt_per_class(json.loads(eval_all.read_text())))
    if bootstrap and bootstrap.exists():
        lines.extend(fmt_bootstrap(json.loads(bootstrap.read_text())))
    if confusion and confusion.exists():
        lines.extend(fmt_confusion(json.loads(confusion.read_text())))

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines))
    click.echo(f"Wrote: {out_md}")


if __name__ == "__main__":
    main()
