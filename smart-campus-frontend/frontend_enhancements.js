/**
 * frontend_enhancements.js - Add this to app.js to enable event-aware predictions and charts
 * 
 * INSTRUCTIONS:
 * 1. Add these functions to app.js
 * 2. Update syncEventsFromBackend() to use new API
 * 3. Update renderEventsView() to show real event data
 */

// ══════════════════════════════════════════════════════════════════════════════
// ENHANCED EVENT DATA SYNCING
// ══════════════════════════════════════════════════════════════════════════════

async function syncEventsFromBackend() {
  try {
    // Get list of events
    const eventsData = await apiFetch('/api/events/list?days_ahead=30');
    if (eventsData && eventsData.events) {
      state.events = eventsData.events.map(e => ({
        id: e.id,
        title: e.name,
        time: new Date(e.start_time).toLocaleString('en-US', { 
          month: 'short', 
          day: 'numeric', 
          hour: '2-digit', 
          minute: '2-digit' 
        }),
        location: e.location || 'Campus',
        attendees: e.expected_attendance || 0,
        impact: e.impact_level,
        type: e.event_type,
        status: e.status,
        duration_hours: e.duration_hours
      }));
    }
    
    // Get event dashboard summary
    const dashboardData = await apiFetch('/api/events/dashboard-summary');
    if (dashboardData) {
      state.eventsDashboard = dashboardData;
    }
    
    // Get historical event patterns for charts
    const historyData = await apiFetch('/api/events/historical-patterns?is_event_day=true');
    if (historyData && historyData.by_gate) {
      // Convert to chart-friendly format
      const gates = Object.keys(historyData.by_gate);
      const hourlyData = new Array(24).fill(0);
      
      gates.forEach(gate => {
        const patterns = historyData.by_gate[gate];
        patterns.forEach(p => {
          hourlyData[p.hour] += p.average_count;
        });
      });
      
      state.eventsHistory = {
        labels: Array.from({length: 24}, (_, i) => `${i}:00`),
        impact_scores: hourlyData.map(v => Math.round((v / gates.length) * 2)) // Normalize
      };
    }
  } catch (error) {
    console.error('Error syncing events:', error);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// ENHANCED EVENTS VIEW RENDERING
// ══════════════════════════════════════════════════════════════════════════════

function renderEventsView() {
  // Timeline
  const tl = document.getElementById('events-timeline');
  if (tl) {
    if (state.events.length) {
      tl.innerHTML = state.events.slice(0, 10).map(ev => `
        <div class="timeline-item">
          <span class="timeline-time">${ev.time}</span>
          <div class="timeline-dot" style="background:${getImpactColor(ev.impact)}"></div>
          <div class="timeline-content">
            <div class="t-title">${ev.title}</div>
            <div class="t-location">
              📍 ${ev.location} &nbsp;·&nbsp; 
              👥 ${ev.attendees.toLocaleString()} expected &nbsp;·&nbsp;
              ⏱️ ${ev.duration_hours}h
            </div>
            <div style="display:flex;gap:6px;margin-top:4px;align-items:center">
              <span class="t-impact impact-${ev.impact}">${ev.impact.toUpperCase()}</span>
              <span class="event-type-badge">${ev.type.toUpperCase()}</span>
              ${ev.status === 'active' ? '<span class="event-status-badge">🔴 LIVE</span>' : ''}
            </div>
          </div>
        </div>
      `).join('');
    } else {
      tl.innerHTML = '<p style="color:var(--text-muted);padding:12px 0;">No upcoming events</p>';
    }
  }
  
  // Impact list
  const il = document.getElementById('events-impact-list');
  if (il) {
    const highImpactEvents = state.events.filter(e => ['high', 'critical'].includes(e.impact));
    if (highImpactEvents.length) {
      il.innerHTML = highImpactEvents.map(ev => `
        <div class="impact-list-item">
          <div style="flex:1">
            <div style="font-size:0.82rem;font-weight:600">${ev.title}</div>
            <div style="font-size:0.7rem;color:var(--text-muted)">
              ${ev.time} · ${ev.attendees.toLocaleString()} pax · ${ev.type}
            </div>
          </div>
          <span class="impact-badge impact-${ev.impact}">${ev.impact.toUpperCase()}</span>
        </div>
      `).join('');
    } else {
      il.innerHTML = '<p style="color:var(--text-muted);padding:8px 0;">No high-impact events scheduled</p>';
    }
  }
  
  // Event history chart (show hourly crowd patterns during events)
  const ehc = document.getElementById('event-history-chart');
  if (ehc && state.eventsHistory.labels && state.eventsHistory.labels.length) {
    drawBarChart(ehc, state.eventsHistory.labels,
      [{ label: 'Avg Crowd During Events', color: '#7c3aed', data: state.eventsHistory.impact_scores }],
      { yMax: Math.max(...state.eventsHistory.impact_scores) * 1.2 || 100 });
  }
}

function getImpactColor(impact) {
  const colors = {
    'critical': '#ef4444',
    'high': '#f59e0b',
    'medium': '#eab308',
    'low': '#10b981'
  };
  return colors[impact] || '#6b7280';
}

// ══════════════════════════════════════════════════════════════════════════════
// ENHANCED ANALYTICS VIEW WITH REAL DATA
// ══════════════════════════════════════════════════════════════════════════════

async function renderAnalyticsView() {
  const container = document.getElementById('analytics-content');
  if (!container) return;
  
  // Fetch real analytics data
  const analyticsData = await apiFetch('/api/traffic/analytics');
  const eventsData = await apiFetch('/api/events/forecast?days_ahead=7');
  const shuttleDemand = await apiFetch('/api/events/shuttle-demand?hours_ahead=1');
  
  let html = '<div class="analytics-grid">';
  
  // Top KPI Cards
  html += `
    <div class="analytics-card">
      <h3>📊 System Performance</h3>
      ${analyticsData ? `
        <div class="kpi-grid">
          <div class="kpi-item">
            <div class="kpi-value">${analyticsData.total_entries || 0}</div>
            <div class="kpi-label">Total  Entries Today</div>
          </div>
          <div class="kpi-item">
            <div class="kpi-value">${Math.round(analyticsData.avg_congestion || 0)}%</div>
            <div class="kpi-label">Avg Congestion</div>
          </div>
        </div>
      ` : '<p>Loading...</p>'}
    </div>
  `;
  
  // Event Forecast Card
  if (eventsData && eventsData.forecast) {
    html += `
      <div class="analytics-card">
        <h3>🎉 Upcoming Events Impact</h3>
        <div class="event-forecast-list">
          ${eventsData.forecast.slice(0, 5).map(f => `
            <div class="forecast-item">
              <div class="forecast-header">
                <strong>${f.event.name}</strong>
                <span class="forecast-time">in ${f.hours_until.toFixed(1)}h</span>
              </div>
              <div class="forecast-details">
                <span class="impact-badge impact-${f.event.impact_level}">${f.event.impact_level.toUpperCase()}</span>
                <span>👥 ${f.expected_peak_crowd} peak crowd</span>
                <span class="priority-badge priority-${f.preparation_priority.toLowerCase()}">${f.preparation_priority}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }
  
  // Shuttle Demand Forecast
  if (shuttleDemand && shuttleDemand.demand) {
    const demand = shuttleDemand.demand;
    html += `
      <div class="analytics-card">
        <h3>🚌 Shuttle Demand Forecast</h3>
        <div class="shuttle-forecast">
          <div class="forecast-stat">
            <span class="stat-label">Predicted Crowd:</span>
            <span class="stat-value">${demand.total_predicted_crowd}</span>
          </div>
          <div class="forecast-stat">
            <span class="stat-label">Shuttles Needed:</span>
            <span class="stat-value">${demand.shuttles_needed}</span>
          </div>
          <div class="forecast-recommendation">
            ${demand.recommendation}
          </div>
          ${demand.high_demand_gates.length ? `
            <div class="high-demand-gates">
              <strong>High Demand Gates:</strong>
              ${demand.high_demand_gates.map(g => `<span class="gate-badge">Gate ${g.gate_id} (${Math.round(g.predicted_density)}%)</span>`).join('')}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }
  
  html += '</div>';
  
  container.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════════════
// ADD CSS STYLES FOR NEW COMPONENTS
// ══════════════════════════════════════════════════════════════════════════════

const enhancedStyles = `
<style>
.event-type-badge {
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  font-weight: 600;
}

.event-status-badge {
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  font-weight: 600;
  animation: pulse 2s infinite;
}

.analytics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 20px;
  padding: 20px;
}

.analytics-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.analytics-card h3 {
  margin: 0 0 16px 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.kpi-item {
  text-align: center;
  padding: 12px;
  background: rgba(124, 58, 237, 0.05);
  border-radius: 8px;
}

.kpi-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--accent-purple);
}

.kpi-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 4px;
}

.event-forecast-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.forecast-item {
  padding: 12px;
  background: rgba(124, 58, 237, 0.05);
  border-radius: 8px;
  border-left: 3px solid var(--accent-purple);
}

.forecast-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.forecast-time {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.forecast-details {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  font-size: 0.85rem;
}

.priority-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 700;
}

.priority-urgent {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.priority-high {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.priority-medium {
  background: rgba(234, 179, 8, 0.1);
  color: #eab308;
}

.priority-normal {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.shuttle-forecast {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.forecast-stat {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.05);
  border-radius: 6px;
}

.stat-label {
  color: var(--text-secondary);
  font-size: 0.9rem;
}

.stat-value {
  font-weight: 700;
  color: var(--accent-blue);
  font-size: 1.1rem;
}

.forecast-recommendation {
  padding: 12px;
  background: rgba(16, 185, 129, 0.1);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 0.9rem;
  border-left: 3px solid #10b981;
}

.high-demand-gates {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 0.85rem;
}

.gate-badge {
  padding: 4px 10px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.8rem;
}
</style>
`;

// Inject enhanced styles into the document
if (typeof document !== 'undefined') {
  const styleEl = document.createElement('div');
  styleEl.innerHTML = enhancedStyles;
  document.head.appendChild(styleEl.querySelector('style'));
}

console.log('✅ Frontend enhancements loaded with event-aware predictions and charts');
