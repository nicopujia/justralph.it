import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { WSState } from "@/hooks/useWebSocket";
import { Activity, Play, Square, RotateCcw, Wifi, WifiOff } from "lucide-react";

type StatusBarProps = {
  loopStatus: "stopped" | "running" | "waiting" | "unknown";
  iterationCount: number;
  loopStartTime: number | null;
  wsState: WSState;
  sessionId?: string;
};

const STATUS_CONFIG = {
  running: { color: "bg-green-500", label: "Running" },
  waiting: { color: "bg-yellow-500", label: "Waiting" },
  stopped: { color: "bg-red-500", label: "Stopped" },
  unknown: { color: "bg-gray-500", label: "Unknown" },
} as const;

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

import { API_URL } from "@/lib/config";

async function loopAction(action: "start" | "stop" | "restart", sessionId?: string) {
  if (!sessionId) return; // no session, no action
  const base = `${API_URL}/api/sessions/${sessionId}`;
  try {
    await fetch(`${base}/${action}`, { method: "POST" });
  } catch {
    // silently ignore network errors
  }
}

export function StatusBar({
  loopStatus,
  iterationCount,
  loopStartTime,
  wsState,
  sessionId,
}: StatusBarProps) {
  const [uptime, setUptime] = useState(0);

  useEffect(() => {
    if (!loopStartTime || loopStatus !== "running") {
      setUptime(0);
      return;
    }
    // Compute initial uptime from the timestamp
    setUptime(Math.floor(Date.now() / 1000 - loopStartTime));
    const interval = setInterval(() => {
      setUptime(Math.floor(Date.now() / 1000 - loopStartTime));
    }, 1000);
    return () => clearInterval(interval);
  }, [loopStartTime, loopStatus]);

  const status = STATUS_CONFIG[loopStatus];
  const wsConnected = wsState === "connected";

  return (
    <Card className="flex-row items-center justify-between px-4 py-3 rounded-none border-x-0 border-t-0 gap-4">
      {/* Left: loop status */}
      <div className="flex items-center gap-2">
        <Activity className="size-4 text-muted-foreground" />
        <span className={`size-2.5 rounded-full ${status.color}`} />
        <span className="text-sm font-medium">{status.label}</span>
      </div>

      {/* Center: iteration + uptime */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>
          Iteration <span className="font-mono font-semibold text-foreground">#{iterationCount}</span>
        </span>
        {loopStatus === "running" && loopStartTime && (
          <span className="font-mono">{formatUptime(uptime)}</span>
        )}
      </div>

      {/* Right: ws status + controls */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-sm">
          {wsConnected ? (
            <>
              <Wifi className="size-3.5 text-green-500" />
              <span className="text-green-600 dark:text-green-400">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="size-3.5 text-red-500" />
              <span className="text-red-600 dark:text-red-400">Disconnected</span>
            </>
          )}
        </div>

        <div className="h-5 w-px bg-border" />

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => loopAction("start", sessionId)}
            title="Start loop"
          >
            <Play className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => loopAction("stop", sessionId)}
            title="Stop loop"
          >
            <Square className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => loopAction("restart", sessionId)}
            title="Restart loop"
          >
            <RotateCcw className="size-3.5" />
          </Button>
        </div>
      </div>
    </Card>
  );
}
