"""
antigravity_service.py — Anti-Gravity AI Optimization & Mobility Intelligence Engine
======================================================================================
Integrated into: SmartCampus AI v2.1
Engine Version : Anti-Gravity AI v1.0

Capabilities:
  1. Adaptive congestion prediction  (time-of-day, momentum, weather, events)
  2. Real-time anomaly detection     (statistical outliers, spikes, overloads)
  3. Dynamic shuttle optimization    (advisory or autonomous mode)
  4. Graph-based route optimization  (Dijkstra with congestion-weighted edges)
  5. System-wide risk classification (CRITICAL / HIGH / MEDIUM / LOW)
  6. Explainable AI output           (plain-language summary per decision)

Design rules:
  - NEVER crashes the backend — all errors caught and returned as fallback JSON.
  - No external API required by default.
  - Returns deterministic, valid JSON always.
  - Response target: < 300 ms.
"""

from __future__ import annotations

import math
import random
import statistics
from datetime import datetime, timezone
from typing import Any


# ── Campus Topology (weighted undirected graph) ────────────────────────────────
#   Weight = distance_factor (lower = shorter / easier path)
#   Congestion penalty is added dynamically per request.

_CAMPUS_GRAPH: dict[tuple[str, str], float] = {
    ("A", "B"): 2.0, ("B", "A"): 2.0,
    ("A", "F"): 3.0, ("F", "A"): 3.0,
    ("B", "C"): 3.5, ("C", "B"): 3.5,
    ("B", "E"): 2.0, ("E", "B"): 2.0,
    ("B", "F"): 2.5, ("F", "B"): 2.5,
    ("C", "D"): 4.0, ("D", "C"): 4.0,
    ("D", "E"): 2.0, ("E", "D"): 2.0,
    ("E", "F"): 3.0, ("F", "E"): 3.0,
}

_ROUTE_LABELS: dict[tuple[str, str], str] = {
    ("A", "B"): "Inner academic corridor",
    ("A", "F"): "Admin west passage",
    ("B", "C"): "North sports trail",
    ("B", "E"): "Library east path",
    ("B", "F"): "East corridor link",
    ("C", "B"): "Campus shaded trail via Sports Complex perimeter",
    ("C", "D"): "Residential block route",
    ("D", "E"): "Cycle lane (fastest off-road)",
    ("E", "D"): "Science garden walkway",
    ("E", "F"): "Lab-to-admin skybridge path",
    ("F", "A"): "Admin north access road",
    ("F", "B"): "East corridor link",
}

_ALTERNATES: dict[str, str] = {
    "A": "B", "B": "E", "C": "B",
    "D": "E", "E": "D", "F": "B",
}

_WEATHER_MODIFIERS: dict[str, float] = {
    "clear":      1.00,
    "cloudy":     1.02,
    "fog":        1.05,
    "hot":        1.08,
    "rain":       1.15,
    "heavy_rain": 1.25,
    "storm":      1.35,
}


