// Lightweight SVG chart components — no external deps, GSAP-animated.
import { useRef, useEffect } from 'react';
import gsap from 'gsap';

// ─── Line / Area chart ───────────────────────────────────────────────────────
interface LineChartProps {
  data: number[];
  color?: string;
  height?: number;
  fill?: boolean;
  animated?: boolean;
}
export function LineChart({ data, color = 'var(--sys-cyan)', height = 64, fill = true, animated = true }: LineChartProps) {
  const pathRef = useRef<SVGPolylineElement>(null);
  const areaRef = useRef<SVGPolygonElement>(null);

  const W = 240; const H = height;
  const max = Math.max(...data, 0.001);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pad = H * 0.08;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - pad - ((v - min) / range) * (H - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const areaPts = `0,${H} ${pts} ${W},${H}`;

  useEffect(() => {
    if (!animated || !pathRef.current) return;
    const el = pathRef.current;
    const len = el.getTotalLength?.() ?? 300;
    gsap.fromTo(el, { strokeDasharray: len, strokeDashoffset: len }, { strokeDashoffset: 0, duration: 0.8, ease: 'power2.out' });
  }, [animated, data.join(',')]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="sys-chart" preserveAspectRatio="none">
      {fill && <polygon ref={areaRef} points={areaPts} fill={color} fillOpacity="0.12" />}
      <polyline ref={pathRef} points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ─── Donut / Pie chart ───────────────────────────────────────────────────────
interface DonutSegment { label: string; value: number; color: string }
export function DonutChart({ segments, size = 160, thickness = 28 }: {
  segments: DonutSegment[]; size?: number; thickness?: number;
}) {
  const r = (size - thickness) / 2;
  const cx = size / 2; const cy = size / 2;
  const circ = 2 * Math.PI * r;
  const total = segments.reduce((s, d) => s + d.value, 0) || 1;
  let offset = 0;
  const arcs = segments.map(seg => {
    const dash = (seg.value / total) * circ;
    const arc = { dash, gap: circ - dash, offset, ...seg };
    offset += dash;
    return arc;
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
      {arcs.map((a, i) => (
        <circle key={i} cx={cx} cy={cy} r={r} fill="none"
          stroke={a.color} strokeWidth={thickness}
          strokeDasharray={`${a.dash.toFixed(2)} ${a.gap.toFixed(2)}`}
          strokeDashoffset={-a.offset} strokeLinecap="round" />
      ))}
    </svg>
  );
}

// ─── Radial health gauge ─────────────────────────────────────────────────────
export function HealthGauge({ score, size = 88 }: { score: number; size?: number }) {
  const r = size * 0.38; const cx = size / 2; const cy = size * 0.52;
  const startAngle = -210; const sweepAngle = 240;
  const angle = startAngle + (score / 100) * sweepAngle;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const arcPath = (a: number) => `${cx + r * Math.cos(toRad(a))},${cy + r * Math.sin(toRad(a))}`;
  const start = arcPath(startAngle); const end = arcPath(startAngle + sweepAngle);
  const active = arcPath(angle);
  const large = sweepAngle > 180 ? 1 : 0;
  const activeLarge = score / 100 * sweepAngle > 180 ? 1 : 0;
  const color = score >= 75 ? 'var(--sys-success)' : score >= 50 ? 'var(--sys-warning)' : 'var(--sys-danger)';
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={`M${start} A${r},${r} 0 ${large},1 ${end}`} fill="none" stroke="var(--sys-faint)" strokeWidth="5" strokeLinecap="round" />
      <path d={`M${start} A${r},${r} 0 ${activeLarge},1 ${active}`} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" />
      <text x={cx} y={cy + 6} textAnchor="middle" fontSize={size * 0.22} fontWeight="800" fill={color}>{score.toFixed(0)}</text>
    </svg>
  );
}

// ─── Vertical bar chart ──────────────────────────────────────────────────────
interface BarChartProps { data: { label: string; value: number; color?: string }[]; height?: number }
export function BarChart({ data, height = 120 }: BarChartProps) {
  const W = 300; const H = height; const max = Math.max(...data.map(d => d.value), 0.001);
  const barW = Math.floor((W - (data.length + 1) * 6) / data.length);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} className="sys-chart">
      {data.map((d, i) => {
        const bh = Math.max(2, (d.value / max) * (H - 24));
        const x = 6 + i * (barW + 6); const y = H - bh - 16;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={bh} rx="3" fill={d.color ?? 'var(--sys-accent)'} opacity="0.8" />
            <text x={x + barW / 2} y={H - 3} textAnchor="middle" fontSize="9" fill="var(--sys-muted)">{d.label}</text>
          </g>
        );
      })}
    </svg>
  );
}