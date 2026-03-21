import { useMemo, useState } from "react";

import { type ProjectDetail } from "@/components/system/app-data";
import { AgentDocumentView } from "@/components/system/agent-document-view";
import { CodeReader } from "@/components/system/code-reader";
import { IssuesBeadBoard } from "@/components/system/issues-bead-board";
import { cn } from "@/lib/utils";

type DetailView = "issues" | "agent" | "code";

const tabs: Array<{ id: DetailView; label: string }> = [
  { id: "agent", label: "agent.md" },
  { id: "issues", label: "Issues" },
  { id: "code", label: "Code" },
];

export function ProjectDetailViews({ project }: { project: ProjectDetail }) {
  const [activeView, setActiveView] = useState<DetailView>("issues");

  const content = useMemo(() => {
    switch (activeView) {
      case "agent":
        return <AgentDocumentView content={project.agentDocument} />;
      case "code":
        return <CodeReader tasks={project.stdoutTasks} />;
      case "issues":
      default:
        return <IssuesBeadBoard rows={project.issues} />;
    }
  }, [activeView, project]);

  return (
    <section className="flex h-full min-h-0 flex-col bg-background">
      <div className="border-b border-border px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="grid gap-1">
            <h2 className="text-lg tracking-[-0.03em] text-foreground">{project.title}</h2>
            <p className="text-sm text-[#cbc7be]">{project.updatedAt}</p>
          </div>

          <div className="inline-flex rounded-[var(--radius-sm)] border border-border bg-[rgba(255,255,255,0.02)] p-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveView(tab.id)}
                className={cn(
                  "rounded-[4px] px-3 py-2 text-sm transition-colors",
                  activeView === tab.id ? "bg-panel text-foreground" : "text-[color:var(--text-muted)] hover:text-[color:var(--text-secondary)]",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-5">{content}</div>
    </section>
  );
}
