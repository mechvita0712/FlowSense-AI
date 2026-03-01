/* =============================================
   SMART CAMPUS MOBILITY SYSTEM â€” AI ENGINE
   ============================================= */
'use strict';

// â”€â”€â”€ BACKEND API INTEGRATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function resolveBackendUrl() {
  const explicit = window.BACKEND_URL || window.__BACKEND_URL;
  if (explicit) return explicit;
  const { origin, port } = window.location;
  if (port === '3000') return 'http://127.0.0.1:5000';
  return origin;
}
const BACKEND_URL = resolveBackendUrl();

// WebSocket connection
let socket = null;
let wsConnected = false;

const backendStatus = {
  online: false,
  lastCheck: 0,
  indicator: null,
};

const GATE_EMOJIS = {
  A: '🏫', B: '📚', C: '🏟️', D: '🏠', E: '🔬',
  F: '🍽️', G: '🚗', H: '🎭', I: '🧪', J: '🚉',
};

function normalizeGate(g) {
  const id = String(g.gate_id || g.id || '?').toUpperCase();
  return {
    id,
    name: g.name || `Gate ${id}`,
    location: g.location || 'Campus Zone',
    emoji: GATE_EMOJIS[id] || '📍',
    density: Math.round(parseFloat(g.density ?? 0)),
    predicted: Math.round(parseFloat(g.predicted_next_hour ?? g.predicted ?? g.density ?? 0)),
    entries: parseInt(g.entries ?? 0, 10),
    trend: Array.isArray(g.trend) ? g.trend : [],
  };
}

function normalizeShuttle(s) {
  const id = s.shuttle_id || s.id || 'S?';
  return {
    id,
    name: s.name || id,
    route: s.route || 'Campus Route',
    load: parseFloat(s.load ?? 0),
    capacity: parseInt(s.capacity ?? 45, 10),
    status: s.status || 'active',
    nextStop: s.next_stop || s.nextStop || '—',
    eta: s.eta_min ?? s.eta ?? 0,
  };
}

function mapRouteRecommendation(r) {
  const saving = parseInt(r.time_saving_min ?? 0, 10);
  const density = parseFloat(r.current_density ?? 0);
  return {
    from: r.from || 'Campus Zone',
    to: r.to || ('Gate ' + (r.gate_id || '?')),
    recommended: r.recommended_path || 'Use alternate path',
    avoid: r.avoid || 'Direct route',
    savings: `${saving} min`,
    tags: r.priority === 'high' ? ['High Priority', 'Less Crowd'] : ['Less Crowd', 'Faster'],
    score: Math.max(60, 100 - Math.round(density * 0.4)),
    currentDensity: density,
  };
}

// Generic fetch helper â€” returns parsed JSON or null on any error
async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(BACKEND_URL + path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// Show a small backend-status pill in the top-bar
function renderBackendStatus(online) {
  let pill = document.getElementById('backend-status-pill');
  if (!pill) {
    pill = document.createElement('div');
    pill.id = 'backend-status-pill';
    pill.style.cssText =
      'display:flex;align-items:center;gap:6px;font-size:0.72rem;font-weight:600;' +
      'padding:6px 12px;border-radius:100px;border:1px solid;white-space:nowrap;';
    const bar = document.querySelector('.top-bar-right');
    if (bar) bar.prepend(pill);
  }
  if (online) {
    pill.style.background = 'rgba(16,185,129,0.1)';
    pill.style.borderColor = 'rgba(16,185,129,0.35)';
    pill.style.color = '#10b981';
    pill.innerHTML = '<span style="width:7px;height:7px;border-radius:50%;background:#10b981;display:inline-block;"></span> Backend Live';
  } else {
    pill.style.background = 'rgba(245,158,11,0.1)';
    pill.style.borderColor = 'rgba(245,158,11,0.35)';
    pill.style.color = '#f59e0b';
    pill.innerHTML = '<span style="width:7px;height:7px;border-radius:50%;background:#f59e0b;display:inline-block;"></span> Simulation Mode';
  }
}

// â”€â”€ Health check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function checkBackend() {
  const data = await apiFetch('/api/health');
  backendStatus.online = !!(data && data.status === 'ok');
  renderBackendStatus(backendStatus.online);
  return backendStatus.online;
}

// â”€â”€ Pull gate data from Flask â†’ merge into state.gates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function syncGatesFromBackend() {
  state.loading.gates = true;
  const data = await apiFetch('/api/traffic/gates');
  if (!data || !Array.isArray(data.gates)) {
    state.loading.gates = false;
    return;
  }
  state.gates = data.gates.map(normalizeGate);
  if (!state.heatZones.length) initHeatZones();
  state.loading.gates = false;
}

// â”€â”€ Pull shuttle data from Flask â†’ merge into state.shuttles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function syncShuttlesFromBackend() {
  state.loading.shuttles = true;
  const data = await apiFetch('/api/traffic/shuttles');
  const fleet = data && Array.isArray(data.fleet) ? data.fleet : [];
  if (!fleet.length) {
    state.loading.shuttles = false;
    return;
  }
  state.shuttles = fleet.map(normalizeShuttle);
  state.loading.shuttles = false;
}

// â”€â”€ Pull route recommendations from Flask â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function syncRoutesFromBackend() {
  const data = await apiFetch('/api/traffic/routes');
  const list = data && Array.isArray(data.recommendations) ? data.recommendations : [];
  state.routes = list.map(mapRouteRecommendation);
}

// â”€â”€ Pull congestion alerts from Flask â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function syncAlertsFromBackend() {
  const data = await apiFetch('/api/traffic/congestion');
  const alerts = data && Array.isArray(data.alerts) ? data.alerts : [];
  state.alerts = alerts.slice(0, 8).map((a, idx) => ({
    id: 'backend-alert-' + idx,
    severity: a.severity,
    backendLoc: a.location,
    title: a.severity === 'critical' ? `CRITICAL: ${a.location}` : `Warning: ${a.location}`,
    desc: a.message + (a.action ? ' — ' + a.action : ''),
    time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
  }));
  setEl('alert-badge', state.alerts.length || '');
}

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
    
    // Get historical event patterns for charts
    const historyData = await apiFetch('/api/events/historical-patterns?is_event_day=true');
    if (historyData && historyData.by_gate) {
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
        impact_scores: hourlyData.map(v => Math.round((v / gates.length) * 2))
      };
    }
  } catch (error) {
    console.error('Error syncing events:', error);
  }
}

async function syncAnalyticsFromBackend() {
  const data = await apiFetch('/api/traffic/analytics');
  state.analytics = data || null;
}

// â”€â”€ Push live simulated data point to Flask (keeps DB populated) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

// â”€â”€ Master sync â€” called every few ticks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function syncWithBackend() {
  if (!backendStatus.online) {
    // Re-check health every 10s
    if (Date.now() - backendStatus.lastCheck > 10000) {
      backendStatus.lastCheck = Date.now();
      await checkBackend();
    }
    return;
  }
  await Promise.all([
    syncGatesFromBackend(),
    syncShuttlesFromBackend(),
  ]);
}

// â”€â”€ Slower sync (every 15s) for routes and alerts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function slowSyncWithBackend() {
  if (!backendStatus.online) return;
  await Promise.all([
    syncRoutesFromBackend(),
    syncAlertsFromBackend(),
    syncEventsFromBackend(),
    syncAnalyticsFromBackend(),
  ]);
}


// â”€â”€â”€ STATE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const state = {
  currentView: 'dashboard',
  tick: 0,
  alerts: [],
  alertFilter: 'all',
  showRoutes: true,
  showShuttles: true,
  thresholds: { critical: 80, warning: 60, shuttle: 85 },
  gates: [],
  shuttles: [],
  events: [],
  eventsHistory: { labels: [], impact_scores: [] },
  routes: [],
  latestSummary: null,
  analytics: null,
  heatZones: [],
  mlHistory: [],
  loading: {
    kpi: false,
    gates: false,
    shuttles: false,
    routes: false,
    recommendations: false,
    forecast: false,
    alerts: false,
  },
};

