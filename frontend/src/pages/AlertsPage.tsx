import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Video } from 'lucide-react';
import { getAlerts, getSites, getSnapshot, updateAlert } from '../lib/api';
import type { Alert, ResolutionReason, Site, Snapshot } from '../lib/types';
import StatusBadge from '../components/StatusBadge';
import BboxOverlay from '../components/BboxOverlay';
import Dropdown from '../components/Dropdown';
import SiteMiniMap from '../components/SiteMiniMap';
import SnapshotLightbox from '../components/SnapshotLightbox';
import { ErrorBanner } from '../components/LoadError';
import { useRequestGuard } from '../lib/useRequestGuard';

const RESOLUTION_OPTIONS: { value: ResolutionReason; label: string; hint: string }[] = [
  {
    value: 'confirmed_and_cleared',
    label: 'Подтверждено и устранено',
    hint: 'Проблема была, бригада выехала и убрала',
  },
  {
    value: 'false_alarm',
    label: 'Ложная тревога',
    hint: 'В реальности проблемы не было — модель ошиблась',
  },
  {
    value: 'resolved_externally',
    label: 'Разрешилось само',
    hint: 'Мусоровоз приехал / ветер сдул / устранено без нас',
  },
];

const PER_PAGE = 10;

const PERIOD_OPTIONS = [
  { value: '', label: 'Всё время' },
  { value: '1', label: 'За сегодня' },
  { value: '7', label: 'За 7 дней' },
  { value: '30', label: 'За 30 дней' },
];

