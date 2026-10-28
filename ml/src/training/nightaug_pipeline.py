"""NightAug-Soiling-CCTV augmentation pipeline for low-light + multi-bin scenes.

Recipe derived from cowork research 2026-05-13 (docs/research_13.05.md):
- Kennerley et al. 2PCNet CVPR 2023 (arXiv:2303.13853) NightAug stack
- Ghiasi et al. CVPR 2021 (arXiv:2012.07177) for copy-paste reference
- Albumentations weather transforms for cam_7 sun glare

Target failure modes:
- cam_2: multi-bin night scenes (lowest mAP 0.277 RT-DETR baseline)
- cam_7: high-contrast morning sun glare (early-epoch collapse YOLOv8m)

For Ultralytics integration via the `augmentations=` hook (2025 API).
"""

from __future__ import annotations

import albumentations as A


def night_aug_cctv(imgsz: int = 640) -> A.Compose:
    """Default recipe: color/exposure heavy + light noise + sparse weather.

    Tuned for our 1920x1080 source frames downsampled to imgsz x imgsz training.
    src_radius for RandomSunFlare scaled to imgsz (linear: 120 at 640).
    """
    flare_radius = max(80, int(imgsz * 0.19))  # 120 at 640, 240 at 1280

    return A.Compose(
        [
            # Color / exposure — main attack on cam_2 night content
            A.RandomBrightnessContrast(
                brightness_limit=(-0.4, 0.2),  # asymmetric: bias toward darkening
                contrast_limit=(-0.3, 0.3),
                p=0.5,
            ),
            A.RandomGamma(gamma_limit=(60, 140), p=0.4),
            A.RandomToneCurve(scale=0.2, p=0.3),
            A.HueSaturationValue(
                hue_shift_limit=10,
                sat_shift_limit=20,
                val_shift_limit=30,
                p=0.3,
            ),
            # Noise / blur — night ISO noise + motion blur
            A.GaussNoise(var_limit=(10.0, 60.0), p=0.3),
            A.GaussianBlur(blur_limit=(3, 5), p=0.15),
            A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=0.15),
            # Weather — sparse, for defense robustness slides + cam_7 glare
            A.RandomFog(fog_coef_range=(0.1, 0.3), alpha_coef=0.08, p=0.10),
            A.RandomRain(
                slant_range=(-10, 10),
                drop_length=10,
                drop_width=1,
                blur_value=3,
                brightness_coefficient=0.9,
                p=0.08,
            ),
            A.RandomSunFlare(
                flare_roi=(0.0, 0.0, 1.0, 0.4),  # upper 40% only
                src_radius=flare_radius,
                num_flare_circles_range=(3, 6),
                p=0.10,
            ),
            A.Spatter(intensity=(0.1, 0.3), mode="rain", p=0.10),
        ],
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_visibility=0.3,  # drop bboxes <30% visible after augmentation
        ),
    )


def night_aug_color_only(imgsz: int = 640) -> A.Compose:
    """Fallback recipe — color/exposure only, no weather.

    Use this if full night_aug_cctv decision benchmark fails (cam_2 mAP <0.31).
    Cheap, low risk, isolates colour-channel contributions.
    """
    return A.Compose(
        [
            A.RandomBrightnessContrast(
                brightness_limit=(-0.4, 0.2),
                contrast_limit=(-0.3, 0.3),
                p=0.5,
            ),
            A.RandomGamma(gamma_limit=(60, 140), p=0.4),
            A.RandomToneCurve(scale=0.2, p=0.3),
            A.HueSaturationValue(
                hue_shift_limit=10,
                sat_shift_limit=20,
                val_shift_limit=30,
                p=0.3,
            ),
            A.GaussNoise(var_limit=(10.0, 60.0), p=0.3),
            A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=0.15),
        ],
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_visibility=0.3,
        ),
    )