// â”€â”€â”€ INIT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function bootstrapFromBackend() {
  await Promise.all([
    syncGatesFromBackend(),
    syncShuttlesFromBackend(),
    syncRoutesFromBackend(),
    syncAlertsFromBackend(),
    syncEventsFromBackend(),
    syncAnalyticsFromBackend(),
  ]);
}

// â"€â"€â"€ WEBSOCKET REAL-TIME UPDATES â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
function initWebSocket() {
  if (typeof io === 'undefined') {
    console.warn('Socket.IO client not loaded. Real-time updates disabled.');
    return;
  }

  socket = io(BACKEND_URL + '/ws/traffic', {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10
  });

  socket.on('connect', () => {
    console.log('WebSocket connected');
    wsConnected = true;
    renderWebSocketStatus();
  });

  socket.on('disconnect', () => {
    console.log('WebSocket disconnected');
    wsConnected = false;
    renderWebSocketStatus();
  });

  socket.on('crowd_update', (data) => {
    console.log('Crowd update received:', data);
    updateGateFromWebSocket(data);
  });

  socket.on('gate_full_alert', (data) => {
    console.log('Gate full alert received:', data);
    showRedirectionAlert(data);
    playNotificationSound();
  });

  socket.on('capacity_updated', (data) => {
    console.log('Capacity updated:', data);
    syncGatesFromBackend();
  });

  socket.on('global_capacity_updated', (data) => {
    console.log('Global capacity updated:', data);
    syncGatesFromBackend();
  });

  socket.on('redirect_notification', (data) => {
    console.log('Redirect notification:', data);
    showRedirectionAlert(data);
  });
}

function renderWebSocketStatus() {
  const topBar = document.querySelector('.top-bar-right');
  if (!topBar) return;

  let indicator = document.getElementById('ws-status-indicator');
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.id = 'ws-status-indicator';
    indicator.className = 'ws-status-indicator';
    topBar.insertBefore(indicator, topBar.firstChild);
  }

  if (wsConnected) {
    indicator.className = 'ws-status-indicator connected';
    indicator.innerHTML = '<span class="ws-status-dot"></span> Live Updates';
  } else {
    indicator.className = 'ws-status-indicator disconnected';
    indicator.innerHTML = '<span class="ws-status-dot"></span> Offline';
  }
}

function updateGateFromWebSocket(data) {
  const gate = state.gates.find(g => g.id === data.gate_id);
  if (gate) {
    gate.density = data.density;
    gate.entries = data.count;
    renderAll();
  }
}

function showRedirectionAlert(data) {
  const modal = document.getElementById('redirect-modal');
  const messageEl = modal.querySelector('.redirect-message');
  
  const message = data.message || `Gate ${data.gate_id} is FULL. Please redirect to Gate ${data.redirect_to}`;
  messageEl.innerHTML = `
    <strong style="color: #ef4444; font-size: 1.5rem;">⚠️ ${data.gate_id ? 'Gate ' + data.gate_id : 'Gate'} is FULL</strong>
    <br><br>
    <strong style="color: #10b981; font-size: 1.25rem;">➡️ Please redirect to Gate ${data.redirect_to}</strong>
    <br><br>
    <span style="color: var(--text-secondary);">Redirecting will reduce congestion and improve flow.</span>
  `;
  
  modal.style.display = 'flex';
}

function closeRedirectModal() {
  const modal = document.getElementById('redirect-modal');
  modal.style.display = 'none';
}

function playNotificationSound() {
  try {
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuAyvDZjDsIF2Gt7O9+MggfeLLo77JqHwYulfHY2YVCBxh00OnzxWwiBSmBzPLalisPFGm46e+tZCEFM4rQ8dGFNggZd8Lr8btvJAc4jtzy0YxBCRl+z+vvs2clBTCS1PHRgzUIGHa95O6kWhwHKoHO8t2LQwkbacLq8bBkIQU0jdTy0YU0CBhzvuvwqF0cBi6H0O7cjkEJGXTA6vGzaiIFM4vQ8tOLQQkZeb/n8bJlIgY2j9Lx0oY1CBhy0O3ypGEeBzSKz/HZjkYKG2bE7PGvZCEFM5HU8tGGOAcZdL3o8aViHAY0jNDu1YxBCRl+zu3wqWEeBzOIz+3ZjkEJG23D6/GyaCMGOJDT8M+IPwgXebv r8LBlIgY5kdPxz4Y2CBZzv+fypGIcBzaLz+/VjkEJGXBA7POuZCEFNU/U8dGGNwgYc8Dp8K1jHgczj9Du1YxCCRh0wOrxsGckBjiO0fHPiD8IF3m76/CtZSMGN4/S8M+HNwgWdb/o8qViHAY2i8/u1Y5BCRdvwOrxsGgjBjmP0vDPiD0HF3m66/CsZCIGNI7Q8NSLPwkXdsDq8q9jHgczjs/u1YxBCRdvv+rxsGcjBjiO0e/Phi8EF3i55OWsZCADNI7Q79SLPwkXdsHp8a9iHQU0js/u1YxBCRdvv+nxsGcjBTiO0e/Phi8EF3i55eWsZCACNI3Q79SLPgkWd7/p8K9hHQQ0js/t1YtACRdvv+nxr2ciBziO0e/Phi4EFnm55OWsZB8BNI3Q79SLPgkWd7/p8K9hHQQ0js/s1YtACRdvv+nwr2ciBziO0e/Phi4EFnm45OWsZB8ANI3Q79SLPgkWd7/p8K9hHQQ0js/s1YtACRdvv+nwr2ciBziO0e/Phi4EFnm45OWsZB8ANI3Q79SLPgkWd7/p8K9hHQQ0js/s1YtACRdvv+nwr2ciBziO0e/Phis=');
    audio.play().catch(e => console.log('Could not play notification sound:', e));
  } catch (e) {
    console.log('Audio playback error:', e);
  }
}

async function init() {
  seedMLHistory();
  bindNavigation();
  bindMenuToggle();
  bindThresholdSliders();
  startLiveClock();
  await checkBackend();
  if (backendStatus.online) {
    await bootstrapFromBackend();
    initWebSocket();  // Initialize WebSocket connection
  }
  initHeatZones();
  renderAll();
  startSimulationLoop();
  setInterval(slowSyncWithBackend, 15000);
}

// â”€â”€â”€ ML PREDICTION ENGINE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Simulated Polynomial + Seasonal + Gaussian noise ML model
function mlPredict(hourOffset, baseDensity) {
  const now = new Date();
  const h = now.getHours() + hourOffset;
  // Bimodal peak curve (morning 8â€“10, evening 16â€“18)
  const morningPeak = gaussianPeak(h, 9, 1.5);
  const eveningPeak = gaussianPeak(h, 17, 1.8);
  const lunchPeak = gaussianPeak(h, 13, 0.8);
  const seasonal = (morningPeak * 0.7 + eveningPeak * 1.0 + lunchPeak * 0.6) * 60;
  const noise = (Math.random() - 0.5) * 6;
  return Math.min(99, Math.max(5, Math.round(baseDensity * 0.4 + seasonal + noise)));
}

function gaussianPeak(x, mean, sigma) {
  return Math.exp(-0.5 * Math.pow((x - mean) / sigma, 2));
}

function predictNextHourCongestion() {
  if (!state.gates.length) return [];
  const points = [];
  for (let i = 0; i <= 6; i++) {
    const avg = state.gates.reduce((s, g) => s + mlPredict(i * 0.5, g.density), 0) / state.gates.length;
    points.push(+avg.toFixed(1));
  }
  return points;
}

