import { useState, useCallback } from "react";
import { useEventReducer } from "@/hooks/useEventReducer";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useChatbot } from "@/hooks/useChatbot";
import { useToast } from "./Toast";
import { WS_URL } from "@/lib/config";
import { ChatPanel } from "./ChatPanel";
import { TaskPreview, type PreviewTask } from "./TaskPreview";
import { StatusBar } from "./StatusBar";
import { AgentOutput } from "./AgentOutput";
import { HelpPanel } from "./HelpPanel";
import { RightPanel } from "./RightPanel";
import { MessageCircle, ChevronLeft, ChevronRight } from "lucide-react";
import type { Theme } from "@/hooks/useTheme";

type Phase = "chat" | "preview" | "loop";

type DashboardProps = {
  theme?: Theme;
  onThemeToggle?: () => void;
};

export function Dashboard({ theme, onThemeToggle }: DashboardProps) {
  const [phase, setPhase] = useState<Phase>("chat");
  const chatbot = useChatbot();
  const [loopState, dispatch] = useEventReducer();
  const [helpTaskId, setHelpTaskId] = useState<string | null>(null);
  // Sidebar starts collapsed in loop phase
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Separate loading flag for the ralph-it transition
  const [ralphItLoading, setRalphItLoading] = useState(false);
  const { toast } = useToast();

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

  // Phase 1: full-screen chat (two-column)
  if (phase === "chat") {
    return (
      <ChatPanel
        state={chatbot.state}
        onSend={chatbot.sendMessage}
        onRalphIt={handleRalphIt}
        onReviewTasks={handleReviewTasks}
        onClearError={chatbot.clearError}
        onUndo={chatbot.undoLastMessage}
        ralphItLoading={ralphItLoading}
        mode="full"
        theme={theme}
        onThemeToggle={onThemeToggle}
      />
    );
  }

  // Phase 2: task preview/edit before starting the loop
  if (phase === "preview") {
    return (
      <TaskPreview
        tasks={(chatbot.state.tasks as PreviewTask[] | null) ?? []}
        project={chatbot.state.project}
        onConfirm={handleConfirmTasks}
        onBack={() => setPhase("chat")}
        loading={ralphItLoading}
      />
    );
  }

  // Phase 3: loop view with collapsible chat sidebar
  const sessionId = chatbot.state.sessionId!;

  return (
    <div className="h-screen flex flex-col bg-black grid-bg overflow-hidden">
      {/* System status strip: session/model/token info */}
      <div className="flex items-center gap-4 px-4 py-1 border-b border-[#1a1a1a] bg-black font-mono text-[10px] uppercase tracking-widest text-[#333]">
        <span>SESSION: <span className="text-[#00FF41]">{sessionId.slice(0, 8)}</span></span>
        <span>MODEL: <span className="text-[#00FF41]">kimi-k2.5</span></span>
        <span>TOKENS: <span className="text-[#00FF41]">{loopState.totalTokens?.toLocaleString() ?? "0"}</span></span>
      </div>

      {/* Status bar */}
      <StatusBar
        loopStatus={loopState.loopStatus}
        iterationCount={loopState.iterationCount}
        loopStartTime={loopState.loopStartTime}
        wsState={wsState}
        sessionId={sessionId}
        onError={(msg) => toast(msg, "error")}
        theme={theme}
        onThemeToggle={onThemeToggle}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Collapsible chat sidebar */}
        <div
          className="flex flex-col bg-[#0a0a0a] border-r border-[#1a1a1a] shrink-0 overflow-hidden transition-all duration-200"
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
                  ralphItLoading={ralphItLoading}
                  mode="sidebar"
                />
              </div>
              {/* Collapse toggle at bottom */}
              <button
                className="w-full border-t border-[#1a1a1a] h-9 flex items-center justify-center gap-1.5 font-mono text-xs uppercase tracking-wider text-[#333] hover:text-[#00FF41] hover:border-[#00FF41] transition-colors shrink-0"
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
                className="p-2 border border-[#333] hover:border-[#00FF41] text-[#333] hover:text-[#00FF41] transition-colors"
                title="Open chat"
                onClick={() => setSidebarOpen(true)}
              >
                <MessageCircle className="size-4" />
              </button>
              <span
                className="text-[10px] text-[#333] uppercase tracking-widest select-none"
                style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
              >
                CHAT
              </span>
              <button
                className="p-1 mt-auto border border-[#333] hover:border-[#00FF41] text-[#333] hover:text-[#00FF41] transition-colors"
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
          <div className="flex flex-col gap-0 overflow-hidden border-r border-[#1a1a1a]">
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
