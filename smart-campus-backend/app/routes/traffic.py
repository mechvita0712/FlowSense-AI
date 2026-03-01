"""
traffic.py — Campus Traffic & Congestion API
=============================================
Endpoints:
  POST /api/traffic/add             – Ingest a traffic data point
  GET  /api/traffic/all             – Retrieve all data (with optional filters)
  GET  /api/traffic/congestion      – Rule-based congestion alerts
  GET  /api/traffic/gates           – Per-gate live stats
  POST /api/traffic/predict         – AI-powered congestion prediction
  GET  /api/traffic/routes          – Smart route recommendations
  GET  /api/traffic/shuttles        – Shuttle fleet status
  POST /api/traffic/shuttles/update – Update a shuttle's status/load
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta

from ..models.traffic_model import TrafficEntry, GateStatus, ShuttleStatus
from ..extensions import db, socketio
from ..services.congestion_service import CongestionService
from ..services.ai_service import AIService
from ..services.enhanced_prediction_service import EnhancedPredictionService

traffic_bp = Blueprint("traffic", __name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bad(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


def _validate_api_key():
    """Validate API key from request headers."""
    api_key = request.headers.get('X-API-Key')
    expected_key = current_app.config.get('API_KEY')
    
    # If no API key is configured, allow all requests (development mode)
    if not expected_key:
        return True
    
    if not api_key:
        return jsonify({"error": "Missing X-API-Key header"}), 401
    
    if api_key != expected_key:
        return jsonify({"error": "Invalid API key"}), 403
    
    return True


# ─── Traffic Data ─────────────────────────────────────────────────────────────

@traffic_bp.route("/add", methods=["POST"])
def add_traffic():
    """
    Ingest a crowd / traffic data point from a sensor, gate scanner, or app.
    Requires X-API-Key header for authentication.

    Body (JSON):
      {
        "location": "Gate A",
        "count":    250,
        "gate_id":  "A",           # optional
        "source":   "sensor"       # optional: sensor | manual | app
      }
    """
    # Validate API key
    validation_result = _validate_api_key()
    if validation_result is not True:
        return validation_result
    
    data = request.get_json(silent=True)
    if not data:
        return _bad("Request body must be valid JSON")

    location = data.get("location", "").strip()
    count = data.get("count")

    if not location:
        return _bad("'location' is required")
    if count is None or not isinstance(count, (int, float)) or count < 0:
        return _bad("'count' must be a non-negative number")

    entry = TrafficEntry(
        location=location,
        count=int(count),
        gate_id=data.get("gate_id", ""),
        source=data.get("source", "manual"),
        timestamp=datetime.now(timezone.utc),
    )
    db.session.add(entry)

    # ── Update live GateStatus ──
    gate_id_val = data.get("gate_id")
    if gate_id_val:
        gate_status = GateStatus.query.filter_by(gate_id=gate_id_val).first()
        
        # Get capacity (per-gate, global, or default)
        if gate_status:
            if gate_status.use_global_capacity:
                capacity = current_app.config.get('DEFAULT_GLOBAL_CAPACITY', 50)
            else:
                capacity = gate_status.max_capacity
        else:
            # Create new gate with default capacity
            capacity = current_app.config.get('DEFAULT_GLOBAL_CAPACITY', 50)
            gate_status = GateStatus(
                gate_id=gate_id_val,
                name=f"Gate {gate_id_val}",
                location=location,
                density=0.0,
                entries=int(count),
                max_capacity=capacity,
                use_global_capacity=True,
            )
            db.session.add(gate_status)
        
        # Calculate density based on capacity (cap at 99.9%)
        calculated_density = min(99.9, (int(count) / capacity) * 100)
        gate_status.density = calculated_density
        gate_status.entries = int(count)
        gate_status.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    
    # ── Emit real-time WebSocket updates ──
    if gate_id_val and gate_status:
        # Emit crowd update
        socketio.emit('crowd_update', {
            'gate_id': gate_id_val,
            'count': int(count),
            'density': round(calculated_density, 1),
            'capacity': capacity,
            'status': 'FULL' if calculated_density >= 100 else 'WARNING' if calculated_density >= 70 else 'NORMAL',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, namespace='/ws/traffic')
        
        # Check if gate is full and trigger redirect alert
        if calculated_density >= 100:
            # Find alternative gate with lowest density
            all_gates = GateStatus.query.filter(GateStatus.gate_id != gate_id_val).order_by(GateStatus.density).all()
            redirect_to = all_gates[0].gate_id if all_gates else None
            
            if redirect_to:
                socketio.emit('gate_full_alert', {
                    'gate_id': gate_id_val,
                    'redirect_to': redirect_to,
                    'message': f'Gate {gate_id_val} is FULL. Please redirect to Gate {redirect_to}',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }, namespace='/ws/traffic')

    return jsonify({
        "message": "Traffic data added successfully",
        "entry_id": entry.id,
        "timestamp": entry.timestamp.isoformat(),
    }), 201


@traffic_bp.route("/all", methods=["GET"])
def get_all():
    """
    Return all stored traffic entries.
    Query params: ?location=Gate+A  ?limit=50  ?since=ISO8601-datetime
    """
    query = TrafficEntry.query

    location_filter = request.args.get("location")
    if location_filter:
        query = query.filter(TrafficEntry.location.ilike(f"%{location_filter}%"))

    since = request.args.get("since")
    if since:
        try:
            dt = datetime.fromisoformat(since)
            query = query.filter(TrafficEntry.timestamp >= dt)
        except ValueError:
            return _bad("'since' must be an ISO-8601 datetime string")

    limit = min(int(request.args.get("limit", 200)), 1000)
    entries = query.order_by(TrafficEntry.timestamp.desc()).limit(limit).all()

    return jsonify({
        "count": len(entries),
        "data": [e.to_dict() for e in entries],
    })


# ─── Congestion Analysis ──────────────────────────────────────────────────────

@traffic_bp.route("/congestion", methods=["GET"])
def check_congestion():
    """
    Rule-based congestion check against configurable thresholds.
    Returns alert list with severity level for each congested location.
    """
    threshold_warn = current_app.config.get("AI_CONGESTION_THRESHOLD", 200)
    threshold_crit = current_app.config.get("AI_CRITICAL_THRESHOLD", 350)

    entries = TrafficEntry.query.order_by(TrafficEntry.timestamp.desc()).limit(500).all()
    alerts = CongestionService.evaluate(entries, threshold_warn, threshold_crit)

    return jsonify({
        "generated_at": _utcnow(),
        "thresholds": {"warning": threshold_warn, "critical": threshold_crit},
        "alert_count": len(alerts),
        "alerts": alerts,
    })


# ─── Gate Status ──────────────────────────────────────────────────────────────

@traffic_bp.route("/gates", methods=["GET"])
def get_gates():
    """
    Return the current congestion status and 1-hour ML forecast for every gate.
    Now uses enhanced prediction with event intelligence.
    """
    gates = GateStatus.query.all()
    if not gates:
        # Return synthetic seed data when DB is empty (demo / first-run)
        gates_data = CongestionService.seed_gate_data()
    else:
        gates_data = [g.to_dict() for g in gates]

    # Attach enhanced AI predictions with event awareness
    for g in gates_data:
        # Get enhanced prediction considering events
        enhanced_pred = EnhancedPredictionService.predict_crowd_with_events(
            gate_id=g["gate_id"],
            hours_ahead=1
        )
        
        g["predicted_next_hour"] = enhanced_pred['predicted_density']
        g["prediction_confidence"] = enhanced_pred['confidence']
        g["prediction_factors"] = enhanced_pred['factors']
        g["active_events"] = enhanced_pred['active_events']
        g["level"] = CongestionService.level_of(g["density"])
        g["ai_recommendation"] = enhanced_pred['recommendation']

    return jsonify({
        "generated_at": _utcnow(),
        "gates": gates_data,
    })


@traffic_bp.route("/crowd-status", methods=["GET"])
def get_crowd_status():
    """
    Return real-time crowd status for a specific gate or overall system.
    Query params: ?gate_id=A
    
    Returns:
    {
        "current_count": number,
        "max_capacity": number,
        "status": "NORMAL" | "WARNING" | "FULL",
        "redirect_gate": "Gate B" (if status is FULL)
    }
    """
    gate_id = request.args.get('gate_id')
    
    if gate_id:
        # Single gate status
        gate = GateStatus.query.filter_by(gate_id=gate_id).first()
        if not gate:
            return jsonify({'error': f'Gate {gate_id} not found'}), 404
        
        # Determine capacity
        if gate.use_global_capacity:
            capacity = current_app.config.get('DEFAULT_GLOBAL_CAPACITY', 50)
        else:
            capacity = gate.max_capacity
        
        # Determine status
        if gate.density >= 100:
            status = 'FULL'
        elif gate.density >= 70:
            status = 'WARNING'
        else:
            status = 'NORMAL'
        
        # Find redirect gate if full
        redirect_gate = None
        if status == 'FULL':
            # Find gate with lowest density
            all_gates = GateStatus.query.filter(GateStatus.gate_id != gate_id).order_by(GateStatus.density).all()
            if all_gates:
                redirect_gate = f"Gate {all_gates[0].gate_id}"
        
        return jsonify({
            'gate_id': gate_id,
            'current_count': gate.entries,
            'max_capacity': capacity,
            'density': round(gate.density, 1),
            'status': status,
            'redirect_gate': redirect_gate,
            'timestamp': gate.updated_at.isoformat() if gate.updated_at else None
        }), 200
    else:
        # Overall system status
        gates = GateStatus.query.all()
        if not gates:
            return jsonify({'error': 'No gate data available'}), 404
        
        total_count = sum(g.entries for g in gates)
        total_capacity = sum(
            current_app.config.get('DEFAULT_GLOBAL_CAPACITY', 50) if g.use_global_capacity else g.max_capacity
            for g in gates
        )
        avg_density = sum(g.density for g in gates) / len(gates)
        
        # Overall status based on average density
        if avg_density >= 100:
            status = 'FULL'
        elif avg_density >= 70:
            status = 'WARNING'
        else:
            status = 'NORMAL'
        
        # Find best redirect gate (lowest density)
        best_gate = min(gates, key=lambda g: g.density)
        
        return jsonify({
            'system_status': status,
            'total_count': total_count,
            'total_capacity': total_capacity,
            'average_density': round(avg_density, 1),
            'gates_count': len(gates),
            'redirect_gate': f"Gate {best_gate.gate_id}" if status == 'FULL' else None,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200


@traffic_bp.route("/update-capacity", methods=["POST"])
def update_capacity():
    """
    Update max capacity for a gate (convenience endpoint, also available in /api/admin).
    
    POST /api/traffic/update-capacity
    {
        "gate_id": "A",
        "capacity": 40
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return _bad("Request body must be valid JSON")
    
    gate_id = data.get('gate_id')
    capacity = data.get('capacity')
    
    if not gate_id:
        return _bad("'gate_id' is required")
    if not capacity or not isinstance(capacity, int) or capacity < 1:
        return _bad("'capacity' must be a positive integer")
    
    gate = GateStatus.query.filter_by(gate_id=gate_id).first()
    if not gate:
        return jsonify({'error': f'Gate {gate_id} not found'}), 404
    
    gate.max_capacity = capacity
    gate.use_global_capacity = False
    gate.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    
    # Emit WebSocket update
    socketio.emit('capacity_updated', {
        'gate_id': gate_id,
        'capacity': capacity
    }, namespace='/ws/traffic')
    
    return jsonify({
        'success': True,
        'gate_id': gate_id,
        'capacity': capacity,
        'message': f'Gate {gate_id} capacity updated to {capacity}'
    }), 200


# ─── AI Prediction ────────────────────────────────────────────────────────────

@traffic_bp.route("/predict", methods=["POST"])
def predict_congestion():
    """
    Body (JSON):
      {
        "traffic_data": [
          {"location": "Gate A", "count": 250},
          ...
        ],
        "use_llm": false   # set true to enrich via LLM prompt (future)
      }

    Returns structured AI insights:
      hotspots, recommendations, risk_level, shuttle_strategy
    """
    body = request.get_json(silent=True)
    if not body:
        return _bad("Request body must be valid JSON")

    traffic_data = body.get("traffic_data", [])
    if not traffic_data:
        return _bad("'traffic_data' array is required")

    result = AIService.analyse_traffic(traffic_data)
    return jsonify(result)


# ─── Routes / Nudges ─────────────────────────────────────────────────────────

@traffic_bp.route("/routes", methods=["GET"])
def get_routes():
    """
    Return AI-generated smart route recommendations based on current gate load.
    """
    gates = GateStatus.query.all()
    gates_data = [g.to_dict() for g in gates] if gates else CongestionService.seed_gate_data()
    recommendations = AIService.recommend_routes(gates_data)
    return jsonify({
        "generated_at": _utcnow(),
        "recommendations": recommendations,
    })


# ─── Shuttles ────────────────────────────────────────────────────────────────

@traffic_bp.route("/shuttles", methods=["GET"])
def get_shuttles():
    """Return current shuttle fleet status."""
    shuttles = ShuttleStatus.query.all()
    if not shuttles:
        fleet = CongestionService.seed_shuttle_data()
    else:
        fleet = [s.to_dict() for s in shuttles]

    for s in fleet:
        s["load_pct"] = round(s["load"] / max(s["capacity"], 1) * 100, 1)
        s["status_level"] = (
            "critical" if s["load_pct"] >= 90 else
            "warning"  if s["load_pct"] >= 70 else
            "normal"
        )

    return jsonify({
        "generated_at": _utcnow(),
        "shuttle_count": len(fleet),
        "fleet": fleet,
    })


@traffic_bp.route("/shuttles/update", methods=["POST"])
def update_shuttle():
    """
    Body (JSON): { "shuttle_id": "S1", "load": 38, "status": "active" }
    """
    body = request.get_json(silent=True)
    if not body:
        return _bad("Request body must be valid JSON")

    shuttle_id = body.get("shuttle_id")
    if not shuttle_id:
        return _bad("'shuttle_id' is required")

    shuttle = ShuttleStatus.query.filter_by(shuttle_id=shuttle_id).first()
    if not shuttle:
        return _bad(f"Shuttle '{shuttle_id}' not found", 404)

    if "load" in body:
        shuttle.load = int(body["load"])
    if "status" in body:
        shuttle.status = body["status"]
    shuttle.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"message": "Shuttle updated", "shuttle": shuttle.to_dict()})


