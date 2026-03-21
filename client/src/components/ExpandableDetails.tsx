import { useState } from "react";
import type { MessageMetadata } from "@/hooks/useChatbot";

type Section = "confidence" | "phase" | "raw";

type SectionConfig = {
  id: Section;
  label: string;
};

const SECTIONS: SectionConfig[] = [
  { id: "confidence", label: "Confidence scores" },
  { id: "phase", label: "Phase info" },
  { id: "raw", label: "Raw response" },
];

/** Formats a 0-1 float as a percentage string. */
function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

/** Single collapsible section with a toggle header. */
function Section({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-2 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors bg-muted/40 hover:bg-muted/60"
        aria-expanded={open}
      >
        <span className="uppercase tracking-wider font-medium">{label}</span>
        <span className="font-mono text-[10px] select-none">{open ? "[-]" : "[+]"}</span>
      </button>
      {open && (
        <div className="px-3 py-2 bg-muted/20 text-xs font-mono text-muted-foreground">
          {children}
        </div>
      )}
    </div>
  );
}

type ExpandableDetailsProps = {
  metadata: MessageMetadata;
  /** If true, renders a compact single "details" toggle instead of individual sections. */
  compact?: boolean;
};

/**
 * Progressive disclosure panel for assistant messages.
 * Shows confidence scores, phase info, and raw API response.
 * All sections collapsed by default.
 */
export function ExpandableDetails({ metadata, compact = false }: ExpandableDetailsProps) {
  const [open, setOpen] = useState(false);

  const confidenceRows = Object.entries(metadata.confidence).map(([k, v]) => ({
    key: k.replace(/_/g, " "),
    conf: v as number,
    rel: (metadata.relevance as Record<string, number>)[k] ?? 1,
  }));

  if (compact) {
    return (
      <div className="mt-1 ml-4">
        <button
          onClick={() => setOpen((v) => !v)}
          className="text-[10px] text-muted-foreground/60 hover:text-muted-foreground transition-colors uppercase tracking-wider"
          aria-expanded={open}
        >
          {open ? "hide details" : "···"}
        </button>
        {open && (
          <div className="mt-1 space-y-1">
            {SECTIONS.map((s) => (
              <Section key={s.id} label={s.label}>
                <SectionContent id={s.id} metadata={metadata} confidenceRows={confidenceRows} />
              </Section>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mt-2 ml-4 space-y-1">
      {/* Top-level toggle */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-[11px] text-muted-foreground/60 hover:text-muted-foreground transition-colors uppercase tracking-wider"
        aria-expanded={open}
      >
        {open ? "hide details" : "details"}
      </button>
      {open && (
        <div className="space-y-1">
          {SECTIONS.map((s) => (
            <Section key={s.id} label={s.label}>
              <SectionContent id={s.id} metadata={metadata} confidenceRows={confidenceRows} />
            </Section>
          ))}
        </div>
      )}
    </div>
  );
}

type ConfidenceRow = { key: string; conf: number; rel: number };

function SectionContent({
  id,
  metadata,
  confidenceRows,
}: {
  id: Section;
  metadata: MessageMetadata;
  confidenceRows: ConfidenceRow[];
}) {
  if (id === "confidence") {
    return (
      <table className="w-full border-collapse">
        <thead>
          <tr className="text-[10px] text-muted-foreground/60">
            <th className="text-left font-normal py-0.5 pr-3">dimension</th>
            <th className="text-right font-normal py-0.5 pr-3">confidence</th>
            <th className="text-right font-normal py-0.5">relevance</th>
          </tr>
        </thead>
        <tbody>
          {confidenceRows.map(({ key, conf, rel }) => (
            <tr key={key}>
              <td className="py-0.5 pr-3 capitalize">{key}</td>
              <td className="text-right py-0.5 pr-3">{pct(conf)}</td>
              <td className="text-right py-0.5">{pct(rel)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (id === "phase") {
    return (
      <dl className="space-y-0.5">
        <div className="flex gap-3">
          <dt className="text-muted-foreground/60 w-28 shrink-0">phase</dt>
          <dd>{metadata.phase}</dd>
        </div>
        <div className="flex gap-3">
          <dt className="text-muted-foreground/60 w-28 shrink-0">questions asked</dt>
          <dd>{metadata.questionCount}</dd>
        </div>
        <div className="flex gap-3">
          <dt className="text-muted-foreground/60 w-28 shrink-0">readiness</dt>
          <dd>{pct(metadata.weightedReadiness)}</dd>
        </div>
      </dl>
    );
  }

  if (id === "raw") {
    return (
      <pre className="text-[10px] whitespace-pre-wrap break-all leading-relaxed max-h-48 overflow-y-auto">
        {JSON.stringify(metadata.rawResponse, null, 2)}
      </pre>
    );
  }

  return null;
}
