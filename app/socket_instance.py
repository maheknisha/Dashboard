from flask_socketio import SocketIO

# Create a single Socket.IO instance
socketio = SocketIO(cors_allowed_origins="*")  # allow all origins for dev
