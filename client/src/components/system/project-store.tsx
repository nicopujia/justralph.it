import { createContext, type ReactNode, useContext, useMemo, useState } from "react";

import {
  createInitialProjectCollection,
  type ChatEntry,
  type ProjectCollection,
  type ProjectDetail,
  type ProjectSummary,
} from "@/components/system/app-data";

type CreateProjectInput = {
  title: string;
  description: string;
};

type ProjectStoreValue = {
  projects: ProjectSummary[];
  getProjectDetail: (projectId: string) => ProjectDetail;
  createProject: (input: CreateProjectInput) => string;
};

const ProjectStoreContext = createContext<ProjectStoreValue | null>(null);

function slugifyProjectTitle(title: string) {
  return title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function deriveClientName(title: string) {
  const trimmed = title.trim();

  if (!trimmed) {
    return "New client";
  }

  const [firstWord] = trimmed.split(/\s+/);
  return `${firstWord} team`;
}

function buildAssistantReply(title: string) {
  return `Understood. I opened ${title} as a new execution workspace and converted the initial brief into the first planning pass. Next I will reduce the scope to stable requirements, surface blockers, and prepare the first operating plan.`;
}

export function ProjectStoreProvider({ children }: { children: ReactNode }) {
  const [collection, setCollection] = useState<ProjectCollection>(() => createInitialProjectCollection());

  const value = useMemo<ProjectStoreValue>(
    () => ({
      projects: collection.projects,
      getProjectDetail: (projectId: string) => collection.projectDetailsById[projectId] ?? collection.projectDetailsById["northstar-web"],
      createProject: ({ title, description }) => {
        const normalizedTitle = title.trim();
        const normalizedDescription = description.trim();
        const baseId = slugifyProjectTitle(normalizedTitle) || "new-project";

        let projectId = baseId;
        let suffix = 2;

        while (collection.projectDetailsById[projectId]) {
          projectId = `${baseId}-${suffix}`;
          suffix += 1;
        }

        const now = Date.now();
        const initialChat: ChatEntry[] = [
          { id: `user-${now}`, role: "user", text: normalizedDescription },
          { id: `assistant-${now + 1}`, role: "assistant", text: buildAssistantReply(normalizedTitle), cta: "just ralph it" },
        ];

        setCollection(current => ({
          projects: [
            {
              id: projectId,
              name: normalizedTitle,
              client: deriveClientName(normalizedTitle),
              status: "Needs input",
              activity: "Workspace opened just now",
              issueCount: 0,
            },
            ...current.projects,
          ],
          projectDetailsById: {
            ...current.projectDetailsById,
            [projectId]: {
              id: projectId,
              title: normalizedTitle,
              branch: `spec/${projectId}`,
              updatedAt: "Updated just now",
              summary: normalizedDescription,
              chat: initialChat,
              issues: [],
              agentDocument: `# agent.md\n\nObjective\nClarify and execute ${normalizedTitle}.\n\nInitial brief\n${normalizedDescription}\n\nOpen\n1. Scope boundaries\n2. Constraints\n3. Delivery sequence\n\nRule\nDo not begin implementation until the brief is reduced to stable requirements.`,
              stdoutTasks: [
                {
                  title: "Task 01  Convert brief into plan",
                  lines: [
                    `[ralph] opening workspace: ${projectId}`,
                    "[ralph] recording initial brief from operator",
                    "[ralph] reducing brief into stable requirements",
                    "[ralph] identifying missing constraints and dependencies",
                    "[ralph] preparing first execution-safe pass",
                    "[ralph] waiting for next user instruction",
                  ],
                },
              ],
            },
          },
        }));

        return projectId;
      },
    }),
    [collection],
  );

  return <ProjectStoreContext.Provider value={value}>{children}</ProjectStoreContext.Provider>;
}

export function useProjectStore() {
  const context = useContext(ProjectStoreContext);

  if (!context) {
    throw new Error("useProjectStore must be used within a ProjectStoreProvider");
  }

  return context;
}
