"""Тесты часового контура: ingest_frame и проход планировщика по каталогу.

Пайплайн подменяется стабом — здесь проверяется запись в БД, копирование
кадров, дедупликация алертов и раскладка файлов, а не инференс (он покрыт
в test_ml_pipeline.py).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from PIL import Image

from app.db.models import Alert, Snapshot
from app.db.models import Detection as DetectionRow
from app.ingest import ingest_frame
from app.ml.detector import Detection
from app.ml.pipeline import Verdict
from app.scheduler import parse_frame_name, process_dir
from tests.conftest import make_camera, make_org, make_site

TAKEN_AT = dt.datetime(2026, 5, 8, 8, 47, 34, tzinfo=dt.UTC)


class StubPipeline:
    def __init__(self, verdict: Verdict):
        self._verdict = verdict
        self.calls = 0

    def run(self, image, camera_key=None, taken_at=None):
        self.calls += 1
        return self._verdict


def verdict(*, overflow=False, contamination=False, detections=None) -> Verdict:
    return Verdict(
        detections=detections or [],
        has_overflow=overflow,
        has_contamination=contamination,
        dropped_by_roi=0,
    )


@pytest.fixture
def frame(tmp_path: Path) -> Path:
    path = tmp_path / "cam2_2026-05-08_084734.jpg"
    Image.new("RGB", (64, 48), color=(50, 60, 70)).save(path, format="JPEG")
    return path


@pytest.fixture
def uploads(tmp_path: Path, monkeypatch) -> Path:
    from app.config import settings
    dest = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(dest))
    return dest


def test_ingest_writes_snapshot_detections_and_alert(db, frame, uploads):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    dets = [Detection("bin_overflow", 0.9, 0.5, 0.5, 0.1, 0.1)]
    result = ingest_frame(
        db, camera, frame, TAKEN_AT,
        pipeline=StubPipeline(verdict(overflow=True, detections=dets)),
    )

    snap = db.query(Snapshot).one()
    assert snap.site_id == site.id and snap.camera_id == camera.id
    assert snap.taken_at == TAKEN_AT.replace(tzinfo=None)  # наивный UTC
    assert (Path(str(uploads)) / snap.image_path).is_file()  # кадр скопирован

    rows = db.query(DetectionRow).all()
    assert len(rows) == 1
    assert rows[0].class_name == "bin_overflow"

    alerts = db.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].level == "overflow"
    assert alerts[0].snapshot_id == snap.id
    assert alerts[0].status == "new"

    db.refresh(site)
    assert site.status == "overflow"
    assert camera.last_checked is not None
    assert result.created_alerts and result.snapshot.id == snap.id


def test_ingest_does_not_duplicate_open_alert(db, frame, uploads):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    pipe = StubPipeline(verdict(overflow=True))

    first = ingest_frame(db, camera, frame, TAKEN_AT, pipeline=pipe)
    second = ingest_frame(db, camera, frame, TAKEN_AT + dt.timedelta(hours=1), pipeline=pipe)

    assert len(first.created_alerts) == 1
    assert len(second.created_alerts) == 0
    assert db.query(Alert).count() == 1


def test_ingest_creates_fresh_alert_after_resolve(db, frame, uploads):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    pipe = StubPipeline(verdict(overflow=True))

    first = ingest_frame(db, camera, frame, TAKEN_AT, pipeline=pipe)
    first.created_alerts[0].status = "resolved"
    db.commit()

    second = ingest_frame(db, camera, frame, TAKEN_AT + dt.timedelta(hours=1), pipeline=pipe)
    assert len(second.created_alerts) == 1
    assert db.query(Alert).count() == 2


def test_ingest_both_levels_and_clean_resets_status(db, frame, uploads):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)

    both = ingest_frame(
        db, camera, frame, TAKEN_AT,
        pipeline=StubPipeline(verdict(overflow=True, contamination=True)),
    )
    assert {a.level for a in both.created_alerts} == {"overflow", "contamination"}
    db.refresh(site)
    assert site.status == "overflow"  # переполнение важнее навала

    ingest_frame(
        db, camera, frame, TAKEN_AT + dt.timedelta(hours=1),
        pipeline=StubPipeline(verdict()),
    )
    db.refresh(site)
    assert site.status == "clean"


# ── планировщик ──────────────────────────────────────────────────────────

def test_parse_frame_name():
    assert parse_frame_name("cam2_2026-05-08_084734.jpg") == ("2", TAKEN_AT)
    assert parse_frame_name("cam2_2026-05-08_084734.PNG") is not None
    assert parse_frame_name("random.jpg") is None
    assert parse_frame_name("cam2_2026-05-08.jpg") is None


def make_frame_file(dir_: Path, name: str) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / name
    Image.new("RGB", (64, 48)).save(path, format="JPEG")
    return path


def test_process_dir_routes_frames(db, tmp_path, uploads):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    camera.external_key = "2"
    db.commit()

    ingest_dir = tmp_path / "ingest"
    make_frame_file(ingest_dir, "cam2_2026-05-08_084734.jpg")   # знакомая камера
    make_frame_file(ingest_dir, "cam99_2026-05-08_084734.jpg")  # неизвестный ключ
    make_frame_file(ingest_dir, "мусорное_имя.jpg")             # не по схеме

    counts = process_dir(db, ingest_dir, pipeline=StubPipeline(verdict(overflow=True)))

    assert counts == {"processed": 1, "failed": 2}
    assert (ingest_dir / "processed" / "cam2_2026-05-08_084734.jpg").is_file()
    assert (ingest_dir / "failed" / "cam99_2026-05-08_084734.jpg").is_file()
    assert (ingest_dir / "failed" / "мусорное_имя.jpg").is_file()
    assert not any(p.is_file() for p in ingest_dir.iterdir())  # каталог пуст
    assert db.query(Snapshot).count() == 1
    assert db.query(Alert).count() == 1


def test_process_dir_fans_out_to_every_org_watching_the_camera(db, tmp_path, uploads):
    """Одна физическая камера может быть заведена в нескольких организациях
    (демо-стенд + реальный заказчик): кадр должен попасть в каждую, а
    инференс при этом выполняться один раз — вердикт зависит только от ключа."""
    cameras = []
    for name in ("ТКО Мониторинг — демо", "Администрация"):
        org = make_org(db, name=name)
        site = make_site(db, org)
        camera = make_camera(db, site)
        camera.external_key = "2"
        cameras.append(camera)
    db.commit()

    ingest_dir = tmp_path / "ingest"
    make_frame_file(ingest_dir, "cam2_2026-05-08_084734.jpg")
    pipe = StubPipeline(verdict(overflow=True))

    counts = process_dir(db, ingest_dir, pipeline=pipe)

    assert counts == {"processed": 1, "failed": 0}
    assert db.query(Snapshot).count() == 2
    assert {s.camera_id for s in db.query(Snapshot)} == {c.id for c in cameras}
    assert db.query(Alert).count() == 2
    assert pipe.calls == 1  # инференс не дублируется на веере


def test_process_dir_inactive_camera_goes_to_failed(db, tmp_path, uploads):
    org = make_org(db)
    site = make_site(db, org)
    camera = make_camera(db, site)
    camera.external_key = "2"
    camera.is_active = False
    db.commit()

    ingest_dir = tmp_path / "ingest"
    make_frame_file(ingest_dir, "cam2_2026-05-08_084734.jpg")
    counts = process_dir(db, ingest_dir, pipeline=StubPipeline(verdict()))
    assert counts == {"processed": 0, "failed": 1}
    assert db.query(Snapshot).count() == 0
