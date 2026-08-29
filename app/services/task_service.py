from typing import Optional

from datetime import datetime

from app.exceptions import NotFoundError, ValidationError
from app.models import Task, User
from app.repositories import TaskRepository
from app.utils.datetime_utils import parse_due_at


class TaskService:
    def __init__(self, task_repo: Optional[TaskRepository] = None):
        self.task_repo = task_repo or TaskRepository()

    def list_tasks(self, user: User) -> list[Task]:
        return self.task_repo.list_by_user(user.id)

    def create_task(self, user: User, data: dict) -> Task:
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationError("title is required")

        due_at, due_err = parse_due_at(data.get("due_at"))
        if due_err:
            raise ValidationError(due_err)

        task = Task(
            user_id=user.id,
            title=title[:500],
            completed=bool(data.get("completed", False)),
            sort_order=self.task_repo.next_sort_order(user.id),
            due_at=due_at,
        )
        return self.task_repo.add(task)

    def update_task(self, user: User, task_id: int, data: dict) -> Task:
        task = self._get_task_or_raise(user, task_id)

        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                raise ValidationError("title must not be empty")
            task.title = title[:500]

        if "completed" in data:
            task.completed = bool(data["completed"])

        if "due_at" in data:
            due_at, due_err = parse_due_at(data.get("due_at"))
            if due_err:
                raise ValidationError(due_err)
            task.due_at = due_at
            task.last_notified_at = None

        if "sort_order" in data:
            sort_order = data["sort_order"]
            if isinstance(sort_order, int) and sort_order >= 0:
                task.sort_order = sort_order

        task.updated_at = datetime.utcnow()
        return self.task_repo.save(task)

    def reorder_tasks(self, user: User, ordered_ids: list) -> list[Task]:
        if not isinstance(ordered_ids, list) or not ordered_ids:
            raise ValidationError("task_ids must be a non-empty array of task ids")
        if not all(isinstance(task_id, int) for task_id in ordered_ids):
            raise ValidationError("task_ids must be integers")

        all_ids = self.task_repo.list_ids_for_user(user.id)
        if set(ordered_ids) != all_ids or len(ordered_ids) != len(all_ids):
            raise ValidationError(
                "task_ids must list every task id exactly once in the desired order"
            )

        return self.task_repo.reorder_for_user(user.id, ordered_ids)

    def delete_task(self, user: User, task_id: int) -> None:
        task = self._get_task_or_raise(user, task_id)
        self.task_repo.delete(task)
        self.task_repo.renumber_for_user(user.id)

    def _get_task_or_raise(self, user: User, task_id: int) -> Task:
        task = self.task_repo.get_for_user(user.id, task_id)
        if task is None:
            raise NotFoundError("Task not found")
        return task
