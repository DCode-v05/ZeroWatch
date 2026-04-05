const FEATURES = [
  { key: 'ip_country', label: 'IP Country', icon: '🌍' },
  { key: 'device_fp', label: 'Device FP', icon: '📱' },
  { key: 'data_mb', label: 'Data (MB)', icon: '📊' },
  { key: 'api_calls', label: 'API Calls', icon: '🔗' },
  { key: 'login_hour', label: 'Login Hour', icon: '🕐' },
  { key: 'wpm', label: 'WPM', icon: '⌨️' },
];

function getBarColor(z) {
  if (z <= 1) return '#22c55e';
  if (z <= 2.5) return '#f59e0b';
  return '#ef4444';
}

function getBarWidth(z) {
  return Math.min(100, (z / 5) * 100);
}

export default function SignalHeatmap({ zScores = {} }) {
  return (
    <div className="bg-[#1e293b] rounded-2xl border border-[#334155] p-5">
      <h3 className="text-sm font-medium text-[#94a3b8] mb-4 uppercase tracking-wider">
        Signal Anomaly Heatmap
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {FEATURES.map(({ key, label, icon }) => {
          const z = zScores[key] || 0;
          const color = getBarColor(z);
          const width = getBarWidth(z);
          return (
            <div
              key={key}
              className="bg-[#0f172a] rounded-xl p-3 border border-[#334155]"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[#94a3b8]">
                  {icon} {label}
                </span>
                <span
                  className="text-xs font-mono font-bold"
                  style={{ color }}
                >
                  {z.toFixed(1)}
                </span>
              </div>
              <div className="h-2 bg-[#1e293b] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${width}%`,
                    backgroundColor: color,
                    transition: 'width 0.5s ease, background-color 0.5s ease',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
