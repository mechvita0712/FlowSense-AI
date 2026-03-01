from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    # Use socketio.run for WebSocket support
    socketio.run(app, debug=True, use_reloader=False, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
