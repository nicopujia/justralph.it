/**
 * BranchSwitcher -- tab bar for selecting conversation branches.
 * Shows "Main" plus any user-created branches with readiness %.
 * Hidden when there are no branches.
 */

import type { Branch } from "@/hooks/useBranching";
import { GitBranch } from "lucide-react";

type Props = {
  branches: Branch[];
  activeBranchId: string;
  onSwitch: (id: string) => void;
  /** Current main-branch readiness (shown next to "Main" tab). */
  mainReadiness?: number;
  /** "sm" for sidebar mode, "default" for full mode. */
  size?: "default" | "sm";
};

export function BranchSwitcher({
  branches,
  activeBranchId,
  onSwitch,
  mainReadiness,
  size = "default",
}: Props) {
  if (branches.length === 0) return null;

  const textClass =
    size === "sm"
      ? "text-[10px] px-2 py-1"
      : "text-xs px-3 py-1.5";

  const tabs: { id: string; name: string; readiness?: number }[] = [
    { id: "main", name: "Main", readiness: mainReadiness },
    ...branches.map((b) => ({
      id: b.id,
      name: b.name,
      readiness: b.stateSnapshot?.weightedReadiness,
    })),
  ];

  return (
    <div className="flex items-center gap-0 border-b border-border shrink-0 bg-background overflow-x-auto">
      <GitBranch className="size-3 text-muted-foreground shrink-0 ml-2 mr-1" />
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onSwitch(tab.id)}
          className={[
            textClass,
            "font-mono uppercase tracking-wider whitespace-nowrap transition-colors border-b-2 flex items-center gap-1",
            activeBranchId === tab.id
              ? "text-primary border-primary"
              : "text-muted-foreground border-transparent hover:text-primary hover:border-primary/50",
          ].join(" ")}
        >
          {tab.name}
          {tab.readiness != null && tab.readiness > 0 && (
            <span className="text-[9px] opacity-70 tabular-nums">
              {Math.round(tab.readiness)}%
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
