import { useState, useCallback } from "react";
import { Share2, Check, Copy } from "lucide-react";
import { API_URL } from "@/lib/config";

type ShareButtonProps = {
  sessionId: string;
  /** Called with error message on failure. */
  onError?: (msg: string) => void;
};

type ShareState = "idle" | "loading" | "copied" | "shown";

/**
 * Generates a shareable read-only link for the session and copies it to
 * clipboard. Idempotent: re-calling returns the same token.
 */
export function ShareButton({ sessionId, onError }: ShareButtonProps) {
  const [status, setStatus] = useState<ShareState>("idle");
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  const handleShare = useCallback(async () => {
    if (status === "loading") return;
    setStatus("loading");

    try {
      const resp = await fetch(
        `${API_URL}/api/sessions/${sessionId}/share`,
        { method: "POST" },
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      // Build a frontend URL: replace the API origin with window.location.origin
      const token: string = data.share_token;
      const url = `${window.location.origin}/shared/${token}`;
      setShareUrl(url);

      await navigator.clipboard.writeText(url);
      setStatus("copied");
      setTimeout(() => setStatus("shown"), 2000);
    } catch {
      onError?.("Failed to generate share link");
      setStatus("idle");
    }
  }, [sessionId, status, onError]);

  const handleCopyAgain = useCallback(async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setStatus("copied");
      setTimeout(() => setStatus("shown"), 2000);
    } catch {
      onError?.("Clipboard write failed");
    }
  }, [shareUrl, onError]);

  if (status === "shown" && shareUrl) {
    return (
      <div className="flex items-center gap-1">
        <span
          className="font-mono text-[10px] text-primary truncate max-w-[140px]"
          title={shareUrl}
        >
          {shareUrl.replace(/^https?:\/\//, "")}
        </span>
        <button
          onClick={handleCopyAgain}
          title="Copy link again"
          className="p-1 border border-border hover:border-primary text-muted-foreground hover:text-primary transition-colors"
        >
          <Copy className="size-3" />
        </button>
      </div>
    );
  }

  if (status === "copied") {
    return (
      <button
        disabled
        className="flex items-center gap-1 p-1 border border-primary text-primary font-mono text-[10px] uppercase tracking-wider"
      >
        <Check className="size-3" />
        COPIED
      </button>
    );
  }

  return (
    <button
      onClick={handleShare}
      disabled={status === "loading"}
      title="Share session (read-only link)"
      aria-label="Share session"
      className="flex items-center gap-1 p-1 border border-border hover:border-primary text-muted-foreground hover:text-primary transition-colors font-mono text-[10px] uppercase tracking-wider disabled:opacity-50"
    >
      <Share2 className="size-3" />
      {status === "loading" ? "..." : "SHARE"}
    </button>
  );
}
