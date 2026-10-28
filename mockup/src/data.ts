// Выдуманные данные макета. Первые 8 площадок — из backend/app/seed.py,
// остальные 4 добавлены, чтобы на карте было что показать.

export type Status = 'clean' | 'overflow' | 'contamination';
export type Level = 'overflow' | 'contamination';
export type AlertStatus = 'new' | 'accepted' | 'resolved';
export type Reason = 'confirmed_and_cleared' | 'false_alarm' | 'resolved_externally';

export type Site = {
  id: number;
  name: string;
  address: string;
  lat: number | null;
  lng: number | null;
  key: string;
  rtsp: string;
  active: boolean;
  checked: string;
};

export type Alert = {
  id: number;
  siteId: number;
  level: Level;
  status: AlertStatus;
  /** Сколько дней назад создано (0 — сегодня). */
  d: number;
  t: string;
  reason: Reason | null;
  rd: number | null;
  rt: string;
  snap: boolean;
};

export const MAP_CENTER: [number, number] = [44.9495, 34.103];

export function day(d: number): string {
  const x = new Date();
  x.setDate(x.getDate() - d);
  return `${String(x.getDate()).padStart(2, '0')}.${String(x.getMonth() + 1).padStart(2, '0')}.${x.getFullYear()}`;
}

export function baseSites(): Site[] {
  const rows: [number, string, string, number | null, number | null][] = [
    [1, 'Площадка Москольцо', 'ул. Москольцо, 15, Симферополь', 44.952, 34.102],
    [2, 'Площадка Центральный Рынок', 'ул. Кирова, 2, Симферополь', 44.949, 34.098],
    [3, 'Площадка Парк Гагарина', 'ул. Гагарина, 50, Симферополь', 44.94, 34.11],
    [4, 'Площадка Марьино', 'ул. Марьинская, 8, Симферополь', 44.958, 34.12],
    [5, 'Площадка ЦУМ', 'ул. Карла Маркса, 12, Симферополь', 44.951, 34.1],
    [6, 'Площадка Ак-Мечеть', 'ул. Ак-Мечетская, 3, Симферополь', 44.945, 34.085],
    [7, 'Площадка Каменка', 'ул. Каменская, 22, Симферополь', 44.935, 34.095],
    [8, 'Площадка Залесская', 'ул. Залесская, 7, Симферополь', 44.96, 34.115],
    [9, 'Площадка Пушкина', 'ул. Пушкина, 31, Симферополь', 44.9475, 34.1045],
    [10, 'Площадка Севастопольская', 'ул. Севастопольская, 44, Симферополь', 44.9425, 34.09],
    [11, 'Площадка Киевская', 'ул. Киевская, 77, Симферополь', 44.9565, 34.108],
    [12, 'Площадка Балаклавская', 'ул. Балаклавская, 68, Симферополь', null, null],
  ];
  return rows.map(([id, name, address, lat, lng]) => ({
    id,
    name,
    address,
    lat,
    lng,
    key: String(id),
    rtsp: `rtsp://admin:••••••@10.0.12.${10 + id}:554/Streaming/Channels/101`,
    active: id !== 7,
    checked: id === 7 ? `${day(1)}, 22:14` : `${day(0)}, 13:${40 + id}`,
  }));
}

export function baseAlerts(): Alert[] {
  const rows: [number, number, Level, AlertStatus, number, string, Reason?, number?, string?, boolean?][] = [
    [1, 4, 'contamination', 'new', 0, '13:52'],
    [2, 2, 'overflow', 'new', 0, '13:10'],
    [3, 8, 'overflow', 'new', 0, '11:47'],
    [4, 6, 'overflow', 'accepted', 0, '09:05'],
    [5, 10, 'contamination', 'accepted', 1, '18:22'],
    [6, 1, 'overflow', 'resolved', 1, '16:40', 'confirmed_and_cleared', 1, '17:55'],
    [7, 5, 'contamination', 'resolved', 2, '12:15', 'false_alarm', 2, '12:40'],
    [8, 3, 'overflow', 'resolved', 3, '08:30', 'resolved_externally', 3, '10:02'],
    [9, 2, 'overflow', 'resolved', 4, '19:11', 'confirmed_and_cleared', 4, '21:30'],
    [10, 9, 'contamination', 'resolved', 5, '07:48', 'confirmed_and_cleared', 5, '09:15'],
    [11, 7, 'overflow', 'resolved', 6, '14:20', 'resolved_externally', 6, '16:00'],
    [12, 11, 'overflow', 'resolved', 9, '10:05', 'false_alarm', 9, '10:30'],
    [13, 12, 'contamination', 'resolved', 12, '15:33', 'confirmed_and_cleared', 12, '18:10'],
    [14, 4, 'overflow', 'resolved', 17, '08:12', 'confirmed_and_cleared', 17, '11:40'],
    [15, 1, 'contamination', 'resolved', 23, '13:00', 'false_alarm', 23, '13:20', false],
    [16, 6, 'overflow', 'resolved', 28, '06:45', 'resolved_externally', 28, '09:00'],
    [17, 8, 'overflow', 'resolved', 40, '17:30', 'confirmed_and_cleared', 40, '19:05'],
    [18, 2, 'contamination', 'resolved', 45, '11:20', 'confirmed_and_cleared', 45, '14:45'],
  ];
  return rows.map(([id, siteId, level, status, d, t, reason, rd, rt, snap]) => ({
    id,
    siteId,
    level,
    status,
    d,
    t,
    reason: reason ?? null,
    rd: rd ?? null,
    rt: rt ?? '',
    snap: snap !== false,
  }));
}

