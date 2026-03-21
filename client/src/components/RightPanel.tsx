import { useState } from "react";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { TaskList } from "./TaskList";
import { DiffViewer } from "./DiffViewer";
import { ToolsetPanel } from "./ToolsetPanel";
import type { ChatState, ToolName } from "@/hooks/useChatbot";
import type { TaskInfo, TaskDiffEntry } from "@/hooks/useEventReducer";
import { ExternalLink, Check, X, AlertTriangle } from "lucide-react";

type Tab = "confidence" | "tasks" | "code" | "tools";

type RightPanelProps = {
  chatState: ChatState;
  tasks: Map<string, TaskInfo>;
  taskDiffs: Map<string, TaskDiffEntry>;
  loopStarted: boolean;
  sessionId?: string;
  githubUrl?: string | null;
  onTaskUpdate?: (taskId: string, patch: Partial<TaskInfo>) => void;
  onDimensionClick?: (dimension: string) => void;
  onRunTool?: (tool: ToolName, context?: string) => void;
  onClearToolResult?: () => void;
};

/** Convert a git remote URL to a browser-friendly GitHub link. */
function toGitHubLink(url: string): string {
  return url
    .replace(/\.git$/, "")
    .replace(/^git@github\.com:/, "https://github.com/");
}

export function RightPanel({
  chatState,
  tasks,
  taskDiffs,
  loopStarted,
  sessionId,
  githubUrl,
  onTaskUpdate,
  onDimensionClick,
  onRunTool,
  onClearToolResult,
}: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>("confidence");
  const [selectedDiffTask, setSelectedDiffTask] = useState<string | null>(null);

  const tabs: { id: Tab; label: string }[] = [
    { id: "confidence", label: "CONFIDENCE" },
    { id: "tasks", label: "TASKS" },
    { id: "code", label: "CODE" },
    { id: "tools", label: "TOOLS" },
  ];

  // Get diff lines for the currently selected task (or all diffs merged)
  const diffTaskIds = Array.from(taskDiffs.keys());
  const activeDiffId = selectedDiffTask ?? diffTaskIds[diffTaskIds.length - 1] ?? null;
  const activeDiff = activeDiffId ? taskDiffs.get(activeDiffId) : null;
  const diffLines = activeDiff?.diff.split("\n") ?? [];

  const ghLink = githubUrl ? toGitHubLink(githubUrl) : null;

  return (
    <div className="flex flex-col overflow-hidden h-full border border-border bg-card">
      {/* Tab bar + optional GitHub link */}
      <div className="flex items-center border-b border-border shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`text-xs uppercase tracking-wider px-3 py-2 font-mono transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-primary"
            }`}
          >
            {tab.label}
            {tab.id === "tasks" && loopStarted && tasks.size > 0 && (
              <span className="ml-1.5 border border-border text-primary px-1 text-[10px]">
                {tasks.size}
              </span>
            )}
            {tab.id === "code" && diffTaskIds.length > 0 && (
              <span className="ml-1.5 border border-border text-primary px-1 text-[10px]">
                {diffTaskIds.length}
              </span>
            )}
            {tab.id === "tools" && chatState.toolResult && (
              <span className="ml-1.5 size-1.5 rounded-full bg-[var(--color-warning)] inline-block" />
            )}
          </button>
        ))}

        {/* GitHub link */}
        {ghLink && (
          <a
            href={ghLink}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto mr-3 text-muted-foreground hover:text-primary transition-colors"
            title={ghLink}
          >
            <ExternalLink className="size-3" />
          </a>
        )}
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
          (loopStarted || tasks.size > 0 || sessionId) ? (
            <>
              <TaskList tasks={tasks} sessionId={sessionId} onTaskUpdate={onTaskUpdate} embedded />
              {/* Push status legend */}
              {Array.from(tasks.values()).some((t) => t.status === "done") && (
                <div className="mt-3 pt-3 border-t border-border font-mono text-[10px] text-muted-foreground uppercase tracking-wider">
                  Push status:{" "}
                  <Check className="inline size-3 text-[var(--color-success)]" /> pushed{" "}
                  <X className="inline size-3 text-red-400" /> failed{" "}
                  <AlertTriangle className="inline size-3 text-yellow-400" /> no remote
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full py-8 text-center">
              <p className="text-muted-foreground font-mono text-xs uppercase tracking-wider">
                TASKS WILL APPEAR WHEN RALPHY IS READY
              </p>
            </div>
          )
        )}
        {activeTab === "code" && (
          diffTaskIds.length > 0 ? (
            <div className="flex flex-col gap-0 h-full -mx-4 -my-3">
              {/* Task selector strip */}
              <div className="flex items-center gap-1 px-3 py-1.5 border-b border-border overflow-x-auto shrink-0">
                {diffTaskIds.map((tid) => (
                  <button
                    key={tid}
                    onClick={() => setSelectedDiffTask(tid)}
                    className={`px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider transition-colors whitespace-nowrap ${
                      tid === activeDiffId
                        ? "border border-primary text-primary bg-primary/5"
                        : "border border-border text-muted-foreground hover:text-primary hover:border-primary"
                    }`}
                  >
                    {tid}
                  </button>
                ))}
                {ghLink && activeDiffId && (
                  <a
                    href={ghLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-primary transition-colors whitespace-nowrap flex items-center gap-1"
                  >
                    <ExternalLink className="size-2.5" />
                    GitHub
                  </a>
                )}
              </div>
              {/* Diff viewer */}
              <div className="flex-1 overflow-hidden">
                <DiffViewer lines={diffLines} />
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full py-8 text-center">
              <p className="text-muted-foreground font-mono text-xs uppercase tracking-wider">
                CODE CHANGES WILL APPEAR WHEN TASKS COMPLETE
              </p>
            </div>
          )
        )}
        {activeTab === "tools" && onRunTool && (
          <ToolsetPanel
            state={chatState}
            onRunTool={onRunTool}
            toolLoading={chatState.toolLoading}
            activeTool={chatState.toolLoadingId ?? null}
          />
        )}
        {activeTab === "tools" && !onRunTool && (
          <p className="text-muted-foreground font-mono text-xs uppercase tracking-wider text-center py-8">
            TOOLS NOT AVAILABLE.
          </p>
        )}
      </div>
    </div>
  );
}
