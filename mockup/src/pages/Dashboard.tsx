import { useState } from 'react';
import { ArrowUpRight, Bell, ChevronRight, CircleCheck, MapPin, Webcam } from 'lucide-react';
import { useApp } from '../ctx';
import { MONTH, MONTH_LABELS, sortAlerts, STATUS_LABEL, WEEK, WEEK_LABELS, whenOf } from '../data';
import { STATUS_ORDER, useStatusColors } from '../hooks';
import { AreaChart, CountUp, Donut } from '../components/charts';
import { Badge, Empty, LoadError, PageHeader, Skeleton } from '../components/ui';

export default function Dashboard() {
  const { sites, alerts, loading, failed, retry, go, siteAny, setOpenAlert, isPhone } = useApp();
  const colors = useStatusColors();
  const empty = sites.length === 0;
  const total = sites.length;
  const cnt = { clean: 0, overflow: 0, contamination: 0 };
  sites.forEach((s) => cnt[s.st]++);
  const cleanPct = total ? Math.round((cnt.clean / total) * 100) : 0;
  const open = alerts.filter((a) => a.status !== 'resolved').length;
  const fresh = alerts.filter((a) => a.status === 'new').length;
  const week = empty ? WEEK.map(() => 0) : WEEK;
  const month = empty ? MONTH.map(() => 0) : MONTH;
  const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
  const [range, setRange] = useState<'7' | '30'>('7');
  const series = range === '7' ? week : month;

  const stats = [
    { icon: MapPin, label: 'Площадок', value: String(total), sub: `${sites.filter((s) => s.hasCoords).length} на карте`, to: '/map' },
    { icon: Webcam, label: 'Активных камер', value: String(sites.filter((s) => s.active).length), sub: `из ${total}`, to: '/cameras' },
    { icon: CircleCheck, label: 'Чистых площадок', value: `${cleanPct}%`, sub: `${cnt.clean} из ${total}`, to: '/map' },
    { icon: Bell, label: 'Открытых оповещений', value: String(open), sub: fresh ? `${fresh} новых` : 'новых нет', to: '/alerts' },
  ];

  const latest = alerts
    .slice()
    .sort((a, b) => Number(a.status === 'resolved') - Number(b.status === 'resolved') || sortAlerts(a, b))
    .slice(0, 5);

  return (
    <div className="page">
      <PageHeader title="Панель управления" subtitle="Состояние контейнерных площадок" />
      {loading && <Skeleton />}
      {failed && <LoadError message="Не удалось загрузить данные панели" onRetry={retry} />}
      {!loading && !failed && (
        <>
          <div className="stats">
            {stats.map((s) => (
              <button key={s.label} type="button" className="panel stat" onClick={() => go(s.to)}>
                <span className="stat-top">
                  <s.icon size={18} strokeWidth={1.75} className="stat-icon" />
                  <span className="stat-label">{s.label}</span>
                  <ArrowUpRight size={16} className="stat-go" />
                </span>
                <span className="stat-value">
                  <CountUp value={s.value} />
                </span>
                <span className="stat-sub">{s.sub}</span>
              </button>
            ))}
          </div>

          <div className="grid-5-7">
            <section className="panel status-panel">
              <div className="panel-head">
                <h2>Статус площадок</h2>
              </div>
              <div className="donut-row">
                <Donut size={isPhone ? 120 : 148} segments={STATUS_ORDER.map((k) => ({ value: cnt[k], color: colors[k] }))} centerValue={String(total)} centerLabel="площадок" />
                <div className="donut-legend">
                  {STATUS_ORDER.map((k) => (
                    <div key={k}>
                      <i style={{ background: colors[k] }} />
                      <span>{STATUS_LABEL[k]}</span>
                      <b>{cnt[k]}</b>
                    </div>
                  ))}
                </div>
              </div>
            </section>
            <section className="panel latest">
              <div className="panel-head">
                <h2>Последние оповещения</h2>
                <button type="button" className="link-btn" onClick={() => go('/alerts')}>
                  Все <ChevronRight size={14} />
                </button>
              </div>
              <div className="latest-list stagger">
                {latest.map((a, k) => (
                  <button
                    key={a.id}
                    style={{ '--i': k } as React.CSSProperties}
                    type="button"
                    className="latest-row"
                    onClick={() => {
                      setOpenAlert(a.id);
                      go('/alerts');
                    }}
                  >
                    <b>{siteAny(a.siteId)?.name ?? `Площадка #${a.siteId}`}</b>
                    <span className="latest-time">{whenOf(a)}</span>
                    <Badge tone={a.level} />
                    <Badge tone={a.status} />
                  </button>
                ))}
              </div>
              {latest.length === 0 && <Empty text="Нет оповещений" />}
            </section>
          </div>

          <section className="panel">
            <div className="panel-head">
              <h2>Динамика проблем</h2>
              <div className="panel-tools">
                <span className="panel-meta">{sum(series)} всего</span>
                <div className="seg" role="group" aria-label="Период графика">
                  {(['7', '30'] as const).map((r) => (
                    <button key={r} type="button" aria-pressed={range === r} className={range === r ? 'on' : ''} onClick={() => setRange(r)}>
                      {r} дней
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <AreaChart key={range} values={series} labels={range === '7' ? WEEK_LABELS : MONTH_LABELS} height={isPhone ? 130 : 190} every={range === '7' ? 1 : isPhone ? 10 : 5} />
          </section>
        </>
      )}
    </div>
  );
}
