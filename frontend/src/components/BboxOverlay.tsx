import { useEffect, useRef, useState } from 'react';

const CLASS_COLORS: Record<string, string> = {
  bin_ok: '#22c55e',
  bin_overflow: '#ef4444',
  metal_ok: '#22c55e',
  metal_overflow: '#ef4444',
  plastic_ok: '#22c55e',
  plastic_overflow: '#ef4444',
  euro_ok: '#22c55e',
  euro_overflow: '#ef4444',
  ground_trash: '#f97316',
};

const CLASS_LABELS: Record<string, string> = {
  bin_ok: 'Бак ОК',
  bin_overflow: 'Бак перепол.',
  metal_ok: 'Металл ОК',
  metal_overflow: 'Металл перепол.',
  plastic_ok: 'Пластик ОК',
  plastic_overflow: 'Пластик перепол.',
  euro_ok: 'Евро ОК',
  euro_overflow: 'Евро перепол.',
  ground_trash: 'Мусор на земле',
};

interface Detection {
  class_name: string;
  confidence: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Props {
  imageUrl: string;
  detections: Detection[];
  width?: number;
  height?: number;
  /** Занять весь родительский блок; width/height тогда игнорируются,
   *  система координат берётся из замеренного размера контейнера. */
  fill?: boolean;
}

export default function BboxOverlay({
  imageUrl,
  detections,
  width = 640,
  height = 480,
  fill = false,
}: Props) {
  // Keyed by URL so a stale size from the previous carousel image is never
  // applied to the next one.
  const [natural, setNatural] = useState<{ url: string; w: number; h: number } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    if (!fill || typeof ResizeObserver === 'undefined') return;
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width: w, height: h } = entries[entries.length - 1].contentRect;
      if (w > 0 && h > 0) setMeasured({ w, h });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fill]);

  const boxW = fill && measured ? measured.w : width;
  const boxH = fill && measured ? measured.h : height;

  // object-contain letterboxes any image whose aspect ratio differs from the
  // container, so normalized YOLO coords must be mapped onto the RENDERED
  // image rect — scaling by the raw container size drew boxes over the bars
  // (BUG-19). Until the image loads we fall back to the container rect.
  let rx = 0;
  let ry = 0;
  let rw = boxW;
  let rh = boxH;
  if (natural && natural.url === imageUrl && natural.w > 0 && natural.h > 0) {
    const scale = Math.min(boxW / natural.w, boxH / natural.h);
    rw = natural.w * scale;
    rh = natural.h * scale;
    rx = (boxW - rw) / 2;
    ry = (boxH - rh) / 2;
  }

  // Без fill width/height задают систему координат (viewBox) и максимальный
  // размер; сам контейнер резиновый — на узких экранах ужимается, сохраняя
  // пропорции, и рамки остаются на месте (SVG и object-contain масштабируются
  // одинаково). С fill контейнер целиком заполняет родителя, а система
  // координат равна его замеренному размеру.
  return (
    <div
      ref={containerRef}
      className={fill ? 'relative w-full h-full' : 'relative'}
      style={
        fill ? undefined : { width: '100%', maxWidth: width, aspectRatio: `${width} / ${height}` }
      }
    >
      <img
        src={imageUrl}
        alt="snapshot"
        onLoad={(e) =>
          setNatural({
            url: imageUrl,
            w: e.currentTarget.naturalWidth,
            h: e.currentTarget.naturalHeight,
          })
        }
        className="w-full h-full object-contain bg-gray-100 rounded-lg"
      />
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox={`0 0 ${boxW} ${boxH}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {detections.map((d, i) => {
          const bx = rx + (d.x - d.w / 2) * rw;
          const by = ry + (d.y - d.h / 2) * rh;
          const bw = d.w * rw;
          const bh = d.h * rh;
          const color = CLASS_COLORS[d.class_name] || '#94a3b8';
          const label = CLASS_LABELS[d.class_name] || d.class_name;

          return (
            <g key={i}>
              <rect
                x={bx}
                y={by}
                width={bw}
                height={bh}
                fill="none"
                stroke={color}
                strokeWidth={2}
              />
              <rect
                x={bx}
                y={by - 16}
                width={label.length * 6.5 + 30}
                height={16}
                fill={color}
                rx={2}
              />
              <text x={bx + 3} y={by - 4} fill="white" fontSize={10} fontFamily="sans-serif">
                {label} {(d.confidence * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
