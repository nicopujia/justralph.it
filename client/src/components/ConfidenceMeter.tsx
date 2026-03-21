import { useState } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import type { Confidence, Relevance } from "@/hooks/useChatbot";

const DIMENSION_LABELS: Record<keyof Confidence, string> = {
  functional: "FUNCTIONAL",
  technical_stack: "TECH STACK",
  data_model: "DATA MODEL",
  auth: "AUTH",
  deployment: "DEPLOYMENT",
  testing: "TESTING",
  edge_cases: "EDGE CASES",
};

// Human-readable descriptions shown in tooltips per dimension.
const DIMENSION_DESCRIPTIONS: Record<keyof Confidence, string> = {
  functional: "Features, user stories, core behavior. Describe what users can do.",
  technical_stack: "Languages, frameworks, infra. Specify your preferred stack.",
  data_model: "Entities, relationships, storage. Describe your data and how it relates.",
  auth: "Login, roles, permissions. Explain who accesses what and how.",
  deployment: "Hosting, CI/CD, environments. Where and how will this run?",
  testing: "Test strategy, coverage. What level of testing do you expect?",
  edge_cases: "Error handling, validation, limits. What can go wrong?",
};

type ConfidenceMeterProps = {
  confidence: Confidence;
  relevance: Relevance;
  weightedReadiness: number;
  questionCount: number;
  phase: number;
  ready: boolean;
  onDimensionClick?: (dimension: string) => void;
};

// Render 10 VU meter blocks based on a 0-100 score.
// Colors use semantic design tokens: success / warning / error.
function VuBlocks({ score }: { score: number }) {
  const filled = Math.round(score / 10);
  const fillColor =
    score >= 80 ? "bg-[var(--color-success)]" : score >= 50 ? "bg-[var(--color-warning)]" : "bg-[var(--color-error)]";

  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 10 }, (_, i) => (
        <div
          key={i}
          className={`flex-1 h-3 border border-border ${i < filled ? fillColor : "bg-muted"}`}
        />
      ))}
    </div>
  );
}

export function ConfidenceMeter({
  confidence,
  relevance,
  weightedReadiness,
  questionCount,
  phase,
  ready,
  onDimensionClick,
}: ConfidenceMeterProps) {
  const dims = Object.entries(confidence) as [keyof Confidence, number][];
  // Track which dimension is hovered for the "ASK" hint
  const [hoveredDim, setHoveredDim] = useState<string | null>(null);

  return (
    <Tooltip.Provider delayDuration={300}>
      <div className="space-y-3 font-mono">
        {/* Overall readiness */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs tracking-wider">
            <span className="text-muted-foreground uppercase">READINESS</span>
            {ready ? (
              <span className="text-primary uppercase">READY</span>
            ) : (
              <span className="text-primary tabular-nums">{Math.round(weightedReadiness)}%</span>
            )}
          </div>
          <VuBlocks score={weightedReadiness} />
        </div>

        {/* Phase + question count */}
        <div className="flex justify-between text-xs tracking-wider">
          <span className="text-muted-foreground">PHASE {phase}/4</span>
          <span className="text-muted-foreground">
            Q:{String(questionCount).padStart(2, "0")}/{questionCount < 10 ? "10 MIN" : "10"}
          </span>
        </div>

        <div className="h-px bg-border" />

        {/* Per-dimension VU meters */}
        {dims.map(([key, value]) => {
          const rel = relevance[key as keyof Relevance] ?? 1.0;
          const isIrrelevant = rel <= 0.3;
          const isHovered = hoveredDim === key;
          const clickable = !!onDimensionClick;

          // Only flag dimensions as weak once the user has meaningful progress (>=30% readiness)
          const isWeak = !isIrrelevant && value < 50 && !ready && weightedReadiness >= 30;

          return (
            <div
              key={key}
              className={`space-y-1 px-1 -mx-1 transition-colors ${
                clickable ? "cursor-crosshair" : ""
              } ${isHovered && clickable ? "border border-primary outline outline-primary" : ""} ${
                isWeak && clickable ? "animate-pulse" : ""
              }`}
              style={{ opacity: isIrrelevant ? 0.35 : 1 }}
              onClick={() => clickable && onDimensionClick(key)}
              onMouseEnter={() => clickable && setHoveredDim(key)}
              onMouseLeave={() => setHoveredDim(null)}
            >
              <div className="flex justify-between items-center text-xs tracking-wider">
                <span className="flex items-center gap-1 text-muted-foreground">
                  {DIMENSION_LABELS[key]}
                  {isIrrelevant && (
                    <span className="text-muted-foreground ml-1">(N/A)</span>
                  )}
                  {/* Weak dimension indicator */}
                  {isWeak && clickable && (
                    <span className="text-[var(--color-error)] text-[9px] tracking-widest">NEEDS ATTENTION</span>
                  )}
                  {/* "Ask about this" hint -- only visible on hover */}
                  {isHovered && clickable && !isIrrelevant && !isWeak && (
                    <span className="text-primary text-[10px]">ASK</span>
                  )}
                  {/* Info tooltip -- explains what this dimension measures */}
                  <DimensionTooltip dimension={key} />
                </span>
                <span className="text-primary tabular-nums">{value}%</span>
              </div>
              <VuBlocks score={value} />
            </div>
          );
        })}
      </div>
    </Tooltip.Provider>
  );
}

// Small info icon that reveals a tooltip explaining the dimension.
// Stops click propagation so it doesn't trigger the parent "ASK" handler.
function DimensionTooltip({ dimension }: { dimension: keyof Confidence }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center justify-center text-muted-foreground opacity-50 hover:opacity-100 transition-opacity focus:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          onClick={(e) => e.stopPropagation()}
          aria-label={`Info: ${DIMENSION_LABELS[dimension]}`}
        >
          <svg
            width="10"
            height="10"
            viewBox="0 0 10 10"
            fill="currentColor"
            aria-hidden="true"
          >
            <circle cx="5" cy="5" r="4.5" stroke="currentColor" strokeWidth="1" fill="none" />
            <rect x="4.4" y="4" width="1.2" height="3.5" rx="0.3" />
            <circle cx="5" cy="2.8" r="0.6" />
          </svg>
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          sideOffset={6}
          className="z-50 max-w-[200px] border border-border bg-popover px-2.5 py-1.5 font-mono text-[10px] leading-tight tracking-wide text-popover-foreground shadow-md"
        >
          {DIMENSION_DESCRIPTIONS[dimension]}
          <Tooltip.Arrow className="fill-border" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
