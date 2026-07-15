import { useEffect, useRef, useState } from "react";
import { Job } from "@/lib/api";

export function useJobAlerts() {
  const [newJobs, setNewJobs] = useState<Job[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = process.env.NEXT_PUBLIC_API_URL?.replace(/^https?:\/\//, "") || "localhost:8000";
    const wsUrl = `${protocol}//${host}/ws/jobs`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      const interval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000);
      ws.onclose = () => {
        clearInterval(interval);
        setConnected(false);
      };
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "new_job") {
          setNewJobs((prev) => [message.data, ...prev].slice(0, 50));
        }
      } catch {}
    };

    ws.onerror = () => setConnected(false);

    return () => ws.close();
  }, []);

  return { newJobs, connected };
}