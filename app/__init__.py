from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.controllers import auth_bp, notification_bp, static_bp, task_bp, user_bp
from app.database.schema import ensure_schema
from app.extensions import db


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": config_class.CORS_ORIGINS,
                "supports_credentials": True,
            }
        },
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(static_bp)

    with app.app_context():
        ensure_schema()

    return app
