"""
event_model.py — Event and Historical Pattern Models
"""

from datetime import datetime, timezone
from ..extensions import db


class Event(db.Model):
    """
    Campus events that affect crowd patterns.
    """
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    event_type = db.Column(db.String(32), nullable=False)  # concert, sports, exam, festival, conference
    location = db.Column(db.String(128), nullable=True)
    expected_attendance = db.Column(db.Integer, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    impact_level = db.Column(db.String(16), nullable=False, default='medium')  # low, medium, high, critical
    status = db.Column(db.String(16), nullable=False, default='scheduled')  # scheduled, active, completed, cancelled
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "event_type": self.event_type,
            "location": self.location,
            "expected_attendance": self.expected_attendance,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "impact_level": self.impact_level,
            "status": self.status,
            "duration_hours": (self.end_time - self.start_time).total_seconds() / 3600 if self.end_time and self.start_time else 0
        }
    
    def __repr__(self) -> str:
        return f"<Event {self.name} type={self.event_type} impact={self.impact_level}>"


class HistoricalPattern(db.Model):
    """
    Historical crowd patterns for normal days - used for baseline predictions.
    """
    __tablename__ = "historical_patterns"

    id = db.Column(db.Integer, primary_key=True)
    gate_id = db.Column(db.String(8), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    hour = db.Column(db.Integer, nullable=False)  # 0-23
    average_count = db.Column(db.Float, nullable=False)
    peak_count = db.Column(db.Integer, nullable=False)
    min_count = db.Column(db.Integer, nullable=False)
    std_deviation = db.Column(db.Float, nullable=False, default=0.0)
    sample_size = db.Column(db.Integer, nullable=False, default=1)
    is_event_day = db.Column(db.Boolean, nullable=False, default=False)
    last_updated = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "gate_id": self.gate_id,
            "day_of_week": self.day_of_week,
            "hour": self.hour,
            "average_count": round(self.average_count, 2),
            "peak_count": self.peak_count,
            "min_count": self.min_count,
            "std_deviation": round(self.std_deviation, 2),
            "sample_size": self.sample_size,
            "is_event_day": self.is_event_day
        }
    
    def __repr__(self) -> str:
        return f"<HistoricalPattern gate={self.gate_id} day={self.day_of_week} hour={self.hour}>"


class EventImpact(db.Model):
    """
    Historical event impact data - how specific event types affected crowd patterns.
    """
    __tablename__ = "event_impacts"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    event_type = db.Column(db.String(32), nullable=False, index=True)
    gate_id = db.Column(db.String(8), nullable=False, index=True)
    time_offset_hours = db.Column(db.Integer, nullable=False)  # hours before/after event start (-2 to +6)
    crowd_multiplier = db.Column(db.Float, nullable=False, default=1.0)  # multiply baseline by this
    additional_count = db.Column(db.Integer, nullable=False, default=0)  # add this to baseline
    recorded_count = db.Column(db.Integer, nullable=False)
    baseline_count = db.Column(db.Integer, nullable=False)
    impact_level = db.Column(db.String(16), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "gate_id": self.gate_id,
            "time_offset_hours": self.time_offset_hours,
            "crowd_multiplier": round(self.crowd_multiplier, 2),
            "additional_count": self.additional_count,
            "recorded_count": self.recorded_count,
            "baseline_count": self.baseline_count,
            "impact_level": self.impact_level,
            "impact_percent": round(((self.recorded_count - self.baseline_count) / self.baseline_count * 100), 1) if self.baseline_count > 0 else 0
        }
    
    def __repr__(self) -> str:
        return f"<EventImpact type={self.event_type} gate={self.gate_id} offset={self.time_offset_hours}h>"
