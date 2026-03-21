import { Terminal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type CodeReaderProps = {
  tasks: Array<{ title: string; lines: string[] }>;
};

export function CodeReader({ tasks }: CodeReaderProps) {
  const [taskIndex, setTaskIndex] = useState(0);
  const [visibleLineCount, setVisibleLineCount] = useState(0);
  const [phase, setPhase] = useState<"typing" | "pause" | "clearing">("typing");

  const activeTask = tasks[taskIndex] ?? tasks[0];
  const visibleLines = useMemo(() => activeTask.lines.slice(0, visibleLineCount), [activeTask.lines, visibleLineCount]);

  useEffect(() => {
    if (!activeTask) {
      return;
    }

    if (phase === "typing") {
      if (visibleLineCount < activeTask.lines.length) {
        const timeout = window.setTimeout(() => setVisibleLineCount(count => count + 1), 160);
        return () => window.clearTimeout(timeout);
      }

      const timeout = window.setTimeout(() => setPhase("pause"), 900);
      return () => window.clearTimeout(timeout);
    }

    if (phase === "pause") {
      const timeout = window.setTimeout(() => setPhase("clearing"), 700);
      return () => window.clearTimeout(timeout);
    }

    if (phase === "clearing") {
      if (visibleLineCount > 0) {
        const timeout = window.setTimeout(() => setVisibleLineCount(count => Math.max(0, count - 1)), 28);
        return () => window.clearTimeout(timeout);
      }

      const timeout = window.setTimeout(() => {
        setTaskIndex(index => (index + 1) % tasks.length);
        setPhase("typing");
      }, 320);
      return () => window.clearTimeout(timeout);
    }
  }, [activeTask, phase, tasks.length, visibleLineCount]);

  return (
    <section className="overflow-hidden rounded-[var(--radius-lg)] border border-[rgba(255,255,255,0.12)] bg-[#090909]">
      <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.08)] px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-foreground">
          <Terminal className="size-4" />
          <span>Agent stdout</span>
        </div>
        <div className="text-sm text-[color:var(--text-secondary)]">{activeTask.title}</div>
      </div>

      <div className="h-[620px] overflow-auto bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.04),transparent_24%)] px-5 py-5 font-mono text-[13px] leading-7 text-[#dbdfeb]">
        <div className="grid gap-1">
          {visibleLines.map((line, index) => (
            <div key={`${taskIndex}-${index}-${line}`} className="grid grid-cols-[40px_1fr] gap-4">
              <span className="select-none text-right text-[#666d78]">{index + 1}</span>
              <span>{line}</span>
            </div>
          ))}

          <div className="mt-2 grid grid-cols-[40px_1fr] gap-4 text-[#8e95a1]">
            <span className="text-right">{Math.max(visibleLines.length, 1)}</span>
            <span className="inline-flex items-center gap-2">
              <span className="size-2 animate-pulse rounded-full bg-[#d8dce7]" />
              {phase === "typing" ? "streaming" : phase === "pause" ? "holding" : "clearing"}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
