/* =============================================
   SMART CAMPUS MOBILITY SYSTEM — AI ENGINE
   ============================================= */
'use strict';

// ─── BACKEND API INTEGRATION ────────────────────────────────────────────────
const BACKEND_URL = 'http://127.0.0.1:5000';

const backendStatus = {
  online: false,
  lastCheck: 0,
  indicator: null,
};

// Generic fetch helper — returns parsed JSON or null on any error
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

// ── Health check ─────────────────────────────────────────────────────────────
async function checkBackend() {
  const data = await apiFetch('/api/health');
  backendStatus.online = !!(data && data.status === 'ok');
  renderBackendStatus(backendStatus.online);
  return backendStatus.online;
}

// ── Pull gate data from Flask → merge into state.gates ───────────────────────
async function syncGatesFromBackend() {
  const data = await apiFetch('/api/traffic/gates');
  if (!data || !data.gates) return;
  data.gates.forEach(g => {
    const local = state.gates.find(lg => lg.id === g.gate_id);
    if (local) {
      local.density = parseFloat(g.density) || local.density;
      local.predicted = parseFloat(g.predicted) || local.predicted;
      if (g.entries) local.entries = g.entries;
    }
  });
}

// ── Pull shuttle data from Flask → merge into state.shuttles ─────────────────
async function syncShuttlesFromBackend() {
  const data = await apiFetch('/api/traffic/shuttles');
  if (!data || !data.fleet) return;
  data.fleet.forEach(s => {
    const local = state.shuttles.find(ls => ls.id === s.shuttle_id);
    if (local) {
      local.load = parseFloat(s.load) || local.load;
      local.status = s.status || local.status;
      if (s.next_stop && s.next_stop !== '—') local.nextStop = s.next_stop;
      if (s.eta_min != null) local.eta = s.eta_min;
    }
  });
}

// ── Pull route recommendations from Flask ─────────────────────────────────────
async function syncRoutesFromBackend() {
  const data = await apiFetch('/api/traffic/routes');
  if (!data || !data.recommendations || !data.recommendations.length) return;
  state.routes = data.recommendations.map(r => ({
    from: r.from || 'Campus Zone',
    to: r.to || 'Gate ' + (r.gate_id || '?'),
    recommended: r.recommended_path || 'Use alternate path',
    avoid: r.avoid || 'Direct route',
    savings: (r.time_saving_min || 5) + ' min',
    tags: r.priority === 'high' ? ['High Priority', 'Less Crowd'] : ['Less Crowd', 'Faster'],
    score: r.current_density ? Math.max(60, 100 - Math.round(r.current_density * 0.4)) : 80,
  }));
}

// ── Pull congestion alerts from Flask ────────────────────────────────────────
async function syncAlertsFromBackend() {
  const data = await apiFetch('/api/traffic/congestion');
  if (!data || !data.alerts) return;
  data.alerts.forEach(a => {
    const alreadyExists = state.alerts.find(
      sa => sa.backendLoc === a.location && sa.severity === a.severity
    );
    if (!alreadyExists) {
      addAlert({
        severity: a.severity,
        backendLoc: a.location,
        title: a.severity === 'critical'
          ? `🚨 CRITICAL: ${a.location}`
          : `⚠️ Warning: ${a.location}`,
        desc: a.message + ' — ' + (a.action || ''),
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
      });
    }
  });
}

// ── Push live simulated data point to Flask (keeps DB populated) ─────────────
async function pushTrafficDataToBackend() {
  if (!backendStatus.online) return;
  const gate = state.gates[Math.floor(Math.random() * state.gates.length)];
  const count = Math.round(gate.density * 4.5); // density% → approximate people count
  await apiFetch('/api/traffic/add', {
    method: 'POST',
    body: JSON.stringify({
      location: gate.name,
      count: count,
      gate_id: gate.id,
      source: 'simulation',
    }),
  });
}

// ── Master sync — called every few ticks ─────────────────────────────────────
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
  await pushTrafficDataToBackend();
}

// ── Slower sync (every 15s) for routes and alerts ────────────────────────────
async function slowSyncWithBackend() {
  if (!backendStatus.online) return;
  await Promise.all([
    syncRoutesFromBackend(),
    syncAlertsFromBackend(),
  ]);
}


