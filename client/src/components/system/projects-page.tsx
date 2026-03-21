import { ArrowRight, FolderPlus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { NewProjectModal } from "@/components/system/new-project-modal";
import { useProjectStore } from "@/components/system/project-store";
import { ProjectSidebar } from "@/components/system/project-sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function ProjectsPage() {
  const navigate = useNavigate();
  const { createProject, projects } = useProjectStore();
  const [modalOpen, setModalOpen] = useState(false);

  function handleCreateProject(input: { title: string; description: string }) {
    const projectId = createProject(input);
    setModalOpen(false);
    navigate(`/app/projects/${projectId}`);
  }

  return (
    <>
      <div className="grid h-full overflow-hidden lg:grid-cols-[320px_1fr]">
        <ProjectSidebar projects={projects} onCreateProject={() => setModalOpen(true)} />

        <section className="relative flex h-full min-h-0 items-center justify-center overflow-hidden px-6 py-10 sm:px-8 lg:px-12">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.05),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_28%)]" />

          <Card className="relative w-full max-w-[620px] bg-[rgba(19,19,20,0.75)] py-0">
            <CardContent className="grid gap-8 px-8 py-10 text-center sm:px-12 sm:py-14">
              <div className="mx-auto flex size-14 items-center justify-center rounded-full border border-border bg-panel">
                <FolderPlus className="size-5 text-[color:var(--text-secondary)]" />
              </div>
              <div className="grid gap-3">
                <h1 className="font-serif-ui text-4xl tracking-[-0.05em] text-foreground sm:text-5xl">Create the next project.</h1>
                <p className="mx-auto max-w-[420px] text-sm leading-7 text-[color:var(--text-secondary)]">
                  Start a new workspace when you need Ralph to turn an idea into a stable execution plan.
                </p>
              </div>
              <div className="flex justify-center">
                <Button className="h-11 px-5" onClick={() => setModalOpen(true)}>
                  New Project
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>

      <NewProjectModal open={modalOpen} onOpenChange={setModalOpen} onCreateProject={handleCreateProject} />
    </>
  );
}
