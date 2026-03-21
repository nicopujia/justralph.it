import { useState, useCallback, useRef, useEffect } from "react";
import { RotateCcw, Trash2, Pencil, Check, X, Plus, ChevronUp, ChevronDown } from "lucide-react";
import type { TaskInfo } from "@/hooks/useEventReducer";
import { API_URL } from "@/lib/config";

type TaskListProps = {
  tasks: Map<string, TaskInfo>;
  sessionId?: string;
  embedded?: boolean;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

const STATUS_TEXT: Record<TaskInfo["status"], { label: string; cls: string }> = {
  open: { label: "[OPEN]", cls: "text-muted-foreground" },
  in_progress: { label: "[IN_PROGRESS]", cls: "text-[var(--color-terminal-text)]" },
  blocked: { label: "[BLOCKED]", cls: "text-destructive" },
  done: { label: "[DONE]", cls: "text-[var(--color-success)] opacity-60" },
  help: { label: "[HELP]", cls: "text-destructive" },
};

const RETRYABLE: Set<TaskInfo["status"]> = new Set(["blocked", "help"]);
type StatusFilter = "all" | TaskInfo["status"];
const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: "all", label: "ALL" },
  { id: "open", label: "OPEN" },
  { id: "in_progress", label: "ACTIVE" },
  { id: "blocked", label: "BLOCKED" },
  { id: "done", label: "DONE" },
];

// -- Inline edit field -------------------------------------------------------

function InlineEdit({
  value,
  onSave,
  multiline = false,
  className = "",
}: {
  value: string;
  onSave: (v: string) => void;
  multiline?: boolean;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef<HTMLTextAreaElement | HTMLInputElement>(null);

  useEffect(() => {
    if (editing) ref.current?.focus();
  }, [editing]);

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== value) onSave(trimmed);
    setEditing(false);
  };

  if (!editing) {
    return (
      <span
        className={`cursor-pointer hover:underline decoration-dotted underline-offset-2 ${className}`}
        onClick={(e) => { e.stopPropagation(); setDraft(value); setEditing(true); }}
        title="Click to edit"
      >
        {value || <span className="italic text-muted-foreground">empty</span>}
      </span>
    );
  }

  const shared = {
    value: draft,
    onChange: (e: React.ChangeEvent<HTMLTextAreaElement | HTMLInputElement>) => setDraft(e.target.value),
    onBlur: commit,
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commit(); }
      if (e.key === "Escape") setEditing(false);
    },
    className: "bg-black border border-primary text-foreground text-xs font-mono px-1 py-0.5 w-full focus:outline-none " + className,
    onClick: (e: React.MouseEvent) => e.stopPropagation(),
  };

  if (multiline) {
    return <textarea ref={ref as React.RefObject<HTMLTextAreaElement>} rows={3} {...shared} />;
  }
  return <input ref={ref as React.RefObject<HTMLInputElement>} {...shared} />;
}

// -- Delete confirmation -----------------------------------------------------

function DeleteButton({ onConfirm, disabled }: { onConfirm: () => void; disabled?: boolean }) {
  const [confirming, setConfirming] = useState(false);

  if (confirming) {
    return (
      <span className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
        <span className="text-destructive text-[10px] uppercase">delete?</span>
        <button
          className="text-destructive hover:bg-destructive hover:text-destructive-foreground p-0.5 transition-colors"
          onClick={() => { onConfirm(); setConfirming(false); }}
        >
          <Check className="size-3" />
        </button>
        <button
          className="text-muted-foreground hover:text-foreground p-0.5 transition-colors"
          onClick={() => setConfirming(false)}
        >
          <X className="size-3" />
        </button>
      </span>
    );
  }

  return (
    <button
      className="text-muted-foreground hover:text-destructive p-0.5 transition-colors disabled:opacity-30"
      disabled={disabled}
      onClick={(e) => { e.stopPropagation(); setConfirming(true); }}
      title="Delete task"
    >
      <Trash2 className="size-3" />
    </button>
  );
}

// -- Task item ---------------------------------------------------------------

