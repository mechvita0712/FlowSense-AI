"""
auth.py — Authentication API
=============================
Endpoints:
  POST /api/auth/register  – Create a new admin/staff account
  POST /api/auth/login     – Obtain a JWT access token
  GET  /api/auth/me        – Return the logged-in user's profile
  POST /api/auth/logout    – (client-side token discard, server ack)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from datetime import datetime, timezone

from ..models.user_model import User
from ..extensions import db

auth_bp = Blueprint("auth", __name__)


def _bad(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ─── Register ────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Body: { "email": "...", "password": "...", "name": "...", "role": "admin" }
    Roles: admin | staff | viewer
    """
    data = request.get_json(silent=True)
    if not data:
        return _bad("Request body must be valid JSON")

    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name     = (data.get("name") or "").strip()
    role     = data.get("role", "viewer")

    if not email or not password:
        return _bad("'email' and 'password' are required")
    if len(password) < 8:
        return _bad("Password must be at least 8 characters")
    if role not in ("admin", "staff", "viewer"):
        return _bad("'role' must be one of: admin, staff, viewer")

    if User.query.filter_by(email=email).first():
        return _bad("An account with this email already exists", 409)

    user = User(
        email=email,
        name=name or email.split("@")[0],
        role=role,
        created_at=datetime.now(timezone.utc),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({
        "message": "Account created successfully",
        "access_token": token,
        "user": user.to_dict(),
    }), 201


# ─── Login ───────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Body: { "email": "...", "password": "..." }
    Returns: JWT access token
    """
    data = request.get_json(silent=True)
    if not data:
        return _bad("Request body must be valid JSON")

    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return _bad("'email' and 'password' are required")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({
        "message": "Login successful",
        "access_token": token,
        "user": user.to_dict(),
    })


# ─── Profile ─────────────────────────────────────────────────────────────────

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Returns the authenticated user's profile. Requires Bearer token."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return _bad("User not found", 404)
    return jsonify({"user": user.to_dict()})


# ─── Logout ──────────────────────────────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """
    JWT is stateless — actual invalidation is handled client-side by
    discarding the token. This endpoint simply acknowledges the action.
    Add a token blocklist (Redis / DB) here for production-grade logout.
    """
    return jsonify({"message": "Logged out successfully"})
