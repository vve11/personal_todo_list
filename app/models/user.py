from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin, utc_iso


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="You")
    email = db.Column(db.String(255), nullable=False, unique=True, default="")
    password_hash = db.Column(db.String(255), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True, nullable=False)

    tasks = db.relationship(
        "Task", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        # pbkdf2: Apple CLT Python builds often lack hashlib.scrypt
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "notifications_enabled": self.notifications_enabled,
            "created_at": utc_iso(self.created_at),
            "updated_at": utc_iso(self.updated_at),
        }
