import { useEffect } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { useApp } from '../ctx';
import { MAP_CENTER } from '../data';

const ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

/** Подложка карты — тайлы OpenStreetMap, как в настоящем фронтенде.
 *  «Спокойный» и тёмный вид — CSS-фильтр поверх тех же тайлов (ключ API не нужен). */
export function Tiles() {
  const { settings } = useApp();
  const cls = settings.theme === 'dark' ? 'tiles-dark' : settings.mapStyle === 'osm' ? 'tiles-plain' : 'tiles-calm';
  return <TileLayer key={cls} className={cls} url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution={ATTR} />;
}

// Метка как на основном сайте: белая капля, в ней цветной круг со значком камеры.
// Рисуется кодом, а не готовым SVG-файлом, чтобы цвет шёл из выбранной палитры.
export function pinIcon(color: string, selected = false): L.DivIcon {
  const w = selected ? 46 : 38;
  const h = Math.round((w * 61) / 54);
  return L.divIcon({
    className: `pin-icon ${selected ? 'selected' : ''}`,
    html: `<svg width="${w}" height="${h}" viewBox="0 0 54 61" fill="none">
      <path fill-rule="evenodd" d="M48 23C48 11.402 38.598 2 27 2C15.402 2 6 11.402 6 23C6 25.871 6.576 28.608 7.619 31.1C11.302 41.155 22.838 48.511 26.189 50.477C26.764 50.815 27.455 50.816 28.03 50.479C31.804 48.264 45.987 39.198 47.593 27.136C47.86 25.799 48 24.416 48 23Z" fill="#fff"/>
      <rect x="9" y="5" width="36" height="36" rx="18" style="fill:${color}"/>
      <g stroke="#fff" stroke-width="2.14" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="27" cy="20.32" r="7.5"/>
        <circle cx="27" cy="20.32" r="3.21"/>
        <path d="M23.25 26.75L20.04 33.18H33.96L30.75 26.75"/>
      </g>
    </svg>`,
    iconSize: [w, h],
    iconAnchor: [w / 2, (h * 51) / 61],
    popupAnchor: [0, -(h * 0.8)],
  });
}

/** Перелёт к точке при смене выбора. */
export function FlyTo({ to, zoom }: { to: [number, number] | null; zoom?: number }) {
  const map = useMap();
  useEffect(() => {
    if (to) map.flyTo(to, zoom ?? Math.max(map.getZoom(), 15), { duration: 0.6 });
  }, [to?.[0], to?.[1]]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** Leaflet не знает, что контейнер поменял размер (свернули меню, режим телефона). */
export function AutoResize() {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(el);
    return () => ro.disconnect();
  }, [map]);
  return null;
}

/** Карта площадки: двигается и приближается колесом и кнопками «+ / −». */
export function MiniMap({ lat, lng, color, height = 180 }: { lat: number; lng: number; color: string; height?: number | string }) {
  return (
    <div className="minimap" style={{ height }} data-lenis-prevent>
      <MapContainer
        center={[lat, lng]}
        zoom={16}
        zoomSnap={0.25}
        wheelPxPerZoomLevel={90}
        attributionControl={false}
        style={{ width: '100%', height: '100%' }}
      >
        <Tiles />
        <Marker position={[lat, lng]} icon={pinIcon(color)} />
        <AutoResize />
      </MapContainer>
    </div>
  );
}

function ClickToPick({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onPick(+e.latlng.lat.toFixed(5), +e.latlng.lng.toFixed(5)) });
  return null;
}

export function PickerMap({ lat, lng, onPick }: { lat: number | null; lng: number | null; onPick: (lat: number, lng: number) => void }) {
  return (
    <div className="minimap picker" style={{ height: 220 }}>
      <MapContainer center={lat != null && lng != null ? [lat, lng] : MAP_CENTER} zoom={13} attributionControl={false} style={{ width: '100%', height: '100%' }}>
        <Tiles />
        <ClickToPick onPick={onPick} />
        {lat != null && lng != null && <Marker position={[lat, lng]} icon={pinIcon('var(--p)')} />}
        <AutoResize />
      </MapContainer>
      {lat == null && <span className="picker-hint">Нажмите на карту, чтобы поставить точку</span>}
    </div>
  );
}
