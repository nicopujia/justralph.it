import type { Confidence } from "@/hooks/useChatbot";

/** Per-dimension suggestion chips shown after assistant replies. */
const DIMENSION_CHIPS: Record<keyof Confidence, string[]> = {
  functional: ["Web app", "Mobile app", "CLI tool"],
  technical_stack: ["Python + FastAPI", "TypeScript + Next.js", "I'm not sure yet"],
  data_model: ["Users + posts + comments", "Simple key-value store", "No database needed"],
  auth: ["Email + password", "GitHub OAuth", "No auth needed"],
  deployment: ["Vercel", "AWS", "Self-hosted"],
  testing: ["Unit tests only", "E2E with Playwright", "No tests needed"],
  edge_cases: ["Rate limiting", "Offline support", "Skip this"],
};

const EARLY_PHASE_CHIPS = ["Web app", "Mobile app", "CLI tool"];
const FALLBACK_CHIPS = ["Tell me more", "I'm not sure", "Skip this"];

/**
 * Determine which dimension is currently being explored.
 * Returns the dimension with the lowest non-zero confidence weight,
 * i.e. the one Ralphy is most likely asking about right now.
 */
function inferActiveDimension(
  confidence: Confidence,
): keyof Confidence | null {
  const dims = Object.keys(confidence) as (keyof Confidence)[];
  // Find dimensions with low confidence (below 0.5)
  const low = dims.filter((d) => confidence[d] < 0.5);
  if (low.length === 0) return null;
  // Pick the one with lowest confidence
  return low.reduce((a, b) => (confidence[a] <= confidence[b] ? a : b));
}

type SuggestionChipsProps = {
  confidence: Confidence;
  /** Number of questions asked so far -- used to show early-phase chips. */
  questionCount: number;
  /** Called with the chip text when user clicks */
  onSelect: (text: string) => void;
  visible: boolean;
};

function resolveChips(confidence: Confidence, questionCount: number): string[] {
  // Early phase: first 3 questions get project-type chips
  if (questionCount <= 3) return EARLY_PHASE_CHIPS;
  const dim = inferActiveDimension(confidence);
  return dim ? DIMENSION_CHIPS[dim] : FALLBACK_CHIPS;
}

/**
 * Clickable suggestion chips shown after each assistant message.
 * Contextual to the current conversation phase and dimension.
 */
export function SuggestionChips({
  confidence,
  questionCount,
  onSelect,
  visible,
}: SuggestionChipsProps) {
  if (!visible) return null;

  const chips = resolveChips(confidence, questionCount);

  return (
    <div className="flex flex-wrap gap-2 px-6 pb-3 pt-1">
      {chips.map((chip) => (
        <button
          key={chip}
          onClick={() => onSelect(chip)}
          className="px-3 py-1 rounded-full text-xs bg-muted text-muted-foreground border border-border hover:bg-primary hover:text-primary-foreground hover:border-primary transition-colors"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}

/** Compact variant for sidebar mode. */
export function SuggestionChipsSidebar({
  confidence,
  questionCount,
  onSelect,
  visible,
}: SuggestionChipsProps) {
  if (!visible) return null;

  const chips = resolveChips(confidence, questionCount);

  return (
    <div className="flex flex-wrap gap-1.5 px-2 pb-2">
      {chips.map((chip) => (
        <button
          key={chip}
          onClick={() => onSelect(chip)}
          className="px-2 py-0.5 rounded-full text-xs bg-muted text-muted-foreground border border-border hover:bg-primary hover:text-primary-foreground hover:border-primary transition-colors"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}
