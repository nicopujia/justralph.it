import { useState, useCallback, useEffect, useRef } from "react";
import { useEventReducer } from "@/hooks/useEventReducer";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useChatbot } from "@/hooks/useChatbot";
import { useBranching } from "@/hooks/useBranching";
import { useToast } from "./Toast";
import { useSoundNotification } from "@/hooks/useSoundNotification";
import { API_URL, WS_URL } from "@/lib/config";
import { ChatPanel } from "./ChatPanel";
import { TaskPreview, type PreviewTask } from "./TaskPreview";
import { StatusBar } from "./StatusBar";
import { LoopStateBar } from "./LoopStateBar";
import { AgentOutput } from "./AgentOutput";
import { HelpPanel } from "./HelpPanel";
import { RightPanel } from "./RightPanel";
import { SessionSidebar, type SessionEntry } from "./SessionSidebar";
import { SessionTitle } from "./SessionTitle";
import { MessageCircle, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Terminal, GripVertical } from "lucide-react";
import type { Theme } from "@/hooks/useTheme";

const PANEL_STORAGE_KEY = "ralph_panel_width";
const PANEL_MIN = 200;
const PANEL_MAX = 500;
const PANEL_DEFAULT = 280;

function useResizablePanel() {
  const [width, setWidth] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(PANEL_STORAGE_KEY);
      if (stored) {
        const val = Number(stored);
        if (val >= PANEL_MIN && val <= PANEL_MAX) return val;
      }
    } catch { /* ignore */ }
    return PANEL_DEFAULT;
  });
  const dragging = useRef(false);
  const startX = useRef(0);
  const startW = useRef(0);

  useEffect(() => {
    try { localStorage.setItem(PANEL_STORAGE_KEY, String(width)); } catch { /* ignore */ }
  }, [width]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = width;

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      // Dragging left increases panel width (panel is on the right)
      const delta = startX.current - ev.clientX;
      const next = Math.min(PANEL_MAX, Math.max(PANEL_MIN, startW.current + delta));
      setWidth(next);
    };
    const onMouseUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [width]);

  return { width, onMouseDown };
}

type Phase = "chat" | "preview" | "loop";

type DashboardUser = {
  login: string;
  name: string;
  avatar_url: string;
};

type DashboardProps = {
  theme?: Theme;
  onThemeToggle?: () => void;
  onLogout?: () => void;
  /** Authenticated GitHub user; undefined when skipped. */
  user?: DashboardUser;
};

