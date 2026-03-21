import { useState, useEffect } from "react";
import type { ToolResult } from "@/hooks/useChatbot";

const TOOL_LABELS: Record<string, string> = {
  brainstorm: "BRAINSTORM",
  expand: "EXPAND",
  refine: "REFINE",
  architect: "ARCHITECT",
};

type ToolSuggestionProps = {
  result: ToolResult;
  onUse: (text: string) => void;
  onEdit: (text: string) => void;
  onDismiss: () => void;
};

export function ToolSuggestion({
  result,
  onUse,
  onEdit,
  onDismiss,
}: ToolSuggestionProps) {
  const label = TOOL_LABELS[result.tool] ?? result.tool.toUpperCase();
  const [expanded, setExpanded] = useState(false);
  const isLong = result.content.length > 300;
  const accentColor = result.mode === "inject" ? "var(--color-terminal-text)" : "var(--color-warning)";

  // Escape key dismisses the suggestion
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onDismiss]);

  return (
    <div
      className="border font-mono mx-2 mb-2"
      style={{
        borderColor: `color-mix(in srgb, ${accentColor} 50%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${accentColor} 5%, transparent)`,
      }}
      role="status"
      aria-live="polite"
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-1.5 border-b"
        style={{ borderColor: `${accentColor}30` }}
      >
        <div className="flex items-center gap-1">
          <span className="text-[10px] tracking-wider" style={{ color: accentColor }}>
            [Tool: {label}]
          </span>
          {result.elapsed_ms && (
            <span className="text-[10px] text-muted-foreground/50 ml-1">
              {(result.elapsed_ms / 1000).toFixed(1)}s
            </span>
          )}
          <span className="text-[10px] text-muted-foreground/50 ml-2">
            {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground">
          {result.mode === "edit" ? "SUGGESTION" : "INJECT"}
        </span>
      </div>

      {/* Content */}
      <div className={`px-3 py-2 overflow-y-auto ${expanded ? "max-h-[60vh]" : "max-h-40"}`}>
        <pre className="text-xs text-foreground whitespace-pre-wrap break-words leading-relaxed">
          {result.content}
        </pre>
      </div>

      {/* Expand/collapse toggle */}
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full text-[10px] text-muted-foreground hover:text-primary py-0.5 border-t transition-colors"
          style={{ borderColor: `${accentColor}20` }}
        >
          {expanded ? "SHOW LESS" : "SHOW MORE"}
        </button>
      )}

      {/* Actions */}
      <div
        className="flex items-center gap-2 px-3 py-1.5 border-t"
        style={{ borderColor: `${accentColor}30` }}
      >
        <button
          onClick={() => onUse(result.content)}
          className="text-[10px] tracking-wider px-2 py-0.5 border border-primary text-primary hover:bg-primary/10 transition-colors"
        >
          {result.mode === "inject" ? "SEND" : "USE"}
        </button>
        <button
          onClick={() => onEdit(result.content)}
          className="text-[10px] tracking-wider px-2 py-0.5 border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors"
        >
          EDIT
        </button>
        <button
          onClick={async () => {
            try { await navigator.clipboard.writeText(result.content); } catch {}
          }}
          className="text-[10px] tracking-wider px-2 py-0.5 border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors"
        >
          COPY
        </button>
        <button
          onClick={onDismiss}
          className="text-[10px] tracking-wider px-2 py-0.5 border border-border text-muted-foreground hover:border-destructive hover:text-destructive transition-colors ml-auto"
        >
          DISMISS
        </button>
      </div>
    </div>
  );
}
