"""Заведение камер платформы Watcher в нашу базу.

Разовая (и повторяемая) операция: берём список камер у платформы и создаём в
нашей организации по площадке на камеру — имя, адрес и координаты у платформы
уже есть, поэтому карта заполняется сама.

Правила:
- операция идемпотентна: камера ищется по ``watcher_stream``, повторный запуск
  ничего не дублирует, только обновляет адрес/координаты и признак активности;
- активны те камеры, которые платформа показывает живыми; остальные заводятся
  выключенными и включатся сами при следующем запуске, когда оживут;
- ``external_key`` — короткий ключ (w1, w2, …) для имён файлов кадров: в имени
  потока есть точки, а планировщик их не принимает.

Запуск:  python -m app.watcher_import --org "Мусорные Баки" [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import re
import secrets

from sqlalchemy.orm import Session

from app import watcher
from app.db.database import SessionLocal
from app.db.models import Camera, Organization, Site

logger = logging.getLogger(__name__)


# Обратная транслитерация: платформа именует камеры латиницей, а адреса видит
# русскоязычный оператор. Порядок важен — длинные сочетания идут первыми.
_TRANSLIT = [
    ("shch", "щ"), ("sch", "щ"), ("lnaya", "льная"), ("lnyj", "льный"),
    # «ts» намеренно НЕ переводится в «ц»: в наших названиях это «тс»
    # (sovetskaya → советская). Буква «ц» приходит из «c».
    ("lsk", "льск"), ("zh", "ж"), ("kh", "х"), ("ch", "ч"),
    ("sh", "ш"), ("yu", "ю"), ("ya", "я"), ("yo", "ё"), ("yj", "ый"),
    ("ij", "ий"), ("j", "й"), ("a", "а"), ("b", "б"), ("v", "в"), ("g", "г"),
    ("d", "д"), ("e", "е"), ("z", "з"), ("i", "и"), ("k", "к"), ("l", "л"),
    ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"), ("r", "р"), ("s", "с"),
    ("t", "т"), ("u", "у"), ("f", "ф"), ("h", "х"), ("c", "ц"), ("y", "ы"),
]


def to_cyrillic(text: str) -> str:
    """Латинское название улицы → кириллица: kievskaya → киевская.

    Перевод приблизительный (мягкий знак и буква «ё» восстанавливаются не
    везде), но для чтения адреса на карте этого достаточно.
    """
    out = text.lower()
    for latin, cyrillic in _TRANSLIT:
        out = out.replace(latin, cyrillic)
    return out


def pretty_address(stream_name: str) -> str:
    """Имя потока → человеческий адрес.

    ``kievskaya.ul..122.g..simferopol-f9a469d498`` → ``Киевская ул. 122, г. Симферополь``.
    Разбор нестрогий: платформа именует камеры свободно, поэтому непонятные
    куски оставляем как есть — пустой адрес хуже неровного.
    """
    name = re.sub(r"-[0-9a-f]{6,}$", "", stream_name)      # убрать хвост-идентификатор
    text = name.replace("..", ". ").replace(".", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()

    # Служебные слова заменяем ДО транслитерации, иначе «ul» станет «ул» и т.п.
    words = []
    for word in text.split():
        short = {"ul": "ул.", "per": "пер.", "pr": "пр.", "sh": "ш.",
                 "pl": "пл.", "d": "д.", "g": "г."}.get(word)
        if short:
            words.append(short)
        elif word == "simferopol":
            words.append("Симферополь")
        else:
            words.append(to_cyrillic(word))
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def parse_coordinates(value: str | None) -> tuple[float | None, float | None]:
    """'44.95 34.11' → (44.95, 34.11). Мусор → (None, None)."""
    if not value:
        return None, None
    parts = value.split()
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None


def get_or_create_org(db: Session, name: str) -> Organization:
    org = db.query(Organization).filter(Organization.name == name).first()
    if org:
        return org
    org = Organization(name=name, join_code=secrets.token_hex(8))
    db.add(org)
    db.flush()
    logger.info("создана организация %r (код присоединения %s)", org.name, org.join_code)
    return org


def next_key(db: Session) -> str:
    """Следующий свободный короткий ключ вида w17."""
    used = {
        key for (key,) in db.query(Camera.external_key).filter(Camera.external_key.isnot(None))
    }
    index = 1
    while f"w{index}" in used:
        index += 1
    return f"w{index}"


def import_cameras(db: Session, org_name: str, *, dry_run: bool = False) -> dict:
    """Завести/обновить камеры платформы. Возвращает сводку по операции."""
    cameras = watcher.list_cameras()
    if not cameras:
        raise RuntimeError("платформа не вернула ни одной камеры")

    org = get_or_create_org(db, org_name)
    summary = {"всего": len(cameras), "создано": 0, "обновлено": 0, "живых": 0}

    for item in sorted(cameras, key=lambda c: c.get("name", "")):
        stream = item.get("name")
        if not stream:
            continue
        alive = bool(item.get("stream_status", {}).get("alive"))
        summary["живых"] += int(alive)
        address = pretty_address(stream)
        lat, lon = parse_coordinates(item.get("coordinates"))

        camera = db.query(Camera).filter(Camera.watcher_stream == stream).first()
        if camera:
            site = camera.site
            site.address, site.latitude, site.longitude = address, lat, lon
            camera.is_active = alive
            summary["обновлено"] += 1
            continue

        site = Site(organization_id=org.id, name=address, address=address,
                    latitude=lat, longitude=lon, status="clean")
        db.add(site)
        db.flush()
        db.add(Camera(
            site_id=site.id, name=address,
            rtsp_url=f"watcher://{stream}",   # поле обязательное; храним источник
            external_key=next_key(db), watcher_stream=stream, is_active=alive,
        ))
        db.flush()
        summary["создано"] += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return summary


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Завести камеры платформы Watcher")
    parser.add_argument("--org", default="Мусорные Баки", help="название организации")
    parser.add_argument("--dry-run", action="store_true", help="показать, но не сохранять")
    args = parser.parse_args()

    if not watcher.enabled():
        logger.error("Настройки платформы не заданы (WATCHER_URL/LOGIN/PASSWORD)")
        return 1

    with SessionLocal() as db:
        summary = import_cameras(db, args.org, dry_run=args.dry_run)
    print("Итог:", ", ".join(f"{k}: {v}" for k, v in summary.items()))
    if args.dry_run:
        print("(пробный запуск — ничего не сохранено)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
