import { useCallback, useEffect, useRef, useState } from "react";
import type { RalphEvent } from "./useEventReducer";

export type WSState = "connecting" | "connected" | "disconnected";

const MAX_BACKOFF = 10_000;

/**
 * WebSocket hook with auto-reconnect. Pass null URL to defer connection.
 */
export function useWebSocket(
  url: string | null,
  onEvent: (event: RalphEvent) => void,
): { state: WSState; send: (msg: string) => void } {
  const [state, setState] = useState<WSState>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!url) {
      setState("disconnected");
      return;
    }

    let reconnectTimer: ReturnType<typeof setTimeout>;
    let unmounted = false;

    function connect() {
      if (unmounted) return;
      setState("connecting");
      const ws = new WebSocket(url!);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmounted) return;
        setState("connected");
        backoffRef.current = 1000;
      };

      ws.onmessage = (ev) => {
        try {
          const event: RalphEvent = JSON.parse(ev.data);
          onEventRef.current(event);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (unmounted) return;
        setState("disconnected");
        wsRef.current = null;
        reconnectTimer = setTimeout(() => {
          backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF);
          connect();
        }, backoffRef.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [url]);

  const send = useCallback((msg: string) => {
    wsRef.current?.send(msg);
  }, []);

  return { state, send };
}
