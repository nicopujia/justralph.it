import { useState, useEffect } from "react";
import type { ChatState, ToolName } from "@/hooks/useChatbot";

type ToolDef = {
  id: ToolName;
  label: string;
  description: string;
  icon: string;
};

const TOOLS: ToolDef[] = [
  {
    id: "brainstorm",
    label: "BRAINSTORM",
    description: "Generate creative feature angles targeting weak dimensions.",
    icon: "[*]",
  },
  {
    id: "expand",
    label: "EXPAND",
    description: "Flesh out use cases, personas, and data flows.",
    icon: "[+]",
  },
  {
    id: "refine",
    label: "REFINE",
    description: "Rewrite your last message for maximum clarity.",
    icon: "[~]",
  },
  {
    id: "architect",
    label: "ARCHITECT",
    description: "Suggest architecture based on known requirements.",
    icon: "[#]",
  },
];

function getToolGating(state: ChatState) {
  const totalChars = state.messages
    .filter((m) => m.role === "user")
    .reduce((sum, m) => sum + m.content.length, 0);
  return {
    brainstorm: totalChars >= 120,
    expand: totalChars >= 120,
    refine: state.questionCount >= 1,
    architect: state.phase >= 2,
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
};

export function ToolsetPanel({
  state,
  onRunTool,
  toolLoading,
  activeTool,
}: ToolsetPanelProps) {
  const gating = getToolGating(state);
  const weakDims = getWeakDims(state);
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

  return (
    <div className="space-y-3 font-mono">
      <div className="flex items-center justify-between text-xs tracking-wider">
        <span className="text-muted-foreground uppercase">TOOLSET</span>
        <span className="text-muted-foreground text-[10px]">
          {weakDims ? `WEAK: ${weakDims}` : "NO DATA YET"}
        </span>
      </div>

      <div className="h-px bg-border" />

      {TOOLS.map((tool) => {
        const enabled = gating[tool.id];
        const isRunning = toolLoading && activeTool === tool.id;
        const isDisabled = !enabled || (toolLoading && !isRunning);

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
                  ? "border-border hover:border-primary hover:bg-primary/5 cursor-pointer"
                  : "border-border/50 opacity-40 cursor-not-allowed"
            }`}
          >
            <div className="flex items-center justify-between text-xs tracking-wider">
              <span className="flex items-center gap-2">
                <span className="text-primary">{tool.icon}</span>
                <span>{tool.label}</span>
              </span>
              <span
                className={`text-[10px] ${
                  isRunning
                    ? "text-primary"
                    : enabled
                      ? "text-[#00FF41]"
                      : "text-muted-foreground"
                }`}
              >
                {isRunning
                  ? `RUNNING... ${elapsed}s`
                  : enabled
                    ? "[READY]"
                    : "[LOCKED]"}
              </span>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5 leading-relaxed">
              {tool.description}
            </p>
            {!enabled && (
              <p className="text-[10px] text-muted-foreground/60 mt-1">
                {getGateReason(tool.id, state)}
              </p>
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
        </div>
      )}
    </div>
  );
}
