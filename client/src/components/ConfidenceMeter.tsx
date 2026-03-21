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
};

export function ConfidenceMeter({
  confidence,
  relevance,
  weightedReadiness,
  questionCount,
  phase,
  ready,
}: ConfidenceMeterProps) {
  const dims = Object.entries(confidence) as [keyof Confidence, number][];

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
        return (
          <div key={key} className="space-y-1" style={{ opacity: isIrrelevant ? 0.35 : 1 }}>
            <div className="flex justify-between text-xs">
              <span>
                {DIMENSION_LABELS[key]}
                {isIrrelevant && (
                  <span className="text-muted-foreground ml-1">(N/A)</span>
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
