import os

from flask import Blueprint, jsonify, request

from app.jobs.worker import drain_reminders

job_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


def _cron_authorized() -> bool:
    if os.environ.get("VERCEL") != "1":
        return True
    secret = os.environ.get("CRON_SECRET", "").strip()
    header = request.headers.get("Authorization", "")
    return bool(secret) and header == f"Bearer {secret}"


@job_bp.get("/drain")
def drain_jobs():
    if not _cron_authorized():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(drain_reminders())
