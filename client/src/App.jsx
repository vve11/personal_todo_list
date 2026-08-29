import { useState, useEffect, useCallback, useRef } from "react";
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

const fetchOpts = { credentials: "include" };

async function apiMe() {
  const r = await fetch("/api/auth/me", fetchOpts);
  if (!r.ok) throw new Error("Failed to check login");
  return r.json();
}

async function apiRegister({ name, email, password }) {
  const r = await fetch("/api/auth/register", {
    ...fetchOpts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Could not register");
  return d;
}

async function apiLogin({ email, password }) {
  const r = await fetch("/api/auth/login", {
    ...fetchOpts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Could not log in");
  return d;
}

async function apiLogout() {
  const r = await fetch("/api/auth/logout", { ...fetchOpts, method: "POST" });
  if (!r.ok) throw new Error("Could not log out");
  return r.json();
}

async function apiGetUser() {
  const r = await fetch("/api/user", fetchOpts);
  if (r.status === 401) throw new Error("Login required");
  if (!r.ok) throw new Error((await r.text()) || "Failed to load profile");
  return r.json();
}

async function apiUpdateUser(patch) {
  const r = await fetch("/api/user", {
    ...fetchOpts,
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || "Could not save profile");
  }
  return r.json();
}

async function apiList() {
  const r = await fetch("/api/tasks", fetchOpts);
  if (r.status === 401) throw new Error("Login required");
  if (!r.ok) throw new Error((await r.text()) || "Failed to load tasks");
  return r.json();
}

async function apiCreate(title, due_at = null) {
  const body = { title, completed: false };
  if (due_at) body.due_at = due_at;
  const r = await fetch("/api/tasks", {
    ...fetchOpts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.error || "Could not add task");
  }
  return r.json();
}

async function apiUpdate(id, patch) {
  const r = await fetch(`/api/tasks/${id}`, {
    ...fetchOpts,
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
  const r = await fetch(`/api/tasks/${id}`, { ...fetchOpts, method: "DELETE" });
  if (!r.ok) throw new Error("Delete failed");
}

async function apiReorder(taskIds) {
  const r = await fetch("/api/tasks/reorder", {
    ...fetchOpts,
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

async function apiGetDueNotifications() {
  const r = await fetch("/api/notifications/due", fetchOpts);
  if (!r.ok) throw new Error("Failed to load notifications");
  return r.json();
}

async function apiSendNotifications() {
  const r = await fetch("/api/notifications/send", { ...fetchOpts, method: "POST" });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Could not send notifications");
  return d;
}

function toDatetimeLocalValue(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function dueAtFromLocalInput(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function formatDueLabel(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function urgencyClass(urgency) {
  if (urgency === "overdue") return "due-overdue";
  if (urgency === "due_soon") return "due-soon";
  return "";
}

function AuthScreen({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user =
        mode === "register"
          ? await apiRegister({ name: name.trim(), email: email.trim(), password })
          : await apiLogin({ email: email.trim(), password });
      onAuthed(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app-wrap auth-wrap">
      <header>
        <h1>Personal Todo</h1>
        <p className="sub">
          {mode === "login"
            ? "Log in to see only your tasks."
            : "Create an account so your tasks stay linked to you."}
        </p>
      </header>
      <form className="auth-panel" onSubmit={onSubmit}>
        {mode === "register" && (
          <label className="profile-field">
            <span className="profile-label">Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={120}
              autoComplete="name"
              required
            />
          </label>
        )}
        <label className="profile-field">
          <span className="profile-label">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            maxLength={255}
            autoComplete="email"
            required
          />
        </label>
        <label className="profile-field">
          <span className="profile-label">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />
        </label>
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        <button className="btn-primary" type="submit" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
        </button>
        <p className="auth-switch">
          {mode === "login" ? (
            <>
              No account yet?{" "}
              <button type="button" className="link-btn" onClick={() => setMode("register")}>
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" className="link-btn" onClick={() => setMode("login")}>
                Log in
              </button>
            </>
          )}
        </p>
      </form>
    </div>
  );
}

function SortableTask({
  task,
  onToggle,
  onSaveTitle,
  onStartEdit,
  onDelete,
  onDueChange,
  urgency,
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
        {!task.completed && (
          <label className="task-due-field">
            <span className="sr-only">Deadline</span>
            <input
              type="datetime-local"
              className={`task-due-input ${urgencyClass(urgency)}`}
              value={toDatetimeLocalValue(task.due_at)}
              onChange={(e) => onDueChange(task, e.target.value)}
              title="Set deadline"
            />
            {task.due_at && (
              <span className={`task-due-label ${urgencyClass(urgency)}`}>
                {urgency === "overdue"
                  ? "Overdue"
                  : urgency === "due_soon"
                    ? "Due soon"
                    : "Due"}{" "}
                · {formatDueLabel(task.due_at)}
              </span>
            )}
          </label>
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
  const [user, setUser] = useState(null);
  const [authed, setAuthed] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newTitle, setNewTitle] = useState("");
  const [newDue, setNewDue] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileDraft, setProfileDraft] = useState({
    name: "",
    email: "",
    notifications_enabled: true,
  });
  const [savingProfile, setSavingProfile] = useState(false);
  const [dueAlerts, setDueAlerts] = useState([]);
  const [notifyBeforeHours, setNotifyBeforeHours] = useState(24);
  const [sendingNotify, setSendingNotify] = useState(false);
  const [notifyInfo, setNotifyInfo] = useState(null);
  const shownBrowserAlerts = useRef(new Set());

  const loadAppData = useCallback(async (profile) => {
    setUser(profile);
    setProfileDraft({
      name: profile.name,
      email: profile.email || "",
      notifications_enabled: profile.notifications_enabled !== false,
    });
    const data = await apiList();
    setTasks(data);
    if (profile.notifications_enabled !== false) {
      const dueData = await apiGetDueNotifications();
      setDueAlerts(dueData.items || []);
      setNotifyBeforeHours(dueData.notify_before_hours || 24);
      return dueData;
    }
    setDueAlerts([]);
    return { items: [] };
  }, []);

  const refresh = useCallback(async () => {
    setError(null);
    const data = await apiList();
    setTasks(data);
  }, []);

  const refreshDueAlerts = useCallback(async () => {
    const data = await apiGetDueNotifications();
    setDueAlerts(data.items || []);
    setNotifyBeforeHours(data.notify_before_hours || 24);
    return data;
  }, []);

  const showBrowserNotifications = useCallback((items) => {
    if (!items.length || typeof Notification === "undefined") return;
    if (Notification.permission !== "granted") return;
    for (const item of items) {
      const tag = `${item.task_id}-${item.urgency}`;
      if (shownBrowserAlerts.current.has(tag)) continue;
      shownBrowserAlerts.current.add(tag);
      new Notification(item.urgency === "overdue" ? "Task overdue" : "Task due soon", {
        body: item.message,
        tag: `todo-${item.task_id}`,
      });
    }
  }, []);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        setLoading(true);
        const me = await apiMe();
        if (!live) return;
        if (!me.user) {
          setAuthed(false);
          setUser(null);
          setTasks([]);
          return;
        }
        setAuthed(true);
        const dueData = await loadAppData(me.user);
        if (live) showBrowserNotifications(dueData.items || []);
      } catch (e) {
        if (live) {
          setAuthed(false);
          setError(e instanceof Error ? e.message : "Load error");
        }
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [loadAppData, showBrowserNotifications]);

  useEffect(() => {
    if (!authed || !user?.notifications_enabled) {
      if (!authed) setDueAlerts([]);
      return undefined;
    }
    let live = true;
    const tick = async () => {
      try {
        const data = await refreshDueAlerts();
        if (live) showBrowserNotifications(data.items || []);
      } catch {
        /* ignore polling errors */
      }
    };
    const id = window.setInterval(tick, 60_000);
    return () => {
      live = false;
      window.clearInterval(id);
    };
  }, [authed, user?.notifications_enabled, refreshDueAlerts, showBrowserNotifications]);

  const onAuthed = async (profile) => {
    setLoading(true);
    setError(null);
    try {
      setAuthed(true);
      shownBrowserAlerts.current = new Set();
      const dueData = await loadAppData(profile);
      showBrowserNotifications(dueData.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your tasks");
    } finally {
      setLoading(false);
    }
  };

  const onLogout = async () => {
    setError(null);
    try {
      await apiLogout();
      setAuthed(false);
      setUser(null);
      setTasks([]);
      setDueAlerts([]);
      setEditingProfile(false);
      shownBrowserAlerts.current = new Set();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log out");
    }
  };

  const requestNotificationPermission = async () => {
    if (typeof Notification === "undefined") {
      setError("Browser notifications are not supported here");
      return;
    }
    if (Notification.permission === "granted") return;
    const result = await Notification.requestPermission();
    if (result !== "granted") {
      setError("Browser notification permission was denied");
    }
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const onStartProfileEdit = () => {
    if (!user) return;
    setProfileDraft({
      name: user.name,
      email: user.email || "",
      notifications_enabled: user.notifications_enabled !== false,
    });
    setEditingProfile(true);
  };

  const onCancelProfileEdit = () => {
    if (user) {
      setProfileDraft({
        name: user.name,
        email: user.email || "",
        notifications_enabled: user.notifications_enabled !== false,
      });
    }
    setEditingProfile(false);
  };

  const onSaveProfile = async (e) => {
    e.preventDefault();
    const name = profileDraft.name.trim();
    const email = profileDraft.email.trim();
    if (!name) {
      setError("Name cannot be empty");
      return;
    }
    if (!email || !email.includes("@")) {
      setError("A valid email is required");
      return;
    }
    setSavingProfile(true);
    setError(null);
    try {
      const updated = await apiUpdateUser({
        name,
        email,
        notifications_enabled: profileDraft.notifications_enabled,
      });
      setUser(updated);
      setProfileDraft({
        name: updated.name,
        email: updated.email || "",
        notifications_enabled: updated.notifications_enabled !== false,
      });
      setEditingProfile(false);
      if (updated.notifications_enabled !== false) {
        await requestNotificationPermission();
        await refreshDueAlerts();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile");
    } finally {
      setSavingProfile(false);
    }
  };

  const onAdd = async (e) => {
    e.preventDefault();
    const t = newTitle.trim();
    if (!t) return;
    setSaving(true);
    setError(null);
    try {
      await apiCreate(t, dueAtFromLocalInput(newDue));
      setNewTitle("");
      setNewDue("");
      await refresh();
      if (user?.notifications_enabled) await refreshDueAlerts();
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

  const onDueChange = async (task, localValue) => {
    setError(null);
    const due_at = dueAtFromLocalInput(localValue);
    setTasks((prev) =>
      prev.map((r) => (r.id === task.id ? { ...r, due_at } : r))
    );
    try {
      await apiUpdate(task.id, { due_at });
      if (user?.notifications_enabled) await refreshDueAlerts();
    } catch {
      setError("Failed to update deadline");
      await refresh();
    }
  };

  const onSendNotifications = async () => {
    setSendingNotify(true);
    setError(null);
    setNotifyInfo(null);
    try {
      await requestNotificationPermission();
      const result = await apiSendNotifications();
      setNotifyInfo(result.message);
      showBrowserNotifications(result.sent || []);
      await refreshDueAlerts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reminders");
    } finally {
      setSendingNotify(false);
    }
  };

  const urgencyForTask = (taskId) =>
    dueAlerts.find((item) => item.task_id === taskId)?.urgency || null;

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

  if (!authed || !user) {
    return <AuthScreen onAuthed={onAuthed} />;
  }

  return (
    <div className="app-wrap">
      <header>
        <h1>{`${user.name}'s tasks`}</h1>
        <p className="sub">
          Set deadlines, get reminders for tasks due within {notifyBeforeHours} hours, and drag to reorder.
        </p>
      </header>
      <section className="profile-panel" aria-label="User profile">
          {editingProfile ? (
            <form className="profile-form" onSubmit={onSaveProfile}>
              <label className="profile-field">
                <span className="profile-label">Name</span>
                <input
                  type="text"
                  value={profileDraft.name}
                  onChange={(e) =>
                    setProfileDraft((p) => ({ ...p, name: e.target.value }))
                  }
                  maxLength={120}
                  autoComplete="name"
                  required
                />
              </label>
              <label className="profile-field">
                <span className="profile-label">Email</span>
                <input
                  type="email"
                  value={profileDraft.email}
                  onChange={(e) =>
                    setProfileDraft((p) => ({ ...p, email: e.target.value }))
                  }
                  maxLength={255}
                  autoComplete="email"
                  required
                />
              </label>
              <label className="profile-field profile-check">
                <input
                  type="checkbox"
                  checked={profileDraft.notifications_enabled}
                  onChange={(e) =>
                    setProfileDraft((p) => ({
                      ...p,
                      notifications_enabled: e.target.checked,
                    }))
                  }
                />
                <span>Enable deadline notifications (browser + email)</span>
              </label>
              <p className="profile-hint">
                Reminder emails use your account email. SMTP must be configured on the server.
              </p>
              <div className="profile-actions">
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={onCancelProfileEdit}
                  disabled={savingProfile}
                >
                  Cancel
                </button>
                <button className="btn-primary" type="submit" disabled={savingProfile}>
                  {savingProfile ? "Saving…" : "Save profile"}
                </button>
              </div>
            </form>
          ) : (
            <div className="profile-view">
              <div className="profile-meta">
                <span className="profile-name">{user.name}</span>
                <span className="profile-email">{user.email}</span>
                <span className="profile-email muted">User ID: {user.id}</span>
                <span className="profile-email">
                  Notifications:{" "}
                  {user.notifications_enabled !== false ? "On" : "Off"}
                </span>
              </div>
              <div className="profile-actions">
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={onStartProfileEdit}
                >
                  Edit profile
                </button>
                <button type="button" className="btn-ghost" onClick={onLogout}>
                  Log out
                </button>
              </div>
            </div>
          )}
        </section>
      {notifyInfo && (
        <div className="info-banner" role="status">
          {notifyInfo}
        </div>
      )}
      {user?.notifications_enabled !== false && dueAlerts.length > 0 && (
        <section className="notify-panel" aria-label="Deadline reminders">
          <div className="notify-panel-head">
            <h2>Deadline reminders</h2>
            <button
              type="button"
              className="btn-ghost"
              onClick={onSendNotifications}
              disabled={sendingNotify}
            >
              {sendingNotify ? "Sending…" : "Send reminders"}
            </button>
          </div>
          <ul className="notify-list">
            {dueAlerts.map((item) => (
              <li key={item.task_id} className={urgencyClass(item.urgency)}>
                {item.message}
              </li>
            ))}
          </ul>
        </section>
      )}
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <form className="add-form" onSubmit={onAdd}>
        <div className="add-row">
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
        </div>
        <label className="add-due">
          <span className="profile-label">Deadline (optional)</span>
          <input
            type="datetime-local"
            value={newDue}
            onChange={(e) => setNewDue(e.target.value)}
          />
        </label>
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
                  urgency={urgencyForTask(task.id)}
                  onToggle={onToggle}
                  onSaveTitle={onSaveTitle}
                  onStartEdit={onStartEdit}
                  onDelete={onDelete}
                  onDueChange={onDueChange}
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
