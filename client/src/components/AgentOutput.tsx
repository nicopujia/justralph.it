import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";

type AgentOutputProps = {
  lines: string[];
};

// Classify a line into a semantic color token.
type LineToken = "default" | "filepath" | "addition" | "removal" | "status" | "error" | "commit";

function classifyLine(line: string): LineToken {
  const trimmed = line.trimStart();
  if (/^(modified:|created:|deleted:)/.test(trimmed)) return "filepath";
  if (trimmed.startsWith("+")) return "addition";
  if (trimmed.startsWith("-")) return "removal";
  if (/\[(STATUS|TAG|ROLLBACK)\]/.test(line)) return "status";
  if (/error/i.test(line)) return "error";
  if (/\bcommit\b/i.test(line)) return "commit";
  return "default";
}

// Single terminal color set -- always dark, no dark: variants needed.
const TOKEN_CLASSES: Record<LineToken, string> = {
  default: "text-[#00FF41] terminal-glow",
  filepath: "text-[#00ccff]",
  addition: "text-[#00FF41]",
  removal: "text-[#FF0033]",
  status: "text-[#FFaa00]",
  error: "text-[#FF0033]",
  commit: "text-[#6699ff]",
};

export function AgentOutput({ lines }: AgentOutputProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  // Track whether auto-scroll should fire (suppressed while user scrolls up).
  const atBottomRef = useRef(true);

  const scrollToBottom = useCallback((smooth = false) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    atBottomRef.current = true;
    setShowScrollBtn(false);
  }, []);

  // Auto-scroll only when user is already at the bottom.
  useEffect(() => {
    if (atBottomRef.current) {
      scrollToBottom(false);
    }
  }, [lines.length, scrollToBottom]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    // 32px threshold -- a little slack so minor rounding doesn't hide the btn.
    const isAtBottom = distFromBottom < 32;
    atBottomRef.current = isAtBottom;
    setShowScrollBtn(!isAtBottom);
  }, []);

  return (
    <div className="flex flex-col overflow-hidden h-full border border-[#1a1a1a] bg-black">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1a1a1a] bg-[#0a0a0a] px-4 py-2 shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-[#00FF41] text-xs uppercase tracking-wider font-mono">TERMINAL</span>
          {lines.length > 0 && (
            <span className="text-[#333] text-xs font-mono">[{lines.length}]</span>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden relative">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto font-mono text-sm p-4 terminal-scroll bg-black scanline-overlay grid-bg"
        >
          {lines.length === 0 ? (
            <span className="text-[#333]">
              AWAITING INPUT<span className="animate-blink">_</span>
            </span>
          ) : (
            lines.map((line, i) => {
              const token = classifyLine(line);
              return (
                <div
                  key={i}
                  className={`whitespace-pre-wrap leading-relaxed ${TOKEN_CLASSES[token]}`}
                >
                  <span className="text-[#333] select-none mr-3">{String(i + 1).padStart(4, " ")}</span>
                  {line || "\u00A0" /* keep blank lines visible */}
                </div>
              );
            })
          )}
        </div>

        {/* Scroll-to-bottom button, shown when user scrolled away */}
        {showScrollBtn && (
          <button
            onClick={() => scrollToBottom(true)}
            aria-label="Scroll to bottom"
            className="absolute bottom-3 right-5 border border-[#00FF41] bg-black text-[#00FF41] hover:bg-[#00FF41] hover:text-black transition-colors p-1"
          >
            <ArrowDown className="size-4" />
          </button>
        )}
      </div>
    </div>
  );
}
