"""
db_logger.py — Local SQLite Event Logger
=========================================
Logs every IN/OUT crossing event with gate_id, track_id, and timestamp.
Uses Python's built-in sqlite3 — no extra dependencies.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class DBLogger:
    """
    Lightweight SQLite logger for gate crossing events.

    Table: gate_events
      id          INTEGER PRIMARY KEY
      gate_id     TEXT       — e.g. "A"
      location    TEXT       — e.g. "Main Entrance, North"
      event_type  TEXT       — "IN" or "OUT"
      track_id    INTEGER    — ByteTrack unique person ID
      timestamp   TEXT       — ISO-8601 UTC
    """

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS gate_events (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        gate_id    TEXT    NOT NULL,
        location   TEXT    NOT NULL,
        event_type TEXT    NOT NULL,
        track_id   INTEGER NOT NULL,
        timestamp  TEXT    NOT NULL
    );
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(self.CREATE_TABLE)
        logger.info("DBLogger initialised. DB: %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Write ─────────────────────────────────────────────────────────────────

    def log_event(
        self,
        gate_id:    str,
        location:   str,
        event_type: str,   # "IN" or "OUT"
        track_id:   int,
    ):
        """Insert a single crossing event into the local DB."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO gate_events (gate_id, location, event_type, track_id, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (gate_id, location, event_type, track_id, ts),
            )
        logger.debug("Logged %s event: gate=%s track_id=%d", event_type, gate_id, track_id)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_summary(self, gate_id: str, since: str | None = None) -> dict:
        """
        Return aggregated IN/OUT totals for a gate, optionally filtered by time.

        Args:
            gate_id: Gate identifier (e.g. "A")
            since:   ISO-8601 datetime string to filter from (optional)

        Returns:
            {"gate_id": ..., "total_in": N, "total_out": M, "net": N-M, "since": ...}
        """
        base = "SELECT event_type, COUNT(*) as cnt FROM gate_events WHERE gate_id = ?"
        params: list = [gate_id]

        if since:
            base += " AND timestamp >= ?"
            params.append(since)

        base += " GROUP BY event_type"

        with self._connect() as conn:
            rows = conn.execute(base, params).fetchall()

        totals = {"IN": 0, "OUT": 0}
        for row in rows:
            totals[row["event_type"]] = row["cnt"]

        return {
            "gate_id":   gate_id,
            "total_in":  totals["IN"],
            "total_out": totals["OUT"],
            "net":       totals["IN"] - totals["OUT"],
            "since":     since or "all time",
        }

    def get_recent_events(self, gate_id: str, limit: int = 50) -> list[dict]:
        """Return the most recent N events for a gate."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM gate_events WHERE gate_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (gate_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
