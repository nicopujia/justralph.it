import { useState } from "react";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { TaskList } from "./TaskList";
import type { ChatState } from "@/hooks/useChatbot";
import type { TaskInfo } from "@/hooks/useEventReducer";

type Tab = "confidence" | "tasks" | "code";

type RightPanelProps = {
  chatState: ChatState;
  tasks: Map<string, TaskInfo>;
  loopStarted: boolean;
  sessionId?: string;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
  onDimensionClick?: (dimension: string) => void;
};

export function RightPanel({
  chatState,
  tasks,
  loopStarted,
  sessionId,
  onTaskUpdate,
  onDimensionClick,
}: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>("confidence");

  const tabs: { id: Tab; label: string }[] = [
    { id: "confidence", label: "CONFIDENCE" },
    { id: "tasks", label: "TASKS" },
    { id: "code", label: "CODE" },
  ];

  return (
    <div className="flex flex-col overflow-hidden h-full border border-[#1a1a1a] bg-[#0a0a0a]">
      {/* Tab bar */}
      <div className="flex border-b border-[#1a1a1a] shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`text-xs uppercase tracking-wider px-3 py-2 font-mono transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-[#00FF41] text-[#00FF41]"
                : "text-[#333] hover:text-[#00FF41]"
            }`}
          >
            {tab.label}
            {tab.id === "tasks" && loopStarted && tasks.size > 0 && (
              <span className="ml-1.5 border border-[#333] text-[#00FF41] px-1 text-[10px]">
                {tasks.size}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3">
        {activeTab === "confidence" && (
          <ConfidenceMeter
            confidence={chatState.confidence}
            relevance={chatState.relevance}
            weightedReadiness={chatState.weightedReadiness}
            questionCount={chatState.questionCount}
            phase={chatState.phase}
            ready={chatState.ready}
            onDimensionClick={onDimensionClick}
          />
        )}
        {activeTab === "tasks" && (
          loopStarted ? (
            <TaskList tasks={tasks} sessionId={sessionId} onTaskUpdate={onTaskUpdate} embedded />
          ) : (
            <div className="flex flex-col items-center justify-center h-full py-8 text-center">
              <p className="text-[#333] font-mono text-xs uppercase tracking-wider">
                TASKS WILL APPEAR WHEN RALPHY IS READY
              </p>
            </div>
          )
        )}
        {activeTab === "code" && (
          <div className="flex flex-col items-center justify-center h-full py-8 text-center">
            <p className="text-[#333] font-mono text-xs uppercase tracking-wider">
              CODE CHANGES WILL APPEAR WHEN LOOP STARTS
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
