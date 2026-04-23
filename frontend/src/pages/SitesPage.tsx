import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getSites } from '../lib/api';
import StatusBadge from '../components/StatusBadge';

export default function SitesPage() {
  const [sites, setSites] = useState<any[]>([]);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    getSites().then(setSites);
  }, []);

  const filtered = filter === 'all' ? sites : sites.filter((s) => s.status === filter);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Площадки</h1>
          <p className="text-sm text-gray-500">Список контейнерных площадок</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        {[
          { value: 'all', label: 'Все' },
          { value: 'clean', label: 'Чистые' },
          { value: 'overflow', label: 'Переполненные' },
          { value: 'contamination', label: 'Загрязнённые' },
        ].map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              filter === f.value
                ? 'bg-gray-900 text-white'
                : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500">
              <th className="px-4 py-3 font-medium">Название</th>
              <th className="px-4 py-3 font-medium">Адрес</th>
              <th className="px-4 py-3 font-medium">Камеры</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium">Обновлено</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((site) => (
              <tr key={site.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{site.name}</td>
                <td className="px-4 py-3 text-gray-600">{site.address}</td>
                <td className="px-4 py-3 text-gray-600">{site.camera_count ?? '—'}</td>
                <td className="px-4 py-3"><StatusBadge value={site.status} /></td>
                <td className="px-4 py-3 text-gray-400 text-xs">
                  {site.updated_at ? new Date(site.updated_at).toLocaleString('ru-RU') : '—'}
                </td>
                <td className="px-4 py-3">
                  <Link to={`/sites/${site.id}`} className="text-blue-500 hover:underline text-xs">
                    Открыть
                  </Link>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">Нет площадок</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
