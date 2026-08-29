from typing import Optional

from flask import session

from app.exceptions import UnauthorizedError, ValidationError
from app.models import User
from app.repositories import UserRepository
from app.utils.datetime_utils import normalize_email


class AuthService:
    def __init__(self, user_repo: Optional[UserRepository] = None):
        self.user_repo = user_repo or UserRepository()

    def register(self, name: str, email: str, password: str) -> User:
        name = (name or "").strip()
        email = normalize_email(email)
        password = password or ""

        if not name:
            raise ValidationError("name is required")
        if not email or "@" not in email:
            raise ValidationError("valid email is required")
        if len(password) < 6:
            raise ValidationError("password must be at least 6 characters")
        if self.user_repo.email_exists(email):
            from app.exceptions import ConflictError

            raise ConflictError("email is already registered")

        user = User(name=name[:120], email=email[:255], notifications_enabled=True)
        user.set_password(password)
        self.user_repo.add(user)
        self.login_user(user)
        return user

    def login(self, email: str, password: str) -> User:
        email = normalize_email(email)
        password = password or ""
        if not email or not password:
            raise ValidationError("email and password are required")

        user = self.user_repo.get_by_email(email)
        if user is None or not user.check_password(password):
            raise UnauthorizedError("invalid email or password")

        self.login_user(user)
        return user

    def logout(self) -> None:
        session.clear()

    def current_user(self) -> Optional[User]:
        user_id = session.get("user_id")
        if not user_id:
            return None
        return self.user_repo.get_by_id(user_id)

    def login_user(self, user: User) -> None:
        session.clear()
        session["user_id"] = user.id
        session.permanent = True

    def require_user(self) -> User:
        user = self.current_user()
        if user is None:
            raise UnauthorizedError()
        return user
