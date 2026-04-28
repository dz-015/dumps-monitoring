import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';

const TONES: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-700 hover:bg-blue-100',
  yellow: 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100',
  green: 'bg-green-50 text-green-700 hover:bg-green-100',
  red: 'bg-red-50 text-red-700 hover:bg-red-100',
};

export type DropdownOption = {
  value: string;
  label: string;
  tone?: keyof typeof TONES;
};

interface Props {
  value: string;
  onChange: (value: string) => void;
  options: DropdownOption[];
  ariaLabel?: string;
}

export default function Dropdown({ value, onChange, options, ariaLabel }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const current = options.find((o) => o.value === value) ?? options[0];

  return (
    <div ref={rootRef} className="relative inline-block">
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="appearance-none border border-gray-200 rounded-xl pl-3 pr-9 py-2 text-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-sky-400 min-w-[160px] text-left"
      >
        {current?.label ?? ''}
        <ChevronDown
          size={16}
          className={`pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg p-1 max-h-64 overflow-y-auto"
        >
          {options.map((o) => {
            const tone = o.tone ? TONES[o.tone] : 'text-gray-700 hover:bg-gray-100';
            const isActive = o.value === value;
            return (
              <li key={o.value}>
                <button
                  type="button"
                  role="option"
                  aria-selected={isActive}
                  onClick={() => {
                    onChange(o.value);
                    setOpen(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors ${tone} ${
                    isActive ? 'ring-1 ring-inset ring-sky-300' : ''
                  }`}
                >
                  {o.label}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
