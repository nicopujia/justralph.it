import { useState, useCallback } from "react";

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

export type ChatState = {
  messages: ChatMessage[];
  confidence: Confidence;
  ready: boolean;
  loading: boolean;
  sessionId: string | null;
  tasks: any[] | null;
  project: any | null;
};

import { API_URL } from "@/lib/config";
const API = API_URL;

const EMPTY_CONFIDENCE: Confidence = {
  functional: 0,
  technical_stack: 0,
  data_model: 0,
  auth: 0,
  deployment: 0,
  testing: 0,
  edge_cases: 0,
};

export function useChatbot() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    confidence: EMPTY_CONFIDENCE,
    ready: false,
    loading: false,
    sessionId: null,
    tasks: null,
    project: null,
  });

  const createSession = useCallback(async () => {
    const resp = await fetch(`${API}/api/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await resp.json();
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
          ready: data.ready ?? false,
          tasks: data.tasks ?? null,
          project: data.project ?? null,
          loading: false,
        }));
      } catch (err) {
        setState((s) => ({
          ...s,
          messages: [
            ...s.messages,
            {
              role: "assistant",
              content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
            },
          ],
          loading: false,
        }));
      }
    },
    [state.sessionId, createSession],
  );

  const ralphIt = useCallback(async () => {
    if (!state.sessionId) return null;
    setState((s) => ({ ...s, loading: true }));

    const resp = await fetch(
      `${API}/api/sessions/${state.sessionId}/ralph-it`,
      { method: "POST" },
    );
    const data = await resp.json();
    setState((s) => ({ ...s, loading: false }));
    return data;
  }, [state.sessionId]);

  return { state, sendMessage, ralphIt, createSession };
}
