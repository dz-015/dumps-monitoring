import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { Link } from 'react-router-dom';
import { getSites } from '../lib/api';
import type { Site } from '../lib/types';
import StatusBadge from '../components/StatusBadge';
import 'leaflet/dist/leaflet.css';

const STATUS_COLOR: Record<string, string> = {
  clean: '#22c55e',
  overflow: '#eab308',
  contamination: '#ef4444',
};

export default function MapPage() {
  const [sites, setSites] = useState<Site[]>([]);

  useEffect(() => {
    getSites().then(setSites);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Карта</h1>
      <p className="text-sm text-gray-500 mb-4">Расположение контейнерных площадок</p>

      <div
        className="bg-white rounded-xl border border-gray-200 overflow-hidden"
        style={{ height: 'calc(100vh - 180px)' }}
      >
        <MapContainer center={[44.952, 34.1]} zoom={13} className="w-full h-full" scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://osm.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {sites
            .filter(
              (s): s is Site & { latitude: number; longitude: number } =>
                s.latitude !== null && s.longitude !== null
            )
            .map((site) => {
              const derived = site.active_status ?? site.status;
              return (
              <CircleMarker
                key={site.id}
                center={[site.latitude, site.longitude]}
                radius={10}
                pathOptions={{
                  color: STATUS_COLOR[derived] || '#94a3b8',
                  fillColor: STATUS_COLOR[derived] || '#94a3b8',
                  fillOpacity: 0.7,
                  weight: 2,
                }}
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
              </CircleMarker>
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
