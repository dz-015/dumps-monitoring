"""Тесты синка S3→ingest: перенос кадров сборщика в каталог планировщика.

S3 подменяется стабом — проверяется преобразование ключей, маркеры,
идемпотентность и атомарность раскладки, а не boto3.
"""

from __future__ import annotations

from pathlib import Path

from app.s3_sync import (
    active_keys,
    key_to_frame_name,
    load_state,
    save_state,
    sync_once,
    sync_prefix,
)
from tests.conftest import make_camera, make_org, make_site


class FakeS3:
    """Стаб клиента boto3: словарь ключ → байты, листинг с пагинацией."""

    def __init__(self, objects: dict[str, bytes], page_size: int = 1000):
        self.objects = dict(objects)
        self.page_size = page_size
        self.downloads: list[str] = []

    # Имена аргументов — CamelCase, как в реальном API boto3.
    def list_objects_v2(self, Bucket, Prefix="", StartAfter="", ContinuationToken=None):  # noqa: N803
        keys = sorted(k for k in self.objects if k.startswith(Prefix) and k > StartAfter)
        start = int(ContinuationToken) if ContinuationToken else 0
        page = keys[start : start + self.page_size]
        resp = {"Contents": [{"Key": k} for k in page], "IsTruncated": False}
        if start + self.page_size < len(keys):
            resp["IsTruncated"] = True
            resp["NextContinuationToken"] = str(start + self.page_size)
        return resp

    def download_file(self, Bucket, Key, Filename):  # noqa: N803
        self.downloads.append(Key)
        Path(Filename).write_bytes(self.objects[Key])


def test_key_to_frame_name():
    assert (
        key_to_frame_name("cameras/3/2026/08/03/134500.jpg")
        == "cam3_2026-08-03_134500.jpg"
    )
    # Чужие и кривые ключи не переносим.
    assert key_to_frame_name("cameras/3/2026/08/03/134500.txt") is None
    assert key_to_frame_name("cameras/3/134500.jpg") is None
    assert key_to_frame_name("other/3/2026/08/03/134500.jpg") is None


def test_first_run_sets_marker_without_download(tmp_path):
    s3 = FakeS3({
        "cameras/2/2026/08/01/100000.jpg": b"old1",
        "cameras/2/2026/08/07/110000.jpg": b"old2",
    })
    marker, downloaded = sync_prefix(s3, "bucket", "2", None, tmp_path)
    # В бакете тысячи исторических кадров — на первом запуске только маркер.
    assert marker == "cameras/2/2026/08/07/110000.jpg"
    assert downloaded == 0
    assert s3.downloads == []
    assert list(tmp_path.glob("*.jpg")) == []


def test_sync_downloads_new_and_advances_marker(tmp_path):
    s3 = FakeS3(
        {
            "cameras/2/2026/08/07/110000.jpg": b"old",
            "cameras/2/2026/08/10/120000.jpg": b"new1",
            "cameras/2/2026/08/10/130000.jpg": b"new2",
        },
        page_size=1,  # заодно проверяем пагинацию листинга
    )
    marker, downloaded = sync_prefix(
        s3, "bucket", "2", "cameras/2/2026/08/07/110000.jpg", tmp_path
    )
    assert downloaded == 2
    assert marker == "cameras/2/2026/08/10/130000.jpg"
    assert (tmp_path / "cam2_2026-08-10_120000.jpg").read_bytes() == b"new1"
    assert (tmp_path / "cam2_2026-08-10_130000.jpg").read_bytes() == b"new2"
    # Временных недокачанных файлов в каталоге планировщика не остаётся.
    assert list(tmp_path.glob("*.part")) == []


def test_sync_skips_frames_already_handled(tmp_path):
    s3 = FakeS3({"cameras/2/2026/08/10/120000.jpg": b"new"})
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "cam2_2026-08-10_120000.jpg").write_bytes(b"done")

    marker, downloaded = sync_prefix(s3, "bucket", "2", "cameras/2/2026/08/09/000000.jpg", tmp_path)
    # Кадр уже прошёл через планировщик — не скачиваем, но маркер двигаем.
    assert downloaded == 0
    assert s3.downloads == []
    assert marker == "cameras/2/2026/08/10/120000.jpg"


def test_active_keys_only_active_cameras_with_key(db):
    org = make_org(db)
    site = make_site(db, org)
    cam_ok = make_camera(db, site, name="ok")
    cam_ok.external_key = "2"
    cam_off = make_camera(db, site, name="off")
    cam_off.external_key = "9"
    cam_off.is_active = False
    make_camera(db, site, name="nokey")  # без external_key — не синкается
    db.commit()

    assert active_keys(db) == ["2"]


def test_sync_once_walks_active_cameras_and_saves_state(db, tmp_path):
    org = make_org(db)
    site = make_site(db, org)
    cam = make_camera(db, site)
    cam.external_key = "2"
    db.commit()

    s3 = FakeS3({"cameras/2/2026/08/10/120000.jpg": b"x"})
    # Первый проход — только маркеры.
    counts = sync_once(db, s3, "bucket", tmp_path)
    assert counts == {"downloaded": 0, "prefixes": 1}

    # Появился новый кадр — второй проход его забирает.
    s3.objects["cameras/2/2026/08/10/130000.jpg"] = b"y"
    counts = sync_once(db, s3, "bucket", tmp_path)
    assert counts == {"downloaded": 1, "prefixes": 1}
    assert (tmp_path / "cam2_2026-08-10_130000.jpg").read_bytes() == b"y"

    state = load_state(tmp_path)
    assert state["2"] == "cameras/2/2026/08/10/130000.jpg"


def test_state_roundtrip(tmp_path):
    save_state(tmp_path, {"2": "cameras/2/a.jpg", "7": "cameras/7/b.jpg"})
    assert load_state(tmp_path) == {"2": "cameras/2/a.jpg", "7": "cameras/7/b.jpg"}
    assert load_state(tmp_path / "nope") == {}
