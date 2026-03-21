/**
 * useBranching -- conversation tree management.
 *
 * Each branch is an independent list of messages forked from a specific index
 * in the parent branch. Branches are persisted to localStorage under a key
 * derived from the session ID.
 *
 * Constraints:
 * - Max MAX_BRANCHES per session (oldest non-main branch auto-pruned).
 * - Branch from any user message; the fork point is inclusive (messages up to
 *   and including that index are copied into the new branch).
 */

import { useState, useCallback, useEffect } from "react";
import type { ChatMessage } from "./useChatbot";

export const MAX_BRANCHES = 5;

export type Branch = {
  id: string;
  /** Human-readable label shown in the switcher. */
  name: string;
  /** Messages on this branch (copied up to fork point + any new messages). */
  messages: ChatMessage[];
  /** Index (0-based) of the last shared message from the parent branch. */
  forkIndex: number;
  createdAt: number;
};

type BranchStore = {
  /** ID of the currently active branch. "main" is the default. */
  activeBranchId: string;
  branches: Branch[];
};

function lsKey(sessionId: string) {
  return `ralph_branches_${sessionId}`;
}

function loadStore(sessionId: string): BranchStore | null {
  try {
    const raw = localStorage.getItem(lsKey(sessionId));
    return raw ? (JSON.parse(raw) as BranchStore) : null;
  } catch {
    return null;
  }
}

function saveStore(sessionId: string, store: BranchStore) {
  try {
    localStorage.setItem(lsKey(sessionId), JSON.stringify(store));
  } catch {
    // quota exceeded -- silently ignore
  }
}

function makeId() {
  return Math.random().toString(36).slice(2, 9);
}

type UseBranchingReturn = {
  /** All branches for the session. */
  branches: Branch[];
  /** Currently active branch ("main" or a branch id). */
  activeBranchId: string;
  /** Messages to display (from the active branch). */
  activeMessages: ChatMessage[];
  /**
   * Create a new branch forked from `forkIndex` (inclusive).
   * Returns the id of the new branch.
   */
  branchFrom: (allMessages: ChatMessage[], forkIndex: number) => string;
  /** Switch the active branch. */
  switchBranch: (id: string) => void;
  /**
   * Update messages on the active branch (called whenever the chatbot state
   * changes -- main branch messages are always mirrored from chatbot state,
   * so this only matters for non-main branches).
   */
  setActiveBranchMessages: (messages: ChatMessage[]) => void;
  /** Whether the current branch is the main branch. */
  isMainBranch: boolean;
};

/**
 * @param sessionId - current chat session ID, used to key localStorage. Pass
 *   null when no session yet; the hook will be a no-op.
 * @param mainMessages - the canonical messages from useChatbot (always the
 *   source of truth for the main branch).
 */
export function useBranching(
  sessionId: string | null,
  mainMessages: ChatMessage[],
): UseBranchingReturn {
  const [store, setStore] = useState<BranchStore>({
    activeBranchId: "main",
    branches: [],
  });

  // Load persisted branches when session becomes available
  useEffect(() => {
    if (!sessionId) return;
    const persisted = loadStore(sessionId);
    if (persisted) {
      setStore(persisted);
    } else {
      setStore({ activeBranchId: "main", branches: [] });
    }
  }, [sessionId]);

  // Persist whenever store changes
  useEffect(() => {
    if (!sessionId) return;
    saveStore(sessionId, store);
  }, [sessionId, store]);

  const branchFrom = useCallback(
    (allMessages: ChatMessage[], forkIndex: number): string => {
      const newId = makeId();
      const branchNumber =
        store.branches.filter((b) => b.id !== "main").length + 1;
      const newBranch: Branch = {
        id: newId,
        name: `Branch ${branchNumber}`,
        messages: allMessages.slice(0, forkIndex + 1),
        forkIndex,
        createdAt: Date.now(),
      };

      setStore((prev) => {
        let branches = [...prev.branches, newBranch];
        // Prune oldest non-main branch when exceeding MAX_BRANCHES
        const nonMain = branches.filter((b) => b.id !== "main");
        if (nonMain.length > MAX_BRANCHES - 1) {
          const oldest = nonMain.sort((a, b) => a.createdAt - b.createdAt)[0];
          branches = branches.filter((b) => b.id !== oldest.id);
        }
        return { activeBranchId: newId, branches };
      });

      return newId;
    },
    [store.branches],
  );

  const switchBranch = useCallback((id: string) => {
    setStore((prev) => ({ ...prev, activeBranchId: id }));
  }, []);

  const setActiveBranchMessages = useCallback((messages: ChatMessage[]) => {
    setStore((prev) => {
      if (prev.activeBranchId === "main") return prev; // main is managed externally
      return {
        ...prev,
        branches: prev.branches.map((b) =>
          b.id === prev.activeBranchId ? { ...b, messages } : b,
        ),
      };
    });
  }, []);

  const isMainBranch = store.activeBranchId === "main";

  const activeBranch = isMainBranch
    ? null
    : store.branches.find((b) => b.id === store.activeBranchId);

  const activeMessages = isMainBranch
    ? mainMessages
    : (activeBranch?.messages ?? mainMessages);

  return {
    branches: store.branches,
    activeBranchId: store.activeBranchId,
    activeMessages,
    branchFrom,
    switchBranch,
    setActiveBranchMessages,
    isMainBranch,
  };
}
