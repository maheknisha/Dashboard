
from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy import func, case
from app.extensions import db, socketio
from app.models import Chat, Message
from app.utils.auth import token_required

chat_bp = Blueprint("chat_bp", __name__, url_prefix="/chat")
@chat_bp.route("/start", methods=["POST"])
@token_required
def start_chat(current_user):
    data = request.get_json()
    strategy_id = data.get("strategy_id")
    creator_id = data.get("creator_id")

    if not strategy_id or not creator_id:
        return jsonify({
            "status": "error",
            "message": "Missing strategy_id or creator_id"
        }), 400

    chat = Chat.query.filter_by(
        strategy_id=strategy_id,
        creator_id=creator_id,
        user_id=current_user.id
    ).first()

    is_new_chat = False

    if not chat:
        chat = Chat(
            strategy_id=strategy_id,
            creator_id=creator_id,
            user_id=current_user.id,
            updated_at=datetime.utcnow()
        )
        db.session.add(chat)
        is_new_chat = True
    else:
        # 🔥 bring existing chat to top when reopened
        chat.updated_at = datetime.utcnow()

    db.session.commit()

    socketio.emit(
        "question_asked",
        {
            "chat_id": chat.id,
            "strategy_id": chat.strategy_id,
            "strategy_name": getattr(chat.strategy, "name", None),
            "asked_by": {
                "user_id": current_user.id,
                "user_name": current_user.name
            },
            "created_at": chat.created_at.isoformat(),
            "is_new_chat": is_new_chat
        },
        room=f"user_{creator_id}"
    )

    return jsonify({
        "status": "success",
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
        return jsonify({"status": "error", "message": "Access denied"}), 403

    data = request.get_json()
    content = data.get("content")

    if not content:
        return jsonify({"status": "error", "message": "Content is required"}), 400

    receiver_id = chat.creator_id if current_user.id == chat.user_id else chat.user_id

    message = Message(
        chat_id=chat.id,
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        created_at=datetime.utcnow(),
        is_read=False
    )

    db.session.add(message)

    # 🔥 bump chat to top
    chat.updated_at = datetime.utcnow()

    db.session.commit()

    message_data = {
        "message_id": message.id,
        "chat_id": chat.id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.name,
        "receiver_id": message.receiver_id,
        "receiver_name": message.receiver.name,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "is_read": message.is_read
    }

    for uid in {current_user.id, receiver_id}:
        socketio.emit("new_message", message_data, room=f"user_{uid}")

    return jsonify({
        "status": "success",
        "data": message_data
    }), 201


# -------------------------------------------------
# LIST CHATS (UNREAD FIRST, NEWEST ON TOP)
# -------------------------------------------------
@chat_bp.route("/list", methods=["GET"])
@token_required
def list_chats(current_user):

    unread_subquery = (
        db.session.query(
            Message.chat_id,
            func.count(Message.id).label("unread_count")
        )
        .filter(
            Message.receiver_id == current_user.id,
            Message.is_read.is_(False)
        )
        .group_by(Message.chat_id)
        .subquery()
    )

    chats = (
        db.session.query(
            Chat,
            func.coalesce(unread_subquery.c.unread_count, 0).label("unread_count")
        )
        .outerjoin(unread_subquery, Chat.id == unread_subquery.c.chat_id)
        .filter(
            (Chat.creator_id == current_user.id) |
            (Chat.user_id == current_user.id)
        )
        .order_by(
            case(
                (func.coalesce(unread_subquery.c.unread_count, 0) > 0, 1),
                else_=0
            ).desc(),
            Chat.updated_at.desc()
        )
        .all()
    )

    data = []

    for chat, unread_count in chats:
        last_msg = (
            Message.query
            .filter_by(chat_id=chat.id)
            .order_by(Message.created_at.desc())
            .first()
        )

        data.append({
            "id": chat.id,
            "strategy_id": chat.strategy_id,
            "strategy_name": chat.strategy.name if chat.strategy else "No strategy",
            "creator_id": chat.creator_id,
            "creator_name": chat.creator.name if chat.creator else "Unknown",
            "user_id": chat.user_id,
            "user_name": chat.user.name if chat.user else "Unknown",
            "last_message": last_msg.content if last_msg else "",
            "last_message_sender_id": last_msg.sender_id if last_msg else None,
            "last_message_sender_name": last_msg.sender.name if last_msg else "",
            "updated_at": chat.updated_at,
            "unread_count": unread_count
        })

    return jsonify({"status": "success", "data": data}), 200


# -------------------------------------------------
# GET MESSAGES (ASCENDING)
# -------------------------------------------------
@chat_bp.route("/<int:chat_id>/messages", methods=["GET"])
@token_required
def get_messages(current_user, chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if current_user.id not in [chat.user_id, chat.creator_id]:
        return jsonify({"status": "error", "message": "Access denied"}), 403

    messages = (
        Message.query
        .filter_by(chat_id=chat.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    data = [{
        "id": m.id,
        "sender_id": m.sender_id,
        "sender_name": m.sender.name,
        "receiver_id": m.receiver_id,
        "receiver_name": m.receiver.name,
        "content": m.content,
        "is_read": m.is_read,
        "created_at": m.created_at.isoformat()
    } for m in messages]

    return jsonify({"status": "success", "data": data}), 200


# -------------------------------------------------
# MARK AS READ
# -------------------------------------------------
@chat_bp.route("/<int:chat_id>/read", methods=["PUT"])
@token_required
def mark_as_read(current_user, chat_id):
    chat = Chat.query.get_or_404(chat_id)

    if current_user.id not in [chat.user_id, chat.creator_id]:
        return jsonify({"status": "error", "message": "Access denied"}), 403

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
        "data": {
            "chat_id": chat.id,
            "read_count": len(message_ids)
        }
    }), 200


# -------------------------------------------------
# ALL UNREAD COUNTS
# -------------------------------------------------
@chat_bp.route("/all-unread-counts", methods=["GET"])
@token_required
def all_unread_counts(current_user):
    chats = Chat.query.filter(
        (Chat.user_id == current_user.id) |
        (Chat.creator_id == current_user.id)
    ).order_by(Chat.id.asc()).all()

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

        socketio.emit(
            "unread_count_update",
            {"chat_id": chat.id, "unread_count": count},
            room=f"user_{current_user.id}"
        )

    return jsonify({
        "status": "success",
        "data": result
    }), 200


# -------------------------------------------------
# PROFILE
# -------------------------------------------------
@chat_bp.route("/profile", methods=["GET"])
@token_required
def get_profile(current_user):
    return jsonify({
        "status": "success",
        "data": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "phone": current_user.phone,
            "address": current_user.address,
            "is_verified": current_user.is_verified
        }
    }), 200
