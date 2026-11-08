import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import useWebSocket from '../hooks/useWebSocket';
import RiskGauge from '../components/RiskGauge';
import SignalHeatmap from '../components/SignalHeatmap';
import IncidentCard from '../components/IncidentCard';
import AttackSimulator from '../components/AttackSimulator';

function predictiveData(history) {
  if (history.length < 3) return [];
  const last5 = history.slice(-5);
  const n = last5.length;
  const xMean = (n - 1) / 2;
  const yMean = last5.reduce((s, p) => s + p.score, 0) / n;

  let num = 0, den = 0;
  last5.forEach((p, i) => {
    num += (i - xMean) * (p.score - yMean);
    den += (i - xMean) ** 2;
  });
  const slope = den !== 0 ? num / den : 0;
  const intercept = yMean - slope * xMean;

  const predictions = [];
  for (let i = 1; i <= 3; i++) {
    const projected = Math.max(0, Math.min(100, slope * (n - 1 + i) + intercept));
    predictions.push({
      time: `+${i * 3}s`,
      predicted: Math.round(projected * 10) / 10,
    });
  }
  return predictions;
}

export default function Dashboard() {
  const { score, delta, flags, user, z_scores, incidents, scoreHistory } = useWebSocket();

  const chartData = useMemo(() => {
    const predictions = predictiveData(scoreHistory);
    const base = scoreHistory.map((p) => ({ ...p, predicted: null }));
    if (predictions.length > 0 && scoreHistory.length > 0) {
      const lastReal = scoreHistory[scoreHistory.length - 1];
      return [
        ...base,
        { time: lastReal.time, score: null, predicted: lastReal.score },
        ...predictions.map((p) => ({ time: p.time, score: null, predicted: p.predicted })),
      ];
    }
    return base;
  }, [scoreHistory]);

  const projectedMFA = useMemo(() => {
    const preds = predictiveData(scoreHistory);
    return preds.some((p) => p.predicted >= 70);
  }, [scoreHistory]);

  return (
    <div className="flex flex-col min-h-screen">
      <header className="bg-[#1e293b] border-b border-[#334155] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            ZW
          </div>
          <h1 className="text-lg font-semibold text-white">ZeroWatch</h1>
          <span className="text-xs text-[#64748b] ml-2">Zero-Trust Session Security</span>
        </div>
        <div className="flex items-center gap-3">
          {user && (
            <span className="text-sm text-[#94a3b8]">
              Monitoring: <span className="text-white font-medium">{user}</span>
            </span>
          )}
          {projectedMFA && (
            <span className="text-xs px-2 py-1 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full animate-pulse">
              PRE-EMPTIVE MFA PREDICTED
            </span>
          )}
          {flags.length > 0 && (
            <span className="text-xs px-2 py-1 bg-red-500/20 text-red-400 border border-red-500/30 rounded-full">
              {flags.length} FLAG{flags.length > 1 ? 'S' : ''}
            </span>
          )}
        </div>
      </header>

      <main className="flex-1 p-6 space-y-6 overflow-y-auto pb-24">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <RiskGauge score={score} />
          </div>
          <div className="lg:col-span-2 bg-[#1e293b] rounded-2xl border border-[#334155] p-5">
            <h3 className="text-sm font-medium text-[#94a3b8] mb-3 uppercase tracking-wider">
              Risk Timeline
            </h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#64748b" fontSize={11} />
                <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f1f5f9',
                  }}
                />
                <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" label="" />
                <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" label="" />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  connectNulls={false}
                />
                <Line
                  type="monotone"
                  dataKey="predicted"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <SignalHeatmap zScores={z_scores} />

        <IncidentCard incidents={incidents} />
      </main>

      <div className="fixed bottom-0 left-0 right-0 z-50">
        <AttackSimulator />
      </div>
    </div>
  );
}
