"""
congestion_service.py — Rule-based & statistical congestion analysis
"""

from __future__ import annotations
import math
import random
from datetime import datetime, timezone
from typing import Any


class CongestionService:
    """
    Stateless service that evaluates traffic entries and gates,
    produces alert payloads, and generates seed data for demo/testing.
    """

    # ── Congestion Evaluation ─────────────────────────────────────────────────

    @staticmethod
    def evaluate(
        entries: list,
        warn_threshold: int = 200,
        crit_threshold: int = 350,
    ) -> list[dict]:
        """
        Scan a list of TrafficEntry ORM objects (or plain dicts) and return
        a structured alert for every location that exceeds a threshold.
        """
        # Aggregate the latest count per location
        latest: dict[str, dict] = {}
        for e in entries:
            loc = e.location if hasattr(e, "location") else e.get("location", "Unknown")
            cnt = e.count    if hasattr(e, "count")    else e.get("count", 0)
            if loc not in latest or cnt > latest[loc]["count"]:
                latest[loc] = {"location": loc, "count": cnt}

        alerts: list[dict] = []
        for loc, info in latest.items():
            count = info["count"]
            if count >= crit_threshold:
                alerts.append({
                    "severity":    "critical",
                    "location":    loc,
                    "count":       count,
                    "message":     f"CRITICAL congestion at {loc} ({count} people)",
                    "action":      "Redirect crowd to alternate gates immediately.",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                })
            elif count >= warn_threshold:
                alerts.append({
                    "severity":    "warning",
                    "location":    loc,
                    "count":       count,
                    "message":     f"High congestion at {loc} ({count} people)",
                    "action":      "Deploy additional staff and increase shuttle frequency.",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                })

        # Sort by severity then count descending
        severity_order = {"critical": 0, "warning": 1}
        alerts.sort(key=lambda a: (severity_order.get(a["severity"], 9), -a["count"]))
        return alerts

    # ── Level Labels ─────────────────────────────────────────────────────────

    @staticmethod
    def level_of(density: float) -> str:
        if density >= 80:
            return "critical"
        if density >= 60:
            return "high"
        if density >= 30:
            return "moderate"
        return "low"

    # ── Gate Recommendation ───────────────────────────────────────────────────

    @staticmethod
    def recommend(gate: dict) -> str:
        density = gate.get("density", 0)
        gate_id = gate.get("gate_id", "?")
        alternates = {"A": "B", "B": "E", "C": "B", "D": "E", "E": "D", "F": "B"}
        if density >= 80:
            alt = alternates.get(gate_id, "B")
            return f"⚠️ Redirect crowd to Gate {alt}. Deploy marshals at {gate_id}."
        if density >= 60:
            return f"Monitor closely. Increase shuttle frequency at Gate {gate_id}."
        return "Normal flow. No action required."

    # ── Seed Data (Demo / First-Run) ──────────────────────────────────────────

    @staticmethod
    def seed_gate_data() -> list[dict]:
        """Returns 10 empty gates. Values will be updated dynamically by YOLO."""
        gates = [
            {"gate_id": "A", "name": "Gate A", "location": "Main Entrance, North",   "density": 0.0, "entries": 0},
            {"gate_id": "B", "name": "Gate B", "location": "Academic Block, East",   "density": 0.0, "entries": 0},
            {"gate_id": "C", "name": "Gate C", "location": "Sports Complex, West",   "density": 0.0, "entries": 0},
            {"gate_id": "D", "name": "Gate D", "location": "Residential Block",      "density": 0.0, "entries": 0},
            {"gate_id": "E", "name": "Gate E", "location": "Library & Labs",         "density": 0.0, "entries": 0},
            {"gate_id": "F", "name": "Gate F", "location": "Admin & Cafeteria",      "density": 0.0, "entries": 0},
            {"gate_id": "G", "name": "Gate G", "location": "South Car Park",         "density": 0.0, "entries": 0},
            {"gate_id": "H", "name": "Gate H", "location": "Auditorium Hub",         "density": 0.0, "entries": 0},
            {"gate_id": "I", "name": "Gate I", "location": "Research Wing",          "density": 0.0, "entries": 0},
            {"gate_id": "J", "name": "Gate J", "location": "East Station Hub",       "density": 0.0, "entries": 0},
        ]
        return gates

    @staticmethod
    def seed_shuttle_data() -> list[dict]:
        return [
            {"shuttle_id": "S1", "name": "Shuttle 01", "route": "Gate A → B → C", "load": 38.0, "capacity": 45, "status": "active",      "next_stop": "Gate B", "eta_min": 3},
            {"shuttle_id": "S2", "name": "Shuttle 02", "route": "Gate C → D → E", "load": 29.0, "capacity": 45, "status": "active",      "next_stop": "Gate D", "eta_min": 6},
            {"shuttle_id": "S3", "name": "Shuttle 03", "route": "Gate F → A → B", "load": 16.0, "capacity": 45, "status": "active",      "next_stop": "Gate A", "eta_min": 2},
            {"shuttle_id": "S4", "name": "Shuttle 04", "route": "Gate B → E → F", "load": 43.0, "capacity": 45, "status": "active",      "next_stop": "Gate E", "eta_min": 5},
            {"shuttle_id": "S5", "name": "Shuttle 05", "route": "Gate A → F",     "load":  7.0, "capacity": 45, "status": "active",      "next_stop": "Gate F", "eta_min": 8},
            {"shuttle_id": "S6", "name": "Shuttle 06", "route": "Event Special",   "load":  0.0, "capacity": 45, "status": "standby",     "next_stop": "—",      "eta_min": None},
            {"shuttle_id": "S7", "name": "Shuttle 07", "route": "Gate C → B → A", "load":  0.0, "capacity": 45, "status": "maintenance", "next_stop": "—",      "eta_min": None},
            {"shuttle_id": "S8", "name": "Shuttle 08", "route": "Gate D → E",     "load": 25.0, "capacity": 45, "status": "active",      "next_stop": "Gate E", "eta_min": 4},
        ]
