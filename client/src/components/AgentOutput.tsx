import { useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Terminal } from "lucide-react";

type AgentOutputProps = {
  lines: string[];
};

export function AgentOutput({ lines }: AgentOutputProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new lines
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines.length]);

  return (
    <Card className="flex flex-col overflow-hidden h-full">
      <CardHeader className="pb-3 px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Terminal className="size-4" />
          Agent Output
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
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
      </CardContent>
    </Card>
  );
}
