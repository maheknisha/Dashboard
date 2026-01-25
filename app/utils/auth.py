
from functools import wraps
from flask import request, jsonify, current_app
import jwt
from app.models import User

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            token = request.args.get("token")

        if not token:
            return jsonify({
                "success": False,
                "status": "error",
                "message": "Token is missing. Please provide a valid token."
            }), 401

        try:
            payload = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=["HS256"]
            )

            current_user = User.query.get(payload.get("user_id"))
            if not current_user:
                return jsonify({
                    "success": False,
                    "status": "error",
                    "message": "User not found. Invalid token."
                }), 401

        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "status": "error",
                "message": "Token has expired. Please login again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "status": "error",
                "message": "Invalid token. Authentication failed."
            }), 401

        return f(current_user, *args, **kwargs)

    return decorated
