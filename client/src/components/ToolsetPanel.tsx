import { useState, useEffect, useMemo, useRef } from "react";
import { Lightbulb, Maximize2, Pencil, Network, ListChecks } from "lucide-react";
import type { ChatState, ToolName } from "@/hooks/useChatbot";

type ToolDef = {
  id: ToolName;
  label: string;
  description: string;
  icon: React.ReactNode;
};

const TOOLS: ToolDef[] = [
  {
    id: "brainstorm",
    label: "BRAINSTORM",
    description: "Generate creative feature angles targeting weak dimensions.",
    icon: <Lightbulb className="size-3.5" />,
  },
  {
    id: "expand",
    label: "EXPAND",
    description: "Flesh out use cases, personas, and data flows.",
    icon: <Maximize2 className="size-3.5" />,
  },
  {
    id: "refine",
    label: "REFINE",
    description: "Rewrite your last message for maximum clarity.",
    icon: <Pencil className="size-3.5" />,
  },
  {
    id: "architect",
    label: "ARCHITECT",
    description: "Suggest architecture based on known requirements.",
    icon: <Network className="size-3.5" />,
  },
  {
    id: "modify",
    label: "MODIFY TASKS",
    description: "Suggest task additions, removals, or priority changes.",
    icon: <ListChecks className="size-3.5" />,
  },
];

const TOOL_MODES: Record<ToolName, "inject" | "edit"> = {
  brainstorm: "inject",
  expand: "inject",
  refine: "edit",
  architect: "inject",
  modify: "inject",
};

const TOOL_SHORTCUTS: Record<ToolName, string> = {
  brainstorm: "Ctrl+1",
  expand: "Ctrl+2",
  refine: "Ctrl+3",
  architect: "Ctrl+4",
  modify: "Ctrl+5",
};

function getToolGating(state: ChatState) {
  const totalChars = state.messages
    .filter((m) => m.role === "user")
    .reduce((sum, m) => sum + m.content.length, 0);
  return {
    brainstorm: totalChars >= 120,
    expand: totalChars >= 120,
    refine: state.questionCount >= 1,
    architect: state.phase >= 2,
    modify: state.questionCount >= 1,
  };
}

function getGateReason(tool: ToolName, state: ChatState): string {
  const totalChars = state.messages
    .filter((m) => m.role === "user")
    .reduce((sum, m) => sum + m.content.length, 0);
  switch (tool) {
    case "brainstorm":
    case "expand":
      return `Need ${Math.max(0, 120 - totalChars)} more chars`;
    case "refine":
    case "modify":
      return "Need 1+ message";
    case "architect":
      return `Need Phase 2+ (${Math.max(0, 4 - state.questionCount)} more msgs)`;
  }
}

function getWeakDims(state: ChatState): string {
  const dims = Object.entries(state.confidence) as [string, number][];
  const relevant = dims.filter(([k]) => {
    const rel = (state.relevance as Record<string, number>)[k] ?? 1.0;
    return rel > 0.3;
  });
  const weakest = relevant.sort((a, b) => a[1] - b[1]).slice(0, 3);
  return weakest.map(([d, v]) => `${d} (${v}%)`).join(", ");
}

type ToolsetPanelProps = {
  state: ChatState;
  onRunTool: (tool: ToolName, context?: string) => void;
  toolLoading: boolean;
  activeTool: string | null;
  onCancelTool?: () => void;
};

