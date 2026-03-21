import { useState, useCallback, useEffect } from "react";

export type TokenUsage = {
  /** Estimated output tokens (chars / 4). Always present for assistant messages. */
  outputTokens: number;
  /** Input token count from API -- absent when only estimated. */
  inputTokens?: number;
  /** Whether counts are estimated (true) or from API (false). */
  estimated: boolean;
};

/** Per-message metadata snapshot captured from the API response. Only set on assistant messages. */
export type MessageMetadata = {
  confidence: Confidence;
  relevance: Relevance;
  phase: number;
  questionCount: number;
  weightedReadiness: number;
  /** Full raw API response, for power-user inspection. */
  rawResponse: Record<string, unknown>;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  /** Unix ms timestamp when the message was created. May be absent for history-restored messages. */
  timestamp?: number;
  /** Send status -- only set on user messages. 'error' means the request failed. */
  status?: "pending" | "sent" | "error";
  /** Token usage -- only set on assistant messages. */
  tokenUsage?: TokenUsage;
  /** Snapshot of API metadata at the time this assistant message was received. */
  metadata?: MessageMetadata;
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

export type ToolName = "brainstorm" | "expand" | "refine" | "architect" | "modify";
export type ToolResult = { content: string; mode: "edit" | "inject"; tool: ToolName; elapsed_ms?: number; model?: string };

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
  /** @deprecated use toolLoadingId !== null */
  toolLoading: boolean;
  toolLoadingId: ToolName | null;
  toolResult: ToolResult | null;
  toolUsageCount: Record<ToolName, number>;
};

import { API_URL } from "@/lib/config";
const API = API_URL;

const LS_KEY = "ralph_session_id";

/**
 * Parse a history message from the API. Assistant messages may arrive as:
 * - Already parsed by the backend (content is text, metadata is object)
 * - Legacy JSON string (content is a JSON blob with .message inside)
 * This normalizes both cases into a proper ChatMessage.
 */
function _parseHistoryMessage(m: { role: string; content: string; created_at?: number; metadata?: Record<string, unknown> }): ChatMessage {
  const base: ChatMessage = {
    role: m.role as "user" | "assistant",
    content: m.content,
    timestamp: m.created_at ? m.created_at * 1000 : undefined,
  };

  if (m.role !== "assistant") return base;

  // If backend already parsed and provided metadata, use it
  if (m.metadata) {
    const md = m.metadata as Record<string, any>;
    base.metadata = {
      confidence: md.confidence ?? EMPTY_CONFIDENCE,
      relevance: md.relevance ?? EMPTY_RELEVANCE,
      phase: md.phase ?? 1,
      questionCount: md.question_count ?? 0,
      weightedReadiness: md.weighted_readiness ?? 0,
      rawResponse: md,
    };
    return base;
  }

  // Fallback: try parsing content as JSON (legacy double-encoded messages)
  try {
    const parsed = JSON.parse(m.content);
    if (typeof parsed === "object" && parsed !== null && "message" in parsed) {
      base.content = parsed.message;
      base.metadata = {
        confidence: parsed.confidence ?? EMPTY_CONFIDENCE,
        relevance: parsed.relevance ?? EMPTY_RELEVANCE,
        phase: parsed.phase ?? 1,
        questionCount: parsed.question_count ?? 0,
        weightedReadiness: parsed.weighted_readiness ?? 0,
        rawResponse: parsed,
      };
    }
  } catch {
    // Not JSON -- leave content as-is
  }

  return base;
}

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

