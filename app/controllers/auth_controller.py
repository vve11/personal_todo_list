from flask import Blueprint, jsonify, request

from app.middleware.auth import handle_service_errors, login_required
from app.services import AuthService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
auth_service = AuthService()


@auth_bp.post("/register")
@handle_service_errors
def register():
    data = request.get_json(silent=True) or {}
    user = auth_service.register(
        name=data.get("name"),
        email=data.get("email"),
        password=data.get("password"),
    )
    return jsonify(user.to_dict()), 201


@auth_bp.post("/login")
@handle_service_errors
def login():
    data = request.get_json(silent=True) or {}
    user = auth_service.login(
        email=data.get("email"),
        password=data.get("password"),
    )
    return jsonify(user.to_dict())


@auth_bp.post("/logout")
def logout():
    auth_service.logout()
    return jsonify({"ok": True})


@auth_bp.get("/me")
def auth_me():
    user = auth_service.current_user()
    if user is None:
        return jsonify({"user": None})
    return jsonify({"user": user.to_dict()})
