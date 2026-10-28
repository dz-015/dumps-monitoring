"""Tests for training.balance — class-imbalance helpers.

These tests document the invariants the existing functions already satisfy.
They were written retroactively — balance.py was committed without tests in
4a33a86 (ml: scaffolding). New code in this module must be TDD'd properly.
"""

from __future__ import annotations

import pytest

from training.balance import (
    compute_inverse_frequency_weights,
    count_instances_per_class,
)


# ── compute_inverse_frequency_weights ─────────────────────────────────


class TestInverseFrequencyWeights:
    def test_equal_counts_give_equal_weights(self):
        weights = compute_inverse_frequency_weights(
            instance_counts={"a": 10, "b": 10, "c": 10},
            class_order=["a", "b", "c"],
            smoothing=0.0,
        )
        assert weights == pytest.approx([1.0, 1.0, 1.0])

    def test_rarer_class_gets_higher_weight(self):
        weights = compute_inverse_frequency_weights(
            instance_counts={"common": 100, "rare": 10},
            class_order=["common", "rare"],
            smoothing=0.0,
        )
        # rare is 10× rarer → 10× weight
        assert weights[1] == pytest.approx(10 * weights[0])

    def test_weights_normalised_so_mean_is_one(self):
        weights = compute_inverse_frequency_weights(
            instance_counts={"a": 5, "b": 50, "c": 500},
            class_order=["a", "b", "c"],
            smoothing=0.0,
        )
        assert sum(weights) / len(weights) == pytest.approx(1.0)

    def test_class_order_controls_output_order(self):
        wa = compute_inverse_frequency_weights(
            instance_counts={"x": 10, "y": 100},
            class_order=["x", "y"],
            smoothing=0.0,
        )
        wb = compute_inverse_frequency_weights(
            instance_counts={"x": 10, "y": 100},
            class_order=["y", "x"],
            smoothing=0.0,
        )
        # Same numbers, swapped order
        assert wa[0] == pytest.approx(wb[1])
        assert wa[1] == pytest.approx(wb[0])

    def test_missing_class_treated_as_zero_count_with_smoothing(self):
        # 'c' is missing; with smoothing=1.0 it gets count 1, not error
        weights = compute_inverse_frequency_weights(
            instance_counts={"a": 9, "b": 9},
            class_order=["a", "b", "c"],
            smoothing=1.0,
        )
        assert len(weights) == 3
        # 'c' (count 1) should get the highest weight
        assert weights[2] > weights[0]
        assert weights[2] > weights[1]

    def test_zero_count_with_zero_smoothing_raises(self):
        with pytest.raises(ValueError, match="Zero count"):
            compute_inverse_frequency_weights(
                instance_counts={"a": 10, "b": 0},
                class_order=["a", "b"],
                smoothing=0.0,
            )

    def test_smoothing_dampens_extremes(self):
        # With smoothing, the gap between rare and common shrinks
        no_smooth = compute_inverse_frequency_weights(
            instance_counts={"common": 1000, "rare": 1},
            class_order=["common", "rare"],
            smoothing=0.0,
        )
        with_smooth = compute_inverse_frequency_weights(
            instance_counts={"common": 1000, "rare": 1},
            class_order=["common", "rare"],
            smoothing=10.0,
        )
        ratio_no_smooth = no_smooth[1] / no_smooth[0]
        ratio_with_smooth = with_smooth[1] / with_smooth[0]
        assert ratio_with_smooth < ratio_no_smooth


# ── count_instances_per_class ─────────────────────────────────────────


def _write_label_file(path, lines):
    """Helper: write a YOLO-format label file, one bbox per line."""
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


class TestCountInstancesPerClass:
    def test_empty_file_list_returns_empty_counter(self):
        counter = count_instances_per_class([], n_classes=7)
        assert dict(counter) == {}

    def test_single_file_counts_each_line(self, tmp_path):
        f = tmp_path / "img1.txt"
        _write_label_file(f, [
            "0 0.5 0.5 0.1 0.1",
            "0 0.3 0.3 0.1 0.1",
            "1 0.7 0.7 0.1 0.1",
        ])
        counter = count_instances_per_class([str(f)], n_classes=7)
        assert dict(counter) == {0: 2, 1: 1}

    def test_multiple_files_combined(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        _write_label_file(f1, ["0 0.5 0.5 0.1 0.1", "2 0.5 0.5 0.1 0.1"])
        _write_label_file(f2, ["0 0.5 0.5 0.1 0.1", "1 0.5 0.5 0.1 0.1"])
        counter = count_instances_per_class([str(f1), str(f2)], n_classes=7)
        assert dict(counter) == {0: 2, 1: 1, 2: 1}

    def test_class_id_out_of_range_skipped(self, tmp_path):
        f = tmp_path / "img.txt"
        _write_label_file(f, [
            "0 0.5 0.5 0.1 0.1",   # valid
            "7 0.5 0.5 0.1 0.1",   # >= n_classes → skip
            "-1 0.5 0.5 0.1 0.1",  # negative → skip
        ])
        counter = count_instances_per_class([str(f)], n_classes=7)
        assert dict(counter) == {0: 1}

    def test_blank_lines_skipped(self, tmp_path):
        f = tmp_path / "img.txt"
        f.write_text("0 0.5 0.5 0.1 0.1\n\n   \n1 0.5 0.5 0.1 0.1\n")
        counter = count_instances_per_class([str(f)], n_classes=7)
        assert dict(counter) == {0: 1, 1: 1}

    def test_empty_file_contributes_nothing(self, tmp_path):
        f = tmp_path / "negative.txt"
        f.write_text("")
        counter = count_instances_per_class([str(f)], n_classes=7)
        assert dict(counter) == {}
