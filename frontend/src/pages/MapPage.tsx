import { useCallback, useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { Link } from 'react-router-dom';
import { getSites } from '../lib/api';
import type { Site } from '../lib/types';
import StatusBadge from '../components/StatusBadge';
import { ErrorBanner } from '../components/LoadError';
import 'leaflet/dist/leaflet.css';
import pinGreen from '../assets/map-pins/green.svg';
import pinYellow from '../assets/map-pins/yellow.svg';
import pinRed from '../assets/map-pins/red.svg';

const STATUS_PIN: Record<string, string> = {
  clean: pinGreen,
  overflow: pinYellow,
  contamination: pinRed,
};

const ICON_CACHE: Record<string, L.Icon> = {};
function pinIcon(status: string): L.Icon {
  const url = STATUS_PIN[status] ?? pinGreen;
  if (!ICON_CACHE[url]) {
    ICON_CACHE[url] = L.icon({
      iconUrl: url,
      iconSize: [54, 61],
      iconAnchor: [27, 53],
      popupAnchor: [0, -50],
    });
  }
  return ICON_CACHE[url];
}

export default function MapPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    getSites()
      .then((s) => {
        setSites(s);
        setError('');
      })
      .catch(() => setError('Не удалось загрузить площадки'));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Карта</h1>
      <p className="text-sm text-gray-500 mb-4">Расположение контейнерных площадок</p>

      {error && <ErrorBanner message={error} onRetry={load} />}

      <div
        className="bg-white rounded-xl border border-gray-200 overflow-hidden"
        style={{ height: 'calc(100vh - 180px)' }}
      >
        <MapContainer
          center={[44.952, 34.1]}
          zoom={13}
          className="w-full h-full"
          scrollWheelZoom
          attributionControl={false}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {sites
            .filter(
              (s): s is Site & { latitude: number; longitude: number } =>
                s.latitude !== null && s.longitude !== null
            )
            .map((site) => {
              const derived = site.active_status ?? site.status;
              return (
                <Marker
                  key={site.id}
                  position={[site.latitude, site.longitude]}
                  icon={pinIcon(derived)}
                >
                  <Popup>
                    <div className="text-sm min-w-[180px]">
                      <div className="font-semibold mb-1">{site.name}</div>
                      <div className="text-gray-500 text-xs mb-2">{site.address}</div>
                      <StatusBadge value={derived} />
                      <div className="mt-2">
                        <Link
                          to={`/cameras/${site.id}`}
                          className="text-blue-500 text-xs hover:underline"
                        >
                          Подробнее →
                        </Link>
                      </div>
                    </div>
                  </Popup>
                </Marker>
              );
            })}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-3">
        {[
          { color: '#22c55e', label: 'Чисто' },
          { color: '#eab308', label: 'Переполнение' },
          { color: '#ef4444', label: 'Загрязнение' },
        ].map((item) => (
          <div key={item.label} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}
