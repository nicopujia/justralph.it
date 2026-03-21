import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import {
  Rocket,
  ArrowUp,
  ArrowDown,
  X,
  Pencil,
  ChevronDown,
  ChevronRight,
  Loader2,
} from "lucide-react";

export type PreviewTask = {
  title: string;
  body: string;
  priority: number;
  parent: string | null;
};

type TaskPreviewProps = {
  tasks: PreviewTask[];
  project: {
    name: string;
    language: string;
    framework: string;
    description: string;
  } | null;
  onConfirm: (tasks: PreviewTask[]) => void;
  onBack: () => void;
  loading?: boolean;
};

type TaskCardProps = {
  task: PreviewTask;
  index: number;
  total: number;
  onUpdate: (patch: Partial<PreviewTask>) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
};

// Priority badge: color by level 1-5
const PRIORITY_COLORS: Record<number, string> = {
  1: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  2: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  3: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  4: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  5: "bg-muted text-muted-foreground",
};

function PriorityBadge({ priority }: { priority: number }) {
  const cls = PRIORITY_COLORS[priority] ?? PRIORITY_COLORS[5];
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      P{priority}
    </span>
  );
}

function TaskCard({
  task,
  index,
  total,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
}: TaskCardProps) {
  const [editingTitle, setEditingTitle] = useState(false);
  const [bodyOpen, setBodyOpen] = useState(false);
  const [titleDraft, setTitleDraft] = useState(task.title);

  const commitTitle = () => {
    const trimmed = titleDraft.trim();
    if (trimmed) onUpdate({ title: trimmed });
    setEditingTitle(false);
  };

  return (
    <Card className="py-0 gap-0">
      <CardContent className="px-4 py-3 flex flex-col gap-2">
        {/* Top row: reorder + title + badges + actions */}
        <div className="flex items-start gap-2">
          {/* Reorder buttons */}
          <div className="flex flex-col gap-0.5 shrink-0 mt-0.5">
            <Button
              variant="ghost"
              size="icon"
              className="size-5"
              disabled={index === 0}
              onClick={onMoveUp}
              title="Move up"
            >
              <ArrowUp className="size-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-5"
              disabled={index === total - 1}
              onClick={onMoveDown}
              title="Move down"
            >
              <ArrowDown className="size-3" />
            </Button>
          </div>

          {/* Title */}
          <div className="flex-1 min-w-0">
            {editingTitle ? (
              <Input
                autoFocus
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                onBlur={commitTitle}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitTitle();
                  if (e.key === "Escape") {
                    setTitleDraft(task.title);
                    setEditingTitle(false);
                  }
                }}
                className="h-7 text-sm"
              />
            ) : (
              <button
                className="text-sm font-medium text-left w-full truncate flex items-center gap-1 group"
                onClick={() => {
                  setTitleDraft(task.title);
                  setEditingTitle(true);
                }}
                title="Click to edit title"
              >
                <span className="truncate">{task.title}</span>
                <Pencil className="size-3 opacity-0 group-hover:opacity-50 shrink-0 transition-opacity" />
              </button>
            )}
          </div>

          {/* Priority badge */}
          <PriorityBadge priority={task.priority} />

          {/* Delete */}
          <Button
            variant="ghost"
            size="icon"
            className="size-6 shrink-0 text-muted-foreground hover:text-destructive"
            onClick={onDelete}
            title="Remove task"
          >
            <X className="size-3.5" />
          </Button>
        </div>

        {/* Parent dependency indicator */}
        {task.parent && (
          <p className="text-xs text-muted-foreground pl-7">
            Depends on: <span className="font-mono">{task.parent}</span>
          </p>
        )}

        {/* Collapsible body / acceptance criteria */}
        <div className="pl-7">
          <button
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setBodyOpen((v) => !v)}
          >
            {bodyOpen ? (
              <ChevronDown className="size-3" />
            ) : (
              <ChevronRight className="size-3" />
            )}
            {bodyOpen ? "Hide" : "Show"} acceptance criteria
          </button>

          {bodyOpen && (
            <Textarea
              className="mt-2 text-xs min-h-20 resize-y"
              value={task.body}
              placeholder="No acceptance criteria yet..."
              onChange={(e) => onUpdate({ body: e.target.value })}
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function TaskPreview({
  tasks: initialTasks,
  project,
  onConfirm,
  onBack,
  loading = false,
}: TaskPreviewProps) {
  // Local mutable copy -- user edits apply here before confirm
  const [tasks, setTasks] = useState<PreviewTask[]>(initialTasks);

  const updateTask = (index: number, patch: Partial<PreviewTask>) => {
    setTasks((prev) =>
      prev.map((t, i) => (i === index ? { ...t, ...patch } : t)),
    );
  };

  const deleteTask = (index: number) => {
    setTasks((prev) => prev.filter((_, i) => i !== index));
  };

  const moveTask = (index: number, direction: -1 | 1) => {
    const next = index + direction;
    if (next < 0 || next >= tasks.length) return;
    setTasks((prev) => {
      const copy = [...prev];
      [copy[index], copy[next]] = [copy[next], copy[index]];
      return copy;
    });
  };

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <div className="border-b px-6 py-4 shrink-0">
        <h1 className="text-lg font-semibold">Review Tasks</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {tasks.length} task{tasks.length !== 1 ? "s" : ""} generated
          {project ? ` for ${project.name}` : ""}. Edit before starting the loop.
        </p>
      </div>

      {/* Scrollable task list */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <p className="text-sm">All tasks removed. Go back to chat to regenerate.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3 max-w-2xl mx-auto">
            {tasks.map((task, i) => (
              <TaskCard
                key={i}
                task={task}
                index={i}
                total={tasks.length}
                onUpdate={(patch) => updateTask(i, patch)}
                onDelete={() => deleteTask(i)}
                onMoveUp={() => moveTask(i, -1)}
                onMoveDown={() => moveTask(i, 1)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t px-6 py-4 flex items-center justify-between gap-3 shrink-0">
        <Button variant="outline" onClick={onBack} disabled={loading}>
          Back to Chat
        </Button>

        <Button
          className="bg-green-600 hover:bg-green-700 text-white"
          onClick={() => onConfirm(tasks)}
          disabled={loading || tasks.length === 0}
          size="lg"
        >
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Starting...
            </>
          ) : (
            <>
              <Rocket className="size-4" />
              Confirm &amp; Start
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
