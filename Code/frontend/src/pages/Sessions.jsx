import { useState, useEffect } from 'react';

export default function Sessions() {
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const resp = await fetch('/api/sessions');
        const data = await resp.json();
        setSessions(data.sessions || []);
      } catch (e) {
        console.error('Failed to load sessions:', e);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6">
      <h2 className="text-xl font-semibold mb-4">Active Sessions</h2>
      <div className="bg-[#1e293b] rounded-2xl border border-[#334155] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#334155] text-[#94a3b8] text-left">
              <th className="p-3">Session ID</th>
              <th className="p-3">User</th>
              <th className="p-3">Status</th>
              <th className="p-3">Risk Score</th>
              <th className="p-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s, i) => (
              <tr key={i} className="border-b border-[#334155]/50 hover:bg-[#334155]/20">
                <td className="p-3 font-mono text-xs">{s.session_id?.slice(0, 12)}...</td>
                <td className="p-3">{s.username || 'N/A'}</td>
                <td className="p-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    s.status === 'active' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {s.status}
                  </span>
                </td>
                <td className="p-3 font-mono">{s.risk_score?.toFixed(1) || '0.0'}</td>
                <td className="p-3 text-[#64748b]">{s.created_at ? new Date(s.created_at).toLocaleTimeString() : ''}</td>
              </tr>
            ))}
            {sessions.length === 0 && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-[#475569]">No active sessions</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
