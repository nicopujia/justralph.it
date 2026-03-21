import { Pencil, Trash2, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { type ProjectSummary } from "@/components/system/app-data";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type ProjectManageModalProps = {
  mode: "rename" | "delete" | null;
  project?: ProjectSummary;
  onOpenChange: (open: boolean) => void;
  onRenameProject: (projectId: string, title: string) => void;
  onDeleteProject: (projectId: string) => void;
};

export function ProjectManageModal({ mode, project, onOpenChange, onRenameProject, onDeleteProject }: ProjectManageModalProps) {
  const [title, setTitle] = useState("");
  const open = Boolean(mode && project);

  useEffect(() => {
    if (!open || !project) {
      setTitle("");
      return;
    }

    setTitle(project.name);
  }, [open, project]);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onOpenChange(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpenChange, open]);

  function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!project || !title.trim()) {
      return;
    }

    onRenameProject(project.id, title.trim());
    onOpenChange(false);
  }

  function handleDelete() {
    if (!project) {
      return;
    }

    onDeleteProject(project.id);
    onOpenChange(false);
  }

  if (!open || !project) {
    return null;
  }

  const isRename = mode === "rename";

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-[rgba(0,0,0,0.62)] px-4 py-4 backdrop-blur-sm sm:items-center sm:px-6">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Close project management modal" onClick={() => onOpenChange(false)} />

      <section className="relative z-10 w-full max-w-[560px] overflow-hidden rounded-[var(--radius-lg)] border border-border bg-[rgba(12,12,13,0.96)] shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(230,235,255,0.06),transparent_32%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_28%)]" />

        <div className="relative border-b border-border px-5 py-5 sm:px-7 sm:py-6">
          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-4">
              <div className="flex size-12 items-center justify-center rounded-[var(--radius-md)] border border-border bg-[rgba(255,255,255,0.03)]">
                {isRename ? <Pencil className="size-5 text-[color:var(--text-secondary)]" /> : <Trash2 className="size-5 text-[#f3d2d2]" />}
              </div>
              <div className="grid gap-2">
                <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Project actions</p>
                <h2 className="font-serif-ui text-3xl tracking-[-0.04em] text-foreground sm:text-[2.2rem]">
                  {isRename ? "Rename this workspace." : "Delete this workspace?"}
                </h2>
                <p className="max-w-xl text-sm leading-7 text-[color:var(--text-secondary)]">
                  {isRename
                    ? "Update the project title shown in the sidebar and detail view."
                    : `Remove ${project.name} from the project list and close out its current workspace data.`}
                </p>
              </div>
            </div>

            <Button variant="ghost" size="icon-sm" onClick={() => onOpenChange(false)} aria-label="Close modal">
              <X className="size-4" />
            </Button>
          </div>
        </div>

        {isRename ? (
          <form onSubmit={handleRename} className="relative grid gap-6 px-5 py-5 sm:px-7 sm:py-7">
            <div className="grid gap-2">
              <Label htmlFor="rename-project-title">Project title</Label>
              <Input id="rename-project-title" value={title} onChange={event => setTitle(event.target.value)} autoFocus />
            </div>

            <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-[color:var(--text-secondary)]">Keep the title specific enough that the workspace still reads clearly in the sidebar.</p>
              <div className="flex flex-wrap gap-3">
                <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button type="submit" className="h-11 px-5" disabled={!title.trim()}>
                  Save name
                </Button>
              </div>
            </div>
          </form>
        ) : (
          <div className="relative grid gap-6 px-5 py-5 sm:px-7 sm:py-7">
            <div className="rounded-[var(--radius-md)] border border-[#654545] bg-[rgba(208,141,141,0.08)] px-4 py-4 text-sm leading-7 text-[#f3d2d2]">
              This action removes the project from the current app session. Use it when the workspace is no longer needed.
            </div>

            <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-[color:var(--text-secondary)]">Delete only if you are done with this project card and its local detail state.</p>
              <div className="flex flex-wrap gap-3">
                <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button type="button" variant="destructive" className="h-11 px-5" onClick={handleDelete}>
                  Delete project
                </Button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
