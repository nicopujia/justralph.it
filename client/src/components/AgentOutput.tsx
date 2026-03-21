import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Terminal, GitBranch } from "lucide-react";
import { DiffViewer } from "./DiffViewer";

type AgentOutputProps = {
  lines: string[];
};

type Tab = "terminal" | "changes";

export function AgentOutput({ lines }: AgentOutputProps) {
  const [activeTab, setActiveTab] = useState<Tab>("terminal");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll terminal to bottom on new lines
  useEffect(() => {
    if (activeTab !== "terminal") return;
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines.length, activeTab]);

  return (
    <Card className="flex flex-col overflow-hidden h-full">
      <CardHeader className="pb-0 px-4 py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            {activeTab === "terminal" ? (
              <Terminal className="size-4" />
            ) : (
              <GitBranch className="size-4" />
            )}
            Agent Output
          </CardTitle>
          {/* Tab strip */}
          <div className="flex gap-1">
            <TabButton
              active={activeTab === "terminal"}
              onClick={() => setActiveTab("terminal")}
              icon={<Terminal className="size-3" />}
              label="Terminal"
            />
            <TabButton
              active={activeTab === "changes"}
              onClick={() => setActiveTab("changes")}
              icon={<GitBranch className="size-3" />}
              label="Changes"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        {activeTab === "terminal" ? (
          <div
            ref={scrollRef}
            className="h-full overflow-y-auto bg-zinc-900 text-green-400 font-mono text-sm p-4 terminal-scroll"
          >
            {lines.length === 0 ? (
              <span className="text-zinc-500">
                Waiting for agent output<span className="animate-pulse">_</span>
              </span>
            ) : (
              lines.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap leading-relaxed">
                  {line}
                </div>
              ))
            )}
          </div>
        ) : (
          <DiffViewer lines={lines} />
        )}
      </CardContent>
    </Card>
  );
}

// Small reusable tab button -- active state uses bottom border highlight
function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={[
        "flex items-center gap-1 px-2 py-1 text-xs rounded-sm transition-colors",
        active
          ? "text-zinc-100 border-b-2 border-zinc-100 bg-zinc-800/60"
          : "text-zinc-500 border-b-2 border-transparent hover:text-zinc-300 hover:bg-zinc-800/30",
      ].join(" ")}
    >
      {icon}
      {label}
    </button>
  );
}
