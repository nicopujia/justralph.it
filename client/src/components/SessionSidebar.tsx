import { useState, useEffect, useCallback } from "react";
import { History, ChevronLeft, ChevronRight, RefreshCw, Trash2 } from "lucide-react";
import { API_URL } from "@/lib/config";

export type SessionEntry = {
  id: string;
  status: string;
  created_at: number;
  github_url: string;
  running: boolean;
  iteration_count: number;
};

type SessionSidebarProps = {
  /** Currently active session ID -- highlighted in list. */
  activeSessionId: string | null;
  /** Called when user clicks a session entry. */
  onSelectSession: (session: SessionEntry) => void;
  /** Called after a session is deleted. Receives the deleted session ID. */
  onDeleteSession?: (id: string) => void;
};

/** Map session status to a short colored label. */
function StatusBadge({ status, running }: { status: string; running: boolean }) {
  const effective = running ? "running" : status;
  const colors: Record<string, string> = {
    running: "text-green-400",
    ready: "text-primary",
    needs_help: "text-yellow-400",
    stopped: "text-muted-foreground",
    done: "text-muted-foreground",
    crashed: "text-red-400",
    initializing: "text-yellow-400",
  };
  return (
    <span className={`text-[9px] uppercase tracking-widest font-mono ${colors[effective] ?? "text-muted-foreground"}`}>
      {effective}
    </span>
  );
}

/** Format epoch seconds as locale date+time string, short form. */
function formatDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SessionSidebar({ activeSessionId, onSelectSession, onDeleteSession }: SessionSidebarProps) {
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** ID of session pending delete confirmation; null = no dialog open. */
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/api/sessions`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: SessionEntry[] = await resp.json();
      // Sort newest first
      setSessions(data.sort((a, b) => b.created_at - a.created_at));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch when sidebar opens
  useEffect(() => {
    if (open) fetchSessions();
  }, [open, fetchSessions]);

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await fetch(`${API_URL}/api/sessions/${pendingDelete}`, { method: "DELETE" });
      setSessions((prev) => prev.filter((s) => s.id !== pendingDelete));
      onDeleteSession?.(pendingDelete);
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  }, [pendingDelete, onDeleteSession]);

  return (
    <div
      className="relative flex flex-col bg-card border-r border-border shrink-0 overflow-hidden transition-all duration-200"
      style={{ width: open ? 240 : 44 }}
    >
      {open ? (
        <>
          {/* Header row */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-border shrink-0">
            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              SESSIONS
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={fetchSessions}
                disabled={loading}
                title="Refresh"
                className="text-muted-foreground hover:text-primary transition-colors disabled:opacity-40"
              >
                <RefreshCw className={`size-3 ${loading ? "animate-spin" : ""}`} />
              </button>
              <button
                onClick={() => setOpen(false)}
                title="Collapse"
                className="text-muted-foreground hover:text-primary transition-colors"
              >
                <ChevronLeft className="size-3.5" />
              </button>
            </div>
          </div>

          {/* Session list -- relative so the confirm overlay is scoped here */}
          <div className="flex-1 overflow-y-auto relative">
            {error && (
              <p className="text-[10px] text-red-400 uppercase tracking-wider px-3 py-2">
                {error}
              </p>
            )}
            {!error && sessions.length === 0 && !loading && (
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider px-3 py-4 text-center">
                NO SESSIONS
              </p>
            )}
            {sessions.map((s) => {
              const isActive = s.id === activeSessionId;
              return (
                <div
                  key={s.id}
                  className={[
                    "group relative border-b border-border transition-colors",
                    isActive
                      ? "bg-primary/10 border-l-2 border-l-primary"
                      : "hover:bg-muted/30",
                  ].join(" ")}
                >
                  <button
                    onClick={() => onSelectSession(s)}
                    className="w-full text-left px-3 py-2.5 pr-8"
                  >
                    {/* Session ID */}
                    <p className={`text-[11px] font-mono font-bold truncate ${isActive ? "text-primary" : "text-foreground"}`}>
                      {s.id.slice(0, 8)}
                    </p>
                    {/* Status + timestamp */}
                    <div className="flex items-center justify-between mt-0.5 gap-1">
                      <StatusBadge status={s.status} running={s.running} />
                      <span className="text-[9px] text-muted-foreground truncate">
                        {formatDate(s.created_at)}
                      </span>
                    </div>
                    {/* GitHub URL if present */}
                    {s.github_url && (
                      <p className="text-[9px] text-muted-foreground truncate mt-0.5">
                        {s.github_url.replace("https://github.com/", "")}
                      </p>
                    )}
                  </button>
                  {/* Delete button: visible on hover */}
                  <button
                    onClick={(e) => { e.stopPropagation(); setPendingDelete(s.id); }}
                    title="Delete session"
                    aria-label="Delete session"
                    className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 text-muted-foreground hover:text-destructive transition-all"
                  >
                    <Trash2 className="size-3" />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Confirmation dialog overlay */}
          {pendingDelete && (
            <div className="absolute inset-0 bg-background/80 backdrop-blur-[2px] flex items-center justify-center z-10">
              <div className="border-2 border-destructive bg-card p-4 mx-3 flex flex-col gap-3">
                <p className="text-[11px] font-mono uppercase tracking-wider text-foreground">
                  Delete session <span className="text-primary">{pendingDelete.slice(0, 8)}</span>?
                </p>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  This cannot be undone.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={confirmDelete}
                    disabled={deleting}
                    className="flex-1 border border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground text-[10px] uppercase tracking-wider py-1.5 transition-colors disabled:opacity-40"
                  >
                    {deleting ? "DELETING..." : "DELETE"}
                  </button>
                  <button
                    onClick={() => setPendingDelete(null)}
                    disabled={deleting}
                    className="flex-1 border border-border text-muted-foreground hover:text-foreground text-[10px] uppercase tracking-wider py-1.5 transition-colors disabled:opacity-40"
                  >
                    CANCEL
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        /* Collapsed: icon strip */
        <div className="flex flex-col items-center py-3 gap-3">
          <button
            onClick={() => setOpen(true)}
            title="Session history"
            className="p-2 border border-border hover:border-primary text-muted-foreground hover:text-primary transition-colors"
          >
            <History className="size-4" />
          </button>
          <span
            className="text-[10px] text-muted-foreground uppercase tracking-widest select-none"
            style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
          >
            HISTORY
          </span>
          <button
            onClick={() => setOpen(true)}
            title="Expand history"
            className="p-1 mt-auto border border-border hover:border-primary text-muted-foreground hover:text-primary transition-colors"
          >
            <ChevronRight className="size-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
