import { useReducer } from "react";

export type RalphEvent = {
  type: string;
  timestamp: number;
  data: Record<string, any>;
};

export type TaskInfo = {
  id: string;
  title: string;
  status: "open" | "in_progress" | "blocked" | "done" | "help";
  error?: string;
  pushed?: boolean;
  pushError?: string;
};

export type TaskDiffEntry = {
  taskId: string;
  diff: string;
  timestamp: number;
};

export type GitPushInfo = {
  taskId: string;
  success: boolean;
  remoteUrl?: string;
  commitSha?: string;
  error?: string;
  timestamp: number;
};

export type LoopStateValue =
  | "idle"
  | "processing_task"
  | "waiting_for_tasks"
  | "stalled"
  | "stopped"
  | "unknown";

export type TaskCounts = {
  open: number;
  in_progress: number;
  blocked: number;
  done: number;
  help: number;
};

export type DashboardState = {
  loopStatus: "stopped" | "running" | "waiting" | "unknown";
  iterationCount: number;
  loopStartTime: number | null;
  tasks: Map<string, TaskInfo>;
  agentOutputLines: string[];
  resources: { cpu: number; ram: number; disk: number } | null;
  totalTokens: number;
  // Heartbeat / progress fields
  loopState: LoopStateValue;
  taskCounts: TaskCounts | null;
  lastHeartbeatAt: number | null;
  currentTaskId: string | null;
  currentTaskElapsed: number | null;
  currentTaskOutputLines: number | null;
  blockedTaskIds: string[];
  loopElapsedSeconds: number | null;
  // diff + git push tracking
  taskDiffs: Map<string, TaskDiffEntry>;
  gitPushes: GitPushInfo[];
  githubUrl: string | null;
};

const MAX_OUTPUT_LINES = 1000;

const initialState: DashboardState = {
  loopStatus: "unknown",
  iterationCount: 0,
  loopStartTime: null,
  tasks: new Map(),
  agentOutputLines: [],
  resources: null,
  totalTokens: 0,
  loopState: "unknown",
  taskCounts: null,
  lastHeartbeatAt: null,
  currentTaskId: null,
  currentTaskElapsed: null,
  currentTaskOutputLines: null,
  blockedTaskIds: [],
  loopElapsedSeconds: null,
  taskDiffs: new Map(),
  gitPushes: [],
  githubUrl: null,
};

