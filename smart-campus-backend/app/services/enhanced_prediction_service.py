"""
enhanced_prediction_service.py — Advanced prediction using historical and event data
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import random
import math
from sqlalchemy import and_, or_
from ..extensions import db
from ..models.event_model import Event, HistoricalPattern, EventImpact


class EnhancedPredictionService:
    """
    Advanced prediction service that combines:
    1. Historical normal-day patterns
    2. Event-based predictions
    3. Real-time data trends
    """
    
    @classmethod
    def predict_crowd_with_events(cls, gate_id: str, hours_ahead: int = 1) -> Dict:
        """
        Predict crowd levels considering both historical patterns and upcoming events.
        
        Returns:
            {
                'predicted_count': int,
                'predicted_density': float,
                'confidence': float (0-100),
                'factors': {
                    'baseline': int,
                    'event_impact': int,
                    'trend_adjustment': int
                },
                'active_events': List[dict],
                'recommendation': str
            }
        """
        now = datetime.now(timezone.utc)
        target_time = now + timedelta(hours=hours_ahead)
        
        # 1. Get baseline from historical patterns
        baseline = cls._get_historical_baseline(gate_id, target_time)
        
        # 2. Check for active/upcoming events and their impact
        event_impact, active_events = cls._calculate_event_impact(gate_id, target_time)
        
        # 3. Get current trend
        trend_adjustment = cls._calculate_trend_adjustment(gate_id)
        
        # 4. Combine predictions
        predicted_count = max(5, baseline + event_impact + trend_adjustment)
        
        # 5. Calculate confidence based on data availability
        confidence = cls._calculate_confidence(gate_id, bool(active_events))
        
        # 6. Generate recommendation
        recommendation = cls._generate_recommendation(
            predicted_count, 
            baseline, 
            event_impact,
            active_events
        )
        
        # Assume capacity of 50 for density calculation
        predicted_density = min(99.9, (predicted_count / 50) * 100)
        
        return {
            'predicted_count': round(predicted_count),
            'predicted_density': round(predicted_density, 1),
            'confidence': round(confidence, 1),
            'factors': {
                'baseline': round(baseline),
                'event_impact': round(event_impact),
                'trend_adjustment': round(trend_adjustment)
            },
            'active_events': active_events,
            'recommendation': recommendation
        }
    
    @classmethod
    def _get_historical_baseline(cls, gate_id: str, target_time: datetime) -> float:
        """Get baseline prediction from historical normal-day patterns."""
        day_of_week = target_time.weekday()
        hour = target_time.hour
        
        pattern = HistoricalPattern.query.filter_by(
            gate_id=gate_id,
            day_of_week=day_of_week,
            hour=hour,
            is_event_day=False
        ).first()
        
        if pattern:
            # Add some randomness within std deviation
            noise = random.uniform(-pattern.std_deviation/2, pattern.std_deviation/2)
            return pattern.average_count + noise
        
        # Fallback to time-based estimation if no historical data
        return cls._estimate_baseline_by_hour(hour)
    
    @classmethod
    def _estimate_baseline_by_hour(cls, hour: int) -> float:
        """Fallback baseline estimation based on typical campus patterns."""
        if 7 <= hour <= 9:  # Morning peak
            return 40 + random.uniform(-5, 5)
        elif 12 <= hour <= 14:  # Lunch
            return 35 + random.uniform(-5, 5)
        elif 17 <= hour <= 19:  # Evening peak
            return 45 + random.uniform(-5, 5)
        elif 22 <= hour or hour <= 6:  # Night
            return 10 + random.uniform(-3, 3)
        else:
            return 25 + random.uniform(-5, 5)
    
    @classmethod
    def _calculate_event_impact(cls, gate_id: str, target_time: datetime) -> Tuple[float, List[dict]]:
        """Calculate crowd impact from nearby events."""
        # Ensure target_time is timezone-aware
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        
        # Find events that overlap with or are near the target time
        time_window_start = target_time - timedelta(hours=3)
        time_window_end = target_time + timedelta(hours=6)
        
        nearby_events = Event.query.filter(
            and_(
                Event.start_time <= time_window_end,
                Event.end_time >= time_window_start,
                or_(Event.status == 'active', Event.status == 'scheduled')
            )
        ).all()
        
        total_impact = 0
        active_events_info = []
        
        for event in nearby_events:
            # Ensure event times are timezone-aware
            event_start = event.start_time
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=timezone.utc)
            
            # Calculate time offset from event start
            time_diff = (target_time - event_start).total_seconds() / 3600  # hours
            offset_hours = round(time_diff)
            
            # Skip if too far from event
            if abs(offset_hours) > 6:
                continue
            
            # Get historical impact data for this event type and time offset
            impact_data = EventImpact.query.filter_by(
                event_type=event.event_type,
                gate_id=gate_id,
                time_offset_hours=offset_hours
            ).first()
            
            if impact_data:
                impact_value = impact_data.additional_count
                multiplier = impact_data.crowd_multiplier
            else:
                # Use default impact based on event level
                impact_factor = {
                    'critical': 1.8,
                    'high': 1.4,
                    'medium': 1.2,
                    'low': 1.1
                }.get(event.impact_level, 1.0)
                
                if -1 <= offset_hours <= 2:  # Peak impact period
                    impact_value = (impact_factor - 1.0) * 40
                    multiplier = impact_factor
                else:
                    impact_value = (impact_factor - 1.0) * 20
                    multiplier = impact_factor
            
            total_impact += impact_value
            
            active_events_info.append({
                'name': event.name,
                'type': event.event_type,
                'impact_level': event.impact_level,
                'time_offset_hours': offset_hours,
                'expected_attendance': event.expected_attendance,
                'impact_value': round(impact_value, 1)
            })
        
        return total_impact, active_events_info
    
    @classmethod
    def _calculate_trend_adjustment(cls, gate_id: str) -> float:
        """Calculate adjustment based on recent trend."""
        from ..models.traffic_model import TrafficEntry
        
        # Get last 3 hours of data
        now = datetime.now(timezone.utc)
        recent_entries = TrafficEntry.query.filter(
            and_(
                TrafficEntry.gate_id == gate_id,
                TrafficEntry.timestamp >= now - timedelta(hours=3)
            )
        ).order_by(TrafficEntry.timestamp.desc()).limit(6).all()
        
        if len(recent_entries) < 2:
            return 0
        
        # Calculate trend (increasing or decreasing)
        counts = [e.count for e in recent_entries]
        avg_recent = sum(counts[:3]) / min(3, len(counts))
        avg_older = sum(counts[3:]) / max(1, len(counts) - 3)
        
        trend = avg_recent - avg_older
        # Dampen the trend (don't overreact)
        return trend * 0.3
    
    @classmethod
    def _calculate_confidence(cls, gate_id: str, has_events: bool) -> float:
        """Calculate prediction confidence score."""
        # Base confidence
        confidence = 70.0
        
        # Check if we have historical data
        pattern_count = HistoricalPattern.query.filter_by(gate_id=gate_id).count()
        if pattern_count > 100:
            confidence += 20
        elif pattern_count > 50:
            confidence += 10
        
        # Events reduce confidence slightly (more unpredictable)
        if has_events:
            confidence -= 15
        else:
            confidence += 10
        
        return min(100, max(50, confidence))
    
    @classmethod
    def _generate_recommendation(cls, predicted_count: int, baseline: float, 
                                 event_impact: float, active_events: List) -> str:
        """Generate actionable recommendation."""
        density = (predicted_count / 50) * 100
        
        if density >= 90:
            if active_events:
                event_names = ", ".join([e['name'] for e in active_events])
                return f"CRITICAL: Expected crowd surge due to {event_names}. Activate emergency protocols, redirect to alternate gates, and deploy additional shuttles."
            return "CRITICAL: Very high congestion predicted. Implement crowd control measures immediately."
        
        elif density >= 70:
            if event_impact > 20:
                return "HIGH ALERT: Major event impact detected. Increase shuttle frequency and staff presence."
            return "WARNING: High congestion expected. Prepare additional capacity and monitor closely."
        
        elif density >= 50:
            if active_events:
                return "MODERATE: Event-related traffic increase. Maintain enhanced monitoring and readiness."
            return "Normal elevated traffic. Standard protocols sufficient."
        
        else:
            return "Normal flow expected. Maintain standard operations."
    
    @classmethod
    def predict_shuttle_demand(cls, hours_ahead: int = 1) -> Dict:
        """Predict shuttle demand system-wide."""
        from ..models.traffic_model import GateStatus
        
        # Get predictions for all gates
        gates = GateStatus.query.all()
        total_predicted = 0
        high_demand_gates = []
        
        for gate in gates:
            prediction = cls.predict_crowd_with_events(gate.gate_id, hours_ahead)
            total_predicted += prediction['predicted_count']
            
            if prediction['predicted_density'] >= 70:
                high_demand_gates.append({
                    'gate_id': gate.gate_id,
                    'predicted_density': prediction['predicted_density'],
                    'events': prediction['active_events']
                })
        
        # Calculate shuttle requirements
        # Assume 1 shuttle can handle 50 people per trip, 3 trips per hour
        shuttles_needed = math.ceil(total_predicted / 150)
        
        return {
            'hours_ahead': hours_ahead,
            'total_predicted_crowd': total_predicted,
            'shuttles_needed': shuttles_needed,
            'high_demand_gates': high_demand_gates,
            'recommendation': cls._shuttle_recommendation(shuttles_needed, high_demand_gates)
        }
    
    @classmethod
    def _shuttle_recommendation(cls, shuttles_needed: int, high_demand_gates: List) -> str:
        """Generate shuttle deployment recommendation."""
        if shuttles_needed >= 5:
            locations = [g['gate_id'] for g in high_demand_gates]
            return f"Deploy ALL {shuttles_needed} shuttles immediately. Prioritize routes: {', '.join(locations)}"
        elif shuttles_needed >= 3:
            return f"Activate {shuttles_needed} shuttles. Focus on high-traffic routes."
        elif high_demand_gates:
            return f"Standard fleet sufficient, but monitor gates: {', '.join([g['gate_id'] for g in high_demand_gates])}"
        else:
            return "Standard shuttle schedule adequate for predicted demand."
    
    @classmethod
    def get_event_forecast(cls, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming events and their predicted impacts."""
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(days=days_ahead)
        
        upcoming_events = Event.query.filter(
            and_(
                Event.start_time >= now,
                Event.start_time <= end_time,
                Event.status == 'scheduled'
            )
        ).order_by(Event.start_time).all()
        
        forecast = []
        for event in upcoming_events:
            # Calculate expected peak crowd at event gates
            peak_impact = cls._estimate_event_peak_impact(event)
            
            forecast.append({
                'event': event.to_dict(),
                'days_until': (event.start_time - now).days,
                'hours_until': round((event.start_time - now).total_seconds() / 3600, 1),
                'expected_peak_crowd': peak_impact,
                'preparation_priority': cls._event_priority(event),
                'recommended_actions': cls._event_preparation_actions(event)
            })
        
        return forecast
    
    @classmethod
    def _estimate_event_peak_impact(cls, event: Event) -> int:
        """Estimate peak crowd numbers during event."""
        base = event.expected_attendance or 1000
        
        multipliers = {
            'critical': 1.5,
            'high': 1.3,
            'medium': 1.1,
            'low': 1.0
        }
        
        return int(base * multipliers.get(event.impact_level, 1.0) / 4)  # Spread across 4 gates
    
    @classmethod
    def _event_priority(cls, event: Event) -> str:
        """Determine preparation priority."""
        hours_until = (event.start_time - datetime.now(timezone.utc)).total_seconds() / 3600
        
        if event.impact_level == 'critical':
            if hours_until < 24:
                return "URGENT"
            elif hours_until < 72:
                return "HIGH"
            else:
                return "MEDIUM"
        elif event.impact_level == 'high':
            if hours_until < 48:
                return "HIGH"
            else:
                return "MEDIUM"
        else:
            return "NORMAL"
    
    @classmethod
    def _event_preparation_actions(cls, event: Event) -> List[str]:
        """Generate preparation action items."""
        actions = []
        
        if event.impact_level in ['critical', 'high']:
            actions.append("Pre-deploy additional security and crowd management staff")
            actions.append("Set up temporary signage and barriers")
            actions.append("Activate all available shuttles 30 minutes before event")
        
        if event.expected_attendance and event.expected_attendance > 2000:
            actions.append("Coordinate with event organizers for staggered entry")
            actions.append("Set up express lanes at main gates")
        
        actions.append(f"Send mobile push notifications to redirect traffic away from congested areas")
        actions.append(f"Monitor {event.location} and surrounding gates in real-time")
        
        return actions
