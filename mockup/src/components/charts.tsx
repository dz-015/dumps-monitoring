import { useId, useRef, useState } from 'react';
import { useProgress } from '../hooks';

// Графики без библиотек: тонкая плавная линия с едва заметной заливкой.
// Точки не рисуются постоянно — только та, над которой курсор.
// Появление как на основном сайте (Recharts): график проявляется слева направо,
// кольцо диаграммы прорисовывается по часовой стрелке.

function smoothPath(pts: [number, number][], H: number): string {
  const cl = (y: number) => Math.max(0, Math.min(H, y));
  let d = `M${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const a = [p1[0] + (p2[0] - p0[0]) / 6, cl(p1[1] + (p2[1] - p0[1]) / 6)];
    const b = [p2[0] - (p3[0] - p1[0]) / 6, cl(p2[1] - (p3[1] - p1[1]) / 6)];
    d += ` C${a[0].toFixed(1)} ${a[1].toFixed(1)} ${b[0].toFixed(1)} ${b[1].toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
}

export function AreaChart({
  values,
  labels,
  height = 160,
  every = 1,
  unit = 'проблем',
}: {
  values: number[];
  labels: string[];
  height?: number;
  every?: number;
  unit?: string;
}) {
  const W = 600;
  const H = height;
  const n = values.length;
  const top = Math.max(4, Math.ceil(Math.max(...values) / 4) * 4);
  const pts = values.map((v, i) => [(i * W) / (n - 1), H - (v / top) * H * 0.92] as [number, number]);
  const d = smoothPath(pts, H);
  const [hover, setHover] = useState<number | null>(null);
  const plot = useRef<HTMLDivElement>(null);
  const p = useProgress(1100);
  const clip = `reveal-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;

  const onMove = (e: React.PointerEvent) => {
    const r = plot.current!.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left) / r.width) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };

  return (
    <div className="chart">
      <div className="chart-plot" style={{ height }} ref={plot} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {[top, top / 2, 0].map((v) => (
          <div key={v} className="chart-grid" style={{ top: `${(1 - (v / top) * 0.92) * 100}%` }}>
            <span>{Math.round(v)}</span>
          </div>
        ))}
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="chart-svg">
          <defs>
            <clipPath id={clip}>
              <rect x="-4" y="-4" width={(W + 8) * p} height={H + 8} />
            </clipPath>
          </defs>
          <g clipPath={`url(#${clip})`}>
            <path d={`${d} L${W} ${H} L0 ${H} Z`} className="chart-area" />
            <path d={d} className="chart-line" />
          </g>
        </svg>
        {hover !== null && (
          <>
            <div className="chart-guide" style={{ left: `${(pts[hover][0] / W) * 100}%` }} />
            <div className="chart-dot" style={{ left: `${(pts[hover][0] / W) * 100}%`, top: `${(pts[hover][1] / H) * 100}%` }} />
            <div
              className="chart-tip"
              style={{
                left: `${(pts[hover][0] / W) * 100}%`,
                transform: `translateX(${hover < n * 0.15 ? '0' : hover > n * 0.85 ? '-100%' : '-50%'})`,
              }}
            >
              <span className="muted">{labels[hover]}</span> <b>{values[hover]}</b> {unit}
            </div>
          </>
        )}
      </div>
      <div className="chart-x">
        {labels.map((l, i) =>
          i % every === 0 || i === n - 1 ? (
            <span key={i} style={{ left: `${(i / (n - 1)) * 100}%`, transform: `translateX(${i === 0 ? '0' : i === n - 1 ? '-100%' : '-50%'})` }}>
              {l}
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}

export function Donut({ segments, size = 148, centerValue, centerLabel }: { segments: { value: number; color: string }[]; size?: number; centerValue: string; centerLabel: string }) {
  const C = 2 * Math.PI * 64;
  const total = segments.reduce((a, s) => a + s.value, 0);
  const drawn = useProgress(1200) * C;
  let off = 0;
  return (
    <div className="donut" style={{ width: size, height: size }}>
      <svg viewBox="0 0 160 160" width={size} height={size}>
        <circle cx="80" cy="80" r="64" className="donut-track" />
        <g transform="rotate(-90 80 80)">
          {segments.map((s, i) => {
            const len = total ? (s.value / total) * C : 0;
            const gap = s.value && s.value < total ? 2.5 : 0;
            const visible = Math.max(0, Math.min(len - gap, drawn - off));
            const el = <circle key={i} cx="80" cy="80" r="64" className={`donut-seg ${drawn < C ? 'drawing' : ''}`} style={{ stroke: s.color, strokeDasharray: `${visible} ${C}`, strokeDashoffset: -off }} />;
            off += len;
            return el;
          })}
        </g>
      </svg>
      <div className="donut-center">
        <b>
          <CountUp value={centerValue} />
        </b>
        <span>{centerLabel}</span>
      </div>
    </div>
  );
}

/** Число, которое «набегает» от нуля при появлении. Понимает суффикс: «58%». */
export function CountUp({ value, ms = 900 }: { value: string; ms?: number }) {
  const m = value.match(/^(\d+)(.*)$/);
  const p = useProgress(ms, value);
  if (!m) return <>{value}</>;
  return (
    <>
      {Math.round(Number(m[1]) * p)}
      {m[2]}
    </>
  );
}
