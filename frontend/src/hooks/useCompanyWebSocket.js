import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";

const WS_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/^http/, "ws");

/**
 * FEATURE 17: subscribes to /ws/companies/{id} and invalidates the relevant
 * React Query caches on push, so chat replies, task moves, and events show
 * up live without polling. Reconnects with backoff if the socket drops.
 */
export function useCompanyWebSocket(companyId) {
  const { auth } = useAuth();
  const queryClient = useQueryClient();
  const retryRef = useRef(0);

  useEffect(() => {
    if (!companyId || !auth?.token) return undefined;

    let socket;
    let closedByUs = false;
    let retryTimeout;

    const connect = () => {
      socket = new WebSocket(`${WS_BASE}/ws/companies/${companyId}?token=${auth.token}`);

      socket.onopen = () => {
        retryRef.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const { type } = JSON.parse(event.data);
          if (type === "task_updated" || type === "bug_reported") {
            queryClient.invalidateQueries({ queryKey: ["board"] });
            queryClient.invalidateQueries({ queryKey: ["projectState"] });
            queryClient.invalidateQueries({ queryKey: ["events"] });
            queryClient.invalidateQueries({ queryKey: ["timeline"] });
          } else if (type === "chat_message") {
            queryClient.invalidateQueries({ queryKey: ["chat"] });
          } else if (type === "event" || type === "notification") {
            queryClient.invalidateQueries({ queryKey: ["notifications"] });
            queryClient.invalidateQueries({ queryKey: ["events"] });
            queryClient.invalidateQueries({ queryKey: ["timeline"] });
          }
        } catch {
          // ignore malformed frames
        }
      };

      socket.onclose = () => {
        if (closedByUs) return;
        const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
        retryRef.current += 1;
        retryTimeout = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      closedByUs = true;
      clearTimeout(retryTimeout);
      socket?.close();
    };
  }, [companyId, auth?.token, queryClient]);
}