// ─── STATE ─────────────────────────────────────────────────────────────────
const state = {
  currentView: 'dashboard',
  tick: 0,
  alerts: [],
  alertFilter: 'all',
  showRoutes: true,
  showShuttles: true,
  thresholds: { critical: 80, warning: 60, shuttle: 85 },

  gates: [
    { id: 'A', name: 'Gate A', location: 'Main Entrance, North', emoji: '🏫', density: 72, predicted: 85, entries: 1240, trend: [] },
    { id: 'B', name: 'Gate B', location: 'Academic Block, East', emoji: '📚', density: 45, predicted: 58, entries: 870, trend: [] },
    { id: 'C', name: 'Gate C', location: 'Sports Complex, West', emoji: '🏟️', density: 88, predicted: 91, entries: 1680, trend: [] },
    { id: 'D', name: 'Gate D', location: 'Residential Block', emoji: '🏠', density: 31, predicted: 40, entries: 520, trend: [] },
    { id: 'E', name: 'Gate E', location: 'Library & Labs', emoji: '🔬', density: 56, predicted: 62, entries: 990, trend: [] },
    { id: 'F', name: 'Gate F', location: 'Admin & Cafeteria', emoji: '🍽️', density: 64, predicted: 78, entries: 1120, trend: [] },
  ],

  shuttles: [
    { id: 'S1', name: 'Shuttle 01', route: 'Gate A → B → C', load: 92, capacity: 45, status: 'active', nextStop: 'Gate B', eta: 3 },
    { id: 'S2', name: 'Shuttle 02', route: 'Gate C → D → E', load: 67, capacity: 45, status: 'active', nextStop: 'Gate D', eta: 6 },
    { id: 'S3', name: 'Shuttle 03', route: 'Gate F → A → B', load: 38, capacity: 45, status: 'active', nextStop: 'Gate A', eta: 2 },
    { id: 'S4', name: 'Shuttle 04', route: 'Gate B → E → F', load: 95, capacity: 45, status: 'active', nextStop: 'Gate E', eta: 5 },
    { id: 'S5', name: 'Shuttle 05', route: 'Gate A → F', load: 15, capacity: 45, status: 'active', nextStop: 'Gate F', eta: 8 },
    { id: 'S6', name: 'Shuttle 06', route: 'Event Special', load: 0, capacity: 45, status: 'standby', nextStop: '—', eta: 0 },
    { id: 'S7', name: 'Shuttle 07', route: 'Gate C → B → A', load: 0, capacity: 45, status: 'maintenance', nextStop: '—', eta: 0 },
    { id: 'S8', name: 'Shuttle 08', route: 'Gate D → E', load: 55, capacity: 45, status: 'active', nextStop: 'Gate E', eta: 4 },
  ],

  events: [
    { time: '09:00', title: 'Morning Assembly', location: 'Main Auditorium', impact: 'high', attendees: 800 },
    { time: '11:30', title: 'Guest Lecture — AI & Robotics', location: 'Lecture Hall B3', impact: 'medium', attendees: 250 },
    { time: '13:00', title: 'Lunch Break', location: 'Cafeteria — Gate F', impact: 'high', attendees: 2000 },
    { time: '14:30', title: 'Sports Meet — Basketball Finals', location: 'Sports Complex — Gate C', impact: 'high', attendees: 600 },
    { time: '16:00', title: 'Lab Sessions', location: 'Lab Block B, Gate E', impact: 'low', attendees: 180 },
    { time: '17:30', title: 'Evening Shuttle Rush', location: 'All Gates', impact: 'high', attendees: 2500 },
    { time: '19:00', title: 'Cultural Night', location: 'Central Amphitheatre', impact: 'medium', attendees: 400 },
  ],

  routes: [
    { from: 'Library', to: 'Cafeteria', recommended: 'Via Gate B inner path', avoid: 'Gate F direct', savings: '8 min', tags: ['Less Crowd', 'Shaded Path'], score: 92 },
    { from: 'Hostel Block', to: 'Academic Zone', recommended: 'Via Gate D → E pathway', avoid: 'Gate A main road', savings: '5 min', tags: ['Shorter', 'Safe'], score: 88 },
    { from: 'Sports Complex', to: 'Library', recommended: 'Internal campus trail', avoid: 'Gate C main gate', savings: '11 min', tags: ['Bike Lane', 'Off-peak'], score: 85 },
    { from: 'Admin Block', to: 'Lecture Halls', recommended: 'East corridor via Gate B', avoid: 'Central plaza', savings: '6 min', tags: ['Covered', 'Low Density'], score: 80 },
  ],

  heatZones: [],
  mlHistory: [], // historical crowd readings for forecast
};

