import { useState, useRef, useEffect } from "react";
import { Check, Pencil } from "lucide-react";
import { API_URL } from "@/lib/config";

type Priority = "low" | "medium" | "high" | "critical";

type Task = {
  id: string;
  title: string;
  priority?: Priority;
  status?: string;
};

type InlineTaskCardProps = {
  task: Task;
  sessionId: string;
};

const PRIORITY_COLORS: Record<Priority, string> = {
  low: "text-blue-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  critical: "text-red-500",
};

const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];

/** Editable task card rendered inside the chat panel after ready state. */
export function InlineTaskCard({ task, sessionId }: InlineTaskCardProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [priority, setPriority] = useState<Priority>(
    (task.priority as Priority) ?? "medium",
  );
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const save = async () => {
    setSaving(true);
    try {
      await fetch(
        `${API_URL}/api/sessions/${sessionId}/tasks/${task.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, priority }),
        },
      );
    } catch {
      // best-effort -- local state already updated
    } finally {
      setSaving(false);
      setEditing(false);
    }
  };

  return (
    <div className="border border-border bg-card/60 font-mono text-xs flex items-center gap-2 px-2 py-1.5 group">
      {/* Priority dropdown */}
      <select
        value={priority}
        onChange={(e) => setPriority(e.target.value as Priority)}
        className={[
          "bg-transparent border-none outline-none cursor-pointer text-[10px] uppercase tracking-wider shrink-0",
          PRIORITY_COLORS[priority] ?? "text-muted-foreground",
        ].join(" ")}
        title="Priority"
      >
        {PRIORITIES.map((p) => (
          <option key={p} value={p} className="bg-background text-foreground">
            {p.toUpperCase()}
          </option>
        ))}
      </select>

      {/* Title -- inline edit on click */}
      {editing ? (
        <input
          ref={inputRef}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") {
              setTitle(task.title);
              setEditing(false);
            }
          }}
          className="flex-1 bg-transparent border-b border-primary outline-none text-foreground"
          disabled={saving}
        />
      ) : (
        <span
          className="flex-1 text-foreground truncate cursor-text"
          onClick={() => setEditing(true)}
          title="Click to edit"
        >
          {title}
        </span>
      )}

      {/* Status badge */}
      {task.status && (
        <span className="shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
          {task.status}
        </span>
      )}

      {/* Edit / save icon */}
      {editing ? (
        <button
          onClick={save}
          disabled={saving}
          title="Save"
          className="shrink-0 text-primary hover:opacity-70 disabled:opacity-40"
        >
          <Check className="size-3" />
        </button>
      ) : (
        <button
          onClick={() => setEditing(true)}
          title="Edit"
          className="shrink-0 text-muted-foreground hover:text-primary opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Pencil className="size-3" />
        </button>
      )}
    </div>
  );
}
