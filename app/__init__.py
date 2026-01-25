


from flask import Flask, request
from flask_cors import CORS
from .extensions import db, socketio
from .routes.auth_routes import auth_bp
from .routes.strategy import strategy_bp
from .routes.chat_routes import chat_bp
import app.routes.websocket_handlers  # registers socket events
from .config import Config


def create_app():
   
    

    app = Flask(__name__, template_folder="templates")
    app.config.from_object(Config)
    # ---------------------------
    # CORS
    # ---------------------------
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # ---------------------------
    # Intercept OPTIONS requests
    # ---------------------------
    @app.before_request
    def block_options():
        if request.method == "OPTIONS":
            return "", 200

    # ---------------------------
    # Initialize extensions
    # ---------------------------
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins=["*"])

    # ---------------------------
    # Register Blueprints
    # ---------------------------
    app.register_blueprint(auth_bp)
    app.register_blueprint(strategy_bp, url_prefix="/strategy")
    app.register_blueprint(chat_bp, url_prefix="/chat")
 # ✅ now safe

    # ---------------------------
    # Create Tables
    # ---------------------------
    with app.app_context():
        db.create_all()
        print("✅ Tables created successfully")

    return app