/** Статус площадки = худшее открытое оповещение по ней. */
export function statusOf(alerts: Alert[], siteId: number): Status {
  let r: Status = 'clean';
  for (const a of alerts) {
    if (a.siteId !== siteId || a.status === 'resolved') continue;
    if (a.level === 'contamination') r = 'contamination';
    else if (r === 'clean') r = 'overflow';
  }
  return r;
}

export const sortAlerts = (a: Alert, b: Alert) => a.d - b.d || b.t.localeCompare(a.t);
export const whenOf = (a: Alert) => `${day(a.d)}, ${a.t}`;

export const WEEK = [4, 6, 3, 7, 5, 8, 6];
export const MONTH = [3, 5, 4, 6, 2, 4, 7, 5, 3, 6, 8, 5, 4, 3, 6, 7, 9, 6, 4, 5, 7, 6, 5, 4, 6, 3, 7, 5, 8, 6];
export const WEEK_LABELS = [6, 5, 4, 3, 2, 1, 0].map((d) => day(d).slice(0, 5));
export const MONTH_LABELS = Array.from({ length: 30 }, (_, i) => day(29 - i).slice(0, 5));

export const STATUS_LABEL: Record<Status | AlertStatus, string> = {
  clean: 'Чисто',
  overflow: 'Переполнение',
  contamination: 'Загрязнение',
  new: 'Новый',
  accepted: 'Принят',
  resolved: 'Решён',
};

export const REASONS: Record<Reason, { label: string; hint: string }> = {
  confirmed_and_cleared: { label: 'Подтверждено и устранено', hint: 'Проблема была, бригада выехала и убрала' },
  false_alarm: { label: 'Ложная тревога', hint: 'В реальности проблемы не было — модель ошиблась' },
  resolved_externally: { label: 'Разрешилось само', hint: 'Мусоровоз приехал / ветер сдул / устранено без нас' },
};

// ---- настоящие кадры ----
// Кадры с реальных камер, рамки — ответ прод-модели (backend/app/ml, ансамбль из
// трёх ONNX + ROI) на этих кадрах. Координаты — центр и размер в долях кадра.
import FRAMES from './frames.json';

export type Det = { c: string; p: number; x: number; y: number; w: number; h: number };
export type FrameInfo = { name: string; cam: string; dets: Det[] };

const FRAME_MAP = FRAMES as Record<string, { cam: string; dets: Det[] }>;

const POOL: Record<Status, string[]> = {
  clean: ['cam5_2026-05-04_154734.jpg'],
  overflow: ['cam2_2026-04-29_104734.jpg', 'cam3_2026-04-28_134734.jpg', 'cam2_2026-04-29_134734.jpg'],
  contamination: ['cam7_2026-05-02_134734.jpg', 'cam5_2026-05-06_134734.jpg', 'cam1_2026-05-03_144734.jpg', 'cam7_2026-05-03_134734.jpg'],
};

function frame(name: string): FrameInfo {
  const f = FRAME_MAP[name];
  return { name, cam: f.cam, dets: f.dets };
}

/** До трёх кадров для карусели площадки — из тех, что соответствуют её статусу. */
export function framesFor(st: Status, seed: number): FrameInfo[] {
  const pool = POOL[st];
  const out: FrameInfo[] = [];
  for (let i = 0; i < Math.min(3, pool.length); i++) out.push(frame(pool[(seed + i) % pool.length]));
  return out;
}

export function frameForAlert(level: Level, id: number): FrameInfo {
  const pool = POOL[level];
  return frame(pool[id % pool.length]);
}