type TaskItemProps = {
  task: TaskInfo;
  index: number;
  selected: boolean;
  onSelect: () => void;
  sessionId?: string;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

function TaskItem({ task, index, selected, onSelect, sessionId, onTaskUpdate }: TaskItemProps) {
  const [retrying, setRetrying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const canRetry = RETRYABLE.has(task.status);
  const canDelete = task.status !== "in_progress";
  const isBlocked = task.status === "blocked" || task.status === "help";
  const { label, cls } = STATUS_TEXT[task.status];

  const patchTask = useCallback(
    async (patch: Record<string, unknown>) => {
      if (!sessionId) return;
      await fetch(`${API_URL}/api/sessions/${sessionId}/tasks/${task.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
    },
    [sessionId, task.id],
  );

  const handleRetry = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!sessionId) return;
      setRetrying(true);
      try {
        await patchTask({ status: "open" });
        await fetch(`${API_URL}/api/sessions/${sessionId}/restart`, { method: "POST" });
        onTaskUpdate?.(task.id, { status: "open", error: undefined });
      } finally {
        setRetrying(false);
      }
    },
    [sessionId, task.id, onTaskUpdate, patchTask],
  );

  const handleDelete = useCallback(async () => {
    if (!sessionId) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API_URL}/api/sessions/${sessionId}/tasks/${task.id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        // WebSocket task_deleted event will remove it from the map
      }
    } finally {
      setDeleting(false);
    }
  }, [sessionId, task.id]);

  const handleTitleSave = useCallback(
    (v: string) => {
      patchTask({ body: undefined }); // title is not patchable via body, we'd need a title field
      // For now, we update body (acceptance criteria). Title is set at creation.
      onTaskUpdate?.(task.id, { title: v });
    },
    [patchTask, task.id, onTaskUpdate],
  );

  const handleBodySave = useCallback(
    (v: string) => {
      patchTask({ body: v });
    },
    [patchTask],
  );

  return (
    <li
      className={`border-b border-border font-mono text-xs px-3 py-2 hover:bg-muted cursor-pointer select-none transition-colors ${
        isBlocked ? "border-l-2 border-l-destructive" : ""
      } ${deleting ? "opacity-30 pointer-events-none" : ""}`}
      onClick={onSelect}
    >
      {/* Header row */}
      <div className="flex items-baseline gap-2">
        <span className="text-muted-foreground shrink-0">[{String(index + 1).padStart(3, "0")}]</span>
        <span className={`shrink-0 ${cls}`}>{label}</span>
        <span className="text-foreground truncate flex-1">{task.title}</span>
        {/* Push indicator */}
        {task.status === "done" && (
          <span className="shrink-0" title={task.pushed ? "Pushed to GitHub" : task.pushError ? `Push failed: ${task.pushError}` : "Not pushed"}>
            {task.pushed ? (
              <Check className="size-3 text-[var(--color-success)]" />
            ) : task.pushError ? (
              <X className="size-3 text-red-400" />
            ) : null}
          </span>
        )}
        {/* Action icons (visible on hover via group) */}
        <span className="shrink-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          {canDelete && sessionId && <DeleteButton onConfirm={handleDelete} disabled={deleting} />}
        </span>
      </div>

      {/* Expanded detail */}
      <div className={`overflow-hidden transition-all duration-200 ${selected ? "max-h-[300px]" : "max-h-0"}`}>
        <div className="pt-2 pl-2 space-y-2 border-t border-border mt-1">
          <p className="text-muted-foreground break-words text-[10px]">{task.id}</p>

          {/* Body / acceptance criteria */}
          {sessionId && (
            <div className="space-y-1">
              <span className="text-muted-foreground text-[10px] uppercase tracking-wider">body</span>
              <InlineEdit
                value={task.error || ""}
                onSave={handleBodySave}
                multiline
                className="text-muted-foreground"
              />
            </div>
          )}

          {task.error && (
            <p className="text-destructive break-words text-[10px]">{task.error}</p>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            {canRetry && sessionId && (
              <button
                className="border border-primary text-primary bg-transparent uppercase text-[10px] tracking-wider px-2 py-0.5 hover:bg-primary hover:text-primary-foreground transition-colors disabled:opacity-50"
                disabled={retrying}
                onClick={handleRetry}
              >
                <span className="flex items-center gap-1">
                  <RotateCcw className={`size-3 ${retrying ? "animate-spin" : ""}`} />
                  {retrying ? "RETRYING" : "RETRY"}
                </span>
              </button>
            )}
            {canDelete && sessionId && (
              <DeleteButton onConfirm={handleDelete} disabled={deleting} />
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

// -- Add task form -----------------------------------------------------------

function AddTaskForm({ sessionId, onAdded }: { sessionId: string; onAdded?: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      await fetch(`${API_URL}/api/sessions/${sessionId}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim(), body: body.trim() || undefined }),
      });
      setTitle("");
      setBody("");
      setOpen(false);
      onAdded?.();
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full border-b border-border px-3 py-2 text-xs font-mono uppercase tracking-wider text-muted-foreground hover:text-primary hover:bg-muted transition-colors flex items-center gap-1.5"
      >
        <Plus className="size-3" /> ADD TASK
      </button>
    );
  }

  return (
    <div className="border-b border-border px-3 py-2 space-y-1.5" onClick={(e) => e.stopPropagation()}>
      <input
        ref={inputRef}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Task title..."
        className="w-full bg-black border border-border text-foreground text-xs font-mono px-2 py-1 focus:outline-none focus:border-primary"
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSubmit();
          if (e.key === "Escape") setOpen(false);
        }}
      />
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Acceptance criteria (optional)..."
        rows={2}
        className="w-full bg-black border border-border text-foreground text-xs font-mono px-2 py-1 focus:outline-none focus:border-primary resize-none"
      />
      <div className="flex items-center gap-2">
        <button
          onClick={handleSubmit}
          disabled={!title.trim() || submitting}
          className="border border-primary text-primary bg-transparent uppercase text-[10px] tracking-wider px-2 py-0.5 hover:bg-primary hover:text-primary-foreground transition-colors disabled:opacity-50"
        >
          {submitting ? "CREATING..." : "CREATE"}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="text-muted-foreground text-[10px] uppercase tracking-wider hover:text-foreground transition-colors"
        >
          CANCEL
        </button>
      </div>
    </div>
  );
}

