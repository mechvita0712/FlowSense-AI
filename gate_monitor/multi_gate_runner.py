"""
multi_gate_runner.py — 1-to-10 Gate Multiplexer
=================================================
Reads a single video feed, processes it ONCE per frame with YOLOv8+ByteTrack,
and passes the tracked people into 10 independent virtual gates.

This simulates a 10-camera campus setup without melting the GPU/CPU.
To make the 10 gates behave differently, each gate has a uniquely offset
virtual counting line (from 15% to 85% of frame height).

Usage:
    python multi_gate_runner.py --source ../videos/feed.mp4
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

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("multi_gate")

GATE_DEFS = [
    {"id": "A", "loc": "Main Entrance, North", "line": 0.15},
    {"id": "B", "loc": "Academic Block, East", "line": 0.22},
    {"id": "C", "loc": "Sports Complex, West", "line": 0.30},
    {"id": "D", "loc": "Residential Block",    "line": 0.38},
    {"id": "E", "loc": "Library & Labs",       "line": 0.45},
    {"id": "F", "loc": "Admin & Cafeteria",    "line": 0.52},
    {"id": "G", "loc": "South Car Park",       "line": 0.60},
    {"id": "H", "loc": "Auditorium Hub",       "line": 0.68},
    {"id": "I", "loc": "Research Wing",        "line": 0.76},
    {"id": "J", "loc": "East Station Hub",     "line": 0.85},
]


class VirtualGate:
    """Wraps Counter, DBLogger, and APIClient for a single gate."""
    def __init__(self, gate_id: str, location: str, line_pos: float):
        self.gate_id = gate_id
        self.location = location
        self.counter = Counter(line_position=line_pos)
        self.db = DBLogger(db_path=Config.DB_PATH)
        self.api = APIClient(
            api_url=Config.API_URL,
            gate_id=gate_id,
            location=location,
            interval_sec=Config.POST_INTERVAL_SEC,
            api_key=Config.API_KEY,
        )
        self.api.start(self.counter)

    def process_tracks(self, tracks: list[dict], frame_h: int):
        new_in, new_out = self.counter.update(tracks, frame_h)
        for tid in new_in:
            self.db.log_event(self.gate_id, self.location, "IN", tid)
        for tid in new_out:
            self.db.log_event(self.gate_id, self.location, "OUT", tid)

    def draw_line(self, frame: np.ndarray, frame_h: int):
        y = self.counter.line_y(frame_h)
        cv2.line(frame, (0, y), (frame.shape[1], y), (0, 255, 255), 1)
        cv2.putText(frame, self.gate_id, (10, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    def stop(self):
        self.api.post_now()
        self.api.stop()


import os
# Compute path to videos/feed.mp4 relative to this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_VIDEO = os.path.join(BASE_DIR, "videos", "feed.mp4")

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_VIDEO, help="Video source")
    parser.add_argument("--no-window", action="store_true")
    args = parser.parse_args()

    logger.info("==================================================")
    logger.info("🚀 Starting 10-Gate AI Multiplexer")
    logger.info("Source: %s", args.source)
    logger.info("==================================================")

    # 1. Initialize YOLOv8 Tracker (ONCE)
    tracker = Tracker(model_path=Config.YOLO_MODEL, confidence=Config.CONFIDENCE_THRESHOLD)

    # 2. Initialize 10 Virtual Gates
    gates = [VirtualGate(g["id"], g["loc"], g["line"]) for g in GATE_DEFS]

    # 3. Open Video
    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        logger.error("❌ Cannot open video: %s", args.source)
        sys.exit(1)

    # Determine FPS to enforce normal playback speed
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    target_delay_sec = 1.0 / fps

    frame_count = 0
    show_win = not args.no_window

    try:
        while True:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                logger.info("End of stream. Looping video...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_h = frame.shape[0]
            frame_count += 1

            # --- RUN HEAVY AI EXACTLY ONCE ---
            tracks = tracker.track(frame)

            # --- DISTRIBUTE TO 10 GATES ---
            for g in gates:
                g.process_tracks(tracks, frame_h)

            # --- DRAWING ---
            if show_win:
                # Draw bounding boxes
                for t in tracks:
                    x1, y1, x2, y2 = t["bbox"]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"ID:{t['id']}", (x1, max(y1-5, 10)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

                # Draw 10 lines
                for g in gates:
                    g.draw_line(frame, frame_h)

                # Stats Box
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (200, 40), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
                cv2.putText(frame, f"10 Gates Running", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

                cv2.imshow("10-Gate AI Multiplexer", frame)
                
                # Enforce normal playback speed
                # Calculate how much time the frame processing took
                elapsed = time.time() - start_time
                # We need to wait (target_delay - elapsed)
                wait_time_ms = int(max(1, (target_delay_sec - elapsed) * 1000))
                
                if cv2.waitKey(wait_time_ms) & 0xFF == ord('q'):
                    break

            if frame_count % 150 == 0:
                logger.info("Processing frame %d...", frame_count)

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        logger.info("Shutting down 10 gates (sending final counts to backend)...")
        for g in gates:
            g.stop()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
