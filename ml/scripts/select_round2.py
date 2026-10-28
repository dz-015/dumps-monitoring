"""Отбор кадров платформы Watcher для разметки №2 (октябрь 2026).

Конвейер (согласован с Арсением 02.10, пересмотрен 05.10.2026):

1. Кадры из data/round2/raw (скачаны с прода из ingest/processed, сверены
   по md5), без w38 (ветки закрывают кадр), без точных копий (зависший поток)
   и без нечитаемых файлов.
2. Прогон боевого ансамбля из трёх ONNX-моделей: «сильные» рамки — боевая
   планка (≥0.25, 2 голоса из 3), «сомнительные» — проходят низкую планку
   (≥0.1, 1 голос), но не боевую. Учитываются только рамки в зоне площадки.
3. Признаки DINOv2 по вырезке зоны площадки (без зоны — весь кадр).
4. Ночь — по солнцу над Симферополем во время съёмки (время из имени файла,
   UTC сервера), НЕ по цвету: под фонарями камера до 22:00 снимает в цвете.
   Ночь — ровно треть квоты каждой камеры (решение Арсения 05.10).
5. 20% квоты — сомнительные кадры: верхняя треть камеры по числу
   сомнительных рамок (k-center среди них); остальное — k-center по всем,
   продолжая от уже взятых.
6. Общий набор: первые, самые разные кадры каждой камеры (2 дня + 1 ночь) —
   его размечают все.
7. Остальное — по 8 пачкам, каждая камера размазана по всем пачкам.
8. Яркость зоны пишется в таблицу — почти чёрные кадры НЕ выкидываются,
   их показываем Арсению отдельно (решение 05.10).

Признаки и рамки кэшируются в data/round2/cache — пересчитываются только новые кадры.

    ml/venv/bin/python ml/scripts/select_round2.py --out sel_v2
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import click
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ML_ROOT = Path(__file__).resolve().parent.parent
REPO = ML_ROOT.parent
sys.path.insert(0, str(ML_ROOT / "src"))
sys.path.insert(0, str(REPO / "backend"))

from datasets.round2_selection import (  # noqa: E402
    assign_packs,
    extend_packs,
    frame_time_utc,
    is_night,
    is_night_by_sun,
    kcenter_greedy,
    roi_brightness,
    roi_crop_box,
    select_indices,
    uncertain_boxes,
    uncertain_mask,
)

RAW = ML_ROOT / "data" / "round2" / "raw"
CACHE = ML_ROOT / "data" / "round2" / "cache"
ROI_CONFIG = ML_ROOT / "configs" / "cameras_roi_v2.json"
MODELS = ML_ROOT / "models" / "rtdetr_temporal_640"

EXCLUDED = {"w38", "w11"}   # w38 — ветки закрывают кадр; w11 — кадры смазаны (решение Арсения 14.10)
QUOTA = {
    "w41": 40, "w42": 40, "w4": 40, "w8": 40, "w13": 40, "w47": 40,
    "w5": 60, "w39": 60, "w40": 60,   # модель на них не видит бункеры — берём больше
    "w25": 40, "w26": 40,             # включены 02.10, зон пока нет — признаки по всему кадру
    "w9": 30,                         # включена 12.10: баки за сплошной перегородкой (скрытые баки)
}
NIGHT_SHARE = 1 / 3
UNCERTAIN_SHARE = 0.2
N_PACKS = 8


def camera_key(name: str) -> str:
    return name.split("_")[0][3:]  # camw41_2026-... → w41


def load_rois() -> dict[str, list[list[int]]]:
    cfg = json.loads(ROI_CONFIG.read_text())
    return {k: v["rects"] for k, v in cfg.items() if k.startswith("w") and "rects" in v}


def inside_roi(rects, row, size) -> bool:
    if not rects:
        return True
    x, y = row[0] * size[0], row[1] * size[1]
    return any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in rects)


def readable(path: Path) -> bool:
    try:
        Image.open(path).load()
        return True
    except OSError:
        return False


def compute_features(frames: list[Path], rois) -> dict[str, dict]:
    """Признаки, рамки и яркость зоны по каждому кадру; кэш по имени файла."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / "features.json"
    emb_file = CACHE / "embeddings.npz"
    meta = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    embs = dict(np.load(emb_file)) if emb_file.exists() else {}

    def save():
        cache_file.write_text(json.dumps(meta))
        np.savez(emb_file, **embs)

    todo = [p for p in frames if p.name not in meta or p.name not in embs]
    if todo:
        import torch
        from transformers import AutoImageProcessor, AutoModel

        from app.ml.detector import Detector

        click.echo(f"считаю {len(todo)} новых кадров (DINOv2 + ансамбль)...")
        processor = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
        dino = AutoModel.from_pretrained("facebook/dinov2-base").eval()
        weak_det = Detector(MODELS, conf_threshold=0.1, min_votes=1)
        strong_det = Detector(MODELS, conf_threshold=0.25, min_votes=2)
        weak_det.load()

        for i, p in enumerate(todo, 1):
            img = Image.open(p).convert("RGB")
            rects = rois.get(camera_key(p.name))

            tensor = weak_det.preprocess(img)
            per_model = [weak_det._run_one(s, tensor) for s in weak_det._sessions]
            weak = weak_det._fuse(per_model)
            strong = strong_det._fuse([m[m[:, 4] >= 0.25] for m in per_model])
            weak = np.array([r for r in weak if inside_roi(rects, r, img.size)]).reshape(-1, 6)
            strong = np.array([r for r in strong if inside_roi(rects, r, img.size)]).reshape(-1, 6)
            unsure = uncertain_boxes(weak, strong)

            crop = img.crop(roi_crop_box(rects, img.size))
            with torch.no_grad():
                out = dino(**processor(images=crop, return_tensors="pt"))
            vec = out.last_hidden_state[0, 0].numpy()
            embs[p.name] = vec / np.linalg.norm(vec)

            meta[p.name] = {
                "camera": camera_key(p.name),
                "ir": is_night(img),   # режим камеры, только для сверки с солнцем
                "md5": hashlib.md5(p.read_bytes()).hexdigest(),
                "strong": strong.round(4).tolist(),
                "uncertain": unsure.round(4).tolist(),
                "brightness": round(roi_brightness(img, rects), 1),
            }
            if i % 50 == 0 or i == len(todo):
                click.echo(f"  {i}/{len(todo)}")
                save()

    # Кэш первого прогона (02.10) писал режим камеры под ключом "night"
    # (тогда ночь определяли по цвету) — переносим в "ir".
    for p in frames:
        if "ir" not in meta[p.name]:
            meta[p.name]["ir"] = meta[p.name].pop("night")

    # Кадры из кэша первого прогона без яркости — досчитываем.
    missing = [p for p in frames if "brightness" not in meta[p.name]]
    for p in missing:
        meta[p.name]["brightness"] = round(
            roi_brightness(Image.open(p).convert("RGB"), rois.get(camera_key(p.name))), 1)
    if missing:
        click.echo(f"досчитал яркость зоны для {len(missing)} кадров из кэша")
        save()

    return {
        n: {**meta[n], "emb": embs[n], "night": is_night_by_sun(frame_time_utc(n))}
        for n in (p.name for p in frames)
    }


