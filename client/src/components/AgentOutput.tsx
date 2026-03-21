import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ArrowDown, Moon, Sun, Terminal } from "lucide-react";

type AgentOutputProps = {
  lines: string[];
};

// Terminal theme: stored in localStorage, falls back to system preference.
function getInitialTheme(): "dark" | "light" {
  const stored = localStorage.getItem("terminal-theme");
  if (stored === "dark" || stored === "light") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

// Classify a line into a semantic color token.
type LineToken =
  | "default"
  | "filepath"
  | "addition"
  | "removal"
  | "status"
  | "error"
  | "commit";

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

// Map token to Tailwind class set for each theme.
const TOKEN_CLASSES: Record<LineToken, { dark: string; light: string }> = {
  default: {
    dark: "text-emerald-400 terminal-glow",
    light: "text-gray-800",
  },
  filepath: {
    dark: "text-cyan-400",
    light: "text-blue-600",
  },
  addition: {
    dark: "text-emerald-400 terminal-glow",
    light: "text-green-700",
  },
  removal: {
    dark: "text-red-400",
    light: "text-red-600",
  },
  status: {
    dark: "text-yellow-400",
    light: "text-amber-600",
  },
  error: {
    dark: "text-red-400",
    light: "text-red-600",
  },
  commit: {
    dark: "text-blue-400",
    light: "text-blue-600",
  },
};

export function AgentOutput({ lines }: AgentOutputProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<"dark" | "light">(getInitialTheme);
  // True while the user has manually scrolled away from the bottom.
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

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      localStorage.setItem("terminal-theme", next);
      return next;
    });
  }, []);

  const isDark = theme === "dark";

  return (
    <Card className="flex flex-col overflow-hidden h-full">
      {/* Header */}
      <CardHeader className="flex-row items-center justify-between pb-0 px-4 py-2 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Terminal className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold tracking-tight">Terminal</span>
          {lines.length > 0 && (
            <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
              {lines.length}
            </span>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggleTheme}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? (
            <Sun className="size-4" />
          ) : (
            <Moon className="size-4" />
          )}
        </Button>
      </CardHeader>

      {/* Body */}
      <CardContent className="flex-1 overflow-hidden p-0 relative">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className={[
            "h-full overflow-y-auto font-mono text-sm p-4 terminal-scroll",
            isDark
              ? "bg-[#0a0e14] text-emerald-400"
              : "bg-gray-50 text-gray-800",
          ].join(" ")}
        >
          {lines.length === 0 ? (
            <span
              className={
                isDark ? "text-zinc-500" : "text-gray-400"
              }
            >
              Waiting for agent output
              <span className="animate-pulse">_</span>
            </span>
          ) : (
            lines.map((line, i) => {
              const token = classifyLine(line);
              const classes = TOKEN_CLASSES[token][theme];
              return (
                <div
                  key={i}
                  className={`whitespace-pre-wrap leading-relaxed ${classes}`}
                >
                  {line || "\u00A0" /* keep blank lines visible */}
                </div>
              );
            })
          )}
        </div>

        {/* Scroll-to-bottom button, shown when user scrolled away */}
        {showScrollBtn && (
          <Button
            variant="secondary"
            size="icon-sm"
            onClick={() => scrollToBottom(true)}
            aria-label="Scroll to bottom"
            className={[
              "absolute bottom-3 right-5 shadow-md opacity-90 hover:opacity-100 transition-opacity",
              isDark ? "bg-zinc-700 hover:bg-zinc-600 text-zinc-100" : "",
            ].join(" ")}
          >
            <ArrowDown className="size-4" />
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
