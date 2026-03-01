"""
generate_historical_data.py — Generate realistic historical data for both normal and event days
"""

import random
import math
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db
from app.models.traffic_model import GateStatus, TrafficEntry, ShuttleStatus
from app.models.event_model import Event, HistoricalPattern, EventImpact
from app.models.user_model import User


def generate_normal_day_patterns():
    """Generate 30 days of historical data for normal weekdays and weekends."""
    print("\n📊 Generating Normal Day Patterns...")
    
    gates = ['A', 'B', 'C', 'D']
    patterns_added = 0
    
    # For each gate, generate patterns for each day of week and each hour
    for gate_id in gates:
        for day_of_week in range(7):  # 0=Monday, 6=Sunday
            for hour in range(24):
                # Base patterns based on hour and day
                is_weekend = day_of_week >= 5
                
                # Morning peak (7-9am) - higher on weekdays
                morning_peak = max(0, 40 - abs(hour - 8) * 5) if not is_weekend else max(0, 20 - abs(hour - 10) * 4)
                
                # Lunch peak (12-2pm)
                lunch_peak = max(0, 35 - abs(hour - 13) * 4)
                
                # Evening peak (5-7pm) - higher on weekdays
                evening_peak = max(0, 45 - abs(hour - 18) * 5) if not is_weekend else max(0, 25 - abs(hour - 19) * 4)
                
                # Late night (10pm-6am) - very low
                late_night_factor = 0.2 if (hour >= 22 or hour <= 6) else 1.0
                
                # Combine patterns
                base_count = (morning_peak + lunch_peak + evening_peak) * late_night_factor
                
                # Weekend adjustment - generally lower
                if is_weekend:
                    base_count *= 0.6
                
                # Gate-specific multipliers
                gate_multipliers = {'A': 1.2, 'B': 0.9, 'C': 1.1, 'D': 0.8}
                base_count *= gate_multipliers.get(gate_id, 1.0)
                
                # Add randomness
                average_count = base_count + random.uniform(-5, 5)
                peak_count = int(average_count * random.uniform(1.3, 1.6))
                min_count = max(2, int(average_count * random.uniform(0.4, 0.7)))
                std_dev = average_count * random.uniform(0.15, 0.25)
                
                pattern = HistoricalPattern(
                    gate_id=gate_id,
                    day_of_week=day_of_week,
                    hour=hour,
                    average_count=max(2, average_count),
                    peak_count=peak_count,
                    min_count=min_count,
                    std_deviation=std_dev,
                    sample_size=random.randint(15, 30),  # 15-30 days of data
                    is_event_day=False
                )
                db.session.add(pattern)
                patterns_added += 1
    
    db.session.commit()
    print(f"✓ Added {patterns_added} normal day patterns")


def generate_events():
    """Generate historical and upcoming events."""
    print("\n🎉 Generating Events...")
    
    now = datetime.now(timezone.utc)
    events_data = [
        # Past events (for historical learning)
        {
            "name": "Annual Tech Fest",
            "event_type": "festival",
            "location": "Main Auditorium",
            "expected_attendance": 2500,
            "impact_level": "critical",
            "start_offset_days": -14,
            "duration_hours": 8,
            "status": "completed"
        },
        {
            "name": "Basketball Championship Finals",
            "event_type": "sports",
            "location": "Sports Complex",
            "expected_attendance": 1800,
            "impact_level": "high",
            "start_offset_days": -10,
            "duration_hours": 4,
            "status": "completed"
        },
        {
            "name": "Semester Final Exams",
            "event_type": "exam",
            "location": "Exam Halls",
            "expected_attendance": 3500,
            "impact_level": "high",
            "start_offset_days": -7,
            "duration_hours": 3,
            "status": "completed"
        },
        {
            "name": "Guest Lecture - AI in Healthcare",
            "event_type": "conference",
            "location": "Conference Hall",
            "expected_attendance": 800,
            "impact_level": "medium",
            "start_offset_days": -3,
            "duration_hours": 3,
            "status": "completed"
        },
        # Current/Upcoming events
        {
            "name": "Spring Concert - Live Band Night",
            "event_type": "concert",
            "location": "Open Amphitheater",
            "expected_attendance": 2200,
            "impact_level": "critical",
            "start_offset_days": 0,
            "duration_hours": 5,
            "status": "active"
        },
        {
            "name": "Career Fair 2026",
            "event_type": "conference",
            "location": "Main Building",
            "expected_attendance": 1500,
            "impact_level": "high",
            "start_offset_days": 2,
            "duration_hours": 6,
            "status": "scheduled"
        },
        {
            "name": "Football League Finals",
            "event_type": "sports",
            "location": "Stadium",
            "expected_attendance": 2000,
            "impact_level": "high",
            "start_offset_days": 5,
            "duration_hours": 3,
            "status": "scheduled"
        },
        {
            "name": "Cultural Festival - Day 1",
            "event_type": "festival",
            "location": "Cultural Center",
            "expected_attendance": 3000,
            "impact_level": "critical",
            "start_offset_days": 7,
            "duration_hours": 10,
            "status": "scheduled"
        },
        {
            "name": "Cultural Festival - Day 2",
            "event_type": "festival",
            "location": "Cultural Center",
            "expected_attendance": 3200,
            "impact_level": "critical",
            "start_offset_days": 8,
            "duration_hours": 10,
            "status": "scheduled"
        },
        {
            "name": "Midterm Exams - Week 1",
            "event_type": "exam",
            "location": "All Academic Buildings",
            "expected_attendance": 3500,
            "impact_level": "high",
            "start_offset_days": 14,
            "duration_hours": 3,
            "status": "scheduled"
        }
    ]
    
    for event_data in events_data:
        start_time = now + timedelta(days=event_data['start_offset_days'])
        end_time = start_time + timedelta(hours=event_data['duration_hours'])
        
        event = Event(
            name=event_data['name'],
            event_type=event_data['event_type'],
            location=event_data['location'],
            expected_attendance=event_data['expected_attendance'],
            start_time=start_time,
            end_time=end_time,
            impact_level=event_data['impact_level'],
            status=event_data['status']
        )
        db.session.add(event)
    
    db.session.commit()
    print(f"✓ Added {len(events_data)} events (historical and upcoming)")


