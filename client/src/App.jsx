import { useState, useEffect, useCallback } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

async function apiList() {
  const r = await fetch("/api/tasks");
  if (!r.ok) throw new Error(await r.text() || "Failed to load tasks");
  return r.json();
}

async function apiCreate(title) {
  const r = await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, completed: false }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || "Could not add task");
  }
  return r.json();
}

async function apiUpdate(id, patch) {
  const r = await fetch(`/api/tasks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || "Update failed");
  }
  return r.json();
}

async function apiDelete(id) {
  const r = await fetch(`/api/tasks/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Delete failed");
}

async function apiReorder(taskIds) {
  const r = await fetch("/api/tasks/reorder", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_ids: taskIds }),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || "Reorder failed");
  }
  return r.json();
}

function SortableTask({
  task,
  onToggle,
  onSaveTitle,
  onStartEdit,
  onDelete,
  editing,
  setEditingId,
  draft,
  setDraft,
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const isEd = editing === task.id;
  return (
    <li
      ref={setNodeRef}
      style={style}
      className={`task-row${isDragging ? " is-dragging" : ""}`}
    >
      <button
        type="button"
        className="handle"
        ref={setActivatorNodeRef}
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        title="Drag to reorder"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
          <path d="M8 5h2v2H8V5zm6 0h2v2h-2V5zM8 10h2v2H8v-2zm6 0h2v2h-2v-2zM8 15h2v2H8v-2zm6 0h2v2h-2v-2z" />
        </svg>
      </button>
      <label className="check">
        <span className="sr-only">Completed</span>
        <input
          type="checkbox"
          checked={task.completed}
          onChange={() => onToggle(task)}
        />
      </label>
      <div className="task-title-wrap">
        {isEd ? (
          <input
            className="task-title-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
            onBlur={() => onSaveTitle(task)}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") {
                setEditingId(null);
                setDraft(task.title);
              }
            }}
          />
        ) : (
          <span
            role="button"
            tabIndex={0}
            className={
              "task-title" + (task.completed ? " compact" : "")
            }
            onClick={() => onStartEdit(task)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onStartEdit(task);
            }}
          >
            {task.title}
          </span>
        )}
      </div>
      <div className="row-actions">
        <button
          type="button"
          className="icon-btn"
          onClick={() => (isEd ? onSaveTitle(task) : onStartEdit(task))}
          title={isEd ? "Save title" : "Edit title"}
        >
          <span className="sr-only">{isEd ? "Save title" : "Edit title"}</span>
          {isEd ? "✓" : "✎"}
        </button>
        <button
          type="button"
          className="icon-btn danger"
          onClick={() => onDelete(task.id)}
          title="Delete task"
        >
          <span className="sr-only">Delete task</span>
          ✕
        </button>
      </div>
    </li>
  );
}

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newTitle, setNewTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");

  const refresh = useCallback(async () => {
    setError(null);
    const data = await apiList();
    setTasks(data);
  }, []);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        setLoading(true);
        await refresh();
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : "Load error");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [refresh]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const onAdd = async (e) => {
    e.preventDefault();
    const t = newTitle.trim();
    if (!t) return;
    setSaving(true);
    setError(null);
    try {
      await apiCreate(t);
      setNewTitle("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add");
    } finally {
      setSaving(false);
    }
  };

  const onToggle = async (task) => {
    setError(null);
    const next = !task.completed;
    setTasks((prev) =>
      prev.map((r) => (r.id === task.id ? { ...r, completed: next } : r))
    );
    try {
      await apiUpdate(task.id, { completed: next });
    } catch {
      setError("Failed to update task");
      await refresh();
    }
  };

  const onStartEdit = (task) => {
    setEditingId(task.id);
    setDraft(task.title);
  };

  const onSaveTitle = async (task) => {
    const t = draft.trim();
    if (!t) {
      setError("Title cannot be empty");
      return;
    }
    setError(null);
    if (t === task.title) {
      setEditingId(null);
      return;
    }
    setTasks((prev) => prev.map((r) => (r.id === task.id ? { ...r, title: t } : r)));
    setEditingId(null);
    try {
      await apiUpdate(task.id, { title: t });
    } catch {
      setError("Failed to save title");
      await refresh();
    }
  };

  const onDelete = async (id) => {
    setError(null);
    setEditingId((e) => (e === id ? null : e));
    try {
      await apiDelete(id);
      setTasks((prev) => prev.filter((x) => x.id !== id));
    } catch {
      setError("Delete failed");
      await refresh();
    }
  };

  const onDragEnd = async (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setError(null);
    const oldIndex = tasks.findIndex((t) => t.id === active.id);
    const newIndex = tasks.findIndex((t) => t.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(tasks, oldIndex, newIndex);
    const ids = reordered.map((x) => x.id);
    setTasks(reordered);
    try {
      const updated = await apiReorder(ids);
      setTasks(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reorder failed");
      await refresh();
    }
  };

  if (loading) {
    return (
      <div className="app-wrap">
        <p className="muted" style={{ marginTop: "3rem" }}>
          Loading…
        </p>
      </div>
    );
  }

  return (
    <div className="app-wrap">
      <header>
        <h1>Your tasks</h1>
        <p className="sub">Add items, mark done, edit text, and drag to put them in order.</p>
      </header>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <form className="add-row" onSubmit={onAdd}>
        <input
          type="text"
          placeholder="New task…"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          maxLength={500}
          autoComplete="off"
        />
        <button className="btn-primary" type="submit" disabled={!newTitle.trim() || saving}>
          Add
        </button>
      </form>
      {tasks.length === 0 ? (
        <div className="list">
          <p className="list-empty">No tasks yet. Add one above.</p>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={onDragEnd}
        >
          <SortableContext
            items={tasks.map((t) => t.id)}
            strategy={verticalListSortingStrategy}
          >
            <ul
              className="list"
              style={{ listStyle: "none", margin: 0, padding: 0 }}
            >
              {tasks.map((task) => (
                <SortableTask
                  key={task.id}
                  task={task}
                  onToggle={onToggle}
                  onSaveTitle={onSaveTitle}
                  onStartEdit={onStartEdit}
                  onDelete={onDelete}
                  editing={editingId}
                  setEditingId={setEditingId}
                  draft={editingId === task.id ? draft : task.title}
                  setDraft={setDraft}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
      )}
      <p className="muted">Use the grip to drag tasks into a new order.</p>
    </div>
  );
}
