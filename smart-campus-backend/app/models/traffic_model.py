"""
traffic_model.py — SQLAlchemy ORM models for traffic & shuttle data
"""

from datetime import datetime, timezone
from ..extensions import db


# ─── Traffic Entry ────────────────────────────────────────────────────────────

class TrafficEntry(db.Model):
    """
    Stores each crowd / gate sensor data point ingested via POST /api/traffic/add.
    All data is anonymised (no user identifiers stored).
    """
    __tablename__ = "traffic_entries"

    id        = db.Column(db.Integer, primary_key=True)
    location  = db.Column(db.String(128), nullable=False, index=True)
    gate_id   = db.Column(db.String(8),   nullable=True,  index=True)
    count     = db.Column(db.Integer,     nullable=False, default=0)
    source    = db.Column(db.String(32),  nullable=True,  default="manual")
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "location":  self.location,
            "gate_id":   self.gate_id,
            "count":     self.count,
            "source":    self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self) -> str:
        return f"<TrafficEntry {self.location} count={self.count}>"


# ─── Gate Status ─────────────────────────────────────────────────────────────

class GateStatus(db.Model):
    """
    Snapshot of current congestion state per campus gate.
    Updated by the simulation loop or sensor push.
    """
    __tablename__ = "gate_status"

    id         = db.Column(db.Integer, primary_key=True)
    gate_id    = db.Column(db.String(8),   unique=True, nullable=False)
    name       = db.Column(db.String(64),  nullable=False)
    location   = db.Column(db.String(128), nullable=True)
    density    = db.Column(db.Float,       nullable=False, default=0.0)  # 0–100 %
    entries    = db.Column(db.Integer,     nullable=False, default=0)
    predicted  = db.Column(db.Float,       nullable=True)                # ML 1-hr forecast
    max_capacity = db.Column(db.Integer,   nullable=False, default=50)   # Per-gate capacity
    use_global_capacity = db.Column(db.Boolean, nullable=False, default=True)  # Use global vs per-gate
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "gate_id":   self.gate_id,
            "name":      self.name,
            "location":  self.location,
            "density":   round(self.density, 1),
            "entries":   self.entries,
            "predicted": round(self.predicted, 1) if self.predicted is not None else None,
            "max_capacity": self.max_capacity,
            "use_global_capacity": self.use_global_capacity,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<GateStatus {self.gate_id} density={self.density}%>"


# ─── Shuttle Status ───────────────────────────────────────────────────────────

class ShuttleStatus(db.Model):
    """
    Live status record for each shuttle in the campus fleet.
    """
    __tablename__ = "shuttle_status"

    id         = db.Column(db.Integer, primary_key=True)
    shuttle_id = db.Column(db.String(16), unique=True, nullable=False)
    name       = db.Column(db.String(64), nullable=False)
    route      = db.Column(db.String(128), nullable=True)
    load       = db.Column(db.Float,  nullable=False, default=0.0)   # current passengers
    capacity   = db.Column(db.Integer, nullable=False, default=45)
    status     = db.Column(db.String(16), nullable=False, default="active")  # active|standby|maintenance
    next_stop  = db.Column(db.String(64), nullable=True)
    eta_min    = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "shuttle_id": self.shuttle_id,
            "name":       self.name,
            "route":      self.route,
            "load":       self.load,
            "capacity":   self.capacity,
            "status":     self.status,
            "next_stop":  self.next_stop,
            "eta_min":    self.eta_min,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ShuttleStatus {self.shuttle_id} load={self.load}/{self.capacity}>"
