import type { CSSProperties } from 'react';

// Палитра намеренно сдержанная: нейтральная серая основа и один акцент —
// небесно-голубой. Зелёный, жёлтый и красный появляются только там, где они
// что-то сообщают: статус площадки, рамки детекций, графики.

export type Settings = {
  theme: 'light' | 'dark';
  primary: string;
  /** Набор цветов статусов (зелёный, жёлтый, красный) — только сигналы и графики. */
  palette: PaletteKey;
  sidebar: 'light' | 'gray';
  badges: 'dot' | 'soft';
  font: string;
  radius: number;
  density: 'comfortable' | 'compact';
  dataState: 'normal' | 'loading' | 'error' | 'empty';
  device: 'desktop' | 'phone';
  mapStyle: 'calm' | 'osm';
  motion: boolean;
};

export const DEFAULTS: Settings = {
  theme: 'light',
  primary: '#0EA5E9',
  palette: 'soft',
  sidebar: 'light',
  badges: 'dot',
  font: 'Onest',
  radius: 10,
  density: 'comfortable',
  dataState: 'normal',
  device: 'desktop',
  mapStyle: 'osm',
  motion: true,
};

export const PRIMARY_SWATCHES = ['#0EA5E9', '#38BDF8', '#0284C7', '#2196F3'];
export const FONTS = ['Onest', 'Manrope', 'Golos Text', 'IBM Plex Sans'];

// Цвет опасных действий («Удалить», «Выйти») — от палитры статусов не зависит.
const DANGER = '#DC2626';

/** Палитры статусов: одни и те же три цвета в разных оттенках. */
export const PALETTES = {
  soft: { label: 'Мягкая', clean: '#34B27B', overflow: '#E9A23B', contamination: '#E5625E' },
  classic: { label: 'Классическая', clean: '#16A34A', overflow: '#D97706', contamination: '#DC2626' },
  bright: { label: 'Яркая', clean: '#22C55E', overflow: '#F59E0B', contamination: '#EF4444' },
  muted: { label: 'Приглушённая', clean: '#5FA37A', overflow: '#C99846', contamination: '#C4625A' },
  deep: { label: 'Глубокая', clean: '#15803D', overflow: '#B45309', contamination: '#B91C1C' },
  lime: { label: 'Салатовая', clean: '#84CC16', overflow: '#F5A524', contamination: '#F0524F' },
} as const;
export type PaletteKey = keyof typeof PALETTES;
export function paletteOf(s: Settings) {
  return PALETTES[s.palette] ?? PALETTES[DEFAULTS.palette];
}

