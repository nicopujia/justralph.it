import { useEffect, useState, useCallback } from "react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { AlertTriangle } from "lucide-react";
import type { LoopStateValue, TaskCounts } from "@/hooks/useEventReducer";
import { API_URL } from "@/lib/config";

type LoopStateBarProps = {
  loopState: LoopStateValue;
  currentTaskId: string | null;
  currentTaskElapsed: number | null;
  taskCounts: TaskCounts | null;
  lastHeartbeatAt: number | null;
  loopElapsedSeconds: number | null;
  loopStartTime: number | null;
  blockedTaskIds: string[];
  sessionId?: string;
  onError?: (msg: string) => void;
};

const DOT_CONFIG: Record<LoopStateValue, { cls: string; label: string }> = {
  processing_task: { cls: "bg-[var(--color-success)] animate-pulse-dot", label: "PROCESSING" },
  waiting_for_tasks: { cls: "bg-[var(--color-warning)] animate-pulse", label: "WAITING FOR TASKS" },
  stalled: { cls: "bg-[var(--color-error)] animate-pulse", label: "STALLED" },
  idle: { cls: "bg-zinc-500", label: "IDLE" },
  stopped: { cls: "bg-zinc-600", label: "STOPPED" },
  unknown: { cls: "bg-zinc-600", label: "IDLE" },
};

