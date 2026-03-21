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
};

export type DashboardState = {
  loopStatus: "stopped" | "running" | "waiting" | "unknown";
  iterationCount: number;
  loopStartTime: number | null;
  tasks: Map<string, TaskInfo>;
  agentOutputLines: string[];
  resources: { cpu: number; ram: number; disk: number } | null;
};

const MAX_OUTPUT_LINES = 1000;

const initialState: DashboardState = {
  loopStatus: "unknown",
  iterationCount: 0,
  loopStartTime: null,
  tasks: new Map(),
  agentOutputLines: [],
  resources: null,
};

function reducer(state: DashboardState, event: RalphEvent): DashboardState {
  switch (event.type) {
    case "loop_started":
      return {
        ...state,
        loopStatus: "running",
        loopStartTime: event.timestamp,
      };

    case "loop_stopped":
      return { ...state, loopStatus: "stopped" };

    case "loop_waiting":
      return { ...state, loopStatus: "waiting" };

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
      return { ...state, tasks };
    }

    case "task_done": {
      const tasks = new Map(state.tasks);
      const existing = tasks.get(event.data.task_id);
      if (existing) {
        tasks.set(event.data.task_id, { ...existing, status: "done" });
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

    case "iter_completed":
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

    default:
      return state;
  }
}

export function useEventReducer() {
  return useReducer(reducer, initialState);
}
