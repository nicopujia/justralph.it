import { useEffect, useState } from "react";
import { MarkdownMessage } from "./MarkdownMessage";
import { API_URL } from "@/lib/config";

type SharedMessage = {
  role: "user" | "assistant";
  content: string;
  created_at: number;
};

type SharedSession = {
  id: string;
  name: string;
  github_url: string;
  status: string;
  created_at: number;
};

type SharedData = {
  session: SharedSession;
  messages: SharedMessage[];
  state: Record<string, unknown>;
};

type Props = {
  shareToken: string;
};

/**
 * Read-only view of a shared session. Fetches data from the public
 * /api/shared/{token} endpoint -- no auth required.
 */
export function SharedView({ shareToken }: Props) {
  const [data, setData] = useState<SharedData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/shared/${shareToken}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<SharedData>;
      })
      .then(setData)
      .catch(() => setError("Session not found or link has expired."));
  }, [shareToken]);

  if (error) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center font-mono">
        <div className="text-center space-y-3">
          <p className="text-[#FF0033] text-sm uppercase tracking-widest">{error}</p>
          <a
            href="/"
            className="text-[#00FF41] text-xs uppercase tracking-wider underline hover:opacity-80"
          >
            Go to justralph.it
          </a>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <span className="text-[#00FF41] text-sm font-mono uppercase tracking-widest">
          LOADING...<span className="animate-blink">_</span>
        </span>
      </div>
    );
  }

  const { session, messages } = data;
  const displayName = session.name || `Session ${session.id.slice(0, 8)}`;

  return (
    <div className="min-h-screen bg-background text-foreground font-mono flex flex-col">
      {/* Header */}
      <div className="border-b border-border px-4 py-3 flex items-center justify-between bg-card">
        <div className="flex items-center gap-3">
          <span className="text-primary text-xs uppercase tracking-widest font-bold">
            JUSTRALPH.IT
          </span>
          <span className="text-muted-foreground text-xs">|</span>
          <span className="text-foreground text-xs uppercase tracking-wider">
            {displayName}
          </span>
          {session.github_url && (
            <a
              href={session.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary text-xs underline hover:opacity-80 uppercase tracking-wider"
            >
              GitHub
            </a>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground uppercase tracking-widest px-1.5 py-0.5 border border-border">
            READ-ONLY
          </span>
          <span
            className={`text-[10px] uppercase tracking-widest px-1.5 py-0.5 border ${
              session.status === "running"
                ? "border-[#00FF41] text-[#00FF41]"
                : "border-border text-muted-foreground"
            }`}
          >
            {session.status}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 max-w-3xl mx-auto w-full space-y-4">
        {messages.length === 0 ? (
          <p className="text-muted-foreground text-xs uppercase tracking-wider text-center py-12">
            No messages in this session.
          </p>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] px-3 py-2 border text-sm ${
                  msg.role === "user"
                    ? "border-primary text-foreground bg-primary/5"
                    : "border-border text-foreground bg-card"
                }`}
              >
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                  {msg.role === "user" ? "USER" : "RALPH"}
                </div>
                {msg.role === "assistant" ? (
                  <MarkdownMessage content={msg.content} />
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-border px-4 py-2 text-center">
        <a
          href="/"
          className="text-[10px] text-muted-foreground uppercase tracking-widest hover:text-primary transition-colors"
        >
          Build your own at justralph.it
        </a>
      </div>
    </div>
  );
}
