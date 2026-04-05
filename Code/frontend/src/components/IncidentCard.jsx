function getBadgeColor(action) {
  if (action === 'session_terminated') return 'bg-red-500/20 text-red-400 border-red-500/30';
  if (action === 'mfa_required') return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
}

function getBadgeLabel(action) {
  if (action === 'session_terminated') return 'TERMINATED';
  if (action === 'mfa_required') return 'MFA REQUIRED';
  return action?.toUpperCase() || 'INFO';
}

export default function IncidentCard({ incidents = [] }) {
  if (incidents.length === 0) {
    return (
      <div className="bg-[#1e293b] rounded-2xl border border-[#334155] p-5">
        <h3 className="text-sm font-medium text-[#94a3b8] mb-3 uppercase tracking-wider">
          Incident Reports
        </h3>
        <p className="text-[#475569] text-sm italic">No incidents yet. Waiting for anomalies...</p>
      </div>
    );
  }

  return (
    <div className="bg-[#1e293b] rounded-2xl border border-[#334155] p-5">
      <h3 className="text-sm font-medium text-[#94a3b8] mb-3 uppercase tracking-wider">
        Incident Reports (Claude AI)
      </h3>
      <div className="space-y-3 max-h-80 overflow-y-auto">
        {incidents.map((inc, i) => (
          <div
            key={i}
            className="bg-[#0f172a] rounded-xl p-4 border border-[#334155] animate-fade-in"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-white font-medium text-sm">
                  {inc.user || 'Unknown'}
                </span>
                <span className="text-[#64748b] text-xs">
                  {inc.timestamp
                    ? new Date(inc.timestamp).toLocaleTimeString()
                    : ''}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono font-bold text-red-400">
                  {inc.score?.toFixed(0)}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full border ${getBadgeColor(
                    inc.action
                  )}`}
                >
                  {getBadgeLabel(inc.action)}
                </span>
              </div>
            </div>
            <p className="text-[#cbd5e1] text-sm leading-relaxed whitespace-pre-line">
              {inc.narrative || 'Generating incident report...'}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
