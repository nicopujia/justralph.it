import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ListTodo } from "lucide-react";
import type { TaskInfo } from "@/hooks/useEventReducer";

type TaskListProps = {
  tasks: Map<string, TaskInfo>;
  /** When true, renders without outer Card (for embedding in RightPanel). */
  embedded?: boolean;
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

function TaskItems({ tasks }: { tasks: Map<string, TaskInfo> }) {
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
        <li
          key={task.id}
          className="rounded-md border px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="font-mono text-xs text-muted-foreground truncate">
                {task.id}
              </p>
              <p className="truncate mt-0.5">{task.title}</p>
            </div>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[task.status]}`}
            >
              {STATUS_LABEL[task.status]}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function TaskList({ tasks, embedded = false }: TaskListProps) {
  const count = tasks.size;

  if (embedded) {
    return (
      <div className="h-full overflow-y-auto">
        <TaskItems tasks={tasks} />
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
        <TaskItems tasks={tasks} />
      </CardContent>
    </Card>
  );
}