def select_camera(names, feats, quota, fixed=()):
    """Отбор по одной камере: [(имя, причина)] — сначала закреплённые, потом новые."""
    emb = np.stack([feats[n]["emb"] for n in names])
    night = np.array([feats[n]["night"] for n in names])
    unsure = uncertain_mask(np.array([len(feats[n]["uncertain"]) for n in names]))
    fixed_idx = [names.index(n) for n in fixed]
    picks = select_indices(emb, night, unsure, quota, fixed_idx, NIGHT_SHARE, UNCERTAIN_SHARE)
    return [(n, "размечен") for n in fixed] + [(names[i], reason) for i, reason in picks]


def contact_sheet(rows, out: Path, title: str):
    """Сетка миниатюр для просмотра глазами."""
    tw, th, cols = 384, 216, 5
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    n_rows = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, n_rows * (th + 24) + 40), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), title, fill=(255, 255, 0), font=font)
    for i, r in enumerate(rows):
        x, y = (i % cols) * tw, 40 + (i // cols) * (th + 24)
        sheet.paste(Image.open(RAW / r["file"]).convert("RGB").resize((tw, th)), (x, y))
        stamp = r["msk"][5:]  # ММ-ДД ЧЧ:ММ
        tag = f"{'Н' if r['night'] else 'Д'} {stamp} {r['reason']}{' ОБЩИЙ' if r['common'] else ''}"
        d.text((x + 4, y + th + 3), tag, fill=(0, 255, 255) if r["common"] else (230, 230, 230), font=font)
    sheet.save(out, quality=85)


def keep_packs(base_name: str, selected: list[dict], common: set[str],
               rest: list[tuple[str, str]]) -> dict[str, int]:
    """Пачки прежней выборки — без перестановок; новые кадры доложить в самые маленькие."""
    base = list(csv.DictReader(open(ML_ROOT / "data" / "round2" / base_name / "manifest.csv", encoding="utf-8")))
    names = {s["file"] for s in selected}
    lost = [r["file"] for r in base if r["file"] not in names]
    moved = [r["file"] for r in base if (r["pack"] == "общий") != (r["file"] in common)]
    if lost or moved:
        raise click.ClickException(f"выборка разошлась с {base_name}: выпали {lost[:5]}, "
                                   f"сменили общий набор {moved[:5]} — сохранить пачки нельзя")
    existing = {r["file"]: int(r["pack"]) for r in base if r["pack"] != "общий"}
    new = [(cam, name) for cam, name in rest if name not in existing]
    click.echo(f"пачки из {base_name}: {len(existing)} кадров на местах, новых {len(new)}")
    return extend_packs(existing, new, N_PACKS)


@click.command()
@click.option("--out", "out_name", default="sel_v2")
@click.option("--keep-packs", "keep_from", default=None,
              help="выборка, чьи пачки сохранить: её кадры остаются на местах, новые — в самые маленькие пачки")
@click.option("--fix-from", "fix_from", default=None,
              help="выборка, чьи размеченные кадры закрепить: общий набор и пачки из --fix-packs")
@click.option("--fix-packs", default="", help="номера уже размеченных пачек через запятую, например 5,6")
@click.option("--review-dir", type=click.Path(path_type=Path),
              default=Path("/mnt/c/Users/killh/Desktop/Разметка-отбор-v2"))
def main(out_name: str, keep_from: str | None, fix_from: str | None, fix_packs: str,
         review_dir: Path) -> None:
    from datetime import timedelta, timezone
    msk = timezone(timedelta(hours=3))

    rois = load_rois()
    frames, broken = [], []
    for p in sorted(RAW.glob("camw*.jpg")):
        if camera_key(p.name) in EXCLUDED:
            continue
        (frames if readable(p) else broken).append(p)
    if broken:
        click.secho(f"нечитаемые, пропущены: {[p.name for p in broken]}", fg="yellow")
    feats = compute_features(frames, rois)

    # Точные копии (зависший поток) — оставляем первую.
    seen, by_cam = set(), defaultdict(list)
    for p in frames:
        if feats[p.name]["md5"] in seen:
            continue
        seen.add(feats[p.name]["md5"])
        by_cam[feats[p.name]["camera"]].append(p.name)

    fixed_pack, base_common = {}, set()
    if fix_from:
        closed = {int(x) for x in fix_packs.split(",") if x}
        base = list(csv.DictReader(open(ML_ROOT / "data" / "round2" / fix_from / "manifest.csv", encoding="utf-8")))
        base_common = {r["file"] for r in base if r["pack"] == "общий"}
        fixed_pack = {r["file"]: int(r["pack"]) for r in base if r["pack"] != "общий" and int(r["pack"]) in closed}
        pool = {n for names in by_cam.values() for n in names}
        missing = sorted((base_common | set(fixed_pack)) - pool)
        if missing:
            raise click.ClickException(f"закреплённых кадров нет в пуле: {missing[:5]}")
        click.echo(f"закреплено из {fix_from}: общий набор {len(base_common)}, пачки {sorted(closed)} — {len(fixed_pack)}")
    fixed_all = base_common | set(fixed_pack)

    selected = []
    for cam, quota in QUOTA.items():
        fixed = [n for n in by_cam[cam] if n in fixed_all]
        picks = select_camera(by_cam[cam], feats, quota, fixed)
        selected += [{"file": n, "camera": cam, "reason": r} for n, r in picks]
        n_night = sum(feats[n]["night"] for n, _ in picks)
        click.echo(f"{cam}: пул {len(by_cam[cam])} (ночь {sum(feats[n]['night'] for n in by_cam[cam])}), "
                   f"взято {len(picks)}, из них ночь {n_night}")

    # Общий набор: первые (самые разные) кадры каждой камеры — 2 дня + 1 ночь.
    common = set(base_common)
    for cam in QUOTA:
        rows = [s["file"] for s in selected if s["camera"] == cam]
        if fix_from and any(r in base_common for r in rows):
            continue   # у камеры уже есть кадры в общем наборе — его не трогаем
        common |= set([n for n in rows if not feats[n]["night"]][:2])
        common |= set([n for n in rows if feats[n]["night"]][:1])

    rest = [(s["camera"], s["file"]) for s in selected if s["file"] not in common]
    if fix_from:
        open_packs = [p for p in range(1, N_PACKS + 1) if p not in set(fixed_pack.values())]
        new = [(cam, name) for cam, name in rest if name not in fixed_pack]
        pack_of = extend_packs(fixed_pack, new, N_PACKS, packs=open_packs)
        click.echo(f"новые {len(new)} кадров — в пачки {open_packs}")
    elif keep_from:
        pack_of = keep_packs(keep_from, selected, common, rest)
    else:
        pack_of = {name: i + 1 for i, pack in enumerate(assign_packs(rest, N_PACKS)) for name in pack}

    out = ML_ROOT / "data" / "round2" / out_name
    (out / "frames").mkdir(parents=True, exist_ok=True)
    prelabels = {}
    for s in selected:
        f = feats[s["file"]]
        s.update(
            msk=frame_time_utc(s["file"]).astimezone(msk).strftime("%Y-%m-%d %H:%M"),
            night=f["night"], camera_ir=f["ir"], brightness=f["brightness"],
            common=s["file"] in common,
            pack="общий" if s["file"] in common else pack_of[s["file"]],
            n_strong=len(f["strong"]), n_uncertain=len(f["uncertain"]),
        )
        shutil.copy2(RAW / s["file"], out / "frames" / s["file"])
        prelabels[s["file"]] = f["strong"]

    fields = ["file", "camera", "msk", "night", "camera_ir", "brightness", "reason",
              "common", "pack", "n_strong", "n_uncertain"]
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(selected)
    # Предразметка: боевые рамки ансамбля [cx, cy, w, h, conf, class] в долях кадра.
    (out / "prelabels.json").write_text(json.dumps(prelabels, ensure_ascii=False))

    review_dir.mkdir(parents=True, exist_ok=True)
    for cam in QUOTA:
        rows = sorted((s for s in selected if s["camera"] == cam), key=lambda s: s["file"])
        contact_sheet(rows, review_dir / f"{cam}.jpg",
                      f"{cam}: {len(rows)} кадров (Д/Н — день/ночь по солнцу, время МСК; голубым — общий набор)")
    shutil.copy2(out / "manifest.csv", review_dir / "manifest.csv")

    packs = defaultdict(int)
    for s in selected:
        packs[s["pack"]] += 1
    click.echo(f"всего {len(selected)}, общий набор {len(common)}, пачки: "
               + ", ".join(f"{k}: {v}" for k, v in sorted(packs.items(), key=str)))
    click.echo(f"ночных {sum(s['night'] for s in selected)} "
               f"({sum(s['night'] for s in selected) / len(selected):.1%}), "
               f"сомнительных {sum(s['reason'] == 'сомнение' for s in selected)}")


if __name__ == "__main__":
    main()
