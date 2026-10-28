import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { Check, ChevronDown, TriangleAlert } from 'lucide-react';
import type { Tone } from '../theme';
import { STATUS_LABEL } from '../data';
import { usePresence } from '../hooks';

/** Метка статуса: точка цвета статуса и обычный текст. */
export function Badge({ tone, label }: { tone: Tone; label?: string }) {
  const style = { '--c': `var(--t-${tone})`, '--cs': `var(--t-${tone}-soft)` } as CSSProperties;
  return (
    <span className="badge" style={style}>
      <i />
      {label ?? STATUS_LABEL[tone]}
    </span>
  );
}

export function Wordmark({ size = 15 }: { size?: number }) {
  return (
    <span className="wordmark" style={{ fontSize: size }}>
      <b>ТКО</b>
      <span className="wordmark-bar" style={{ height: size * 0.95 }} />
      <span>Мониторинг</span>
    </span>
  );
}

export function Logo({ size = 32 }: { size?: number }) {
  return <img className="logo" src="/logo.svg" alt="ТКО | Мониторинг" style={{ width: size, height: size }} />;
}

export function PageHeader({ title, subtitle, right }: { title: ReactNode; subtitle?: ReactNode; right?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="error-banner" role="alert">
      <TriangleAlert size={16} />
      <span>{message}</span>
      <button type="button" className="link-btn" onClick={onRetry}>
        Повторить
      </button>
    </div>
  );
}

export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="panel load-error">
      <TriangleAlert size={20} className="red-ink" />
      <div>{message}</div>
      <button type="button" className="btn btn-secondary" onClick={onRetry}>
        Повторить
      </button>
    </div>
  );
}

export function Skeleton() {
  return (
    <div className="skeleton" aria-label="Загрузка">
      <div className="sk" style={{ height: 96 }} />
      <div className="grid-5-7">
        <div className="sk" style={{ height: 250 }} />
        <div className="sk" style={{ height: 250 }} />
      </div>
      <div className="sk" style={{ height: 220 }} />
    </div>
  );
}

export function Empty({ icon, text }: { icon?: ReactNode; text: string }) {
  return (
    <div className="empty">
      {icon}
      <span>{text}</span>
    </div>
  );
}

export type DropdownOption = { value: string; label: string; color?: string };

export function Dropdown({
  value,
  options,
  onChange,
  ariaLabel,
  align = 'left',
}: {
  value: string;
  options: DropdownOption[];
  onChange: (v: string) => void;
  ariaLabel: string;
  align?: 'left' | 'right';
}) {
  const [open, setOpen] = useState(false);
  const { mounted, shown } = usePresence(open, 140);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);
  const cur = options.find((o) => o.value === value) ?? options[0];
  return (
    <div className="dropdown" ref={ref}>
      <button type="button" className={`dropdown-btn ${open ? 'open' : ''}`} aria-label={ariaLabel} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {cur.color && <span className="dot" style={{ background: cur.color }} />}
        <span className="dropdown-label">{cur.label}</span>
        <ChevronDown size={15} className="dropdown-chev" />
      </button>
      {mounted && (
        <div className={`dropdown-menu ${align === 'right' ? 'right' : ''} ${shown ? 'shown' : ''}`} role="listbox" data-lenis-prevent>
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="option"
              aria-selected={o.value === value}
              className="dropdown-item"
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
            >
              {o.color ? <span className="dot" style={{ background: o.color }} /> : <span className="dot-space" />}
              <span className="grow">{o.label}</span>
              {o.value === value && <Check size={15} className="p-ink" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Chips<T extends string>({
  items,
  value,
  onChange,
}: {
  items: { value: T; label: string; color?: string; count?: number }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="chips">
      {items.map((it) => (
        <button key={it.value} type="button" aria-pressed={value === it.value} className={`chip ${value === it.value ? 'on' : ''}`} onClick={() => onChange(it.value)}>
          {it.color && <span className="dot" style={{ background: it.color }} />}
          {it.label}
          {it.count !== undefined && <span className="chip-count">{it.count}</span>}
        </button>
      ))}
    </div>
  );
}
