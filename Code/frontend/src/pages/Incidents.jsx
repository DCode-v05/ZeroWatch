import { useState, useEffect } from 'react';

export default function Incidents() {
  const [incidents, setIncidents] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const resp = await fetch('/api/incidents');
        const data = await resp.json();
        setIncidents(data.incidents || []);
      } catch (e) {
        console.error('Failed to load incidents:', e);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6">
      <h2 className="text-xl font-semibold mb-4">Incident History</h2>
      <div className="space-y-3">
        {incidents.map((inc, i) => (
          <div key={i} className="bg-[#1e293b] rounded-2xl border border-[#334155] p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">User {inc.user_id}</span>
              <div className="flex items-center gap-2">
                <span className="text-red-400 font-mono">{inc.score?.toFixed(0)}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 border border-red-500/30">
                  {inc.action || 'TERMINATED'}
                </span>
              </div>
            </div>
            <p className="text-sm text-[#cbd5e1]">{inc.narrative}</p>
            <p className="text-xs text-[#64748b] mt-2">{inc.created_at}</p>
          </div>
        ))}
        {incidents.length === 0 && (
          <p className="text-[#475569] italic">No incidents recorded yet.</p>
        )}
      </div>
    </div>
  );
}