function reducer(state: DashboardState, event: RalphEvent): DashboardState {
  switch (event.type) {
    // Synthetic: reset all loop state when switching sessions.
    case "reset":
      return { ...initialState };

    case "loop_started":
      return {
        ...state,
        loopStatus: "running",
        loopState: "idle",
        loopStartTime: event.timestamp,
        blockedTaskIds: [],
      };

    case "loop_stopped":
      return { ...state, loopStatus: "stopped", loopState: "stopped" };

    case "loop_waiting":
      return { ...state, loopStatus: "waiting", loopState: "waiting_for_tasks" };

    case "iter_started":
      return {
        ...state,
        iterationCount: state.iterationCount + 1,
      };

    case "agent_output": {
      const lines = [...state.agentOutputLines, event.data.line];
      // Cap at MAX_OUTPUT_LINES, drop oldest
      if (lines.length > MAX_OUTPUT_LINES) {
        lines.splice(0, lines.length - MAX_OUTPUT_LINES);
      }
      return { ...state, agentOutputLines: lines };
    }

    case "task_claimed": {
      const tasks = new Map(state.tasks);
      tasks.set(event.data.task_id, {
        id: event.data.task_id,
        title: event.data.title ?? event.data.task_id,
        status: "in_progress",
      });
      return {
        ...state,
        tasks,
        loopState: "processing_task",
        currentTaskId: event.data.task_id,
        currentTaskElapsed: 0,
        currentTaskOutputLines: 0,
      };
    }

    case "task_done": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, {
          ...existing,
          status: "done",
          pushed: event.data.pushed ?? false,
        });
      }
      return { ...state, tasks };
    }

    case "task_blocked": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, { ...existing, status: "blocked" });
      }
      return { ...state, tasks };
    }

    case "task_help": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, { ...existing, status: "help", error: event.data.error });
      }
      return { ...state, tasks };
    }

    // Synthetic event dispatched after a successful retry to reset local state.
    case "task_reset": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, { ...existing, status: "open", error: undefined });
      }
      return { ...state, tasks };
    }

    case "resource_check":
      return {
        ...state,
        resources: {
          cpu: event.data.cpu,
          ram: event.data.ram,
          disk: event.data.disk,
        },
      };

    case "iter_completed": {
      // Accumulate tokens if provided with the event
      const tokens = event.data.tokens ?? 0;
      return { ...state, totalTokens: state.totalTokens + tokens };
    }

    case "iter_failed":
      return state;

    case "agent_status": {
      const lines = [...state.agentOutputLines, `[STATUS] ${event.data.status}`];
      if (lines.length > MAX_OUTPUT_LINES) {
        lines.splice(0, lines.length - MAX_OUTPUT_LINES);
      }
      return { ...state, agentOutputLines: lines };
    }

    case "tag_created": {
      const lines = [...state.agentOutputLines, `[TAG] ${event.data.tag}`];
      if (lines.length > MAX_OUTPUT_LINES) {
        lines.splice(0, lines.length - MAX_OUTPUT_LINES);
      }
      return { ...state, agentOutputLines: lines };
    }

    case "rollback": {
      const lines = [...state.agentOutputLines, `[ROLLBACK] ${event.data.tag}`];
      if (lines.length > MAX_OUTPUT_LINES) {
        lines.splice(0, lines.length - MAX_OUTPUT_LINES);
      }
      return { ...state, agentOutputLines: lines };
    }

    case "validation_failed": {
      const lines = [
        ...state.agentOutputLines,
        `[VALIDATION FAILED] ${event.data.reason}`,
      ];
      if (lines.length > MAX_OUTPUT_LINES) {
        lines.splice(0, lines.length - MAX_OUTPUT_LINES);
      }
      return { ...state, agentOutputLines: lines };
    }

    case "task_diff": {
      const diffs = new Map(state.taskDiffs);
      diffs.set(event.data.task_id, {
        taskId: event.data.task_id,
        diff: event.data.diff ?? "",
        timestamp: event.timestamp,
      });
      return { ...state, taskDiffs: diffs };
    }

    case "git_push_success": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, { ...existing, pushed: true });
      }
      return {
        ...state,
        tasks,
        githubUrl: event.data.remote_url ?? state.githubUrl,
        gitPushes: [...state.gitPushes, {
          taskId: event.data.task_id,
          success: true,
          remoteUrl: event.data.remote_url,
          commitSha: event.data.commit_sha,
          timestamp: event.timestamp,
        }],
      };
    }

    case "git_push_failed": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, { ...existing, pushed: false, pushError: event.data.error });
      }
      return {
        ...state,
        tasks,
        gitPushes: [...state.gitPushes, {
          taskId: event.data.task_id,
          success: false,
          error: event.data.error,
          timestamp: event.timestamp,
        }],
      };
    }

    case "loop_heartbeat":
      return {
        ...state,
        loopState: (event.data.loop_state as LoopStateValue) ?? state.loopState,
        taskCounts: event.data.task_counts ?? state.taskCounts,
        lastHeartbeatAt: event.timestamp,
        loopElapsedSeconds: event.data.elapsed_seconds ?? state.loopElapsedSeconds,
      };

    case "task_progress":
      return {
        ...state,
        currentTaskId: event.data.task_id ?? state.currentTaskId,
        currentTaskElapsed: event.data.elapsed_seconds ?? state.currentTaskElapsed,
        currentTaskOutputLines: event.data.output_line_count ?? state.currentTaskOutputLines,
        loopState: (event.data.loop_state as LoopStateValue) ?? state.loopState,
        lastHeartbeatAt: event.timestamp,
      };

    case "loop_stalled":
      return {
        ...state,
        loopState: "stalled",
        blockedTaskIds: Array.isArray(event.data.blocked_task_ids)
          ? event.data.blocked_task_ids
          : state.blockedTaskIds,
        lastHeartbeatAt: event.timestamp,
      };

    case "task_created": {
      const tasks = new Map(state.tasks);
      tasks.set(event.data.task_id, {
        id: event.data.task_id,
        title: event.data.title ?? event.data.task_id,
        status: event.data.status ?? "open",
      });
      return { ...state, tasks };
    }

    case "task_updated": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, {
          ...existing,
          ...(event.data.status && { status: event.data.status }),
          ...(event.data.title && { title: event.data.title }),
        });
      }
      return { ...state, tasks };
    }

    case "task_deleted": {
      const tasks = new Map(state.tasks);
      tasks.delete(event.data.task_id);
      return { ...state, tasks };
    }

    default:
      return state;
  }
}

export function useEventReducer() {
  return useReducer(reducer, initialState);
}
