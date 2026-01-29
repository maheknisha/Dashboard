# websocket_handlers.py
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask import session, request
import jwt
from app.extensions import socketio, db
from app.models import User, Chat, Message
from datetime import datetime
# Replace with your app's secret key
SECRET_KEY = "jwt-secret-key-123"
@socketio.on("connect")
def connect_socket(auth):  # accept the auth parameter
    # Get token from query string
    token = request.args.get("token")
    chat_id = request.args.get("chat_id", type=int)  # define chat_id
    role = request.args.get("role")                  # define role
    if not token:
        return False
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
    except Exception as e:
        print("JWT decode error:", e)
        return False

    user = User.query.get(user_id)
    if not user:
        return False

    session['user_id'] = user.id
    session['user_name'] = user.name

    # 🔑 Join a personal room for private messages
    join_room(f"user_{user.id}")

    emit("connected", {
        "status": "success",
        "message": "Socket connected",
        "data": {
            "user_id": user.id,
            "user_name": user.name
        }
    })

    # Automatically join chat if chat_id and role provided
    if chat_id and role:
        chat = Chat.query.get(chat_id)
        if not chat:
            emit("error", {"status": "error", "message": "Chat not found"})
            return
        allowed_roles = {"creator": chat.creator_id, "user": chat.user_id}
        if role not in allowed_roles or user.id != allowed_roles[role]:
            emit("error", {"status": "error", "message": f"Unauthorized role '{role}'"})
            return
        room = f"chat_{chat.id}"
        join_room(room)
        emit("joined_chat", {
            "status": "success",
            "message": f"Joined chat as {role}",
            "data": {
                "chat_id": chat.id,
                "room": room,
                "role": role,
                "user_id": user.id,
                "user_name": user.name
            }
        })
@socketio.on("mark_messages_as_read")
def mark_messages_as_read(data):
    chat_id = data.get("chat_id")
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")

    reader_id = session.get("user_id")

    # 🔐 Step 1: validate user
    if not reader_id or reader_id != receiver_id:
        return

    # 🔐 Step 2: validate chat
    chat = Chat.query.get(chat_id)
    if not chat or reader_id not in [chat.user_id, chat.creator_id]:
        return

    # 🔥 Step 3: fetch unread messages
    unread_messages = Message.query.filter(
        Message.chat_id == chat_id,
        Message.receiver_id == reader_id,
        Message.is_read.is_(False)
    ).all()

    if not unread_messages:
        return

    # 🔥 Step 4: update DB
    message_ids = []
    for msg in unread_messages:
        msg.is_read = True
        message_ids.append(msg.id)

    db.session.commit()

    # 🔔 Step 5: notify sender
    socketio.emit(
        "messages_read",
        {
            "chat_id": chat_id,
            "reader_id": reader_id,
            "message_ids": message_ids
        },
        room=f"user_{sender_id}"
    )

# -----------------------------
# SOCKET DISCONNECT
# -----------------------------
@socketio.on("disconnect")
def disconnect_socket():
    user_id = session.get("user_id")
    user_name = session.get("user_name")
    if user_name:
        print(f"❌ {user_name} disconnected")
    else:
        print("❌ Socket disconnected")
# -----------------------------
# LEAVE CHAT ROOM
# -----------------------------
@socketio.on("leave_chat")
def leave_chat(data):
    chat_id = data.get("chat_id")
    user_id = session.get("user_id")
    user_name = session.get("user_name")
    if not chat_id or not user_id:
        emit("error", {"status": "error", "message": "Invalid chat_id"})
        return
    room = f"chat_{chat_id}"
    leave_room(room)
    emit("left_chat", {
        "status": "success",
        "message": f"Left chat {chat_id}",
        "data": {"chat_id": chat_id, "user_id": user_id, "user_name": user_name}
    })
