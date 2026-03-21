import { useState } from "react";
import { MessageCircle } from "lucide-react";
import type { Confidence, Relevance } from "@/hooks/useChatbot";

const DIMENSION_LABELS: Record<keyof Confidence, string> = {
  functional: "Functional",
  technical_stack: "Tech Stack",
  data_model: "Data Model",
  auth: "Auth",
  deployment: "Deployment",
  testing: "Testing",
  edge_cases: "Edge Cases",
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
  // Track which dimension is hovered for tooltip
  const [hoveredDim, setHoveredDim] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      {/* Overall readiness */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium">Readiness</span>
          {ready ? (
            <span className="text-green-600 dark:text-green-400 font-medium">Ready</span>
          ) : (
            <span className="font-mono tabular-nums">{Math.round(weightedReadiness)}%</span>
          )}
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              ready
                ? "bg-green-500"
                : weightedReadiness >= 50
                  ? "bg-yellow-500"
                  : "bg-red-400"
            }`}
            style={{ width: `${Math.min(weightedReadiness, 100)}%` }}
          />
        </div>
      </div>

      {/* Phase + question count */}
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Phase {phase}/4</span>
        <span>
          Q{questionCount}
          {questionCount < 10 && <span className="opacity-60">/10 min</span>}
        </span>
      </div>

      <div className="h-px bg-border" />

      {/* Per-dimension bars */}
      {dims.map(([key, value]) => {
        const rel = relevance[key as keyof Relevance] ?? 1.0;
        const isIrrelevant = rel <= 0.3;
        const isHovered = hoveredDim === key;
        const clickable = !!onDimensionClick;

        return (
          <div
            key={key}
            className={`space-y-1 rounded px-1 -mx-1 transition-colors ${
              clickable ? "cursor-pointer" : ""
            } ${isHovered && clickable ? "bg-muted/60" : ""}`}
            style={{ opacity: isIrrelevant ? 0.35 : 1 }}
            onClick={() => clickable && onDimensionClick(key)}
            onMouseEnter={() => clickable && setHoveredDim(key)}
            onMouseLeave={() => setHoveredDim(null)}
          >
            <div className="flex justify-between items-center text-xs">
              <span className="flex items-center gap-1">
                {DIMENSION_LABELS[key]}
                {isIrrelevant && (
                  <span className="text-muted-foreground ml-1">(N/A)</span>
                )}
                {/* "Ask about this" hint -- only visible on hover */}
                {isHovered && clickable && !isIrrelevant && (
                  <span className="inline-flex items-center gap-0.5 text-primary/70 font-medium">
                    <MessageCircle className="size-2.5" />
                    Ask
                  </span>
                )}
              </span>
              <span className="font-mono tabular-nums">{value}%</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  value >= 70
                    ? "bg-green-500"
                    : value >= 40
                      ? "bg-yellow-500"
                      : "bg-red-400"
                }`}
                style={{ width: `${Math.min(value, 100)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
