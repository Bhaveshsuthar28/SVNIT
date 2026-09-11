import { useCallback, useEffect, useRef, useState } from "react";
import { websocketUrl } from "../services/api";

export function useTrafficSocket(onFrame) {
  const socketRef = useRef(null);
  const reconnectRef = useRef(null);
  const activeRef = useRef(true);
  const onFrameRef = useRef(onFrame);
  const [status, setStatus] = useState("connecting");

  useEffect(() => { onFrameRef.current = onFrame; }, [onFrame]);

  useEffect(() => {
    activeRef.current = true;
    const connect = () => {
      setStatus("connecting");
      const socket = new WebSocket(websocketUrl());
      socketRef.current = socket;
      socket.onopen = () => setStatus("connected");
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "frame") onFrameRef.current(message);
        } catch { /* Ignore malformed server messages without breaking replay. */ }
      };
      socket.onerror = () => setStatus("error");
      socket.onclose = () => {
        socketRef.current = null;
        if (!activeRef.current) return;
        setStatus("reconnecting");
        reconnectRef.current = window.setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      activeRef.current = false;
      window.clearTimeout(reconnectRef.current);
      socketRef.current?.close();
    };
  }, []);

  const send = useCallback((payload) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send(JSON.stringify(payload));
  }, []);
  return { status, send };
}
