import { useEffect, useRef } from "react";
import { GitBranch } from "lucide-react";

type DiffViewerProps = {
  lines: string[];
};

// Classify a diff line to determine its styling
function classifyLine(line: string): {
  bg: string;
  text: string;
  bold: boolean;
  borderTop: boolean;
} {
  if (line.startsWith("diff --git")) {
    return { bg: "", text: "text-zinc-100", bold: true, borderTop: true };
  }
  if (line.startsWith("+++ ") || line.startsWith("--- ")) {
    return { bg: "", text: "text-cyan-400 font-bold", bold: true, borderTop: false };
  }
  if (line.startsWith("@@")) {
    return { bg: "", text: "text-purple-400", bold: false, borderTop: false };
  }
  if (line.startsWith("+")) {
    return {
      bg: "bg-green-900/30",
      text: "text-green-300",
      bold: false,
      borderTop: false,
    };
  }
  if (line.startsWith("-")) {
    return {
      bg: "bg-red-900/30",
      text: "text-red-300",
      bold: false,
      borderTop: false,
    };
  }
  return { bg: "", text: "text-zinc-300", bold: false, borderTop: false };
}

// Returns true if the lines array contains recognisable diff content
function hasDiffContent(lines: string[]): boolean {
  return lines.some(
    (l) =>
      l.startsWith("diff --git") ||
      l.startsWith("+++ ") ||
      l.startsWith("--- ") ||
      l.startsWith("@@")
  );
}

export function DiffViewer({ lines }: DiffViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines.length]);

  const showPlaceholder = lines.length === 0 || !hasDiffContent(lines);

  return (
    <div
      ref={scrollRef}
      className="h-full overflow-y-auto bg-zinc-950 font-mono text-sm p-4 scroll-smooth"
    >
      {showPlaceholder ? (
        <div className="flex flex-col items-center justify-center h-full gap-2 text-zinc-500">
          <GitBranch className="size-5" />
          <span>No changes detected yet</span>
        </div>
      ) : (
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, i) => {
              const { bg, text, bold, borderTop } = classifyLine(line);
              return (
                <tr
                  key={i}
                  className={`${bg} ${borderTop ? "border-t border-zinc-700 mt-2" : ""}`}
                >
                  {/* line number gutter */}
                  <td className="select-none text-zinc-500 w-12 min-w-12 pr-4 text-right align-top leading-relaxed">
                    {i + 1}
                  </td>
                  {/* diff line */}
                  <td
                    className={`${text} ${bold ? "font-bold" : ""} whitespace-pre-wrap leading-relaxed w-full`}
                  >
                    {line}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
