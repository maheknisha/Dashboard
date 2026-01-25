
# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import redis
from .config import Config  # ✅ correct import

db = SQLAlchemy()
socketio = SocketIO()

# Redis client
redis_client = redis.StrictRedis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    db=Config.REDIS_DB,
    decode_responses=True
)
