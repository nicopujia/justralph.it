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
import { AgentOutput } from "./AgentOutput";
import { HelpPanel } from "./HelpPanel";
import { RightPanel } from "./RightPanel";
import { SessionSidebar, type SessionEntry } from "./SessionSidebar";
import { SessionTitle } from "./SessionTitle";
import { MessageCircle, ChevronLeft, ChevronRight } from "lucide-react";
import type { Theme } from "@/hooks/useTheme";

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

  // Derived chat state: swap in active branch messages + loading when not on main branch.
  const displayState = branching.isMainBranch
    ? chatbot.state
    : { ...chatbot.state, messages: branching.activeMessages, loading: branchLoading };

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
    } catch {
      // leave branch with just user message on error
    } finally {
      setBranchLoading(false);
    }
  }, [branching, chatbot.sendMessage, chatbot.state.sessionId]);

  const handleBranchFrom = useCallback((msgIndex: number) => {
    branching.branchFrom(chatbot.state.messages, msgIndex);
  }, [branching, chatbot.state.messages]);

  const [loopState, dispatch] = useEventReducer();
  const [helpTaskId, setHelpTaskId] = useState<string | null>(null);
  // Sidebar starts collapsed in loop phase
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Separate loading flag for the ralph-it transition
  const [ralphItLoading, setRalphItLoading] = useState(false);
  const { toast } = useToast();
  const sound = useSoundNotification();
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
    chatbot.sendMessage(`Let's talk more about ${labels[dim] ?? dim}.`);
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

        {/* Main area: agent output + right panel -- borders separate panels, no gaps */}
        <div className="flex-1 grid grid-cols-[1fr_280px] gap-0 overflow-hidden min-w-0">
          {/* Center: agent output + optional help panel */}
          <div className="flex flex-col gap-0 overflow-hidden border-r border-border">
            <AgentOutput lines={loopState.agentOutputLines} />
            {helpTaskId && (
              <HelpPanel
                sessionId={sessionId}
                taskId={helpTaskId}
                onResume={() => setHelpTaskId(null)}
                onError={(msg) => toast(msg, "error")}
              />
            )}
          </div>

          {/* Right: tabbed confidence + tasks + code */}
          <RightPanel
            chatState={chatbot.state}
            tasks={loopState.tasks}
            loopStarted={phase === "loop"}
            sessionId={sessionId}
            onDimensionClick={handleDimensionClick}
            onTaskUpdate={(taskId, patch) => {
              if (patch.status === "open") {
                dispatch({ type: "task_reset", timestamp: Date.now(), data: { task_id: taskId } });
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}