const EMPTY_TOOL_USAGE: Record<ToolName, number> = {
  brainstorm: 0,
  expand: 0,
  refine: 0,
  architect: 0,
  modify: 0,
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
    toolLoading: false,
    toolLoadingId: null,
    toolResult: null,
    toolUsageCount: { ...EMPTY_TOOL_USAGE },
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

        // Fetch chat history + live state in parallel
        const [histResp, stateResp] = await Promise.all([
          fetch(`${API}/api/sessions/${saved}/chat/history`),
          fetch(`${API}/api/sessions/${saved}/chat/state`),
        ]);
        if (!histResp.ok) {
          // Session exists but no history endpoint -- restore just the id
          setState((s) => ({ ...s, sessionId: saved }));
          return;
        }
        const hist = await histResp.json();
        // Live state is the authoritative source for confidence/readiness
        const liveState = stateResp.ok ? await stateResp.json() : null;

        // Parse history messages (handles both new parsed format and legacy JSON strings)
        const parsedMessages = (hist.messages ?? []).map(_parseHistoryMessage);

        // Priority: liveState (authoritative) > hist top-level > hist.state > session > default
        const st = hist.state ?? {};
        const confidence = liveState?.confidence ?? hist.confidence ?? st.confidence ?? EMPTY_CONFIDENCE;
        const relevance = liveState?.relevance ?? hist.relevance ?? st.relevance ?? EMPTY_RELEVANCE;

        setState((s) => ({
          ...s,
          sessionId: saved,
          messages: parsedMessages.length > 0 ? parsedMessages : s.messages,
          confidence,
          relevance,
          ready: liveState?.ready ?? hist.ready ?? st.ready ?? session.ready ?? s.ready,
          weightedReadiness:
            liveState?.weighted_readiness ?? hist.weighted_readiness ?? st.weighted_readiness ??
            session.weighted_readiness ?? s.weightedReadiness,
          questionCount:
            liveState?.question_count ?? hist.question_count ?? st.question_count ??
            session.question_count ?? s.questionCount,
          phase:
            session.status === "running"
              ? 2
              : (liveState?.phase ?? hist.phase ?? st.phase ?? session.phase ?? s.phase),
          tasks: hist.tasks ?? st.tasks ?? s.tasks,
          project: hist.project ?? st.project ?? s.project,
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
    async (message: string, replaceTimestamp?: number) => {
      let sid = state.sessionId;
      if (!sid) {
        sid = await createSession();
      }

      const msgTimestamp = replaceTimestamp ?? Date.now();

      setState((s) => {
        // If retrying, replace the errored message in-place; otherwise append.
        const next = replaceTimestamp
          ? s.messages.map((m) =>
              m.timestamp === replaceTimestamp
                ? { role: "user" as const, content: message, timestamp: msgTimestamp, status: "pending" as const }
                : m,
            )
          : [...s.messages, { role: "user" as const, content: message, timestamp: msgTimestamp, status: "pending" as const }];
        return { ...s, sessionId: sid, messages: next, loading: true, error: null, toolResult: null };
      });

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
        // Estimate output tokens: ~4 chars per token (no API token data available)
        const assistantTokenUsage: TokenUsage = data.token_usage
          ? { outputTokens: data.token_usage.output_tokens, inputTokens: data.token_usage.input_tokens, estimated: false }
          : { outputTokens: Math.round((data.message?.length ?? 0) / 4), estimated: true };
        // Snapshot metadata at message creation time so each message carries its own state
        const assistantMetadata: MessageMetadata = {
          confidence: data.confidence ?? EMPTY_CONFIDENCE,
          relevance: data.relevance ?? EMPTY_RELEVANCE,
          phase: data.phase ?? 1,
          questionCount: data.question_count ?? 0,
          weightedReadiness: data.weighted_readiness ?? 0,
          rawResponse: data as Record<string, unknown>,
        };
        setState((s) => ({
          ...s,
          messages: [
            // Mark the pending user message as sent
            ...s.messages.map((m) =>
              m.timestamp === msgTimestamp ? { ...m, status: "sent" as const } : m,
            ),
            { role: "assistant", content: data.message, timestamp: Date.now(), tokenUsage: assistantTokenUsage, metadata: assistantMetadata },
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
        // Mark the pending user message with error status; keep it visible for retry.
        setState((s) => ({
          ...s,
          messages: s.messages.map((m) =>
            m.timestamp === msgTimestamp ? { ...m, status: "error" as const } : m,
          ),
          loading: false,
        }));
      }
    },
    [state.sessionId, createSession],
  );

  /** Retry a failed user message identified by its timestamp. */
  const retryMessage = useCallback(
    (content: string, timestamp: number) => sendMessage(content, timestamp),
    [sendMessage],
  );

  // tasksOverride: if provided, sent in the request body so the server
  // uses the user-edited list instead of chatbot-generated tasks.
  const ralphIt = useCallback(async (tasksOverride?: any[]) => {
    if (!state.sessionId) return null;
    setState((s) => ({ ...s, loading: true, error: null }));

    try {
      const body = tasksOverride ? JSON.stringify({ tasks: tasksOverride }) : undefined;
      const resp = await fetch(
        `${API}/api/sessions/${state.sessionId}/ralph-it`,
        {
          method: "POST",
          headers: body ? { "Content-Type": "application/json" } : undefined,
          body,
        },
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

  /** Remove the last user+assistant message pair and sync confidence from server. */
  const undoLastMessage = useCallback(async () => {
    if (!state.sessionId) return;
    const resp = await fetch(`${API}/api/sessions/${state.sessionId}/chat/undo`, {
      method: "POST",
    });
    if (!resp.ok) return;
    const data = await resp.json();
    setState((s) => ({
      ...s,
      messages: s.messages.slice(0, -2),
      confidence: data.confidence ?? s.confidence,
      relevance: data.relevance ?? s.relevance,
      ready: data.ready ?? false,
      weightedReadiness: data.weighted_readiness ?? s.weightedReadiness,
      questionCount: data.question_count ?? s.questionCount,
    }));
  }, [state.sessionId]);

  /**
   * Delete a session by ID (defaults to current). Clears localStorage and
   * resets state so the user starts fresh.
   */
  const deleteSession = useCallback(async (id?: string) => {
    const target = id ?? state.sessionId;
    if (!target) return;
    await fetch(`${API}/api/sessions/${target}`, { method: "DELETE" });
    // Only reset local state when deleting the active session
    if (target === state.sessionId) {
      localStorage.removeItem(LS_KEY);
      setState({
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
        toolLoading: false,
        toolLoadingId: null,
        toolResult: null,
        toolUsageCount: { ...EMPTY_TOOL_USAGE },
      });
    }
  }, [state.sessionId]);

  /** Clear all messages for the current session without destroying the session. */
  const clearChat = useCallback(async () => {
    if (!state.sessionId) return;
    const resp = await fetch(`${API}/api/sessions/${state.sessionId}/chat/clear`, {
      method: "POST",
    });
    if (!resp.ok) return;
    setState((s) => ({
      ...s,
      messages: [],
      confidence: EMPTY_CONFIDENCE,
      relevance: EMPTY_RELEVANCE,
      ready: false,
      tasks: null,
      project: null,
      weightedReadiness: 0,
      questionCount: 0,
      phase: 1,
      toolUsageCount: { ...EMPTY_TOOL_USAGE },
    }));
  }, [state.sessionId]);

  /**
   * Switch to an existing session by ID: fetch its history and restore state.
   * Updates localStorage so the next page load resumes the same session.
   */
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const [sessionResp, histResp, stateResp] = await Promise.all([
        fetch(`${API}/api/sessions/${sessionId}`),
        fetch(`${API}/api/sessions/${sessionId}/chat/history`),
        fetch(`${API}/api/sessions/${sessionId}/chat/state`),
      ]);
      if (!sessionResp.ok) return;
      const session = await sessionResp.json();
      const hist = histResp.ok ? await histResp.json() : {};
      const liveState = stateResp.ok ? await stateResp.json() : null;

      const parsedMessages = (hist.messages ?? []).map(_parseHistoryMessage);
      const st = hist.state ?? {};
      const confidence = liveState?.confidence ?? hist.confidence ?? st.confidence ?? session.confidence ?? EMPTY_CONFIDENCE;
      const relevance = liveState?.relevance ?? hist.relevance ?? st.relevance ?? session.relevance ?? EMPTY_RELEVANCE;

      localStorage.setItem(LS_KEY, sessionId);
      setState((s) => ({
        ...s,
        sessionId,
        messages: parsedMessages,
        confidence,
        relevance,
        ready: liveState?.ready ?? hist.ready ?? st.ready ?? session.ready ?? false,
        tasks: hist.tasks ?? st.tasks ?? null,
        project: hist.project ?? st.project ?? null,
        weightedReadiness: liveState?.weighted_readiness ?? hist.weighted_readiness ?? st.weighted_readiness ?? session.weighted_readiness ?? 0,
        questionCount: liveState?.question_count ?? hist.question_count ?? st.question_count ?? session.question_count ?? 0,
        phase: liveState?.phase ?? hist.phase ?? st.phase ?? session.phase ?? 1,
        loading: false,
        error: null,
        toolLoading: false,
        toolLoadingId: null,
        toolResult: null,
        toolUsageCount: { ...EMPTY_TOOL_USAGE },
      }));
    } catch {
      // silently ignore -- leave state unchanged
    }
  }, []);

  const runTool = useCallback(
    async (tool: ToolName, context?: string) => {
      if (!state.sessionId) return;
      setState((s) => ({ ...s, toolLoadingId: tool, toolLoading: true, error: null }));
      try {
        const resp = await fetch(
          `${API}/api/sessions/${state.sessionId}/chat/tool`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool, context: context ?? "" }),
          },
        );
        if (!resp.ok) {
          const err = await resp
            .json()
            .catch(() => ({ detail: "Tool failed" }));
          throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        const toolLabel = data.tool.charAt(0).toUpperCase() + data.tool.slice(1);
        const prefixedContent = data.mode === "inject"
          ? `[Tool: ${toolLabel}] ${data.result}`
          : data.result;
        setState((s) => ({
          ...s,
          toolLoadingId: null,
          toolLoading: false,
          toolResult: { content: prefixedContent, mode: data.mode, tool: data.tool, elapsed_ms: data.elapsed_ms, model: data.model },
          toolUsageCount: { ...s.toolUsageCount, [tool]: (s.toolUsageCount[tool] || 0) + 1 },
        }));
      } catch (err) {
        setState((s) => ({
          ...s,
          toolLoadingId: null,
          toolLoading: false,
          error: err instanceof Error ? err.message : "Tool failed",
        }));
      }
    },
    [state.sessionId],
  );

  const clearToolResult = useCallback(() => {
    setState((s) => ({ ...s, toolResult: null }));
  }, []);

  /**
   * Start a fresh chat: clear localStorage, reset all state, create a new session.
   * Useful for "New Chat" UX where the user wants a blank slate without deleting the old session.
   */
  const newChat = useCallback(async () => {
    localStorage.removeItem(LS_KEY);
    setState({
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
      toolLoading: false,
      toolLoadingId: null,
      toolResult: null,
      toolUsageCount: { ...EMPTY_TOOL_USAGE },
    });
    try {
      const resp = await fetch(`${API}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (resp.ok) {
        const data = await resp.json();
        localStorage.setItem(LS_KEY, data.id);
        setState((s) => ({ ...s, sessionId: data.id }));
      }
    } catch {
      // Network error -- state already reset, user can still chat
    }
  }, []);

  return {
    state,
    sendMessage,
    ralphIt,
    createSession,
    clearError,
    clearChat,
    deleteSession,
    loadSession,
    undoLastMessage,
    retryMessage,
    runTool,
    clearToolResult,
    newChat,
  };
}