function seedMLHistory() {
  const now = new Date();
  for (let i = 11; i >= 0; i--) {
    const h = now.getHours() - i;
    const morningPeak = gaussianPeak(h, 9, 1.5);
    const eveningPeak = gaussianPeak(h, 17, 1.8);
    const lunchPeak = gaussianPeak(h, 13, 0.8);
    const v = Math.min(95, Math.max(10, Math.round((morningPeak * 0.7 + eveningPeak + lunchPeak * 0.6) * 60 + (Math.random() - 0.5) * 8)));
    state.mlHistory.push(v);
  }
}

// â”€â”€â”€ HEATMAP DATA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function initHeatZones() {
  const zones = [
    { name: 'Main Entrance', x: 0.12, y: 0.15, r: 0.10 },
    { name: 'Academic Block', x: 0.45, y: 0.20, r: 0.12 },
    { name: 'Sports Complex', x: 0.82, y: 0.30, r: 0.11 },
    { name: 'Cafeteria', x: 0.55, y: 0.55, r: 0.09 },
    { name: 'Library', x: 0.25, y: 0.60, r: 0.08 },
    { name: 'Lab Block', x: 0.68, y: 0.65, r: 0.10 },
    { name: 'Residential', x: 0.15, y: 0.82, r: 0.09 },
    { name: 'Admin Block', x: 0.75, y: 0.15, r: 0.08 },
    { name: 'Parking', x: 0.90, y: 0.80, r: 0.07 },
    { name: 'Amphitheatre', x: 0.40, y: 0.80, r: 0.09 },
  ];
  state.heatZones = zones.map((z, i) => ({
    ...z,
    density: state.gates.length
      ? state.gates[i % state.gates.length].density + (Math.random() - 0.5) * 15
      : 20 + Math.random() * 25,
  }));
}

// â”€â”€â”€ CONGESTION LEVEL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function levelOf(pct) {
  if (pct >= 80) return 'critical';
  if (pct >= 60) return 'high';
  if (pct >= 30) return 'moderate';
  return 'low';
}

function colorOf(pct, alpha = 1) {
  if (pct >= 80) return `rgba(239,68,68,${alpha})`;
  if (pct >= 60) return `rgba(249,115,22,${alpha})`;
  if (pct >= 30) return `rgba(245,158,11,${alpha})`;
  return `rgba(16,185,129,${alpha})`;
}

// â”€â”€â”€ NAVIGATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const pageTitles = {
  dashboard: ['Command Center', 'Real-time campus mobility intelligence'],
  map: ['Live Campus Map', 'Crowd density heatmap & route overlay'],
  gates: ['Gate Congestion', 'AI-powered entry point monitoring & prediction'],
  shuttle: ['Shuttle Forecast', 'ML-driven demand prediction & fleet management'],
  routes: ['Route Advisor', 'Smart mobility nudges & alternate path recommendations'],
  events: ['Events & Schedule', 'Proactive congestion forecasting for campus events'],
  alerts: ['Smart Alert Center', 'Threshold-based notifications & anomaly detection'],
  analytics: ['Analytics', 'Historical patterns, AI model performance & impact metrics'],
  admin: ['Admin Settings', 'Capacity management & system configuration'],
};

function switchView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const view = document.getElementById('view-' + name);
  const navEl = document.getElementById('nav-' + name);
  if (view) view.classList.add('active');
  if (navEl) navEl.classList.add('active');
  const [title, sub] = pageTitles[name] || ['Dashboard', ''];
  document.getElementById('page-title').textContent = title;
  document.getElementById('page-subtitle').textContent = sub;
  state.currentView = name;
  renderViewSpecific(name);
}

function bindNavigation() {
  const navItems = Array.from(document.querySelectorAll('.nav-item'));
  navItems.forEach((item, idx) => {
    item.addEventListener('click', e => {
      e.preventDefault();
      switchView(item.dataset.view);
    });
    item.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = navItems[(idx + 1) % navItems.length];
        next.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = navItems[(idx - 1 + navItems.length) % navItems.length];
        prev.focus();
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        switchView(item.dataset.view);
      }
    });
  });
}

function bindMenuToggle() {
  document.getElementById('menu-toggle').addEventListener('click', () => {
    const sb = document.getElementById('sidebar');
    const mc = document.querySelector('.main-content');
    sb.classList.toggle('collapsed');
    mc.classList.toggle('expanded');
  });
}

// â”€â”€â”€ RENDER ALL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderAll() {
  updateKPIs();
  renderMiniHeatmap();
  renderForecastChart();
  renderGateListMini();
  renderAlertsMini();
  renderShuttleMini();
  renderRouteNudgesMini();
  renderViewSpecific(state.currentView);
}

function renderViewSpecific(name) {
  if (name === 'map') renderFullMap();
  if (name === 'gates') renderGatesView();
  if (name === 'shuttle') renderShuttleView();
  if (name === 'routes') renderRoutesView();
  if (name === 'events') renderEventsView();
  if (name === 'alerts') renderAlertsView();
  if (name === 'analytics') renderAnalyticsView();
  if (name === 'admin') renderAdminView();
}

// â”€â”€â”€ KPIs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function updateKPIs() {
  state.loading.kpi = true;
  setEl('kpi-people-val', 'Loading...');
  setEl('kpi-congestion-val', 'Loading...');
  setEl('kpi-shuttle-val', 'Loading...');
  setEl('kpi-alerts-val', 'Loading...');
  setEl('kpi-alerts-change', 'Loading...');
  try {
    const summary = await apiFetch('/api/traffic/dashboard/summary');
    if (!summary) {
      setEl('kpi-people-val', 'No Data Available');
      setEl('kpi-congestion-val', 'No Data Available');
      setEl('kpi-shuttle-val', 'No Data Available');
      setEl('kpi-alerts-val', 'No Data Available');
      setEl('kpi-alerts-change', 'No Data Available');
      return;
    }
    state.latestSummary = summary;
    setEl('kpi-people-val', summary.total_people?.toLocaleString() ?? 'No Data Available');
    setEl('kpi-congestion-val', (summary.avg_congestion ?? 'No Data Available') + '%');
    setEl('kpi-shuttle-val', summary.active_shuttles ?? 'No Data Available');
    setEl('kpi-alerts-val', summary.active_alerts ?? 'No Data Available');
    setEl('kpi-alerts-change', `AI Confidence: ${summary.ai_confidence ?? 'No Data Available'}%`);
    const pill = document.getElementById('campus-status-pill');
    const ind = pill.querySelector('.status-indicator');
    const lvl = levelOf(summary.avg_congestion ?? 0);
    ind.className = 'status-indicator ' + lvl;
    pill.lastChild.textContent = ' ' + ({ low: 'Clear', moderate: 'Moderate Traffic', high: 'Heavy Traffic', critical: 'CRITICAL' }[lvl]);
    setEl('alert-badge', summary.active_alerts ?? '');
  } catch (e) {
    setEl('kpi-people-val', 'Error');
    setEl('kpi-congestion-val', 'Error');
    setEl('kpi-shuttle-val', 'Error');
    setEl('kpi-alerts-val', 'Error');
    setEl('kpi-alerts-change', 'Error');
  } finally {
    state.loading.kpi = false;
  }
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// â”€â”€â”€ MINI HEATMAP (Canvas) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderMiniHeatmap() {
  const canvas = document.getElementById('heatmap-canvas');
  if (!canvas) return;
  if (state.loading.gates) {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    canvas.getContext('2d').fillText('Loading...', 10, 20);
    return;
  }
  if (!state.gates.length) {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    canvas.getContext('2d').fillText('No Data Available', 10, 20);
    return;
  }
  drawCampusMap(canvas, 700, 350, false);
}

function renderFullMap() {
  const canvas = document.getElementById('full-map-canvas');
  if (!canvas) return;
  drawCampusMap(canvas, 1000, 560, true);
}

