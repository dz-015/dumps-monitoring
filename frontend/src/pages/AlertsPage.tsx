import { useEffect, useState } from 'react';
import { getAlerts, updateAlert } from '../lib/api';
import StatusBadge from '../components/StatusBadge';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [levelFilter, setLevelFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const perPage = 20;

  const load = () => {
    getAlerts({ level: levelFilter || undefined, status: statusFilter || undefined, page, per_page: perPage })
      .then((res) => {
        setAlerts(res.items);
        setTotal(res.total);
      });
  };

  useEffect(() => { load(); }, [page, levelFilter, statusFilter]);

  const totalPages = Math.ceil(total / perPage);

  const handleStatusChange = async (id: number, newStatus: string) => {
    await updateAlert(id, newStatus);
    load();
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Оповещения</h1>
      <p className="text-sm text-gray-500 mb-4">Все оповещения системы</p>

      {/* Filters */}
      <div className="flex gap-4 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Тип:</span>
          <select
            value={levelFilter}
            onChange={(e) => { setLevelFilter(e.target.value); setPage(1); }}
            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white"
          >
            <option value="">Все</option>
            <option value="overflow">Переполнение</option>
            <option value="contamination">Загрязнение</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Статус:</span>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white"
          >
            <option value="">Все</option>
            <option value="new">Новый</option>
            <option value="accepted">Принят</option>
            <option value="resolved">Решён</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500">
              <th className="px-4 py-3 font-medium">ID</th>
              <th className="px-4 py-3 font-medium">Площадка</th>
              <th className="px-4 py-3 font-medium">Тип</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium">Создан</th>
              <th className="px-4 py-3 font-medium">Действие</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-400">#{a.id}</td>
                <td className="px-4 py-3 font-medium text-gray-900">{a.site_name || `Площадка #${a.site_id}`}</td>
                <td className="px-4 py-3">
                  <StatusBadge value={a.level} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge value={a.status} />
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs">
                  {new Date(a.created_at).toLocaleString('ru-RU')}
                </td>
                <td className="px-4 py-3">
                  {a.status === 'new' && (
                    <button
                      onClick={() => handleStatusChange(a.id, 'accepted')}
                      className="text-xs text-blue-500 hover:underline mr-2"
                    >
                      Принять
                    </button>
                  )}
                  {a.status === 'accepted' && (
                    <button
                      onClick={() => handleStatusChange(a.id, 'resolved')}
                      className="text-xs text-green-600 hover:underline"
                    >
                      Решено
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {alerts.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">Нет оповещений</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className="px-3 py-1.5 rounded-lg text-sm border border-gray-200 bg-white disabled:opacity-40"
          >
            ←
          </button>
          <span className="text-sm text-gray-500">
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
            className="px-3 py-1.5 rounded-lg text-sm border border-gray-200 bg-white disabled:opacity-40"
          >
            →
          </button>
        </div>
      )}
    </div>
  );
}
