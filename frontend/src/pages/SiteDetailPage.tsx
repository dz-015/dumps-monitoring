import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getSite, getSiteSnapshots, getSiteAlerts } from '../lib/api';
import StatusBadge from '../components/StatusBadge';
import BboxOverlay from '../components/BboxOverlay';

export default function SiteDetailPage() {
  const { id } = useParams();
  const [site, setSite] = useState<any>(null);
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [selectedSnap, setSelectedSnap] = useState<any>(null);

  useEffect(() => {
    if (!id) return;
    const numId = Number(id);
    getSite(numId).then(setSite);
    getSiteSnapshots(numId).then((snaps) => {
      setSnapshots(snaps);
      if (snaps.length > 0) setSelectedSnap(snaps[0]);
    });
    getSiteAlerts(numId).then(setAlerts);
  }, [id]);

  if (!site) return <div className="text-gray-400 p-4">Загрузка...</div>;

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <Link to="/sites" className="text-gray-400 hover:text-gray-600 text-sm">← Площадки</Link>
      </div>
      <div className="flex items-center gap-3 mb-4">
        <h1 className="text-2xl font-bold text-gray-900">{site.name}</h1>
        <StatusBadge value={site.status} />
      </div>
      <p className="text-sm text-gray-500 mb-6">{site.address}</p>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-xs text-gray-500 mb-1">Координаты</div>
          <div className="text-sm font-medium">{site.latitude?.toFixed(5)}, {site.longitude?.toFixed(5)}</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-xs text-gray-500 mb-1">Камеры</div>
          <div className="text-sm font-medium">{site.camera_count ?? '—'}</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200">
          <div className="text-xs text-gray-500 mb-1">Открытых оповещений</div>
          <div className="text-sm font-medium">{alerts.filter((a) => a.status !== 'resolved').length}</div>
        </div>
      </div>

      {/* Snapshot viewer */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h2 className="font-semibold text-gray-900 mb-3">Последний снимок</h2>
        {selectedSnap ? (
          <div>
            <BboxOverlay
              imageUrl={`/uploads/${selectedSnap.image_path}`}
              detections={selectedSnap.detections || []}
              width={640}
              height={480}
            />
            <div className="text-xs text-gray-400 mt-2">
              {new Date(selectedSnap.created_at).toLocaleString('ru-RU')}
              {selectedSnap.camera_id && ` · Камера #${selectedSnap.camera_id}`}
            </div>
          </div>
        ) : (
          <div className="text-gray-400 text-sm">Нет снимков</div>
        )}

        {/* Snapshot carousel */}
        {snapshots.length > 1 && (
          <div className="flex gap-2 mt-3 overflow-x-auto pb-2">
            {snapshots.map((snap) => (
              <button
                key={snap.id}
                onClick={() => setSelectedSnap(snap)}
                className={`flex-shrink-0 w-20 h-14 rounded-lg overflow-hidden border-2 transition-colors ${
                  selectedSnap?.id === snap.id ? 'border-blue-500' : 'border-transparent'
                }`}
              >
                <img
                  src={`/uploads/${snap.image_path}`}
                  alt=""
                  className="w-full h-full object-cover"
                />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Alert history */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-900 mb-3">История оповещений</h2>
        {alerts.length > 0 ? (
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.id} className="flex items-center gap-3 text-sm py-2 border-b border-gray-50 last:border-0">
                <StatusBadge value={a.level} />
                <StatusBadge value={a.status} />
                <span className="text-gray-400 text-xs ml-auto">
                  {new Date(a.created_at).toLocaleString('ru-RU')}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-400 text-sm">Нет оповещений</div>
        )}
      </div>
    </div>
  );
}