def cam7_sun_glare_aug(imgsz: int = 640) -> A.Compose:
    """Targeted recipe for cam_7 morning sun glare.

    Bias brightness UP, contrast DOWN (washed-out simulation).
    Higher RandomSunFlare probability than default.
    """
    flare_radius = max(60, int(imgsz * 0.15))

    return A.Compose(
        [
            A.RandomBrightnessContrast(
                brightness_limit=(0.0, 0.4),  # bias UP
                contrast_limit=(-0.4, 0.0),  # bias DOWN (washed-out)
                p=0.5,
            ),
            A.RandomToneCurve(scale=0.3, p=0.3),
            A.RandomSunFlare(
                flare_roi=(0.0, 0.0, 1.0, 0.5),
                src_radius=flare_radius,
                num_flare_circles_range=(3, 6),
                p=0.15,  # higher than default for cam_7
            ),
            A.GaussNoise(var_limit=(5.0, 30.0), p=0.2),
            A.HueSaturationValue(
                hue_shift_limit=8,
                sat_shift_limit=15,
                val_shift_limit=25,
                p=0.25,
            ),
        ],
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_visibility=0.3,
        ),
    )


# --------------------------------------------------------------------------
# Conditional time-of-day aug — picks recipe based on hour from filename stem.
# --------------------------------------------------------------------------

import re

_HOUR_RE = re.compile(r"_(\d{2})\d{4}\.")  # "_HHMMSS." in filename


def _hour_from_filename(filename: str) -> int | None:
    """Extract hour from filename like '2026-04-25_234734.jpg' or 'cam2_2026-...'."""
    m = _HOUR_RE.search(filename)
    if m:
        return int(m.group(1))
    return None


def _minimal_aug() -> A.Compose:
    """Daytime: just light colour jitter, no aggressive transforms."""
    return A.Compose(
        [
            A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=0.3),
            A.HueSaturationValue(hue_shift_limit=5, sat_shift_limit=10,
                                 val_shift_limit=15, p=0.2),
        ],
        bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"],
                                 min_visibility=0.3),
    )


class ConditionalTimeOfDayAug:
    """Stateful selector applying time-specific Albumentations recipe.

    Usage:
        sel = ConditionalTimeOfDayAug(imgsz=640)
        compose = sel.pick_for_filename("2026-03-04_023439.jpg")
    """

    def __init__(self, imgsz: int = 640):
        self.imgsz = imgsz
        self._night = night_aug_cctv(imgsz)
        self._morning = cam7_sun_glare_aug(imgsz)
        self._day = _minimal_aug()

    def pick_for_filename(self, filename: str) -> A.Compose:
        hour = _hour_from_filename(filename)
        if hour is None:
            return self._day
        if 21 <= hour <= 23 or 0 <= hour <= 4:
            return self._night
        if 5 <= hour <= 8:
            return self._morning
        return self._day

    # Compose-compatible interface — Albumentations callers expect __call__(image=..., bboxes=...)
    def __call__(self, *args, image=None, bboxes=None, class_labels=None, **kwargs):
        # Note: Ultralytics passes filename context only at dataset level, not here.
        # For the per-sample variant to work we'd need to monkey-patch the YOLODataset.
        # Default to night-aug if no filename context known (safer for cam_2 night cases).
        compose = self._night
        return compose(image=image, bboxes=bboxes or [], class_labels=class_labels or [], **kwargs)


def conditional_time_of_day_aug(imgsz: int = 640) -> ConditionalTimeOfDayAug:
    return ConditionalTimeOfDayAug(imgsz=imgsz)


# Registry for lookup by name in train_detection_aug.py
AUGMENT_REGISTRY = {
    "nightaug_cctv": night_aug_cctv,
    "nightaug_color_only": night_aug_color_only,
    "cam7_glare": cam7_sun_glare_aug,
    "conditional_tod": conditional_time_of_day_aug,
}


def get_pipeline(name: str, imgsz: int = 640):
    if name not in AUGMENT_REGISTRY:
        raise KeyError(f"Unknown augment pipeline '{name}'; available: {sorted(AUGMENT_REGISTRY)}")
    return AUGMENT_REGISTRY[name](imgsz=imgsz)
