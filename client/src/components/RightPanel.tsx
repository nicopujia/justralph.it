import { useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { TaskList } from "./TaskList";
import type { ChatState } from "@/hooks/useChatbot";
import type { TaskInfo } from "@/hooks/useEventReducer";

type Tab = "confidence" | "tasks";

type RightPanelProps = {
  chatState: ChatState;
  tasks: Map<string, TaskInfo>;
  loopStarted: boolean;
  sessionId?: string;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
};

export function RightPanel({ chatState, tasks, loopStarted, sessionId, onTaskUpdate }: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>("confidence");

  return (
    <Card className="flex flex-col overflow-hidden h-full">
      <CardHeader className="pb-0 px-4 pt-3">
        {/* Tab buttons */}
        <div className="flex gap-1 border-b pb-2">
          <Button
            variant={activeTab === "confidence" ? "secondary" : "ghost"}
            size="sm"
            className="text-xs h-7 px-3"
            onClick={() => setActiveTab("confidence")}
          >
            Confidence
          </Button>
          <Button
            variant={activeTab === "tasks" ? "secondary" : "ghost"}
            size="sm"
            className="text-xs h-7 px-3"
            onClick={() => setActiveTab("tasks")}
          >
            Tasks
            {loopStarted && tasks.size > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-muted px-1.5 py-0 text-xs font-medium tabular-nums">
                {tasks.size}
              </span>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-y-auto px-4 py-3">
        {activeTab === "confidence" && (
          <ConfidenceMeter
            confidence={chatState.confidence}
            relevance={chatState.relevance}
            weightedReadiness={chatState.weightedReadiness}
            questionCount={chatState.questionCount}
            phase={chatState.phase}
            ready={chatState.ready}
          />
        )}
        {activeTab === "tasks" && (
          loopStarted ? (
            <TaskList tasks={tasks} sessionId={sessionId} onTaskUpdate={onTaskUpdate} embedded />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm py-8 text-center">
              <p className="opacity-60">Tasks appear once the loop starts.</p>
            </div>
          )
        )}
      </CardContent>
    </Card>
  );
}
