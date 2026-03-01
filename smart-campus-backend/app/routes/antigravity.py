"""
antigravity.py — Anti-Gravity AI API Route
============================================
Endpoints:
  POST /api/antigravity/analyze        – Full AI analysis (predict + anomaly + routing + shuttles)
  GET  /api/antigravity/health         – Engine health check
  GET  /api/antigravity/capabilities   – Describe what the engine can do

These endpoints AUGMENT the existing /api/traffic/* routes.
No existing routes are modified.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

from ..services.antigravity_service import AntiGravityAI
from ..services.congestion_service import CongestionService
from ..models.traffic_model import GateStatus, ShuttleStatus

ag_bp = Blueprint("antigravity", __name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bad(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ─── Main Analysis Endpoint ────────────────────────────────────────────────────

@ag_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    Run the complete Anti-Gravity AI intelligence pipeline.

    Body (JSON):
    {
      "timestamp":   "2026-02-24T16:10:00",         # optional, defaults to now
      "gates": [
        { "gate_id": "A", "density": 45, "entries": 210 },
        ...
      ],
      "shuttles": [
        { "id": "S1", "load_percent": 82, "status": "active" },
        ...
      ],
      "event_flags": [],                             # optional list of event labels
      "weather":     "clear",                        # optional: clear/rain/storm/fog/hot
      "mode":        "advisory"                      # optional: advisory (default) | autonomous
    }

    Returns:
    {
      "predictions":         [...],
      "anomalies":           [...],
      "risk_level":          "critical|high|medium|low",
      "shuttle_strategy":    [...],
      "route_optimizations": [...],
      "explanation":         "...",
      "mode":                "advisory",
      "generated_at":        "ISO8601",
      "engine":              "Anti-Gravity AI v1.0"
    }

    On failure (input issues / model error):
    {
      "status":     "fallback",
      "message":    "...",
      "risk_level": "unknown"
    }
    """
    body = request.get_json(silent=True)
    if not body:
        return _bad("Request body must be valid JSON.")

    mode = str(body.get("mode", "advisory")).lower()
    if mode not in ("advisory", "autonomous"):
        mode = "advisory"

    # If gates not provided in body, auto-fetch from DB / seed data
    if not body.get("gates"):
        try:
            db_gates = GateStatus.query.all()
            gates = [g.to_dict() for g in db_gates] if db_gates else CongestionService.seed_gate_data()
            body["gates"] = gates
        except Exception:
            body["gates"] = CongestionService.seed_gate_data()

    # If shuttles not provided, auto-fetch from DB / seed data
    if not body.get("shuttles"):
        try:
            db_shuttles = ShuttleStatus.query.all()
            shuttles = []
            if db_shuttles:
                for s in db_shuttles:
                    d = s.to_dict()
                    cap = max(d.get("capacity", 45), 1)
                    d["load_percent"] = round(d.get("load", 0) / cap * 100, 1)
                    shuttles.append(d)
            else:
                raw = CongestionService.seed_shuttle_data()
                for s in raw:
                    cap = max(s.get("capacity", 45), 1)
                    s["load_percent"] = round(s.get("load", 0) / cap * 100, 1)
                    s["id"] = s.get("shuttle_id", s.get("id", "?"))
                    shuttles.append(s)
            body["shuttles"] = shuttles
        except Exception:
            body["shuttles"] = []

    result = AntiGravityAI.analyze(body, mode=mode)
    return jsonify(result)


# ─── Live Analysis (pulls current DB state automatically) ─────────────────────

@ag_bp.route("/live", methods=["GET"])
def live_analysis():
    """
    Convenience endpoint — runs Anti-Gravity AI against the CURRENT live data
    from the database without requiring a request body.

    Query params:
      ?mode=advisory      (default)
      ?mode=autonomous
      ?weather=clear      (optional weather modifier)
    """
    mode    = request.args.get("mode", "advisory")
    weather = request.args.get("weather", "clear")

    try:
        db_gates    = GateStatus.query.all()
        gates       = [g.to_dict() for g in db_gates] if db_gates else CongestionService.seed_gate_data()

        db_shuttles = ShuttleStatus.query.all()
        shuttles    = []
        if db_shuttles:
            for s in db_shuttles:
                d   = s.to_dict()
                cap = max(d.get("capacity", 45), 1)
                d["load_percent"] = round(d.get("load", 0) / cap * 100, 1)
                shuttles.append(d)
        else:
            raw = CongestionService.seed_shuttle_data()
            for s in raw:
                cap = max(s.get("capacity", 45), 1)
                s["load_percent"] = round(s.get("load", 0) / cap * 100, 1)
                s["id"] = s.get("shuttle_id", s.get("id", "?"))
                shuttles.append(s)
    except Exception:
        gates    = CongestionService.seed_gate_data()
        shuttles = []

    payload = {
        "timestamp":   _utcnow(),
        "gates":       gates,
        "shuttles":    shuttles,
        "weather":     weather,
        "event_flags": [],
    }

    result = AntiGravityAI.analyze(payload, mode=mode)
    return jsonify(result)


