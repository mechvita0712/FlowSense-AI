"""
events.py — Event Management and Forecasting API
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_, or_

from ..models.event_model import Event, HistoricalPattern, EventImpact
from ..extensions import db
from ..services.enhanced_prediction_service import EnhancedPredictionService

events_bp = Blueprint("events", __name__)


@events_bp.route("/list", methods=["GET"])
def list_events():
    """
    Get list of events with optional filters.
    Query params: ?status=active&days_ahead=7
    """
    status = request.args.get('status')  # scheduled, active, completed
    days_ahead = int(request.args.get('days_ahead', 30))
    
    query = Event.query
    
    if status:
        query = query.filter_by(status=status)
    else:
        # By default, show only upcoming and active events
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(days=days_ahead)
        query = query.filter(
            and_(
                Event.start_time <= end_time,
                or_(
                    Event.status == 'scheduled',
                    Event.status == 'active'
                )
            )
        )
    
    events = query.order_by(Event.start_time).all()
    
    return jsonify({
        'count': len(events),
        'events': [e.to_dict() for e in events],
        'generated_at': datetime.now(timezone.utc).isoformat()
    })


@events_bp.route("/forecast", methods=["GET"])
def event_forecast():
    """
    Get detailed forecast for upcoming events including predicted impacts.
    Query params: ?days_ahead=7
    """
    days_ahead = int(request.args.get('days_ahead', 7))
    
    forecast = EnhancedPredictionService.get_event_forecast(days_ahead)
    
    return jsonify({
        'days_ahead': days_ahead,
        'event_count': len(forecast),
        'forecast': forecast,
        'generated_at': datetime.now(timezone.utc).isoformat()
    })


@events_bp.route("/current", methods=["GET"])
def current_events():
    """Get events happening right now."""
    now = datetime.now(timezone.utc)
    
    active = Event.query.filter(
        and_(
            Event.start_time <= now,
            Event.end_time >= now,
            Event.status == 'active'
        )
    ).all()
    
    # Also get events starting in next 2 hours
    upcoming_soon = Event.query.filter(
        and_(
            Event.start_time > now,
            Event.start_time <= now + timedelta(hours=2),
            Event.status == 'scheduled'
        )
    ).all()
    
    return jsonify({
        'active_now': [e.to_dict() for e in active],
        'starting_soon': [e.to_dict() for e in upcoming_soon],
        'total_active': len(active),
        'total_upcoming': len(upcoming_soon),
        'generated_at': now.isoformat()
    })


@events_bp.route("/impact/<event_id>", methods=["GET"])
def event_impact(event_id):
    """Get predicted impact for a specific event."""
    event = Event.query.get_or_404(event_id)
    
    # Get historical impact data for this event type
    impacts = EventImpact.query.filter_by(
        event_type=event.event_type
    ).all()
    
    impact_by_gate = {}
    for impact in impacts:
        gate_id = impact.gate_id
        if gate_id not in impact_by_gate:
            impact_by_gate[gate_id] = []
        impact_by_gate[gate_id].append(impact.to_dict())
    
    return jsonify({
        'event': event.to_dict(),
        'historical_impacts': impact_by_gate,
        'gates_count': len(impact_by_gate),
        'generated_at': datetime.now(timezone.utc).isoformat()
    })


@events_bp.route("/historical-patterns", methods=["GET"])
def historical_patterns():
    """
    Get historical crowd patterns.
    Query params: ?gate_id=A&day_of_week=0&is_event_day=false
    """
    gate_id = request.args.get('gate_id')
    day_of_week = request.args.get('day_of_week')
    is_event_day = request.args.get('is_event_day', 'false').lower() == 'true'
    
    query = HistoricalPattern.query.filter_by(is_event_day=is_event_day)
    
    if gate_id:
        query = query.filter_by(gate_id=gate_id)
    
    if day_of_week is not None:
        query = query.filter_by(day_of_week=int(day_of_week))
    
    patterns = query.order_by(
        HistoricalPattern.gate_id,
        HistoricalPattern.day_of_week,
        HistoricalPattern.hour
    ).all()
    
    # Group by gate for easier frontend consumption
    by_gate = {}
    for pattern in patterns:
        gate = pattern.gate_id
        if gate not in by_gate:
            by_gate[gate] = []
        by_gate[gate].append(pattern.to_dict())
    
    return jsonify({
        'total_patterns': len(patterns),
        'by_gate': by_gate,
        'is_event_day': is_event_day,
        'generated_at': datetime.now(timezone.utc).isoformat()
    })


@events_bp.route("/predict-with-events", methods=["GET"])
def predict_with_events():
    """
    Get enhanced predictions considering events.
    Query params: ?gate_id=A&hours_ahead=1
    """
    gate_id = request.args.get('gate_id', 'A')
    hours_ahead = int(request.args.get('hours_ahead', 1))
    
    prediction = EnhancedPredictionService.predict_crowd_with_events(gate_id, hours_ahead)
    
    return jsonify({
        'gate_id': gate_id,
        'hours_ahead': hours_ahead,
        'prediction': prediction,
        'generated_at': datetime.now(timezone.utc).isoformat()
    })


@events_bp.route("/shuttle-demand", methods=["GET"])
def shuttle_demand_forecast():
    """
    Get system-wide shuttle demand prediction.
    Query params: ?hours_ahead=1
    """
    hours_ahead = int(request.args.get('hours_ahead', 1))
    
    demand = EnhancedPredictionService.predict_shuttle_demand(hours_ahead)
    
    return jsonify({
        'demand': demand,
        'generated_at': datetime.now(timezone.utc).isoformat()
    })


@events_bp.route("/dashboard-summary", methods=["GET"])
def event_dashboard():
    """Get comprehensive dashboard data for events view."""
    now = datetime.now(timezone.utc)
    
    # Current events
    active = Event.query.filter_by(status='active').count()
    
    # Events today
    today_start = now.replace(hour=0, minute=0, second=0)
    today_end = today_start + timedelta(days=1)
    today_events = Event.query.filter(
        and_(
            Event.start_time >= today_start,
            Event.start_time < today_end
        )
    ).all()
    
    # Upcoming week
    week_end = now + timedelta(days=7)
    upcoming_week = Event.query.filter(
        and_(
            Event.start_time >= now,
            Event.start_time <= week_end,
            Event.status == 'scheduled'
        )
    ).count()
    
    # High impact events in next 48h
    high_impact_soon = Event.query.filter(
        and_(
            Event.start_time >= now,
            Event.start_time <= now + timedelta(hours=48),
            Event.impact_level.in_(['high', 'critical']),
            Event.status == 'scheduled'
        )
    ).all()
    
    # Get next major event
    next_major = Event.query.filter(
        and_(
            Event.start_time >= now,
            Event.status == 'scheduled'
        )
    ).order_by(Event.start_time).first()
    
    return jsonify({
        'active_now': active,
        'today_count': len(today_events),
        'today_events': [e.to_dict() for e in today_events],
        'upcoming_week_count': upcoming_week,
        'high_impact_alerts': [e.to_dict() for e in high_impact_soon],
        'next_major_event': next_major.to_dict() if next_major else None,
        'generated_at': now.isoformat()
    })
