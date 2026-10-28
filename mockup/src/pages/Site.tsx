import { useRef, useState } from 'react';
import { ArrowLeft, ChevronLeft, ChevronRight, CircleCheck, CircleMinus, CircleX, Download, Maximize2, Pencil } from 'lucide-react';
import { useApp } from '../ctx';
import { day, framesFor, MONTH, MONTH_LABELS, REASONS, sortAlerts, WEEK, WEEK_LABELS, whenOf, type Reason } from '../data';
import { useStatusColors, useWheelToOpen } from '../hooks';
import { AreaChart } from '../components/charts';
import { MiniMap } from '../components/maps';
import { Frame } from '../components/Frame';
import { Badge, LoadError, Skeleton } from '../components/ui';

const TIMES = ['13:50', '13:40', '13:30'];

export function ResolutionCell({ reason }: { reason: Reason | null }) {
  if (!reason) return <span className="muted">—</span>;
  const Icon = reason === 'confirmed_and_cleared' ? CircleCheck : reason === 'false_alarm' ? CircleX : CircleMinus;
  return (
    <span className={`res res-${reason}`}>
      <Icon size={15} /> {REASONS[reason].label}
    </span>
  );
}

export default function Site({ id }: { id: number }) {
  const { sites, alerts, loading, failed, retry, go, setModal, isPhone } = useApp();
  const colors = useStatusColors();
  const [idx, setIdx] = useState(0);
  const [boxes, setBoxes] = useState(true);
  const wheelOpen = useRef<(at: [number, number]) => void>(() => {});
  const frameRef = useWheelToOpen((at) => wheelOpen.current(at));
  const site = sites.find((s) => s.id === id);

  const back = (
    <button type="button" className="link-btn back" onClick={() => go('/cameras')}>
      <ArrowLeft size={15} /> Камеры
    </button>
  );
  if (loading || failed || !site)
    return (
      <div className="page">
        {back}
        {loading && <Skeleton />}
        {failed && <LoadError message="Не удалось загрузить площадку" onRetry={retry} />}
        {!loading && !failed && <div className="panel empty">Площадка не найдена</div>}
      </div>
    );

  const frames = framesFor(site.st, site.id);
  const i = Math.min(idx, frames.length - 1);
  const frame = frames[i];
  const scale = (((site.id * 7) % 5) + 1) / 8;
  const sw = WEEK.map((v) => Math.round(v * scale));
  const sm = MONTH.map((v) => Math.round(v * scale));
  const siteAlerts = alerts.filter((a) => a.siteId === site.id).sort(sortAlerts);
  const caption = `${day(0)}, ${TIMES[i]}`;
  const openLb = (zoomAt?: [number, number]) => setModal({ kind: 'lightbox', info: { frame, caption: `${site.name} · ${caption}`, zoomAt } });

  wheelOpen.current = openLb;

  return (
    <div className="page">
      {back}
      <div className="page-header">
        <div>
          <div className="title-row">
            <h1>{site.name}</h1>
            <Badge tone={site.st} />
          </div>
          <p>{site.address}</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => setModal({ kind: 'edit', siteId: site.id })}>
          <Pencil size={15} /> {!isPhone && 'Изменить'}
        </button>
      </div>

      <div className="grid-2-1">
        <section className="panel">
          <div className="panel-head">
            <h2>Последний снимок</h2>
            <div className="row-gap">
              <label className="switch">
                <input type="checkbox" checked={boxes} onChange={(e) => setBoxes(e.target.checked)} />
                <span className="switch-track" />
                Рамки
              </label>
              <button type="button" className="icon-btn sm" aria-label="Скачать кадр" title="Скачать">
                <Download size={16} />
              </button>
              <button type="button" className="icon-btn sm" onClick={() => openLb()} aria-label="Открыть на весь экран" title="На весь экран">
                <Maximize2 size={16} />
              </button>
            </div>
          </div>
          <div className="frame-wrap" ref={frameRef}>
            <button type="button" className="frame-btn" onClick={() => openLb()} aria-label="Открыть кадр на весь экран">
              <Frame key={frame.name} frame={frame} boxes={boxes} />
            </button>
            {frames.length > 1 && (
              <>
                <button type="button" className="frame-nav l" disabled={i <= 0} onClick={() => setIdx(i - 1)} aria-label="Более новый снимок">
                  <ChevronLeft size={18} />
                </button>
                <button type="button" className="frame-nav r" disabled={i >= frames.length - 1} onClick={() => setIdx(i + 1)} aria-label="Более старый снимок">
                  <ChevronRight size={18} />
                </button>
              </>
            )}
          </div>
          <div className="frame-foot">
            <span className="muted">{caption}</span>
            {frames.length > 1 && (
              <div className="thumbs">
                {frames.map((f, k) => (
                  <button key={f.name} type="button" className={`thumb ${k === i ? 'on' : ''}`} onClick={() => setIdx(k)} aria-label={`Снимок ${TIMES[k]}`}>
                    <img src={`/frames/${f.name}`} alt="" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        <div className="stack">
          <section className="panel">
            <div className="panel-head">
              <h2>Расположение</h2>
            </div>
            {site.hasCoords ? (
              <>
                <MiniMap lat={site.lat!} lng={site.lng!} color={colors[site.st]} height={170} />
                <div className="mono small muted" style={{ marginTop: 10 }}>
                  {site.lat!.toFixed(5)}, {site.lng!.toFixed(5)}
                </div>
              </>
            ) : (
              <div className="placeholder" style={{ height: 170 }}>
                Координаты не заданы — добавьте их через «Изменить»
              </div>
            )}
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>Камера</h2>
            </div>
            <dl className="kv">
              <dt>Связь</dt>
              <dd>
                <Badge tone={site.active ? 'resolved' : 'contamination'} label={site.active ? 'На связи' : 'Нет сигнала'} />
              </dd>
              <dt>Последняя проверка</dt>
              <dd>{site.checked}</dd>
            </dl>
            <div className="field-label" style={{ marginTop: 12 }}>
              RTSP-ссылка
            </div>
            <code className="code-box">{site.rtsp}</code>
          </section>
        </div>
      </div>

      <div className="grid-2">
        <section className="panel">
          <div className="panel-head">
            <h2>Проблемы за 7 дней</h2>
            <span className="panel-meta">{sw.reduce((a, b) => a + b, 0)} всего</span>
          </div>
          <AreaChart values={sw} labels={WEEK_LABELS} height={130} />
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Проблемы за 30 дней</h2>
            <span className="panel-meta">{sm.reduce((a, b) => a + b, 0)} всего</span>
          </div>
          <AreaChart values={sm} labels={MONTH_LABELS} height={130} every={isPhone ? 10 : 6} />
        </section>
      </div>

      <section className="panel table">
        <div className="panel-head pad">
          <h2>История оповещений</h2>
        </div>
        {isPhone ? (
          siteAlerts.map((a) => (
            <div key={a.id} className="list-row static">
              <span className="list-main">
                <b>{whenOf(a)}</b>
                <ResolutionCell reason={a.reason} />
              </span>
              <span className="list-side">
                <Badge tone={a.level} />
                <Badge tone={a.status} />
              </span>
            </div>
          ))
        ) : (
          <>
            <div className="t-head t-hist">
              <span>Время</span>
              <span>Уровень</span>
              <span>Статус</span>
              <span>Итог</span>
            </div>
            {siteAlerts.map((a) => (
              <div key={a.id} className="t-row t-hist static">
                <span className="t-time">{whenOf(a)}</span>
                <span>
                  <Badge tone={a.level} />
                </span>
                <span>
                  <Badge tone={a.status} />
                </span>
                <ResolutionCell reason={a.reason} />
              </div>
            ))}
          </>
        )}
        {siteAlerts.length === 0 && <div className="empty small">Оповещений по этой площадке не было</div>}
      </section>
    </div>
  );
}
