import { FolderPlus, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { type ProjectSummary } from "@/components/system/app-data";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ProjectSidebarProps = {
  projects: ProjectSummary[];
  activeProjectId?: string;
  compact?: boolean;
  onCreateProject?: () => void;
  onRenameProject?: (project: ProjectSummary) => void;
  onDeleteProject?: (project: ProjectSummary) => void;
};

export function ProjectSidebar({
  projects,
  activeProjectId,
  compact = false,
  onCreateProject,
  onRenameProject,
  onDeleteProject,
}: ProjectSidebarProps) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const sidebarRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (!sidebarRef.current?.contains(event.target as Node)) {
        setOpenMenuId(null);
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <aside ref={sidebarRef} className={cn("flex h-full min-h-0 flex-col border-r border-border bg-elevated", compact ? "w-[300px]" : "w-full")}>
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
              <div
                key={project.id}
                className={cn(
                  "relative rounded-[var(--radius-md)] border border-transparent transition-colors",
                  isActive
                    ? "border-border bg-panel text-foreground"
                    : "text-[color:var(--text-secondary)] hover:border-border hover:bg-[rgba(255,255,255,0.03)] hover:text-foreground",
                )}
              >
                <Link to={`/app/projects/${project.id}`} className="grid gap-2 px-3 py-3 pr-12">
                  <div className="flex items-start justify-between gap-3">
                    <div className="grid gap-1">
                      <p className="text-sm text-inherit">{project.name}</p>
                      <p className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{project.client}</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-3 text-xs text-[color:var(--text-muted)]">
                    <span>{project.status}</span>
                    <span>{project.issueCount} issues</span>
                  </div>
                  <p className="text-xs text-[color:var(--text-muted)]">{project.activity}</p>
                </Link>

                <div className="absolute right-2 top-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="size-8"
                    aria-label={`Open actions for ${project.name}`}
                    onClick={event => {
                      event.preventDefault();
                      event.stopPropagation();
                      setOpenMenuId(current => (current === project.id ? null : project.id));
                    }}
                  >
                    <MoreHorizontal className="size-4 text-[color:var(--text-muted)]" />
                  </Button>

                  {openMenuId === project.id ? (
                    <div className="absolute right-0 top-10 z-20 grid min-w-[168px] gap-1 rounded-[var(--radius-md)] border border-border bg-[rgba(12,12,13,0.98)] p-1 shadow-[0_18px_48px_rgba(0,0,0,0.42)]">
                      <Button
                        type="button"
                        variant="ghost"
                        className="h-9 justify-start px-3 text-left text-foreground"
                        onClick={event => {
                          event.preventDefault();
                          event.stopPropagation();
                          setOpenMenuId(null);
                          onRenameProject?.(project);
                        }}
                      >
                        <Pencil className="size-4" />
                        Rename
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        className="h-9 justify-start px-3 text-left text-[#f3d2d2] hover:bg-[rgba(208,141,141,0.12)] hover:text-[#f7dede]"
                        onClick={event => {
                          event.preventDefault();
                          event.stopPropagation();
                          setOpenMenuId(null);
                          onDeleteProject?.(project);
                        }}
                      >
                        <Trash2 className="size-4" />
                        Delete
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
