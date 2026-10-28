"""Тесты отбора кадров для разметки №2 (кадры платформы Watcher, октябрь 2026)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest
from PIL import Image

from datasets.round2_selection import (
    SIMFEROPOL,
    assign_packs,
    extend_packs,
    frame_time_utc,
    is_night,
    is_night_by_sun,
    kcenter_greedy,
    roi_brightness,
    roi_crop_box,
    select_indices,
    sun_altitude,
    uncertain_boxes,
    uncertain_mask,
)


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


# ── frame_time_utc ────────────────────────────────────────────────────


class TestFrameTimeUtc:
    def test_parses_server_utc_timestamp_from_name(self):
        # Время в имени ставит watcher_sync по часам сервера, в UTC; надпись
        # на самом кадре (1970 год) не используется.
        assert frame_time_utc("camw41_2026-10-01_094336.jpg") == _utc(2026, 10, 1, 9, 43, 36)


# ── sun_altitude / is_night_by_sun ────────────────────────────────────


class TestSunAltitude:
    def test_summer_solstice_noon_is_high(self):
        # Полдень по солнцу в Симферополе ≈ 09:45 UTC; высота ≈ 90 − 44.95 + 23.44.
        assert sun_altitude(*SIMFEROPOL, _utc(2026, 6, 21, 9, 45)) == pytest.approx(68.5, abs=1.0)

    def test_winter_solstice_noon_is_low(self):
        assert sun_altitude(*SIMFEROPOL, _utc(2026, 12, 21, 9, 45)) == pytest.approx(21.6, abs=1.0)

    def test_local_midnight_is_deep_below_horizon(self):
        assert sun_altitude(*SIMFEROPOL, _utc(2026, 10, 1, 21, 0)) < -30


class TestIsNightBySun:
    def test_equinox_sunrise_falls_between_03_and_05_utc(self):
        # На равноденствие восход ≈ 06:00 по солнцу = ≈ 03:50 UTC при долготе 34.1°.
        assert is_night_by_sun(_utc(2026, 9, 23, 3, 0))
        assert not is_night_by_sun(_utc(2026, 9, 23, 5, 0))

    def test_moscow_afternoon_is_day_and_late_evening_is_night(self):
        assert not is_night_by_sun(_utc(2026, 10, 1, 12, 0))   # 15:00 МСК
        assert is_night_by_sun(_utc(2026, 10, 1, 19, 0))       # 22:00 МСК


# ── roi_brightness ────────────────────────────────────────────────────


class TestRoiBrightness:
    def test_black_zone_in_bright_frame_is_dark(self):
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        img.paste((0, 0, 0), (10, 10, 50, 50))
        assert roi_brightness(img, [[10, 10, 50, 50]]) == pytest.approx(0.0)

    def test_no_zone_measures_whole_frame(self):
        img = Image.new("RGB", (100, 100), (200, 200, 200))
        assert roi_brightness(img, None) == pytest.approx(200.0, abs=1.0)


# ── uncertain_mask ────────────────────────────────────────────────────


class TestUncertainMask:
    def test_keeps_only_top_third_by_count(self):
        # Признак «есть хоть одна сомнительная рамка» срабатывал почти на всех
        # кадрах — берём только верхнюю треть камеры по числу таких рамок.
        mask = uncertain_mask(np.array([0, 0, 1, 5, 5, 9]))
        assert mask.tolist() == [False, False, False, True, True, True]

    def test_no_uncertain_boxes_means_empty_mask(self):
        assert not uncertain_mask(np.array([0, 0, 0])).any()


# ── is_night ──────────────────────────────────────────────────────────


class TestIsNight:
    def test_grayscale_ir_frame_is_night(self):
        # Ночью камера переходит в ИК-режим и отдаёт бесцветный кадр.
        gray = Image.new("RGB", (64, 36), (120, 120, 120))
        assert is_night(gray)

    def test_colour_frame_is_day(self):
        img = Image.new("RGB", (64, 36), (40, 160, 60))
        assert not is_night(img)

    def test_near_gray_with_compression_noise_is_night(self):
        rng = np.random.default_rng(0)
        base = np.full((36, 64, 3), 128, dtype=np.int16)
        noisy = np.clip(base + rng.integers(-3, 4, size=base.shape), 0, 255).astype(np.uint8)
        assert is_night(Image.fromarray(noisy))


# ── kcenter_greedy ────────────────────────────────────────────────────


class TestKCenterGreedy:
    def test_picks_far_apart_points_first(self):
        # Два плотных облака и одна дальняя точка: из трёх выбранных
        # должны оказаться представители всех трёх мест.
        emb = np.array(
            [[0.0, 0.0], [0.01, 0.0], [0.0, 0.01],
             [1.0, 0.0], [1.01, 0.0],
             [0.0, 5.0]]
        )
        picked = kcenter_greedy(emb, k=3)
        groups = {0 if i < 3 else 1 if i < 5 else 2 for i in picked}
        assert groups == {0, 1, 2}

    def test_continues_from_already_selected(self):
        emb = np.array([[0.0, 0.0], [0.1, 0.0], [10.0, 0.0]])
        picked = kcenter_greedy(emb, k=1, already=[0])
        assert picked == [2]

    def test_never_returns_already_selected_or_duplicates(self):
        emb = np.random.default_rng(1).normal(size=(20, 4))
        picked = kcenter_greedy(emb, k=10, already=[3, 7])
        assert len(picked) == len(set(picked)) == 10
        assert not {3, 7} & set(picked)

    def test_k_larger_than_pool_returns_whole_pool(self):
        emb = np.eye(3)
        assert sorted(kcenter_greedy(emb, k=10)) == [0, 1, 2]


# ── uncertain_boxes ───────────────────────────────────────────────────


def _box(cx, cy, conf, cls=0, w=0.1, h=0.1):
    return np.array([cx, cy, w, h, conf, cls], dtype=np.float32)


class TestUncertainBoxes:
    def test_weak_box_without_confirmed_twin_is_uncertain(self):
        weak = np.stack([_box(0.5, 0.5, 0.2)])
        strong = np.empty((0, 6), dtype=np.float32)
        assert len(uncertain_boxes(weak, strong)) == 1

    def test_weak_box_matching_confirmed_box_is_not_uncertain(self):
        weak = np.stack([_box(0.5, 0.5, 0.2)])
        strong = np.stack([_box(0.505, 0.5, 0.8)])
        assert len(uncertain_boxes(weak, strong)) == 0

    def test_class_disagreement_counts_as_uncertain(self):
        # Модель уверена, что бак в норме, но часть ансамбля видит переполнение.
        weak = np.stack([_box(0.5, 0.5, 0.2, cls=1)])
        strong = np.stack([_box(0.5, 0.5, 0.8, cls=0)])
        assert len(uncertain_boxes(weak, strong)) == 1


# ── roi_crop_box ──────────────────────────────────────────────────────


class TestRoiCropBox:
    def test_union_of_several_rects(self):
        assert roi_crop_box([[10, 20, 30, 40], [5, 50, 25, 60]], (100, 100)) == (5, 20, 30, 60)

    def test_no_roi_means_whole_frame(self):
        assert roi_crop_box(None, (2560, 1440)) == (0, 0, 2560, 1440)


# ── assign_packs ──────────────────────────────────────────────────────


class TestAssignPacks:
    def test_every_frame_lands_in_exactly_one_pack(self):
        frames = [(f"cam{c}", f"f{c}_{i}") for c in "abc" for i in range(10)]
        packs = assign_packs(frames, n_packs=8)
        flat = [f for p in packs for f in p]
        assert sorted(flat) == sorted(name for _, name in frames)

    def test_pack_sizes_differ_by_at_most_one(self):
        frames = [(f"cam{c}", f"f{c}_{i}") for c in "abcd" for i in range(13)]
        sizes = [len(p) for p in assign_packs(frames, n_packs=8)]
        assert max(sizes) - min(sizes) <= 1

    def test_a_camera_is_spread_over_packs(self):
        # Один человек не должен получить камеру целиком — его манера разметки
        # тогда целиком ляжет на эту камеру.
        frames = [("cam_a", f"a{i}") for i in range(16)] + [("cam_b", f"b{i}") for i in range(16)]
        packs = assign_packs(frames, n_packs=8)
        assert all(any(f.startswith("a") for f in p) and any(f.startswith("b") for f in p) for p in packs)


# ── extend_packs ──────────────────────────────────────────────────────


class TestExtendPacks:
    def test_existing_frames_keep_their_packs(self):
        existing = {"a1": 1, "a2": 2, "b1": 3}
        result = extend_packs(existing, [("w11", "n1"), ("w11", "n2")], n_packs=3)
        assert {k: result[k] for k in existing} == existing

    def test_new_frames_go_to_the_smallest_packs_first(self):
        existing = {"a1": 1, "a2": 1, "b1": 2, "b2": 2, "c1": 3}
        result = extend_packs(existing, [("w11", "n1")], n_packs=3)
        assert result["n1"] == 3

    def test_sizes_stay_within_one_and_ties_go_to_the_lower_pack(self):
        existing = {f"f{i}": i % 8 + 1 for i in range(467)}   # 1–3: 59, 4–8: 58
        new = [("w11", f"n{i}") for i in range(9)]
        result = extend_packs(existing, new, n_packs=8)
        sizes = [list(result.values()).count(p) for p in range(1, 9)]
        assert max(sizes) - min(sizes) <= 1
        assert [result[f"n{i}"] for i in range(9)] == [4, 5, 6, 7, 8, 1, 2, 3, 4]


    def test_new_frames_go_only_to_open_packs(self):
        existing = {"a1": 5, "a2": 6, "b1": 1}
        new = [("w9", f"n{i}") for i in range(6)]
        result = extend_packs(existing, new, n_packs=8, packs=[1, 2, 3])
        assert {result[f"n{i}"] for i in range(6)} <= {1, 2, 3}
        assert [list(result.values()).count(p) for p in (1, 2, 3)] == [3, 2, 2]


# ── select_indices ────────────────────────────────────────────────────


class TestSelectIndices:
    def _pool(self, n=30, n_night=10, seed=0):
        emb = np.random.default_rng(seed).normal(size=(n, 8))
        night = np.zeros(n, dtype=bool)
        night[:n_night] = True
        return emb, night, np.zeros(n, dtype=bool)

    def test_without_fixed_fills_quota_with_a_third_at_night(self):
        emb, night, unsure = self._pool()
        picks = select_indices(emb, night, unsure, quota=9)
        idx = [i for i, _ in picks]
        assert len(idx) == len(set(idx)) == 9
        assert sum(night[i] for i in idx) == 3

    def test_fixed_frames_count_toward_quota_and_are_not_returned(self):
        emb, night, unsure = self._pool()
        fixed = [12, 13, 14, 0]             # три дневных и один ночной
        picks = select_indices(emb, night, unsure, quota=9, fixed=fixed)
        idx = [i for i, _ in picks]
        assert len(idx) == 5 and not set(fixed) & set(idx)
        assert sum(night[i] for i in idx + fixed) == 3

    def test_new_picks_avoid_twins_of_fixed_frames(self):
        # Кадр 1 — почти копия закреплённого кадра 0; брать его не нужно,
        # пока есть непохожие.
        emb = np.array([[0.0, 0.0], [0.01, 0.0], [5.0, 0.0], [0.0, 5.0], [5.0, 5.0]])
        night = np.zeros(5, dtype=bool)
        picks = select_indices(emb, night, np.zeros(5, dtype=bool), quota=4, fixed=[0])
        assert 1 not in [i for i, _ in picks]

    def test_more_fixed_than_quota_adds_nothing(self):
        emb, night, unsure = self._pool()
        assert select_indices(emb, night, unsure, quota=2, fixed=[11, 12, 13]) == []

    def test_fixed_frames_that_are_not_uncertain_keep_the_uncertain_share(self):
        emb, night, _ = self._pool(n=30, n_night=0)
        unsure = np.zeros(30, dtype=bool)
        unsure[20:] = True
        picks = select_indices(emb, night, unsure, quota=15, fixed=[0, 1, 2, 3, 4])
        assert sum(reason == "сомнение" for _, reason in picks) == 3   # 20% от 15
