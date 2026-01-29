

from flask import Blueprint, request, jsonify
from datetime import datetime
from app.extensions import db, socketio
from app.models import Chat, Message
from app.utils.auth import token_required

chat_bp = Blueprint("chat_bp", __name__, url_prefix="/chat")

# -------------------------------------------------
# START OR FETCH CHAT
# -------------------------------------------------
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

# -------------------------------------------------
# SEND MESSAGE
# -------------------------------------------------
@chat_bp.route("/<int:chat_id>/message", methods=["POST"])
@token_required
def send_message(current_user, chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if current_user.id not in [chat.user_id, chat.creator_id]:
        return jsonify({"status": "error", "message": "Access denied", "data": None}), 403

    data = request.get_json()
    content = data.get("content")
    if not content:
        return jsonify({"status": "error", "message": "Content is required", "data": None}), 400

    # Determine receiver
    receiver_id = chat.creator_id if current_user.id == chat.user_id else chat.user_id

    # Save message
    message = Message(
        chat_id=chat.id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        created_at=datetime.utcnow(),
        is_read=False  # default: double gray tick
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
        "created_at": message.created_at.isoformat(),
        "is_read": message.is_read
    }

    # Emit to both users
    for user_id in {current_user.id, receiver_id}:
        socketio.emit("new_message", message_data, room=f"user_{user_id}")

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
        return jsonify({"status": "error", "message": "Access denied", "data": None}), 403

    messages = Message.query.filter_by(chat_id=chat.id)\
        .order_by(Message.created_at.asc())\
        .all()

    data = [{
        "id": m.id,
        "sender_id": m.sender_id,
        "sender_name": m.sender.name,
        "content": m.content,
        "is_read": m.is_read,
        "created_at": str(m.created_at)
    } for m in messages]

    return jsonify({
        "status": "success",
        "message": "Messages fetched successfully",
        "data": data
    }), 200
@chat_bp.route("/list", methods=["GET"])
@token_required
def list_chats(current_user):
    try:
        chats = Chat.query.filter(
            (Chat.creator_id == current_user.id) | (Chat.user_id == current_user.id)
        ).all()

        chat_list = []

        for c in chats:
            last_msg = None
            if c.messages:
                last_msg = sorted(c.messages, key=lambda m: m.created_at, reverse=True)[0]

            chat_list.append({
                "id": c.id,
                "strategy_id": c.strategy_id,
                "strategy_name": c.strategy.name if c.strategy else "No strategy",
                "creator_id": c.creator_id,
                "user_id": c.user_id,
                "last_message": last_msg.content if last_msg else "",
                "updated_at": c.updated_at
            })

        return jsonify({"status": "success", "data": chat_list}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@chat_bp.route("/<int:chat_id>/read", methods=["PUT"])
@token_required
def mark_as_read(current_user, chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if current_user.id not in [chat.user_id, chat.creator_id]:
        return jsonify({"status": "error", "message": "Access denied"}), 403

    # Get unread messages
    unread_messages = Message.query.filter(
        Message.chat_id == chat.id,
        Message.receiver_id == current_user.id,
        Message.is_read.is_(False)
    ).all()

    if not unread_messages:
        return jsonify({"status": "success", "message": "No unread messages"}), 200

    message_ids = []

    for msg in unread_messages:
        msg.is_read = True
        message_ids.append(msg.id)

    db.session.commit()

    # 🔥 SINGLE EMIT (not N emits)
    socketio.emit(
        "messages_read",
        {
            "chat_id": chat.id,
            "reader_id": current_user.id,
            "message_ids": message_ids
        },
        room=f"user_{chat.creator_id if current_user.id == chat.user_id else chat.user_id}"
    )

    return jsonify({
        "status": "success",
        "message": "Messages marked as read",
        "data": {
            "chat_id": chat.id,
            "read_count": len(message_ids)
        }
    }), 200

# -------------------------------------------------
# FETCH ALL UNREAD COUNTS
# -------------------------------------------------
@chat_bp.route("/all-unread-counts", methods=["GET"])
@token_required
def all_unread_counts(current_user):
    chats = Chat.query.filter(
        (Chat.user_id == current_user.id) | (Chat.creator_id == current_user.id)
    ).all()

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
        # Emit unread count update to this user
        socketio.emit(
            "unread_count_update",
            {"chat_id": chat.id, "unread_count": count},
            room=f"user_{current_user.id}"
        )

    return jsonify({
        "status": "success",
        "message": "Unread counts fetched successfully",
        "data": result
    }), 200

# -------------------------------------------------
# GET USER PROFILE
# -------------------------------------------------
@chat_bp.route("/profile", methods=["GET"])
@token_required
def get_profile(current_user):
    return jsonify({
        "status": "success",
        "message": "Profile fetched successfully",
        "data": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "phone": current_user.phone,
            "address": current_user.address,
            "is_verified": current_user.is_verified,
        }
    }), 200 