# ─── Dashboard Summary ────────────────────────────────────────────────────────

@traffic_bp.route("/dashboard/summary", methods=["GET"])
def dashboard_summary():
    """
    Aggregate KPI summary for the frontend dashboard.
    GET /api/traffic/dashboard/summary

    Response:
    {
      "total_people":    number,
      "avg_congestion":  number,
      "active_shuttles": number,
      "active_alerts":   number,
      "ai_confidence":   number
    }
    """
    gates = GateStatus.query.all()
    gates_data = [g.to_dict() for g in gates] if gates else CongestionService.seed_gate_data()

    total_people = sum(int(g.get("entries", 0)) for g in gates_data)
    avg_congestion = (
        round(sum(g.get("density", 0) for g in gates_data) / len(gates_data), 1)
        if gates_data else 0
    )

    shuttles = ShuttleStatus.query.all()
    if shuttles:
        active_shuttles = sum(1 for s in shuttles if s.status == "active")
    else:
        seed = CongestionService.seed_shuttle_data()
        active_shuttles = sum(1 for s in seed if s["status"] == "active")

    # Alert count from congestion evaluation
    entries = TrafficEntry.query.order_by(TrafficEntry.timestamp.desc()).limit(500).all()
    threshold_warn = current_app.config.get("AI_CONGESTION_THRESHOLD", 200)
    threshold_crit = current_app.config.get("AI_CRITICAL_THRESHOLD", 350)
    alerts = CongestionService.evaluate(entries, threshold_warn, threshold_crit)

    return jsonify({
        "total_people":    total_people,
        "avg_congestion":  avg_congestion,
        "active_shuttles": active_shuttles,
        "active_alerts":   len(alerts),
        "ai_confidence":   92.0,
        "generated_at":    _utcnow(),
    })


