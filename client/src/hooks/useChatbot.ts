import { useState, useCallback, useEffect } from "react";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type Confidence = {
  functional: number;
  technical_stack: number;
  data_model: number;
  auth: number;
  deployment: number;
  testing: number;
  edge_cases: number;
};

export type Relevance = {
  functional: number;
  technical_stack: number;
  data_model: number;
  auth: number;
  deployment: number;
  testing: number;
  edge_cases: number;
};

export type ChatState = {
  messages: ChatMessage[];
  confidence: Confidence;
  relevance: Relevance;
  ready: boolean;
  loading: boolean;
  /** Last transient error to be consumed by the UI layer. */
  error: string | null;
  sessionId: string | null;
  tasks: any[] | null;
  project: any | null;
  weightedReadiness: number;
  questionCount: number;
  phase: number;
};

import { API_URL } from "@/lib/config";
const API = API_URL;

const LS_KEY = "ralph_session_id";

const EMPTY_CONFIDENCE: Confidence = {
  functional: 0,
  technical_stack: 0,
  data_model: 0,
  auth: 0,
  deployment: 0,
  testing: 0,
  edge_cases: 0,
};

const EMPTY_RELEVANCE: Relevance = {
  functional: 1.0,
  technical_stack: 1.0,
  data_model: 1.0,
  auth: 1.0,
  deployment: 1.0,
  testing: 1.0,
  edge_cases: 1.0,
};

export function useChatbot() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    confidence: EMPTY_CONFIDENCE,
    relevance: EMPTY_RELEVANCE,
    ready: false,
    loading: false,
    error: null,
    sessionId: null,
    tasks: null,
    project: null,
    weightedReadiness: 0,
    questionCount: 0,
    phase: 1,
  });

  // Restore session from localStorage on mount.
  useEffect(() => {
    const saved = localStorage.getItem(LS_KEY);
    if (!saved) return;

    (async () => {
      try {
        // Verify session exists
        const verifyResp = await fetch(`${API}/api/sessions/${saved}`);
        if (!verifyResp.ok) {
          localStorage.removeItem(LS_KEY);
          return;
        }
        const session = await verifyResp.json();

        // Fetch chat history if available
        const histResp = await fetch(
          `${API}/api/sessions/${saved}/chat/history`,
        );
        if (!histResp.ok) {
          // Session exists but no history endpoint -- restore just the id
          setState((s) => ({ ...s, sessionId: saved }));
          return;
        }
        const hist = await histResp.json();

        setState((s) => ({
          ...s,
          sessionId: saved,
          messages: hist.messages ?? s.messages,
          confidence: hist.confidence ?? session.confidence ?? s.confidence,
          relevance: hist.relevance ?? session.relevance ?? s.relevance,
          ready: hist.ready ?? session.ready ?? s.ready,
          weightedReadiness:
            hist.weighted_readiness ??
            session.weighted_readiness ??
            s.weightedReadiness,
          questionCount:
            hist.question_count ?? session.question_count ?? s.questionCount,
          // If session was running, set phase to 2
          phase:
            session.status === "running"
              ? 2
              : (hist.phase ?? session.phase ?? s.phase),
        }));
      } catch {
        // Network error -- leave state as-is, don't clear localStorage
      }
    })();
    // Run only on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createSession = useCallback(async () => {
    const resp = await fetch(`${API}/api/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await resp.json();
    localStorage.setItem(LS_KEY, data.id);
    setState((s) => ({ ...s, sessionId: data.id }));
    return data.id as string;
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      let sid = state.sessionId;
      if (!sid) {
        sid = await createSession();
      }

      setState((s) => ({
        ...s,
        sessionId: sid,
        messages: [...s.messages, { role: "user", content: message }],
        loading: true,
        error: null,
      }));

      try {
        const resp = await fetch(`${API}/api/sessions/${sid}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        });

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({ detail: "Server error" }));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }

        const data = await resp.json();
        setState((s) => ({
          ...s,
          messages: [
            ...s.messages,
            { role: "assistant", content: data.message },
          ],
          confidence: data.confidence ?? s.confidence,
          relevance: data.relevance ?? s.relevance,
          ready: data.ready ?? false,
          tasks: data.tasks ?? null,
          project: data.project ?? null,
          weightedReadiness: data.weighted_readiness ?? s.weightedReadiness,
          questionCount: data.question_count ?? s.questionCount,
          phase: data.phase ?? s.phase,
          loading: false,
        }));
      } catch (err) {
        setState((s) => ({
          ...s,
          error: err instanceof Error ? err.message : "Unknown error",
          loading: false,
        }));
      }
    },
    [state.sessionId, createSession],
  );

  const ralphIt = useCallback(async () => {
    if (!state.sessionId) return null;
    setState((s) => ({ ...s, loading: true, error: null }));

    try {
      const resp = await fetch(
        `${API}/api/sessions/${state.sessionId}/ralph-it`,
        { method: "POST" },
      );
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "Server error" }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setState((s) => ({ ...s, loading: false }));
      return data;
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err instanceof Error ? err.message : "Unknown error",
      }));
      return null;
    }
  }, [state.sessionId]);

  /** Clear the transient error after it has been consumed by the UI. */
  const clearError = useCallback(() => {
    setState((s) => ({ ...s, error: null }));
  }, []);

  return { state, sendMessage, ralphIt, createSession, clearError };
}
