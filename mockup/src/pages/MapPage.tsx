import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { ArrowRight, Search } from 'lucide-react';
import L from 'leaflet';
import { MapContainer, Marker, Popup } from 'react-leaflet';
import { useApp, type SiteView } from '../ctx';
import { MAP_CENTER, STATUS_LABEL, type Status } from '../data';
import { STATUS_ORDER, useSmoothWheel, useStatusColors } from '../hooks';
import { AutoResize, FlyTo, pinIcon, Tiles } from '../components/maps';
import { Badge, Chips, ErrorBanner, PageHeader, Skeleton } from '../components/ui';

export default function MapPage() {
  const { sites, loading, failed, retry, go, isPhone } = useApp();
  const colors = useStatusColors();
  const [filter, setFilter] = useState<'all' | Status>('all');
  const [q, setQ] = useState('');
  const [sel, setSel] = useState<number | null>(2);
  const [flyTarget, setFlyTarget] = useState<[number, number] | null>(null);
  const markers = useRef<Record<number, L.Marker | null>>({});
  const listRef = useRef<HTMLDivElement>(null);
  useSmoothWheel(listRef, 0.2);

  const base = sites.filter((s) => !q.trim() || `${s.name} ${s.address}`.toLowerCase().includes(q.trim().toLowerCase()));
  const list = base.filter((s) => filter === 'all' || s.st === filter);
  const selected = list.find((s) => s.id === sel && s.hasCoords) ?? null;

  // Открыть подпись маркера, когда выбор пришёл из списка.
  useEffect(() => {
    if (selected) setTimeout(() => markers.current[selected.id]?.openPopup(), 650);
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (s: SiteView) => {
    setSel(s.id);
    if (s.hasCoords) setFlyTarget([s.lat!, s.lng!]);
  };

  const chips = useMemo(
    () => [
      { value: 'all' as const, label: 'Все', color: 'var(--text3)', count: base.length },
      ...STATUS_ORDER.map((k) => ({ value: k, label: STATUS_LABEL[k], color: colors[k], count: base.filter((s) => s.st === k).length })),
    ],
    [base, colors],
  );

  const map = (
    <div className="map-area" data-lenis-prevent>
      <MapContainer center={MAP_CENTER} zoom={14} scrollWheelZoom attributionControl={false} style={{ width: '100%', height: '100%' }}>
        <Tiles />
        {list
          .filter((s) => s.hasCoords)
          .map((s) => (
            <Marker
              key={s.id}
              position={[s.lat!, s.lng!]}
              icon={pinIcon(colors[s.st], s.id === selected?.id)}
              ref={(m) => {
                markers.current[s.id] = m;
              }}
              eventHandlers={{ click: () => setSel(s.id) }}
            >
              <Popup closeButton={false}>
                <div className="map-popup">
                  <b>{s.name}</b>
                  <span>{s.address}</span>
                  <div className="map-popup-row">
                    <Badge tone={s.st} />
                    <button type="button" className="link-btn" onClick={() => go(`/cameras/${s.id}`)}>
                      Подробнее <ArrowRight size={14} />
                    </button>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        <FlyTo to={flyTarget} />
        <AutoResize />
      </MapContainer>
      <div className="map-legend">
        {STATUS_ORDER.map((k) => (
          <span key={k}>
            <i style={{ background: colors[k] }} />
            {STATUS_LABEL[k]}
          </span>
        ))}
      </div>
    </div>
  );

  if (isPhone) {
    return (
      <div className="page page-map-phone">
        {map}
        <div className="map-phone-chips">
          <Chips items={chips} value={filter} onChange={setFilter} />
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader title="Карта" subtitle="Расположение контейнерных площадок" />
      {failed && <ErrorBanner message="Не удалось загрузить площадки" onRetry={retry} />}
      {loading ? (
        <Skeleton />
      ) : (
        <div className="panel map-card" data-lenis-prevent>
          <div className="map-list">
            <div className="map-list-head">
              <div className="input-wrap">
                <Search size={15} className="input-icon" />
                <input type="search" className="input with-icon" placeholder="Поиск по названию или адресу" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Поиск площадки" />
              </div>
              <Chips items={chips} value={filter} onChange={setFilter} />
            </div>
            <div className="map-list-items" ref={listRef}>
              <div key={`${filter}|${q}`} className="map-list-inner stagger">
              {list.map((s, k) => (
                <button key={s.id} type="button" className={`map-item ${s.id === sel ? 'on' : ''}`} style={{ '--i': k } as CSSProperties} onClick={() => pick(s)}>
                  <i style={{ background: colors[s.st] }} />
                  <span>
                    <b>{s.name}</b>
                    <span className="muted small">{s.address}</span>
                    {!s.hasCoords && <span className="warn small">Нет координат — не отмечена на карте</span>}
                  </span>
                </button>
              ))}
              {list.length === 0 && <div className="empty small">Нет площадок</div>}
              </div>
            </div>
          </div>
          {map}
        </div>
      )}
    </div>
  );
}