# ─── Congestion Forecast ──────────────────────────────────────────────────────

@traffic_bp.route("/forecast", methods=["GET"])
def get_forecast():
    """
    Return a 6-hour ahead congestion forecast in 30-minute slots.
    GET /api/traffic/forecast

    Response:
    {
      "peak_time":     "HH:MM",
      "predicted_max": number,
      "confidence":    number,
      "hourly":        [number, ...]  # 12 values, each 30 min apart
    }
    """
    gates = GateStatus.query.all()
    gates_data = [g.to_dict() for g in gates] if gates else CongestionService.seed_gate_data()

    avg_density = (
        sum(g.get("density", 0) for g in gates_data) / len(gates_data)
        if gates_data else 0
    )

    now = datetime.now()
    hourly = []
    for i in range(12):
        predicted = AIService.predict_congestion(current=avg_density, hour_offset=i * 0.5)
        hourly.append(round(predicted, 1))

    predicted_max = max(hourly) if hourly else 0
    peak_idx = hourly.index(predicted_max) if hourly else 0
    peak_dt = datetime(now.year, now.month, now.day, now.hour, now.minute)
    from datetime import timedelta
    peak_dt = peak_dt + timedelta(minutes=peak_idx * 30)
    peak_time = peak_dt.strftime("%H:%M")

    return jsonify({
        "peak_time":     peak_time,
        "predicted_max": predicted_max,
        "confidence":    92.0,
        "hourly":        hourly,
        "generated_at":  _utcnow(),
    })


