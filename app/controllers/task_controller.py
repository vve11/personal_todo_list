from flask import Blueprint, jsonify, request

from app.middleware.auth import handle_service_errors, login_required
from app.services import TaskService

task_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")
task_service = TaskService()


@task_bp.get("")
@login_required
@handle_service_errors
def list_tasks(user):
    tasks = task_service.list_tasks(user)
    return jsonify([task.to_dict() for task in tasks])


@task_bp.post("")
@login_required
@handle_service_errors
def create_task(user):
    data = request.get_json(silent=True) or {}
    task = task_service.create_task(user, data)
    return jsonify(task.to_dict()), 201


@task_bp.patch("/<int:task_id>")
@login_required
@handle_service_errors
def update_task(user, task_id: int):
    data = request.get_json(silent=True) or {}
    task = task_service.update_task(user, task_id, data)
    return jsonify(task.to_dict())


@task_bp.put("/reorder")
@login_required
@handle_service_errors
def reorder_tasks(user):
    data = request.get_json(silent=True) or {}
    tasks = task_service.reorder_tasks(user, data.get("task_ids"))
    return jsonify([task.to_dict() for task in tasks])


@task_bp.delete("/<int:task_id>")
@login_required
@handle_service_errors
def delete_task(user, task_id: int):
    task_service.delete_task(user, task_id)
    return "", 204