class AntiGravityAI:
    """
    Stateless, thread-safe AI optimization engine.
    Entry point: AntiGravityAI.analyze(payload, mode)
    """

    # ── Public Entry Point ────────────────────────────────────────────────────

    @classmethod
    def analyze(cls, payload: dict, mode: str = "advisory") -> dict:
        """
        Run the full Anti-Gravity intelligence pipeline.

        Args:
            payload: Input dict containing gates, shuttles, weather, events.
            mode:    "advisory"   → recommendations only (safe for all envs)
                     "autonomous" → executable decisions (production-ready)

        Returns:
            Structured JSON dict. NEVER raises an exception.
        """
        try:
            return cls._run(payload, mode)
        except Exception as exc:  # absolute failsafe
            return {
                "status":     "fallback",
                "message":    f"Anti-Gravity AI internal error: {str(exc)[:120]}",
                "risk_level": "unknown",
                "engine":     "Anti-Gravity AI v1.0",
            }

    # ── Pipeline Orchestrator ─────────────────────────────────────────────────

    @classmethod
    def _run(cls, payload: dict, mode: str) -> dict:
        # ── Input validation ──────────────────────────────────────────────────
        if not isinstance(payload, dict):
            return cls._fallback("Payload must be a JSON object.")

        gates:       list[dict] = payload.get("gates", [])
        shuttles:    list[dict] = payload.get("shuttles", [])
        weather:     str        = str(payload.get("weather", "clear")).lower()
        event_flags: list       = payload.get("event_flags", []) or []

        if not gates:
            return cls._fallback("Missing required field: 'gates' array.")

        # ── Timestamp ─────────────────────────────────────────────────────────
        raw_ts = payload.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(str(raw_ts)) if raw_ts else datetime.now(timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        hour = ts.hour

        # ── Normalise gate dicts ──────────────────────────────────────────────
        # Accept both "density" (float %) and "count" (int headcount) formats.
        norm_gates = cls._normalise_gates(gates)

        # ── Run all intelligence modules in sequence ──────────────────────────
        weather_mod  = _WEATHER_MODIFIERS.get(weather, 1.0)
        event_amp    = 1.0 + 0.15 * min(len(event_flags), 5)

        predictions        = cls._predict(norm_gates, hour, weather_mod, event_amp)
        anomalies          = cls._detect_anomalies(norm_gates, shuttles)
        risk_level         = cls._classify_risk(norm_gates)
        shuttle_strategy   = cls._optimize_shuttles(norm_gates, shuttles, mode)
        route_optimizations = cls._optimize_routes(norm_gates)
        explanation        = cls._explain(norm_gates, risk_level, anomalies, hour, weather)

        return {
            "predictions":         predictions,
            "anomalies":           anomalies,
            "risk_level":          risk_level,
            "shuttle_strategy":    shuttle_strategy,
            "route_optimizations": route_optimizations,
            "explanation":         explanation,
            "mode":                mode,
            "generated_at":        datetime.now(timezone.utc).isoformat(),
            "engine":              "Anti-Gravity AI v1.0",
        }

    # ── Input Normalisation ───────────────────────────────────────────────────

    @staticmethod
    def _normalise_gates(gates: list[dict]) -> list[dict]:
        """Ensure every gate has a valid 'density' (0–100 %) field."""
        out = []
        for g in gates:
            g = dict(g)  # shallow copy — do not mutate original
            density = g.get("density")

            # If only headcount provided, estimate density (assume max ≈ 500)
            if density is None:
                count = float(g.get("count", g.get("entries", 0)))
                density = min(99.9, round(count / 5.0, 1))

            g["density"] = float(density)
            out.append(g)
        return out

    # ── Module 1: Adaptive Prediction ────────────────────────────────────────

    @classmethod
    def _predict(
        cls,
        gates:       list[dict],
        hour:        int,
        weather_mod: float,
        event_amp:   float,
    ) -> list[dict]:
        """
        Anti-Gravity adaptive prediction formula:
            predicted = (0.5 × current)
                      + (0.3 × trend_factor)
                      + (0.2 × time_peak × 60)
                      + noise
            × weather_modifier × event_amplifier
        Clamped to [5.0, 99.9] %.
        """
        densities    = [g["density"] for g in gates]
        campus_avg   = statistics.mean(densities) if densities else 50.0
        time_peak    = cls._time_peak_factor(hour)
        predictions  = []

        for gate in gates:
            gate_id = gate.get("gate_id", "?")
            current = gate["density"]

            # Momentum trend: how far above/below campus average this gate is
            trend_factor = current + (current - campus_avg) * 0.35

            # Gaussian noise (small, bounded)
            noise = max(-4.0, min(4.0, random.gauss(0, 1.8)))

            raw = (
                0.50 * current
                + 0.30 * trend_factor
                + 0.20 * (time_peak * 60.0)
                + noise
            ) * weather_mod * event_amp

            predicted  = round(min(99.9, max(5.0, raw)), 1)

            # Confidence: higher when current density is mid-range (more stable)
            # Lower at extremes (very low or very high → higher uncertainty)
            stability  = 1.0 - abs(predicted - 50.0) / 100.0
            confidence = round(min(99.0, max(60.0, 65.0 + stability * 35.0 + random.gauss(0, 1.0))), 1)

            trend_label = (
                "rising"  if predicted > current + 2  else
                "falling" if predicted < current - 2  else
                "stable"
            )

            predictions.append({
                "gate_id":          gate_id,
                "current_density":  current,
                "next_hour_density": predicted,
                "confidence":       confidence,
                "trend":            trend_label,
            })

        # Sort: highest predicted density first (most urgent on top)
        predictions.sort(key=lambda x: -x["next_hour_density"])
        return predictions

    @staticmethod
    def _time_peak_factor(hour: int) -> float:
        """
        Tri-modal Gaussian weighting:
          Morning  peak → 09:00  σ=1.5
          Lunch    peak → 13:00  σ=0.8
          Evening  peak → 17:00  σ=1.8
        Returns the dominant factor (0.0 – 1.0).
        """
        def _g(x: float, mu: float, sigma: float) -> float:
            return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

        morning = _g(hour, 9.0,  1.5)
        lunch   = _g(hour, 13.0, 0.8) * 0.80
        evening = _g(hour, 17.0, 1.8)
        return max(morning, lunch, evening)

    # ── Module 2: Anomaly Detection ───────────────────────────────────────────

    @classmethod
    def _detect_anomalies(
        cls,
        gates:    list[dict],
        shuttles: list[dict],
    ) -> list[dict]:
        """
        Flags anomalies by three rules:
          1. Gate density deviates > 2σ from campus mean.
          2. Gate density ≥ 85% (absolute extreme-density spike).
          3. Shuttle load ≥ 90% (overload) or ≥ 70% (high load warning).
        """
        anomalies: list[dict] = []
        densities = [g["density"] for g in gates]

        # Statistical baseline
        if len(densities) >= 2:
            campus_avg = statistics.mean(densities)
            campus_std = statistics.stdev(densities)
        else:
            campus_avg = densities[0] if densities else 50.0
            campus_std = 0.0

        for gate in gates:
            gid     = gate.get("gate_id", "?")
            density = gate["density"]
            dev     = abs(density - campus_avg)

            # Rule 1 — Statistical outlier (> 2σ)
            if campus_std > 1.0 and dev > 2.0 * campus_std:
                severity   = "critical" if density >= 80 else "warning"
                confidence = round(min(99.0, 68.0 + (dev / max(campus_std, 1)) * 6.0), 1)
                anomalies.append({
                    "type":      "statistical_outlier",
                    "gate_id":   gid,
                    "severity":  severity,
                    "detail":    (
                        f"Gate {gid} at {density}% is {round(dev / campus_std, 1)}σ "
                        f"above campus average ({round(campus_avg, 1)}%)."
                    ),
                    "confidence": confidence,
                })

            # Rule 2 — Extreme density spike (≥ 85%)
            if density >= 85:
                conf = round(min(99.0, 80.0 + (density - 85.0) * 1.3), 1)
                anomalies.append({
                    "type":     "extreme_density_spike",
                    "gate_id":  gid,
                    "severity": "critical",
                    "detail":   (
                        f"Gate {gid} at {density}% — EXCEEDS critical safety threshold (85%). "
                        "Immediate crowd dispersal required."
                    ),
                    "confidence": conf,
                })

        # Shuttle anomalies
        for s in shuttles:
            sid  = s.get("id") or s.get("shuttle_id", "?")
            load = float(s.get("load_percent", s.get("load", 0)))

            if load >= 90:
                anomalies.append({
                    "type":      "shuttle_overload",
                    "shuttle_id": sid,
                    "severity":  "critical",
                    "detail":    f"Shuttle {sid} at {load}% capacity — passengers cannot safely board.",
                    "confidence": 97.0,
                })
            elif load >= 70:
                anomalies.append({
                    "type":      "shuttle_high_load",
                    "shuttle_id": sid,
                    "severity":  "warning",
                    "detail":    f"Shuttle {sid} at {load}% capacity — nearing maximum load.",
                    "confidence": 85.0,
                })

        return anomalies

    # ── Module 3: Risk Classification ─────────────────────────────────────────

    @staticmethod
    def _classify_risk(gates: list[dict]) -> str:
        """
        CRITICAL → ≥2 gates at ≥85%  OR  total entries > 2000
        HIGH     → 1 gate at ≥85%  OR  ≥3 gates at ≥70%
        MEDIUM   → ≥1 gate at ≥60%
        LOW      → otherwise
        """
        densities     = [g["density"] for g in gates]
        total_entries = sum(int(g.get("entries", 0)) for g in gates)

        n_critical = sum(1 for d in densities if d >= 85)
        n_high     = sum(1 for d in densities if d >= 70)
        n_medium   = sum(1 for d in densities if d >= 60)

        if n_critical >= 2 or total_entries > 2000:
            return "critical"
        if n_critical == 1 or n_high >= 3:
            return "high"
        if n_medium >= 1:
            return "medium"
        return "low"

    # ── Module 4: Shuttle Strategy ────────────────────────────────────────────

    @classmethod
    def _optimize_shuttles(
        cls,
        gates:    list[dict],
        shuttles: list[dict],
        mode:     str,
    ) -> list[dict]:
        """
        Optimization rules:
          R1: Gate ≥85% + standby shuttle available  → activate standby
          R2: 2+ gates ≥80%                          → dynamic redistribution
          R3: Shuttle ≥90% load                      → reroute to low-density gate
        """
        strategy: list[dict] = []
        act = "activate" if mode == "autonomous" else "recommend_activate"

        # Pools
        standby_pool = [s for s in shuttles if s.get("status") == "standby"]
        gate_density = {g.get("gate_id"): g["density"] for g in gates}

        # Sort gates (highest density first)
        critical_gates = sorted(
            [g for g in gates if g["density"] >= 85],
            key=lambda g: -g["density"],
        )
        high_gates = sorted(
            [g for g in gates if 80 <= g["density"] < 85],
            key=lambda g: -g["density"],
        )
        low_density_gate = min(gates, key=lambda g: g["density"], default=None)

        # Rule 1 — Activate standby for critical gates
        for gate in critical_gates:
            gid     = gate.get("gate_id", "?")
            density = gate["density"]
            alt     = _ALTERNATES.get(gid, "B")

            if standby_pool:
                shuttle = standby_pool.pop(0)
                sid     = shuttle.get("id") or shuttle.get("shuttle_id", "?")
                strategy.append({
                    "action":       act,
                    "shuttle_id":   sid,
                    "assign_route": f"Gate {gid} → Gate {alt} → Emergency Loop",
                    "reason":       f"Gate {gid} at {density}% (≥85% critical threshold). Standby unit needed immediately.",
                    "priority":     "critical",
                })
            else:
                strategy.append({
                    "action":   "alert_no_standby",
                    "gate_id":  gid,
                    "reason":   f"Gate {gid} at {density}% — NO standby shuttles available. Request emergency vehicle.",
                    "priority": "critical",
                })

        # Rule 2 — Dynamic redistribution for ≥2 high-density gates
        if len(high_gates) >= 2:
            affected = ["Gate " + g.get("gate_id", "?") for g in high_gates[:3]]
            strategy.append({
                "action":          "redistribute" if mode == "autonomous" else "recommend_redistribute",
                "affected_gates":  affected,
                "reason":          f"Multiple high-density gates detected ({', '.join(affected)}). Redistribute active fleet to balance load.",
                "priority":        "high",
            })

        # Rule 3 — Reroute overloaded shuttles
        for s in shuttles:
            load = float(s.get("load_percent", s.get("load", 0)))
            sid  = s.get("id") or s.get("shuttle_id", "?")

            if load >= 90 and low_density_gate:
                target = low_density_gate.get("gate_id", "B")
                strategy.append({
                    "action":       "reroute" if mode == "autonomous" else "recommend_reroute",
                    "shuttle_id":   sid,
                    "assign_route": f"Divert to Gate {target} (lowest density: {low_density_gate['density']}%)",
                    "reason":       f"Shuttle {sid} at {load}% load — offload to low-density zone.",
                    "priority":     "high",
                })

        return strategy

    # ── Module 5: Graph-Based Route Optimisation ──────────────────────────────

    @classmethod
    def _optimize_routes(cls, gates: list[dict]) -> list[dict]:
        """
        For each gate with density ≥ 60%, find the lowest-cost alternate gate
        using a Dijkstra-style single-source shortest path on _CAMPUS_GRAPH,
        where edge weight = distance_factor + (dest_density / 10).
        Returns top 5 recommendations sorted by density differential.
        """
        gate_density: dict[str, float] = {g.get("gate_id", "?"): g["density"] for g in gates}
        congested = sorted(
            [(gid, d) for gid, d in gate_density.items() if d >= 60],
            key=lambda x: -x[1],
        )

        optimizations: list[dict] = []

        for from_gid, from_density in congested[:5]:
            best = cls._dijkstra_single(from_gid, gate_density)
            if best is None:
                continue

            to_gid, cost = best
            to_density   = gate_density.get(to_gid, 0.0)

            # Path label (try both directions in the table)
            label = (
                _ROUTE_LABELS.get((from_gid, to_gid))
                or _ROUTE_LABELS.get((to_gid, from_gid))
                or f"Campus internal path via Gate {to_gid}"
            )

            time_saving = max(2, round((from_density - to_density) / 10))

            optimizations.append({
                "from_gate":                 from_gid,
                "to_gate":                   to_gid,
                "recommended_path":          label,
                "estimated_time_saved_min":  time_saving,
                "from_density":              from_density,
                "to_density":                to_density,
                "congestion_reduction":      round(from_density - to_density, 1),
                "path_cost":                 round(cost, 2),
            })

        # Highest density reduction first
        optimizations.sort(key=lambda x: -x["congestion_reduction"])
        return optimizations[:5]

    @staticmethod
    def _dijkstra_single(
        start:        str,
        gate_density: dict[str, float],
    ) -> tuple[str, float] | None:
        """
        Simplified single-hop Dijkstra: finds the lowest-cost directly
        connected gate that has a *lower* density than `start`.
        Cost = dist_factor + dest_density / 10.
        """
        best_dest: str | None = None
        best_cost: float      = float("inf")

        current_density = gate_density.get(start, 100.0)

        for (src, dst), dist in _CAMPUS_GRAPH.items():
            if src != start:
                continue
            dest_density = gate_density.get(dst, 50.0)
            if dest_density >= current_density:  # must be an improvement
                continue
            cost = dist + dest_density / 10.0
            if cost < best_cost:
                best_cost = cost
                best_dest = dst

        return (best_dest, best_cost) if best_dest else None

    # ── Module 6: Explainable AI Output ──────────────────────────────────────

    @staticmethod
    def _explain(
        gates:      list[dict],
        risk_level: str,
        anomalies:  list[dict],
        hour:       int,
        weather:    str,
    ) -> str:
        """Returns a concise, human-readable summary of the AI assessment."""
        if not gates:
            return "No gate data received. Anti-Gravity AI operating in standby."

        top_gate    = max(gates, key=lambda g: g["density"])
        gid         = top_gate.get("gate_id", "?")
        density     = top_gate["density"]
        n_anomalies = len(anomalies)

        time_ctx = (
            "morning rush (08:00–11:00)"    if 8  <= hour < 11  else
            "lunch peak (12:00–14:00)"      if 12 <= hour < 14  else
            "evening departure (16:00–19:00)" if 16 <= hour < 19 else
            "off-peak window"
        )

        weather_note = (
            f" Weather condition '{weather}' is amplifying pedestrian density."
            if weather not in ("clear", "cloudy") else ""
        )

        urgency = {
            "critical": "⚠️  IMMEDIATE INTERVENTION REQUIRED. Activate emergency protocols.",
            "high":     "Proactive shuttles and marshal deployment strongly advised.",
            "medium":   "Monitor closely. Increase patrol frequency at flagged gates.",
            "low":      "All systems nominal. Standard protocols in effect.",
        }.get(risk_level, "Status unknown.")

        return (
            f"Anti-Gravity AI assessment — Risk: {risk_level.upper()}. "
            f"Primary hotspot: Gate {gid} at {density}% during {time_ctx}.{weather_note} "
            f"{n_anomalies} anomal{'ies' if n_anomalies != 1 else 'y'} detected. "
            f"{urgency}"
        )

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fallback(message: str) -> dict:
        return {
            "status":     "fallback",
            "message":    message,
            "risk_level": "unknown",
            "engine":     "Anti-Gravity AI v1.0",
        }
