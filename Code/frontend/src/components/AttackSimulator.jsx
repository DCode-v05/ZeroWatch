import { useState } from 'react';

const SCENARIOS = [
  {
    id: 'normal',
    label: 'Normal Session',
    icon: '✅',
    color: 'bg-green-600 hover:bg-green-700',
    desc: 'Baseline activity',
  },
  {
    id: 'change_country',
    label: 'Change Country',
    icon: '🌍',
    color: 'bg-amber-600 hover:bg-amber-700',
    desc: 'Login from Russia',
  },
  {
    id: 'stolen_token',
    label: 'Stolen Token',
    icon: '🔓',
    color: 'bg-red-600 hover:bg-red-700',
    desc: 'No ECDSA signature',
  },
  {
    id: 'rapid_export',
    label: 'Rapid Export',
    icon: '📤',
    color: 'bg-orange-600 hover:bg-orange-700',
    desc: 'Mass data exfil',
  },
  {
    id: 'full_attack',
    label: 'Full Attack',
    icon: '💀',
    color: 'bg-red-800 hover:bg-red-900',
    desc: 'Escalating attack',
  },
];

export default function AttackSimulator() {
  const [loading, setLoading] = useState(null);
  const [lastResult, setLastResult] = useState('');

  async function runScenario(id) {
    setLoading(id);
    setLastResult('');
    try {
      const resp = await fetch(`/api/demo/simulate/${id}`, {
        method: 'POST',
        credentials: 'include',
      });
      const data = await resp.json();
      setLastResult(`${id}: ${data.status || data.error || 'sent'}`);
    } catch (e) {
      setLastResult(`Error: ${e.message}`);
    }
    setLoading(null);
  }

  return (
    <div className="bg-[#0f172a] border-t border-[#334155] p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-medium text-[#94a3b8] uppercase tracking-wider">
          Attack Simulator
        </span>
        {lastResult && (
          <span className="text-xs text-[#64748b] ml-2">{lastResult}</span>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {SCENARIOS.map(({ id, label, icon, color, desc }) => (
          <button
            key={id}
            onClick={() => runScenario(id)}
            disabled={loading !== null}
            className={`${color} text-white text-sm px-4 py-2 rounded-lg font-medium
              transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
              flex items-center gap-1.5 shadow-lg`}
            title={desc}
          >
            <span>{icon}</span>
            <span>{loading === id ? 'Sending...' : label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
