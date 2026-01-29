from flask import Blueprint, request, jsonify
from datetime import datetime
from app.extensions import db, socketio
from app.models import Strategy
from app.utils.auth import token_required
strategy_bp = Blueprint("strategy_bp", __name__, url_prefix="/strategy")
@strategy_bp.route("/public", methods=["GET"])
def get_public_strategies():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    pagination = Strategy.query.filter_by(
        status=1,
        published=1
    ).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "data": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "capital_required": s.capital_required,
                "status": int(s.status),
                "published": int(s.published),
                "owner_id": s.owner_id,
                "owner_name": s.owner.name if s.owner else None  # <-- added owner_name
            }
            for s in pagination.items
        ],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total_pages": pagination.pages,
            "total_items": pagination.total,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }
    }), 200
@strategy_bp.route("/private", methods=["GET"])
@token_required
def get_private_strategies(current_user):
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    # Fetch all strategies of the current user, regardless of published
    pagination = Strategy.query.filter_by(owner_id=current_user.id)\
                              .order_by(Strategy.id.desc())\
                              .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "success": True,
        "data": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "capital_required": s.capital_required,
                "status": int(s.status),
                "published": int(s.published),
                "published_at": s.published_at
            }
            for s in pagination.items
        ],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total_pages": pagination.pages,
            "total_items": pagination.total,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }
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
    if strategy.status == 1 and strategy.published == 1:
        socketio.emit("strategy_published", {
            "id": strategy.id,
            "name": strategy.name
        })

    return jsonify({
        "status": "success",
        "message": "Strategy created successfully",
        "data": {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "capital_required": strategy.capital_required,
            "status": strategy.status,
            "published": strategy.published,
            "owner_id": strategy.owner_id
        }
    }), 201
# -------------------------------------------------
# UPDATE STRATEGY
# -------------------------------------------------
@strategy_bp.route("/<int:strategy_id>", methods=["PUT"])
@token_required
def update_strategy(current_user, strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)

    if strategy.owner_id != current_user.id:
        return jsonify({
            "status": "error",
            "message": "Permission denied",
            "data": None
        }), 403

    data = request.get_json()
    strategy.name = data.get("name", strategy.name)
    strategy.description = data.get("description", strategy.description)
    strategy.capital_required = data.get(
        "capital_required", strategy.capital_required
    )
    strategy.status = int(data.get("status", strategy.status))
    strategy.published = int(data.get("published", strategy.published))

    db.session.commit()

    socketio.emit("strategy_updated", {"id": strategy.id})

    return jsonify({
        "status": "success",
        "message": "Strategy updated successfully",
        "data": {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "capital_required": strategy.capital_required,
            "status": strategy.status,
            "published": strategy.published,
            "owner_id": strategy.owner_id
        }
    }), 200


# -------------------------------------------------
# PUBLISH / UNPUBLISH STRATEGY
# -------------------------------------------------

# -------------------------------------------------
@strategy_bp.route("/<int:strategy_id>/toggle-status", methods=["PATCH"])
@token_required
def toggle_strategy_status(current_user, strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)

    if strategy.owner_id != current_user.id:
        return jsonify({
            "status": "error",
            "message": "You are not allowed to update this strategy",
            "data": None
        }), 403

    data = request.get_json()
    status = data.get("status")

    # Validate input
    if status not in [0, 1]:
        return jsonify({
            "status": "error",
            "message": "status must be 0 or 1",
            "data": None
        }), 400

    # Update only status
    strategy.status = status

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Strategy status updated successfully",
        "data": {
            "id": strategy.id,
            "status": strategy.status
        }
    }), 200

@strategy_bp.route("/<int:strategy_id>/publish", methods=["PATCH"])
@token_required
def toggle_publish_strategy(current_user, strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)

    if strategy.owner_id != current_user.id:
        return jsonify({
            "status": "error",
            "message": "You are not allowed to publish this strategy",
            "data": None
        }), 403

    data = request.get_json()
    published = data.get("published")

    if published not in [0, 1]:
        return jsonify({
            "status": "error",
            "message": "published must be 0 or 1",
            "data": None
        }), 400

    strategy.published = published
    strategy.published_at = datetime.utcnow() if published == 1 else None

    # ❌ REMOVE this line to keep private strategies private
    # if published == 1:
    #     strategy.status = 1

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Strategy published" if published == 1 else "Strategy unpublished",
        "data": {
            "id": strategy.id,
            "published": strategy.published,
            "published_at": strategy.published_at,
            "status": strategy.status
        }
    }), 200

# -------------------------------------------------
# DELETE STRATEGY
# -------------------------------------------------
@strategy_bp.route("/<int:strategy_id>", methods=["DELETE"])
@token_required
def delete_strategy(current_user, strategy_id):
    strategy = Strategy.query.get_or_404(strategy_id)

    if strategy.owner_id != current_user.id:
        return jsonify({
            "status": "error",
            "message": "Permission denied",
            "data": None
        }), 403

    db.session.delete(strategy)
    db.session.commit()

    socketio.emit("strategy_deleted", {"id": strategy_id})

    return jsonify({
        "status": "success",
        "message": "Strategy deleted successfully",
        "data": {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "capital_required": strategy.capital_required,
            "status": strategy.status,
            "published": strategy.published,
            "owner_id": strategy.owner_id
        }
    }), 200