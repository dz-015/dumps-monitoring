import { useState } from 'react';

const CLASS_COLORS: Record<string, string> = {
  metal_ok: '#22c55e',
  metal_overflow: '#ef4444',
  plastic_ok: '#22c55e',
  plastic_overflow: '#ef4444',
  euro_ok: '#22c55e',
  euro_overflow: '#ef4444',
  ground_trash: '#f97316',
};

const CLASS_LABELS: Record<string, string> = {
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
}

export default function BboxOverlay({ imageUrl, detections, width = 640, height = 480 }: Props) {
  // Keyed by URL so a stale size from the previous carousel image is never
  // applied to the next one.
  const [natural, setNatural] = useState<{ url: string; w: number; h: number } | null>(null);

  // object-contain letterboxes any image whose aspect ratio differs from the
  // container, so normalized YOLO coords must be mapped onto the RENDERED
  // image rect — scaling by the raw container size drew boxes over the bars
  // (BUG-19). Until the image loads we fall back to the container rect.
  let rx = 0;
  let ry = 0;
  let rw = width;
  let rh = height;
  if (natural && natural.url === imageUrl && natural.w > 0 && natural.h > 0) {
    const scale = Math.min(width / natural.w, height / natural.h);
    rw = natural.w * scale;
    rh = natural.h * scale;
    rx = (width - rw) / 2;
    ry = (height - rh) / 2;
  }

  return (
    <div className="relative inline-block" style={{ width, height }}>
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
        viewBox={`0 0 ${width} ${height}`}
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
