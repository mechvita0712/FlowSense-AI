"""
tracker.py — ByteTrack Multi-Object Tracker Wrapper
=====================================================
Uses Ultralytics' built-in ByteTrack (no separate install needed).
Assigns a persistent integer track_id to each detected person across frames.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class Tracker:
    """
    Wraps YOLOv8 + ByteTrack for consistent person tracking.

    ByteTrack is included in Ultralytics >= 8.0.
    It solves the re-ID problem: the same physical person keeps the same
    track_id even if briefly occluded.

    Usage:
        tracker = Tracker("yolov8n.pt", confidence=0.45)
        tracks  = tracker.track(frame)
        # tracks: list of {"id": int, "bbox": [x1,y1,x2,y2], "confidence": float}
    """

    PERSON_CLASS_ID = 0  # COCO class 0 = person

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.45):
        from ultralytics import YOLO
        import torch
        
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        logger.info("Initializing ByteTrack tracker with model: %s on device: %s", model_path, self.device)
        self.model = YOLO(model_path)
        self.model.to(self.device)
        self.confidence = confidence

    def track(self, frame: np.ndarray) -> list[dict]:
        """
        Run YOLOv8 + ByteTrack on a single BGR frame.

        Returns:
            List of dicts:
            [{"id": int, "bbox": [x1, y1, x2, y2], "confidence": float}]
            Filtered to persons only. id=-1 means tracking not yet established.
        """
        results = self.model.track(
            frame,
            persist=True,          # keep tracks alive across frames
            tracker="bytetrack.yaml",
            conf=self.confidence,
            classes=[self.PERSON_CLASS_ID],
            device=self.device,
            verbose=False,
        )

        tracks = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                # box.id is None if track not yet assigned
                track_id = int(box.id[0]) if box.id is not None else -1
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                tracks.append({
                    "id":         track_id,
                    "bbox":       [x1, y1, x2, y2],
                    "confidence": conf,
                })
        return tracks
