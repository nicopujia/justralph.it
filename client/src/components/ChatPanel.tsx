import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageCircle, Send, Loader2, Rocket, Paperclip, Undo2 } from "lucide-react";
import { API_URL } from "@/lib/config";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { useToast } from "./Toast";
import type { ChatState } from "@/hooks/useChatbot";

const SLOW_THRESHOLD_MS = 15_000;

type ChatPanelProps = {
  state: ChatState;
  onSend: (message: string) => void;
  onRalphIt: () => void;
  /** Called when user wants to review generated tasks before starting loop. */
  onReviewTasks?: () => void;
  onClearError?: () => void;
  /** true while ralphIt() is in flight (distinct from message loading). */
  ralphItLoading?: boolean;
  /** "full" = Phase 1 fullscreen; "sidebar" = Phase 2 collapsed sidebar. */
  mode?: "full" | "sidebar";
  /** Undo the last user+assistant message pair. */
  onUndo?: () => void;
};

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
  const fileRef = useRef<HTMLInputElement>(null);
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

  // True while any loading is happening (chat or ralph-it)
  const busy = state.loading || ralphItLoading;

  if (mode === "sidebar") {
    return (
      <div className="h-full flex flex-col bg-background border-r overflow-hidden">
        {/* Compact header */}
        <div className="px-3 py-3 border-b shrink-0">
          <h2 className="text-xs font-semibold flex items-center gap-1.5 text-muted-foreground uppercase tracking-wide">
            <MessageCircle className="size-3.5" />
            Chat
          </h2>
        </div>

        {/* Messages: compact bubbles */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-2">
          {state.messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-xs text-center py-6 px-2">
              <MessageCircle className="size-6 mb-2 opacity-30" />
              <p>No messages yet.</p>
            </div>
          )}
          {state.messages.map((msg, i) => {
            // Last user message index (for undo button)
            const lastUserIdx = state.messages.length >= 2
              ? state.messages.map((m) => m.role).lastIndexOf("user")
              : -1;
            const showUndo = onUndo && msg.role === "user" && i === lastUserIdx && state.messages.length >= 2;
            return (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div className={`flex items-end gap-1 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                  {showUndo && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-5 shrink-0 text-muted-foreground hover:text-foreground opacity-60 hover:opacity-100"
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
                className="w-full bg-green-600 hover:bg-green-700 text-white text-xs h-8"
                size="sm"
              >
                <Rocket className="size-3 mr-1" />
                Review Tasks
              </Button>
            ) : (
              <Button
                onClick={onRalphIt}
                disabled={busy}
                className="w-full bg-green-600 hover:bg-green-700 text-white text-xs h-8"
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
        <div className="border-t p-2 shrink-0">
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              onClick={() => fileRef.current?.click()}
              title="Attach files"
              disabled={!state.sessionId}
            >
              <Paperclip className="size-3" />
            </Button>
            <input
              ref={fileRef}
              type="file"
              multiple
              className="hidden"
              onChange={async (e) => {
                if (!state.sessionId || !e.target.files) return;
                for (const file of Array.from(e.target.files)) {
                  const form = new FormData();
                  form.append("file", file);
                  await fetch(
                    `${API_URL}/api/sessions/${state.sessionId}/uploads`,
                    { method: "POST", body: form },
                  );
                }
                onSend(`[Attached ${e.target.files.length} file(s)]`);
                e.target.value = "";
              }}
            />
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

  // mode === "full"
  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <div className="border-b px-6 py-4">
        <h1 className="text-lg font-semibold flex items-center gap-2">
          <MessageCircle className="size-5" />
          justralph.it
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Describe your project. Ralphy will ask questions until he's confident enough to build it.
        </p>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Chat messages */}
        <div className="flex-1 flex flex-col">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
            {state.messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                <MessageCircle className="size-12 mb-4 opacity-30" />
                <p className="text-lg font-medium">What do you want to build?</p>
                <p className="text-sm mt-1">Describe your idea and Ralphy will take it from there.</p>
              </div>
            )}
            {state.messages.map((msg, i) => {
              const lastUserIdx = state.messages.length >= 2
                ? state.messages.map((m) => m.role).lastIndexOf("user")
                : -1;
              const showUndo = onUndo && msg.role === "user" && i === lastUserIdx && state.messages.length >= 2;
              return (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div className={`flex items-end gap-1.5 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                    {showUndo && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-6 shrink-0 text-muted-foreground hover:text-foreground opacity-60 hover:opacity-100"
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

          {/* Input */}
          <div className="border-t p-4">
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => fileRef.current?.click()}
                title="Attach files"
                disabled={!state.sessionId}
              >
                <Paperclip className="size-4" />
              </Button>
              <input
                ref={fileRef}
                type="file"
                multiple
                className="hidden"
                onChange={async (e) => {
                  if (!state.sessionId || !e.target.files) return;
                  for (const file of Array.from(e.target.files)) {
                    const form = new FormData();
                    form.append("file", file);
                    await fetch(
                      `${API_URL}/api/sessions/${state.sessionId}/uploads`,
                      { method: "POST", body: form },
                    );
                  }
                  onSend(`[Attached ${e.target.files.length} file(s)]`);
                  e.target.value = "";
                }}
              />
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

        {/* Right sidebar: confidence + ralph it button */}
        <div className="w-64 border-l p-4 flex flex-col gap-4">
          <ConfidenceMeter
            confidence={state.confidence}
            relevance={state.relevance}
            weightedReadiness={state.weightedReadiness}
            questionCount={state.questionCount}
            phase={state.phase}
            ready={state.ready}
          />

          {state.ready && (
            <div className="flex flex-col items-center gap-2">
              {onReviewTasks ? (
                <Button
                  onClick={onReviewTasks}
                  disabled={busy}
                  className="w-full bg-green-600 hover:bg-green-700 text-white"
                  size="lg"
                >
                  <Rocket className="size-4 mr-2" />
                  Review Tasks
                </Button>
              ) : (
                <Button
                  onClick={onRalphIt}
                  disabled={busy}
                  className="w-full bg-green-600 hover:bg-green-700 text-white"
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
              {/* Shown if ralphIt has been loading for >15s (only applies to direct ralph-it flow) */}
              {slowLoad && !onReviewTasks && (
                <p className="text-xs text-muted-foreground text-center">
                  This is taking a while...
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
