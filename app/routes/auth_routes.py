from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, redis_client
from app.models import User
from app.services.email_service import send_otp_email
from app.services.otp_service import (
    generate_and_store_otp,
    verify_otp,
    can_resend_otp,
    increment_attempt
)
import jwt
import datetime

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")

# -------------------------------------------------
# SEND OTP
# -------------------------------------------------
@auth_bp.route("/send_otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email is required"}), 400

    existing_user = User.query.filter(
        User.email == email,
        User.password.isnot(None)
    ).first()

    if existing_user:
        return jsonify({"message": "Email already registered"}), 400

    otp = generate_and_store_otp(email)
    send_otp_email(email, otp)

    return jsonify({"message": "OTP sent successfully"}), 200


# -------------------------------------------------
# VERIFY OTP
# -------------------------------------------------
@auth_bp.route("/verify_otp", methods=["POST"])
def verify_otp_route():
    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")

    if not email or not otp:
        return jsonify({"message": "Email and OTP are required"}), 400

    # Trim whitespace
    email = email.strip()
    otp = str(otp).strip()

    if verify_otp(email, otp):
        # Mark OTP as verified for 5 minutes
        redis_client.set(f"{email}_verified", "1", ex=300)
        return jsonify({"message": "OTP verified successfully"}), 200

    increment_attempt(email)
    return jsonify({"message": "Invalid OTP"}), 400


# -------------------------------------------------
# RESEND OTP
# -------------------------------------------------
@auth_bp.route("/resend_otp", methods=["POST"])
def resend_otp():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email is required"}), 400

    if not can_resend_otp(email):
        return jsonify({"message": "Please wait before requesting OTP again"}), 429

    otp = generate_and_store_otp(email)
    send_otp_email(email, otp)

    return jsonify({"message": "OTP resent successfully"}), 200

@auth_bp.route("/create_account", methods=["POST"])
def create_account():
    data = request.get_json()

    user = User(
        name=data["name"],
        email=data["email"],
        password=generate_password_hash(data["password"])
    )

    db.session.add(user)
    db.session.commit()

    token = jwt.encode(
        {
            "user_id": user.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256"
    )

    return jsonify({
        "status": "success",
        "data": {"token": token}
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    user = User.query.filter_by(email=data["email"]).first()
    if not user or not check_password_hash(user.password, data["password"]):
        return jsonify({"message": "Invalid credentials"}), 401

    token = jwt.encode(
        {
            "user_id": user.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256"
    )

    return jsonify({
        "status": "success",
        "data": {"token": token}
    }), 200
