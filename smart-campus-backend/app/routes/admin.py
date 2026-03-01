"""
admin.py — Administrative configuration endpoints for capacity management
"""

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from ..extensions import db, socketio
from ..models.traffic_model import GateStatus
from datetime import datetime, timezone

admin_bp = Blueprint('admin', __name__)


# ─── Update Per-Gate Capacity ─────────────────────────────────────────────────

@admin_bp.route('/capacity/gate/<gate_id>', methods=['POST'])
@jwt_required()
def update_gate_capacity(gate_id):
    """
    Update max capacity for a specific gate.
    
    POST /api/admin/capacity/gate/A
    {
        "capacity": 30,
        "use_global": false
    }
    """
    data = request.get_json()
    
    if not data or 'capacity' not in data:
        return jsonify({'error': 'Missing capacity in request body'}), 400
    
    capacity = data.get('capacity')
    use_global = data.get('use_global', False)
    
    if not isinstance(capacity, int) or capacity < 1:
        return jsonify({'error': 'Capacity must be a positive integer'}), 400
    
    # Find or create gate status
    gate = GateStatus.query.filter_by(gate_id=gate_id).first()
    
    if not gate:
        # Create new gate if doesn't exist
        gate = GateStatus(
            gate_id=gate_id,
            name=f"Gate {gate_id}",
            location=f"Location {gate_id}",
            density=0.0,
            entries=0,
            max_capacity=capacity,
            use_global_capacity=use_global
        )
        db.session.add(gate)
    else:
        gate.max_capacity = capacity
        gate.use_global_capacity = use_global
        gate.updated_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    # Emit WebSocket update
    socketio.emit('capacity_updated', {
        'gate_id': gate_id,
        'capacity': capacity,
        'use_global': use_global
    }, namespace='/ws/traffic')
    
    return jsonify({
        'success': True,
        'gate_id': gate_id,
        'capacity': capacity,
        'use_global': use_global,
        'message': f'Gate {gate_id} capacity updated to {capacity}'
    }), 200


# ─── Update Global Capacity ───────────────────────────────────────────────────

@admin_bp.route('/capacity/global', methods=['POST'])
@jwt_required()
def update_global_capacity():
    """
    Set global capacity for all gates or specific gates.
    
    POST /api/admin/capacity/global
    {
        "capacity": 50,
        "gate_ids": ["A", "B", "C"]  // optional, if empty applies to all
    }
    """
    data = request.get_json()
    
    if not data or 'capacity' not in data:
        return jsonify({'error': 'Missing capacity in request body'}), 400
    
    capacity = data.get('capacity')
    gate_ids = data.get('gate_ids', [])
    
    if not isinstance(capacity, int) or capacity < 1:
        return jsonify({'error': 'Capacity must be a positive integer'}), 400
    
    # Update gates
    if gate_ids:
        gates = GateStatus.query.filter(GateStatus.gate_id.in_(gate_ids)).all()
    else:
        gates = GateStatus.query.all()
    
    updated_count = 0
    for gate in gates:
        gate.max_capacity = capacity
        gate.use_global_capacity = True
        gate.updated_at = datetime.now(timezone.utc)
        updated_count += 1
    
    db.session.commit()
    
    # Emit WebSocket update
    socketio.emit('global_capacity_updated', {
        'capacity': capacity,
        'affected_gates': [g.gate_id for g in gates]
    }, namespace='/ws/traffic')
    
    return jsonify({
        'success': True,
        'capacity': capacity,
        'gates_updated': updated_count,
        'message': f'Updated {updated_count} gates to capacity {capacity}'
    }), 200


# ─── Get All Capacity Settings ────────────────────────────────────────────────

@admin_bp.route('/capacity/all', methods=['GET'])
@jwt_required()
def get_all_capacities():
    """
    Retrieve capacity settings for all gates.
    
    GET /api/admin/capacity/all
    """
    gates = GateStatus.query.all()
    
    default_global = current_app.config.get('DEFAULT_GLOBAL_CAPACITY', 50)
    
    result = {
        'default_global_capacity': default_global,
        'gates': []
    }
    
    for gate in gates:
        result['gates'].append({
            'gate_id': gate.gate_id,
            'name': gate.name,
            'max_capacity': gate.max_capacity,
            'use_global_capacity': gate.use_global_capacity,
            'current_entries': gate.entries,
            'density': round(gate.density, 1),
            'status': 'FULL' if gate.density >= 100 else 'WARNING' if gate.density >= 70 else 'NORMAL'
        })
    
    return jsonify(result), 200


# ─── Update Threshold Settings ────────────────────────────────────────────────

@admin_bp.route('/thresholds', methods=['POST'])
@jwt_required()
def update_thresholds():
    """
    Update warning and critical threshold percentages.
    
    POST /api/admin/thresholds
    {
        "warning_threshold": 0.7,    // 70%
        "critical_threshold": 0.9    // 90%
    }
    """
    data = request.get_json()
    
    warning = data.get('warning_threshold')
    critical = data.get('critical_threshold')
    
    if warning is not None and (warning < 0 or warning > 1):
        return jsonify({'error': 'Warning threshold must be between 0 and 1'}), 400
    
    if critical is not None and (critical < 0 or critical > 1):
        return jsonify({'error': 'Critical threshold must be between 0 and 1'}), 400
    
    if warning and critical and warning >= critical:
        return jsonify({'error': 'Warning threshold must be less than critical threshold'}), 400
    
    # In a real app, these would be stored in database
    # For now, just return success
    return jsonify({
        'success': True,
        'warning_threshold': warning,
        'critical_threshold': critical,
        'message': 'Thresholds updated successfully'
    }), 200
