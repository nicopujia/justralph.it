import { ArrowRight, FolderPlus, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type NewProjectModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateProject: (input: { title: string; description: string }) => void;
};

export function NewProjectModal({ open, onOpenChange, onCreateProject }: NewProjectModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (open) {
      return;
    }

    setTitle("");
    setDescription("");
  }, [open]);

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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextTitle = title.trim();
    const nextDescription = description.trim();

    if (!nextTitle || !nextDescription) {
      return;
    }

    onCreateProject({ title: nextTitle, description: nextDescription });
  }

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-[rgba(0,0,0,0.62)] px-4 py-4 backdrop-blur-sm sm:items-center sm:px-6">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Close new project modal" onClick={() => onOpenChange(false)} />

      <section className="relative z-10 w-full max-w-[760px] overflow-hidden rounded-[var(--radius-lg)] border border-border bg-[rgba(12,12,13,0.96)] shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(230,235,255,0.06),transparent_32%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_28%)]" />

        <div className="relative border-b border-border px-5 py-5 sm:px-7 sm:py-6">
          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-4">
              <div className="flex size-12 items-center justify-center rounded-[var(--radius-md)] border border-border bg-[rgba(255,255,255,0.03)]">
                <FolderPlus className="size-5 text-[color:var(--text-secondary)]" />
              </div>
              <div className="grid gap-2">
                <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">New project</p>
                <h2 className="font-serif-ui text-3xl tracking-[-0.04em] text-foreground sm:text-[2.2rem]">Open a fresh execution workspace.</h2>
                <p className="max-w-2xl text-sm leading-7 text-[color:var(--text-secondary)]">
                  Title the workspace, then provide the first operating brief. That description becomes the opening message Ralph uses to start the chat.
                </p>
              </div>
            </div>

            <Button variant="ghost" size="icon-sm" onClick={() => onOpenChange(false)} aria-label="Close modal">
              <X className="size-4" />
            </Button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="relative grid gap-6 px-5 py-5 sm:px-7 sm:py-7">
          <div className="grid gap-5">
            <div className="grid gap-2">
              <Label htmlFor="new-project-title">Project title</Label>
              <Input
                id="new-project-title"
                value={title}
                onChange={event => setTitle(event.target.value)}
                placeholder="Northstar relaunch"
                autoFocus
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="new-project-description">Initial brief</Label>
              <Textarea
                id="new-project-description"
                value={description}
                onChange={event => setDescription(event.target.value)}
                placeholder="Define the project goals, constraints, stakeholders, and what Ralph should clarify first."
                className="min-h-[180px]"
              />
              <p className="text-xs leading-6 text-[color:var(--text-muted)]">
                The brief is sent as the first user message when the project opens.
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm leading-6 text-[color:var(--text-secondary)]">Keep the first brief tight enough to anchor scope, then refine inside the chat.</p>
            <div className="flex flex-wrap gap-3">
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" className="h-11 px-5" disabled={!title.trim() || !description.trim()}>
                Create project
                <ArrowRight className="size-4" />
              </Button>
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
