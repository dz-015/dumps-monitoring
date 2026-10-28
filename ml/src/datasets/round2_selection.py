"""Отбор кадров платформы Watcher для разметки №2 (октябрь 2026).

Чистые функции без ввода-вывода; сборка конвейера — ml/scripts/select_round2.py.

Почему не «топ по дисперсии пикселей»: камера неподвижна, и дисперсия яркости
выбирает самые контрастные кадры (блики, засветку фарами), а не разные
состояния площадки. Вместо этого — k-center greedy по признакам DINOv2
вырезки зоны площадки: каждый следующий кадр — самый непохожий на уже взятые.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
from PIL import Image

# Широта и долгота Симферополя — все камеры платформы в городе.
SIMFEROPOL = (44.95, 34.10)

# Высота центра солнца на восходе/закате с учётом рефракции и радиуса диска.
SUNSET_ALTITUDE = -0.833

# Средняя насыщенность (HSV, 0..255), ниже которой кадр считаем ночным.
# Ночью камера в ИК-режиме и отдаёт бесцветную картинку; шум сжатия даёт
# насыщенность в единицы. Сверено 02.10.2026 на 923 кадрах платформы: ночные
# 406 кадров — ниже 2, дневные 517 — от 14 и выше, между ними пусто.
NIGHT_SATURATION = 12.0

# Две рамки — «одно и то же» при IoU не ниже этого (как в ансамбле прода).
MATCH_IOU = 0.5


def is_night(image: Image.Image) -> bool:
    small = image.convert("RGB").resize((160, 90))
    saturation = np.asarray(small.convert("HSV"), dtype=np.float32)[..., 1]
    return float(saturation.mean()) < NIGHT_SATURATION


def frame_time_utc(name: str) -> datetime:
    """Время съёмки из имени `cam{key}_YYYY-MM-DD_HHMMSS.jpg`.

    Его ставит watcher_sync по часам сервера в UTC. Надпись на кадре не годится:
    часы камер сбиты (1970 год).
    """
    _, date, time = name.rsplit(".", 1)[0].split("_")
    return datetime.strptime(f"{date}_{time}", "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)


def sun_altitude(lat: float, lon: float, when: datetime) -> float:
    """Высота солнца в градусах (формулы NOAA, точность ~0.1° — с запасом)."""
    when = when.astimezone(timezone.utc)
    day = when.timetuple().tm_yday
    hour = when.hour + when.minute / 60 + when.second / 3600
    g = 2 * math.pi / 365 * (day - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    solar_minutes = hour * 60 + eqtime + 4 * lon
    hour_angle = math.radians(solar_minutes / 4 - 180)
    phi = math.radians(lat)
    cos_zenith = (math.sin(phi) * math.sin(decl)
                  + math.cos(phi) * math.cos(decl) * math.cos(hour_angle))
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))


def is_night_by_sun(when: datetime) -> bool:
    """Ночь — солнце над Симферополем ниже горизонта (между закатом и восходом)."""
    return sun_altitude(*SIMFEROPOL, when) < SUNSET_ALTITUDE


def roi_brightness(image: Image.Image, rects: list[list[int]] | None) -> float:
    """Средняя яркость (0..255) вырезки зоны — чтобы найти почти чёрные кадры."""
    crop = image.crop(roi_crop_box(rects, image.size)).convert("L").resize((128, 72))
    return float(np.asarray(crop, dtype=np.float32).mean())


def uncertain_mask(counts: np.ndarray) -> np.ndarray:
    """Кадры камеры из верхней трети по числу сомнительных рамок (и хотя бы с одной)."""
    counts = np.asarray(counts)
    if not (counts > 0).any():
        return np.zeros(len(counts), dtype=bool)
    return (counts > 0) & (counts >= np.quantile(counts, 2 / 3))


def kcenter_greedy(emb: np.ndarray, k: int, already: list[int] | None = None) -> list[int]:
    """Индексы k новых точек: каждая следующая — самая далёкая от уже выбранных.

    Если выбранных нет, первой берётся точка, самая далёкая от центра облака, —
    так результат не зависит от порядка файлов.
    """
    n = len(emb)
    already = list(already or [])
    k = min(k, n - len(set(already)))
    if k <= 0:
        return []

    picked: list[int] = []
    if already:
        dist = np.min(np.linalg.norm(emb[:, None] - emb[already][None], axis=2), axis=1)
    else:
        first = int(np.argmax(np.linalg.norm(emb - emb.mean(axis=0), axis=1)))
        picked.append(first)
        dist = np.linalg.norm(emb - emb[first], axis=1)
    dist[already] = -1.0
    if picked:
        dist[picked] = -1.0

    while len(picked) < k:
        nxt = int(np.argmax(dist))
        picked.append(nxt)
        dist = np.minimum(dist, np.linalg.norm(emb - emb[nxt], axis=1))
        dist[already] = -1.0
        dist[picked] = -1.0
    return picked


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1, bx2, by2 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return float(inter / union) if union > 0 else 0.0


def uncertain_boxes(weak: np.ndarray, strong: np.ndarray) -> np.ndarray:
    """Рамки, которые модель «почти видит».

    weak — ансамбль с низкой планкой (уверенность ≥0.1, хватает одного голоса),
    strong — боевая планка (≥0.25, два голоса из трёх). Сомнительная рамка —
    слабая, у которой нет подтверждённого двойника того же класса.
    """
    keep = [
        row for row in weak
        if not any(s[5] == row[5] and _iou(row, s) >= MATCH_IOU for s in strong)
    ]
    return np.stack(keep) if keep else np.empty((0, 6), dtype=np.float32)


def roi_crop_box(rects: list[list[int]] | None, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Общий охват всех прямоугольников зоны; без зоны — весь кадр."""
    if not rects:
        return (0, 0, size[0], size[1])
    xs1, ys1, xs2, ys2 = zip(*rects)
    return (min(xs1), min(ys1), max(xs2), max(ys2))


