import { useState, useCallback } from "react";
import { useEventReducer } from "@/hooks/useEventReducer";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useChatbot } from "@/hooks/useChatbot";
import { WS_URL } from "@/lib/config";
import { ChatPanel } from "./ChatPanel";
import { StatusBar } from "./StatusBar";
import { TaskList } from "./TaskList";
import { AgentOutput } from "./AgentOutput";
import { HelpPanel } from "./HelpPanel";

type Phase = "chat" | "loop";

export function Dashboard() {
  const [phase, setPhase] = useState<Phase>("chat");
  const chatbot = useChatbot();
  const [loopState, dispatch] = useEventReducer();
  const [helpTaskId, setHelpTaskId] = useState<string | null>(null);

  // Connect WebSocket once we have a session, scoped to that session
  const wsUrl = chatbot.state.sessionId
    ? `${WS_URL}/ws/${chatbot.state.sessionId}`
    : null;

  const { state: wsState } = useWebSocket(wsUrl, (event) => {
    dispatch(event);
    // Detect HELP events
    if (event.type === "task_help" && event.data?.task_id) {
      setHelpTaskId(event.data.task_id);
    }
  });

  // "Just Ralph It" trigger: creates tasks + starts loop + switches to phase 2
  const handleRalphIt = useCallback(async () => {
    const result = await chatbot.ralphIt();
    if (result?.status === "ralph_it_started") {
      setPhase("loop");
    }
  }, [chatbot]);

  // Phase 1: Chatbot
  if (phase === "chat") {
    return (
      <ChatPanel
        state={chatbot.state}
        onSend={chatbot.sendMessage}
        onRalphIt={handleRalphIt}
      />
    );
  }

  // Phase 2: Loop monitoring
  const sessionId = chatbot.state.sessionId!;

  return (
    <div className="h-screen flex flex-col bg-background">
      <StatusBar
        loopStatus={loopState.loopStatus}
        iterationCount={loopState.iterationCount}
        loopStartTime={loopState.loopStartTime}
        wsState={wsState}
        sessionId={sessionId}
      />
      <div className="flex-1 grid grid-cols-[280px_1fr] gap-4 p-4 overflow-hidden">
        <div className="flex flex-col gap-4 overflow-hidden">
          <TaskList tasks={loopState.tasks} />
          {helpTaskId && (
            <HelpPanel
              sessionId={sessionId}
              taskId={helpTaskId}
              onResume={() => setHelpTaskId(null)}
            />
          )}
        </div>
        <AgentOutput lines={loopState.agentOutputLines} />
      </div>
    </div>
  );
}