function useNow(intervalMs: number) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function fmtSeconds(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

async function forceStop(sessionId: string, onError?: (m: string) => void) {
  try {
    const resp = await fetch(`${API_URL}/api/sessions/${sessionId}/stop`, { method: "POST" });
    if (!resp.ok) onError?.("Force stop failed");
  } catch {
    onError?.("Force stop failed");
  }
}

// How many seconds since last heartbeat before we warn.
const HEARTBEAT_WARN_AFTER = 10;
// Stall timeout before overlay appears.
const STALL_OVERLAY_AFTER = 60;

export function LoopStateBar({
  loopState,
  currentTaskId,
  currentTaskElapsed,
  taskCounts,
  lastHeartbeatAt,
  loopElapsedSeconds,
  loopStartTime,
  blockedTaskIds,
  sessionId,
  onError,
}: LoopStateBarProps) {
  const now = useNow(1000);
  const [overlayDismissed, setOverlayDismissed] = useState(false);

  // Reset dismissed state whenever stall clears.
  useEffect(() => {
    if (loopState !== "stalled") setOverlayDismissed(false);
  }, [loopState]);

  const handleForceStop = useCallback(async () => {
    if (sessionId) await forceStop(sessionId, onError);
    setOverlayDismissed(true);
  }, [sessionId, onError]);

  const dot = DOT_CONFIG[loopState] ?? DOT_CONFIG.unknown;

  // Elapsed loop time: prefer server-reported, fallback to local calc from loopStartTime.
  const elapsedSec =
    loopElapsedSeconds != null
      ? loopElapsedSeconds
      : loopStartTime != null
        ? Math.floor((now - loopStartTime) / 1000)
        : null;

  // Seconds since last heartbeat.
  const secSinceHeartbeat =
    lastHeartbeatAt != null ? Math.floor((now - lastHeartbeatAt) / 1000) : null;
  const heartbeatStale =
    secSinceHeartbeat != null && secSinceHeartbeat > HEARTBEAT_WARN_AFTER;

  // Stall overlay: visible when stalled > STALL_OVERLAY_AFTER seconds with no fresh heartbeat.
  const stallSeconds =
    loopState === "stalled" && lastHeartbeatAt != null
      ? Math.floor((now - lastHeartbeatAt) / 1000)
      : 0;
  const showOverlay =
    loopState === "stalled" &&
    stallSeconds > STALL_OVERLAY_AFTER &&
    !overlayDismissed;

  // Build center label.
  let centerLabel: string;
  if (loopState === "processing_task" && currentTaskId) {
    centerLabel = `PROCESSING ${currentTaskId.toUpperCase()}`;
  } else if (loopState === "stalled") {
    centerLabel = `STALLED - ${blockedTaskIds.length} TASK${blockedTaskIds.length !== 1 ? "S" : ""} BLOCKED`;
  } else {
    centerLabel = dot.label;
  }

  // Don't render bar at all in idle/stopped/unknown with no history.
  if (
    loopState === "unknown" &&
    lastHeartbeatAt == null &&
    loopStartTime == null
  ) {
    return null;
  }

  return (
    <>
      {/* Indicator strip */}
      <div className="flex items-center gap-3 px-4 py-1.5 border-b border-border bg-background font-mono text-[10px] uppercase tracking-widest text-muted-foreground shrink-0">
        {/* Pulsing state dot */}
        <span className={`w-2 h-2 rounded-full shrink-0 ${dot.cls}`} />

        {/* State label */}
        <span className={loopState === "stalled" ? "text-red-400" : loopState === "processing_task" ? "text-[var(--color-terminal-text)]" : "text-muted-foreground"}>
          {centerLabel}
        </span>

        {/* Task elapsed when processing */}
        {loopState === "processing_task" && currentTaskElapsed != null && (
          <>
            <span className="text-muted-foreground">|</span>
            <span className="text-primary">{fmtSeconds(currentTaskElapsed)}</span>
          </>
        )}

        {/* Task counts summary */}
        {taskCounts != null && (
          <>
            <span className="text-muted-foreground">|</span>
            <span>
              <span className="text-muted-foreground">DONE:</span>
              <span className="text-[var(--color-success)] ml-0.5">{taskCounts.done}</span>
              <span className="text-muted-foreground ml-2">OPEN:</span>
              <span className="text-foreground ml-0.5">{taskCounts.open}</span>
              {taskCounts.blocked > 0 && (
                <>
                  <span className="text-muted-foreground ml-2">BLOCKED:</span>
                  <span className="text-red-400 ml-0.5">{taskCounts.blocked}</span>
                </>
              )}
            </span>
          </>
        )}

        {/* Loop elapsed */}
        {elapsedSec != null && elapsedSec > 0 && (
          <>
            <span className="text-muted-foreground">|</span>
            <span>
              <span className="text-muted-foreground">ELAPSED:</span>
              <span className="text-foreground ml-0.5">{fmtSeconds(elapsedSec)}</span>
            </span>
          </>
        )}

        {/* Last heartbeat */}
        {secSinceHeartbeat != null && (
          <>
            <span className="text-muted-foreground">|</span>
            <span className={heartbeatStale ? "text-yellow-400" : "text-muted-foreground"}>
              LAST SEEN {secSinceHeartbeat}s AGO
            </span>
          </>
        )}

        {/* Stalled: inline blocked IDs */}
        {loopState === "stalled" && blockedTaskIds.length > 0 && (
          <>
            <span className="text-muted-foreground">|</span>
            <span className="text-red-400">
              {blockedTaskIds.map((id) => id.toUpperCase()).join(", ")}
            </span>
            {sessionId && (
              <button
                onClick={() => forceStop(sessionId, onError)}
                className="ml-2 px-2 py-0.5 border border-red-500 text-red-400 hover:bg-red-500 hover:text-black transition-colors text-[10px]"
              >
                FORCE STOP
              </button>
            )}
          </>
        )}
      </div>

      {/* Stall overlay (> 60s stalled, no heartbeat) */}
      <AlertDialog.Root open={showOverlay}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm" />
          <AlertDialog.Content className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[440px] bg-card border border-red-500 p-6 font-mono shadow-2xl shadow-red-900/40">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="size-5 text-red-400 shrink-0" />
              <AlertDialog.Title className="text-red-400 text-sm uppercase tracking-widest">
                Loop Stalled
              </AlertDialog.Title>
            </div>

            <AlertDialog.Description className="text-muted-foreground text-xs mb-3">
              The loop has been stalled for over {STALL_OVERLAY_AFTER}s with no heartbeat.
              {blockedTaskIds.length > 0 && (
                <> Blocked tasks: <span className="text-red-400">{blockedTaskIds.join(", ")}</span>.</>
              )}
            </AlertDialog.Description>

            <div className="flex items-center gap-3 mt-5">
              <AlertDialog.Action asChild>
                <button
                  onClick={handleForceStop}
                  className="flex-1 py-2 border border-red-500 text-red-400 hover:bg-red-500 hover:text-black transition-colors text-xs uppercase tracking-wider"
                >
                  Force Stop
                </button>
              </AlertDialog.Action>
              <AlertDialog.Cancel asChild>
                <button
                  onClick={() => setOverlayDismissed(true)}
                  className="flex-1 py-2 border border-border text-muted-foreground hover:text-foreground hover:border-foreground transition-colors text-xs uppercase tracking-wider"
                >
                  Dismiss
                </button>
              </AlertDialog.Cancel>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </>
  );
}
