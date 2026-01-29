
from datetime import datetime
from app.extensions import db
# -----------------------------
# USER MODEL (minimal required)
# -----------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(200))
    is_verified = db.Column(db.Boolean, default=False)
class Strategy(db.Model):
    __tablename__ = "strategy"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    capital_required = db.Column(db.Float, default=0)

    # 0 = draft, 1 = active, 2 = archived (optional usage)
    status = db.Column(db.Integer, default=0)

    # 0 = unpublished, 1 = published
    published = db.Column(db.Integer, default=0)
    published_at = db.Column(db.DateTime, nullable=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    owner = db.relationship("User", backref="strategies")

# -----------------------------
# CHAT MODEL
# -----------------------------
class Chat(db.Model):
    __tablename__ = "chats"

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey("strategy.id", ondelete="CASCADE"),
        nullable=False
    )

    creator_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "strategy_id",
            "creator_id",
            "user_id",
            name="unique_chat"
        ),
    )

    # 🔥 Relationships
    strategy = db.relationship("Strategy", backref="chats")
    creator = db.relationship("User", foreign_keys=[creator_id])
    user = db.relationship("User", foreign_keys=[user_id])

    messages = db.relationship(
        "Message",
        backref="chat",
        cascade="all, delete-orphan",
        lazy=True
    )
class Message(db.Model):
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)

    chat_id = db.Column(
        db.Integer,
        db.ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    receiver_id = db.Column(  # 🔑 Make sure this exists
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 🔑 Relationships
    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])  