export function ToolsetPanel({
  state,
  onRunTool,
  toolLoading,
  activeTool,
  onCancelTool,
}: ToolsetPanelProps) {
  // Change 5: memoize gating and weakDims
  const gating = useMemo(
    () => getToolGating(state),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [state.messages, state.questionCount, state.phase],
  );
  const weakDims = useMemo(
    () => getWeakDims(state),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [state.confidence, state.relevance],
  );

  const [elapsed, setElapsed] = useState(0);

  // Elapsed timer for loading state
  useEffect(() => {
    if (!toolLoading) {
      setElapsed(0);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [toolLoading]);

  // Refine tool: optional freeform input
  const [refineInput, setRefineInput] = useState("");

  // Change 11: animate tool unlock
  const [prevGating, setPrevGating] = useState(gating);
  const [justUnlocked, setJustUnlocked] = useState<Set<ToolName>>(new Set());

  useEffect(() => {
    const newlyUnlocked = new Set<ToolName>();
    for (const tool of ["brainstorm", "expand", "refine", "architect", "modify"] as ToolName[]) {
      if (!prevGating[tool] && gating[tool]) {
        newlyUnlocked.add(tool);
      }
    }
    setPrevGating(gating);
    if (newlyUnlocked.size > 0) {
      setJustUnlocked(newlyUnlocked);
      const t = setTimeout(() => setJustUnlocked(new Set()), 1500);
      return () => clearTimeout(t);
    }
  }, [gating]);

  // Change 7: keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.shiftKey || e.altKey) return;
      const toolMap: Record<string, ToolName> = {
        "1": "brainstorm",
        "2": "expand",
        "3": "refine",
        "4": "architect",
        "5": "modify",
      };
      const tool = toolMap[e.key];
      if (tool && gating[tool] && !toolLoading && !state.loading) {
        e.preventDefault();
        if (tool === "refine" && refineInput.trim()) {
          onRunTool(tool, refineInput.trim());
        } else {
          onRunTool(tool);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [gating, toolLoading, state.loading, onRunTool, refineInput]);

  // Unused ref kept for future abort integration
  const _abortRef = useRef<(() => void) | null>(null);

  return (
    <div className="space-y-3 font-mono">
      <div className="space-y-1 text-xs tracking-wider">
        <span className="text-muted-foreground uppercase block">TOOLSET</span>
        <span className="text-muted-foreground text-[10px] block break-words leading-relaxed">
          {weakDims ? `WEAK: ${weakDims}` : "NO DATA YET"}
        </span>
      </div>

      <div className="h-px bg-border" />

      {TOOLS.map((tool) => {
        const enabled = gating[tool.id];
        const isRunning = toolLoading && activeTool === tool.id;
        // Change 6: also disable when state.loading
        const isDisabled = !enabled || (toolLoading && !isRunning) || state.loading;

        // Change 10: collapsed locked tools
        if (!enabled) {
          return (
            <div
              key={tool.id}
              className="w-full text-left border border-border/50 px-3 py-2 opacity-40"
            >
              <div className="flex items-center gap-2 text-xs tracking-wider">
                <span className="text-primary shrink-0">{tool.icon}</span>
                <span className="truncate">{tool.label}</span>
                <span className="text-[10px] text-muted-foreground ml-auto shrink-0 whitespace-nowrap">
                  [LOCKED]
                </span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5 pl-5">
                {getGateReason(tool.id, state)}
              </p>
            </div>
          );
        }

        return (
          <button
            key={tool.id}
            onClick={() => {
              if (tool.id === "refine" && refineInput.trim()) {
                onRunTool(tool.id, refineInput.trim());
              } else {
                onRunTool(tool.id);
              }
            }}
            disabled={isDisabled}
            className={`w-full text-left border p-3 transition-all ${
              isRunning
                ? "border-primary animate-pulse bg-primary/5"
                : enabled
                  ? `border-border hover:border-primary hover:bg-primary/5 cursor-pointer ${
                      justUnlocked.has(tool.id) ? "ring-1 ring-[var(--color-success)] border-[var(--color-success)]" : ""
                    }`
                  : "border-border/50 opacity-40 cursor-not-allowed"
            }`}
          >
            <div className="flex items-center gap-2 text-xs tracking-wider flex-wrap">
              <span className="text-primary shrink-0">{tool.icon}</span>
              <span className="shrink-0">{tool.label}</span>
              <span className="text-muted-foreground/40 text-[9px]">
                {TOOL_SHORTCUTS[tool.id]}
              </span>
              <span className="ml-auto flex items-center gap-1.5 shrink-0">
                <span
                  className={`text-[10px] ${
                    isRunning
                      ? "text-primary"
                      : enabled
                        ? "text-[var(--color-success)]"
                        : "text-muted-foreground"
                  }`}
                >
                  {isRunning
                    ? `RUNNING... ${elapsed}s`
                    : enabled
                      ? "[READY]"
                      : "[LOCKED]"}
                </span>
                <span
                  className={`text-[10px] ${
                    TOOL_MODES[tool.id] === "inject"
                      ? "text-[var(--color-terminal-text)]"
                      : "text-[var(--color-warning)]"
                  }`}
                >
                  {TOOL_MODES[tool.id] === "inject" ? "INJECT" : "EDIT"}
                </span>
              </span>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5 leading-relaxed">
              {tool.description}
            </p>
            {/* Change 4: slow-load warning */}
            {isRunning && elapsed > 15 && (
              <p className="text-[10px] text-[var(--color-warning)] mt-1 animate-pulse">
                THIS IS TAKING A WHILE...
              </p>
            )}
            {/* Change 12: cancel button */}
            {isRunning && onCancelTool && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCancelTool();
                }}
                className="text-[10px] text-destructive border border-destructive/50 px-1.5 py-0.5 hover:bg-destructive/10 transition-colors mt-1"
              >
                CANCEL
              </button>
            )}
          </button>
        );
      })}

      {/* Refine tool: optional freeform input */}
      {gating.refine && (
        <div className="space-y-1">
          <label className="text-[10px] text-muted-foreground tracking-wider">
            REFINE CUSTOM TEXT (OPTIONAL)
          </label>
          <textarea
            value={refineInput}
            onChange={(e) => setRefineInput(e.target.value)}
            placeholder="Paste text to refine, or leave empty to refine your last message..."
            className="w-full bg-background border border-border text-xs font-mono p-2 resize-none h-16 focus:outline-none focus:border-primary placeholder:text-muted-foreground/40"
            disabled={toolLoading}
          />
          {/* Change 3: preview of what will be refined */}
          {!refineInput.trim() && state.messages.length > 0 && (
            <p className="text-[10px] text-muted-foreground/60 italic truncate">
              Will refine: "
              {state.messages
                .filter((m) => m.role === "user")
                .pop()
                ?.content.slice(0, 60)}
              ..."
            </p>
          )}
          {/* Change 9: character count */}
          {refineInput.length > 0 && (
            <p className="text-[9px] text-muted-foreground/40 text-right">
              {refineInput.length} chars
            </p>
          )}
        </div>
      )}

      {/* Change 8: usage hint */}
      <p className="text-[10px] text-muted-foreground/40 text-center mt-2 leading-relaxed">
        TOOLS TARGET YOUR WEAKEST DIMENSIONS TO ACCELERATE READINESS.
      </p>
    </div>
  );
}
