import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import type { WSState } from "@/hooks/useWebSocket";
import { Play, Square, RotateCcw, Sun, Moon } from "lucide-react";
import { API_URL } from "@/lib/config";

type StatusBarProps = {
  loopStatus: "stopped" | "running" | "waiting" | "unknown";
  iterationCount: number;
  loopStartTime: number | null;
  wsState: WSState;
  sessionId?: string;
  onError?: (message: string) => void;
  /** Current theme, used to show correct icon. */
  theme?: "dark" | "light";
  /** Called to toggle the global theme. */
  onThemeToggle?: () => void;
};

const STATUS_CONFIG = {
  running: { color: "bg-[#00FF41] animate-pulse-dot", label: "RUNNING" },
  waiting: { color: "bg-[#FFaa00]", label: "WAITING" },
  stopped: { color: "bg-[#FF0033]", label: "STOPPED" },
  unknown: { color: "bg-[#333]", label: "UNKNOWN" },
} as const;

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

/** Pad iteration count to 3 digits. */
function fmtIter(n: number): string {
  return String(n).padStart(3, "0");
}

async function loopAction(
  action: "start" | "stop" | "restart",
  sessionId?: string,
  onError?: (msg: string) => void,
) {
  if (!sessionId) return;
  const base = `${API_URL}/api/sessions/${sessionId}`;
  try {
    const resp = await fetch(`${base}/${action}`, { method: "POST" });
    if (!resp.ok) onError?.("Action failed");
  } catch {
    onError?.("Action failed");
  }
}

export function StatusBar({
  loopStatus,
  iterationCount,
  loopStartTime,
  wsState,
  sessionId,
  onError,
  theme,
  onThemeToggle,
}: StatusBarProps) {
  const [uptime, setUptime] = useState(0);

  useEffect(() => {
    if (!loopStartTime || loopStatus !== "running") {
      setUptime(0);
      return;
    }
    setUptime(Math.floor(Date.now() / 1000 - loopStartTime));
    const interval = setInterval(() => {
      setUptime(Math.floor(Date.now() / 1000 - loopStartTime));
    }, 1000);
    return () => clearInterval(interval);
  }, [loopStartTime, loopStatus]);

  const status = STATUS_CONFIG[loopStatus];
  const wsConnected = wsState === "connected";

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-[#1a1a1a] bg-[#0a0a0a] font-mono text-xs uppercase tracking-wider">
      {/* Left: loop status */}
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 ${status.color}`} />
        <span className="text-white">{status.label}</span>
      </div>

      {/* Center: iteration + uptime */}
      <div className="flex items-center gap-3">
        <span>
          <span className="text-[#333]">ITER:</span>
          <span className="text-white">#{fmtIter(iterationCount)}</span>
        </span>
        {loopStatus === "running" && loopStartTime && (
          <>
            <span className="text-[#333]">|</span>
            <span className="text-[#00FF41]">{formatUptime(uptime)}</span>
          </>
        )}
      </div>

      {/* Right: ws status + theme toggle + controls */}
      <div className="flex items-center gap-3">
        {wsConnected ? (
          <span className="text-[#00FF41]">WS:OK</span>
        ) : (
          <span className="text-[#FF0033]">WS:OFF</span>
        )}

        <span className="text-[#333]">|</span>

        {/* Theme toggle */}
        {onThemeToggle && (
          <button
            onClick={onThemeToggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="p-1 border border-[#333] hover:border-[#00FF41] text-white hover:text-[#00FF41] transition-colors"
          >
            {theme === "dark" ? <Sun className="size-3" /> : <Moon className="size-3" />}
          </button>
        )}

        <span className="text-[#333]">|</span>

        {/* Loop controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => loopAction("start", sessionId, onError)}
            title="Start loop"
            className="p-1 border border-[#333] hover:border-[#00FF41] text-white hover:text-[#00FF41] transition-colors"
          >
            <Play className="size-3" />
          </button>
          <button
            onClick={() => loopAction("stop", sessionId, onError)}
            title="Stop loop"
            className="p-1 border border-[#333] hover:border-[#00FF41] text-white hover:text-[#00FF41] transition-colors"
          >
            <Square className="size-3" />
          </button>
          <button
            onClick={() => loopAction("restart", sessionId, onError)}
            title="Restart loop"
            className="p-1 border border-[#333] hover:border-[#00FF41] text-white hover:text-[#00FF41] transition-colors"
          >
            <RotateCcw className="size-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
