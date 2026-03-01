"""
ai_service.py — AI / ML logic for the Smart Campus Mobility System
===================================================================
Implements:
  1. Simulate ML crowd-density prediction (bimodal Gaussian — no external deps)
  2. Structured AI traffic analysis with the standard LLM prompt format
  3. Smart route recommendation engine

No external AI API key is required by default — the model runs fully locally
using the Gaussian simulation. To plug in a real LLM (OpenAI / Gemini), just
fill in _call_llm() below and set USE_LLM=true in your .env.
"""

from __future__ import annotations

import json
import math
import os
import random
from datetime import datetime, timezone
from typing import Any


class AIService:
    """Stateless service exposing all AI/ML methods as class methods."""

    # ── Congestion Prediction (Simulated ML) ──────────────────────────────────

    @classmethod
    def predict_congestion(cls, current: float, hour_offset: float = 1.0) -> float:
        """
        Simulated ML model using a bimodal Gaussian (morning + evening peaks)
        with small Gaussian noise.  Replace with a real sklearn / ONNX model
        in production.

        Args:
            current:     current density reading (0–100 %).
            hour_offset: how many hours ahead to predict.

        Returns:
            Predicted density (0–99.9 %).
        """
        now_h = datetime.now(timezone.utc).hour + hour_offset
        morning_peak = cls._gaussian(now_h, mean=9.0,  sigma=1.5)
        evening_peak = cls._gaussian(now_h, mean=17.0, sigma=1.8)
        lunch_peak   = cls._gaussian(now_h, mean=13.0, sigma=0.8)

        seasonal = (morning_peak * 0.7 + evening_peak * 1.0 + lunch_peak * 0.6) * 60.0
        noise    = random.gauss(0, 2.5)

        predicted = current * 0.40 + seasonal + noise
        return round(min(99.9, max(5.0, predicted)), 1)

    @staticmethod
    def _gaussian(x: float, mean: float, sigma: float) -> float:
        return math.exp(-0.5 * ((x - mean) / sigma) ** 2)

    # ── Full Traffic Analysis (Structured AI Prompt Pattern) ─────────────────

    @classmethod
    def analyse_traffic(cls, traffic_data: list[dict]) -> dict:
        """
        Analyse a list of traffic data points and return structured insights.

        The method first tries to call a real LLM (if USE_LLM=true in .env),
        then falls back to the built-in rule-based engine.

        Returns JSON matching the schema:
            {
              "hotspots":        [...],
              "recommendations": [...],
              "risk_level":      "low|medium|high|critical",
              "shuttle_strategy": [...],
              "peak_patterns":   [...],
              "generated_at":    "ISO8601"
            }
        """
        use_llm = os.getenv("USE_LLM", "false").lower() == "true"

        if use_llm:
            result = cls._call_llm(traffic_data)
            if result:
                return result

        # ── Built-in rule-based fallback ─────────────────────────────────────
        return cls._rule_based_analysis(traffic_data)

    @classmethod
    def _rule_based_analysis(cls, traffic_data: list[dict]) -> dict:
        """
        Pure-Python analysis: identifies hotspots, assigns risk level,
        and drafts actionable recommendations — no AI API required.
        """
        hotspots:        list[dict] = []
        recommendations: list[str] = []
        shuttle_strategy: list[str] = []
        peak_patterns:    list[str] = []

        total_count = 0
        max_entry   = {"location": "N/A", "count": 0}

        for entry in traffic_data:
            loc   = entry.get("location", "Unknown")
            count = int(entry.get("count", 0))
            total_count += count

            if count > max_entry["count"]:
                max_entry = {"location": loc, "count": count}

            if count >= 350:
                hotspots.append({"location": loc, "count": count, "severity": "critical"})
                recommendations.append(
                    f"Immediately redirect crowd from {loc} to the nearest alternate gate."
                )
                shuttle_strategy.append(
                    f"Deploy emergency shuttle to {loc}. Reduce loop interval to ≤5 min."
                )
            elif count >= 200:
                hotspots.append({"location": loc, "count": count, "severity": "warning"})
                recommendations.append(
                    f"Increase marshal presence at {loc} and boost shuttle frequency."
                )
                shuttle_strategy.append(
                    f"Add one extra shuttle rotation via {loc}."
                )

        # Risk level
        critical_count = sum(1 for h in hotspots if h["severity"] == "critical")
        warning_count  = sum(1 for h in hotspots if h["severity"] == "warning")

        if critical_count >= 2 or total_count > 1500:
            risk_level = "critical"
        elif critical_count == 1 or warning_count >= 3:
            risk_level = "high"
        elif warning_count >= 1:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Generic recommendations
        if not recommendations:
            recommendations.append("Current traffic levels are within acceptable limits.")
            recommendations.append("Maintain standard shuttle schedule.")
        recommendations.append(
            "Send real-time route nudges via the mobile app to distribute pedestrian flow."
        )
        recommendations.append(
            "Use pre-emptive alerts 15 minutes before predicted peaks."
        )

        # Peak pattern heuristic
        now_h = datetime.now(timezone.utc).hour
        if 8 <= now_h < 11:
            peak_patterns.append("Morning rush currently active (8–11 AM).")
        elif 12 <= now_h < 14:
            peak_patterns.append("Lunch break congestion window (12–2 PM).")
        elif 16 <= now_h < 19:
            peak_patterns.append("Evening departure rush (4–7 PM).")
        else:
            peak_patterns.append("Off-peak period — congestion expected to stay low.")
        peak_patterns.append(
            f"Highest single location: {max_entry['location']} ({max_entry['count']} people)."
        )

        return {
            "hotspots":         hotspots,
            "recommendations":  recommendations,
            "risk_level":       risk_level,
            "shuttle_strategy": shuttle_strategy,
            "peak_patterns":    peak_patterns,
            "total_count":      total_count,
            "generated_at":     datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _call_llm(traffic_data: list[dict]) -> dict | None:
        """
        Send traffic data to an external LLM using the structured AI prompt.
        Set USE_LLM=true, LLM_PROVIDER=openai, and OPENAI_API_KEY in .env.

        ┌─────────────────────────────────────────────────────────────┐
        │  PROMPT TEMPLATE (see README for full documentation)        │
        │                                                             │
        │  You are an AI Smart Campus Traffic Analyst.                │
        │  Analyse the following campus traffic data: {traffic_data}  │
        │  Tasks:                                                     │
        │    1. Identify congestion hotspots.                         │
        │    2. Suggest shuttle re-routing strategies.                │
        │    3. Recommend safe-mobility nudges.                       │
        │    4. Predict possible peak time patterns.                  │
        │    5. Actionable recommendations for administration.        │
        │  Respond in structured JSON:                                │
        │    { "hotspots": [], "recommendations": [],                 │
        │      "risk_level": "", "shuttle_strategy": [],              │
        │      "peak_patterns": [] }                                  │
        └─────────────────────────────────────────────────────────────┘
        """
        provider = os.getenv("LLM_PROVIDER", "openai").lower()

        if provider == "openai":
            try:
                import openai  # pip install openai
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                prompt = (
                    "You are an AI Smart Campus Traffic Analyst.\n\n"
                    f"Analyse the following campus traffic data:\n{json.dumps(traffic_data, indent=2)}\n\n"
                    "Tasks:\n"
                    "1. Identify congestion hotspots.\n"
                    "2. Suggest shuttle re-routing strategies.\n"
                    "3. Recommend safe-mobility nudges.\n"
                    "4. Predict possible peak time patterns.\n"
                    "5. Provide actionable recommendations for campus administration.\n\n"
                    "Respond ONLY in valid JSON with keys: "
                    "hotspots, recommendations, risk_level, shuttle_strategy, peak_patterns."
                )
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                return json.loads(resp.choices[0].message.content)
            except Exception:
                return None  # Fall through to rule-based

        # Add more providers (Gemini, Claude, etc.) here
        return None

    # ── Route Recommendations ─────────────────────────────────────────────────

    @classmethod
    def recommend_routes(cls, gates_data: list[dict]) -> list[dict]:
        """
        Given current gate densities, return a prioritised list of
        smart route nudges users should receive.
        """
        route_map = {
            "A": {"from": "Main Entrance", "alt_gate": "B", "path": "Via inner academic corridor"},
            "B": {"from": "Academic Block", "alt_gate": "E", "path": "Via library east path"},
            "C": {"from": "Sports Complex", "alt_gate": "B", "path": "Via campus trail (shaded)"},
            "D": {"from": "Residential Block", "alt_gate": "E", "path": "Via cycle lane"},
            "E": {"from": "Library/Labs", "alt_gate": "D", "path": "Via science garden"},
            "F": {"from": "Admin/Cafeteria", "alt_gate": "B", "path": "Via east corridor"},
        }

        recs: list[dict] = []
        for g in sorted(gates_data, key=lambda x: -x.get("density", 0)):
            density  = g.get("density", 0)
            gate_id  = g.get("gate_id", "")
            info     = route_map.get(gate_id, {})
            if density < 60 or not info:
                continue
            savings = 5 + round((density - 60) / 10)  # heuristic: 1 min per 10% above 60
            recs.append({
                "gate_id":       gate_id,
                "from":          info["from"],
                "to":            f"Gate {info['alt_gate']}",
                "recommended_path": info["path"],
                "avoid":         f"Gate {gate_id} direct route",
                "time_saving_min": savings,
                "current_density": density,
                "priority":      "high" if density >= 80 else "medium",
            })

        return recs[:5]  # Return top 5 recommendations