function periodToSince(days: string): string | undefined {
  if (!days) return undefined;
  if (days === '1') {
    // "За сегодня" is a calendar-day claim: since local midnight, not a
    // rolling 24-hour window (BUG-38).
    const midnight = new Date();
    midnight.setHours(0, 0, 0, 0);
    return midnight.toISOString().replace(/\.\d{3}Z$/, 'Z');
  }
  const n = Number(days);
  const since = new Date(Date.now() - n * 24 * 60 * 60 * 1000);
  // Z-suffix avoids the "+00:00" → space pitfall in URL query parsing.
  return since.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [levelFilter, setLevelFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [periodFilter, setPeriodFilter] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [error, setError] = useState('');
  // Site coords for the mini-map in the expanded row; keyed by site_id.
  const [sitesById, setSitesById] = useState<Record<number, Site>>({});
  // Snapshot cache for expanded alerts, keyed by snapshot_id.
  const [snapshotCache, setSnapshotCache] = useState<
    Record<number, Snapshot | 'loading' | 'error'>
  >({});
  const begin = useRequestGuard();

  useEffect(() => {
    // Non-fatal: without sites the expanded row just skips the mini-map.
    getSites()
      .then((sites) => {
        setSitesById(Object.fromEntries(sites.map((s) => [s.id, s])));
      })
      .catch(() => {});
  }, []);

  const handleToggleExpand = (a: Alert) => {
    const opening = expanded !== a.id;
    setExpanded(opening ? a.id : null);
    if (opening && a.snapshot_id && !snapshotCache[a.snapshot_id]) {
      const snapId = a.snapshot_id;
      setSnapshotCache((c) => ({ ...c, [snapId]: 'loading' }));
      getSnapshot(snapId)
        .then((snap) => setSnapshotCache((c) => ({ ...c, [snapId]: snap })))
        .catch(() => setSnapshotCache((c) => ({ ...c, [snapId]: 'error' })));
    }
  };

  const load = useCallback(() => {
    const fresh = begin();
    getAlerts({
      level: levelFilter || undefined,
      status: statusFilter || undefined,
      since: periodToSince(periodFilter),
      page,
      per_page: PER_PAGE,
    })
      .then((res) => {
        if (!fresh()) return; // stale response for older filters/page (BUG-21)
        // A mutation can shrink the filtered set below the current page —
        // clamp instead of showing a false empty state (BUG-36/37).
        const lastPage = Math.max(1, Math.ceil(res.total / PER_PAGE));
        if (page > lastPage) {
          setPage(lastPage);
          return; // page change re-triggers load
        }
        setError('');
        setAlerts(res.items);
        setTotal(res.total);
      })
      .catch(() => {
        if (fresh()) setError('Не удалось загрузить оповещения');
      });
  }, [page, levelFilter, statusFilter, periodFilter, begin]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  const handleAccept = async (id: number) => {
    try {
      await updateAlert(id, { status: 'accepted' });
    } catch {
      setError('Не удалось принять оповещение');
      return;
    }
    load();
  };

  const handleResolve = async (id: number, reason: ResolutionReason) => {
    try {
      await updateAlert(id, { status: 'resolved', resolution_reason: reason });
    } catch {
      setError('Не удалось отметить оповещение решённым');
      return;
    } finally {
      setResolvingId(null);
    }
    load();
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Оповещения</h1>
      <p className="text-sm text-gray-500 mb-4">
        Управление оповещениями о загрязнениях и переполнениях
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        <Dropdown
          value={levelFilter}
          onChange={(v) => {
            setLevelFilter(v);
            setPage(1);
          }}
          options={[
            { value: '', label: 'Все уровни' },
            { value: 'overflow', label: 'Переполнение', tone: 'yellow' },
            { value: 'contamination', label: 'Загрязнение', tone: 'red' },
          ]}
          ariaLabel="Фильтр по уровню"
        />
        <Dropdown
          value={statusFilter}
          onChange={(v) => {
            setStatusFilter(v);
            setPage(1);
          }}
          options={[
            { value: '', label: 'Все статусы' },
            { value: 'new', label: 'Новый', tone: 'blue' },
            { value: 'accepted', label: 'Принят', tone: 'yellow' },
            { value: 'resolved', label: 'Решён', tone: 'green' },
          ]}
          ariaLabel="Фильтр по статусу"
        />
        <Dropdown
          value={periodFilter}
          onChange={(v) => {
            setPeriodFilter(v);
            setPage(1);
          }}
          options={PERIOD_OPTIONS}
          ariaLabel="Фильтр по периоду"
        />
      </div>

      {error && <ErrorBanner message={error} onRetry={load} />}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Таблица — десктоп; на телефоне те же алерты карточками ниже */}
        <table className="w-full text-sm hidden md:table">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500 text-xs uppercase tracking-wide">
              <th className="px-4 py-3 font-medium">Время</th>
              <th className="px-4 py-3 font-medium">Площадка</th>
              <th className="px-4 py-3 font-medium">Уровень</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium w-10"></th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => {
              const open = expanded === a.id;
              return (
                <Fragment key={a.id}>
                  <tr
                    className={`cursor-pointer ${
                      // В раскрытом виде шапка — часть серого блока деталей.
                      open ? 'bg-gray-50/60' : 'border-b border-gray-50 hover:bg-gray-50'
                    }`}
                    onClick={() => handleToggleExpand(a)}
                  >
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {formatDate(a.created_at)}
                    </td>
                    <td className="px-4 py-3 text-gray-900">
                      {a.site_name || `Площадка #${a.site_id}`}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge value={a.level} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge value={a.status} />
                    </td>
                    <td className="px-4 py-3 text-right text-gray-400">
                      {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </td>
                  </tr>
                  {open && (
                    <tr className="bg-gray-50/60 border-b border-gray-100">
                      <td colSpan={5} className="p-0">
                        <Expand>
                          <div className="px-6 pb-4 pt-1 text-sm text-gray-700">
                            <AlertDetails
                              alert={a}
                              site={sitesById[a.site_id]}
                              cached={a.snapshot_id ? snapshotCache[a.snapshot_id] : undefined}
                              resolving={resolvingId === a.id}
                              onAccept={() => handleAccept(a.id)}
                              onStartResolve={() => setResolvingId(a.id)}
                              onCancelResolve={() => setResolvingId(null)}
                              onResolve={(reason) => handleResolve(a.id, reason)}
                            />
                          </div>
                        </Expand>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {alerts.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-gray-400 text-sm">
                  Нет оповещений
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Карточки — телефон */}
        <div className="md:hidden">
          {alerts.map((a) => {
            const open = expanded === a.id;
            return (
              <div key={a.id} className="border-b border-gray-50 last:border-0">
                <button
                  type="button"
                  onClick={() => handleToggleExpand(a)}
                  className={`w-full text-left px-4 py-3 flex items-center gap-3 ${
                    open ? 'bg-gray-50/60' : ''
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {a.site_name || `Площадка #${a.site_id}`}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {formatDate(a.created_at)}
                    </div>
                    <div className="flex gap-1.5 mt-1.5">
                      <StatusBadge value={a.level} />
                      <StatusBadge value={a.status} />
                    </div>
                  </div>
                  <span className="text-gray-400">
                    {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </span>
                </button>
                {open && (
                  <Expand>
                    <div className="bg-gray-50/60 px-4 pb-4 text-sm text-gray-700">
                      <AlertDetails
                        alert={a}
                        site={sitesById[a.site_id]}
                        cached={a.snapshot_id ? snapshotCache[a.snapshot_id] : undefined}
                        resolving={resolvingId === a.id}
                        onAccept={() => handleAccept(a.id)}
                        onStartResolve={() => setResolvingId(a.id)}
                        onCancelResolve={() => setResolvingId(null)}
                        onResolve={(reason) => handleResolve(a.id, reason)}
                      />
                    </div>
                  </Expand>
                )}
              </div>
            );
          })}
          {alerts.length === 0 && (
            <div className="px-4 py-10 text-center text-gray-400 text-sm">Нет оповещений</div>
          )}
        </div>

        <div className="flex items-center justify-end gap-1 px-4 py-3 border-t border-gray-100 text-sm">
          <PagerButton disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <ChevronLeft size={14} />
          </PagerButton>
          {pagerNumbers(page, totalPages).map((n, i) =>
            n === '…' ? (
              <span key={i} className="px-2 text-gray-400">
                …
              </span>
            ) : (
              <PagerButton key={i} active={n === page} onClick={() => setPage(n as number)}>
                {n}
              </PagerButton>
            )
          )}
          <PagerButton disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            <ChevronRight size={14} />
          </PagerButton>
        </div>
      </div>
    </div>
  );
}

/** Плавное выпадение раскрытого оповещения: grid-rows 0fr → 1fr, поэтому
 *  работает с содержимым любой высоты без magic-чисел max-height. */
function Expand({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    // Два rAF: первый кадр монтируется схлопнутым, затем стартует переход.
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setOpen(true)));
    return () => cancelAnimationFrame(id);
  }, []);
  return (
    <div
      className="grid transition-[grid-template-rows] duration-300 ease-out"
      style={{ gridTemplateRows: open ? '1fr' : '0fr' }}
    >
      <div className="overflow-hidden min-h-0">{children}</div>
    </div>
  );
}

/** Раскрытое содержимое алерта — общее для строки таблицы и мобильной карточки. */
function AlertDetails({
  alert: a,
  site,
  cached,
  resolving,
  onAccept,
  onStartResolve,
  onCancelResolve,
  onResolve,
}: {
  alert: Alert;
  site?: Site;
  cached?: Snapshot | 'loading' | 'error';
  resolving: boolean;
  onAccept: () => void;
  onStartResolve: () => void;
  onCancelResolve: () => void;
  onResolve: (reason: ResolutionReason) => void;
}) {
  return (
    // Одна сетка на всё: ряд действий занимает колонку кадра, поэтому кнопки
    // выровнены по его краям (Арсений 2026-08-03). «Создан» не показываем —
    // время уже есть в шапке оповещения.
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <AlertLocation site={site} />
      <AlertSnapshot snapshotId={a.snapshot_id} cached={cached} />
      {a.resolved_at && (
        <div>
          <div className="text-xs text-gray-500 mb-0.5">Решён</div>
          <div>{new Date(a.resolved_at).toLocaleString('ru-RU')}</div>
          {a.resolution_reason && (
            <div className="text-xs text-gray-500 mt-1">
              {RESOLUTION_OPTIONS.find((o) => o.value === a.resolution_reason)?.label ??
                a.resolution_reason}
            </div>
          )}
        </div>
      )}
      {/* Кнопки по центру колонки кадра («попробуем и так» — Арсений 2026-08-03) */}
      <div className="sm:col-start-2 flex flex-wrap items-start justify-center gap-3">
        <Link
          to={`/cameras/${a.site_id}`}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1.5 bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-medium px-4 py-2 rounded-lg shadow-sm"
        >
          <Video size={15} className="text-sky-500" />
          Перейти к камере
        </Link>
        <div className="flex flex-col items-end gap-2">
          {a.status === 'new' && <ActionButton onClick={onAccept}>Принять</ActionButton>}
          {a.status === 'accepted' && !resolving && (
            <ActionButton onClick={onStartResolve} tone="green">
              Отметить решённым
            </ActionButton>
          )}
          {a.status === 'accepted' && resolving && (
            <div className="flex flex-col gap-1.5 text-xs">
              <div className="text-gray-500">Причина решения:</div>
              {RESOLUTION_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  onClick={(e) => {
                    e.stopPropagation();
                    onResolve(o.value);
                  }}
                  className="text-left bg-white border border-gray-200 rounded-lg px-3 py-2 hover:bg-gray-50"
                >
                  <div className="font-medium text-gray-900">{o.label}</div>
                  <div className="text-gray-500">{o.hint}</div>
                </button>
              ))}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCancelResolve();
                }}
                className="text-gray-500 hover:text-gray-700 self-start mt-1"
              >
                Отмена
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AlertLocation({ site }: { site?: Site }) {
  if (!site || site.latitude === null || site.longitude === null) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white flex items-center justify-center text-gray-400 text-xs h-[220px]">
        Координаты площадки не заданы
      </div>
    );
  }
  return (
    <SiteMiniMap
      latitude={site.latitude}
      longitude={site.longitude}
      status={site.active_status ?? site.status}
      height={220}
      interactive
    />
  );
}

function AlertSnapshot({
  snapshotId,
  cached,
}: {
  snapshotId: number | null;
  cached?: Snapshot | 'loading' | 'error';
}) {
  const [zoomed, setZoomed] = useState(false);
  // Колесо ВВЕРХ над кадром открывает лайтбокс (экономим клик по лупе);
  // нативный non-passive слушатель, чтобы страница при этом не прокрутилась.
  // Колесо вниз не перехватываем — это обычная прокрутка списка.
  const wheelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = wheelRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY >= 0) return;
      e.preventDefault();
      setZoomed(true);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
    // Элемент появляется только после загрузки снимка.
  }, [cached]);
  const placeholder = (text: string) => (
    <div className="rounded-lg border border-gray-200 bg-white flex items-center justify-center text-gray-400 text-xs h-[220px] text-center px-4">
      {text}
    </div>
  );
  if (!snapshotId) {
    // Seeded alerts (and alerts until real inference lands) carry no snapshot.
    return placeholder('Снимок не сохранён для этого оповещения');
  }
  if (!cached || cached === 'loading') return placeholder('Загрузка снимка…');
  if (cached === 'error') return placeholder('Не удалось загрузить снимок');
  return (
    <>
      {/* h-[220px] + fill: снимок занимает ровно ту же ячейку, что и карта
          рядом, — блоки выровнены по ширине и высоте (Арсений 2026-08-03). */}
      <div
        ref={wheelRef}
        className="cursor-zoom-in h-[220px]"
        onClick={() => setZoomed(true)}
        title="Открыть на весь экран"
      >
        <BboxOverlay
          fill
          imageUrl={`/uploads/${cached.image_path}`}
          detections={cached.detections || []}
        />
      </div>
      {zoomed && (
        <SnapshotLightbox
          imageUrl={`/uploads/${cached.image_path}`}
          detections={cached.detections || []}
          caption={new Date(cached.taken_at).toLocaleString('ru-RU')}
          onClose={() => setZoomed(false)}
        />
      )}
    </>
  );
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function pagerNumbers(current: number, total: number): (number | '…')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out: (number | '…')[] = [1];
  if (current > 3) out.push('…');
  for (let n = Math.max(2, current - 1); n <= Math.min(total - 1, current + 1); n++) out.push(n);
  if (current < total - 2) out.push('…');
  out.push(total);
  return out;
}

function ActionButton({
  children,
  onClick,
  tone = 'blue',
}: {
  children: React.ReactNode;
  onClick: () => void;
  tone?: 'blue' | 'green';
}) {
  // Тон темнее бейджа «Новый» + размер и тень, чтобы кнопка не терялась на
  // карточке (Арсений 2026-08-03: «голубая, но темнее и крупнее»).
  const cls =
    tone === 'green' ? 'bg-green-600 hover:bg-green-700' : 'bg-sky-600 hover:bg-sky-700';
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`${cls} text-white text-sm font-medium px-4 py-2 rounded-lg shadow-sm`}
    >
      {children}
    </button>
  );
}

function PagerButton({
  children,
  onClick,
  disabled,
  active,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`min-w-[28px] h-7 px-1.5 rounded text-sm ${
        active
          ? 'bg-gray-900 text-white'
          : 'text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-transparent'
      }`}
    >
      {children}
    </button>
  );
}