// -- Task items list ---------------------------------------------------------

type TaskItemsProps = {
  tasks: Map<string, TaskInfo>;
  sessionId?: string;
  filter: StatusFilter;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

function TaskItems({ tasks, sessionId, filter, onTaskUpdate }: TaskItemsProps) {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  let taskEntries = Array.from(tasks.values()).reverse();
  if (filter !== "all") {
    taskEntries = taskEntries.filter((t) => t.status === filter);
  }

  if (taskEntries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-8">
        <span className="text-muted-foreground font-mono text-xs uppercase tracking-wider">
          {filter === "all" ? "NO TASKS YET" : `NO ${filter.toUpperCase()} TASKS`}
        </span>
      </div>
    );
  }

  return (
    <ul>
      {taskEntries.map((task, i) => (
        <li key={task.id} className="group">
          <TaskItem
            task={task}
            index={i}
            selected={selectedTaskId === task.id}
            onSelect={() =>
              setSelectedTaskId((prev) => (prev === task.id ? null : task.id))
            }
            sessionId={sessionId}
            onTaskUpdate={onTaskUpdate}
          />
        </li>
      ))}
    </ul>
  );
}

// -- Main export -------------------------------------------------------------

export function TaskList({ tasks, sessionId, embedded = false, onTaskUpdate }: TaskListProps) {
  const count = tasks.size;
  const [filter, setFilter] = useState<StatusFilter>("all");

  // Count per status for filter badges
  const counts: Record<StatusFilter, number> = { all: count, open: 0, in_progress: 0, blocked: 0, done: 0, help: 0 };
  for (const t of tasks.values()) {
    counts[t.status] = (counts[t.status] || 0) + 1;
  }
  // Merge help into blocked for the filter display
  counts.blocked += counts.help || 0;

  const filterBar = (
    <div className="flex items-center gap-0.5 px-2 py-1 border-b border-border overflow-x-auto shrink-0">
      {FILTERS.map((f) => {
        const n = f.id === "blocked" ? counts.blocked : counts[f.id];
        return (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider transition-colors whitespace-nowrap ${
              filter === f.id
                ? "border-b border-primary text-primary"
                : "text-muted-foreground hover:text-primary"
            }`}
          >
            {f.label}
            {n > 0 && <span className="ml-0.5 opacity-60">{n}</span>}
          </button>
        );
      })}
    </div>
  );

  if (embedded) {
    return (
      <div className="h-full overflow-y-auto flex flex-col">
        {count > 0 && filterBar}
        {sessionId && <AddTaskForm sessionId={sessionId} />}
        <div className="flex-1 overflow-y-auto">
          <TaskItems tasks={tasks} sessionId={sessionId} filter={filter} onTaskUpdate={onTaskUpdate} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col overflow-hidden h-full border border-border">
      <div className="border-b border-border bg-card px-4 py-2 shrink-0 flex items-center gap-3">
        <span className="text-primary text-xs uppercase tracking-wider font-mono">TASKS</span>
        <span className="text-muted-foreground text-xs font-mono">[{count}]</span>
      </div>
      {count > 0 && filterBar}
      {sessionId && <AddTaskForm sessionId={sessionId} />}
      <div className="flex-1 overflow-y-auto">
        <TaskItems tasks={tasks} sessionId={sessionId} filter={filter} onTaskUpdate={onTaskUpdate} />
      </div>
    </div>
  );
}