def assign_packs(frames: list[tuple[str, str]], n_packs: int) -> list[list[str]]:
    """Раскладка (камера, имя) по пачкам: размеры равны ±1, камера — по всем пачкам.

    Идём по кадрам, сгруппированным по камере, и раздаём по кругу со сквозным
    счётчиком — тогда каждая камера размазана по пачкам, а не отдана одному
    человеку целиком.
    """
    packs: list[list[str]] = [[] for _ in range(n_packs)]
    for i, (_, name) in enumerate(sorted(frames)):
        packs[i % n_packs].append(name)
    return packs


def extend_packs(existing: dict[str, int], frames: list[tuple[str, str]], n_packs: int,
                 packs: list[int] | None = None) -> dict[str, int]:
    """Дополнить готовую раскладку новыми кадрами, не трогая прежние.

    Каждый новый кадр (по порядку (камера, имя)) идёт в самую маленькую пачку,
    при равенстве — в пачку с меньшим номером. Нужно, когда в выборку
    добавляется камера, а пачки уже загружены и розданы. `packs` — в какие
    пачки можно докладывать (по умолчанию во все): пачки тех, кто уже
    закончил, закрыты.
    """
    result = dict(existing)
    sizes = {p: 0 for p in (packs or range(1, n_packs + 1))}
    for pack in existing.values():
        if pack in sizes:
            sizes[pack] += 1
    for _, name in sorted(frames):
        pack = min(sizes, key=lambda p: (sizes[p], p))
        result[name] = pack
        sizes[pack] += 1
    return result


def select_indices(emb: np.ndarray, night: np.ndarray, unsure: np.ndarray, quota: int,
                   fixed: list[int] | tuple[int, ...] = (), night_share: float = 1 / 3,
                   uncertain_share: float = 0.2) -> list[tuple[int, str]]:
    """Отбор кадров одной камеры: [(индекс, причина)] в порядке отбора.

    Ночь — `night_share` квоты (если ночных хватает), из каждой половины
    `uncertain_share` — сомнительные кадры, остальное — k-center по всем.
    `fixed` — уже размеченные кадры: они входят в квоту (и в долю ночи), не
    возвращаются, а k-center продолжает от них, чтобы новые кадры не повторяли их.
    """
    fixed = list(fixed)
    n_night = min(round(quota * night_share), int(night.sum()))
    want = {True: n_night, False: quota - n_night}
    taken = set(fixed)
    picked: list[tuple[int, str]] = []

    def take(mask, k, reason):
        k = min(k, quota - len(fixed) - len(picked))   # квота общая на камеру
        if k <= 0:
            return
        pool = np.flatnonzero(mask)
        local_already = [j for j, i in enumerate(pool) if i in taken]
        for j in kcenter_greedy(emb[pool], k, already=local_already):
            picked.append((int(pool[j]), reason))
            taken.add(int(pool[j]))

    for is_n in (False, True):
        bucket = night == is_n
        have = sum(1 for i in fixed if night[i] == is_n)
        have_unsure = sum(1 for i in fixed if night[i] == is_n and unsure[i])
        take(bucket & unsure, round(want[is_n] * uncertain_share) - have_unsure, "сомнение")
        got = have + sum(1 for i, _ in picked if night[i] == is_n)
        take(bucket, want[is_n] - got, "непохожий")
    return picked
