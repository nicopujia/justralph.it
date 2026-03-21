import { useState, useCallback } from "react";
import { RotateCcw } from "lucide-react";
import type { TaskInfo } from "@/hooks/useEventReducer";
import { API_URL } from "@/lib/config";

type TaskListProps = {
  tasks: Map<string, TaskInfo>;
  sessionId?: string;
  /** When true, renders without outer border wrapper (for embedding in RightPanel). */
  embedded?: boolean;
  /** Callback so parent can update a task's status locally after retry. */
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

// Bracketed status text -- open/done use muted, active/blocked use terminal colors.
const STATUS_TEXT: Record<TaskInfo["status"], { label: string; cls: string }> = {
  open: { label: "[OPEN]", cls: "text-muted-foreground" },
  in_progress: { label: "[IN_PROGRESS]", cls: "text-[#00FF41]" },
  blocked: { label: "[BLOCKED]", cls: "text-destructive" },
  done: { label: "[DONE]", cls: "text-[#00FF41] opacity-60" },
  help: { label: "[HELP]", cls: "text-destructive" },
};

const RETRYABLE: Set<TaskInfo["status"]> = new Set(["blocked", "help"]);

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
  const canRetry = RETRYABLE.has(task.status);
  const isBlocked = task.status === "blocked" || task.status === "help";
  const { label, cls } = STATUS_TEXT[task.status];

  const handleRetry = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!sessionId) return;
      setRetrying(true);
      try {
        // Reset task to open
        await fetch(`${API_URL}/api/sessions/${sessionId}/tasks/${task.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "open" }),
        });
        // Restart the loop so it picks up the task
        await fetch(`${API_URL}/api/sessions/${sessionId}/restart`, {
          method: "POST",
        });
        onTaskUpdate?.(task.id, { status: "open", error: undefined });
      } finally {
        setRetrying(false);
      }
    },
    [sessionId, task.id, onTaskUpdate],
  );

  return (
    <li
      className={`border-b border-border font-mono text-xs px-3 py-2 hover:bg-muted cursor-pointer select-none transition-colors ${
        isBlocked ? "border-l-2 border-l-destructive" : ""
      }`}
      onClick={onSelect}
    >
      {/* Fixed-width column row: [001] [STATUS] Title */}
      <div className="flex items-baseline gap-2">
        <span className="text-muted-foreground shrink-0">[{String(index + 1).padStart(3, "0")}]</span>
        <span className={`shrink-0 ${cls}`}>{label}</span>
        <span className="text-foreground truncate">{task.title}</span>
      </div>

      {/* Expanded detail */}
      <div
        className={`overflow-hidden transition-all duration-200 ${selected ? "max-h-40" : "max-h-0"}`}
      >
        <div className="pt-2 pl-2 space-y-2 border-t border-border mt-1">
          <p className="text-muted-foreground break-words">{task.id}</p>
          {task.error && (
            <p className="text-destructive break-words">{task.error}</p>
          )}
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
        </div>
      </div>
    </li>
  );
}

type TaskItemsProps = {
  tasks: Map<string, TaskInfo>;
  sessionId?: string;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

function TaskItems({ tasks, sessionId, onTaskUpdate }: TaskItemsProps) {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  // Most-recently-claimed task at the top (reverse insertion order)
  const taskEntries = Array.from(tasks.values()).reverse();

  if (taskEntries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-8">
        <span className="text-muted-foreground font-mono text-xs uppercase tracking-wider">NO TASKS YET</span>
      </div>
    );
  }

  return (
    <ul>
      {taskEntries.map((task, i) => (
        <TaskItem
          key={task.id}
          task={task}
          index={i}
          selected={selectedTaskId === task.id}
          onSelect={() =>
            setSelectedTaskId((prev) => (prev === task.id ? null : task.id))
          }
          sessionId={sessionId}
          onTaskUpdate={onTaskUpdate}
        />
      ))}
    </ul>
  );
}

export function TaskList({ tasks, sessionId, embedded = false, onTaskUpdate }: TaskListProps) {
  const count = tasks.size;

  if (embedded) {
    return (
      <div className="h-full overflow-y-auto">
        <TaskItems tasks={tasks} sessionId={sessionId} onTaskUpdate={onTaskUpdate} />
      </div>
    );
  }

  return (
    <div className="flex flex-col overflow-hidden h-full border border-border">
      <div className="border-b border-border bg-card px-4 py-2 shrink-0 flex items-center gap-3">
        <span className="text-primary text-xs uppercase tracking-wider font-mono">TASKS</span>
        <span className="text-muted-foreground text-xs font-mono">[{count}]</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <TaskItems tasks={tasks} sessionId={sessionId} onTaskUpdate={onTaskUpdate} />
      </div>
    </div>
  );
}
