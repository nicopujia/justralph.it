import { useState, useCallback, useEffect } from "react";

/** Stable ID for a chat message: "role:content". */
export function msgId(role: string, content: string): string {
  return `${role}:${content}`;
}

const STORAGE_PREFIX = "pinned_messages_";

function loadPins(sessionId: string): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + sessionId);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function savePins(sessionId: string, pins: string[]): void {
  try {
    localStorage.setItem(STORAGE_PREFIX + sessionId, JSON.stringify(pins));
  } catch {
    // storage unavailable -- silently ignore
  }
}

export type UsePinnedMessages = {
  pinnedIds: Set<string>;
  isPinned: (id: string) => boolean;
  togglePin: (id: string) => void;
};

/**
 * Manages pinned message IDs in localStorage, keyed by sessionId.
 * Returns empty set when sessionId is null.
 */
export function usePinnedMessages(sessionId: string | null): UsePinnedMessages {
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(new Set());

  // Reload from localStorage when session changes
  useEffect(() => {
    if (!sessionId) {
      setPinnedIds(new Set());
      return;
    }
    setPinnedIds(new Set(loadPins(sessionId)));
  }, [sessionId]);

  const togglePin = useCallback(
    (id: string) => {
      if (!sessionId) return;
      setPinnedIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) {
          next.delete(id);
        } else {
          next.add(id);
        }
        savePins(sessionId, Array.from(next));
        return next;
      });
    },
    [sessionId],
  );

  const isPinned = useCallback((id: string) => pinnedIds.has(id), [pinnedIds]);

  return { pinnedIds, isPinned, togglePin };
}
