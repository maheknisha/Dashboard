from flask import Blueprint, request, jsonify
from datetime import datetime
from app.extensions import db, socketio
from app.models import Strategy, Chat
from app.utils.auth import token_required

strategy_bp = Blueprint("strategy_bp", __name__, url_prefix="/strategy")

# -------------------------------------------------
# PUBLIC STRATEGIES
# -------------------------------------------------
@strategy_bp.route("/public", methods=["GET"])
def get_public_strategies():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    pagination = Strategy.query.filter(
        Strategy.status == 1,
        Strategy.published == 1
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "success": True,
        "data": [{
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "capital_required": s.capital_required,
            "status": int(s.status),
            "published": int(s.published),
            "owner_id": s.owner_id
        } for s in pagination.items]
    }), 200


# -------------------------------------------------
# PRIVATE STRATEGIES (SERIAL ID)
# -------------------------------------------------
@strategy_bp.route("/private", methods=["GET"])
@token_required
def get_private_strategies(current_user):
    strategies = Strategy.query.filter_by(
        owner_id=current_user.id
    ).order_by(Strategy.id.asc()).all()

    return jsonify({
        "success": True,
        "data": [{
            "id": index + 1,           # 👈 SERIAL NUMBER
            "real_id": s.id,           # internal
            "name": s.name,
            "description": s.description,
            "capital_required": s.capital_required,
            "status": int(s.status),
            "published": int(s.published),
            "published_at": s.published_at
        } for index, s in enumerate(strategies)]
    }), 200


# -------------------------------------------------
# UPDATE STRATEGY (SERIAL SAFE)
# -------------------------------------------------
@strategy_bp.route("/<int:strategy_id>", methods=["PUT"])
@token_required
def update_strategy(current_user, strategy_id):
    strategies = Strategy.query.filter_by(
        owner_id=current_user.id
    ).order_by(Strategy.id.asc()).all()

    index = strategy_id - 1
    if index < 0 or index >= len(strategies):
        return jsonify({"status": "error", "message": "Invalid strategy"}), 404

    strategy = strategies[index]

    data = request.get_json()
    strategy.name = data.get("name", strategy.name)
    strategy.description = data.get("description", strategy.description)
    strategy.capital_required = data.get("capital_required", strategy.capital_required)
    strategy.status = int(data.get("status", strategy.status))
    strategy.published = int(data.get("published", strategy.published))

    db.session.commit()
    socketio.emit("strategy_updated", {"id": strategy.id})

    return jsonify({
        "status": "success",
        "message": "Strategy updated successfully"
    }), 200

@strategy_bp.route("/<int:strategy_id>/toggle-status", methods=["PATCH"])
@token_required
def toggle_strategy_status(current_user, strategy_id):
    strategies = Strategy.query.filter_by(owner_id=current_user.id).order_by(Strategy.id.asc()).all()
    index = strategy_id - 1

    if index < 0 or index >= len(strategies):
        return jsonify({"status": "error", "message": "Invalid strategy"}), 404

    strategy = strategies[index]
    status = request.get_json().get("status")

    if status not in [0, 1]:
        return jsonify({"status": "error", "message": "status must be 0 or 1"}), 400

    strategy.status = status
    db.session.commit()
    socketio.emit("strategy_updated", {"id": strategy.id, "status": strategy.status})

    return jsonify({
        "status": "success",
        "message": "Strategy status updated",
        "data": {"id": strategy_id, "status": strategy.status}
    }), 200
@strategy_bp.route("/<int:strategy_id>/publish", methods=["PATCH"])
@token_required
def toggle_publish_strategy(current_user, strategy_id):
    strategies = Strategy.query.filter_by(owner_id=current_user.id).order_by(Strategy.id.asc()).all()
    index = strategy_id - 1

    if index < 0 or index >= len(strategies):
        return jsonify({"status": "error", "message": "Invalid strategy"}), 404

    strategy = strategies[index]
    published = request.get_json().get("published")

    if published not in [0, 1]:
        return jsonify({"status": "error", "message": "published must be 0 or 1"}), 400

    strategy.published = published
    strategy.published_at = datetime.utcnow() if published else None
    db.session.commit()

    # Convert datetime to ISO string before sending
    published_at_str = strategy.published_at.isoformat() if strategy.published_at else None

    socketio.emit("strategy_updated", {
        "id": strategy.id,
        "published": strategy.published,
        "published_at": published_at_str
    })

    return jsonify({
        "status": "success",
        "message": "Strategy published" if published else "Strategy unpublished",
        "data": {
            "id": strategy_id,
            "published": strategy.published,
            "published_at": published_at_str
        }
    }), 200



# -------------------------------------------------
# DELETE STRATEGY (SERIAL SAFE)
# -------------------------------------------------
@strategy_bp.route("/<int:strategy_id>", methods=["DELETE"])
@token_required
def delete_strategy(current_user, strategy_id):
    strategies = Strategy.query.filter_by(
        owner_id=current_user.id
    ).order_by(Strategy.id.asc()).all()

    index = strategy_id - 1
    if index < 0 or index >= len(strategies):
        return jsonify({"status": "error", "message": "Invalid strategy"}), 404

    strategy = strategies[index]

    Chat.query.filter_by(strategy_id=strategy.id).delete()
    db.session.delete(strategy)
    db.session.commit()

    socketio.emit("strategy_deleted", {"id": strategy.id})

    return jsonify({
        "status": "success",
        "message": "Strategy deleted successfully"
    }), 200


# -------------------------------------------------
# CREATE STRATEGY
# -------------------------------------------------
@strategy_bp.route("/create", methods=["POST"])
@token_required
def create_strategy(current_user):
    data = request.get_json()

    strategy = Strategy(
        name=data.get("name", ""),
        description=data.get("description", ""),
        capital_required=data.get("capital_required", 0),
        status=int(data.get("status", 0)),
        published=int(data.get("published", 0)),
        owner_id=current_user.id
    )

    db.session.add(strategy)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Strategy created successfully"
    }), 201






