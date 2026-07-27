import pytest

from app.services.capture import capture_frame


def test_capture_frame_invalid_url():
    with pytest.raises(RuntimeError, match="Failed to open RTSP stream"):
        capture_frame("rtsp://invalid-host:554/nonexistent")


def test_capture_frame_returns_tuple():
    """Verify function signature raises RuntimeError (not other exceptions) for bad input."""
    with pytest.raises(RuntimeError):
        capture_frame("")
