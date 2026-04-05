import { useEffect, useState } from 'react';

function getColor(score) {
  if (score <= 30) return '#22c55e';
  if (score <= 70) return '#f59e0b';
  return '#ef4444';
}

function getLabel(score) {
  if (score <= 30) return 'LOW RISK';
  if (score <= 70) return 'MEDIUM RISK';
  return 'HIGH RISK';
}

export default function RiskGauge({ score = 0 }) {
  const [displayScore, setDisplayScore] = useState(0);

  useEffect(() => {
    // Animate score change
    const step = score > displayScore ? 1 : -1;
    if (Math.abs(score - displayScore) < 1) {
      setDisplayScore(score);
      return;
    }
    const timer = setTimeout(() => {
      setDisplayScore((prev) => prev + step * Math.max(1, Math.abs(score - prev) * 0.15));
    }, 16);
    return () => clearTimeout(timer);
  }, [score, displayScore]);

  const radius = 80;
  const circumference = Math.PI * radius; // half circle
  const progress = (Math.min(displayScore, 100) / 100) * circumference;
  const color = getColor(displayScore);

  return (
    <div className="flex flex-col items-center p-6 bg-[#1e293b] rounded-2xl border border-[#334155]">
      <h3 className="text-sm font-medium text-[#94a3b8] mb-2 uppercase tracking-wider">Risk Score</h3>
      <svg width="200" height="120" viewBox="0 0 200 120">
        {/* Background arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="#334155"
          strokeWidth="12"
          strokeLinecap="round"
        />
        {/* Score arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${progress} ${circumference}`}
          style={{ transition: 'stroke-dasharray 0.3s ease, stroke 0.3s ease' }}
        />
        {/* Score text */}
        <text
          x="100"
          y="85"
          textAnchor="middle"
          fontSize="36"
          fontWeight="bold"
          fill={color}
          style={{ transition: 'fill 0.3s ease' }}
        >
          {Math.round(displayScore)}
        </text>
        <text x="100" y="105" textAnchor="middle" fontSize="11" fill="#94a3b8">
          {getLabel(displayScore)}
        </text>
      </svg>
      <div className="flex justify-between w-full text-xs text-[#64748b] mt-1 px-2">
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>
    </div>
  );
}
