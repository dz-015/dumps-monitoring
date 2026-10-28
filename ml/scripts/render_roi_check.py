"""Отрисовка ROI поверх кадров — визуальная проверка cameras_roi_v2.json.

Нужна потому, что конфиг v2 восстановлен из записей, а не взят из
оригинального файла (тот жил в /tmp и пропал при перезагрузке хоста). Для
cam_2 ROI зависит от времени: берём по кадру из каждого периода, чтобы
проверить и границы периодов, и сами прямоугольники.

Кадры: ml/data/processed/to_label/<cam>/<YYYY-MM-DD>_<HHMMSS>.jpg (UTC).
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ML_ROOT = Path(__file__).resolve().parent.parent
FRAMES = ML_ROOT / "data" / "processed" / "to_label"
CONFIG = ML_ROOT / "configs" / "cameras_roi_v2.json"
OUT = ML_ROOT / "roi_check"


def frame_time(path: Path) -> datetime | None:
    try:
        return datetime.strptime(path.stem, "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def active_period(cam_cfg: dict, when: datetime) -> tuple[list, str]:
    """Прямоугольники, действующие на момент when, и подпись периода."""
    if "rects" in cam_cfg:
        return cam_cfg["rects"], "постоянный"
    for i, period in enumerate(cam_cfg["periods"], 1):
        until = period.get("until")
        if until is None or when < datetime.fromisoformat(until.replace("Z", "+00:00")):
            return period["rects"], f"период {i}"
    return [], "нет периода"


def pick_frames(cam: str, cam_cfg: dict) -> list[Path]:
    """По кадру на период (для cam_2) либо пара кадров вразброс."""
    cam_dir = FRAMES / cam
    frames = sorted(p for p in cam_dir.glob("*.jpg") if frame_time(p))
    if not frames:
        return []
    if "periods" not in cam_cfg:
        return [frames[len(frames) // 4], frames[-1]]

    picked, seen = [], set()
    for path in frames:
        _, label = active_period(cam_cfg, frame_time(path))
        if label not in seen:
            seen.add(label)
            picked.append(path)
    return picked


def render(cam: str, cam_cfg: dict, path: Path) -> Path:
    when = frame_time(path)
    rects, label = active_period(cam_cfg, when)

    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    for i, (x1, y1, x2, y2) in enumerate(rects, 1):
        draw.rectangle([x1, y1, x2, y2], outline=(0, 255, 0), width=5)
        draw.text((x1 + 8, max(y1 - 18, 2)), f"ROI {i}", fill=(0, 255, 0))
    draw.text((8, 8), f"cam_{cam} | {path.stem} UTC | {label} | кадр {img.size[0]}x{img.size[1]}",
              fill=(255, 255, 0))

    OUT.mkdir(exist_ok=True)
    dst = OUT / f"cam{cam}_{label.replace(' ', '')}_{path.stem}.jpg"
    img.save(dst, quality=88)
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cameras", default="", help="через запятую, по умолчанию все из конфига")
    args = ap.parse_args()

    cfg = {k: v for k, v in json.loads(CONFIG.read_text()).items() if not k.startswith("_")}
    wanted = args.cameras.split(",") if args.cameras else list(cfg)

    for cam in wanted:
        frames = pick_frames(cam, cfg[cam])
        if not frames:
            print(f"cam_{cam}: кадров нет в {FRAMES / cam}")
            continue
        for path in frames:
            dst = render(cam, cfg[cam], path)
            print(f"cam_{cam}: {dst.relative_to(ML_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
