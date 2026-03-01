# SmartCampus AI — Flask Backend

A clean, scalable Flask REST API for the Smart Campus Mobility System.

## Quick Start

```bash
# 1. Install dependencies
pip install flask flask-cors flask-sqlalchemy flask-jwt-extended python-dotenv

# 2. Run the server
cd smart-campus-backend
python run.py
```

Server starts at **http://127.0.0.1:5000**

---

## Project Structure

```
smart-campus-backend/
├── app/
│   ├── __init__.py          ← Flask app factory (create_app)
│   ├── config.py            ← Multi-env config (Dev / Prod / Test)
│   ├── extensions.py        ← db, jwt singletons (avoids circular imports)
│   ├── routes/
│   │   ├── traffic.py       ← Traffic & congestion API (8 endpoints)
│   │   └── auth.py          ← Register / Login / Profile (JWT)
│   ├── models/
│   │   ├── traffic_model.py ← TrafficEntry, GateStatus, ShuttleStatus ORM
│   │   └── user_model.py    ← User ORM with bcrypt password hashing
│   └── services/
│       ├── ai_service.py    ← ML prediction + LLM-ready analysis engine
│       └── congestion_service.py ← Rule-based alerts + seed data
├── run.py                   ← Entry point
├── requirements.txt
├── .env                     ← Environment variables (never commit!)
└── README.md
```

---

## API Reference

### Traffic

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/traffic/add` | Ingest a traffic data point |
| GET | `/api/traffic/all` | Get all entries (filterable) |
| GET | `/api/traffic/congestion` | Rule-based congestion alerts |
| GET | `/api/traffic/gates` | Per-gate stats + AI 1-hr forecast |
| POST | `/api/traffic/predict` | Full AI traffic analysis |
| GET | `/api/traffic/routes` | Smart route nudges |
| GET | `/api/traffic/shuttles` | Fleet status |
| POST | `/api/traffic/shuttles/update` | Update shuttle load/status |

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/auth/me` | My profile (requires Bearer token) |
| POST | `/api/auth/logout` | Logout (acknowledge) |

---

## Example Requests

**Add traffic data:**
```bash
curl -X POST http://127.0.0.1:5000/api/traffic/add \
  -H "Content-Type: application/json" \
  -d '{"location": "Gate A", "count": 250, "gate_id": "A", "source": "sensor"}'
```

**Get AI analysis:**
```bash
curl -X POST http://127.0.0.1:5000/api/traffic/predict \
  -H "Content-Type: application/json" \
  -d '{"traffic_data": [{"location": "Gate A", "count": 380}, {"location": "Gate C", "count": 210}]}'
```

**Login and get token:**
```bash
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@campus.edu", "password": "password123"}'
```

---

## Connecting the Frontend

Add this to your `app.js` to connect to the live backend:

```js
// Replace the simulation tick with a real API call:
fetch("http://127.0.0.1:5000/api/traffic/gates")
  .then(r => r.json())
  .then(data => {
    // data.gates → same shape as state.gates
    state.gates = data.gates.map(g => ({...g, trend: []}));
    renderGateListMini();
  });
```

---

## Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me` | Flask secret key |
| `DATABASE_URL` | `sqlite:///smart_campus.db` | DB connection string |
| `JWT_SECRET_KEY` | `jwt-super-secret` | JWT signing key |
| `JWT_EXPIRES_HOURS` | `24` | Token lifetime |
| `CORS_ORIGINS` | `*` | Allowed origins |
| `AI_CONGESTION_THRESHOLD` | `200` | Warning alert count |
| `AI_CRITICAL_THRESHOLD` | `350` | Critical alert count |
| `USE_LLM` | `false` | Enable real LLM (OpenAI) |
| `OPENAI_API_KEY` | — | Your OpenAI key (if `USE_LLM=true`) |
