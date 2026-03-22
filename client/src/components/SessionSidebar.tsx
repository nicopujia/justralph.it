import { useState, useEffect, useCallback, useMemo } from "react";
import { History, ChevronLeft, ChevronRight, RefreshCw, Trash2, Copy, Search } from "lucide-react";
import { API_URL } from "@/lib/config";

export type SessionEntry = {
  id: string;
  name?: string;
  status: string;
  created_at: number;
  last_activity?: number;
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

/** Relative time label, e.g. "2m ago", "3h ago", "5d ago". */
function relativeTime(epochSeconds: number): string {
  const diff = Math.floor(Date.now() / 1000 - epochSeconds);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

type StatusFilter = "all" | "running" | "ready" | "stopped" | "done" | "crashed" | "needs_help";

export function SessionSidebar({ activeSessionId, onSelectSession, onDeleteSession }: SessionSidebarProps) {
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [duplicating, setDuplicating] = useState<string | null>(null);

  // Search & filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/api/sessions`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: SessionEntry[] = await resp.json();
      setSessions(data.sort((a, b) => (b.last_activity ?? b.created_at) - (a.last_activity ?? a.created_at)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchSessions();
  }, [open, fetchSessions]);

  // Filtered + searched sessions
  const filteredSessions = useMemo(() => {
    let result = sessions;
    if (statusFilter !== "all") {
      result = result.filter((s) => {
        const effective = s.running ? "running" : s.status;
        return effective === statusFilter;
      });
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((s) =>
        (s.name?.toLowerCase().includes(q)) ||
        s.id.toLowerCase().includes(q) ||
        s.github_url?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [sessions, statusFilter, searchQuery]);

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

  const handleDuplicate = useCallback(async (sessionId: string) => {
    setDuplicating(sessionId);
    try {
      const resp = await fetch(`${API_URL}/api/sessions/${sessionId}/duplicate`, { method: "POST" });
      if (resp.ok) {
        await fetchSessions();
      }
    } finally {
      setDuplicating(null);
    }
  }, [fetchSessions]);

  // Status filter options (only show statuses that exist)
  const availableStatuses = useMemo(() => {
    const set = new Set<string>();
    for (const s of sessions) {
      set.add(s.running ? "running" : s.status);
    }
    return Array.from(set).sort();
  }, [sessions]);

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
              {sessions.length > 0 && (
                <span className="text-primary ml-1">{sessions.length}</span>
              )}
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

          {/* Search bar */}
          <div className="px-2 py-1.5 border-b border-border shrink-0">
            <div className="flex items-center gap-1 px-1.5 py-1 border border-border bg-background">
              <Search className="size-3 text-muted-foreground shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search..."
                className="text-[10px] font-mono bg-transparent outline-none text-foreground placeholder:text-muted-foreground w-full"
              />
            </div>
            {/* Status filter pills */}
            {availableStatuses.length > 1 && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                <button
                  onClick={() => setStatusFilter("all")}
                  className={`px-1.5 py-0.5 text-[8px] font-mono uppercase tracking-wider transition-colors ${
                    statusFilter === "all"
                      ? "border border-primary text-primary bg-primary/5"
                      : "border border-border text-muted-foreground hover:text-primary"
                  }`}
                >
                  all
                </button>
                {availableStatuses.map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s as StatusFilter)}
                    className={`px-1.5 py-0.5 text-[8px] font-mono uppercase tracking-wider transition-colors ${
                      statusFilter === s
                        ? "border border-primary text-primary bg-primary/5"
                        : "border border-border text-muted-foreground hover:text-primary"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Session list */}
          <div className="flex-1 overflow-y-auto relative">
            {error && (
              <p className="text-[10px] text-red-400 uppercase tracking-wider px-3 py-2">
                {error}
              </p>
            )}
            {!error && filteredSessions.length === 0 && !loading && (
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider px-3 py-4 text-center">
                {searchQuery || statusFilter !== "all" ? "NO MATCHES" : "NO SESSIONS"}
              </p>
            )}
            {filteredSessions.map((s) => {
              const isActive = s.id === activeSessionId;
              const displayName = s.name || s.id.slice(0, 8);
              const lastAct = s.last_activity ?? s.created_at;
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
                    className="w-full text-left px-3 py-2.5 pr-14"
                  >
                    {/* Session name / ID */}
                    <p className={`text-[11px] font-mono font-bold truncate ${isActive ? "text-primary" : "text-foreground"}`}>
                      {displayName}
                    </p>
                    {/* Status + last activity */}
                    <div className="flex items-center justify-between mt-0.5 gap-1">
                      <StatusBadge status={s.status} running={s.running} />
                      <span className="text-[9px] text-muted-foreground truncate" title={formatDate(lastAct)}>
                        {relativeTime(lastAct)}
                      </span>
                    </div>
                    {/* GitHub URL if present */}
                    {s.github_url && (
                      <p className="text-[9px] text-muted-foreground truncate mt-0.5">
                        {s.github_url.replace("https://github.com/", "")}
                      </p>
                    )}
                  </button>
                  {/* Action buttons: visible on hover */}
                  <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-all">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDuplicate(s.id); }}
                      title="Duplicate session"
                      aria-label="Duplicate session"
                      disabled={duplicating === s.id}
                      className="p-1 text-muted-foreground hover:text-primary transition-colors disabled:opacity-40"
                    >
                      <Copy className={`size-3 ${duplicating === s.id ? "animate-spin" : ""}`} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setPendingDelete(s.id); }}
                      title="Delete session"
                      aria-label="Delete session"
                      className="p-1 text-muted-foreground hover:text-destructive transition-colors"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
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
