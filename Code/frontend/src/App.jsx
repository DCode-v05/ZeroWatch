import { useState } from 'react';
import Dashboard from './pages/Dashboard';
import Sessions from './pages/Sessions';
import Incidents from './pages/Incidents';

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'sessions', label: 'Sessions' },
  { id: 'incidents', label: 'Incidents' },
];

function App() {
  const [tab, setTab] = useState('dashboard');

  return (
    <div className="min-h-screen bg-[#0f172a]">
      {tab !== 'dashboard' && (
        <nav className="bg-[#1e293b] border-b border-[#334155] px-6 py-2 flex items-center gap-1">
          <div className="flex items-center gap-3 mr-6">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
              ZW
            </div>
            <span className="text-lg font-semibold text-white">ZeroWatch</span>
          </div>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                tab === t.id
                  ? 'bg-blue-600 text-white'
                  : 'text-[#94a3b8] hover:text-white hover:bg-[#334155]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      )}

      {tab === 'dashboard' && (
        <div>
          <div className="fixed top-0 right-4 z-50 flex gap-1 pt-2.5">
            {TABS.filter(t => t.id !== 'dashboard').map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className="px-3 py-1 text-xs text-[#64748b] hover:text-white hover:bg-[#334155] rounded transition-colors"
              >
                {t.label}
              </button>
            ))}
          </div>
          <Dashboard />
        </div>
      )}
      {tab === 'sessions' && <Sessions />}
      {tab === 'incidents' && <Incidents />}
    </div>
  );
}

export default App;
