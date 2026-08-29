from flask import Blueprint, jsonify, request

from app.middleware.auth import handle_service_errors, login_required
from app.services import UserService

user_bp = Blueprint("user", __name__, url_prefix="/api/user")
user_service = UserService()


@user_bp.get("")
@login_required
@handle_service_errors
def get_user(user):
    return jsonify(user.to_dict())


@user_bp.patch("")
@login_required
@handle_service_errors
def update_user(user):
    data = request.get_json(silent=True) or {}
    updated = user_service.update_profile(user, data)
    return jsonify(updated.to_dict())
