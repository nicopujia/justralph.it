import { FolderPlus, MoreHorizontal } from "lucide-react";
import { Link } from "react-router-dom";

import { type ProjectSummary } from "@/components/system/app-data";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ProjectSidebarProps = {
  projects: ProjectSummary[];
  activeProjectId?: string;
  compact?: boolean;
  onCreateProject?: () => void;
};

export function ProjectSidebar({ projects, activeProjectId, compact = false, onCreateProject }: ProjectSidebarProps) {
  return (
    <aside className={cn("flex h-full min-h-0 flex-col border-r border-border bg-elevated", compact ? "w-[300px]" : "w-full")}>
      <div className="border-b border-border px-4 py-4">
        <Button
          variant="secondary"
          className="h-10 w-full justify-between bg-[rgba(255,255,255,0.08)] text-foreground hover:bg-[rgba(255,255,255,0.12)]"
          onClick={onCreateProject}
        >
          <span>New Project</span>
          <FolderPlus className="size-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        <div className="grid gap-1">
          {projects.map(project => {
            const isActive = project.id === activeProjectId;

            return (
              <Link
                key={project.id}
                to={`/app/projects/${project.id}`}
                className={cn(
                  "grid gap-2 rounded-[var(--radius-md)] border border-transparent px-3 py-3 transition-colors",
                  isActive
                    ? "border-border bg-panel text-foreground"
                    : "text-[color:var(--text-secondary)] hover:border-border hover:bg-[rgba(255,255,255,0.03)] hover:text-foreground",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="grid gap-1">
                    <p className="text-sm text-inherit">{project.name}</p>
                    <p className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{project.client}</p>
                  </div>
                  <MoreHorizontal className="mt-0.5 size-4 text-[color:var(--text-muted)]" />
                </div>
                <div className="flex items-center justify-between gap-3 text-xs text-[color:var(--text-muted)]">
                  <span>{project.status}</span>
                  <span>{project.issueCount} issues</span>
                </div>
                <p className="text-xs text-[color:var(--text-muted)]">{project.activity}</p>
              </Link>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
