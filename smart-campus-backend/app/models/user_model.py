"""
user_model.py — User account ORM model with password hashing.
"""

from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db


class User(db.Model):
    """
    Represents an admin / staff / viewer account.
    Passwords are stored as Werkzeug bcrypt hashes — never plaintext.
    """
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name       = db.Column(db.String(100), nullable=False)
    role       = db.Column(db.String(20),  nullable=False, default="viewer")
    _password  = db.Column("password_hash", db.String(256), nullable=False)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ── Password Helpers ──────────────────────────────────────────────────────

    def set_password(self, raw_password: str) -> None:
        """Hash and store the password. Never stores raw text."""
        self._password = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Verify a candidate password against the stored hash."""
        return check_password_hash(self._password, raw_password)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Return a safe public view — password hash is NEVER included."""
        return {
            "id":         self.id,
            "email":      self.email,
            "name":       self.name,
            "role":       self.role,
            "is_active":  self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"


# ─── Device Token for Mobile Push Notifications ───────────────────────────────

class DeviceToken(db.Model):
    """
    Stores mobile device tokens for push notifications (FCM/APNs).
    Used to send gate redirection alerts to mobile apps.
    """
    __tablename__ = "device_tokens"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Optional user association
    device_id  = db.Column(db.String(128), unique=True, nullable=False, index=True)  # Unique device identifier
    token      = db.Column(db.String(256), nullable=False)  # FCM/APNs token
    platform   = db.Column(db.String(16), nullable=False)   # 'ios', 'android', 'web'
    is_active  = db.Column(db.Boolean, default=True)
    last_seen  = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "platform": self.platform,
            "is_active": self.is_active,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }

    def __repr__(self) -> str:
        return f"<DeviceToken {self.device_id} {self.platform}>"
