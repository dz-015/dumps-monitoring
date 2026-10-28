import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Bell, ChevronLeft, ChevronRight, Maximize2, X } from 'lucide-react';
import { useApp } from '../ctx';
import { day, frameForAlert, REASONS, sortAlerts, whenOf, type Alert, type AlertStatus, type Reason } from '../data';
import { usePresence, useStatusColors, useWheelToOpen } from '../hooks';
import { MiniMap } from '../components/maps';
import { Frame } from '../components/Frame';
import { Badge, Dropdown, Empty, ErrorBanner, PageHeader, Skeleton } from '../components/ui';
import { ResolutionCell } from './Site';

const PER_PAGE = 10;

/** Окно с подробностями оповещения: по центру на десктопе, снизу на телефоне.
 *  Держит последнее оповещение, пока проигрывается уход. */
function AlertDrawer({ alert, onClose }: { alert: Alert | null; onClose: () => void }) {
  const { siteAny, acceptAlert, resolveAlert, go, setModal, isPhone } = useApp();
  const colors = useStatusColors();
  const { mounted, shown } = usePresence(!!alert, 260);
  const last = useRef<Alert | null>(alert);
  if (alert) last.current = alert;
  const a = alert ?? last.current;
  const [resolving, setResolving] = useState(false);
  const wheelOpen = useRef<(at: [number, number]) => void>(() => {});
  const frameRef = useWheelToOpen((at) => wheelOpen.current(at));
  useEffect(() => setResolving(false), [alert?.id]);
  useEffect(() => {
    if (!alert) return;
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [alert, onClose]);

  if (!mounted || !a) return null;
  const site = siteAny(a.siteId);
  const frame = frameForAlert(a.level, a.id);
  const hasCoords = site?.lat != null && site?.lng != null;
  const openLb = (zoomAt?: [number, number]) => setModal({ kind: 'lightbox', info: { frame, caption: `${site?.name ?? ''} · ${whenOf(a)}`, zoomAt } });
  wheelOpen.current = openLb;

  return (
    <div className={`drawer-layer ${isPhone ? 'sheet' : 'center'} ${shown ? 'shown' : ''}`}>
      <button type="button" className="drawer-bg" aria-label="Закрыть" onClick={onClose} />
      <section className="drawer" role="dialog" aria-modal="true" aria-label={`Оповещение: ${site?.name ?? ''}`} data-lenis-prevent>
        {isPhone && <div className="sheet-grip" />}
        <div className="drawer-head">
          <div className="drawer-title">
            <h2>{site?.name ?? `Площадка #${a.siteId}`}</h2>
            <div className="row-gap">
              <span className="muted">{whenOf(a)}</span>
              <span className="sep-dot" />
              <Badge tone={a.level} />
              <span className="sep-dot" />
              <Badge tone={a.status} />
            </div>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>
        <div className="drawer-body alert-view" key={a.id}>
          {a.snap ? (
            <div className="frame-wrap" ref={frameRef}>
              <button type="button" className="frame-btn" onClick={() => openLb()} aria-label="Открыть кадр на весь экран">
                <Frame frame={frame} labels={isPhone ? 'none' : 'problems'} />
              </button>
              <button type="button" className="frame-expand" onClick={() => openLb()} aria-label="Открыть кадр на весь экран">
                <Maximize2 size={15} />
              </button>
            </div>
          ) : (
            <div className="placeholder ratio">Снимок не сохранён для этого оповещения</div>
          )}

          <div className="alert-info">
            <dl className="kv">
              <dt>Адрес</dt>
              <dd>{site?.address ?? '—'}</dd>
              {a.status === 'resolved' && (
                <>
                  <dt>Решён</dt>
                  <dd>{a.rd != null ? `${day(a.rd)}, ${a.rt}` : '—'}</dd>
                  <dt>Причина</dt>
                  <dd>
                    <ResolutionCell reason={a.reason} />
                  </dd>
                </>
              )}
            </dl>
            {!isPhone && (hasCoords ? <MiniMap lat={site!.lat!} lng={site!.lng!} color={colors[a.level]} height="100%" /> : <div className="placeholder grow">Координаты площадки не заданы</div>)}
          </div>
        </div>

        <div className="drawer-foot">
          {resolving ? (
            <div className="reasons">
              <span className="field-label">Чем закончилось?</span>
              {(Object.keys(REASONS) as Reason[]).map((k) => (
                <button key={k} type="button" className="reason" onClick={() => resolveAlert(a.id, k)}>
                  <b>{REASONS[k].label}</b>
                  <span className="muted">{REASONS[k].hint}</span>
                </button>
              ))}
              <button type="button" className="btn btn-ghost" onClick={() => setResolving(false)}>
                Отмена
              </button>
            </div>
          ) : (
            <div className="actions">
              {a.status === 'new' && (
                <button type="button" className="btn btn-primary" onClick={() => acceptAlert(a.id)}>
                  Принять
                </button>
              )}
              {a.status !== 'resolved' && (
                <button type="button" className="btn btn-secondary" onClick={() => setResolving(true)}>
                  Отметить решённым
                </button>
              )}
              <button type="button" className="btn btn-ghost" onClick={() => go(`/cameras/${a.siteId}`)}>
                Перейти к камере
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default function Alerts() {
  const { alerts, loading, failed, retry, siteAny, openAlert, setOpenAlert, isPhone } = useApp();
  const colors = useStatusColors();
  const [status, setStatus] = useState<'' | AlertStatus>('');
  const [level, setLevel] = useState('');
  const [period, setPeriod] = useState('');
  const [page, setPage] = useState(1);

  const inPeriod = (a: Alert) => !period || (period === '1' ? a.d === 0 : a.d < Number(period));
  const base = alerts.filter((a) => (!level || a.level === level) && inPeriod(a));
  const filtered = base.filter((a) => !status || a.status === status).sort(sortAlerts);
  const pages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const pg = Math.min(page, pages);
  const rows = isPhone ? filtered : filtered.slice((pg - 1) * PER_PAGE, pg * PER_PAGE);

  const tabs: { v: '' | AlertStatus; label: string }[] = [
    { v: '', label: 'Все' },
    { v: 'new', label: 'Новые' },
    { v: 'accepted', label: 'Принятые' },
    { v: 'resolved', label: 'Решённые' },
  ];
  const listKey = `${status}|${level}|${period}|${pg}`;
  const siteName = (a: Alert) => siteAny(a.siteId)?.name ?? `Площадка #${a.siteId}`;

  return (
    <div className="page">
      <PageHeader title="Оповещения" subtitle={isPhone ? undefined : 'Переполнения и мусор, найденные на кадрах'} />
      <div className="toolbar">
        <div className="tabs" role="group" aria-label="Фильтр по статусу">
          {tabs.map((t) => (
            <button
              key={t.v}
              type="button"
              aria-pressed={status === t.v}
              className={status === t.v ? 'on' : ''}
              onClick={() => {
                setStatus(t.v);
                setPage(1);
              }}
            >
              {t.label}
              <span className="tab-count">{t.v ? base.filter((a) => a.status === t.v).length : base.length}</span>
            </button>
          ))}
        </div>
        <div className="toolbar-right">
          <Dropdown
            value={level}
            onChange={(v) => {
              setLevel(v);
              setPage(1);
            }}
            ariaLabel="Фильтр по уровню"
            align="right"
            options={[
              { value: '', label: 'Все уровни' },
              { value: 'overflow', label: 'Переполнение', color: colors.overflow },
              { value: 'contamination', label: 'Загрязнение', color: colors.contamination },
            ]}
          />
          <Dropdown
            value={period}
            onChange={(v) => {
              setPeriod(v);
              setPage(1);
            }}
            ariaLabel="Фильтр по периоду"
            align="right"
            options={[
              { value: '', label: 'Всё время' },
              { value: '1', label: 'Сегодня' },
              { value: '7', label: '7 дней' },
              { value: '30', label: '30 дней' },
            ]}
          />
        </div>
      </div>
      {failed && <ErrorBanner message="Не удалось загрузить оповещения" onRetry={retry} />}
      {loading ? (
        <Skeleton />
      ) : isPhone ? (
        <div className="panel list stagger" key={listKey}>
          {rows.map((a, k) => (
            <button key={a.id} type="button" style={{ '--i': k } as CSSProperties} className={`list-row ${openAlert === a.id ? 'on' : ''}`} onClick={() => setOpenAlert(a.id)}>
              <span className="list-main">
                <b>{siteName(a)}</b>
                <span className="muted small">{whenOf(a)}</span>
              </span>
              <span className="list-side">
                <Badge tone={a.level} />
                <Badge tone={a.status} />
              </span>
            </button>
          ))}
          {rows.length === 0 && <Empty icon={<Bell size={22} />} text="Нет оповещений" />}
        </div>
      ) : (
        <div className="panel table">
          <div className="t-head t-alerts">
            <span>Время</span>
            <span>Площадка</span>
            <span>Уровень</span>
            <span>Статус</span>
          </div>
          <div className="stagger" key={listKey}>
          {rows.map((a, k) => (
            <button key={a.id} type="button" style={{ '--i': k } as CSSProperties} className={`t-row t-alerts ${openAlert === a.id ? 'on' : ''}`} onClick={() => setOpenAlert(a.id)}>
              <span className="t-time">{whenOf(a)}</span>
              <b>{siteName(a)}</b>
              <span>
                <Badge tone={a.level} />
              </span>
              <span>
                <Badge tone={a.status} />
              </span>
            </button>
          ))}
          </div>
          {rows.length === 0 && <Empty icon={<Bell size={22} />} text="Нет оповещений" />}
          <div className="t-foot">
            <span>{filtered.length ? `${(pg - 1) * PER_PAGE + 1}–${Math.min(pg * PER_PAGE, filtered.length)} из ${filtered.length}` : 'Ничего не найдено'}</span>
            <div className="pager">
              <button type="button" className="icon-btn sm" disabled={pg <= 1} onClick={() => setPage(pg - 1)} aria-label="Предыдущая страница">
                <ChevronLeft size={16} />
              </button>
              <span className="muted">
                {pg} / {pages}
              </span>
              <button type="button" className="icon-btn sm" disabled={pg >= pages} onClick={() => setPage(pg + 1)} aria-label="Следующая страница">
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Панель рисуется на уровне всего приложения, а не внутри страницы:
 *  так её не обрезают и не сдвигают прокрутка и анимации страницы. */
export function AlertDrawerHost() {
  const { alerts, openAlert, setOpenAlert, route } = useApp();
  const current = route.page === 'alerts' ? (alerts.find((a) => a.id === openAlert) ?? null) : null;
  return <AlertDrawer alert={current} onClose={() => setOpenAlert(null)} />;
}
