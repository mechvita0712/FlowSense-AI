"""
detector.py — YOLOv8 Person Detection Wrapper
==============================================
Loads YOLOv8 and filters detections to class 'person' only.
The model weights (yolov8n.pt ~6 MB) are downloaded automatically on first run.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class Detector:
    """
    Wraps Ultralytics YOLOv8 for person-only detection.

    Usage:
        detector = Detector("yolov8n.pt", confidence=0.45)
        results  = detector.detect(frame)
        # results: list of {"bbox": [x1,y1,x2,y2], "confidence": float}
    """

    PERSON_CLASS_ID = 0  # COCO class 0 = person

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.45):
        from ultralytics import YOLO  # imported here so module loads even without ultralytics
        logger.info("Loading YOLOv8 model: %s", model_path)
        self.model = YOLO(model_path)
        self.confidence = confidence
        logger.info("YOLOv8 model loaded. Running on: %s", self.model.device)

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run inference on a single BGR frame (as returned by cv2.VideoCapture.read()).

        Returns:
            List of dicts: [{"bbox": [x1, y1, x2, y2], "confidence": float}]
            Filtered to persons only (class 0).
        """
        results = self.model(frame, verbose=False, conf=self.confidence, classes=[self.PERSON_CLASS_ID])
        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                detections.append({"bbox": [x1, y1, x2, y2], "confidence": conf})
        return detections
