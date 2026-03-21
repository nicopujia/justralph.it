import { useState, useEffect } from "react";

/** Returns a human-readable relative time string for a Unix ms timestamp. */
export function formatRelativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 10) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;

  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;

  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

/**
 * Returns a reactive relative-time string that updates every 30s.
 * Returns null if timestamp is not provided.
 */
export function useRelativeTime(timestamp: number | undefined): string | null {
  const [label, setLabel] = useState<string | null>(
    timestamp != null ? formatRelativeTime(timestamp) : null,
  );

  useEffect(() => {
    if (timestamp == null) return;
    // Update immediately when timestamp changes
    setLabel(formatRelativeTime(timestamp));

    const id = setInterval(() => {
      setLabel(formatRelativeTime(timestamp));
    }, 30_000);

    return () => clearInterval(id);
  }, [timestamp]);

  return label;
}
