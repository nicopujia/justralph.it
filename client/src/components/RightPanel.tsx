import { useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { TaskList } from "./TaskList";
import type { ChatState, Confidence } from "@/hooks/useChatbot";
import type { TaskInfo } from "@/hooks/useEventReducer";

type Tab = "confidence" | "tasks" | "summary";

type RightPanelProps = {
  chatState: ChatState;
  tasks: Map<string, TaskInfo>;
  loopStarted: boolean;
  sessionId?: string;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
  onDimensionClick?: (dimension: string) => void;
};

const DIMENSION_LABELS: Record<keyof Confidence, string> = {
  functional: "Functional",
  technical_stack: "Tech Stack",
  data_model: "Data Model",
  auth: "Auth",
  deployment: "Deployment",
  testing: "Testing",
  edge_cases: "Edge Cases",
};

function SummaryTab({ chatState }: { chatState: ChatState }) {
  const { project, confidence, phase, questionCount } = chatState;

  const activeDims = (Object.entries(confidence) as [keyof Confidence, number][]).filter(
    ([, v]) => v > 0,
  );

  return (
    <div className="space-y-4 text-sm">
      {/* Project metadata */}
      {project && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Project
          </p>
          {project.name && (
            <p className="font-medium">{project.name}</p>
          )}
          {project.description && (
            <p className="text-xs text-muted-foreground">{project.description}</p>
          )}
          <div className="flex flex-wrap gap-1 mt-1">
            {project.language && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{project.language}</span>
            )}
            {project.framework && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{project.framework}</span>
            )}
          </div>
        </div>
      )}

      {/* Confidence by dimension */}
      {activeDims.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Confidence
          </p>
          <ul className="space-y-0.5">
            {activeDims.map(([key, value]) => (
              <li key={key} className="flex justify-between text-xs">
                <span className="text-muted-foreground">{DIMENSION_LABELS[key]}</span>
                <span
                  className={`font-mono tabular-nums font-medium ${
                    value >= 70
                      ? "text-green-600 dark:text-green-400"
                      : value >= 40
                        ? "text-yellow-600 dark:text-yellow-400"
                        : "text-red-500"
                  }`}
                >
                  {value}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Session metadata */}
      <div className="space-y-0.5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Session
        </p>
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Phase</span>
          <span>{phase}/4</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Questions</span>
          <span>{questionCount}</span>
        </div>
      </div>

      {activeDims.length === 0 && !project && (
        <p className="text-xs text-muted-foreground text-center py-4 opacity-60">
          Summary builds as you chat.
        </p>
      )}
    </div>
  );
}

export function RightPanel({
  chatState,
  tasks,
  loopStarted,
  sessionId,
  onTaskUpdate,
  onDimensionClick,
}: RightPanelProps) {
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
          <Button
            variant={activeTab === "summary" ? "secondary" : "ghost"}
            size="sm"
            className="text-xs h-7 px-3"
            onClick={() => setActiveTab("summary")}
          >
            Summary
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
            onDimensionClick={onDimensionClick}
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
        {activeTab === "summary" && (
          <SummaryTab chatState={chatState} />
        )}
      </CardContent>
    </Card>
  );
}