function drawCampusMap(canvas, w, h, full) {
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');

  // Background
  ctx.fillStyle = '#0a1628';
  ctx.fillRect(0, 0, w, h);

  // Grid lines
  ctx.strokeStyle = 'rgba(59,130,246,0.05)';
  ctx.lineWidth = 1;
  for (let x = 0; x < w; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
  for (let y = 0; y < h; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }

  // Draw roads
  ctx.strokeStyle = 'rgba(100,130,200,0.18)';
  ctx.lineWidth = full ? 10 : 7;
  ctx.lineCap = 'round';
  const roads = [
    [[0.12, 0.15], [0.45, 0.20], [0.82, 0.30]],
    [[0.12, 0.15], [0.25, 0.60], [0.15, 0.82]],
    [[0.82, 0.30], [0.75, 0.15], [0.68, 0.65]],
    [[0.45, 0.20], [0.55, 0.55], [0.40, 0.80]],
    [[0.55, 0.55], [0.75, 0.15]],
    [[0.25, 0.60], [0.55, 0.55], [0.68, 0.65]],
    [[0.15, 0.82], [0.40, 0.80], [0.90, 0.80]],
  ];
  roads.forEach(pts => {
    ctx.beginPath();
    ctx.moveTo(pts[0][0] * w, pts[0][1] * h);
    pts.slice(1).forEach(p => ctx.lineTo(p[0] * w, p[1] * h));
    ctx.stroke();
  });

  // Shuttle route overlay
  if (state.showRoutes) {
    ctx.strokeStyle = 'rgba(6,182,212,0.35)';
    ctx.lineWidth = full ? 4 : 3;
    ctx.setLineDash([8, 5]);
    ctx.beginPath();
    ctx.moveTo(0.12 * w, 0.15 * h);
    ctx.lineTo(0.45 * w, 0.20 * h);
    ctx.lineTo(0.82 * w, 0.30 * h);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // AI alternate route
  if (state.showRoutes) {
    ctx.strokeStyle = 'rgba(124,58,237,0.45)';
    ctx.lineWidth = full ? 3 : 2;
    ctx.setLineDash([5, 7]);
    ctx.beginPath();
    ctx.moveTo(0.12 * w, 0.15 * h);
    ctx.lineTo(0.25 * w, 0.60 * h);
    ctx.lineTo(0.55 * w, 0.55 * h);
    ctx.lineTo(0.68 * w, 0.65 * h);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Heatmap zones
  state.heatZones.forEach(zone => {
    const cx = zone.x * w, cy = zone.y * h;
    const r = zone.r * Math.min(w, h);
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    const c = colorOf(zone.density, 0.55);
    const c0 = colorOf(zone.density, 0.0);
    grad.addColorStop(0, c);
    grad.addColorStop(1, c0);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();

    // Icon / dot
    ctx.fillStyle = colorOf(zone.density, 0.9);
    ctx.beginPath();
    ctx.arc(cx, cy, full ? 8 : 6, 0, Math.PI * 2);
    ctx.fill();

    if (full) {
      ctx.font = '600 11px Inter, sans-serif';
      ctx.fillStyle = 'rgba(240,244,255,0.85)';
      ctx.textAlign = 'center';
      ctx.fillText(zone.name, cx, cy + 22);
      ctx.font = '700 12px JetBrains Mono, monospace';
      ctx.fillStyle = colorOf(zone.density);
      ctx.fillText(Math.round(zone.density) + '%', cx, cy + 36);
    }
  });

  // Gate markers
  state.gates.forEach(gate => {
    const zone = state.heatZones.find(z => z.name.includes(gate.location.split(',')[0].trim())) || state.heatZones[0];
    // Gate pins drawn as part of zones; just label on full map
    if (!full) return;
  });

  // Shuttle positions (live dots)
  if (state.showShuttles) {
    state.shuttles.filter(s => s.status === 'active').forEach((s, i) => {
      const t = (state.tick * 0.012 + i * (Math.PI * 2 / 5)) % (Math.PI * 2);
      const cx = (0.3 + 0.4 * Math.cos(t)) * w;
      const cy = (0.3 + 0.3 * Math.sin(t)) * h;
      ctx.fillStyle = '#00d4ff';
      ctx.beginPath();
      ctx.arc(cx, cy, full ? 7 : 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#080c14';
      ctx.font = `bold ${full ? 10 : 8}px Inter`;
      ctx.textAlign = 'center';
      ctx.fillText('🚌', cx, cy + (full ? 4 : 3));
    });
  }
}

function toggleRoutes(v) { state.showRoutes = v; renderFullMap(); }
function toggleShuttles(v) { state.showShuttles = v; renderFullMap(); }

// â”€â”€â”€ FORECAST CHART â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function renderForecastChart() {
  const canvas = document.getElementById('forecast-chart');
  if (!canvas) return;
  state.loading.forecast = true;
  setEl('peak-val', 'Loading...');
  setEl('peak-time', 'Loading...');
  setEl('ai-confidence', 'Loading...');
  try {
    const forecast = await apiFetch('/api/traffic/forecast');
    if (!forecast || !forecast.hourly || !forecast.hourly.length) {
      canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
      canvas.getContext('2d').fillText('No Data Available', 10, 20);
      setEl('peak-val', 'No Data Available');
      setEl('peak-time', 'No Data Available');
      setEl('ai-confidence', 'No Data Available');
      return;
    }
    const labels = forecast.hourly.map((_, i) => {
      const d = new Date(); d.setMinutes(d.getMinutes() + i * 30);
      return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
    });
    drawLineChart(canvas, labels, [
      { label: 'Predicted Congestion', data: forecast.hourly, color: '#7c3aed', fill: true },
      { label: 'Current Level', data: new Array(forecast.hourly.length).fill(forecast.predicted_max ?? 0), color: 'rgba(59,130,246,0.5)', dash: [4, 4], fill: false }
    ], { yMax: 100, unit: '%' });
    setEl('peak-val', forecast.predicted_max + '%');
    setEl('peak-time', forecast.peak_time ?? 'No Data Available');
    setEl('ai-confidence', forecast.confidence + '%');
  } catch (e) {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    canvas.getContext('2d').fillText('Error', 10, 20);
    setEl('peak-val', 'Error');
    setEl('peak-time', 'Error');
    setEl('ai-confidence', 'Error');
  } finally {
    state.loading.forecast = false;
  }
}

// â”€â”€â”€ GENERIC LINE CHART â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function drawLineChart(canvas, labels, datasets, opts = {}) {
  const W = canvas.offsetWidth || 400;
  const H = 200;
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const pad = { top: 16, right: 16, bottom: 36, left: 44 };
  const iW = W - pad.left - pad.right;
  const iH = H - pad.top - pad.bottom;
  const yMax = opts.yMax || 100;
  const unit = opts.unit || '';

  ctx.fillStyle = 'transparent';
  ctx.fillRect(0, 0, W, H);

  // Grid
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + iH * (1 - i / 4);
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + iW, y); ctx.stroke();
    ctx.fillStyle = 'rgba(139,159,193,0.6)';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(yMax * i / 4) + unit, pad.left - 6, y + 3);
  }

  // X Labels
  ctx.fillStyle = 'rgba(139,159,193,0.7)';
  ctx.font = '10px Inter, sans-serif';
  ctx.textAlign = 'center';
  labels.forEach((lbl, i) => {
    const x = pad.left + (i / (labels.length - 1 || 1)) * iW;
    ctx.fillText(lbl, x, H - 8);
  });

  // Datasets
  datasets.forEach(ds => {
    const pts = ds.data.map((v, i) => ({
      x: pad.left + (i / (ds.data.length - 1 || 1)) * iW,
      y: pad.top + iH * (1 - v / yMax)
    }));
    ctx.save();
    if (ds.dash) ctx.setLineDash(ds.dash);
    ctx.strokeStyle = ds.color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    pts.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
    ctx.stroke();

    if (ds.fill) {
      ctx.lineTo(pts[pts.length - 1].x, pad.top + iH);
      ctx.lineTo(pts[0].x, pad.top + iH);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + iH);
      grad.addColorStop(0, ds.color.replace(')', ',0.3)').replace('rgb', 'rgba'));
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // Dots
    ctx.setLineDash([]);
    pts.forEach(pt => {
      ctx.fillStyle = ds.color;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  });
}

// â”€â”€â”€ BAR CHART â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function drawBarChart(canvas, labels, datasets, opts = {}) {
  const W = canvas.offsetWidth || 400;
  const H = 220;
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const pad = { top: 16, right: 16, bottom: 40, left: 44 };
  const iW = W - pad.left - pad.right;
  const iH = H - pad.top - pad.bottom;
  const yMax = opts.yMax || 100;
  const n = labels.length;
  const dsCount = datasets.length;
  const groupW = iW / n;
  const barW = (groupW * 0.7) / dsCount;

  ctx.fillStyle = 'transparent';
  ctx.fillRect(0, 0, W, H);

  // Grid
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + iH * (1 - i / 4);
    ctx.strokeStyle = 'rgba(255,255,255,0.05)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + iW, y); ctx.stroke();
    ctx.fillStyle = 'rgba(139,159,193,0.6)'; ctx.font = '10px Inter'; ctx.textAlign = 'right';
    ctx.fillText(Math.round(yMax * i / 4) + '%', pad.left - 6, y + 3);
  }

  labels.forEach((lbl, i) => {
    const gx = pad.left + i * groupW + groupW * 0.15;
    datasets.forEach((ds, di) => {
      const val = ds.data[i] || 0;
      const bh = (val / yMax) * iH;
      const bx = gx + di * barW;
      const by = pad.top + iH - bh;
      const grad = ctx.createLinearGradient(0, by, 0, by + bh);
      const c = ds.color || '#3b82f6';
      grad.addColorStop(0, c); grad.addColorStop(1, c + '66');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(bx, by, barW - 2, bh, [3, 3, 0, 0]);
      ctx.fill();
    });
    ctx.fillStyle = 'rgba(139,159,193,0.7)'; ctx.font = '9px Inter'; ctx.textAlign = 'center';
    ctx.fillText(lbl, pad.left + (i + 0.5) * groupW, H - 8);
  });
}

