import { Fragment, useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from 'lucide-react';
import { getAlerts, getSites, getSnapshot, updateAlert } from '../lib/api';
import type { Alert, ResolutionReason, Site, Snapshot } from '../lib/types';
import StatusBadge from '../components/StatusBadge';
import BboxOverlay from '../components/BboxOverlay';
import Dropdown from '../components/Dropdown';
import SiteMiniMap from '../components/SiteMiniMap';
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

      <div className="flex gap-2 mb-4">
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
        <table className="w-full text-sm">
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
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
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
                      <td colSpan={5} className="px-6 py-4 text-sm text-gray-700">
                        {/* Место и снимок проблемы (Арсений 2026-07-27) */}
                        <div className="grid grid-cols-2 gap-4 mb-4">
                          <AlertLocation site={sitesById[a.site_id]} />
                          <AlertSnapshot
                            snapshotId={a.snapshot_id}
                            cached={a.snapshot_id ? snapshotCache[a.snapshot_id] : undefined}
                          />
                        </div>
                        <div className="flex items-start gap-8">
                          <div>
                            <div className="text-xs text-gray-500 mb-0.5">Создан</div>
                            <div>{new Date(a.created_at).toLocaleString('ru-RU')}</div>
                          </div>
                          {a.resolved_at && (
                            <div>
                              <div className="text-xs text-gray-500 mb-0.5">Решён</div>
                              <div>{new Date(a.resolved_at).toLocaleString('ru-RU')}</div>
                              {a.resolution_reason && (
                                <div className="text-xs text-gray-500 mt-1">
                                  {RESOLUTION_OPTIONS.find((o) => o.value === a.resolution_reason)
                                    ?.label ?? a.resolution_reason}
                                </div>
                              )}
                            </div>
                          )}
                          <div className="ml-auto flex flex-col gap-2 items-end">
                            {a.status === 'new' && (
                              <ActionButton onClick={() => handleAccept(a.id)}>
                                Принять
                              </ActionButton>
                            )}
                            {a.status === 'accepted' && resolvingId !== a.id && (
                              <ActionButton
                                onClick={() => setResolvingId(a.id)}
                                tone="green"
                              >
                                Отметить решённым
                              </ActionButton>
                            )}
                            {a.status === 'accepted' && resolvingId === a.id && (
                              <div className="flex flex-col gap-1.5 text-xs">
                                <div className="text-gray-500">Причина решения:</div>
                                {RESOLUTION_OPTIONS.map((o) => (
                                  <button
                                    key={o.value}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleResolve(a.id, o.value);
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
                                    setResolvingId(null);
                                  }}
                                  className="text-gray-500 hover:text-gray-700 self-start mt-1"
                                >
                                  Отмена
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
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
    <BboxOverlay
      imageUrl={`/uploads/${cached.image_path}`}
      detections={cached.detections || []}
      width={340}
      height={220}
    />
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
  const cls = tone === 'green' ? 'bg-green-500 hover:bg-green-600' : 'bg-sky-500 hover:bg-sky-600';
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`${cls} text-white text-xs font-medium px-3 py-1.5 rounded-lg`}
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