// ─── INIT ───────────────────────────────────────────────────────────────────
function init() {
  initHeatZones();
  seedMLHistory();
  renderAll();
  bindNavigation();
  bindMenuToggle();
  bindThresholdSliders();
  startLiveClock();
  // Connect to Flask backend (silent — falls back to simulation if offline)
  checkBackend().then(() => {
    if (backendStatus.online) {
      // Initial full sync before the loop starts
      syncGatesFromBackend();
      syncShuttlesFromBackend();
      syncRoutesFromBackend();
      syncAlertsFromBackend();
    }
  });
  startSimulationLoop();
  // Slow sync every 15s for routes + backend alerts
  setInterval(slowSyncWithBackend, 15000);
}

// ─── ML PREDICTION ENGINE ───────────────────────────────────────────────────
// Simulated Polynomial + Seasonal + Gaussian noise ML model
function mlPredict(hourOffset, baseDensity) {
  const now = new Date();
  const h = now.getHours() + hourOffset;
  // Bimodal peak curve (morning 8–10, evening 16–18)
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

// ─── HEATMAP DATA ───────────────────────────────────────────────────────────
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
    density: state.gates[i % state.gates.length].density + (Math.random() - 0.5) * 15,
  }));
}

// ─── CONGESTION LEVEL ───────────────────────────────────────────────────────
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

// ─── NAVIGATION ─────────────────────────────────────────────────────────────
const pageTitles = {
  dashboard: ['Command Center', 'Real-time campus mobility intelligence'],
  map: ['Live Campus Map', 'Crowd density heatmap & route overlay'],
  gates: ['Gate Congestion', 'AI-powered entry point monitoring & prediction'],
  shuttle: ['Shuttle Forecast', 'ML-driven demand prediction & fleet management'],
  routes: ['Route Advisor', 'Smart mobility nudges & alternate path recommendations'],
  events: ['Events & Schedule', 'Proactive congestion forecasting for campus events'],
  alerts: ['Smart Alert Center', 'Threshold-based notifications & anomaly detection'],
  analytics: ['Analytics', 'Historical patterns, AI model performance & impact metrics'],
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
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      switchView(item.dataset.view);
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

// ─── RENDER ALL ─────────────────────────────────────────────────────────────
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
}

