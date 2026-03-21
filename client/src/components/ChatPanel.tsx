import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  MessageCircle,
  Send,
  Loader2,
  Rocket,
  Paperclip,
  Undo2,
  Code,
  ListTodo,
  BarChart2,
} from "lucide-react";
import { API_URL } from "@/lib/config";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { useToast } from "./Toast";
import type { ChatState } from "@/hooks/useChatbot";

const SLOW_THRESHOLD_MS = 15_000;

type RightTab = "confidence" | "tasks" | "code";

type ChatPanelProps = {
  state: ChatState;
  onSend: (message: string) => void;
  onRalphIt: () => void;
  /** Called when user wants to review generated tasks before starting loop. */
  onReviewTasks?: () => void;
  onClearError?: () => void;
  /** true while ralphIt() is in flight (distinct from message loading). */
  ralphItLoading?: boolean;
  /** "full" = Phase 1 fullscreen two-column; "sidebar" = Phase 2 collapsed sidebar. */
  mode?: "full" | "sidebar";
  /** Undo the last user+assistant message pair. */
  onUndo?: () => void;
};

/** Shared file upload handler used in both modes. */
function FileInput({
  sessionId,
  onSend,
  size = "default",
}: {
  sessionId: string | null;
  onSend: (msg: string) => void;
  size?: "default" | "sm";
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const iconClass = size === "sm" ? "size-3" : "size-4";
  const btnClass = size === "sm" ? "size-7 shrink-0" : "";

  return (
    <>
      <Button
        variant="ghost"
        size={size === "sm" ? "icon" : "icon"}
        className={btnClass}
        onClick={() => fileRef.current?.click()}
        title="Attach files"
        disabled={!sessionId}
      >
        <Paperclip className={iconClass} />
      </Button>
      <input
        ref={fileRef}
        type="file"
        multiple
        className="hidden"
        onChange={async (e) => {
          if (!sessionId || !e.target.files) return;
          for (const file of Array.from(e.target.files)) {
            const form = new FormData();
            form.append("file", file);
            await fetch(`${API_URL}/api/sessions/${sessionId}/uploads`, {
              method: "POST",
              body: form,
            });
          }
          onSend(`[Attached ${e.target.files.length} file(s)]`);
          e.target.value = "";
        }}
      />
    </>
  );
}

/** Right-side tabbed panel shown in full mode. */
function RightTabPanel({
  state,
  onRalphIt,
  onReviewTasks,
  ralphItLoading,
  slowLoad,
  busy,
}: {
  state: ChatState;
  onRalphIt: () => void;
  onReviewTasks?: () => void;
  ralphItLoading: boolean;
  slowLoad: boolean;
  busy: boolean;
}) {
  const [activeTab, setActiveTab] = useState<RightTab>("confidence");

  const tabs: { id: RightTab; label: string; icon: React.ReactNode }[] = [
    { id: "confidence", label: "Confidence", icon: <BarChart2 className="size-3.5" /> },
    { id: "tasks", label: "Tasks", icon: <ListTodo className="size-3.5" /> },
    { id: "code", label: "Code", icon: <Code className="size-3.5" /> },
  ];

  return (
    <div className="flex flex-col h-full dark:bg-zinc-900 bg-gray-50 border-l dark:border-zinc-800 border-gray-200">
      {/* Tab bar */}
      <div className="flex border-b dark:border-zinc-800 border-gray-200 shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              "flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors",
              activeTab === tab.id
                ? "dark:text-zinc-100 text-gray-900 border-b-2 dark:border-emerald-500 border-emerald-600"
                : "dark:text-zinc-500 text-gray-400 dark:hover:text-zinc-300 hover:text-gray-600",
            ].join(" ")}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "confidence" && (
          <ConfidenceMeter
            confidence={state.confidence}
            relevance={state.relevance}
            weightedReadiness={state.weightedReadiness}
            questionCount={state.questionCount}
            phase={state.phase}
            ready={state.ready}
          />
        )}
        {activeTab === "tasks" && (
          <div className="space-y-2">
            {state.tasks && state.tasks.length > 0 ? (
              state.tasks.map((task: any, i: number) => (
                <div
                  key={i}
                  className="rounded-md dark:bg-zinc-800 bg-white border dark:border-zinc-700 border-gray-200 px-3 py-2"
                >
                  <p className="text-xs font-medium dark:text-zinc-200 text-gray-800 truncate">
                    {task.title ?? task.name ?? `Task ${i + 1}`}
                  </p>
                  {task.body && (
                    <p className="text-xs dark:text-zinc-500 text-gray-400 mt-0.5 line-clamp-2">
                      {task.body}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p className="text-xs dark:text-zinc-500 text-gray-400 text-center py-8">
                Tasks will appear when Ralphy is ready.
              </p>
            )}
          </div>
        )}
        {activeTab === "code" && (
          <p className="text-xs dark:text-zinc-500 text-gray-400 text-center py-8">
            Code changes will appear here when the loop starts.
          </p>
        )}
      </div>

      {/* Action button */}
      {state.ready && (
        <div className="p-4 border-t dark:border-zinc-800 border-gray-200 shrink-0 space-y-2">
          {onReviewTasks ? (
            <Button
              onClick={onReviewTasks}
              disabled={busy}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              size="lg"
            >
              <Rocket className="size-4 mr-2" />
              Review Tasks
            </Button>
          ) : (
            <Button
              onClick={onRalphIt}
              disabled={busy}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              size="lg"
            >
              {ralphItLoading ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  Creating project...
                </>
              ) : (
                <>
                  <Rocket className="size-4 mr-2" />
                  Just Ralph It
                </>
              )}
            </Button>
          )}
          {slowLoad && !onReviewTasks && (
            <p className="text-xs dark:text-zinc-500 text-gray-400 text-center">
              This is taking a while...
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function ChatPanel({
  state,
  onSend,
  onRalphIt,
  onReviewTasks,
  onClearError,
  ralphItLoading = false,
  mode = "full",
  onUndo,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  // Timeout indicator: shown if ralphItLoading has been true >15s
  const [slowLoad, setSlowLoad] = useState(false);
  useEffect(() => {
    if (!ralphItLoading) {
      setSlowLoad(false);
      return;
    }
    const t = setTimeout(() => setSlowLoad(true), SLOW_THRESHOLD_MS);
    return () => clearTimeout(t);
  }, [ralphItLoading]);

  // Consume transient errors from hook state -> toast
  useEffect(() => {
    if (!state.error) return;
    toast("Failed to send message", "error");
    onClearError?.();
  }, [state.error, toast, onClearError]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [state.messages.length]);

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || state.loading) return;
    setInput("");
    onSend(msg);
  };

  const busy = state.loading || ralphItLoading;

  // ----------------------------- sidebar mode -----------------------------
  if (mode === "sidebar") {
    return (
      <div className="h-full flex flex-col dark:bg-zinc-900 bg-white border-r dark:border-zinc-800 border-gray-200 overflow-hidden">
        {/* Compact header */}
        <div className="px-3 py-3 border-b dark:border-zinc-800 border-gray-200 shrink-0">
          <h2 className="text-xs font-semibold flex items-center gap-1.5 dark:text-zinc-500 text-gray-400 uppercase tracking-wide">
            <MessageCircle className="size-3.5" />
            Chat
          </h2>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-2">
          {state.messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full dark:text-zinc-500 text-gray-400 text-xs text-center py-6 px-2">
              <MessageCircle className="size-6 mb-2 opacity-30" />
              <p>No messages yet.</p>
            </div>
          )}
          {state.messages.map((msg, i) => {
            const lastUserIdx =
              state.messages.length >= 2
                ? state.messages.map((m) => m.role).lastIndexOf("user")
                : -1;
            const showUndo =
              onUndo && msg.role === "user" && i === lastUserIdx && state.messages.length >= 2;
            return (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`flex items-end gap-1 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
                >
                  {showUndo && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-5 shrink-0 dark:text-zinc-500 text-gray-400 opacity-60 hover:opacity-100"
                      title="Undo last message"
                      onClick={onUndo}
                    >
                      <Undo2 className="size-3" />
                    </Button>
                  )}
                  <div
                    className={`max-w-full rounded-md px-2.5 py-1.5 text-xs whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              </div>
            );
          })}
          {state.loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-md px-2.5 py-1.5">
                <Loader2 className="size-3 animate-spin" />
              </div>
            </div>
          )}
        </div>

        {/* Ready actions (sidebar) */}
        {state.ready && (
          <div className="px-2 pb-2 shrink-0">
            {onReviewTasks ? (
              <Button
                onClick={onReviewTasks}
                disabled={busy}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-8"
                size="sm"
              >
                <Rocket className="size-3 mr-1" />
                Review Tasks
              </Button>
            ) : (
              <Button
                onClick={onRalphIt}
                disabled={busy}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs h-8"
                size="sm"
              >
                {ralphItLoading ? (
                  <Loader2 className="size-3 mr-1 animate-spin" />
                ) : (
                  <Rocket className="size-3 mr-1" />
                )}
                {ralphItLoading ? "Creating project..." : "Ralph It"}
              </Button>
            )}
          </div>
        )}

        {/* Input */}
        <div className="border-t dark:border-zinc-800 border-gray-200 p-2 shrink-0">
          <div className="flex gap-1">
            <FileInput sessionId={state.sessionId} onSend={onSend} size="sm" />
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="Message..."
              disabled={busy}
              className="flex-1 h-7 text-xs"
            />
            <Button
              onClick={handleSend}
              disabled={busy || !input.trim()}
              size="icon"
              className="size-7 shrink-0"
            >
              <Send className="size-3" />
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ----------------------------- full mode (two columns) -----------------
  return (
    <div className="h-screen flex dark:bg-zinc-950 bg-white overflow-hidden">
      {/* LEFT column: header + messages + input */}
      <div className="flex-1 flex flex-col min-w-0 border-r dark:border-zinc-800 border-gray-200">
        {/* Header */}
        <div className="border-b dark:border-zinc-800 border-gray-200 px-6 py-4 shrink-0">
          <h1 className="text-xl font-mono font-bold dark:text-zinc-100 text-gray-900 flex items-center gap-2">
            <MessageCircle className="size-5 text-emerald-500" />
            justralph.it
          </h1>
          <p className="text-sm dark:text-zinc-500 text-gray-400 mt-1">
            Describe your project. Ralphy will ask questions until he's confident enough to build it.
          </p>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          {state.messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full dark:text-zinc-500 text-gray-400">
              <MessageCircle className="size-12 mb-4 opacity-30" />
              <p className="text-lg font-medium">What do you want to build?</p>
              <p className="text-sm mt-1">Describe your idea and Ralphy will take it from there.</p>
            </div>
          )}
          {state.messages.map((msg, i) => {
            const lastUserIdx =
              state.messages.length >= 2
                ? state.messages.map((m) => m.role).lastIndexOf("user")
                : -1;
            const showUndo =
              onUndo && msg.role === "user" && i === lastUserIdx && state.messages.length >= 2;
            return (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`flex items-end gap-1.5 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
                >
                  {showUndo && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-6 shrink-0 dark:text-zinc-500 text-gray-400 opacity-60 hover:opacity-100"
                      title="Undo last message"
                      onClick={onUndo}
                    >
                      <Undo2 className="size-3.5" />
                    </Button>
                  )}
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              </div>
            );
          })}
          {state.loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg px-4 py-2.5">
                <Loader2 className="size-4 animate-spin" />
              </div>
            </div>
          )}
        </div>

        {/* Input bar */}
        <div className="border-t dark:border-zinc-800 border-gray-200 p-4 shrink-0">
          <div className="flex gap-2">
            <FileInput sessionId={state.sessionId} onSend={onSend} />
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="Describe your project..."
              disabled={busy}
              className="flex-1"
            />
            <Button onClick={handleSend} disabled={busy || !input.trim()} size="icon">
              <Send className="size-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* RIGHT column: tabbed panel (w-80) */}
      <div className="w-80 shrink-0 flex flex-col overflow-hidden">
        <RightTabPanel
          state={state}
          onRalphIt={onRalphIt}
          onReviewTasks={onReviewTasks}
          ralphItLoading={ralphItLoading}
          slowLoad={slowLoad}
          busy={busy}
        />
      </div>
    </div>
  );
}
