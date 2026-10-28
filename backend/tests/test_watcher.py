"""Тесты клиента Flussonic Watcher. Сеть замокана целиком."""

from unittest.mock import MagicMock, patch

import pytest

from app import watcher


@pytest.fixture(autouse=True)
def _creds(monkeypatch):
    """Каждому тесту — свежие креды и пустой кэш сессии."""
    monkeypatch.setattr(watcher.settings, "WATCHER_URL", "http://watcher.test:2002")
    monkeypatch.setattr(watcher.settings, "WATCHER_LOGIN", "kameras")
    monkeypatch.setattr(watcher.settings, "WATCHER_PASSWORD", "secret")
    watcher.reset_session()
    yield
    watcher.reset_session()


def _resp(status=200, json_data=None, content=b""):
    r = MagicMock()
    r.status_code = status
    r.ok = status < 400
    r.json.return_value = json_data if json_data is not None else {}
    r.content = content
    return r


def test_disabled_without_credentials(monkeypatch):
    monkeypatch.setattr(watcher.settings, "WATCHER_URL", "")
    assert watcher.enabled() is False


def test_enabled_with_credentials():
    assert watcher.enabled() is True


def test_login_is_cached_between_calls():
    """Сессия берётся один раз на несколько запросов, а не на каждый."""
    login = _resp(json_data={"session": "S1"})
    cams = _resp(json_data={"cameras": []})
    with patch.object(watcher.requests, "post", return_value=login) as post, \
         patch.object(watcher.requests, "get", return_value=cams):
        watcher.list_cameras()
        watcher.list_cameras()
    assert post.call_count == 1


def test_list_cameras_sends_session_header():
    login = _resp(json_data={"session": "S1"})
    cams = _resp(json_data={"cameras": [{"name": "a"}]})
    with patch.object(watcher.requests, "post", return_value=login), \
         patch.object(watcher.requests, "get", return_value=cams) as get:
        items = watcher.list_cameras()
    assert items == [{"name": "a"}]
    # Платформа принимает сессию только этим заголовком (не Bearer, не кукой).
    assert get.call_args.kwargs["headers"]["x-vsaas-session"] == "S1"


def test_list_cameras_accepts_bare_list():
    """API может отдать и голый список, и объект с ключом cameras."""
    login = _resp(json_data={"session": "S1"})
    cams = _resp(json_data=[{"name": "a"}, {"name": "b"}])
    with patch.object(watcher.requests, "post", return_value=login), \
         patch.object(watcher.requests, "get", return_value=cams):
        assert len(watcher.list_cameras()) == 2


def test_session_is_renewed_after_expiry():
    """Протухшая сессия (403) — перелогин и повтор запроса, без падения."""
    login = _resp(json_data={"session": "S2"})
    forbidden = _resp(status=403, json_data={"error_code": "Forbidden"})
    ok = _resp(json_data={"cameras": [{"name": "x"}]})
    with patch.object(watcher.requests, "post", return_value=login) as post, \
         patch.object(watcher.requests, "get", side_effect=[forbidden, ok]) as get:
        items = watcher.list_cameras()
    assert items == [{"name": "x"}]
    assert post.call_count == 2   # первый вход + перелогин
    assert get.call_count == 2    # отказ + успешный повтор


def test_playback_token_read_from_detail():
    login = _resp(json_data={"session": "S1"})
    detail = _resp(json_data={"name": "cam", "playback_config": {"token": "3.TOKEN"}})
    with patch.object(watcher.requests, "post", return_value=login), \
         patch.object(watcher.requests, "get", return_value=detail):
        assert watcher.playback_token("cam") == "3.TOKEN"


def test_grab_jpeg_returns_decoded_frame():
    """Кадр = preview.mp4 с playback-токеном → декодирование первого кадра."""
    login = _resp(json_data={"session": "S1"})
    detail = _resp(json_data={"playback_config": {"token": "3.TOKEN"}})
    # Больше порога «это не заглушка»: настоящий preview.mp4 весит сотни КБ.
    video = _resp(content=b"\x00\x00\x00\x20ftypmp42" + b"\x00" * 4096)
    with patch.object(watcher.requests, "post", return_value=login), \
         patch.object(watcher.requests, "get", side_effect=[detail, video]) as get, \
         patch.object(watcher, "decode_first_frame", return_value=b"\xff\xd8\xffJPEG") as dec:
        jpeg = watcher.grab_jpeg("cam")
    assert jpeg == b"\xff\xd8\xffJPEG"
    dec.assert_called_once_with(video.content)
    # токен уходит в query медиа-запроса, а не в заголовке
    assert get.call_args_list[1].kwargs["params"]["token"] == "3.TOKEN"


def test_grab_jpeg_returns_none_when_no_token():
    """Камера без playback-токена (нет потока) — не падаем, отдаём None."""
    login = _resp(json_data={"session": "S1"})
    detail = _resp(json_data={"name": "cam"})
    with patch.object(watcher.requests, "post", return_value=login), \
         patch.object(watcher.requests, "get", return_value=detail):
        assert watcher.grab_jpeg("cam") is None


def test_grab_jpeg_returns_none_when_preview_empty():
    """Платформа отдаёт 10-байтную заглушку 'not found' для мёртвых камер."""
    login = _resp(json_data={"session": "S1"})
    detail = _resp(json_data={"playback_config": {"token": "3.T"}})
    empty = _resp(content=b"not found\n")
    with patch.object(watcher.requests, "post", return_value=login), \
         patch.object(watcher.requests, "get", side_effect=[detail, empty]):
        assert watcher.grab_jpeg("cam") is None


def test_alive_names_filters_by_stream_status():
    login = _resp(json_data={"session": "S1"})
    cams = _resp(json_data={"cameras": [
        {"name": "live", "stream_status": {"alive": True}},
        {"name": "dead", "stream_status": {"alive": False}},
        {"name": "unknown"},
    ]})
    with patch.object(watcher.requests, "post", return_value=login), \
         patch.object(watcher.requests, "get", return_value=cams):
        assert watcher.alive_names() == ["live"]
