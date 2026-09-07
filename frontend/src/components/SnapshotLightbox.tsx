import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import BboxOverlay from './BboxOverlay';
import { useEscape } from '../lib/useEscape';

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
  caption?: string;
  onClose: () => void;
}

interface View {
  scale: number;
  tx: number;
  ty: number;
}

const MAX_SCALE = 8;
const RESET: View = { scale: 1, tx: 0, ty: 0 };

/** Полноэкранный просмотр снимка с рамками детекций.
 *  Колёсико — масштаб к курсору, перетаскивание — панорама, двойной клик —
 *  приблизить/сбросить, на телефоне — пинч двумя пальцами. */
export default function SnapshotLightbox({ imageUrl, detections, caption, onClose }: Props) {
  useEscape(onClose);

  // Размер пересчитывается при ресайзе окна; сами пропорции кадра BboxOverlay
  // уже обрабатывает через object-contain, контейнеру важно лишь не вылезать
  // за вьюпорт.
  const [size, setSize] = useState(() => viewportSize());
  useEffect(() => {
    const onResize = () => setSize(viewportSize());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Пока лайтбокс открыт, страница под ним не должна прокручиваться —
  // иначе колёсико при зуме мотает страницу.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  const [view, setView] = useState<View>(RESET);
  // Актуальные scale и onClose для нативного wheel-слушателя (он вешается
  // один раз и не должен пересоздаваться на каждый рендер).
  const viewRef = useRef(view);
  viewRef.current = view;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  // Колесо/дабл-клик анимируем коротким переходом (плавный зум); во время
  // перетаскивания и пинча переход выключен, иначе картинка «резинит».
  const [animated, setAnimated] = useState(true);
  const stageRef = useRef<HTMLDivElement>(null);
  // Активные указатели (мышь при drag / пальцы при пинче), позиции в
  // координатах сцены.
  const pointers = useRef(new Map<number, { x: number; y: number }>());

  // Зум так, чтобы точка (px, py) сцены осталась под курсором.
  const zoomAt = (v: View, px: number, py: number, factor: number): View => {
    const scale = Math.min(MAX_SCALE, Math.max(1, v.scale * factor));
    if (scale <= 1.001) return RESET;
    const k = scale / v.scale;
    return clampPan({ scale, tx: px - (px - v.tx) * k, ty: py - (py - v.ty) * k });
  };

  // Не даём утащить изображение за пределы сцены.
  const clampPan = (v: View): View => ({
    ...v,
    tx: Math.min(0, Math.max(size.w * (1 - v.scale), v.tx)),
    ty: Math.min(0, Math.max(size.h * (1 - v.scale), v.ty)),
  });

  // Нативный слушатель: onWheel из React может оказаться пассивным, а без
  // preventDefault колесо прокручивает страницу вместо зума.
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      // Колесо вниз на минимальном масштабе сворачивает просмотр — зеркально
      // открытию по колесу вверх из карточки (Арсений 2026-08-03).
      if (e.deltaY > 0 && viewRef.current.scale <= 1) {
        onCloseRef.current();
        return;
      }
      const rect = el.getBoundingClientRect();
      // Шаг зума пропорционален прокрутке: у мыши ~1.22 на щелчок, у тачпада
      // много мелких шагов — выходит плавно в обоих случаях.
      setAnimated(true);
      setView((v) =>
        zoomAt(v, e.clientX - rect.left, e.clientY - rect.top, Math.exp(-e.deltaY * 0.002))
      );
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
    // zoomAt/clampPan зависят только от size
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size.w, size.h]);

  const stagePoint = (e: React.PointerEvent | React.MouseEvent) => {
    const rect = stageRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const handlePointerDown = (e: React.PointerEvent) => {
    pointers.current.set(e.pointerId, stagePoint(e));
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    const prev = pointers.current.get(e.pointerId);
    if (!prev) return;
    const now = stagePoint(e);
    pointers.current.set(e.pointerId, now);

    if (pointers.current.size === 2) {
      // Пинч: масштаб по изменению расстояния между пальцами, центр — середина.
      const [a, b] = [...pointers.current.values()];
      const other = a.x === now.x && a.y === now.y ? b : a;
      const dPrev = Math.hypot(other.x - prev.x, other.y - prev.y);
      const dNow = Math.hypot(other.x - now.x, other.y - now.y);
      if (dPrev > 0) {
        const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        setAnimated(false);
        setView((v) => zoomAt(v, mid.x, mid.y, dNow / dPrev));
      }
    } else if (view.scale > 1) {
      setAnimated(false);
      setView((v) => clampPan({ ...v, tx: v.tx + now.x - prev.x, ty: v.ty + now.y - prev.y }));
    }
  };

  const handlePointerEnd = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    const p = stagePoint(e);
    setAnimated(true);
    setView((v) => (v.scale > 1 ? RESET : zoomAt(v, p.x, p.y, 2.5)));
  };

  return (
    <div
      className="fixed inset-0 z-[1100] bg-black/85 flex flex-col items-center justify-center p-4 overflow-hidden"
      onClick={onClose}
      role="dialog"
      aria-label="Просмотр снимка"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Закрыть"
        className="absolute top-4 right-4 z-10 p-2 rounded-full text-white/80 hover:text-white hover:bg-white/10"
      >
        <X size={22} />
      </button>
      <div
        ref={stageRef}
        data-testid="lightbox-stage"
        onClick={(e) => e.stopPropagation()}
        onDoubleClick={handleDoubleClick}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerEnd}
        onPointerCancel={handlePointerEnd}
        className="overflow-hidden touch-none select-none"
        style={{
          width: size.w,
          height: size.h,
          cursor: view.scale > 1 ? 'grab' : 'zoom-in',
        }}
      >
        <div
          data-testid="lightbox-zoom"
          // Гасим серую подложку BboxOverlay: на чёрном фоне лайтбокса
          // letterbox-поля должны быть чёрными, а не светло-серыми.
          className="[&_img]:bg-transparent!"
          style={{
            width: size.w,
            height: size.h,
            transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})`,
            transformOrigin: '0 0',
            transition: animated ? 'transform 0.15s ease-out' : undefined,
          }}
        >
          <BboxOverlay
            imageUrl={imageUrl}
            detections={detections}
            width={size.w}
            height={size.h}
          />
        </div>
      </div>
      <div className="mt-3 text-sm text-white/70 text-center">
        {caption && <div>{caption}</div>}
        <div className="text-xs text-white/40 mt-1 hidden md:block">
          Колёсико — масштаб (вниз до упора — закрыть) · перетаскивание — перемещение ·
          двойной клик — сброс
        </div>
      </div>
    </div>
  );
}

function viewportSize() {
  return {
    w: Math.min(Math.round(window.innerWidth * 0.92), 1500),
    h: Math.round(window.innerHeight * 0.86),
  };
}
