import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageCircle, Send, Loader2, Rocket, Paperclip } from "lucide-react";
import { API_URL } from "@/lib/config";
import { ConfidenceMeter } from "./ConfidenceMeter";
import type { ChatState } from "@/hooks/useChatbot";

type ChatPanelProps = {
  state: ChatState;
  onSend: (message: string) => void;
  onRalphIt: () => void;
  /** "full" = Phase 1 fullscreen; "sidebar" = Phase 2 collapsed sidebar. */
  mode?: "full" | "sidebar";
};

export function ChatPanel({ state, onSend, onRalphIt, mode = "full" }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [state.messages.length]);

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || state.loading) return;
    setInput("");
    onSend(msg);
  };

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
          {state.messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
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
          ))}
          {state.loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-md px-2.5 py-1.5">
                <Loader2 className="size-3 animate-spin" />
              </div>
            </div>
          )}
        </div>

        {/* Ralph It button (sidebar) */}
        {state.ready && (
          <div className="px-2 pb-2 shrink-0">
            <Button
              onClick={onRalphIt}
              disabled={state.loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white text-xs h-8"
              size="sm"
            >
              <Rocket className="size-3 mr-1" />
              Ralph It
            </Button>
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
              disabled={state.loading}
              className="flex-1 h-7 text-xs"
            />
            <Button
              onClick={handleSend}
              disabled={state.loading || !input.trim()}
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
            {state.messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
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
            ))}
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
                disabled={state.loading}
                className="flex-1"
              />
              <Button onClick={handleSend} disabled={state.loading || !input.trim()} size="icon">
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
            <Button
              onClick={onRalphIt}
              disabled={state.loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white"
              size="lg"
            >
              <Rocket className="size-4 mr-2" />
              Just Ralph It
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