def generate_event_impact_data():
    """Generate historical event impact data showing how events affected crowds."""
    print("\n📈 Generating Event Impact Data...")
    
    gates = ['A', 'B', 'C', 'D']
    event_types = ['concert', 'sports', 'exam', 'festival', 'conference']
    impact_levels = {
        'concert': 'critical',
        'sports': 'high',
        'exam': 'high',
        'festival': 'critical',
        'conference': 'medium'
    }
    
    impacts_added = 0
    
    for event_type in event_types:
        for gate_id in gates:
            # Generate impact data for different time offsets
            # -2 hours (before event): moderate increase
            # 0 hours (event start): peak
            # +1 to +3 hours (during event): high
            # +4 to +6 hours (after event): declining
            
            time_offsets = [-2, -1, 0, 1, 2, 3, 4, 5, 6]
            
            for offset in time_offsets:
                # Calculate impact based on event type and time offset
                if event_type in ['concert', 'festival']:
                    if offset == -2:
                        multiplier = 1.3
                        additional = 15
                    elif offset == -1:
                        multiplier = 1.8
                        additional = 25
                    elif offset == 0:
                        multiplier = 2.5
                        additional = 40
                    elif offset <= 2:
                        multiplier = 2.2
                        additional = 35
                    elif offset <= 4:
                        multiplier = 1.6
                        additional = 20
                    else:
                        multiplier = 1.2
                        additional = 10
                        
                elif event_type == 'sports':
                    if offset == -1:
                        multiplier = 1.5
                        additional = 20
                    elif offset == 0:
                        multiplier = 2.0
                        additional = 30
                    elif offset <= 2:
                        multiplier = 1.8
                        additional = 25
                    elif offset <= 3:
                        multiplier = 1.3
                        additional = 12
                    else:
                        multiplier = 1.0
                        additional = 5
                        
                elif event_type == 'exam':
                    if offset == -1:
                        multiplier = 1.6
                        additional = 18
                    elif offset == 0:
                        multiplier = 1.9
                        additional = 25
                    elif offset == 1:
                        multiplier = 1.4
                        additional = 12
                    elif offset <= 3:
                        multiplier = 0.8
                        additional = -5
                    else:
                        multiplier = 1.0
                        additional = 0
                        
                elif event_type == 'conference':
                    if offset == 0:
                        multiplier = 1.4
                        additional = 12
                    elif offset <= 3:
                        multiplier = 1.3
                        additional = 10
                    else:
                        multiplier = 1.1
                        additional = 5
                else:
                    multiplier = 1.0
                    additional = 0
                
                # Gate-specific adjustments
                if gate_id == 'A':  # Main entrance - higher impact
                    multiplier *= 1.2
                    additional = int(additional * 1.3)
                elif gate_id == 'D':  # Side entrance - lower impact
                    multiplier *= 0.8
                    additional = int(additional * 0.7)
                
                # Calculate realistic counts
                baseline = 30 + random.randint(-5, 5)
                recorded = int(baseline * multiplier + additional + random.randint(-3, 3))
                
                impact = EventImpact(
                    event_type=event_type,
                    gate_id=gate_id,
                    time_offset_hours=offset,
                    crowd_multiplier=multiplier,
                    additional_count=additional,
                    recorded_count=max(5, recorded),
                    baseline_count=baseline,
                    impact_level=impact_levels[event_type]
                )
                db.session.add(impact)
                impacts_added += 1
    
    db.session.commit()
    print(f"✓ Added {impacts_added} event impact records")


