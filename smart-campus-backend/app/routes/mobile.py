"""
mobile.py — Mobile app integration endpoints for push notifications
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db, socketio
from ..models.user_model import DeviceToken
from datetime import datetime, timezone

mobile_bp = Blueprint('mobile', __name__)


# ─── Register Device Token ────────────────────────────────────────────────────

@mobile_bp.route('/register', methods=['POST'])
def register_device():
    """
    Register a mobile device for push notifications.
    
    POST /api/mobile/register
    {
        "device_id": "unique-device-uuid",
        "token": "fcm-or-apns-token",
        "platform": "ios" | "android" | "web",
        "user_id": 123  // optional
    }
    """
    data = request.get_json()
    
    if not data or 'device_id' not in data or 'token' not in data or 'platform' not in data:
        return jsonify({'error': 'Missing required fields: device_id, token, platform'}), 400
    
    device_id = data['device_id']
    token = data['token']
    platform = data['platform']
    user_id = data.get('user_id')
    
    if platform not in ['ios', 'android', 'web']:
        return jsonify({'error': 'Invalid platform. Must be: ios, android, or web'}), 400
    
    # Check if device already exists
    device = DeviceToken.query.filter_by(device_id=device_id).first()
    
    if device:
        # Update existing token
        device.token = token
        device.platform = platform
        device.user_id = user_id
        device.is_active = True
        device.last_seen = datetime.now(timezone.utc)
    else:
        # Create new device token
        device = DeviceToken(
            device_id=device_id,
            token=token,
            platform=platform,
            user_id=user_id,
            is_active=True
        )
        db.session.add(device)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'device_id': device_id,
        'message': 'Device registered successfully for push notifications'
    }), 201


# ─── Unregister Device ────────────────────────────────────────────────────────

@mobile_bp.route('/unregister', methods=['POST'])
def unregister_device():
    """
    Unregister a device from push notifications.
    
    POST /api/mobile/unregister
    {
        "device_id": "unique-device-uuid"
    }
    """
    data = request.get_json()
    
    if not data or 'device_id' not in data:
        return jsonify({'error': 'Missing device_id'}), 400
    
    device_id = data['device_id']
    device = DeviceToken.query.filter_by(device_id=device_id).first()
    
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    
    device.is_active = False
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Device unregistered successfully'
    }), 200


# ─── Send Push Notification ───────────────────────────────────────────────────

@mobile_bp.route('/send-redirect', methods=['POST'])
@jwt_required()
def send_redirect_notification():
    """
    Send a gate redirection push notification to specific devices.
    (In production, this would integrate with FCM/APNs)
    
    POST /api/mobile/send-redirect
    {
        "gate_id": "A",
        "redirect_to": "B",
        "message": "Gate A is full. Please proceed to Gate B",
        "device_ids": ["device-1", "device-2"]  // optional, if empty sends to all active
    }
    """
    data = request.get_json()
    
    if not data or 'gate_id' not in data or 'redirect_to' not in data:
        return jsonify({'error': 'Missing required fields: gate_id, redirect_to'}), 400
    
    gate_id = data['gate_id']
    redirect_to = data['redirect_to']
    message = data.get('message', f'Gate {gate_id} is full. Please proceed to Gate {redirect_to}')
    device_ids = data.get('device_ids', [])
    
    # Get target devices
    if device_ids:
        devices = DeviceToken.query.filter(
            DeviceToken.device_id.in_(device_ids),
            DeviceToken.is_active == True
        ).all()
    else:
        devices = DeviceToken.query.filter_by(is_active=True).all()
    
    # In production, this would call FCM/APNs API
    # For now, we'll just emit a WebSocket event
    notification_payload = {
        'type': 'gate_redirect',
        'gate_id': gate_id,
        'redirect_to': redirect_to,
        'message': message,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    # Emit to WebSocket clients
    socketio.emit('redirect_notification', notification_payload, namespace='/ws/traffic')
    
    # Log the notification (in production, send to FCM/APNs here)
    sent_count = 0
    for device in devices:
        # TODO: Implement actual FCM/APNs push
        # For now, just update last_seen
        device.last_seen = datetime.now(timezone.utc)
        sent_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'sent_to': sent_count,
        'devices_targeted': len(devices),
        'message': message,
        'note': 'In production, this would send FCM/APNs push notifications'
    }), 200


# ─── Get Registered Devices ───────────────────────────────────────────────────

@mobile_bp.route('/devices', methods=['GET'])
@jwt_required()
def get_devices():
    """
    Get all registered devices.
    
    GET /api/mobile/devices?active_only=true
    """
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    
    if active_only:
        devices = DeviceToken.query.filter_by(is_active=True).all()
    else:
        devices = DeviceToken.query.all()
    
    return jsonify({
        'devices': [device.to_dict() for device in devices],
        'total': len(devices)
    }), 200
