"""
counter.py — Virtual Line Crossing Counter
===========================================
Detects when a tracked person crosses a virtual horizontal line
and classifies the crossing as IN (entering) or OUT (exiting).

Algorithm:
  - A virtual line sits at y = frame_height × line_position
  - For each track_id, store the y-centroid from the previous frame
  - Crossing direction:
      prev_y < line_y AND curr_y >= line_y  →  IN  (moving downward / entering)
      prev_y > line_y AND curr_y <= line_y  →  OUT (moving upward  / exiting)
  - Each track_id is counted only ONCE (set-based deduplication)

Customise IN/OUT direction:
  If your camera is mounted so that "entering" means moving UP, swap the
  logic in _classify_crossing() or set invert_direction=True in __init__.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CounterState:
    total_in:  int = 0
    total_out: int = 0
    counted_in_ids:  set = field(default_factory=set)
    counted_out_ids: set = field(default_factory=set)
    prev_centroids:  dict = field(default_factory=dict)  # track_id → previous cy


class Counter:
    """
    Stateful virtual-line person counter.

    Args:
        line_position:    Fraction of frame height where the virtual line sits (0.0–1.0).
        invert_direction: If True, treat downward motion as OUT and upward as IN.
    """

    def __init__(self, line_position: float = 0.5, invert_direction: bool = False):
        self.line_position    = line_position
        self.invert_direction = invert_direction
        self.state = CounterState()

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, tracks: list[dict], frame_height: int) -> tuple[list[int], list[int]]:
        """
        Process a list of current tracks and detect line crossings.

        Args:
            tracks:       Output of Tracker.track() — list of {id, bbox, confidence}
            frame_height: Height of the current frame in pixels.

        Returns:
            (newly_in_ids, newly_out_ids) — track IDs that crossed this frame.
        """
        line_y      = int(frame_height * self.line_position)
        newly_in:  list[int] = []
        newly_out: list[int] = []

        for track in tracks:
            tid = track["id"]
            if tid < 0:
                continue  # unassigned track — skip

            x1, y1, x2, y2 = track["bbox"]
            cy = (y1 + y2) // 2  # vertical centroid of bounding box

            if tid in self.state.prev_centroids:
                prev_cy = self.state.prev_centroids[tid]
                direction = self._classify_crossing(prev_cy, cy, line_y)

                if direction == "IN" and tid not in self.state.counted_in_ids:
                    self.state.total_in += 1
                    self.state.counted_in_ids.add(tid)
                    newly_in.append(tid)
                    logger.debug("IN  ← track_id=%d  cy: %d → %d (line=%d)", tid, prev_cy, cy, line_y)

                elif direction == "OUT" and tid not in self.state.counted_out_ids:
                    self.state.total_out += 1
                    self.state.counted_out_ids.add(tid)
                    newly_out.append(tid)
                    logger.debug("OUT → track_id=%d  cy: %d → %d (line=%d)", tid, prev_cy, cy, line_y)

            self.state.prev_centroids[tid] = cy

        return newly_in, newly_out

    def _classify_crossing(self, prev_cy: int, curr_cy: int, line_y: int) -> str | None:
        """
        Returns 'IN', 'OUT', or None based on centroid crossing the virtual line.
        Default: moving downward (increasing y) = IN.
        """
        crossed_down = prev_cy < line_y <= curr_cy
        crossed_up   = prev_cy > line_y >= curr_cy

        if self.invert_direction:
            crossed_down, crossed_up = crossed_up, crossed_down

        if crossed_down:
            return "IN"
        if crossed_up:
            return "OUT"
        return None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def total_in(self) -> int:
        return self.state.total_in

    @property
    def total_out(self) -> int:
        return self.state.total_out

    @property
    def net(self) -> int:
        """Net people currently inside (total_in - total_out)."""
        return self.state.total_in - self.state.total_out

    def line_y(self, frame_height: int) -> int:
        return int(frame_height * self.line_position)

    def reset(self):
        """Reset all counters (e.g. at start of new day)."""
        self.state = CounterState()
        logger.info("Counter reset.")