# ─── Dispatch Recommendations ─────────────────────────────────────────────────

@traffic_bp.route("/recommendations", methods=["GET"])
def get_recommendations():
    """
    Return AI-generated dispatch / reroute / alert recommendations.
    GET /api/traffic/recommendations

    Response:
    [
      {
        "type":        "dispatch | reroute | alert",
        "title":       string,
        "description": string,
        "priority":    "low | medium | high"
      }
    ]
    """
    gates = GateStatus.query.all()
    gates_data = [g.to_dict() for g in gates] if gates else CongestionService.seed_gate_data()

    shuttles = ShuttleStatus.query.all()
    fleet = [s.to_dict() for s in shuttles] if shuttles else CongestionService.seed_shuttle_data()

    recs = []

    # Gate-level reroute recommendations
    for g in sorted(gates_data, key=lambda x: -x.get("density", 0)):
        density = g.get("density", 0)
        name = g.get("name", f"Gate {g.get('gate_id', '?')}")
        alt = {"A": "B", "B": "E", "C": "B", "D": "E", "E": "D", "F": "B"}.get(
            g.get("gate_id", ""), "B"
        )
        if density >= 80:
            recs.append({
                "type":        "reroute",
                "title":       f"Redirect from {name}",
                "description": f"{name} at {density:.0f}% capacity. Redirect pedestrians to Gate {alt}.",
                "priority":    "high",
            })
        elif density >= 60:
            recs.append({
                "type":        "alert",
                "title":       f"Monitor {name}",
                "description": f"{name} at {density:.0f}% — rising. Increase marshal presence.",
                "priority":    "medium",
            })

    # Shuttle-level dispatch recommendations
    for s in fleet:
        cap = max(s.get("capacity", 45), 1)
        load_pct = round(s.get("load", 0) / cap * 100, 1)
        sid = s.get("shuttle_id", s.get("name", "Shuttle"))
        route = s.get("route", "")
        if s.get("status") == "standby":
            recs.append({
                "type":        "dispatch",
                "title":       f"Deploy {sid}",
                "description": f"{sid} is on standby. Consider deploying on {route} route.",
                "priority":    "medium",
            })
        elif s.get("status") == "active" and load_pct >= 90:
            recs.append({
                "type":        "dispatch",
                "title":       f"Overload: {sid}",
                "description": f"{sid} at {load_pct:.0f}% load on {route}. Dispatch backup shuttle.",
                "priority":    "high",
            })

    # Limit to top 6 by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 9))

    return jsonify(recs[:6])


