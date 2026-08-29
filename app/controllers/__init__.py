from app.controllers.auth_controller import auth_bp
from app.controllers.notification_controller import notification_bp
from app.controllers.static_controller import static_bp
from app.controllers.task_controller import task_bp
from app.controllers.user_controller import user_bp

__all__ = ["auth_bp", "user_bp", "task_bp", "notification_bp", "static_bp"]
