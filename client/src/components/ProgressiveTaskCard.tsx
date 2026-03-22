type ProgressiveTaskCardProps = {
  task: {
    title?: string;
    name?: string;
    priority?: number;
    parent?: string | null;
    estimated_complexity?: string;
  };
  index: number;
};

const COMPLEXITY_COLORS: Record<string, string> = {
  low: "text-blue-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
};

export function ProgressiveTaskCard({ task, index }: ProgressiveTaskCardProps) {
  const title = task.title ?? task.name ?? "Untitled";
  const complexity = task.estimated_complexity ?? "";

  return (
    <div className="border border-dashed border-border/60 bg-card/40 px-3 py-2 font-mono text-xs space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground text-[10px] shrink-0">
          [{String(index + 1).padStart(2, "0")}]
        </span>
        {task.priority != null && (
          <span className="text-amber-400 text-[10px] shrink-0">
            [P{task.priority}]
          </span>
        )}
        <span className="text-foreground truncate">{title}</span>
        {complexity && (
          <span className={`text-[9px] uppercase tracking-wider shrink-0 ${COMPLEXITY_COLORS[complexity] ?? "text-muted-foreground"}`}>
            {complexity}
          </span>
        )}
        <span className="ml-auto text-[9px] text-muted-foreground/50 uppercase tracking-widest shrink-0">
          DRAFT
        </span>
      </div>
      {task.parent && (
        <div className="text-[9px] text-muted-foreground uppercase tracking-wider pl-8">
          DEPENDS ON: <span className="text-primary/70">{task.parent}</span>
        </div>
      )}
    </div>
  );
}
