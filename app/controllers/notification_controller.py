from flask import Blueprint, jsonify

from app.middleware.auth import handle_service_errors, login_required
from app.services import NotificationService

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")
notification_service = NotificationService()


@notification_bp.get("/due")
@login_required
@handle_service_errors
def list_due_notifications(user):
    return jsonify(notification_service.list_due(user))


@notification_bp.post("/send")
@login_required
@handle_service_errors
def send_notifications(user):
    return jsonify(notification_service.send_reminders(user))