# ─── Events Feed ───────────────────────────────────────────────────────────────

@traffic_bp.route("/events", methods=["GET"])
def get_events():
    """
    Returns an event timeline and event-impact summary derived from current load.
    GET /api/traffic/events
    """
    now = datetime.now()
    gates = GateStatus.query.all()
    gates_data = [g.to_dict() for g in gates] if gates else CongestionService.seed_gate_data()
    avg_density = (
        sum(g.get("density", 0) for g in gates_data) / len(gates_data)
        if gates_data else 0
    )

    base = [
        ("Morning Assembly", "Main Auditorium", 9, 0, 700),
        ("Guest Lecture", "Lecture Hall B3", 11, 30, 220),
        ("Lunch Break", "Cafeteria - Gate F", 13, 0, 1800),
        ("Sports Practice", "Sports Complex - Gate C", 16, 0, 500),
        ("Evening Exit Flow", "All Gates", 17, 30, 2200),
    ]

    events = []
    for title, location, hh, mm, attendees in base:
        dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        scaled_attendees = int(attendees * (0.8 + min(0.6, avg_density / 140)))
        impact = "high" if scaled_attendees >= 1200 else "medium" if scaled_attendees >= 450 else "low"
        events.append({
            "time": dt.strftime("%H:%M"),
            "title": title,
            "location": location,
            "attendees": scaled_attendees,
            "impact": impact,
        })

    # historical hourly impact from latest entries
    entries = TrafficEntry.query.order_by(TrafficEntry.timestamp.desc()).limit(1000).all()
    buckets = {}
    for e in entries:
        ts = e.timestamp
        key = ts.strftime("%H:00")
        buckets[key] = buckets.get(key, 0) + int(e.count)

    history_labels = []
    history_values = []
    for i in range(6, -1, -1):
        h = (now - timedelta(hours=i)).strftime("%H:00")
        v = buckets.get(h, 0)
        # normalize for 0..100 chart
        score = 95 if v >= 350 else 70 if v >= 220 else 45 if v >= 120 else 20 if v > 0 else 8
        history_labels.append(h)
        history_values.append(score)

    return jsonify({
        "generated_at": _utcnow(),
        "events": events,
        "history": {
            "labels": history_labels,
            "impact_scores": history_values,
        },
    })


