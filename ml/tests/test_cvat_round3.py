"""Тесты подготовки заданий CVAT по схеме разметки от 13.10.2026."""

from __future__ import annotations

from datasets.cvat_round3 import (
    LABELS,
    buckets,
    dedupe,
    row_to_shape,
    upload_name,
    yolo_txt_rows,
)

LABEL_IDS = {"bin": 1, "bin_trash": 2, "ground_trash": 3}
ATTR_IDS = {"state": 10, "type": 11}


class TestLabels:
    def test_three_labels_and_no_empty_state(self):
        assert [lab["name"] for lab in LABELS] == ["bin", "bin_trash", "ground_trash"]
        state = next(a for a in LABELS[0]["attributes"] if a["name"] == "state")
        assert state["values"] == ["не указано", "не переполнен", "переполнено"]
        assert state["default_value"] == "не указано"


class TestYoloTxtRows:
    def test_parses_class_and_box_with_full_confidence(self):
        rows = yolo_txt_rows("1 0.5 0.4 0.1 0.2\n\n2 0.2 0.8 0.05 0.05\n")
        assert rows == [[0.5, 0.4, 0.1, 0.2, 1.0, 1], [0.2, 0.8, 0.05, 0.05, 1.0, 2]]


class TestDedupe:
    def test_two_bin_classes_on_one_bin_become_one_box(self):
        # Старая модель видит один бак то как «норму», то как «переполненный».
        rows = [[0.5, 0.5, 0.1, 0.2, 0.6, 0], [0.505, 0.5, 0.1, 0.2, 0.8, 1]]
        assert dedupe(rows) == [[0.505, 0.5, 0.1, 0.2, 0.8, 1]]

    def test_box_inside_a_bigger_box_of_the_same_label_is_dropped(self):
        rows = [[0.5, 0.5, 0.2, 0.2, 0.9, 2], [0.52, 0.52, 0.05, 0.05, 0.5, 2]]
        assert len(dedupe(rows)) == 1

    def test_neighbouring_bins_both_stay(self):
        rows = [[0.40, 0.5, 0.1, 0.2, 0.9, 0], [0.52, 0.5, 0.1, 0.2, 0.9, 0]]
        assert len(dedupe(rows)) == 2

    def test_bin_and_ground_trash_in_one_place_both_stay(self):
        rows = [[0.5, 0.5, 0.1, 0.2, 0.9, 0], [0.5, 0.5, 0.1, 0.2, 0.9, 2]]
        assert len(dedupe(rows)) == 2


class TestRowToShape:
    def test_bin_gets_pixel_box_and_unset_attributes(self):
        shape = row_to_shape([0.5, 0.5, 0.1, 0.2, 0.9, 1], frame=3, size=(1920, 1080),
                             label_ids=LABEL_IDS, attr_ids=ATTR_IDS)
        assert shape["frame"] == 3 and shape["label_id"] == 1
        assert shape["points"] == [864.0, 432.0, 1056.0, 648.0]
        assert {a["spec_id"]: a["value"] for a in shape["attributes"]} == {10: "не указано", 11: "не указан"}

    def test_ground_trash_has_no_attributes_and_box_is_clipped(self):
        shape = row_to_shape([0.02, 0.5, 0.1, 0.1, 0.9, 2], frame=0, size=(2560, 1440),
                             label_ids=LABEL_IDS, attr_ids=ATTR_IDS)
        assert shape["label_id"] == 3 and shape["attributes"] == []
        assert shape["points"][0] == 0.0


class TestBuckets:
    def test_chunks_of_hundred_keep_order_and_last_takes_the_rest(self):
        names = [f"f{i:04d}" for i in range(250)]
        got = buckets(names, size=100)
        assert [len(b) for b in got] == [100, 100, 50]
        assert sum(got, []) == names

    def test_tiny_tail_joins_the_previous_bucket(self):
        got = buckets([f"f{i}" for i in range(2022)], size=100)
        assert [len(b) for b in got][-2:] == [100, 122]


class TestUploadName:
    def test_old_frame_gets_camera_prefix_and_new_frame_stays(self):
        assert upload_name("3", "2026-02-26_131654.jpg") == "cam3_2026-02-26_131654.jpg"
        assert upload_name("w9", "camw9_2026-10-12_151242.jpg") == "camw9_2026-10-12_151242.jpg"