async function drawDonutChart(canvas, labels = null, values = null, colors = null) {
  const size = Math.min(canvas.offsetWidth || 280, 260);
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, size, size);
  ctx.fillText('Loading...', 10, 20);
  try {
    let chartLabels = labels;
    let chartValues = values;
    let chartColors = colors;

    if (!Array.isArray(chartLabels) || !Array.isArray(chartValues)) {
      const shuttlesRes = await apiFetch('/api/traffic/shuttles');
      const fleet = shuttlesRes && Array.isArray(shuttlesRes.fleet) ? shuttlesRes.fleet : [];
      if (!fleet.length) {
        ctx.clearRect(0, 0, size, size);
        ctx.fillText('No Data Available', 10, 20);
        return;
      }
      const routeCounts = {};
      fleet.forEach(s => {
        const route = s.route || 'Unknown Route';
        routeCounts[route] = (routeCounts[route] || 0) + 1;
      });
      const top = Object.entries(routeCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 4);
      chartLabels = top.map(([route]) => route);
      chartValues = top.map(([, count]) => count);
    }

    if (!Array.isArray(chartColors)) {
      chartColors = ['#3b82f6', '#7c3aed', '#10b981', '#f59e0b', '#ef4444', '#6b7280'];
    }

    const data = chartValues;
    const cx = size / 2, cy = size / 2, ro = size * 0.38, ri = size * 0.24;
    const total = data.reduce((a, b) => a + b, 0);
    let angle = -Math.PI / 2;
    data.forEach((v, i) => {
      const sweep = total === 0 ? 0 : (v / total) * (Math.PI * 2);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, ro, angle, angle + sweep);
      ctx.closePath();
      ctx.fillStyle = chartColors[i % chartColors.length];
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, ri, angle, angle + sweep);
      ctx.closePath();
      ctx.fillStyle = '#111827';
      ctx.fill();
      // Label
      const mid = angle + sweep / 2;
      const lx = cx + (ro + 16) * Math.cos(mid);
      const ly = cy + (ro + 16) * Math.sin(mid);
      ctx.fillStyle = 'rgba(240,244,255,0.8)'; ctx.font = '10px Inter'; ctx.textAlign = 'center';
      ctx.fillText(chartLabels[i], lx, ly);
      ctx.font = '700 11px Inter'; ctx.fillStyle = chartColors[i % chartColors.length];
      ctx.fillText(total === 0 ? '0%' : Math.round(v / total * 100) + '%', cx + (ro * 0.65) * Math.cos(mid), cy + (ro * 0.65) * Math.sin(mid) + 4);
      angle += sweep;
    });
    ctx.fillStyle = 'rgba(240,244,255,0.9)'; ctx.font = '700 18px Inter'; ctx.textAlign = 'center';
    ctx.fillText(total, cx, cy + 4);
    ctx.font = '10px Inter'; ctx.fillStyle = 'rgba(139,159,193,0.7)';
    ctx.fillText('Total', cx, cy + 18);
  } catch (e) {
    ctx.clearRect(0, 0, size, size);
    ctx.fillText('Error', 10, 20);
  }
}

// â”€â”€â”€ GATE LIST MINI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderGateListMini() {
  const el = document.getElementById('gate-list-mini');
  if (!el) return;
  el.innerHTML = state.gates.map(g => {
    const lvl = levelOf(g.density);
    return `<div class="gate-item">
      <span class="gate-name">${g.emoji} ${g.id}</span>
      <div class="gate-bar-wrap">
        <div class="gate-bar-track"><div class="gate-bar ${lvl}" style="width:${g.density}%"></div></div>
      </div>
      <span class="gate-pct ${lvl}">${g.density}%</span>
      <span class="tag ${lvl === 'critical' ? 'red' : lvl === 'high' ? 'orange' : lvl === 'moderate' ? 'orange' : 'green'}" style="font-size:0.6rem;">${lvl.toUpperCase()}</span>
    </div>`;
  }).join('');
}

// â”€â”€â”€ ALERTS MINI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderAlertsMini() {
  const el = document.getElementById('alerts-list-mini');
  if (!el) return;
  const shown = state.alerts.slice(0, 4);
  el.innerHTML = shown.length ? shown.map(a => alertHTML(a, true)).join('')
    : '<p style="color:var(--text-muted);font-size:0.8rem;padding:8px 0;">No active alerts ðŸŽ‰</p>';
}

function alertHTML(a, mini = false) {
  const icons = { critical: 'ðŸ”´', warning: 'ðŸŸ¡', info: 'ðŸ”µ' };
  return `<div class="alert-item ${a.severity}" data-id="${a.id}" style="display:${state.alertFilter !== 'all' && state.alertFilter !== a.severity ? 'none' : 'flex'}">
    <span class="alert-icon">${icons[a.severity] || 'â„¹ï¸'}</span>
    <div class="alert-content">
      <div class="alert-title">${a.title}</div>
      <div class="alert-desc">${a.desc}</div>
    </div>
    <span class="alert-time">${a.time}</span>
    ${!mini ? `<button class="alert-dismiss" onclick="dismissAlert('${a.id}')">âœ•</button>` : ''}
  </div>`;
}

// â”€â”€â”€ SHUTTLE MINI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderShuttleMini() {
  const el = document.getElementById('shuttle-mini-list');
  if (!el) return;
  el.innerHTML = state.shuttles.map(s => {
    const pct = Math.round(s.load / s.capacity * 100);
    const loadCls = pct >= 90 ? 'full' : pct >= 60 ? 'busy' : 'ok';
    return `<div class="shuttle-item">
      <span class="shuttle-indicator ${s.status}"></span>
      <div style="flex:1">
        <div class="shuttle-name">${s.name}</div>
        <div class="shuttle-route">${s.route}</div>
      </div>
      ${s.status === 'active' ? `<span class="shuttle-load ${loadCls}">${pct}%</span>` : ''}
      ${s.status === 'standby' ? `<span class="tag orange" style="font-size:0.6rem">STANDBY</span>` : ''}
      ${s.status === 'maintenance' ? `<span class="tag red" style="font-size:0.6rem">MAINT</span>` : ''}
    </div>`;
  }).join('');
}

