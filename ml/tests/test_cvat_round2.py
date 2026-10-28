"""Тесты подготовки заданий CVAT для разметки №2."""

from __future__ import annotations

import pytest

from datasets.cvat_round2 import order_frames, prelabel_to_shape

LABEL_IDS = {"bin": 10, "ground_trash": 11}
ATTR_IDS = {"state": 100, "type": 101}


class TestPrelabelToShape:
    def test_bin_ok_becomes_bin_with_state_and_type_unset(self):
        # «Норма» модели не различает «пусто» и «есть мусор» — выбирает разметчик.
        shape = prelabel_to_shape([0.5, 0.5, 0.1, 0.2, 0.9, 0], frame=3, size=(2560, 1440),
                                  label_ids=LABEL_IDS, attr_ids=ATTR_IDS)
        assert shape["label_id"] == 10
        assert shape["frame"] == 3
        assert {a["spec_id"]: a["value"] for a in shape["attributes"]} == {100: "не указано", 101: "не указан"}

    def test_bin_overflow_becomes_bin_with_state_overflow(self):
        shape = prelabel_to_shape([0.5, 0.5, 0.1, 0.2, 0.9, 1], frame=0, size=(2560, 1440),
                                  label_ids=LABEL_IDS, attr_ids=ATTR_IDS)
        assert {a["spec_id"]: a["value"] for a in shape["attributes"]}[100] == "переполнение"

    def test_ground_trash_has_no_attributes(self):
        shape = prelabel_to_shape([0.5, 0.5, 0.1, 0.2, 0.9, 2], frame=0, size=(2560, 1440),
                                  label_ids=LABEL_IDS, attr_ids=ATTR_IDS)
        assert shape["label_id"] == 11
        assert shape["attributes"] == []

    def test_normalized_centre_box_becomes_pixel_corners(self):
        shape = prelabel_to_shape([0.5, 0.5, 0.1, 0.2, 0.9, 0], frame=0, size=(2560, 1440),
                                  label_ids=LABEL_IDS, attr_ids=ATTR_IDS)
        assert shape["points"] == pytest.approx([1152.0, 576.0, 1408.0, 864.0])

    def test_box_is_clipped_to_frame(self):
        shape = prelabel_to_shape([0.02, 0.98, 0.1, 0.1, 0.9, 0], frame=0, size=(2560, 1440),
                                  label_ids=LABEL_IDS, attr_ids=ATTR_IDS)
        x1, y1, x2, y2 = shape["points"]
        assert x1 == 0.0 and y2 == 1440.0


class TestOrderFrames:
    def test_groups_by_camera_then_time(self):
        names = [
            "camw42_2026-10-01_100000.jpg",
            "camw41_2026-10-03_090000.jpg",
            "camw5_2026-09-30_120000.jpg",
            "camw41_2026-09-30_230000.jpg",
        ]
        assert order_frames(names) == [
            "camw41_2026-09-30_230000.jpg",
            "camw41_2026-10-03_090000.jpg",
            "camw42_2026-10-01_100000.jpg",
            "camw5_2026-09-30_120000.jpg",
        ]
