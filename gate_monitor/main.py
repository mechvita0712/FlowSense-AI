"""
main.py — AI Smart Gate Monitor Entry Point
============================================
Ties together: YOLOv8 detection, ByteTrack tracking,
virtual-line IN/OUT counting, SQLite logging, and Flask API posting.

Usage:
    python main.py                         # Uses settings from .env
    python main.py --source 0              # USB webcam 0
    python main.py --source video.mp4      # Video file (for testing)
    python main.py --source rtsp://...     # IP camera
    python main.py --gate A --no-window    # Headless mode (server)
    python main.py --help                  # Show all options

Requirements:
    pip install -r requirements.txt

Setup:
    1. Copy .env.example → .env
    2. Set CAMERA_SOURCE, GATE_ID, GATE_LOCATION in .env
    3. Ensure Flask backend is running on localhost:5000
    4. python main.py
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from config import Config
from tracker import Tracker
from counter import Counter
from db_logger import DBLogger
from api_client import APIClient


# ── Logging Setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gate_monitor")


# ── Argument Parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="AI Smart Gate Monitor — YOLOv8 + ByteTrack IN/OUT Counter"
    )
    p.add_argument("--source",     default=None, help="Camera index, RTSP URL, or video file path (overrides .env)")
    p.add_argument("--gate",       default=None, help="Gate ID (e.g. A) — overrides .env")
    p.add_argument("--location",   default=None, help="Gate location label — overrides .env")
    p.add_argument("--model",      default=None, help="YOLOv8 model file (e.g. yolov8n.pt)")
    p.add_argument("--conf",       type=float, default=None, help="Detection confidence threshold (0.0–1.0)")
    p.add_argument("--line",       type=float, default=None, help="Virtual line position as fraction of frame height (0.0–1.0)")
    p.add_argument("--no-window",  action="store_true", help="Disable live video window (headless mode)")
    p.add_argument("--invert",     action="store_true", help="Invert IN/OUT direction (for top-mounted cameras)")
    return p.parse_args()


# ── Drawing Overlay ───────────────────────────────────────────────────────────

def draw_overlay(
    frame:      np.ndarray,
    tracks:     list[dict],
    counter:    Counter,
    frame_h:    int,
    gate_id:    str,
    location:   str,
) -> np.ndarray:
    """Draw bounding boxes, virtual line, and live counts onto the frame."""
    frame_w = frame.shape[1]
    line_y  = counter.line_y(frame_h)

    # ── Virtual counting line ──────────────────────────────────────────────────
    cv2.line(frame, (0, line_y), (frame_w, line_y), (0, 255, 255), 2)
    cv2.putText(frame, "COUNTING LINE", (10, line_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    # ── Bounding boxes + track IDs ────────────────────────────────────────────
    for t in tracks:
        x1, y1, x2, y2 = t["bbox"]
        tid  = t["id"]
        conf = t["confidence"]

        # Box colour: green for tracked, grey for unassigned
        color = (0, 255, 0) if tid >= 0 else (128, 128, 128)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f"ID:{tid}  {conf:.0%}" if tid >= 0 else f"? {conf:.0%}"
        cv2.putText(frame, label, (x1, max(y1 - 6, 16)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        # Draw centroid dot
        cy = (y1 + y2) // 2
        cx = (x1 + x2) // 2
        cv2.circle(frame, (cx, cy), 4, color, -1)

    # ── Stats panel (top-left) ────────────────────────────────────────────────
    panel_lines = [
        f"Gate {gate_id} — {location}",
        f"IN :  {counter.total_in}",
        f"OUT:  {counter.total_out}",
        f"NET:  {counter.net}",
        f"People in frame: {len(tracks)}",
        datetime.now().strftime("%Y-%m-%d  %H:%M:%S"),
    ]
    colors = [
        (255, 255, 255),   # title
        (0, 200, 0),       # IN — green
        (0, 100, 255),     # OUT — orange
        (255, 255, 0),     # NET — yellow
        (200, 200, 200),   # active
        (180, 180, 180),   # time
    ]

    # Semi-transparent background for readability
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (300, len(panel_lines) * 26 + 10), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    for i, (text, col) in enumerate(zip(panel_lines, colors)):
        cv2.putText(frame, text, (8, 22 + i * 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, col, 1)

    return frame


# ── Main Loop ─────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    # ── Config (CLI overrides .env) ────────────────────────────────────────────
    source   = args.source   or Config.get_camera_source()
    gate_id  = args.gate     or Config.GATE_ID
    location = args.location or Config.GATE_LOCATION
    model    = args.model    or Config.YOLO_MODEL
    conf     = args.conf     or Config.CONFIDENCE_THRESHOLD
    line_pos = args.line     or Config.LINE_POSITION
    show_win = (not args.no_window) and Config.SHOW_WINDOW

    logger.info("=" * 60)
    logger.info("  AI Smart Gate Monitor — YOLOv8 + ByteTrack")
    logger.info("  Gate: %s (%s)", gate_id, location)
    logger.info("  Camera: %s", source)
    logger.info("  Model: %s  Conf: %.0f%%  Line: %.0f%%", model, conf * 100, line_pos * 100)
    logger.info("=" * 60)

    # ── Initialise modules ─────────────────────────────────────────────────────
    tracker    = Tracker(model_path=model, confidence=conf)
    counter    = Counter(line_position=line_pos, invert_direction=args.invert)
    db         = DBLogger(db_path=Config.DB_PATH)
    api_client = APIClient(
        api_url=Config.API_URL,
        gate_id=gate_id,
        location=location,
        interval_sec=Config.POST_INTERVAL_SEC,
        api_key=Config.API_KEY,
    )
    api_client.start(counter)

    # ── Open camera / video ────────────────────────────────────────────────────
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("❌  Cannot open camera/video source: %s", source)
        logger.error("    → For USB webcam, ensure CAMERA_SOURCE=0 in .env")
        logger.error("    → For video file testing, use: python main.py --source path/to/video.mp4")
        api_client.stop()
        sys.exit(1)

    logger.info("✅  Camera opened. Press Q to quit.")
    frame_count = 0
    fps_time    = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.info("End of stream / no frame. Exiting.")
                break

            frame_h = frame.shape[0]
            frame_count += 1

            # ── Run tracker ────────────────────────────────────────────────────
            tracks = tracker.track(frame)

            # ── Count crossings ────────────────────────────────────────────────
            new_in, new_out = counter.update(tracks, frame_h)

            # ── Log events to local DB ─────────────────────────────────────────
            for tid in new_in:
                db.log_event(gate_id, location, "IN",  tid)
                logger.info("🟢  IN   track_id=%d  |  total_in=%d", tid, counter.total_in)
            for tid in new_out:
                db.log_event(gate_id, location, "OUT", tid)
                logger.info("🔴  OUT  track_id=%d  |  total_out=%d", tid, counter.total_out)

            # ── Draw overlay ───────────────────────────────────────────────────
            if show_win:
                annotated = draw_overlay(frame, tracks, counter, frame_h, gate_id, location)
                cv2.imshow("SmartCampus Gate Monitor", annotated)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Q pressed — shutting down.")
                    break

            # ── FPS log every 300 frames ───────────────────────────────────────
            if frame_count % 300 == 0:
                elapsed = time.time() - fps_time
                fps = 300 / elapsed if elapsed > 0 else 0
                logger.info("FPS: %.1f  |  IN: %d  OUT: %d  NET: %d",
                            fps, counter.total_in, counter.total_out, counter.net)
                fps_time = time.time()

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user.")
    finally:
        # ── Final POST before shutdown ─────────────────────────────────────────
        logger.info("Sending final count to backend before shutdown…")
        api_client.post_now()
        api_client.stop()

        cap.release()
        if show_win:
            cv2.destroyAllWindows()

        summary = db.get_summary(gate_id)
        logger.info("=" * 60)
        logger.info("  Session Summary — Gate %s", gate_id)
        logger.info("  Total IN : %d", summary["total_in"])
        logger.info("  Total OUT: %d", summary["total_out"])
        logger.info("  Net      : %d", summary["net"])
        logger.info("=" * 60)


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run(parse_args())