export function Dashboard({ theme, onThemeToggle, onLogout, user }: DashboardProps) {
  const [phase, setPhase] = useState<Phase>("chat");
  const chatbot = useChatbot();
  const branching = useBranching(chatbot.state.sessionId, chatbot.state.messages);
  // Loading state for non-main branch sends (main branch uses chatbot.state.loading).
  const [branchLoading, setBranchLoading] = useState(false);

  // Derived chat state: swap in active branch messages + snapshot state when not on main branch.
  const displayState = branching.isMainBranch
    ? chatbot.state
    : {
        ...chatbot.state,
        messages: branching.activeMessages,
        loading: branchLoading,
        // Restore the branch's snapshotted scoring state instead of showing main's
        ...(branching.activeBranchSnapshot && {
          confidence: branching.activeBranchSnapshot.confidence,
          relevance: branching.activeBranchSnapshot.relevance,
          weightedReadiness: branching.activeBranchSnapshot.weightedReadiness,
          questionCount: branching.activeBranchSnapshot.questionCount,
          phase: branching.activeBranchSnapshot.phase,
          ready: branching.activeBranchSnapshot.ready,
        }),
      };

  /**
   * Send handler that is branch-aware:
   * - On main branch: delegates to chatbot.sendMessage (normal flow).
   * - On a non-main branch: appends optimistically, calls API directly,
   *   stores result in branch without touching main chatbot state.
   */
  const handleBranchSend = useCallback(async (message: string) => {
    if (branching.isMainBranch) {
      chatbot.sendMessage(message);
      return;
    }
    // Append user message to branch immediately
    const userMsg = { role: "user" as const, content: message, timestamp: Date.now(), status: "sent" as const };
    const withUser = [...branching.activeMessages, userMsg];
    branching.setActiveBranchMessages(withUser);
    setBranchLoading(true);

    const sessionId = chatbot.state.sessionId;
    if (!sessionId) { setBranchLoading(false); return; }
    try {
      const resp = await fetch(`${API_URL}/api/sessions/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const assistantMsg = { role: "assistant" as const, content: data.message, timestamp: Date.now() };
      branching.setActiveBranchMessages([...withUser, assistantMsg]);
      // Update branch snapshot with latest scoring from this response
      if (data.confidence) {
        branching.updateActiveBranchSnapshot({
          confidence: data.confidence,
          relevance: data.relevance ?? branching.activeBranchSnapshot?.relevance ?? chatbot.state.relevance,
          weightedReadiness: data.weighted_readiness ?? 0,
          questionCount: data.question_count ?? 0,
          phase: data.phase ?? 1,
          ready: data.ready ?? false,
        });
      }
    } catch {
      // leave branch with just user message on error
    } finally {
      setBranchLoading(false);
    }
  }, [branching, chatbot.sendMessage, chatbot.state.sessionId]);

  const handleBranchFrom = useCallback((msgIndex: number) => {
    // Snapshot scoring state at fork point so it can be restored on branch switch
    const snapshot = {
      confidence: chatbot.state.confidence,
      relevance: chatbot.state.relevance,
      weightedReadiness: chatbot.state.weightedReadiness,
      questionCount: chatbot.state.questionCount,
      phase: chatbot.state.phase,
      ready: chatbot.state.ready,
    };
    branching.branchFrom(chatbot.state.messages, msgIndex, snapshot);
  }, [branching, chatbot.state]);

  const [loopState, dispatch] = useEventReducer();
  const [helpTaskId, setHelpTaskId] = useState<string | null>(null);
  // Sidebar starts collapsed in loop phase
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Terminal starts collapsed -- Code tab is primary
  const [terminalOpen, setTerminalOpen] = useState(false);
  // Resizable right panel
  const rightPanel = useResizablePanel();
  // Mobile: which panel is visible when stacked
  const [mobileTab, setMobileTab] = useState<"main" | "right">("main");
  // Separate loading flag for the ralph-it transition
  const [ralphItLoading, setRalphItLoading] = useState(false);
  const { toast } = useToast();
  const sound = useSoundNotification();

  /** Rewind: fork a new branch from the given message index and switch to it. */
  const handleRewind = useCallback((msgIndex: number) => {
    branching.branchFrom(chatbot.state.messages, msgIndex);
    toast("Rewound to message -- new branch created", "info");
  }, [branching, chatbot.state.messages, toast]);
  // User-visible session name; updated optimistically on rename
  const [sessionName, setSessionName] = useState("");

  // Sound: play when Ralphy finishes responding (loading -> false, new assistant msg).
  const prevLoadingRef = useRef(chatbot.state.loading);
  const prevMsgCountRef = useRef(chatbot.state.messages.length);
  useEffect(() => {
    const wasLoading = prevLoadingRef.current;
    const prevCount = prevMsgCountRef.current;
    prevLoadingRef.current = chatbot.state.loading;
    prevMsgCountRef.current = chatbot.state.messages.length;
    if (
      wasLoading &&
      !chatbot.state.loading &&
      chatbot.state.messages.length > prevCount
    ) {
      sound.playResponseDone();
    }
  }, [chatbot.state.loading, chatbot.state.messages.length, sound]);

  // Sound: play when ready state first becomes true.
  const prevReadyRef = useRef(chatbot.state.ready);
  useEffect(() => {
    if (!prevReadyRef.current && chatbot.state.ready) {
      sound.playReadyToRalph();
    }
    prevReadyRef.current = chatbot.state.ready;
  }, [chatbot.state.ready, sound]);

  // Fetch session name when sessionId is set or changes (e.g., after loadSession).
  useEffect(() => {
    const sid = chatbot.state.sessionId;
    if (!sid) return;
    fetch(`${API_URL}/api/sessions/${sid}`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setSessionName(d.name ?? ""); })
      .catch(() => {});
  }, [chatbot.state.sessionId]);

  const wsUrl = chatbot.state.sessionId
    ? `${WS_URL}/ws/${chatbot.state.sessionId}`
    : null;

  const { state: wsState } = useWebSocket(wsUrl, (event) => {
    dispatch(event);
    if (event.type === "task_help" && event.data?.task_id) {
      setHelpTaskId(event.data.task_id);
    }
  });

  // Direct ralph-it (used from the sidebar in loop phase, or as fallback)
  const handleRalphIt = useCallback(async (tasksOverride?: PreviewTask[]) => {
    setRalphItLoading(true);
    const result = await chatbot.ralphIt(tasksOverride);
    setRalphItLoading(false);
    if (result?.status === "ralph_it_started") {
      setPhase("loop");
    }
    // errors are surfaced via chatbot.state.error -> ChatPanel -> toast
  }, [chatbot]);

  // Transition to preview phase when user clicks "Review Tasks"
  const handleReviewTasks = useCallback(() => {
    setPhase("preview");
  }, []);

  // Called from TaskPreview "Confirm & Start" with possibly edited tasks
  const handleConfirmTasks = useCallback(async (editedTasks: PreviewTask[]) => {
    await handleRalphIt(editedTasks);
  }, [handleRalphIt]);

  // Switch to a past session: restore its ID and history, reset loop state.
  const handleSelectSession = useCallback((session: SessionEntry) => {
    chatbot.loadSession(session.id);
    // Reset loop state so stale events from previous session don't linger
    dispatch({ type: "reset", timestamp: Date.now(), data: {} });
    setPhase("chat");
  }, [chatbot, dispatch]);

  // Delete a session from the sidebar; reset state if it was the active session.
  const handleDeleteSession = useCallback((deletedId: string) => {
    if (deletedId === chatbot.state.sessionId) {
      chatbot.deleteSession(deletedId);
      dispatch({ type: "reset", timestamp: Date.now(), data: {} });
      setPhase("chat");
    }
  }, [chatbot, dispatch]);

  // Dimension click -> send a focused chat message and open sidebar
  const handleDimensionClick = useCallback((dim: string) => {
    const labels: Record<string, string> = {
      functional: "functional requirements and features",
      technical_stack: "technical stack (language, framework, libraries)",
      data_model: "data model (entities, relationships, storage)",
      auth: "authentication and authorization",
      deployment: "deployment and infrastructure",
      testing: "testing strategy",
      edge_cases: "edge cases and error handling",
    };
    const score = (chatbot.state.confidence as Record<string, number>)[dim] ?? 0;
    chatbot.sendMessage(
      `What additional details can I provide about ${labels[dim] ?? dim}? Current coverage: ${score}%.`
    );
    setSidebarOpen(true);
  }, [chatbot]);

  // Phase 1: full-screen chat with history sidebar on far left
  if (phase === "chat") {
    return (
      <div className="h-screen flex overflow-hidden">
        <SessionSidebar
          activeSessionId={chatbot.state.sessionId}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
        />
        <div className="flex-1 overflow-hidden">
          <ChatPanel
            state={displayState}
            onSend={handleBranchSend}
            onRalphIt={handleRalphIt}
            onReviewTasks={handleReviewTasks}
            onClearError={chatbot.clearError}
            onUndo={branching.isMainBranch ? chatbot.undoLastMessage : undefined}
            onClearChat={chatbot.clearChat}
            ralphItLoading={ralphItLoading}
            mode="full"
            theme={theme}
            onThemeToggle={onThemeToggle}
            onLogout={onLogout}
            user={user}
            soundEnabled={sound.enabled}
            onSoundToggle={sound.toggle}
            onRunTool={chatbot.runTool}
            onClearToolResult={chatbot.clearToolResult}
            onRetry={chatbot.retryMessage}
            branches={branching.branches}
            activeBranchId={branching.activeBranchId}
            onBranchFrom={handleBranchFrom}
            onBranchSwitch={branching.switchBranch}
            onRewind={handleRewind}
            loopActive={false}
            onNewChat={chatbot.newChat}
            wsStatus={wsState}
            onDimensionClick={handleDimensionClick}
          />
        </div>
      </div>
    );
  }

  // Phase 2: task preview/edit with history sidebar on far left
  if (phase === "preview") {
    return (
      <div className="h-screen flex overflow-hidden">
        <SessionSidebar
          activeSessionId={chatbot.state.sessionId}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
        />
        <div className="flex-1 overflow-hidden">
          <TaskPreview
            tasks={(chatbot.state.tasks as PreviewTask[] | null) ?? []}
            project={chatbot.state.project}
            onConfirm={handleConfirmTasks}
            onBack={() => setPhase("chat")}
            loading={ralphItLoading}
          />
        </div>
      </div>
    );
  }

  // Phase 3: loop view with collapsible chat sidebar
  const sessionId = chatbot.state.sessionId!;

  return (
    <div className="h-screen flex flex-col bg-background grid-bg overflow-hidden">
      {/* System status strip: session/model/token info */}
      <div className="flex items-center gap-4 px-4 py-1 border-b border-border bg-background font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        <span className="flex items-center gap-1">
          SESSION:{" "}
          <SessionTitle
            sessionId={sessionId}
            name={sessionName}
            onRename={setSessionName}
          />
        </span>
        <span>MODEL: <span className="text-primary">kimi-k2.5</span></span>
        <span>TOKENS: <span className="text-primary">{loopState.totalTokens?.toLocaleString() ?? "0"}</span></span>
      </div>

      {/* Loop state / heartbeat indicator strip */}
      <LoopStateBar
        loopState={loopState.loopState}
        currentTaskId={loopState.currentTaskId}
        currentTaskElapsed={loopState.currentTaskElapsed}
        taskCounts={loopState.taskCounts}
        lastHeartbeatAt={loopState.lastHeartbeatAt}
        loopElapsedSeconds={loopState.loopElapsedSeconds}
        loopStartTime={loopState.loopStartTime}
        blockedTaskIds={loopState.blockedTaskIds}
        sessionId={sessionId}
        onError={(msg) => toast(msg, "error")}
      />

      {/* Status bar */}
      <StatusBar
        loopStatus={loopState.loopStatus}
        iterationCount={loopState.iterationCount}
        loopStartTime={loopState.loopStartTime}
        wsState={wsState}
        sessionId={sessionId}
        onError={(msg) => toast(msg, "error")}
        taskCount={loopState.tasks.size}
        theme={theme}
        onThemeToggle={onThemeToggle}
        onLogout={onLogout}
        soundEnabled={sound.enabled}
        onSoundToggle={sound.toggle}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Session history sidebar -- leftmost */}
        <SessionSidebar
          activeSessionId={sessionId}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
        />

        {/* Collapsible chat sidebar */}
        <div
          className="flex flex-col bg-card border-r border-border shrink-0 overflow-hidden transition-all duration-200"
          style={{ width: sidebarOpen ? 350 : 60 }}
        >
          {sidebarOpen ? (
            <>
              <div className="flex-1 overflow-hidden">
                <ChatPanel
                  state={chatbot.state}
                  onSend={chatbot.sendMessage}
                  onRalphIt={handleRalphIt}
                  onReviewTasks={handleReviewTasks}
                  onClearError={chatbot.clearError}
                  onUndo={chatbot.undoLastMessage}
                  onClearChat={chatbot.clearChat}
                  ralphItLoading={ralphItLoading}
                  mode="sidebar"
                  user={user}
                  onRunTool={chatbot.runTool}
                  onClearToolResult={chatbot.clearToolResult}
                  onRetry={chatbot.retryMessage}
                  onRewind={handleRewind}
                  loopActive={loopState.loopStatus === "running"}
                  onNewChat={chatbot.newChat}
                  wsStatus={wsState}
                />
              </div>
              {/* Collapse toggle at bottom */}
              <button
                className="w-full border-t border-border h-9 flex items-center justify-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:text-primary hover:border-primary transition-colors shrink-0"
                onClick={() => setSidebarOpen(false)}
              >
                <ChevronLeft className="size-3.5" />
                Collapse
              </button>
            </>
          ) : (
            /* Collapsed: icon-only strip */
            <div className="flex flex-col items-center py-3 gap-3">
              <button
                className="p-2 border border-border hover:border-primary text-muted-foreground hover:text-primary transition-colors"
                title="Open chat"
                onClick={() => setSidebarOpen(true)}
              >
                <MessageCircle className="size-4" />
              </button>
              <span
                className="text-[10px] text-muted-foreground uppercase tracking-widest select-none"
                style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
              >
                CHAT
              </span>
              <button
                className="p-1 mt-auto border border-border hover:border-primary text-muted-foreground hover:text-primary transition-colors"
                title="Expand chat"
                onClick={() => setSidebarOpen(true)}
              >
                <ChevronRight className="size-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Main area: center content + right panel */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden min-w-0">
          {/* Mobile tab switcher (visible below md) */}
          <div className="flex md:hidden border-b border-border shrink-0">
            <button
              onClick={() => setMobileTab("main")}
              className={`flex-1 py-2 text-xs font-mono uppercase tracking-wider transition-colors ${
                mobileTab === "main"
                  ? "border-b-2 border-primary text-primary"
                  : "text-muted-foreground"
              }`}
            >
              Terminal
            </button>
            <button
              onClick={() => setMobileTab("right")}
              className={`flex-1 py-2 text-xs font-mono uppercase tracking-wider transition-colors ${
                mobileTab === "right"
                  ? "border-b-2 border-primary text-primary"
                  : "text-muted-foreground"
              }`}
            >
              Panel
            </button>
          </div>

          {/* Center: collapsible terminal drawer + help panel */}
          <div className={`flex-1 flex flex-col gap-0 overflow-hidden border-r border-border ${
            mobileTab !== "main" ? "hidden md:flex" : "flex"
          }`}>
            {/* Main content area (fills remaining space) */}
            <div className="flex-1 overflow-hidden" />

            {/* Help panel when a task needs help */}
            {helpTaskId && (
              <HelpPanel
                sessionId={sessionId}
                taskId={helpTaskId}
                onResume={() => setHelpTaskId(null)}
                onError={(msg) => toast(msg, "error")}
              />
            )}

            {/* Collapsible terminal drawer */}
            <div className="flex flex-col shrink-0 border-t border-border">
              <button
                onClick={() => setTerminalOpen(!terminalOpen)}
                className="flex items-center gap-2 px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-primary transition-colors bg-black/50"
              >
                <Terminal className="size-3" />
                <span>TERMINAL OUTPUT</span>
                <span className="text-primary ml-1">{loopState.agentOutputLines.length}</span>
                {terminalOpen
                  ? <ChevronDown className="size-3 ml-auto" />
                  : <ChevronUp className="size-3 ml-auto" />}
              </button>
              {terminalOpen && (
                <div className="h-[300px] overflow-hidden">
                  <AgentOutput lines={loopState.agentOutputLines} />
                </div>
              )}
            </div>
          </div>

          {/* Drag handle (hidden on mobile) */}
          <div
            className="hidden md:flex w-1 shrink-0 cursor-col-resize items-center justify-center hover:bg-primary/20 active:bg-primary/30 transition-colors group"
            onMouseDown={rightPanel.onMouseDown}
          >
            <GripVertical className="size-3 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>

          {/* Right: tabbed confidence + tasks + code (with live diffs) */}
          <div
            className={`shrink-0 overflow-hidden ${
              mobileTab !== "right" ? "hidden md:block" : "block"
            }`}
            style={{ width: mobileTab === "right" ? "100%" : rightPanel.width }}
          >
            <RightPanel
              chatState={chatbot.state}
              tasks={loopState.tasks}
              taskDiffs={loopState.taskDiffs}
              loopStarted={phase === "loop"}
              sessionId={sessionId}
              githubUrl={loopState.githubUrl}
              onDimensionClick={handleDimensionClick}
              onRunTool={chatbot.runTool}
              onClearToolResult={chatbot.clearToolResult}
              onTaskUpdate={(taskId, patch) => {
                if (patch.status === "open") {
                  dispatch({ type: "task_reset", timestamp: Date.now(), data: { task_id: taskId } });
                }
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
