"""
Initialize the database with correct schema
"""
from app import create_app
from app.extensions import db
from app.models.traffic_model import GateStatus, TrafficEntry, ShuttleStatus
from app.models.user_model import User, DeviceToken
from datetime import datetime, timezone

def init_database():
    app = create_app()
    with app.app_context():
        # Drop all existing tables and recreate
        db.drop_all()
        print("✓ Dropped all existing tables")
        
        # Create all tables with new schema
        db.create_all()
        print("✓ Database tables created with updated schema")
        
        # Check if gates already exist
        existing_gates = GateStatus.query.count()
        if existing_gates == 0:
            # Add seed data for gates
            gates = [
                GateStatus(
                    gate_id='A',
                    name='Gate A',
                    location='Main Entrance',
                    density=25.0,
                    entries=12,
                    predicted=30.0,
                    max_capacity=50,
                    use_global_capacity=True,
                    updated_at=datetime.now(timezone.utc)
                ),
                GateStatus(
                    gate_id='B',
                    name='Gate B',
                    location='North Wing',
                    density=45.0,
                    entries=22,
                    predicted=50.0,
                    max_capacity=50,
                    use_global_capacity=True,
                    updated_at=datetime.now(timezone.utc)
                ),
                GateStatus(
                    gate_id='C',
                    name='Gate C',
                    location='South Wing',
                    density=65.0,
                    entries=32,
                    predicted=70.0,
                    max_capacity=50,
                    use_global_capacity=True,
                    updated_at=datetime.now(timezone.utc)
                ),
                GateStatus(
                    gate_id='D',
                    name='Gate D',
                    location='East Entrance',
                    density=15.0,
                    entries=7,
                    predicted=20.0,
                    max_capacity=50,
                    use_global_capacity=True,
                    updated_at=datetime.now(timezone.utc)
                ),
            ]
            
            for gate in gates:
                db.session.add(gate)
            
            db.session.commit()
            print(f"✓ Added {len(gates)} seed gates")
        else:
            print(f"✓ Found {existing_gates} existing gates")
        
        # Add shuttles if they don't exist
        existing_shuttles = ShuttleStatus.query.count()
        if existing_shuttles == 0:
            shuttles = [
                ShuttleStatus(
                    shuttle_id='S1',
                    name='Shuttle 1',
                    route='Campus Loop',
                    load=35,
                    capacity=50,
                    status='active',
                    next_stop='Library',
                    eta_min=5,
                    updated_at=datetime.now(timezone.utc)
                ),
                ShuttleStatus(
                    shuttle_id='S2',
                    name='Shuttle 2',
                    route='Express',
                    load=42,
                    capacity=50,
                    status='active',
                    next_stop='Main Gate',
                    eta_min=3,
                    updated_at=datetime.now(timezone.utc)
                ),
            ]
            
            for shuttle in shuttles:
                db.session.add(shuttle)
            
            db.session.commit()
            print(f"✓ Added {len(shuttles)} seed shuttles")
        else:
            print(f"✓ Found {existing_shuttles} existing shuttles")
        
        print("\n✅ Database initialization complete!")
        print(f"   Gates: {GateStatus.query.count()}")
        print(f"   Shuttles: {ShuttleStatus.query.count()}")
        print(f"   Traffic Entries: {TrafficEntry.query.count()}")

if __name__ == '__main__':
    init_database()