async function renderRouteNudgesMini() {
  const el = document.getElementById('route-nudges-mini');
  if (!el) return;
  el.innerHTML = 'Loading...';
  try {
    const routesRes = await apiFetch('/api/traffic/routes');
    const routes = routesRes && Array.isArray(routesRes.recommendations)
      ? routesRes.recommendations
      : [];
    if (!routes.length) {
      el.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem;padding:8px 0;">No Data Available</p>';
      return;
    }
    el.innerHTML = routes.slice(0, 3).map(r => `
      <div class="nudge-item">
        <div class="nudge-icon">🗺️</div>
        <div class="nudge-content">
          <div class="nudge-title">${r.from || 'Campus'} → ${r.to || ('Gate ' + (r.gate_id || '?'))}</div>
          <div class="nudge-desc">${r.recommended_path || 'Use alternate path'} · Save ${r.time_saving_min || 0} min</div>
        </div>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = 'Error';
  }
}

// â”€â”€â”€ GATES VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderGatesView() {
  const container = document.getElementById('gate-cards-container');
  if (container) {
    container.innerHTML = state.gates.map(g => {
      const lvl = levelOf(g.density);
      const color = lvl === 'critical' ? 'var(--accent-red)' : lvl === 'high' ? 'var(--high-color)' : lvl === 'moderate' ? 'var(--moderate-color)' : 'var(--low-color)';
      return `<div class="gate-full-card" style="border-color:${color}33">
        <div class="gate-full-header">
          <div class="gate-full-icon" style="background:${color}22;">${g.emoji}</div>
          <div>
            <div class="gate-full-title">${g.name}</div>
            <div class="gate-full-loc">${g.location}</div>
          </div>
          <span class="tag ${lvl === 'critical' ? 'red' : lvl === 'high' ? 'orange' : lvl === 'moderate' ? 'orange' : 'green'}" style="margin-left:auto">${lvl.toUpperCase()}</span>
        </div>
        <div style="margin:10px 0;">
          <div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:6px;">
            <span style="color:var(--text-muted)">Congestion</span>
            <span style="color:${color};font-weight:700">${g.density}%</span>
          </div>
          <div class="gate-bar-track" style="height:8px;"><div class="gate-bar ${lvl}" style="width:${g.density}%"></div></div>
        </div>
        <div class="gate-full-metrics">
          <div class="gate-metric"><div class="gate-metric-val" style="color:${color}">${g.entries.toLocaleString()}</div><div class="gate-metric-label">Entries Today</div></div>
          <div class="gate-metric"><div class="gate-metric-val" style="color:var(--accent-cyan)">${g.predicted}%</div><div class="gate-metric-label">1-Hr Forecast</div></div>
        </div>
        <div class="gate-prediction-row">
          <span class="gate-prediction-label">AI Recommendation: </span>
          <span class="gate-prediction-val">${g.density >= 80 ? 'âš ï¸ Redirect to Gate ' + getAlternateGate(g.id) : g.density >= 60 ? 'Monitor closely' : 'Normal flow'}</span>
        </div>
      </div>`;
    }).join('');
  }

  // Gate history chart
  const gateHistCanvas = document.getElementById('gate-history-chart');
  if (gateHistCanvas) {
    const hours = Array.from({ length: 12 }, (_, i) => {
      const d = new Date(); d.setHours(d.getHours() - 11 + i);
      return d.getHours() + ':00';
    });
    drawBarChart(gateHistCanvas, hours.filter((_, i) => i % 2 === 0),
      state.gates.slice(0, 3).map((g, i) => ({
        label: g.name, color: ['#3b82f6', '#7c3aed', '#10b981'][i],
        data: Array.from({ length: 6 }, () => Math.round(g.density * 0.6 + Math.random() * g.density * 0.5))
      })), { yMax: 100 });
  }

  // Gate prediction chart
  const gatePredCanvas = document.getElementById('gate-prediction-chart');
  if (gatePredCanvas) {
    const labels = Array.from({ length: 5 }, (_, i) => {
      const d = new Date(); d.setMinutes(d.getMinutes() + i * 30);
      return d.getHours() + ':' + d.getMinutes().toString().padStart(2, '0');
    });
    drawLineChart(gatePredCanvas, labels,
      state.gates.slice(0, 3).map((g, i) => ({
        label: g.name, data: labels.map((_, j) => mlPredict(j * 0.5, g.density)),
        color: ['#ef4444', '#f59e0b', '#3b82f6'][i], fill: false
      })), { yMax: 100, unit: '%' });
  }
}

function getAlternateGate(id) {
  const alternates = { A: 'B', B: 'E', C: 'B', D: 'E', E: 'D', F: 'B' };
  return alternates[id] || 'B';
}

async function renderShuttleView() {
  const fc = document.getElementById('shuttle-forecast-chart');
  if (fc) await renderForecastChart();
  const fleet = document.getElementById('shuttle-fleet-status');
  if (fleet) {
    fleet.innerHTML = 'Loading...';
    try {
      const shuttlesRes = await apiFetch('/api/traffic/shuttles');
      const shuttles = shuttlesRes && Array.isArray(shuttlesRes.fleet) ? shuttlesRes.fleet : [];
      if (!shuttles.length) {
        fleet.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem;padding:8px 0;">No Data Available</p>';
        return;
      }
      fleet.innerHTML = shuttles.map(s => {
        const pct = !s.capacity ? 0 : Math.round(s.load / s.capacity * 100);
        const c = pct >= 90 ? 'var(--accent-red)' : pct >= 60 ? 'var(--moderate-color)' : 'var(--low-color)';
        return `<div class="fleet-item">
          <span class="shuttle-indicator ${s.status}"></span>
          <div style="flex:1">
            <div style="font-size:0.82rem;font-weight:600;">${s.shuttle_id || s.id}</div>
            <div style="font-size:0.7rem;color:var(--text-muted)">${s.route}</div>
          </div>
          <div style="min-width:80px">
            <div class="fleet-status-bar"><div class="fleet-bar-fill" style="width:${pct}%;background:${c}"></div></div>
          </div>
          <span style="font-size:0.78rem;font-weight:700;min-width:36px;text-align:right;color:${c}">${pct}%</span>
        </div>`;
      }).join('');
    } catch (e) {
      fleet.innerHTML = 'Error';
    }
  }
  const rc = document.getElementById('shuttle-route-chart');
  if (rc) await drawDonutChart(rc);
  const dr = document.getElementById('shuttle-dispatch-recs');
  if (dr) {
    dr.innerHTML = 'Loading...';
    try {
      const recs = await apiFetch('/api/traffic/recommendations');
      if (!recs || !recs.length) {
        dr.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem;padding:8px 0;">No Data Available</p>';
        return;
      }
      dr.innerHTML = `<div class="dispatch-grid">${recs.map(r => `
        <div class="dispatch-item">
          <div class="d-head"><span class="d-icon">${r.type === 'dispatch' ? 'ðŸšŒ' : r.type === 'reroute' ? 'ðŸ”„' : 'âš ï¸'}</span>${r.title}</div>
          <div class="d-reason">${r.description}</div>
          <div class="d-action">Priority: ${r.priority}</div>
        </div>`).join('')}</div>`;
    } catch (e) {
      dr.innerHTML = 'Error';
    }
  }
}

// â”€â”€â”€ ROUTES VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderRoutesView() {
  const rr = document.getElementById('route-recommendations-full');
  if (rr) {
    rr.innerHTML = state.routes.map((r, i) => `
      <div class="route-rec-item">
        <div class="route-num">${i + 1}</div>
        <div class="route-rec-content">
          <div class="r-title">${r.from} â†’ ${r.to}</div>
          <div class="r-desc">âœ… Recommended: ${r.recommended} &nbsp;|&nbsp; âŒ Avoid: ${r.avoid}</div>
          <div class="r-tags">${r.tags.map(t => `<span class="tag blue">${t}</span>`).join('')}</div>
        </div>
        <div class="route-rec-meta">
          <div class="route-save">-${r.savings}</div>
          <div class="route-save-label">time saved</div>
          <div style="margin-top:6px"><span class="tag green">Score ${r.score}</span></div>
        </div>
      </div>`).join('');
  }

  // Efficiency chart
  const ec = document.getElementById('route-efficiency-chart');
  if (ec) {
    drawBarChart(ec, state.routes.map(r => r.from.split(' ')[0]),
      [{ label: 'Score', color: '#06b6d4', data: state.routes.map(r => r.score) }], { yMax: 100 });
  }

  // Stats
  const sd = document.getElementById('route-stats-display');
  if (sd) {
    const savings = state.routes.map(r => parseInt(String(r.savings).replace(/\D/g, ''), 10) || 0);
    const avgSaving = savings.length ? Math.round(savings.reduce((a, b) => a + b, 0) / savings.length) : 0;
    const avgScore = state.routes.length ? Math.round(state.routes.reduce((a, r) => a + r.score, 0) / state.routes.length) : 0;
    const reduction = state.routes.length
      ? Math.round(state.routes.reduce((a, r) => a + (r.currentDensity || 0), 0) / state.routes.length)
      : 0;
    sd.innerHTML = [
      { val: String(state.routes.length), label: 'Active Route Nudges', color: 'var(--accent-cyan)' },
      { val: `${avgSaving} min`, label: 'Avg Time Saved', color: 'var(--accent-green)' },
      { val: `${reduction}%`, label: 'Avg Source Congestion', color: 'var(--accent-purple)' },
      { val: `${avgScore}`, label: 'Avg Route Score', color: 'var(--accent-orange)' },
    ].map(s => `<div class="stat-box"><div class="stat-val" style="color:${s.color}">${s.val}</div><div class="stat-label">${s.label}</div></div>`).join('');
  }
}

// â”€â”€â”€ EVENTS VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  // Event history chart
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

// â”€â”€â”€ ALERTS VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderAlertsView() {
  const al = document.getElementById('alerts-full-list');
  if (al) {
    const filtered = state.alertFilter === 'all' ? state.alerts : state.alerts.filter(a => a.severity === state.alertFilter);
    al.innerHTML = filtered.length ? filtered.map(a => alertHTML(a, false)).join('')
      : '<p style="color:var(--text-muted);padding:20px;text-align:center">No alerts matching filter</p>';
  }

  // Threshold settings
  const ts = document.getElementById('threshold-settings');
  if (ts) {
    ts.innerHTML = [
      { key: 'critical', label: 'Critical Congestion Threshold', unit: '%' },
      { key: 'warning', label: 'Warning Congestion Threshold', unit: '%' },
      { key: 'shuttle', label: 'Shuttle Load Alert Threshold', unit: '%' },
    ].map(t => `<div class="threshold-item">
      <div class="threshold-label"><span>${t.label}</span><span id="thresh-val-${t.key}">${state.thresholds[t.key]}${t.unit}</span></div>
      <input type="range" class="threshold-slider" min="40" max="95" value="${state.thresholds[t.key]}" 
        oninput="updateThreshold('${t.key}',this.value,'${t.unit}')">
    </div>`).join('');
  }

  // Alert history
  const ahc = document.getElementById('alert-history-chart');
  if (ahc) {
    const hours = Array.from({ length: 8 }, (_, i) => `${8 + i}:00`);
    drawBarChart(ahc, hours,
      [{ label: 'Alerts', color: '#ef4444', data: hours.map(() => Math.floor(Math.random() * 5)) }], { yMax: 10 });
  }
}

function filterAlerts(type, btn) {
  state.alertFilter = type;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderAlertsView();
}

function dismissAlert(id) {
  state.alerts = state.alerts.filter(a => a.id !== id);
  updateKPIs(); renderAlertsMini(); renderAlertsView();
  setEl('alert-badge', state.alerts.length || '');
}

function clearAllAlerts() {
  state.alerts = [];
  updateKPIs(); renderAlertsMini(); renderAlertsView();
  setEl('alert-badge', '');
}

function updateThreshold(key, val, unit) {
  state.thresholds[key] = parseInt(val);
  setEl('thresh-val-' + key, val + unit);
}

// â”€â”€â”€ ANALYTICS VIEW â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderAnalyticsView() {
  const summary = state.latestSummary || {};
  const analytics = state.analytics || {};
  const awc = document.getElementById('analytics-weekly-chart');
  if (awc) {
    const days = analytics.weekly_pattern?.labels || ['D-6', 'D-5', 'D-4', 'D-3', 'D-2', 'D-1', 'Now'];
    const gateSeries = analytics.weekly_pattern?.gate_traffic
      || (state.mlHistory.slice(-7).length ? state.mlHistory.slice(-7) : new Array(7).fill(summary.avg_congestion || 0));
    const shuttleSeries = analytics.weekly_pattern?.shuttle_usage || null;
    const active = state.shuttles.filter(s => s.status === 'active');
    const avgLoad = active.length
      ? Math.round(active.reduce((acc, s) => acc + ((s.capacity ? s.load / s.capacity : 0) * 100), 0) / active.length)
      : 0;
    drawLineChart(awc, days, [
      { label: 'Gate Traffic', data: gateSeries, color: '#3b82f6', fill: true },
      { label: 'Shuttle Usage', data: shuttleSeries || new Array(7).fill(avgLoad), color: '#10b981', fill: false },
    ], { yMax: 100, unit: '%' });
  }

  const apc = document.getElementById('analytics-peak-chart');
  if (apc) {
    const labels = analytics.peak_distribution?.labels || ['8–10am', '12–2pm', '4–6pm', 'Other'];
    const values = analytics.peak_distribution?.values || [28, 22, 32, 18];
    drawDonutChart(apc, labels, values, ['#3b82f6', '#f59e0b', '#ef4444', '#6b7280']);
  }

  const is = document.getElementById('impact-stats');
  if (is) {
    const activeShuttles = state.shuttles.filter(s => s.status === 'active').length;
    const stats = analytics.impact_stats || [
      { val: `${summary.avg_congestion ?? 0}%`, label: 'Avg Congestion', change: 'Live backend' },
      { val: `${state.routes.length}`, label: 'Route Nudges', change: 'Current snapshot' },
      { val: `${activeShuttles}`, label: 'Active Shuttles', change: 'Current fleet' },
      { val: `${summary.active_alerts ?? state.alerts.length ?? 0}`, label: 'Active Alerts', change: 'Live backend' },
    ];
    is.innerHTML = stats.map(s => `<div class="impact-stat"><div class="impact-val">${s.val}</div>
      <div class="impact-label">${s.label}</div>
      <div class="impact-change">${s.change}</div></div>`).join('');
  }

  const mm = document.getElementById('ml-metrics');
  if (mm) {
    const activeShuttles = state.shuttles.filter(s => s.status === 'active').length;
    const mode = backendStatus.online ? 'Live Backend' : 'Simulation';
    const metrics = analytics.ml_metrics || [
      { name: 'Mode', val: mode, detail: 'Data source' },
      { name: 'AI Confidence', val: `${summary.ai_confidence ?? 0}%`, detail: 'Backend summary' },
      { name: 'Total People', val: `${summary.total_people ?? 0}`, detail: 'Current total count' },
      { name: 'Gate Count', val: `${state.gates.length}`, detail: 'Tracked gates' },
      { name: 'Shuttle Count', val: `${state.shuttles.length}`, detail: `${activeShuttles} active` },
      { name: 'Alerts', val: `${state.alerts.length}`, detail: 'Current list' },
      { name: 'Routes', val: `${state.routes.length}`, detail: 'Active recommendations' },
      { name: 'Last Refresh', val: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }), detail: 'Client side' },
    ];
    mm.innerHTML = metrics.map(m => `<div class="ml-metric"><div class="ml-metric-name">${m.name}</div>
      <div class="ml-metric-val">${m.val}</div>
      <div class="ml-metric-detail">${m.detail}</div></div>`).join('');
  }
}

// â”€â”€â”€ ALERT ENGINE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let alertIdCounter = 0;
function checkAndGenerateAlerts() {
  const criticalGates = state.gates.filter(g => g.density >= state.thresholds.critical);
  const warningGates = state.gates.filter(g => g.density >= state.thresholds.warning && g.density < state.thresholds.critical);
  const overloadedShuttles = state.shuttles.filter(s => s.status === 'active' && (s.load / s.capacity * 100) >= state.thresholds.shuttle);

  // Limit total alerts
  if (state.alerts.length > 8) state.alerts = state.alerts.slice(0, 8);

  criticalGates.forEach(g => {
    if (!state.alerts.find(a => a.gateId === g.id && a.severity === 'critical')) {
      addAlert({
        severity: 'critical', gateId: g.id,
        title: `ðŸš¨ CRITICAL: ${g.name} Congestion`,
        desc: `Density at ${g.density}% â€” Exceeds critical threshold (${state.thresholds.critical}%). Redirect to Gate ${getAlternateGate(g.id)}.`,
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
      });
    }
  });

  warningGates.forEach(g => {
    if (!state.alerts.find(a => a.gateId === g.id && a.severity === 'warning')) {
      addAlert({
        severity: 'warning', gateId: g.id,
        title: `âš ï¸ Warning: ${g.name} Rising`,
        desc: `Density at ${g.density}% and increasing. AI predicts peak of ${g.predicted}% within 30 min.`,
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
      });
    }
  });

  overloadedShuttles.forEach(s => {
    if (!state.alerts.find(a => a.shuttleId === s.id)) {
      addAlert({
        severity: 'warning', shuttleId: s.id,
        title: `ðŸšŒ Shuttle Overload: ${s.name}`,
        desc: `Capacity at ${Math.round(s.load / s.capacity * 100)}%. Consider deploying standby shuttle on ${s.route}.`,
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
      });
    }
  });
}

function addAlert(alert) {
  alert.id = 'alert-' + (++alertIdCounter);
  state.alerts.unshift(alert);
  // Show banner for critical
  if (alert.severity === 'critical') {
    const banner = document.getElementById('alert-banner');
    setEl('alert-banner-text', alert.title + ' â€” ' + alert.desc);
    if (banner) banner.style.display = 'flex';
    setTimeout(() => { if (banner) banner.style.display = 'none'; }, 8000);
  }
}

// â”€â”€â”€ SIMULATION LOOP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function startSimulationLoop() {
  setInterval(() => {
    state.tick++;
    if (backendStatus.online) {
      if (state.tick % 2 === 0) syncWithBackend();
      if (state.tick % 5 === 0) slowSyncWithBackend();
    } else {
      state.gates.forEach(g => {
        const drift = (Math.random() - 0.48) * 3;
        g.density = Math.min(99, Math.max(5, Math.round(g.density + drift)));
        g.predicted = Math.min(99, Math.max(10, Math.round(mlPredict(1, g.density))));
        g.trend.push(g.density);
        if (g.trend.length > 20) g.trend.shift();
        g.entries += Math.round(Math.random() * 8);
      });

      state.shuttles.forEach(s => {
        if (s.status === 'active') {
          const d = (Math.random() - 0.45) * 4;
          s.load = Math.min(s.capacity, Math.max(0, s.load + d));
          s.eta = Math.max(1, s.eta + (Math.random() > 0.5 ? -1 : 1));
        }
      });

      state.heatZones.forEach((z, i) => {
        const ref = state.gates.length ? state.gates[i % state.gates.length].density : z.density;
        z.density += (ref - z.density) * 0.1 + (Math.random() - 0.5) * 3;
        z.density = Math.min(99, Math.max(5, z.density));
      });

      checkAndGenerateAlerts();
    }

    updateKPIs();
    renderGateListMini();
    renderAlertsMini();
    renderShuttleMini();

    if (state.currentView === 'map') renderFullMap();
    else renderMiniHeatmap();

    if (state.tick % 5 === 0) {
      renderForecastChart();
      renderRouteNudgesMini();
      if (state.currentView === 'gates') renderGatesView();
      if (state.currentView === 'shuttle') renderShuttleView();
    }
  }, 2000);
}

// â”€â”€â”€ LIVE CLOCK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function startLiveClock() {
  const el = document.getElementById('live-clock');
  function tick() {
    if (el) el.textContent = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  }
  tick();
  setInterval(tick, 1000);
}

// â”€â”€â”€ THRESHOLD SLIDERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function bindThresholdSliders() { /* bound inline */ }

// â”€â”€â”€ START â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
document.addEventListener('DOMContentLoaded', init);

// Admin View Functions
function renderAdminView() {
  renderAdminCapacityControls();
  renderAdminGlobalSettings();
}

function renderAdminCapacityControls() {
  const container = document.getElementById('admin-capacity-controls');
  if (!container) return;
  if (!state.gates.length) {
    container.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:24px;">No gates available.</p>';
    return;
  }
  const html = state.gates.map(gate => `
    <div class="capacity-control">
      <div class="gate-label">${gate.emoji} ${gate.name}</div>
      <div class="capacity-slider-container">
        <input type="range" min="10" max="200

" value="${gate.max_capacity || 50}" 
               class="capacity-slider" id="slider-${gate.id}" 
               oninput="updateCapacityDisplay('${gate.id}', this.value)">
        <span class="capacity-value" id="capacity-${gate.id}">${gate.max_capacity || 50}</span>
      </div>
      <span style="color:var(--text-secondary);font-size:0.75rem;">Current: ${gate.entries} / ${gate.max_capacity || 50}</span>
      <button class="capacity-save-btn" onclick="saveGateCapacity('${gate.id}')">Save</button>
    </div>
  `).join('');
  container.innerHTML = html;
}

function renderAdminGlobalSettings() {
  const container = document.getElementById('admin-global-settings');
  if (!container) return;
  container.innerHTML = `
    <div class="global-settings-form">
      <div class="form-group">
        <label>Global Default Capacity</label>
        <input type="number" id="global-capacity-input" value="50" min="10" max="500">
      </div>
      <button class="btn-primary" onclick="saveGlobalSettings()" style="margin-top:8px;">Apply Global Settings</button>
    </div>
  `;
}

function updateCapacityDisplay(gateId, value) {
  const display = document.getElementById('capacity-' + gateId);
  if (display) display.textContent = value;
}

async function saveGateCapacity(gateId) {
  const slider = document.getElementById('slider-' + gateId);
  if (!slider) return;
  const capacity = parseInt(slider.value);
  try {
    const res = await fetch(BACKEND_URL + '/api/admin/capacity/gate/' + gateId, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ capacity, use_global: false })
    });
    if (res.ok) {
      alert('Capacity saved!');
      await syncGatesFromBackend();
    }
  } catch (err) {
    console.error('Error:', err);
  }
}

async function saveGlobalSettings() {
   const capacity = parseInt(document.getElementById('global-capacity-input').value);
  if (!capacity || capacity < 10) {
    alert('Please enter a valid capacity');
    return;
  }
  try {
    const res = await fetch(BACKEND_URL + '/api/admin/capacity/global', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ capacity })
    });
    if (res.ok) {
      alert('Settings applied!');
      await syncGatesFromBackend();
      renderAdminView();
    }
  } catch (err) {
    console.error('Error:', err);
  }
}


