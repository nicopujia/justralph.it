/**
 * TypingIndicator -- assistant "thinking" bubble with bouncing dots.
 *
 * Context message rotates based on elapsed seconds:
 *   0-2s  -> "Analyzing your message..."
 *   3-5s  -> "Evaluating requirements..."
 *   6s+   -> "Generating response..."
 *
 * Pass `compact` for the sidebar (xs text, tighter padding).
 */

type TypingIndicatorProps = {
  elapsedSeconds: number;
  compact?: boolean;
};

const PHASES: { threshold: number; label: string }[] = [
  { threshold: 6, label: "Generating response..." },
  { threshold: 3, label: "Evaluating requirements..." },
  { threshold: 0, label: "Analyzing your message..." },
];

function contextMessage(elapsed: number): string {
  for (const phase of PHASES) {
    if (elapsed >= phase.threshold) return phase.label;
  }
  return PHASES[PHASES.length - 1].label;
}

export function TypingIndicator({ elapsedSeconds, compact = false }: TypingIndicatorProps) {
  const label = contextMessage(elapsedSeconds);

  if (compact) {
    return (
      <div className="py-2 border-b border-border flex items-center gap-2">
        <span className="text-muted-foreground text-xs">$</span>
        <span className="text-xs text-muted-foreground italic">{label}</span>
        <span className="flex items-center gap-[3px]">
          <span className="typing-dot inline-block size-1 rounded-full bg-primary" />
          <span className="typing-dot inline-block size-1 rounded-full bg-primary" />
          <span className="typing-dot inline-block size-1 rounded-full bg-primary" />
        </span>
      </div>
    );
  }

  return (
    <div className="py-3 border-b border-border flex items-center gap-3">
      <span className="text-foreground font-bold text-sm shrink-0">$</span>
      <span className="text-sm text-muted-foreground italic">{label}</span>
      <span className="flex items-center gap-1">
        <span className="typing-dot inline-block size-1.5 rounded-full bg-primary" />
        <span className="typing-dot inline-block size-1.5 rounded-full bg-primary" />
        <span className="typing-dot inline-block size-1.5 rounded-full bg-primary" />
      </span>
    </div>
  );
}
