
from email.mime import message
from flask import Blueprint, request, jsonify
from datetime import datetime

from app.extensions import db, socketio
from app.models import Chat, Message
from app.utils.auth import token_required

chat_bp = Blueprint("chat_bp", __name__, url_prefix="/chat")


# Keep this, remove any other start_chat definitions
@chat_bp.route("/start", methods=["POST"])
@token_required
def start_chat(current_user):
    data = request.get_json()
    strategy_id = data.get("strategy_id")
    creator_id = data.get("creator_id")

    if not strategy_id or not creator_id:
        return jsonify({"status": "error", "message": "Missing strategy_id or creator_id", "data": None}), 400

    chat = Chat.query.filter_by(
        strategy_id=strategy_id,
        creator_id=creator_id,
        user_id=current_user.id
    ).first()

    if not chat:
        chat = Chat(strategy_id=strategy_id, creator_id=creator_id, user_id=current_user.id)
        db.session.add(chat)
        db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Chat started successfully",
        "data": {
            "chat_id": chat.id,
            "strategy_id": chat.strategy_id,
            "strategy_name": getattr(chat.strategy, "name", None),
            "creator_id": chat.creator_id,
            "creator_name": getattr(chat.creator, "name", None),
            "user_id": chat.user_id
        }
    }), 200 
@chat_bp.route("/<int:chat_id>/message", methods=["POST"])
@token_required
def send_message(current_user, chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if current_user.id not in [chat.user_id, chat.creator_id]:
        return jsonify({"status": "error", "message": "Access denied", "data": None}), 403

    data = request.get_json()
    content = data.get("content")

    if not content:
        return jsonify({
            "status": "error",
            "message": "Content is required",
            "data": None
        }), 400

    # 🔥 AUTO receiver detection
    if current_user.id == chat.user_id:
        receiver_id = chat.creator_id
    else:
        receiver_id = chat.user_id

    message = Message(
        chat_id=chat.id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        created_at=datetime.utcnow()
    )

    db.session.add(message)
    db.session.commit()

    message_data = {
        "message_id": message.id,
        "chat_id": chat.id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.name,
        "receiver_id": receiver_id,
        "receiver_name": message.receiver.name,
        "content": message.content,
        "created_at": message.created_at.isoformat()
    }

    # Emit to sender & receiver
    socketio.emit("new_message", message_data, room=f"user_{current_user.id}")
    socketio.emit("new_message", message_data, room=f"user_{receiver_id}")

    return jsonify({
        "status": "success",
        "message": "Message sent successfully",
        "data": message_data
    }), 201
@chat_bp.route("/<int:chat_id>/messages", methods=["GET"])
@token_required
def get_messages(current_user, chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if current_user.id not in [chat.user_id, chat.creator_id]:
        return jsonify({
            "status": "error",
            "message": "Access denied",
            "data": None
        }), 403

    # 🔥 MARK AS READ HERE
    Message.query.filter(
        Message.chat_id == chat.id,
        Message.receiver_id == current_user.id,
        Message.is_read.is_(False)
    ).update({"is_read": True}, synchronize_session=False)

    db.session.commit()

    messages = [{
        "id": m.id,
        "sender_id": m.sender_id,
        "sender_name": m.sender.name,
        "content": m.content,
        "created_at": str(m.created_at)
    } for m in chat.messages]

    return jsonify({
        "status": "success",
        "message": "Messages fetched successfully",
        "data": messages
    }), 200

# -------------------------------------------------
# LIST USER CHATS
# -------------------------------------------------
@chat_bp.route("/list", methods=["GET"])
@token_required
def list_chats(current_user):
    chats = Chat.query.filter(
        (Chat.user_id == current_user.id) |
        (Chat.creator_id == current_user.id)
    ).order_by(Chat.updated_at.desc()).all()

    data = []
    for c in chats:
        last_msg = c.messages[-1].content if c.messages else ""
        data.append({
            "chat_id": c.id,
            "strategy_id": c.strategy_id,
            "strategy_name": c.strategy.name,
            "creator_id": c.creator_id,
            "creator_name": c.creator.name,
            "user_id": c.user_id,
            "last_message": last_msg,
            "updated_at": str(c.updated_at)
        })

    return jsonify({
        "status": "success",
        "message": "Chats fetched successfully",
        "data": data
    }), 200
@chat_bp.route("/<int:chat_id>/read", methods=["PUT"])
@token_required
def mark_as_read(current_user, chat_id):
    chat = Chat.query.get_or_404(chat_id)

    # Only participants can mark messages
    if current_user.id not in [chat.user_id, chat.creator_id]:
        return jsonify({"status": "error", "message": "Access denied", "data": None}), 403

    # Mark all RECEIVED messages as read
    updated = Message.query.filter(
        Message.chat_id == chat.id,
        Message.receiver_id == current_user.id,
        Message.is_read.is_(False)
    ).update({"is_read": True}, synchronize_session=False)

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Messages marked as read",
        "data": {"chat_id": chat.id, "read_count": updated}
    }), 200
@chat_bp.route("/all-unread-counts", methods=["GET"])
@token_required
def all_unread_counts(current_user):
    # Fetch all chats where the user is either the creator or user
    chats = Chat.query.filter(
        (Chat.user_id == current_user.id) | (Chat.creator_id == current_user.id)
    ).all()

    # Prepare unread counts for each chat
    result = []
    for chat in chats:
        count = Message.query.filter_by(
            chat_id=chat.id,
            receiver_id=current_user.id,
            is_read=False
        ).count()
        result.append({
            "chat_id": chat.id,
            "unread_count": count
        })

    return jsonify({
        "status": "success",
        "message": "Unread counts fetched successfully",
        "data": result
    }), 200
@chat_bp.route("/profile", methods=["GET"])
@token_required
def get_profile(current_user):
    return jsonify({
        "status": "success",
        "message": "Profile fetched successfully",  # ✅ added message
        "data": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "phone": current_user.phone,
            "address": current_user.address,
            "is_verified": current_user.is_verified,
            
        }
    }), 200
