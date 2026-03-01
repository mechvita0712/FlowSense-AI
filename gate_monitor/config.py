"""
config.py — Gate Monitor Configuration
=======================================
Loads settings from .env (copy .env.example → .env and customize).
"""

import os
from dotenv import load_dotenv

# Load .env from the gate_monitor directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


class Config:
    # Camera source — int for USB index, string for RTSP URL or video file path
    CAMERA_SOURCE: str | int = os.getenv("CAMERA_SOURCE", "0")

    # Convert "0", "1" etc. to int for OpenCV
    @classmethod
    def get_camera_source(cls) -> int | str:
        src = cls.CAMERA_SOURCE
        try:
            return int(src)
        except (ValueError, TypeError):
            return str(src)  # RTSP URL or file path

    # Gate identity
    GATE_ID: str = os.getenv("GATE_ID", "A")
    GATE_LOCATION: str = os.getenv("GATE_LOCATION", "Main Entrance")

    # Backend API
    API_URL: str = os.getenv("API_URL", "http://localhost:5000/api/traffic/add")
    API_KEY: str = os.getenv("API_KEY", "")  # API key for authentication

    # Detection settings
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.45"))

    # Virtual line position (fraction of frame height, e.g. 0.5 = middle)
    LINE_POSITION: float = float(os.getenv("LINE_POSITION", "0.5"))

    # How often to POST to backend (seconds)
    POST_INTERVAL_SEC: int = int(os.getenv("POST_INTERVAL_SEC", "30"))

    # YOLOv8 model weights file (auto-downloaded on first run)
    YOLO_MODEL: str = os.getenv("YOLO_MODEL", "yolov8n.pt")

    # Show live video window
    SHOW_WINDOW: bool = os.getenv("SHOW_WINDOW", "true").lower() == "true"

    # Local DB path
    DB_PATH: str = os.path.join(os.path.dirname(__file__), "gate_events.db")
