import type { FrameInfo } from '../data';

// Настоящий кадр с камеры и рамки, которые на нём нашла модель.
// Кадры 16:9, контейнер тоже 16:9 — поэтому доли кадра переводятся в проценты напрямую.

const LABEL: Record<string, string> = { bin_ok: 'Бак', bin_overflow: 'Переполнен', ground_trash: 'Мусор' };

export function Frame({
  frame,
  boxes = true,
  labels = 'problems',
}: {
  frame: FrameInfo;
  boxes?: boolean;
  /** problems — подписи только у проблемных рамок; all — у всех; none — без подписей. */
  labels?: 'problems' | 'all' | 'none';
}) {
  return (
    <div className="frame">
      <img src={`/frames/${frame.name}`} alt={`Кадр с камеры ${frame.cam}`} loading="lazy" draggable={false} />
      <div className={`frame-boxes ${boxes ? '' : 'hidden'}`}>
        {frame.dets.map((d, i) => {
          const problem = d.c !== 'bin_ok';
          const showLabel = labels === 'all' || (labels === 'problems' && problem);
          return (
            <span
              key={i}
              className={`box box-${d.c}`}
              style={{ left: `${(d.x - d.w / 2) * 100}%`, top: `${(d.y - d.h / 2) * 100}%`, width: `${d.w * 100}%`, height: `${d.h * 100}%` }}
            >
              {showLabel && (
                <span className="box-label">
                  {LABEL[d.c] ?? d.c} {d.p.toFixed(2)}
                </span>
              )}
            </span>
          );
        })}
      </div>
    </div>
  );
}
