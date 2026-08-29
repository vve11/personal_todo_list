from functools import wraps

from flask import jsonify

from app.exceptions import ServiceError
from app.services import AuthService


auth_service = AuthService()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            user = auth_service.require_user()
        except ServiceError as exc:
            return jsonify({"error": exc.message}), exc.status_code
        return view(user, *args, **kwargs)

    return wrapper


def handle_service_errors(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ServiceError as exc:
            return jsonify({"error": exc.message}), exc.status_code

    return wrapper
