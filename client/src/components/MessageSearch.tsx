import { useEffect, useRef } from "react";
import { X, ChevronUp, ChevronDown } from "lucide-react";

type MessageSearchProps = {
  query: string;
  onChange: (q: string) => void;
  /** Total number of matching segments across all messages. */
  matchCount: number;
  /** 0-based index of the currently focused match. */
  activeMatch: number;
  onNext: () => void;
  onPrev: () => void;
  onClose: () => void;
};

/**
 * Floating search bar rendered at the top of the message list.
 * Auto-focuses the input when mounted.
 */
export function MessageSearch({
  query,
  onChange,
  matchCount,
  activeMatch,
  onNext,
  onPrev,
  onClose,
}: MessageSearchProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.shiftKey ? onPrev() : onNext();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      onNext();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      onPrev();
    }
  };

  const countLabel =
    matchCount === 0
      ? "NO MATCHES"
      : `${activeMatch + 1} OF ${matchCount}`;

  return (
    <div className="flex items-center gap-1 px-3 py-1.5 border-b border-border bg-card shrink-0">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="SEARCH..."
        className="flex-1 bg-transparent text-xs text-primary placeholder:text-muted-foreground outline-none border border-border px-2 py-1 focus:border-primary transition-colors"
        aria-label="Search messages"
      />
      <span
        className="text-xs text-muted-foreground font-mono shrink-0 min-w-[7rem] text-center uppercase tracking-wider"
        aria-live="polite"
      >
        {query ? countLabel : ""}
      </span>
      <button
        onClick={onPrev}
        disabled={matchCount === 0}
        title="Previous match (Shift+Enter)"
        className="text-muted-foreground hover:text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronUp className="size-3.5" />
      </button>
      <button
        onClick={onNext}
        disabled={matchCount === 0}
        title="Next match (Enter)"
        className="text-muted-foreground hover:text-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronDown className="size-3.5" />
      </button>
      <button
        onClick={onClose}
        title="Close search (Escape)"
        className="text-muted-foreground hover:text-primary transition-colors"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}

/**
 * Split `text` into alternating plain/match segments for a case-insensitive
 * search of `query`. Returns an array of `{ text, isMatch }` objects.
 *
 * When `query` is empty every segment is plain.
 */
export function splitHighlight(
  text: string,
  query: string
): { text: string; isMatch: boolean }[] {
  if (!query) return [{ text, isMatch: false }];
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(escaped, "gi");
  const parts: { text: string; isMatch: boolean }[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, m.index), isMatch: false });
    }
    parts.push({ text: m[0], isMatch: true });
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), isMatch: false });
  }
  return parts.length ? parts : [{ text, isMatch: false }];
}
