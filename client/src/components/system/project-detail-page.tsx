import { Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { NewProjectModal } from "@/components/system/new-project-modal";
import { ProjectChatPanel } from "@/components/system/project-chat-panel";
import { ProjectDetailViews } from "@/components/system/project-detail-views";
import { useProjectStore } from "@/components/system/project-store";
import { ProjectSidebar } from "@/components/system/project-sidebar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ProjectDetailPage() {
  const { projectId = "northstar-web" } = useParams();
  const navigate = useNavigate();
  const { createProject, getProjectDetail, projects } = useProjectStore();
  const project = getProjectDetail(projectId);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [chatWidth, setChatWidth] = useState(30);
  const [isDragging, setIsDragging] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  function handleCreateProject(input: { title: string; description: string }) {
    const nextProjectId = createProject(input);
    setModalOpen(false);
    setSidebarOpen(false);
    navigate(`/app/projects/${nextProjectId}`);
  }

  useEffect(() => {
    if (!isDragging) {
      return;
    }

    function handleMove(event: MouseEvent) {
      const width = window.innerWidth;
      const next = (event.clientX / width) * 100;
      setChatWidth(Math.min(55, Math.max(22, next)));
    }

    function handleUp() {
      setIsDragging(false);
    }

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);

    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [isDragging]);

  return (
    <div className="relative h-full overflow-hidden">
      <button
        type="button"
        className="absolute left-0 top-0 z-40 hidden h-full w-4 lg:block"
        onMouseEnter={() => setSidebarOpen(true)}
        aria-label="Reveal projects"
      />

      <div
        className={cn(
          "absolute inset-y-0 left-0 z-50 w-[300px] transition-transform duration-200",
          sidebarOpen ? "translate-x-0" : "-translate-x-[292px]",
        )}
        onMouseLeave={() => setSidebarOpen(false)}
      >
        <ProjectSidebar projects={projects} activeProjectId={project.id} compact onCreateProject={() => setModalOpen(true)} />
      </div>

      <div className="border-b border-border px-4 py-3 lg:hidden">
        <Button variant="secondary" size="sm" onClick={() => setSidebarOpen(open => !open)}>
          <Menu className="size-4" />
          Projects
        </Button>
      </div>

      <div className="lg:hidden">
        {sidebarOpen ? (
          <div className="border-b border-border">
            <ProjectSidebar projects={projects} activeProjectId={project.id} compact onCreateProject={() => setModalOpen(true)} />
          </div>
        ) : null}
      </div>

      <div className="hidden h-full min-h-0 lg:flex">
        <div className="min-w-0" style={{ width: `${chatWidth}%` }}>
          <ProjectChatPanel projectName={project.title} entries={project.chat} />
        </div>

        <button
          type="button"
          onMouseDown={() => setIsDragging(true)}
          className={cn(
            "group relative w-3 cursor-col-resize bg-transparent",
            isDragging && "bg-[rgba(255,255,255,0.04)]",
          )}
          aria-label="Resize panels"
        >
          <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-[rgba(255,255,255,0.1)] transition-colors group-hover:bg-[rgba(255,255,255,0.24)]" />
        </button>

        <div className="min-w-0 flex-1">
          <ProjectDetailViews project={project} />
        </div>
      </div>

      <div className="grid h-full min-h-0 lg:hidden">
        <ProjectChatPanel projectName={project.title} entries={project.chat} />
        <ProjectDetailViews project={project} />
      </div>

      <NewProjectModal open={modalOpen} onOpenChange={setModalOpen} onCreateProject={handleCreateProject} />
    </div>
  );
}
