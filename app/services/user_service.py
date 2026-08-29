from typing import Optional

from datetime import datetime

from app.exceptions import ConflictError, ValidationError
from app.models import User
from app.repositories import UserRepository
from app.utils.datetime_utils import normalize_email


class UserService:
    def __init__(self, user_repo: Optional[UserRepository] = None):
        self.user_repo = user_repo or UserRepository()

    def update_profile(self, user: User, data: dict) -> User:
        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                raise ValidationError("name must not be empty")
            user.name = name[:120]

        if "email" in data:
            email = normalize_email(data.get("email"))
            if not email or "@" not in email:
                raise ValidationError("email is invalid")
            if self.user_repo.email_exists(email, exclude_user_id=user.id):
                raise ConflictError("email is already registered")
            user.email = email[:255]

        if "notifications_enabled" in data:
            user.notifications_enabled = bool(data["notifications_enabled"])

        if data.get("password"):
            password = data.get("password") or ""
            if len(password) < 6:
                raise ValidationError("password must be at least 6 characters")
            user.set_password(password)

        user.updated_at = datetime.utcnow()
        return self.user_repo.save(user)
