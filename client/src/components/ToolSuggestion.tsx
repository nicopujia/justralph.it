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

  return (
    <div className="border border-[#FFaa00]/50 bg-[#FFaa00]/5 font-mono mx-2 mb-2">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#FFaa00]/30">
        <span className="text-[10px] tracking-wider text-[#FFaa00]">
          [Tool: {label}]
        </span>
        <span className="text-[10px] text-muted-foreground">
          {result.mode === "edit" ? "SUGGESTION" : "INJECT"}
        </span>
      </div>

      {/* Content */}
      <div className="px-3 py-2 max-h-40 overflow-y-auto">
        <pre className="text-xs text-foreground whitespace-pre-wrap break-words leading-relaxed">
          {result.text}
        </pre>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-t border-[#FFaa00]/30">
        <button
          onClick={() => onUse(result.text)}
          className="text-[10px] tracking-wider px-2 py-0.5 border border-primary text-primary hover:bg-primary/10 transition-colors"
        >
          USE
        </button>
        <button
          onClick={() => onEdit(result.text)}
          className="text-[10px] tracking-wider px-2 py-0.5 border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors"
        >
          EDIT
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
