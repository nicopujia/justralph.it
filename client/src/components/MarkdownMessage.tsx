import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

// Custom renderers styled for the app's dark terminal aesthetic.
const components: Components = {
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 text-foreground">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-bold text-foreground">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  h1: ({ children }) => (
    <h1 className="text-base font-bold uppercase tracking-wider mb-2 text-foreground">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-sm font-bold uppercase tracking-wider mb-2 text-foreground">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold mb-1 text-foreground">{children}</h3>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-inside mb-2 space-y-0.5 text-foreground">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside mb-2 space-y-0.5 text-foreground">{children}</ol>
  ),
  li: ({ children }) => <li className="text-foreground">{children}</li>,
  // Fenced code blocks
  code: ({ className, children, ...props }) => {
    const isBlock = Boolean(className);
    if (isBlock) {
      return (
        <code
          className="block bg-zinc-800 text-zinc-200 font-mono text-xs p-3 rounded overflow-x-auto whitespace-pre"
          {...props}
        >
          {children}
        </code>
      );
    }
    // Inline code
    return (
      <code
        className="bg-zinc-700 text-zinc-200 font-mono text-xs px-1 rounded"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="mb-2 last:mb-0">{children}</pre>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-400 underline hover:text-blue-300 transition-colors"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-border pl-3 text-muted-foreground italic mb-2">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-border my-2" />,
};

type Props = {
  content: string;
  /** Extra classes applied to the wrapper div. */
  className?: string;
};

/** Renders assistant markdown content with GFM support. */
export function MarkdownMessage({ content, className = "" }: Props) {
  return (
    <div className={["text-sm leading-relaxed", className].filter(Boolean).join(" ")}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
