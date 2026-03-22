import { useCallback, useEffect, useRef, useState } from "react";
import type { RalphEvent } from "./useEventReducer";

export type WSState = "connecting" | "connected" | "disconnected";

const MAX_BACKOFF = 10_000;
const PING_INTERVAL = 30_000; // send ping every 30s to keep connection alive

/**
 * WebSocket hook with auto-reconnect and ping/pong keepalive.
 * Pass null URL to defer connection.
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
    let pingTimer: ReturnType<typeof setInterval>;
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

        // Start ping keepalive to prevent proxy/LB timeouts
        pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, PING_INTERVAL);
      };

      ws.onmessage = (ev) => {
        // Ignore pong responses
        if (ev.data === "pong") return;
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
        clearInterval(pingTimer);
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
      clearInterval(pingTimer);
      wsRef.current?.close();
    };
  }, [url]);

  const send = useCallback((msg: string) => {
    wsRef.current?.send(msg);
  }, []);

  return { state, send };
}
