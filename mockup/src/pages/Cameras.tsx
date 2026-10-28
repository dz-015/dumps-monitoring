import { useState } from 'react';
import { Pencil, Plus, Search, Webcam } from 'lucide-react';
import { useApp } from '../ctx';
import { STATUS_LABEL } from '../data';
import { STATUS_ORDER, useStatusColors } from '../hooks';
import { Badge, Chips, Dropdown, Empty, ErrorBanner, PageHeader, Skeleton } from '../components/ui';

export default function Cameras() {
  const { sites, loading, failed, retry, go, setModal, isPhone } = useApp();
  const colors = useStatusColors();
  const [filter, setFilter] = useState('all');
  const [q, setQ] = useState('');
  const rows = sites
    .filter((s) => filter === 'all' || s.st === filter)
    .filter((s) => !q.trim() || `${s.name} ${s.address}`.toLowerCase().includes(q.trim().toLowerCase()));
  const statusOptions = STATUS_ORDER.map((k) => ({ value: k, label: STATUS_LABEL[k], color: colors[k] }));

  return (
    <div className="page">
      <PageHeader
        title="Камеры"
        subtitle={isPhone ? undefined : `${sites.length} площадок под наблюдением`}
        right={
          <button type="button" className={`btn btn-primary ${isPhone ? 'icon-only' : ''}`} onClick={() => setModal({ kind: 'add' })} aria-label="Добавить камеру">
            <Plus size={16} /> {!isPhone && 'Добавить'}
          </button>
        }
      />
      <div className="toolbar">
        <div className="input-wrap search">
          <Search size={15} className="input-icon" />
          <input type="search" className="input with-icon" placeholder="Поиск по названию или адресу" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Поиск" />
        </div>
        {!isPhone && <Dropdown value={filter} onChange={setFilter} ariaLabel="Фильтр по статусу" options={[{ value: 'all', label: 'Все статусы' }, ...statusOptions]} />}
      </div>
      {isPhone && <Chips items={[{ value: 'all', label: 'Все' }, ...statusOptions]} value={filter} onChange={setFilter} />}
      {failed && <ErrorBanner message="Не удалось загрузить список камер" onRetry={retry} />}
      {loading ? (
        <Skeleton />
      ) : isPhone ? (
        <div className="panel list stagger" key={`${filter}|${q}`}>
          {rows.map((s, k) => (
            <button key={s.id} type="button" style={{ '--i': k } as React.CSSProperties} className="list-row" onClick={() => go(`/cameras/${s.id}`)}>
              <span className="list-main">
                <b>{s.name}</b>
                <span className="muted small">{s.address}</span>
              </span>
              <span className="list-side">
                <Badge tone={s.st} />
                {!s.active && <Badge tone="contamination" label="Нет сигнала" />}
              </span>
            </button>
          ))}
          {rows.length === 0 && <Empty icon={<Webcam size={22} />} text="Нет камер" />}
        </div>
      ) : (
        <div className="panel table">
          <div className="t-head t-cams">
            <span>Площадка</span>
            <span>Статус</span>
            <span>Последняя проверка</span>
            <span />
          </div>
          <div className="stagger" key={`${filter}|${q}`}>
          {rows.map((s, k) => (
            <div key={s.id} className="t-row-wrap" style={{ '--i': k } as React.CSSProperties}>
              <button type="button" className="t-row t-cams" onClick={() => go(`/cameras/${s.id}`)}>
                <span className="cell-main">
                  <b>{s.name}</b>
                  <span className="muted small">{s.address}</span>
                </span>
                <span>
                  <Badge tone={s.st} />
                </span>
                <span className="t-time">
                  {s.checked}
                  {!s.active && <Badge tone="contamination" label="Нет сигнала" />}
                </span>
                <span />
              </button>
              <button type="button" className="icon-btn sm t-edit" aria-label={`Изменить ${s.name}`} title="Изменить" onClick={() => setModal({ kind: 'edit', siteId: s.id })}>
                <Pencil size={15} />
              </button>
            </div>
          ))}
          </div>
          {rows.length === 0 && <Empty icon={<Webcam size={22} />} text="Нет камер" />}
        </div>
      )}
    </div>
  );
}
