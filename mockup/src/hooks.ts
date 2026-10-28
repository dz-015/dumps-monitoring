import { useEffect, useRef, useState, type RefObject } from 'react';
import { useApp } from './ctx';
import { paletteOf } from './theme';
import type { Status } from './data';

/** Настоящие цвета статусов (для карты и легенд, где CSS-переменная не подходит). */
export function useStatusColors(): Record<Status, string> {
  const { settings } = useApp();
  const { clean, overflow, contamination } = paletteOf(settings);
  return { clean, overflow, contamination };
}

export const STATUS_ORDER: Status[] = ['clean', 'overflow', 'contamination'];

/**
 * Держит элемент в DOM, пока играет анимация ухода.
 * mounted — рендерить ли вообще; shown — класс «видим» (ставится кадром позже,
 * чтобы переход сработал и на появлении).
 */
export function usePresence(open: boolean, ms = 220): { mounted: boolean; shown: boolean } {
  const [mounted, setMounted] = useState(open);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (open) {
      setMounted(true);
      const id = requestAnimationFrame(() => requestAnimationFrame(() => setShown(true)));
      return () => cancelAnimationFrame(id);
    }
    setShown(false);
    const t = setTimeout(() => setMounted(false), ms);
    return () => clearTimeout(t);
  }, [open, ms]);
  return { mounted, shown };
}

/** Включены ли анимации: настройка макета и системное «уменьшить движение». */
export function useMotion(): boolean {
  const { settings } = useApp();
  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  return settings.motion && !reduced;
}

/** Ход анимации от 0 до 1 с замедлением к концу. Перезапускается при смене key. */
export function useProgress(ms: number, key: unknown = 0): number {
  const motion = useMotion();
  const [p, setP] = useState(motion ? 0 : 1);
  useEffect(() => {
    if (!motion) {
      setP(1);
      return;
    }
    const t0 = performance.now();
    let raf = 0;
    const f = (t: number) => {
      const x = Math.min(1, (t - t0) / ms);
      setP(1 - Math.pow(1 - x, 3));
      if (x < 1) raf = requestAnimationFrame(f);
    };
    raf = requestAnimationFrame(f);
    return () => cancelAnimationFrame(raf);
  }, [key, motion, ms]);
  return p;
}

/**
 * Плавная прокрутка колесом внутри отдельного блока (список на карте).
 * Каждый кадр проходит долю оставшегося пути: чем больше ease, тем быстрее.
 */
export function useSmoothWheel(ref: RefObject<HTMLElement | null>, ease = 0.24) {
  const motion = useMotion();
  useEffect(() => {
    const el = ref.current;
    if (!el || !motion) return;
    let pos = el.scrollTop;
    let target = pos;
    let raf = 0;
    const step = () => {
      const d = target - pos;
      if (Math.abs(d) < 0.5) {
        pos = target;
        el.scrollTop = pos;
        raf = 0;
        return;
      }
      pos += d * ease;
      el.scrollTop = pos;
      raf = requestAnimationFrame(step);
    };
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey) return;
      const max = el.scrollHeight - el.clientHeight;
      if (max <= 0) return;
      e.preventDefault();
      e.stopPropagation();
      if (!raf) pos = target = el.scrollTop; // прокрутили ползунком или клавишами — начинаем с текущего места
      const dy = e.deltaMode === 1 ? e.deltaY * 33 : e.deltaMode === 2 ? e.deltaY * el.clientHeight : e.deltaY;
      target = Math.max(0, Math.min(max, target + dy));
      if (!raf) raf = requestAnimationFrame(step);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      el.removeEventListener('wheel', onWheel);
      cancelAnimationFrame(raf);
    };
  }, [ref, ease, motion]);
}

/**
 * Прокрутка колесом «к себе» над кадром открывает просмотр и сразу приближает
 * к точке под курсором. «От себя» — обычная прокрутка страницы.
 */
export function useWheelToOpen(open: (at: [number, number]) => void): (el: HTMLElement | null) => void {
  const cb = useRef(open);
  cb.current = open;
  // Кадр может появиться позже (загрузка, открытие панели) — поэтому ref-функция, а не объект.
  const [el, setEl] = useState<HTMLElement | null>(null);
  useEffect(() => {
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY >= 0 || e.ctrlKey) return;
      e.preventDefault();
      e.stopPropagation();
      // Просмотр уже открыт, а браузер ещё шлёт ту же прокрутку сюда — передаём её туда.
      if (document.querySelector('.lightbox')) {
        window.dispatchEvent(new CustomEvent('lb-wheel', { detail: { deltaY: e.deltaY, deltaMode: e.deltaMode, clientX: e.clientX, clientY: e.clientY } }));
        return;
      }
      const r = el.getBoundingClientRect();
      cb.current([(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [el]);
  return setEl;
}
