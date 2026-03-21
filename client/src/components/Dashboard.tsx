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
import { Button } from "@/components/ui/button";
import { MessageCircle, ChevronLeft, ChevronRight } from "lucide-react";

type Phase = "chat" | "preview" | "loop";

export function Dashboard() {
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

  // Phase 1: full-screen chat
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

  // Phase 2: loop view with collapsible chat sidebar
  const sessionId = chatbot.state.sessionId!;
  const sidebarWidth = sidebarOpen ? 350 : 60;

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <StatusBar
        loopStatus={loopState.loopStatus}
        iterationCount={loopState.iterationCount}
        loopStartTime={loopState.loopStartTime}
        wsState={wsState}
        sessionId={sessionId}
        onError={(msg) => toast(msg, "error")}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Collapsible chat sidebar */}
        <div
          className="flex flex-col border-r shrink-0 overflow-hidden transition-all duration-200"
          style={{ width: sidebarWidth }}
        >
          {sidebarOpen ? (
            <>
              {/* Expanded: full sidebar chat */}
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
              <Button
                variant="ghost"
                size="sm"
                className="w-full rounded-none border-t h-9 text-xs text-muted-foreground gap-1.5 shrink-0"
                onClick={() => setSidebarOpen(false)}
              >
                <ChevronLeft className="size-3.5" />
                Collapse
              </Button>
            </>
          ) : (
            /* Collapsed: icon-only strip */
            <div className="flex flex-col items-center py-3 gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="size-10"
                title="Open chat"
                onClick={() => setSidebarOpen(true)}
              >
                <MessageCircle className="size-5" />
              </Button>
              {/* Vertical label */}
              <span
                className="text-xs text-muted-foreground select-none"
                style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
              >
                Chat
              </span>
              {/* Expand arrow at bottom */}
              <Button
                variant="ghost"
                size="icon"
                className="size-7 mt-auto"
                title="Expand chat"
                onClick={() => setSidebarOpen(true)}
              >
                <ChevronRight className="size-3.5" />
              </Button>
            </div>
          )}
        </div>

        {/* Main area: agent output + right panel */}
        <div className="flex-1 grid grid-cols-[1fr_280px] gap-4 p-4 overflow-hidden min-w-0">
          {/* Left: agent output + optional help panel */}
          <div className="flex flex-col gap-4 overflow-hidden">
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

          {/* Right: tabbed confidence + tasks */}
          <RightPanel
            chatState={chatbot.state}
            tasks={loopState.tasks}
            loopStarted={phase === "loop"}
            sessionId={sessionId}
            onDimensionClick={handleDimensionClick}
            onTaskUpdate={(taskId, patch) => {
              // Only "open" resets are issued via retry; dispatch synthetic event.
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