# ─── Analytics Feed ───────────────────────────────────────────────────────────

@traffic_bp.route("/analytics", methods=["GET"])
def get_analytics():
    """
    Returns analytics payload for charts/stats/metrics.
    GET /api/traffic/analytics
    """
    summary = dashboard_summary().json
    entries = TrafficEntry.query.order_by(TrafficEntry.timestamp.desc()).limit(5000).all()
    shuttles = ShuttleStatus.query.all()

    now = datetime.now()
    week_labels = []
    gate_series = []
    shuttle_series = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i))
        week_labels.append(day.strftime("%a"))
        day_entries = [e.count for e in entries if e.timestamp.date() == day.date()]
        day_avg = round(sum(day_entries) / len(day_entries), 1) if day_entries else 0
        gate_series.append(min(100, round(day_avg / 4)))
        if shuttles:
            load_pct = round(sum((s.load / max(s.capacity, 1)) * 100 for s in shuttles) / len(shuttles), 1)
        else:
            load_pct = 0
        shuttle_series.append(load_pct)

    # Peak distribution from hour buckets
    hour_counts = {h: 0 for h in range(24)}
    for e in entries:
        hour_counts[e.timestamp.hour] += int(e.count)
    morning = sum(hour_counts[h] for h in range(8, 11))
    lunch = sum(hour_counts[h] for h in range(12, 15))
    evening = sum(hour_counts[h] for h in range(16, 19))
    other = max(0, sum(hour_counts.values()) - morning - lunch - evening)

    routes = AIService.recommend_routes(
        [g.to_dict() for g in GateStatus.query.all()] or CongestionService.seed_gate_data()
    )
    avg_route_score = (
        round(sum(max(60, 100 - round(float(r.get("current_density", 0)) * 0.4)) for r in routes) / len(routes), 1)
        if routes else 0
    )

    return jsonify({
        "generated_at": _utcnow(),
        "weekly_pattern": {
            "labels": week_labels,
            "gate_traffic": gate_series,
            "shuttle_usage": shuttle_series,
        },
        "peak_distribution": {
            "labels": ["8-10am", "12-2pm", "4-6pm", "Other"],
            "values": [morning, lunch, evening, other],
        },
        "impact_stats": [
            {"val": f"{summary.get('avg_congestion', 0)}%", "label": "Avg Congestion", "change": "Live backend"},
            {"val": str(len(routes)), "label": "Route Nudges", "change": "Current snapshot"},
            {"val": str(summary.get("active_shuttles", 0)), "label": "Active Shuttles", "change": "Current fleet"},
            {"val": str(summary.get("active_alerts", 0)), "label": "Active Alerts", "change": "Live backend"},
        ],
        "ml_metrics": [
            {"name": "Mode", "val": "Live Backend", "detail": "Data source"},
            {"name": "AI Confidence", "val": f"{summary.get('ai_confidence', 0)}%", "detail": "Backend summary"},
            {"name": "Total People", "val": str(summary.get("total_people", 0)), "detail": "Current total count"},
            {"name": "Gate Count", "val": str(len([g for g in GateStatus.query.all()] or CongestionService.seed_gate_data())), "detail": "Tracked gates"},
            {"name": "Shuttle Count", "val": str(len(shuttles) if shuttles else len(CongestionService.seed_shuttle_data())), "detail": "Current fleet"},
            {"name": "Routes", "val": str(len(routes)), "detail": "Active recommendations"},
            {"name": "Avg Route Score", "val": str(avg_route_score), "detail": "Density-adjusted score"},
            {"name": "Last Refresh", "val": now.strftime("%H:%M"), "detail": "Server time"},
        ],
    })
