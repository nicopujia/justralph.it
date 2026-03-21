import { useState } from "react";
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
function VuBlocks({ score }: { score: number }) {
  const filled = Math.round(score / 10);
  // Color is determined by the overall score level, not per-block.
  const fillColor =
    score >= 80 ? "bg-[#00FF41]" : score >= 50 ? "bg-[#FFaa00]" : "bg-[#FF0033]";

  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 10 }, (_, i) => (
        <div
          key={i}
          className={`flex-1 h-3 border border-[#1a1a1a] ${i < filled ? fillColor : "bg-[#111]"}`}
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
  // Track which dimension is hovered for tooltip
  const [hoveredDim, setHoveredDim] = useState<string | null>(null);

  return (
    <div className="space-y-3 font-mono">
      {/* Overall readiness */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs tracking-wider">
          <span className="text-[#333] uppercase">READINESS</span>
          {ready ? (
            <span className="text-[#00FF41] uppercase">READY</span>
          ) : (
            <span className="text-[#00FF41] tabular-nums">{Math.round(weightedReadiness)}%</span>
          )}
        </div>
        <VuBlocks score={weightedReadiness} />
      </div>

      {/* Phase + question count */}
      <div className="flex justify-between text-xs tracking-wider">
        <span className="text-[#333]">PHASE {phase}/4</span>
        <span className="text-[#333]">
          Q:{String(questionCount).padStart(2, "0")}/{questionCount < 10 ? "10 MIN" : "10"}
        </span>
      </div>

      <div className="h-px bg-[#1a1a1a]" />

      {/* Per-dimension VU meters */}
      {dims.map(([key, value]) => {
        const rel = relevance[key as keyof Relevance] ?? 1.0;
        const isIrrelevant = rel <= 0.3;
        const isHovered = hoveredDim === key;
        const clickable = !!onDimensionClick;

        return (
          <div
            key={key}
            className={`space-y-1 px-1 -mx-1 transition-colors ${
              clickable ? "cursor-crosshair" : ""
            } ${isHovered && clickable ? "border border-[#00FF41] outline outline-[#00FF41]" : ""}`}
            style={{ opacity: isIrrelevant ? 0.35 : 1 }}
            onClick={() => clickable && onDimensionClick(key)}
            onMouseEnter={() => clickable && setHoveredDim(key)}
            onMouseLeave={() => setHoveredDim(null)}
          >
            <div className="flex justify-between items-center text-xs tracking-wider">
              <span className="flex items-center gap-1 text-[#333]">
                {DIMENSION_LABELS[key]}
                {isIrrelevant && (
                  <span className="text-[#333] ml-1">(N/A)</span>
                )}
                {/* "Ask about this" hint -- only visible on hover */}
                {isHovered && clickable && !isIrrelevant && (
                  <span className="text-[#00FF41] text-[10px]">ASK</span>
                )}
              </span>
              <span className="text-[#00FF41] tabular-nums">{value}%</span>
            </div>
            <VuBlocks score={value} />
          </div>
        );
      })}
    </div>
  );
}
