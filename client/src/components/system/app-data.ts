import issuesData from "@/data/issues.json";

export type ProjectSummary = {
  id: string;
  name: string;
  client: string;
  status: string;
  activity: string;
  issueCount: number;
};

export type ChatEntry = {
  id: string;
  role: "assistant" | "user";
  text: string;
  cta?: string;
};

export type IssueRow = {
  id: string;
  type: "Task" | "Feature" | "Epic" | "Bug";
  title: string;
  status: "Open" | "In progress" | "Closed";
  assignee: string;
  priority: "High" | "Medium" | "Low";
};

export type RepoNode = {
  id: string;
  name: string;
  type: "folder" | "file";
  children?: RepoNode[];
};

export type ProjectDetail = {
  id: string;
  title: string;
  branch: string;
  updatedAt: string;
  summary: string;
  chat: ChatEntry[];
  issues: IssueRow[];
  agentDocument: string;
  stdoutTasks: Array<{ title: string; lines: string[] }>;
};

export type ProjectCollection = {
  projects: ProjectSummary[];
  projectDetailsById: Record<string, ProjectDetail>;
};

export const currentPlan = "Pro";

const mockedIssues = issuesData as IssueRow[];

export const initialProjects: ProjectSummary[] = [
  {
    id: "northstar-web",
    name: "Northstar relaunch",
    client: "Northstar Studio",
    status: "Needs input",
    activity: "Requirements tightened 24m ago",
    issueCount: 11,
  },
  {
    id: "atlas-portal",
    name: "Atlas client portal",
    client: "Atlas Capital",
    status: "Blocked",
    activity: "Credential request pending",
    issueCount: 8,
  },
  {
    id: "signal-api",
    name: "Signal API rollout",
    client: "Signal Health",
    status: "In review",
    activity: "Spec revision published",
    issueCount: 5,
  },
  {
    id: "meridian-admin",
    name: "Meridian admin",
    client: "Meridian Ops",
    status: "Ready",
    activity: "Execution map approved",
    issueCount: 4,
  },
  {
    id: "lattice-mobile",
    name: "Lattice mobile sync",
    client: "Lattice Labs",
    status: "Needs input",
    activity: "Awaiting offline rules",
    issueCount: 7,
  },
];

export const initialProjectDetailsById: Record<string, ProjectDetail> = {
  "northstar-web": {
    id: "northstar-web",
    title: "Northstar relaunch",
    branch: "spec/northstar-relaunch",
    updatedAt: "Updated 12 minutes ago",
    summary: "A tighter build brief for the relaunch, with CMS, analytics, and deployment dependencies still under review.",
    chat: [
      {
        id: "c1",
        role: "assistant",
        text: "The plan is now reduced to one marketing flow, one case-study collection, and a gated contact path. Remaining risk is concentrated in analytics ownership and the launch cutover window.",
      },
      {
        id: "c2",
        role: "user",
        text: "Keep the scope narrow and make sure we do not add operational dependencies that the client cannot own after launch.",
      },
      {
        id: "c3",
        role: "assistant",
        text: "Understood. I removed optional integrations from the first milestone and kept the architecture biased toward a low-maintenance handoff. The next step is to resolve the notification owner and DNS timing.",
        cta: "just ralph it",
      },
    ],
    issues: mockedIssues,
    agentDocument: `# agent.md

Objective
Stabilize the relaunch before implementation begins.

Constraints
- One CMS collection only.
- Lightweight public pages.
- Contact flow must route through an owned channel.
- Bilingual support stays dormant in v1.

Open
1. Analytics ownership
2. DNS cutover timing
3. Notification target

Rule
Do not create build tasks that depend on unknown credentials.`,
    stdoutTasks: [
      {
        title: "Task 01  Resolve remaining ownership assumptions",
        lines: [
          "[ralph] loading project memory: northstar-web",
          "[ralph] scanning unresolved notes in agent.md",
          "[ralph] detected open question: analytics account owner",
          "[ralph] detected open question: dns cutover timing",
          "[ralph] detected open question: contact notification target",
          "[ralph] comparing previous user replies against current execution graph",
          "[ralph] no contradiction found in cms scope",
          "[ralph] no contradiction found in bilingual deferral",
          "[ralph] drafting clarification request bundle",
          "[ralph] task complete",
        ],
      },
      {
        title: "Task 02  Prepare execution-safe milestone map",
        lines: [
          "[ralph] clearing previous terminal output",
          "[ralph] generating milestone map from stable requirements",
          "[ralph] milestone 1: information architecture and narrative hierarchy",
          "[ralph] milestone 2: case study schema and editorial model",
          "[ralph] milestone 3: contact path with owned delivery channel",
          "[ralph] milestone 4: preview deployment and final cutover checklist",
          "[ralph] assigning blockers to pre-execution state",
          "[ralph] writing success criteria for each milestone",
          "[ralph] validating tasks for missing credentials",
          "[ralph] task complete",
        ],
      },
      {
        title: "Task 03  Simulate implementation stdout",
        lines: [
          "[ralph] opening implementation branch spec/northstar-relaunch",
          "[ralph] writing project shell components",
          "[ralph] updating issues search behavior",
          "[ralph] streaming stdout to operator view",
          "[ralph] resizing split workspace support enabled",
          "[ralph] hover sidebar trigger patched",
          "[ralph] contrast review complete",
          "[ralph] build verification scheduled",
          "[ralph] waiting for next user instruction",
          "[ralph] task complete",
        ],
      },
    ],
  },
};

export function getProjectDetail(projectId: string): ProjectDetail {
  return initialProjectDetailsById[projectId] ?? initialProjectDetailsById["northstar-web"];
}

export const projects = initialProjects;

export function createInitialProjectCollection(): ProjectCollection {
  return {
    projects: initialProjects.map(project => ({ ...project })),
    projectDetailsById: Object.fromEntries(
      Object.entries(initialProjectDetailsById).map(([projectId, detail]) => [
        projectId,
        {
          ...detail,
          chat: detail.chat.map(entry => ({ ...entry })),
          issues: detail.issues.map(issue => ({ ...issue })),
          stdoutTasks: detail.stdoutTasks.map(task => ({ ...task, lines: [...task.lines] })),
        },
      ]),
    ),
  };
}
