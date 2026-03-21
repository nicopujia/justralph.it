import { useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ListTodo, RotateCcw } from "lucide-react";
import type { TaskInfo } from "@/hooks/useEventReducer";
import { API_URL } from "@/lib/config";

type TaskListProps = {
  tasks: Map<string, TaskInfo>;
  sessionId?: string;
  /** When true, renders without outer Card (for embedding in RightPanel). */
  embedded?: boolean;
  /** Callback so parent can update a task's status locally after retry. */
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

const STATUS_BADGE: Record<TaskInfo["status"], string> = {
  open: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  in_progress: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  blocked: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  done: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  help: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

const STATUS_LABEL: Record<TaskInfo["status"], string> = {
  open: "Open",
  in_progress: "In Progress",
  blocked: "Blocked",
  done: "Done",
  help: "Help",
};

const RETRYABLE: Set<TaskInfo["status"]> = new Set(["blocked", "help"]);

type TaskItemProps = {
  task: TaskInfo;
  selected: boolean;
  onSelect: () => void;
  sessionId?: string;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

function TaskItem({ task, selected, onSelect, sessionId, onTaskUpdate }: TaskItemProps) {
  const [retrying, setRetrying] = useState(false);
  const canRetry = RETRYABLE.has(task.status);
  const isBlocked = task.status === "blocked" || task.status === "help";

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
      className={`rounded-md border text-sm transition-colors cursor-pointer select-none
        ${isBlocked && selected ? "border-red-400 border-l-2" : ""}
        hover:bg-muted/50`}
      onClick={onSelect}
    >
      {/* Summary row */}
      <div className="flex items-start justify-between gap-2 px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-xs text-muted-foreground truncate">{task.id}</p>
          <p className={selected ? "mt-0.5" : "truncate mt-0.5"}>{task.title}</p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[task.status]}`}
        >
          {STATUS_LABEL[task.status]}
        </span>
      </div>

      {/* Expanded detail */}
      <div
        className={`overflow-hidden transition-all duration-200 ${selected ? "max-h-40" : "max-h-0"}`}
      >
        <div className="px-3 pb-3 pt-0 border-t space-y-2 ml-2">
          {task.error && (
            <p className="text-red-500 text-xs break-words">{task.error}</p>
          )}
          {canRetry && sessionId && (
            <Button
              variant="outline"
              size="sm"
              className="h-6 px-2 text-xs gap-1"
              disabled={retrying}
              onClick={handleRetry}
            >
              <RotateCcw className={`size-3 ${retrying ? "animate-spin" : ""}`} />
              {retrying ? "Retrying..." : "Retry"}
            </Button>
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
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm py-8">
        <ListTodo className="size-8 mb-2 opacity-40" />
        No tasks yet
      </div>
    );
  }

  return (
    <ul className="space-y-1">
      {taskEntries.map((task) => (
        <TaskItem
          key={task.id}
          task={task}
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
    <Card className="flex flex-col overflow-hidden h-full">
      <CardHeader className="pb-3 px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <ListTodo className="size-4" />
          Tasks
          <span className="ml-auto inline-flex items-center justify-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium tabular-nums">
            {count}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto px-2 pb-2">
        <TaskItems tasks={tasks} sessionId={sessionId} onTaskUpdate={onTaskUpdate} />
      </CardContent>
    </Card>
  );
}
