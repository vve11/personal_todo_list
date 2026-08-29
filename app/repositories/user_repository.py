from typing import Optional

from app.extensions import db
from app.models import User


class UserRepository:
    def get_by_id(self, user_id: int) -> Optional[User]:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return User.query.filter_by(email=email).first()

    def email_exists(self, email: str, exclude_user_id: Optional[int] = None) -> bool:
        query = User.query.filter_by(email=email)
        if exclude_user_id is not None:
            query = query.filter(User.id != exclude_user_id)
        return query.first() is not None

    def add(self, user: User) -> User:
        db.session.add(user)
        db.session.commit()
        return user

    def save(self, user: User) -> User:
        db.session.commit()
        return user
