export function AgentDocumentView({ content }: { content: string }) {
  const lines = content.trim().split("\n");

  return (
    <article className="flex min-h-full w-full items-start justify-start px-4 py-10 sm:px-6">
      <div className="grid w-full max-w-2xl gap-3 text-sm leading-7 text-[#dad7ce]">
        {lines.map((line, index) => {
          if (line.startsWith("# ")) {
            return (
              <h1 key={index} className="text-[1.55rem] tracking-[-0.04em] text-foreground">
                {line.slice(2)}
              </h1>
            );
          }

          if (!line.trim()) {
            return <div key={index} className="h-2" />;
          }

          if (line.startsWith("- ")) {
            return (
              <p key={index} className="pl-4 text-[color:var(--text-secondary)]">
                • {line.slice(2)}
              </p>
            );
          }

          return (
            <p key={index} className={line.endsWith("ive") || line === "Constraints" || line === "Open" || line === "Rule" ? "text-foreground" : "text-[color:var(--text-secondary)]"}>
              {line}
            </p>
          );
        })}
      </div>
    </article>
  );
}
