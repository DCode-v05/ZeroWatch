import { useState, useEffect, useRef, useCallback } from 'react';

export default function useWebSocket(url = 'ws://localhost:8000/ws/risk') {
  const [data, setData] = useState({
    score: 0,
    delta: 0,
    flags: [],
    user: '',
    z_scores: {},
    incidents: [],
    scoreHistory: [],
  });
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Connected');
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'risk_update') {
          setData((prev) => {
            const newHistory = [
              ...prev.scoreHistory,
              { time: new Date().toLocaleTimeString(), score: msg.score },
            ].slice(-30);

            return {
              ...prev,
              score: msg.score,
              delta: msg.delta,
              flags: msg.flags || [],
              user: msg.user || prev.user,
              z_scores: msg.z_scores || prev.z_scores,
              scoreHistory: newHistory,
            };
          });
        }

        if (msg.type === 'incident') {
          setData((prev) => ({
            ...prev,
            incidents: [msg, ...prev.incidents].slice(0, 10),
          }));
        }
      } catch (e) {
        console.warn('[WS] Parse error:', e);
      }
    };

    ws.onclose = () => {
      console.log('[WS] Disconnected, reconnecting in 2s...');
      reconnectRef.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  return data;
}
