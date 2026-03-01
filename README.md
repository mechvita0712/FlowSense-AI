# 🎓 Smart Campus Crowd Detection & Gate Redirection System

Complete AI-powered crowd detection system with automated gate redirection logic using YOLOv8, ByteTrack, and real-time WebSocket notifications.

## 🎯 Features Implemented

### ✅ Detection & Tracking (gate_monitor/)
- **YOLOv8** person detection with GPU acceleration
- **ByteTrack** multi-object tracking (no duplicate counting)
- Virtual line counting with IN/OUT direction detection
- Per-gate SQLite event logging
- Automated API posting to backend every 30s

### ✅ Backend API (smart-campus-backend/)
- **Flask + Flask-SocketIO** for real-time communication
- **Dynamic per-gate capacity management** with admin API
- **WebSocket push notifications** for instant alerts
- **API key authentication** for sensor endpoints
- **Mobile push notification endpoints** (FCM/APNs ready)
- **13+ REST API endpoints** for traffic, gates, shuttles, routes
- **Anti-Gravity AI** prediction engine with anomaly detection

### ✅ Frontend Dashboard (smart-campus-frontend/)
- **Real-time WebSocket** integration - no polling needed
- **Redirection alert modal** - automatic popup when gate is full
- **Admin settings panel** - manage gate capacities in real-time
- **8 interactive views**: Dashboard, Map, Gates, Shuttles, Routes, Events, Alerts, Analytics, Admin
- **Live heatmap** with Canvas rendering
- **Responsive design** with collapsible sidebar

### ✅ Key APIs

#### Crowd Status
```http
GET /api/traffic/crowd-status?gate_id=A
Response: {
  "current_count": 35,
  "max_capacity": 50,
  "density": 70.0,
  "status": "WARNING",
  "redirect_gate": null
}
```

#### Update Capacity
```http
POST /api/traffic/update-capacity
Body: {"gate_id": "A", "capacity": 40}
```

#### Admin Capacity Management
```http
POST /api/admin/capacity/gate/A
Headers: Authorization: Bearer <JWT_TOKEN>
Body: {"capacity": 30, "use_global": false}

POST /api/admin/capacity/global
Body: {"capacity": 50, "gate_ids": ["A","B","C"]}

GET /api/admin/capacity/all
```

