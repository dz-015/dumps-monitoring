"""Region-of-interest post-filter.

Detections whose centre falls outside the site's ROI are dropped. This is not
cosmetic: on the thesis data the filter is worth +0.036 F1, and on cam_1 84.6%
of the hallucinations at 1280 landed outside the ROI.

Some cameras had their bins physically rearranged, so their ROI is
time-dependent — the config stores a list of periods and we pick the one
covering the frame's timestamp.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# Pixel rectangle in the ORIGINAL frame: (x1, y1, x2, y2).
Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class _Period:
    # Upper bound, exclusive. None means "everything after the previous one".
    until: datetime | None
    rects: tuple[Rect, ...]


class RoiConfig:
    """ROI rectangles per camera, loaded from cameras_roi_v2.json."""

    def __init__(self, periods_by_camera: dict[str, list[_Period]]):
        self._by_camera = periods_by_camera

    @classmethod
    def load(cls, path: str | Path) -> RoiConfig:
        raw = json.loads(Path(path).read_text())
        by_camera: dict[str, list[_Period]] = {}
        for camera, cfg in raw.items():
            # Keys starting with "_" are documentation, not cameras.
            if camera.startswith("_"):
                continue
            if "rects" in cfg:
                periods = [_Period(None, tuple(map(tuple, cfg["rects"])))]
            else:
                periods = [
                    _Period(
                        _parse_ts(p["until"]) if p.get("until") else None,
                        tuple(map(tuple, p["rects"])),
                    )
                    for p in cfg["periods"]
                ]
            by_camera[str(camera)] = periods
        return cls(by_camera)

    def has(self, camera: str | int) -> bool:
        return str(camera) in self._by_camera

    def rects_at(self, camera: str | int, when: datetime) -> tuple[Rect, ...]:
        """Rectangles in force for a frame taken at `when` (UTC)."""
        periods = self._by_camera.get(str(camera))
        if not periods:
            return ()
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        for period in periods:
            if period.until is None or when < period.until:
                return period.rects
        return periods[-1].rects


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def inside(rects: tuple[Rect, ...], cx: float, cy: float, width: int, height: int) -> bool:
    """Is the centre (normalised 0..1) inside any rectangle (frame pixels)?"""
    px, py = cx * width, cy * height
    return any(x1 <= px <= x2 and y1 <= py <= y2 for x1, y1, x2, y2 in rects)