// ─── KPIs ────────────────────────────────────────────────────────────────────
function updateKPIs() {
  const totalPeople = 2400 + Math.round(Math.random() * 600);
  const avgCongestion = Math.round(state.gates.reduce((s, g) => s + g.density, 0) / state.gates.length);
  const activeShuttles = state.shuttles.filter(s => s.status === 'active').length;
  const critAlerts = state.alerts.filter(a => a.severity === 'critical').length;
  const warnAlerts = state.alerts.filter(a => a.severity === 'warning').length;

  setEl('kpi-people-val', totalPeople.toLocaleString());
  setEl('kpi-congestion-val', avgCongestion + '%');
  setEl('kpi-shuttle-val', `${activeShuttles} / ${state.shuttles.length}`);
  setEl('kpi-alerts-val', state.alerts.length);
  setEl('kpi-alerts-change', `${critAlerts} critical, ${warnAlerts} warning`);

  // Campus status pill
  const pill = document.getElementById('campus-status-pill');
  const ind = pill.querySelector('.status-indicator');
  [pill.querySelector('span:last-child') || pill].forEach(() => { });
  const lvl = levelOf(avgCongestion);
  ind.className = 'status-indicator ' + lvl;
  pill.lastChild.textContent = ' ' + ({ low: 'Clear', moderate: 'Moderate Traffic', high: 'Heavy Traffic', critical: 'CRITICAL' }[lvl]);

  // Alert badge
  setEl('alert-badge', state.alerts.length || '');
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ─── MINI HEATMAP (Canvas) ──────────────────────────────────────────────────
function renderMiniHeatmap() {
  const canvas = document.getElementById('heatmap-canvas');
  if (!canvas) return;
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

// ─── FORECAST CHART ─────────────────────────────────────────────────────────
function renderForecastChart() {
  const canvas = document.getElementById('forecast-chart');
  if (!canvas) return;
  const predictions = predictNextHourCongestion();
  const labels = predictions.map((_, i) => {
    const d = new Date(); d.setMinutes(d.getMinutes() + i * 30);
    return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
  });
  drawLineChart(canvas, labels, [
    { label: 'Predicted Congestion', data: predictions, color: '#7c3aed', fill: true },
    {
      label: 'Current Level', data: new Array(predictions.length).fill(
        Math.round(state.gates.reduce((s, g) => s + g.density, 0) / state.gates.length)
      ), color: 'rgba(59,130,246,0.5)', dash: [4, 4], fill: false
    }
  ], { yMax: 100, unit: '%' });

  const peak = Math.max(...predictions);
  const peakIdx = predictions.indexOf(peak);
  setEl('peak-val', peak + '%');
  const d2 = new Date(); d2.setMinutes(d2.getMinutes() + peakIdx * 30);
  setEl('peak-time', d2.getHours().toString().padStart(2, '0') + ':' + d2.getMinutes().toString().padStart(2, '0'));
  setEl('ai-confidence', (88 + Math.round(Math.random() * 8)) + '%');
}

// ─── GENERIC LINE CHART ─────────────────────────────────────────────────────
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

// ─── BAR CHART ──────────────────────────────────────────────────────────────
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

// ─── DONUT CHART ────────────────────────────────────────────────────────────
function drawDonutChart(canvas, labels, data, colors) {
  const size = Math.min(canvas.offsetWidth || 280, 260);
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext('2d');
  const cx = size / 2, cy = size / 2, ro = size * 0.38, ri = size * 0.24;
  const total = data.reduce((a, b) => a + b, 0);
  let angle = -Math.PI / 2;
  data.forEach((v, i) => {
    const sweep = (v / total) * (Math.PI * 2);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, ro, angle, angle + sweep);
    ctx.closePath();
    ctx.fillStyle = colors[i];
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
    ctx.fillText(labels[i], lx, ly);
    ctx.font = '700 11px Inter'; ctx.fillStyle = colors[i];
    ctx.fillText(Math.round(v / total * 100) + '%', cx + (ro * 0.65) * Math.cos(mid), cy + (ro * 0.65) * Math.sin(mid) + 4);
    angle += sweep;
  });
  ctx.fillStyle = 'rgba(240,244,255,0.9)'; ctx.font = '700 18px Inter'; ctx.textAlign = 'center';
  ctx.fillText(total, cx, cy + 4);
  ctx.font = '10px Inter'; ctx.fillStyle = 'rgba(139,159,193,0.7)';
  ctx.fillText('Total', cx, cy + 18);
}

// ─── GATE LIST MINI ─────────────────────────────────────────────────────────
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

// ─── ALERTS MINI ────────────────────────────────────────────────────────────
function renderAlertsMini() {
  const el = document.getElementById('alerts-list-mini');
  if (!el) return;
  const shown = state.alerts.slice(0, 4);
  el.innerHTML = shown.length ? shown.map(a => alertHTML(a, true)).join('')
    : '<p style="color:var(--text-muted);font-size:0.8rem;padding:8px 0;">No active alerts 🎉</p>';
}

function alertHTML(a, mini = false) {
  const icons = { critical: '🔴', warning: '🟡', info: '🔵' };
  return `<div class="alert-item ${a.severity}" data-id="${a.id}" style="display:${state.alertFilter !== 'all' && state.alertFilter !== a.severity ? 'none' : 'flex'}">
    <span class="alert-icon">${icons[a.severity] || 'ℹ️'}</span>
    <div class="alert-content">
      <div class="alert-title">${a.title}</div>
      <div class="alert-desc">${a.desc}</div>
    </div>
    <span class="alert-time">${a.time}</span>
    ${!mini ? `<button class="alert-dismiss" onclick="dismissAlert('${a.id}')">✕</button>` : ''}
  </div>`;
}

// ─── SHUTTLE MINI ────────────────────────────────────────────────────────────
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

// ─── ROUTE NUDGES MINI ──────────────────────────────────────────────────────
function renderRouteNudgesMini() {
  const el = document.getElementById('route-nudges-mini');
  if (!el) return;
  el.innerHTML = state.routes.slice(0, 3).map(r => `
    <div class="nudge-item">
      <div class="nudge-icon">🗺️</div>
      <div class="nudge-content">
        <div class="nudge-title">${r.from} → ${r.to}</div>
        <div class="nudge-desc">Take: ${r.recommended}</div>
      </div>
      <span class="nudge-saving">-${r.savings}</span>
    </div>`).join('');
}

// ─── GATES VIEW ─────────────────────────────────────────────────────────────
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
          <span class="gate-prediction-val">${g.density >= 80 ? '⚠️ Redirect to Gate ' + getAlternateGate(g.id) : g.density >= 60 ? 'Monitor closely' : 'Normal flow'}</span>
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

// ─── SHUTTLE VIEW ────────────────────────────────────────────────────────────
function renderShuttleView() {
  // Forecast chart
  const fc = document.getElementById('shuttle-forecast-chart');
  if (fc) {
    const labels = Array.from({ length: 12 }, (_, i) => {
      const d = new Date(); d.setMinutes(d.getMinutes() + i * 30);
      return d.getHours() + ':' + d.getMinutes().toString().padStart(2, '0');
    });
    drawLineChart(fc, labels, [
      { label: 'Predicted Demand', data: labels.map((_, i) => mlPredict(i * 0.5, 72)), color: '#7c3aed', fill: true },
      { label: 'Capacity', data: new Array(12).fill(85), color: 'rgba(239,68,68,0.6)', dash: [6, 4], fill: false },
    ], { yMax: 100, unit: '%' });
  }

  // Fleet status
  const fleet = document.getElementById('shuttle-fleet-status');
  if (fleet) {
    fleet.innerHTML = state.shuttles.map(s => {
      const pct = Math.round(s.load / s.capacity * 100);
      const c = pct >= 90 ? 'var(--accent-red)' : pct >= 60 ? 'var(--moderate-color)' : 'var(--low-color)';
      return `<div class="fleet-item">
        <span class="shuttle-indicator ${s.status}"></span>
        <div style="flex:1">
          <div style="font-size:0.82rem;font-weight:600;">${s.name}</div>
          <div style="font-size:0.7rem;color:var(--text-muted)">${s.route}</div>
        </div>
        <div style="min-width:80px">
          <div class="fleet-status-bar"><div class="fleet-bar-fill" style="width:${pct}%;background:${c}"></div></div>
        </div>
        <span style="font-size:0.78rem;font-weight:700;min-width:36px;text-align:right;color:${c}">${pct}%</span>
      </div>`;
    }).join('');
  }

  // Route utilization donut
  const rc = document.getElementById('shuttle-route-chart');
  if (rc) {
    drawDonutChart(rc, ['Gate A→C', 'Gate C→E', 'Gate F→B', 'Event'],
      [380, 240, 195, 120], ['#3b82f6', '#7c3aed', '#10b981', '#f59e0b']);
  }

  // Dispatch recommendations
  const dr = document.getElementById('shuttle-dispatch-recs');
  if (dr) {
    const recs = [
      { icon: '🚌', title: 'Deploy S6 — Gate C', reason: 'Predicted 91% crowd at Gate C in 20 min', action: 'Dispatch immediately to Sports Complex route' },
      { icon: '⚡', title: 'Increase S4 Frequency', reason: 'Load at 95%. 47 passengers waiting at Gate B', action: 'Reduce interval from 15min → 8min' },
      { icon: '🔄', title: 'Reroute S3', reason: 'Gate F congestion spike expected at 17:30', action: 'Redirect via east corridor to reduce 8min delay' },
      { icon: '📍', title: 'Pre-position for Event', reason: 'Cultural Night 19:00 — Amphitheatre (400 pax)', action: 'Stage 2 shuttles at south entrance by 18:30' },
    ];
    dr.innerHTML = `<div class="dispatch-grid">${recs.map(r => `
      <div class="dispatch-item">
        <div class="d-head"><span class="d-icon">${r.icon}</span>${r.title}</div>
        <div class="d-reason">${r.reason}</div>
        <div class="d-action">→ ${r.action}</div>
      </div>`).join('')}</div>`;
  }
}

// ─── ROUTES VIEW ─────────────────────────────────────────────────────────────
function renderRoutesView() {
  const rr = document.getElementById('route-recommendations-full');
  if (rr) {
    rr.innerHTML = state.routes.map((r, i) => `
      <div class="route-rec-item">
        <div class="route-num">${i + 1}</div>
        <div class="route-rec-content">
          <div class="r-title">${r.from} → ${r.to}</div>
          <div class="r-desc">✅ Recommended: ${r.recommended} &nbsp;|&nbsp; ❌ Avoid: ${r.avoid}</div>
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
    sd.innerHTML = [
      { val: '1,284', label: 'People Rerouted', color: 'var(--accent-cyan)' },
      { val: '32 min', label: 'Avg Time Saved', color: 'var(--accent-green)' },
      { val: '67%', label: 'Congestion Reduced', color: 'var(--accent-purple)' },
      { val: '98.2%', label: 'AI Accuracy', color: 'var(--accent-orange)' },
    ].map(s => `<div class="stat-box"><div class="stat-val" style="color:${s.color}">${s.val}</div><div class="stat-label">${s.label}</div></div>`).join('');
  }
}

// ─── EVENTS VIEW ─────────────────────────────────────────────────────────────
function renderEventsView() {
  const tl = document.getElementById('events-timeline');
  if (tl) {
    tl.innerHTML = state.events.map(ev => `
      <div class="timeline-item">
        <span class="timeline-time">${ev.time}</span>
        <div class="timeline-dot" style="background:${ev.impact === 'high' ? 'var(--accent-red)' : ev.impact === 'medium' ? 'var(--accent-orange)' : 'var(--accent-green)'}"></div>
        <div class="timeline-content">
          <div class="t-title">${ev.title}</div>
          <div class="t-location">📍 ${ev.location} &nbsp;·&nbsp; 👥 ${ev.attendees.toLocaleString()} expected</div>
          <span class="t-impact impact-${ev.impact}">${ev.impact.toUpperCase()} IMPACT</span>
        </div>
      </div>`).join('');
  }

  const il = document.getElementById('events-impact-list');
  if (il) {
    il.innerHTML = state.events.map(ev => `
      <div class="impact-list-item">
        <div style="flex:1"><div style="font-size:0.82rem;font-weight:600">${ev.title}</div>
        <div style="font-size:0.7rem;color:var(--text-muted)">${ev.time} · ${ev.attendees.toLocaleString()} pax</div></div>
        <span class="impact-badge impact-${ev.impact}">${ev.impact.toUpperCase()}</span>
      </div>`).join('');
  }

  const ehc = document.getElementById('event-history-chart');
  if (ehc) {
    drawBarChart(ehc, state.events.map(e => e.time),
      [{ label: 'Impact', color: '#7c3aed', data: state.events.map(e => e.impact === 'high' ? 85 : e.impact === 'medium' ? 55 : 30) }],
      { yMax: 100 });
  }
}

// ─── ALERTS VIEW ─────────────────────────────────────────────────────────────
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

// ─── ANALYTICS VIEW ──────────────────────────────────────────────────────────
function renderAnalyticsView() {
  const awc = document.getElementById('analytics-weekly-chart');
  if (awc) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    drawLineChart(awc, days, [
      { label: 'Gate Traffic', data: [72, 68, 80, 85, 90, 55, 42], color: '#3b82f6', fill: true },
      { label: 'Shuttle Usage', data: [65, 62, 74, 78, 83, 48, 36], color: '#10b981', fill: false },
    ], { yMax: 100, unit: '%' });
  }

  const apc = document.getElementById('analytics-peak-chart');
  if (apc) {
    drawDonutChart(apc, ['8–10am', '12–2pm', '4–6pm', 'Other'],
      [28, 22, 32, 18], ['#3b82f6', '#f59e0b', '#ef4444', '#6b7280']);
  }

  const is = document.getElementById('impact-stats');
  if (is) {
    is.innerHTML = [
      { val: '34%', label: 'Congestion Reduction', change: '+8% vs last week' },
      { val: '18 min', label: 'Avg Delay Saved', change: '+3 min improvement' },
      { val: '4,821', label: 'Smart Nudges Sent', change: 'Today' },
      { val: '96.4%', label: 'Satisfaction Score', change: 'Admin rating' },
    ].map(s => `<div class="impact-stat"><div class="impact-val">${s.val}</div>
      <div class="impact-label">${s.label}</div>
      <div class="impact-change">${s.change}</div></div>`).join('');
  }

  const mm = document.getElementById('ml-metrics');
  if (mm) {
    mm.innerHTML = [
      { name: 'Precision', val: '94.2%', detail: 'Congestion model' },
      { name: 'Recall', val: '91.8%', detail: 'Alert detection' },
      { name: 'F1-Score', val: '93.0%', detail: 'Overall model' },
      { name: 'MAPE', val: '3.7%', detail: 'Demand forecast' },
      { name: 'Latency', val: '42 ms', detail: 'Avg inference time' },
      { name: 'Data Points', val: '182K', detail: 'Training samples' },
      { name: 'Model Version', val: 'v2.1.4', detail: 'Last trained 2d ago' },
      { name: 'Uptime', val: '99.98%', detail: '30-day SLA' },
    ].map(m => `<div class="ml-metric"><div class="ml-metric-name">${m.name}</div>
      <div class="ml-metric-val">${m.val}</div>
      <div class="ml-metric-detail">${m.detail}</div></div>`).join('');
  }
}

// ─── ALERT ENGINE ────────────────────────────────────────────────────────────
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
        title: `🚨 CRITICAL: ${g.name} Congestion`,
        desc: `Density at ${g.density}% — Exceeds critical threshold (${state.thresholds.critical}%). Redirect to Gate ${getAlternateGate(g.id)}.`,
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
      });
    }
  });

  warningGates.forEach(g => {
    if (!state.alerts.find(a => a.gateId === g.id && a.severity === 'warning')) {
      addAlert({
        severity: 'warning', gateId: g.id,
        title: `⚠️ Warning: ${g.name} Rising`,
        desc: `Density at ${g.density}% and increasing. AI predicts peak of ${g.predicted}% within 30 min.`,
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
      });
    }
  });

  overloadedShuttles.forEach(s => {
    if (!state.alerts.find(a => a.shuttleId === s.id)) {
      addAlert({
        severity: 'warning', shuttleId: s.id,
        title: `🚌 Shuttle Overload: ${s.name}`,
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
    setEl('alert-banner-text', alert.title + ' — ' + alert.desc);
    if (banner) banner.style.display = 'flex';
    setTimeout(() => { if (banner) banner.style.display = 'none'; }, 8000);
  }
}

// ─── SIMULATION LOOP ─────────────────────────────────────────────────────────
function startSimulationLoop() {
  // Initial alerts
  addAlert({ severity: 'critical', gateId: 'C', title: '🚨 CRITICAL: Gate C Congestion', desc: 'Density at 88% — Sports Meet crowd. Redirect to Gate B inner path.', time: '15:58' });
  addAlert({ severity: 'warning', gateId: 'A', title: '⚠️ Warning: Gate A Rising', desc: 'Density at 72%, predicted 85% at 16:30. Deploy extra marshals.', time: '15:56' });
  addAlert({ severity: 'info', gateId: 'F', title: 'ℹ️ Gate F: Lunch Rush Subsiding', desc: 'Density dropping from 78% to 64%. Traffic normalizing.', time: '15:50' });

  updateKPIs();
  setEl('alert-badge', state.alerts.length);

  setInterval(() => {
    state.tick++;
    // Evolve gate densities (random walk with bounds + time-based trend)
    state.gates.forEach(g => {
      const drift = (Math.random() - 0.48) * 3;
      g.density = Math.min(99, Math.max(5, Math.round(g.density + drift)));
      g.predicted = Math.min(99, Math.max(10, Math.round(mlPredict(1, g.density))));
      g.trend.push(g.density);
      if (g.trend.length > 20) g.trend.shift();
      g.entries += Math.round(Math.random() * 8);
    });

    // Evolve shuttle loads
    state.shuttles.forEach(s => {
      if (s.status === 'active') {
        const d = (Math.random() - 0.45) * 4;
        s.load = Math.min(s.capacity, Math.max(0, s.load + d));
        s.eta = Math.max(1, s.eta + (Math.random() > 0.5 ? -1 : 1));
      }
    });

    // Evolve heatZones
    state.heatZones.forEach((z, i) => {
      const ref = state.gates[i % state.gates.length].density;
      z.density += (ref - z.density) * 0.1 + (Math.random() - 0.5) * 3;
      z.density = Math.min(99, Math.max(5, z.density));
    });

    checkAndGenerateAlerts();
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

    // ── Backend sync every 4s (every 2 ticks) ─────────────────────────────
    if (state.tick % 2 === 0) {
      syncWithBackend();
    }
  }, 2000);
}

// ─── LIVE CLOCK ──────────────────────────────────────────────────────────────
function startLiveClock() {
  const el = document.getElementById('live-clock');
  function tick() {
    if (el) el.textContent = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  }
  tick();
  setInterval(tick, 1000);
}

// ─── THRESHOLD SLIDERS ───────────────────────────────────────────────────────
function bindThresholdSliders() { /* bound inline */ }

// ─── START ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
