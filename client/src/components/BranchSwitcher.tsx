/**
 * BranchSwitcher -- tab bar for selecting conversation branches.
 * Shows "Main" plus any user-created branches.
 * Hidden when there are no branches.
 */

import type { Branch } from "@/hooks/useBranching";
import { GitBranch } from "lucide-react";

type Props = {
  branches: Branch[];
  activeBranchId: string;
  onSwitch: (id: string) => void;
  /** "sm" for sidebar mode, "default" for full mode. */
  size?: "default" | "sm";
};

export function BranchSwitcher({
  branches,
  activeBranchId,
  onSwitch,
  size = "default",
}: Props) {
  if (branches.length === 0) return null;

  const textClass =
    size === "sm"
      ? "text-[10px] px-2 py-1"
      : "text-xs px-3 py-1.5";

  const tabs = [{ id: "main", name: "Main" }, ...branches];

  return (
    <div className="flex items-center gap-0 border-b border-border shrink-0 bg-background overflow-x-auto">
      <GitBranch className="size-3 text-muted-foreground shrink-0 ml-2 mr-1" />
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onSwitch(tab.id)}
          className={[
            textClass,
            "font-mono uppercase tracking-wider whitespace-nowrap transition-colors border-b-2",
            activeBranchId === tab.id
              ? "text-primary border-primary"
              : "text-muted-foreground border-transparent hover:text-primary hover:border-primary/50",
          ].join(" ")}
        >
          {tab.name}
        </button>
      ))}
    </div>
  );
}