#### Mobile Push Notifications
```http
POST /api/mobile/register
Body: {
  "device_id": "unique-uuid",
  "token": "fcm-token",
  "platform": "android"
}

POST /api/mobile/send-redirect
Headers: Authorization: Bearer <JWT_TOKEN>
Body: {
  "gate_id": "A",
  "redirect_to": "B",
  "message": "Gate A is full. Redirect to Gate B"
}
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ with Anaconda
- Conda environment named "croud"
- USB webcam or video file for testing

### 1. Install Backend Dependencies
```bash
cd smart-campus-backend
conda activate croud
pip install -r requirements.txt
```

### 2. Configure Environment Variables

**Backend** (`smart-campus-backend/.env`):
```env
SECRET_KEY=smartcampus-flask-secret-key-change-in-production-2026
JWT_SECRET_KEY=smartcampus-jwt-secret-key-change-in-production-2026
API_KEY=smartcampus-secret-key-2026
DEFAULT_GLOBAL_CAPACITY=50
DATABASE_URL=sqlite:///smart_campus.db
```

**Gate Monitor** (`gate_monitor/.env`):
```env
CAMERA_SOURCE=0
GATE_ID=A
GATE_LOCATION=Main Entrance, North
API_URL=http://localhost:5000/api/traffic/add
API_KEY=smartcampus-secret-key-2026
```

### 3. Start Backend Server
```bash
cd smart-campus-backend
C:\Users\Admin\anaconda3\envs\croud\python.exe run.py
```

Backend will start on: http://localhost:5000

### 4. Start Gate Monitor
```bash
cd gate_monitor
C:\Users\Admin\anaconda3\envs\croud\python.exe main.py
```

For testing with video file:
```bash
python main.py --source path/to/video.mp4 --gate-id A --location "Main Gate"
```

### 5. Open Frontend Dashboard
Open `smart-campus-frontend/index.html` in your browser (Chrome/Edge recommended)

The frontend will automatically:
- Connect to backend via WebSocket
- Display real-time crowd updates
- Show redirection alerts when gates are full

## 📊 System Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Gate Monitor   │         │  Flask Backend   │         │   Frontend      │
│  (YOLOv8 +      │◄────────┤  (Flask-SocketIO)│◄────────┤   Dashboard     │
│   ByteTrack)    │  HTTP   │                  │ WebSocket│                 │
│                 │  POST   │  - REST APIs     │         │  - Real-time UI │
│  - Detection    │         │  - WebSocket     │         │  - Admin Panel  │
│  - Tracking     │         │  - Database      │         │  - Alerts       │
│  - Counting     │         │  - Auth          │         │                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

## 🎮 Usage Examples

### Scenario 1: Single Gate Monitoring
1. Start backend
2. Start gate monitor for Gate A
3. Open frontend dashboard
4. Watch real-time crowd count in "Gates" view
5. When count exceeds capacity, alert modal will appear

### Scenario 2: Multi-Gate System
1. Start backend
2. Run multi-gate simulator:
   ```bash
   python gate_monitor/multi_gate_runner.py --source test_video.mp4
   ```
3. Open frontend - see all 10 gates updating in real-time
4. Use Admin panel to set different capacities per gate

### Scenario 3: Admin Configuration
1. Login to backend (POST /api/auth/login)
2. Navigate to Admin view in frontend
3. Adjust gate capacities
4. See density calculations update immediately

## 🔧 Configuration Options

### Gate Capacity Settings
- **Per-Gate Mode**: Each gate has individual capacity
- **Global Mode**: All gates share same capacity
- **Admin UI**: Change settings without server restart

### Detection Settings (gate_monitor/.env)
- `CONFIDENCE_THRESHOLD`: 0.45 (adjust for accuracy vs speed)
- `LINE_POSITION`: 0.5 (virtual line position in frame)
- `POST_INTERVAL_SEC`: 30 (how often to send data to backend)

### Capacity Thresholds (smart-campus-backend/.env)
- `DEFAULT_GLOBAL_CAPACITY`: 50 (default people capacity)
- `DEFAULT_WARNING_THRESHOLD`: 0.7 (70% = warning)
- `DEFAULT_CRITICAL_THRESHOLD`: 0.9 (90% = critical)

## 📡 WebSocket Events

### Client → Server
None currently (future: manual overrides)

### Server → Client
- `crowd_update`: Real-time gate status
  ```json
  {
    "gate_id": "A",
    "count": 35,
    "density": 70.0,
    "capacity": 50,
    "status": "WARNING"
  }
  ```

- `gate_full_alert`: Redirection notification
  ```json
  {
    "gate_id": "A",
    "redirect_to": "B",
    "message": "Gate A is FULL. Please redirect to Gate B"
  }
  ```

- `capacity_updated`: Admin changed capacity
  ```json
  {
    "gate_id": "A",
    "capacity": 40,
    "use_global": false
  }
  ```

## 🐛 Troubleshooting

### Backend won't start
- Check conda environment is activated
- Verify all packages installed: `pip install -r requirements.txt`
- Check port 5000 is available

### Gate monitor can't connect to camera
- Try different CAMERA_SOURCE values (0, 1, 2)
- For testing, use a video file: `--source video.mp4`
- Check camera permissions in Windows

### Frontend shows "Backend Offline"
- Verify backend is running on port 5000
- Check browser console for CORS errors
- Ensure firewall allows localhost connections

### WebSocket not connecting
- Check Flask-SocketIO is installed
- Verify Socket.IO CDN loaded in browser network tab
- Check browser console for connection errors

## 📦 Project Structure

```
c2/
├── gate_monitor/              # YOLOv8 detection & tracking
│   ├── main.py               # Single gate runner
│   ├── multi_gate_runner.py  # 10-gate simulator
│   ├── detector.py           # YOLOv8 wrapper
│   ├── tracker.py            # ByteTrack integration
│   ├── counter.py            # Virtual line counting
│   ├── api_client.py         # Backend API client
│   ├── db_logger.py          # SQLite logging
│   └── .env                  # Configuration
│
├── smart-campus-backend/      # Flask API server
│   ├── app/
│   │   ├── __init__.py       # App factory
│   │   ├── extensions.py     # SQLAlchemy, JWT, SocketIO
│   │   ├── config.py         # Environment config
│   │   ├── models/           # Database models
│   │   │   ├── traffic_model.py
│   │   │   └── user_model.py
│   │   ├── routes/           # API endpoints
│   │   │   ├── traffic.py    # Traffic & crowd APIs
│   │   │   ├── admin.py      # Admin capacity management
│   │   │   ├── mobile.py     # Mobile push notifications
│   │   │   ├── auth.py       # JWT authentication
│   │   │   └── antigravity.py # AI prediction engine
│   │   └── services/         # Business logic
│   │       ├── ai_service.py
│   │       ├── congestion_service.py
│   │       └── antigravity_service.py
│   ├── run.py                # Server entry point
│   └── .env                  # Configuration
│
└── smart-campus-frontend/     # Web dashboard
    ├── index.html            # Main UI
    ├── app.js                # Frontend logic + WebSocket
    └── index.css             # Styles

```

## 🔐 Security Notes

- API key authentication protects POST /api/traffic/add
- JWT tokens required for admin endpoints
- In production, use HTTPS and strong secrets
- Change all default keys in .env files

## 🚀 Production Deployment

For production use:
1. Replace SQLite with PostgreSQL
2. Use gunicorn/waitress WSGI server
3. Setup nginx reverse proxy
4. Enable HTTPS with SSL certificates
5. Implement proper logging and monitoring
6. Add rate limiting
7. Deploy with Docker/Kubernetes

## 📝 API Documentation

Full API documentation available at:
- Backend root: http://localhost:5000/api
- Health check: http://localhost:5000/api/health

## 🎉 Success! Your System is Ready

You now have a fully functional crowd detection system with:
- ✅ Real-time person tracking
- ✅ Duplicate-free counting
- ✅ Automated gate redirection
- ✅ WebSocket live updates
- ✅ Admin capacity management
- ✅ Mobile push notification support

**Next Steps:**
1. Test with live camera feed
2. Configure gate capacities via Admin panel
3. Monitor real-time alerts
4. Integrate with mobile app (optional)
5. Deploy to production server

For questions or issues, refer to this documentation or check the inline code comments.

---

**Built with:** YOLOv8, ByteTrack, Flask, Flask-SocketIO, SQLAlchemy, JWT, Socket.IO Client, HTML5 Canvas

**License:** Educational/Research Use

**Date:** February 27, 2026
