"""Подготовка заданий CVAT для разметки №2: порядок кадров и предразметка.

Чистые функции; загрузка в CVAT — ml/scripts/cvat_upload_round2.py.
"""

from __future__ import annotations

# Классы боевой модели → метка разметки №2 и значение атрибута state.
# «Норма» модели не различает «пусто» и «есть мусор» (решение Арсения 08.10) —
# состояние выбирает разметчик, как и вид бака.
UNSET_STATE = "не указано"
MODEL_CLASSES = {0: ("bin", UNSET_STATE), 1: ("bin", "переполнение"), 2: ("ground_trash", None)}
UNKNOWN_TYPE = "не указан"


def order_frames(names: list[str]) -> list[str]:
    """По камерам, внутри камеры — по времени съёмки.

    Камера неподвижна, баки стоят на тех же местах — так горячая клавиша R
    (копировать рамки на следующие кадры) имеет смысл. Имя файла
    cam{key}_YYYY-MM-DD_HHMMSS.jpg сортируется по времени как строка.
    """
    return sorted(names, key=lambda n: (n.split("_", 1)[0], n))


def prelabel_to_shape(row, frame: int, size: tuple[int, int],
                      label_ids: dict[str, int], attr_ids: dict[str, int]) -> dict:
    """Рамка ансамбля [cx, cy, w, h, conf, class] (доли кадра) → прямоугольник CVAT."""
    cx, cy, w, h, _conf, cls = row
    width, height = size
    x1 = min(max((cx - w / 2) * width, 0.0), width)
    y1 = min(max((cy - h / 2) * height, 0.0), height)
    x2 = min(max((cx + w / 2) * width, 0.0), width)
    y2 = min(max((cy + h / 2) * height, 0.0), height)

    label, state = MODEL_CLASSES[int(round(cls))]
    attributes = []
    if label == "bin":
        attributes = [
            {"spec_id": attr_ids["state"], "value": state},
            {"spec_id": attr_ids["type"], "value": UNKNOWN_TYPE},
        ]
    return {
        "type": "rectangle", "frame": frame, "label_id": label_ids[label], "group": 0,
        "source": "auto", "occluded": False, "outside": False, "rotation": 0.0,
        "z_order": 0, "elements": [], "points": [x1, y1, x2, y2], "attributes": attributes,
    }
