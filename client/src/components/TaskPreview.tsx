import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
    <div className="border border-border bg-card font-mono">
      <div className="px-4 py-3 flex flex-col gap-2">
        {/* Top row: reorder + title + priority + delete */}
        <div className="flex items-start gap-2">
          {/* Reorder buttons */}
          <div className="flex flex-col gap-0.5 shrink-0 mt-0.5">
            <button
              className="size-5 flex items-center justify-center text-muted-foreground hover:text-primary disabled:opacity-20 transition-colors"
              disabled={index === 0}
              onClick={onMoveUp}
              title="Move up"
            >
              <ArrowUp className="size-3" />
            </button>
            <button
              className="size-5 flex items-center justify-center text-muted-foreground hover:text-primary disabled:opacity-20 transition-colors"
              disabled={index === total - 1}
              onClick={onMoveDown}
              title="Move down"
            >
              <ArrowDown className="size-3" />
            </button>
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
                className="h-7 text-xs bg-background border-border text-primary"
              />
            ) : (
              <button
                className="text-xs text-foreground text-left w-full truncate flex items-center gap-1 group"
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

          {/* Priority [P1] format -- amber is intentional, not theme-switched */}
          <span className="text-amber-500 text-[10px] tracking-wider shrink-0">[P{task.priority}]</span>

          {/* Delete */}
          <button
            className="size-6 shrink-0 flex items-center justify-center text-muted-foreground hover:text-destructive transition-colors"
            onClick={onDelete}
            title="Remove task"
          >
            <X className="size-3.5" />
          </button>
        </div>

        {/* Parent dependency indicator */}
        {task.parent && (
          <p className="text-muted-foreground text-[10px] pl-7">
            DEPENDS ON: <span className="text-amber-500">{task.parent}</span>
          </p>
        )}

        {/* Collapsible body / acceptance criteria */}
        <div className="pl-7">
          <button
            className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-primary uppercase tracking-wider transition-colors"
            onClick={() => setBodyOpen((v) => !v)}
          >
            {bodyOpen ? (
              <ChevronDown className="size-3" />
            ) : (
              <ChevronRight className="size-3" />
            )}
            {bodyOpen ? "HIDE" : "SHOW"} ACCEPTANCE CRITERIA
          </button>

          {bodyOpen && (
            <Textarea
              className="mt-2 text-xs min-h-20 resize-y bg-background border-border text-primary placeholder:text-muted-foreground"
              value={task.body}
              placeholder="No acceptance criteria yet..."
              onChange={(e) => onUpdate({ body: e.target.value })}
            />
          )}
        </div>
      </div>
    </div>
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
  // Track whether the initial load had tasks (to distinguish "never generated" from "user removed all")
  const [hadInitialTasks] = useState(() => initialTasks.length > 0);

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
    <div className="h-screen flex flex-col bg-background font-mono">
      {/* Header */}
      <div className="border-b border-border px-6 py-4 shrink-0">
        <h1 className="text-foreground text-sm font-bold uppercase tracking-wider">REVIEW TASKS</h1>
        <p className="text-muted-foreground text-xs mt-1 tracking-wider">
          {tasks.length} TASK{tasks.length !== 1 ? "S" : ""} GENERATED
          {project ? ` FOR ${project.name.toUpperCase()}` : ""}. EDIT BEFORE STARTING THE LOOP.
        </p>
      </div>

      {/* Scrollable task list */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <p className="text-muted-foreground text-xs uppercase tracking-wider">
              {hadInitialTasks
                ? "ALL TASKS REMOVED. GO BACK TO CHAT TO REGENERATE."
                : "NO TASKS GENERATED YET. GO BACK TO CHAT TO CONTINUE THE CONVERSATION."}
            </p>
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
      <div className="border-t border-border px-6 py-4 flex items-center justify-between gap-3 shrink-0">
        <button
          className="border border-border text-muted-foreground hover:text-foreground hover:border-foreground uppercase tracking-wider text-xs px-4 py-2 transition-colors disabled:opacity-50"
          onClick={onBack}
          disabled={loading}
        >
          BACK TO CHAT
        </button>

        <button
          className="border-2 border-primary text-primary hover:bg-primary hover:text-primary-foreground uppercase tracking-wider text-xs px-6 py-2 transition-colors disabled:opacity-50 flex items-center gap-2"
          onClick={() => onConfirm(tasks)}
          disabled={loading || tasks.length === 0}
        >
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              STARTING...
            </>
          ) : (
            <>
              <Rocket className="size-4" />
              CONFIRM &amp; START
            </>
          )}
        </button>
      </div>
    </div>
  );
}