// ---- работа с цветом ----
function rgb(h: string): number[] {
  let x = h.replace('#', '');
  if (x.length === 3) x = x.split('').map((c) => c + c).join('');
  return [0, 2, 4].map((i) => parseInt(x.substring(i, i + 2), 16) || 0);
}
function hex(a: number[]): string {
  return '#' + a.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('');
}
export function mix(a: string, b: string, k: number): string {
  const A = rgb(a);
  const B = rgb(b);
  return hex(A.map((v, i) => v + (B[i] - v) * k));
}
function lum(h: string): number {
  const c = rgb(h).map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function contrast(a: string, b: string): number {
  const x = lum(a);
  const y = lum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
/** Темнит (или светлит на тёмном фоне) цвет, пока он не станет читаемым на фоне. */
export function ink(fg: string, bg: string, target = 4.5): string {
  let c = fg;
  const toward = lum(bg) > 0.4 ? '#06121C' : '#FFFFFF';
  for (let i = 0; i < 30 && contrast(c, bg) < target; i++) c = mix(c, toward, 0.08);
  return c;
}
/** Белый или тёмный текст — что контрастнее на этой заливке. */
export function onColor(bg: string): string {
  return contrast('#FFFFFF', bg) >= contrast('#0A1F2E', bg) ? '#FFFFFF' : '#0A1F2E';
}

export const TONE_KEYS = ['clean', 'overflow', 'contamination', 'new', 'accepted', 'resolved'] as const;
export type Tone = (typeof TONE_KEYS)[number];

/** Все цвета и размеры макета — CSS-переменные на корневом элементе. */
export function buildVars(s: Settings): Record<string, string> {
  const dark = s.theme === 'dark';
  const P = s.primary;
  const pal = paletteOf(s);
  const G = pal.clean;
  const AMBER = pal.overflow;
  const RED = DANGER;
  const n = dark
    ? { bg: '#0D1117', surface: '#11161D', surface2: '#161C24', hover: '#1A212B', border: '#232B36', borderStrong: '#2E3845', text: '#E6EAF0', text2: '#A7B0BC', text3: '#7F8995', input: '#0D1117', skel: '#1A212B' }
    : { bg: '#FAFAFB', surface: '#FFFFFF', surface2: '#F6F7F9', hover: '#F3F4F6', border: '#E7E9EE', borderStrong: '#D6DAE1', text: '#111827', text2: '#4B5563', text3: '#6B7280', input: '#FFFFFF', skel: '#EEF0F3' };
  const surface = n.surface;
  const v: Record<string, string> = {
    '--bg': n.bg,
    '--surface': surface,
    '--surface2': n.surface2,
    '--hover': n.hover,
    '--border': n.border,
    '--border-strong': n.borderStrong,
    '--text': n.text,
    '--text2': n.text2,
    '--text3': n.text3,
    '--input': n.input,
    '--skel': n.skel,
    '--overlay': dark ? 'rgba(0,0,0,0.55)' : 'rgba(17,24,39,0.28)',
    '--shadow-md': dark ? '0 8px 24px rgba(0,0,0,.45)' : '0 8px 24px rgba(17,24,39,.08)',
    '--shadow-lg': dark ? '0 20px 50px rgba(0,0,0,.55)' : '0 20px 50px rgba(17,24,39,.14)',
    '--tip-bg': dark ? '#E6EAF0' : '#111827',
    '--tip-text': dark ? '#111827' : '#FFFFFF',

    '--p': P,
    '--on-p': onColor(P),
    '--p-ink': ink(P, surface),
    '--p-soft': mix(surface, P, dark ? 0.16 : 0.08),
    '--p-line': ink(P, surface, 2.4),
    '--g': G,
    '--red': RED,
    '--on-red': onColor(RED),
    '--red-ink': ink(RED, surface),
    '--red-soft': mix(surface, RED, dark ? 0.14 : 0.07),
    '--amber': AMBER,

    '--r': `${s.radius}px`,
    '--rs': `${Math.max(4, Math.round(s.radius * 0.8))}px`,
    '--rl': `${s.radius + 4}px`,
    '--font': `'${s.font}', system-ui, sans-serif`,
    '--mono': `'JetBrains Mono', ui-monospace, monospace`,
  };
  v['--p-soft-ink'] = ink(P, v['--p-soft']);

  // Статусы. «Принят» и «Решён» — нейтральные: они не требуют внимания.
  const toneColor: Record<Tone, string> = { clean: G, overflow: AMBER, contamination: pal.contamination, new: P, accepted: dark ? '#7F8995' : '#9CA3AF', resolved: dark ? '#4B5563' : '#D1D5DB' };
  for (const k of TONE_KEYS) {
    const col = toneColor[k];
    v[`--t-${k}`] = col;
    v[`--t-${k}-soft`] = mix(surface, col, dark ? 0.16 : 0.1);
  }

  v['--sb-bg'] = s.sidebar === 'gray' ? (dark ? '#0D1117' : '#F6F7F9') : surface;
  return v;
}

export function varsStyle(v: Record<string, string>): CSSProperties {
  return v as unknown as CSSProperties;
}

/** Текст для кнопки «Скопировать токены»: готовый блок :root для переноса во фронтенд. */
export function varsAsCss(v: Record<string, string>): string {
  return ':root {\n' + Object.entries(v).map(([k, val]) => `  ${k}: ${val};`).join('\n') + '\n}\n';
}