# ─── Health Check ─────────────────────────────────────────────────────────────

@ag_bp.route("/health", methods=["GET"])
def health():
    """Quick liveness probe for the Anti-Gravity AI engine."""
    # Run a minimal self-test
    test_payload = {
        "gates":    [{"gate_id": "TEST", "density": 50, "entries": 100}],
        "shuttles": [],
        "weather":  "clear",
    }
    result = AntiGravityAI.analyze(test_payload)
    engine_ok = "risk_level" in result and result.get("engine") == "Anti-Gravity AI v1.0"

    return jsonify({
        "status":       "ok" if engine_ok else "degraded",
        "engine":       "Anti-Gravity AI v1.0",
        "self_test":    "passed" if engine_ok else "failed",
        "generated_at": _utcnow(),
    }), (200 if engine_ok else 503)


# ─── Capabilities Manifest ────────────────────────────────────────────────────

@ag_bp.route("/capabilities", methods=["GET"])
def capabilities():
    """Returns a description of all Anti-Gravity AI capabilities and endpoints."""
    return jsonify({
        "engine":  "Anti-Gravity AI v1.0",
        "integration": "SmartCampus AI — Mobility Intelligence Platform v2.1",
        "modes":   ["advisory", "autonomous"],
        "modules": {
            "adaptive_prediction": {
                "description": "Next-hour density forecast per gate using tri-modal Gaussian with weather and event amplifiers.",
                "formula":     "0.5×current + 0.3×trend + 0.2×time_peak × weather_mod × event_amp",
                "output":      ["next_hour_density", "confidence", "trend"],
            },
            "anomaly_detection": {
                "description": "Flags statistical outliers (>2σ), extreme spikes (≥85%), and shuttle overloads (≥90%).",
                "types":       ["statistical_outlier", "extreme_density_spike", "shuttle_overload", "shuttle_high_load"],
            },
            "shuttle_optimizer": {
                "description": "Dynamic shuttle fleet control using three priority rules.",
                "rules": [
                    "Activate standby shuttle if gate ≥85% and standby available",
                    "Redistribute fleet if ≥2 gates at ≥80%",
                    "Reroute shuttle if load ≥90% to lowest-density gate",
                ],
            },
            "route_optimizer": {
                "description": "Graph-based Dijkstra path finder across campus gate topology.",
                "algorithm":   "Dijkstra (edge cost = distance_factor + dest_density / 10)",
                "output":      ["from_gate", "to_gate", "path", "time_saved_min", "congestion_reduction"],
            },
            "risk_classifier": {
                "description": "System-wide risk level using multi-gate and total-entry thresholds.",
                "levels": {
                    "critical": "≥2 gates at ≥85%  OR  total entries > 2000",
                    "high":     "1 gate at ≥85%  OR  ≥3 gates at ≥70%",
                    "medium":   "≥1 gate at ≥60%",
                    "low":      "All gates below 60%",
                },
            },
            "explainable_ai": {
                "description": "Plain-language summary combining risk, hotspot, time context, and weather context.",
            },
        },
        "endpoints": {
            "POST /api/antigravity/analyze":      "Full AI pipeline with custom payload",
            "GET  /api/antigravity/live":          "Full AI pipeline using live DB state",
            "GET  /api/antigravity/health":        "Engine health and self-test",
            "GET  /api/antigravity/capabilities":  "This manifest",
        },
        "failsafe": "All errors caught. Always returns valid JSON. Never crashes backend.",
        "performance_target": "< 300ms",
        "generated_at": _utcnow(),
    })
