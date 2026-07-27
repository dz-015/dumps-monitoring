import logging
import os

import cv2

logger = logging.getLogger(__name__)

CAPTURE_TIMEOUT_MS = 15_000
JPEG_QUALITY = 95

# Use TCP transport for RTSP (more reliable for remote cameras)
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;15000000",
)


def capture_frame(rtsp_url: str) -> tuple[bytes, int, int]:
    """
    Capture a single frame from RTSP stream.

    Returns (jpeg_bytes, width, height).
    Raises RuntimeError on failure.
    """
    cap = cv2.VideoCapture()
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CAPTURE_TIMEOUT_MS)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, CAPTURE_TIMEOUT_MS)
    cap.open(rtsp_url, cv2.CAP_FFMPEG)

    try:
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open RTSP stream: {rtsp_url}")

        ret, frame = cap.read()
        if not ret or frame is None:
            raise RuntimeError(f"Failed to read frame from: {rtsp_url}")

        height, width = frame.shape[:2]
        success, jpeg_data = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )
        if not success:
            raise RuntimeError("Failed to encode frame as JPEG")

        return jpeg_data.tobytes(), width, height
    finally:
        cap.release()
