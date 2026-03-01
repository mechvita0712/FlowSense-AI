"""
api_client.py — Flask Backend API Client
=========================================
Periodically POSTs the aggregated IN+OUT count to the existing
SmartCampus Flask backend at POST /api/traffic/add.

Fails silently: if the backend is unreachable, the gate monitor
keeps running and logging locally — no crash, no data loss.
"""

from __future__ import annotations

import logging
import time
import threading
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


class APIClient:
    """
    Sends aggregated crowd counts to the backend on a configurable interval.

    Usage:
        client = APIClient(api_url, gate_id, location, interval_sec=30)
        client.start(counter)      # starts background thread
        # ... gate monitor runs ...
        client.stop()
    """

    def __init__(
        self,
        api_url:      str,
        gate_id:      str,
        location:     str,
        interval_sec: int = 30,
        timeout_sec:  int = 5,
        api_key:      str = "",
    ):
        self.api_url      = api_url
        self.gate_id      = gate_id
        self.location     = location
        self.interval_sec = interval_sec
        self.timeout_sec  = timeout_sec
        self.api_key      = api_key

        self._counter_ref = None
        self._stop_event  = threading.Event()
        self._thread:     threading.Thread | None = None

    # ── Threading ─────────────────────────────────────────────────────────────

    def start(self, counter) -> None:
        """
        Start the background thread that periodically POSTs counts.

        Args:
            counter: A Counter instance (exposes .total_in, .total_out, .net)
        """
        self._counter_ref = counter
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="api-poster")
        self._thread.start()
        logger.info(
            "APIClient started — posting to %s every %ds",
            self.api_url, self.interval_sec,
        )

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("APIClient stopped.")

    # ── Internal Loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_sec):
            self.post_now()

    # ── Single POST ───────────────────────────────────────────────────────────

    def post_now(self) -> bool:
        """
        POST the current total count to the Flask backend.
        Returns True on success, False on failure.
        """
        if self._counter_ref is None:
            return False

        total = self._counter_ref.total_in + self._counter_ref.total_out
        payload = {
            "location": self.location,
            "count":    total,
            "gate_id":  self.gate_id,
            "source":   "vision",          # identifies as AI vision system
        }

        # Prepare headers with API key if provided
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            logger.info(
                "✅ Posted to backend: gate=%s  total=%d (in=%d out=%d) → HTTP %d",
                self.gate_id,
                total,
                self._counter_ref.total_in,
                self._counter_ref.total_out,
                resp.status_code,
            )
            return True

        except requests.exceptions.ConnectionError:
            logger.warning("⚠️  Backend unreachable (%s). Will retry in %ds.", self.api_url, self.interval_sec)
        except requests.exceptions.Timeout:
            logger.warning("⚠️  Backend POST timed out after %ds.", self.timeout_sec)
        except requests.exceptions.HTTPError as e:
            logger.warning("⚠️  Backend returned error: %s", e)
        except Exception as e:
            logger.warning("⚠️  Unexpected error posting to backend: %s", e)

        return False
