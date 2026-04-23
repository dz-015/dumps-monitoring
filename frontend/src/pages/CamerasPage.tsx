import { useEffect, useState } from 'react';
import { getCameras, createCamera, deleteCamera, getSites } from '../lib/api';

export default function CamerasPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [sites, setSites] = useState<any[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: '', rtsp_url: '', site_id: '' });
  const [saving, setSaving] = useState(false);

  const load = () => {
    getCameras().then(setCameras);
    getSites().then(setSites);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await createCamera({ name: form.name, rtsp_url: form.rtsp_url, site_id: Number(form.site_id) });
      setShowModal(false);
      setForm({ name: '', rtsp_url: '', site_id: '' });
      load();
    } catch {
      alert('Ошибка создания камеры');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить камеру?')) return;
    await deleteCamera(id);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Камеры</h1>
          <p className="text-sm text-gray-500">Управление камерами наблюдения</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="bg-sky-400 hover:bg-sky-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          + Добавить камеру
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500">
              <th className="px-4 py-3 font-medium">ID</th>
              <th className="px-4 py-3 font-medium">Название</th>
              <th className="px-4 py-3 font-medium">Площадка</th>
              <th className="px-4 py-3 font-medium">RTSP URL</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {cameras.map((cam) => (
              <tr key={cam.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-400">#{cam.id}</td>
                <td className="px-4 py-3 font-medium text-gray-900">{cam.name}</td>
                <td className="px-4 py-3 text-gray-600">{cam.site_name || `#${cam.site_id}`}</td>
                <td className="px-4 py-3 text-gray-400 text-xs font-mono truncate max-w-[200px]">{cam.rtsp_url}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                    cam.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {cam.is_active ? 'Активна' : 'Неактивна'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDelete(cam.id)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
            {cameras.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">Нет камер</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Add camera modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Добавить камеру</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Название</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">RTSP URL</label>
                <input
                  value={form.rtsp_url}
                  onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
                  placeholder="rtsp://..."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-400"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">Площадка</label>
                <select
                  value={form.site_id}
                  onChange={(e) => setForm({ ...form, site_id: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                  required
                >
                  <option value="">Выберите площадку</option>
                  {sites.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 bg-sky-400 hover:bg-sky-500 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50"
                >
                  {saving ? 'Создание...' : 'Создать'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 border border-gray-300 text-gray-600 font-medium py-2.5 rounded-lg hover:bg-gray-50"
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
