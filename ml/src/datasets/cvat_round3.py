"""Подготовка заданий CVAT по схеме разметки от 13.10.2026: метки, черновые
рамки, раскладка по пачкам. Чистые функции; загрузка — ml/scripts/cvat_upload_round3.py.

Схема: «бак» — рамка только по корпусу, с видом и состоянием (не указано /
не переполнен / переполнено; «пусто» не ставится — это бак без рамки мусора);
«мусор бака» — весь видимый мусор бака; «мусор на земле» — низ кучи на земле.
"""

from __future__ import annotations

UNSET_STATE = "не указано"
UNKNOWN_TYPE = "не указан"

# Совпадает с LABELS в ml/cvat/razmetka/test/cvat.mjs — горячие клавиши
# (tools.js) опираются на эти имена.
LABELS = [
    {
        "name": "bin",
        "attributes": [
            {"name": "state", "mutable": True, "input_type": "select",
             "default_value": UNSET_STATE, "values": [UNSET_STATE, "не переполнен", "переполнено"]},
            {"name": "type", "mutable": True, "input_type": "select",
             "default_value": UNKNOWN_TYPE, "values": [UNKNOWN_TYPE, "евробак", "контейнер", "бутылки"]},
        ],
    },
    {"name": "bin_trash", "attributes": []},
    {"name": "ground_trash", "attributes": []},
]

# Классы старой модели и старой разметки → новая метка. Состояние черновой
# рамке не ставим: решают люди (старый «переполненный» бак ещё и включал гору).
OLD_CLASSES = {0: "bin", 1: "bin", 2: "ground_trash"}

_DUP_IOU = 0.6        # две рамки одной метки с таким перекрытием — один предмет
_DUP_INSIDE = 0.85    # рамка почти целиком внутри другой рамки той же метки


def yolo_txt_rows(text: str) -> list[list[float]]:
    """Строки YOLO «класс cx cy w h» (доли кадра) → [cx, cy, w, h, 1.0, класс]."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if parts:
            cls, cx, cy, w, h = int(parts[0]), *map(float, parts[1:5])
            rows.append([cx, cy, w, h, 1.0, cls])
    return rows


def _corners(row):
    cx, cy, w, h = row[:4]
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def _overlap(a, b) -> tuple[float, float]:
    """(IoU, доля меньшей рамки внутри большей)."""
    ax1, ay1, ax2, ay2 = _corners(a)
    bx1, by1, bx2, by2 = _corners(b)
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a, area_b = a[2] * a[3], b[2] * b[3]
    union = area_a + area_b - inter
    return (inter / union if union > 0 else 0.0,
            inter / min(area_a, area_b) if min(area_a, area_b) > 0 else 0.0)


def dedupe(rows: list[list[float]]) -> list[list[float]]:
    """Убрать двойные рамки одного предмета: из пары рамок одной НОВОЙ метки,
    которые почти совпадают или одна почти целиком внутри другой, остаётся
    более уверенная. Оба класса бака старой модели — одна метка «бак»."""
    kept: list[list[float]] = []
    for row in sorted(rows, key=lambda r: -r[4]):
        label = OLD_CLASSES[int(round(row[5]))]
        if any(OLD_CLASSES[int(round(k[5]))] == label
               and (lambda o: o[0] >= _DUP_IOU or o[1] >= _DUP_INSIDE)(_overlap(row, k))
               for k in kept):
            continue
        kept.append(row)
    return kept


def row_to_shape(row, frame: int, size: tuple[int, int],
                 label_ids: dict[str, int], attr_ids: dict[str, int]) -> dict:
    """[cx, cy, w, h, conf, класс] (доли кадра) → прямоугольник CVAT в пикселях кадра."""
    width, height = size
    x1, y1, x2, y2 = _corners(row)
    points = [min(max(x1 * width, 0.0), width), min(max(y1 * height, 0.0), height),
              min(max(x2 * width, 0.0), width), min(max(y2 * height, 0.0), height)]
    label = OLD_CLASSES[int(round(row[5]))]
    attributes = []
    if label == "bin":
        attributes = [{"spec_id": attr_ids["state"], "value": UNSET_STATE},
                      {"spec_id": attr_ids["type"], "value": UNKNOWN_TYPE}]
    return {
        "type": "rectangle", "frame": frame, "label_id": label_ids[label], "group": 0,
        "source": "auto", "occluded": False, "outside": False, "rotation": 0.0,
        "z_order": 0, "elements": [], "points": [round(p, 1) for p in points], "attributes": attributes,
    }


def buckets(names: list[str], size: int = 100) -> list[list[str]]:
    """Подряд по `size`; хвост меньше половины пачки присоединяется к последней."""
    chunks = [names[i:i + size] for i in range(0, len(names), size)]
    if len(chunks) > 1 and len(chunks[-1]) < size / 2:
        tail = chunks.pop()
        chunks[-1] += tail
    return chunks


def upload_name(camera: str, file: str) -> str:
    """Имя кадра в CVAT: у старых кадров (папка = номер камеры) — префикс камеры,
    иначе имена разных камер совпадают; новые кадры уже называются camw…"""
    return file if file.startswith("cam") else f"cam{camera}_{file}"
