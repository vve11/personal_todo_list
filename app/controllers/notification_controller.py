from flask import Blueprint, jsonify, request

from app.middleware.auth import handle_service_errors, login_required
from app.services import NotificationService

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")
notification_service = NotificationService()


@notification_bp.get("/due")
@login_required
@handle_service_errors
def list_due_notifications(user):
    return jsonify(notification_service.list_due(user))


@notification_bp.get("/inbox")
@login_required
@handle_service_errors
def inbox(user):
    return jsonify(notification_service.inbox(user))


@notification_bp.patch("/inbox/<int:log_id>/read")
@login_required
@handle_service_errors
def mark_read(user, log_id: int):
    return jsonify(notification_service.mark_read(user, log_id))


@notification_bp.post("/inbox/read-all")
@login_required
@handle_service_errors
def mark_all_read(user):
    return jsonify(notification_service.mark_all_read(user))
