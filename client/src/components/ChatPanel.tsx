import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Send,
  Paperclip,
  Undo2,
  Code,
  ListTodo,
  BarChart2,
  Sun,
  Moon,
} from "lucide-react";
import type { Theme } from "@/hooks/useTheme";
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
  /** Theme control for the header toggle. */
  theme?: Theme;
  onThemeToggle?: () => void;
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
  const sizeClass = size === "sm" ? "size-7 shrink-0" : "size-8 shrink-0";
  const iconClass = size === "sm" ? "size-3" : "size-4";

  return (
    <>
      <button
        className={[
          sizeClass,
          "border border-[#333] text-[#333] hover:text-[#00FF41] hover:border-[#00FF41] transition-colors flex items-center justify-center bg-transparent",
          !sessionId ? "opacity-40 cursor-not-allowed" : "",
        ].join(" ")}
        onClick={() => fileRef.current?.click()}
        title="Attach files"
        disabled={!sessionId}
      >
        <Paperclip className={iconClass} />
      </button>
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
    { id: "confidence", label: "CONFIDENCE", icon: <BarChart2 className="size-3" /> },
    { id: "tasks", label: "TASKS", icon: <ListTodo className="size-3" /> },
    { id: "code", label: "CODE", icon: <Code className="size-3" /> },
  ];

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] border-l border-[#1a1a1a]">
      {/* Tab bar */}
      <div className="flex border-b border-[#1a1a1a] shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              "flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors",
              activeTab === tab.id
                ? "text-[#00FF41] border-b-2 border-[#00FF41]"
                : "text-[#333] hover:text-[#00FF41]",
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
                  className="border border-[#1a1a1a] px-3 py-2 bg-black"
                >
                  <p className="text-xs font-bold text-white uppercase truncate">
                    {task.title ?? task.name ?? `TASK ${i + 1}`}
                  </p>
                  {task.body && (
                    <p className="text-xs text-[#333] mt-0.5 line-clamp-2">
                      {task.body}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p className="text-xs text-[#333] uppercase tracking-wider text-center py-8">
                TASKS WILL APPEAR WHEN RALPH IS READY.
              </p>
            )}
          </div>
        )}
        {activeTab === "code" && (
          <p className="text-xs text-[#333] uppercase tracking-wider text-center py-8">
            CODE CHANGES WILL APPEAR WHEN THE LOOP STARTS.
          </p>
        )}
      </div>

      {/* Action button */}
      {state.ready && (
        <div className="p-4 border-t border-[#1a1a1a] shrink-0 space-y-2">
          {onReviewTasks ? (
            <button
              onClick={onReviewTasks}
              disabled={busy}
              className="w-full border-2 border-[#00FF41] bg-transparent text-[#00FF41] hover:bg-[#00FF41] hover:text-black uppercase tracking-wider text-sm font-bold py-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              REVIEW TASKS
            </button>
          ) : (
            <button
              onClick={onRalphIt}
              disabled={busy}
              className="w-full border-2 border-[#00FF41] bg-transparent text-[#00FF41] hover:bg-[#00FF41] hover:text-black uppercase tracking-wider text-sm font-bold py-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {ralphItLoading ? "CREATING PROJECT..." : "JUST RALPH IT"}
            </button>
          )}
          {slowLoad && !onReviewTasks && (
            <p className="text-xs text-[#333] uppercase tracking-wider text-center">
              THIS IS TAKING A WHILE...
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
  theme,
  onThemeToggle,
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

  // Elapsed seconds counter while loading
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  useEffect(() => {
    if (!state.loading) {
      setElapsedSeconds(0);
      return;
    }
    setElapsedSeconds(0);
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [state.loading]);

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
      <div className="h-full flex flex-col bg-[#0a0a0a] border-r border-[#1a1a1a] overflow-hidden">
        {/* Compact header */}
        <div className="px-3 py-3 border-b border-[#1a1a1a] shrink-0">
          <h2 className="text-xs font-bold text-[#333] uppercase tracking-wider">
            CHAT
          </h2>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-2 py-1">
          {state.messages.length === 0 && (
            <div className="flex flex-col justify-center h-full text-[#333] text-xs text-center py-6 px-2 uppercase tracking-wider">
              <p>NO MESSAGES YET.</p>
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
                className="border-b border-[#1a1a1a] py-2 flex items-start gap-1"
              >
                {showUndo && (
                  <button
                    className="shrink-0 text-[#333] hover:text-[#00FF41] opacity-60 hover:opacity-100 mt-0.5"
                    title="Undo last message"
                    onClick={onUndo}
                  >
                    <Undo2 className="size-3" />
                  </button>
                )}
                <p
                  className={[
                    "text-xs whitespace-pre-wrap break-words",
                    msg.role === "user" ? "text-[#00FF41]" : "text-white",
                  ].join(" ")}
                >
                  <span className={msg.role === "user" ? "text-[#00FF41]" : "text-white"}>
                    {msg.role === "user" ? "> " : "$ "}
                  </span>
                  {msg.content}
                </p>
              </div>
            );
          })}
          {state.loading && (
            <div className="py-2 border-b border-[#1a1a1a]">
              <span className="text-xs text-white">
                $ PROCESSING...<span className="animate-blink">_</span>
                <span className="text-[#333] ml-2">{elapsedSeconds}s</span>
              </span>
            </div>
          )}
        </div>

        {/* Ready actions (sidebar) */}
        {state.ready && (
          <div className="px-2 pb-2 shrink-0">
            {onReviewTasks ? (
              <button
                onClick={onReviewTasks}
                disabled={busy}
                className="w-full border border-[#00FF41] bg-transparent text-[#00FF41] hover:bg-[#00FF41] hover:text-black uppercase tracking-wider text-xs font-bold py-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                REVIEW TASKS
              </button>
            ) : (
              <button
                onClick={onRalphIt}
                disabled={busy}
                className="w-full border border-[#00FF41] bg-transparent text-[#00FF41] hover:bg-[#00FF41] hover:text-black uppercase tracking-wider text-xs font-bold py-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {ralphItLoading ? "CREATING..." : "RALPH IT"}
              </button>
            )}
          </div>
        )}

        {/* Input */}
        <div className="border-t border-[#1a1a1a] p-2 shrink-0">
          <div className="flex gap-1">
            <FileInput sessionId={state.sessionId} onSend={onSend} size="sm" />
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="MSG..."
              disabled={busy}
              className="flex-1 h-7 text-xs bg-transparent border border-[#333] text-[#00FF41] placeholder:text-[#333] px-2 outline-none focus:border-[#00FF41] transition-colors"
            />
            <button
              onClick={handleSend}
              disabled={busy || !input.trim()}
              className="size-7 shrink-0 border border-[#00FF41] bg-transparent text-[#00FF41] hover:bg-[#00FF41] hover:text-black transition-colors flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="size-3" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ----------------------------- full mode (two columns) -----------------
  return (
    <div className="h-screen flex bg-black overflow-hidden">
      {/* LEFT column: header + messages + input */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#1a1a1a]">
        {/* Header */}
        <div className="border-b border-[#1a1a1a] px-6 py-4 shrink-0 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold uppercase tracking-[0.15em] text-white">
              JUSTRALPH.IT
            </h1>
            <p className="text-[#00FF41] text-xs uppercase tracking-widest mt-1">
              DESCRIBE YOUR PROJECT. RALPH BUILDS IT.
            </p>
          </div>
          {onThemeToggle && (
            <button
              onClick={onThemeToggle}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              title={theme === "dark" ? "Light mode" : "Dark mode"}
              className="shrink-0 text-[#00FF41] hover:opacity-70 transition-opacity"
            >
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
          )}
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-2">
          {state.messages.length === 0 && (
            <div className="flex flex-col justify-center h-full text-[#333] uppercase tracking-wider text-center">
              <p className="text-sm font-bold">WHAT DO YOU WANT TO BUILD?</p>
              <p className="text-xs mt-1">DESCRIBE YOUR IDEA AND RALPH WILL TAKE IT FROM THERE.</p>
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
                className="border-b border-[#1a1a1a] py-3 flex items-start gap-2"
              >
                {showUndo && (
                  <button
                    className="shrink-0 text-[#333] hover:text-[#00FF41] opacity-60 hover:opacity-100 mt-0.5"
                    title="Undo last message"
                    onClick={onUndo}
                  >
                    <Undo2 className="size-3.5" />
                  </button>
                )}
                <p
                  className={[
                    "text-sm whitespace-pre-wrap break-words w-full",
                    msg.role === "user" ? "text-[#00FF41]" : "text-white",
                  ].join(" ")}
                >
                  <span className="font-bold mr-1">
                    {msg.role === "user" ? "> " : "$ "}
                  </span>
                  {msg.content}
                </p>
              </div>
            );
          })}
          {state.loading && (
            <div className="py-3 border-b border-[#1a1a1a]">
              <span className="text-sm text-white">
                $ PROCESSING...<span className="animate-blink">_</span>
                <span className="text-[#333] text-xs ml-2">{elapsedSeconds}s</span>
              </span>
            </div>
          )}
        </div>

        {/* Input bar */}
        <div className="border-t border-[#1a1a1a] p-4 shrink-0">
          <div className="flex gap-2 items-center">
            <FileInput sessionId={state.sessionId} onSend={onSend} />
            <span className="text-[#00FF41] font-bold text-sm shrink-0">&gt;</span>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="DESCRIBE YOUR PROJECT..."
              disabled={busy}
              className="flex-1 bg-transparent border border-[#333] text-[#00FF41] placeholder:text-[#333] px-3 py-2 text-sm outline-none focus:border-[#00FF41] transition-colors"
            />
            <button
              onClick={handleSend}
              disabled={busy || !input.trim()}
              className="border border-[#00FF41] bg-transparent text-[#00FF41] hover:bg-[#00FF41] hover:text-black transition-colors px-3 py-2 flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="size-4" />
            </button>
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
