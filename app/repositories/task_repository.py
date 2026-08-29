from typing import Optional

from datetime import datetime

from sqlalchemy import func

from app.extensions import db
from app.models import Task


class TaskRepository:
    def list_by_user(self, user_id: int) -> list[Task]:
        return (
            Task.query.filter_by(user_id=user_id)
            .order_by(Task.sort_order, Task.id)
            .all()
        )

    def get_for_user(self, user_id: int, task_id: int) -> Optional[Task]:
        return Task.query.filter_by(id=task_id, user_id=user_id).first()

    def list_ids_for_user(self, user_id: int) -> set[int]:
        return {row.id for row in Task.query.filter_by(user_id=user_id).all()}

    def next_sort_order(self, user_id: int) -> int:
        max_order = (
            db.session.query(func.max(Task.sort_order))
            .filter(Task.user_id == user_id)
            .scalar()
        )
        return (max_order or -1) + 1

    def add(self, task: Task) -> Task:
        db.session.add(task)
        db.session.commit()
        return task

    def save(self, task: Task) -> Task:
        db.session.commit()
        return task

    def delete(self, task: Task) -> None:
        db.session.delete(task)
        db.session.commit()

    def renumber_for_user(self, user_id: int) -> None:
        tasks = (
            Task.query.filter_by(user_id=user_id)
            .order_by(Task.sort_order, Task.id)
            .all()
        )
        for index, task in enumerate(tasks):
            task.sort_order = index
        db.session.commit()

    def reorder_for_user(self, user_id: int, ordered_ids: list[int]) -> list[Task]:
        for index, task_id in enumerate(ordered_ids):
            Task.query.filter_by(id=task_id, user_id=user_id).update(
                {"sort_order": index, "updated_at": datetime.utcnow()}
            )
        db.session.commit()
        return self.list_by_user(user_id)

    def list_by_user_ordered_by_due(self, user_id: int) -> list[Task]:
        return (
            Task.query.filter_by(user_id=user_id)
            .order_by(Task.due_at, Task.id)
            .all()
        )