def generate_traffic_entries():
    """Generate recent traffic entries for realistic feel."""
    print("\n🚦 Generating Recent Traffic Entries...")
    
    gates = ['A', 'B', 'C', 'D']
    now = datetime.now(timezone.utc)
    entries_added = 0
    
    # Generate entries for last 24 hours
    for hours_ago in range(24, 0, -1):
        timestamp = now - timedelta(hours=hours_ago)
        hour = timestamp.hour
        
        for gate_id in gates:
            # Get appropriate count based on hour
            if 7 <= hour <= 9:  # Morning peak
                count = random.randint(35, 55)
            elif 12 <= hour <= 14:  # Lunch
                count = random.randint(30, 45)
            elif 17 <= hour <= 19:  # Evening peak
                count = random.randint(40, 60)
            elif 22 <= hour or hour <= 6:  # Night
                count = random.randint(5, 15)
            else:
                count = random.randint(20, 35)
            
            entry = TrafficEntry(
                location=f"Gate {gate_id}",
                gate_id=gate_id,
                count=count,
                source='sensor',
                timestamp=timestamp
            )
            db.session.add(entry)
            entries_added += 1
    
    db.session.commit()
    print(f"✓ Added {entries_added} traffic entries")


def init_full_database():
    """Complete database initialization with all data."""
    app = create_app()
    with app.app_context():
        print("\n" + "="*60)
        print("  SMART CAMPUS - FULL DATABASE INITIALIZATION")
        print("="*60)
        
        # Drop and recreate all tables
        print("\n🗑️  Dropping existing tables...")
        db.drop_all()
        print("✓ Tables dropped")
        
        print("\n🏗️  Creating new tables...")
        db.create_all()
        print("✓ Tables created")
        
        # Generate all data
        generate_normal_day_patterns()
        generate_events()
        generate_event_impact_data()
        generate_traffic_entries()
        
        # Add current gate status
        print("\n🚪 Initializing Gate Status...")
        gates_data = [
            {'gate_id': 'A', 'name': 'Gate A - Main Entrance', 'location': 'Main Building', 'density': 35.0, 'entries': 18},
            {'gate_id': 'B', 'name': 'Gate B - North Wing', 'location': 'North Wing', 'density': 52.0, 'entries': 26},
            {'gate_id': 'C', 'name': 'Gate C - South Wing', 'location': 'South Wing', 'density': 68.0, 'entries': 34},
            {'gate_id': 'D', 'name': 'Gate D - East Entrance', 'location': 'East Building', 'density': 22.0, 'entries': 11},
        ]
        
        for gate_data in gates_data:
            gate = GateStatus(
                gate_id=gate_data['gate_id'],
                name=gate_data['name'],
                location=gate_data['location'],
                density=gate_data['density'],
                entries=gate_data['entries'],
                predicted=gate_data['density'] + random.uniform(-5, 10),
                max_capacity=50,
                use_global_capacity=True,
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(gate)
        db.session.commit()
        print(f"✓ Added {len(gates_data)} gates")
        
        # Add shuttles
        print("\n🚌 Initializing Shuttles...")
        shuttles_data = [
            {'shuttle_id': 'S1', 'name': 'Express Loop', 'route': 'Main-Library-Sports', 'load': 38, 'capacity': 50, 'next_stop': 'Library', 'eta_min': 4},
            {'shuttle_id': 'S2', 'name': 'Academic Circle', 'route': 'All Academic Buildings', 'load': 44, 'capacity': 50, 'next_stop': 'Engineering Block', 'eta_min': 2},
            {'shuttle_id': 'S3', 'name': 'Hostel Shuttle', 'route': 'Hostels-Main Gate', 'load': 28, 'capacity': 50, 'next_stop': 'Hostel B', 'eta_min': 6},
        ]
        
        for shuttle_data in shuttles_data:
            shuttle = ShuttleStatus(
                shuttle_id=shuttle_data['shuttle_id'],
                name=shuttle_data['name'],
                route=shuttle_data['route'],
                load=shuttle_data['load'],
                capacity=shuttle_data['capacity'],
                status='active',
                next_stop=shuttle_data['next_stop'],
                eta_min=shuttle_data['eta_min'],
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(shuttle)
        db.session.commit()
        print(f"✓ Added {len(shuttles_data)} shuttles")
        
        # Final statistics
        print("\n" + "="*60)
        print("  📊 DATABASE STATISTICS")
        print("="*60)
        print(f"  Normal Day Patterns:  {HistoricalPattern.query.filter_by(is_event_day=False).count()}")
        print(f"  Events:               {Event.query.count()}")
        print(f"  Event Impact Records: {EventImpact.query.count()}")
        print(f"  Traffic Entries:      {TrafficEntry.query.count()}")
        print(f"  Gate Status:          {GateStatus.query.count()}")
        print(f"  Shuttles:             {ShuttleStatus.query.count()}")
        print("="*60)
        print("\n✅ FULL DATABASE INITIALIZATION COMPLETE!")
        print(f"\n📍 Active Events Today: {Event.query.filter_by(status='active').count()}")
        print(f"📅 Upcoming Events: {Event.query.filter_by(status='scheduled').count()}")
        print("\n🚀 System is ready for predictions and analytics!\n")


if __name__ == '__main__':
    init_full_database()
