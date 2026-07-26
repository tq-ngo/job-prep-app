import { useEffect, useRef, useState, useCallback } from "react";
import { Job } from "@/lib/api";

const MAX_RECONNECT_DELAY = 30000; // 30s cap
const BASE_RECONNECT_DELAY = 1000; // 1s initial

export function useJobAlerts() {
  const [newJobs, setNewJobs] = useState<Job[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = process.env.NEXT_PUBLIC_API_URL?.replace(/^https?:\/\//, "") || "localhost:8000";
    const wsUrl = `${protocol}//${host}/ws/jobs`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    let pingInterval: ReturnType<typeof setInterval> | null = null;

    ws.onopen = () => {
      setConnected(true);
      reconnectAttemptRef.current = 0; // reset backoff on successful connect

      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "new_job") {
          setNewJobs((prev) => [message.data, ...prev].slice(0, 50));
        }
      } catch {}
    };

    ws.onclose = () => {
      if (pingInterval) clearInterval(pingInterval);
      setConnected(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnect is handled there
      setConnected(false);
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped)
    const delay = Math.min(BASE_RECONNECT_DELAY * Math.pow(2, attempt), MAX_RECONNECT_DELAY);
    reconnectAttemptRef.current = attempt + 1;

    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      // Cleanup on unmount: cancel reconnect timer and close socket
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        // Remove onclose to prevent reconnect during intentional cleanup
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { newJobs, connected };
}