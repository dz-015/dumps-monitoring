import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link2, Search, Pencil, X, Plus } from 'lucide-react';
import { getSites, createSite } from '../lib/api';
import StatusBadge from '../components/StatusBadge';

type Site = {
  id: number;
  name: string;
  address: string;
  status: string;
  latitude: number | null;
  longitude: number | null;
  camera_count: number;
  created_at: string;
};

const STATUS_FILTERS = [
  { value: 'all', label: 'Все типы' },
  { value: 'clean', label: 'Чисто' },
  { value: 'overflow', label: 'Переполнение' },
  { value: 'contamination', label: 'Загрязнение' },
];

export default function CamerasPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  const load = () => getSites().then(setSites);
  useEffect(() => { load(); }, []);

  const filtered = sites
    .filter((s) => filter === 'all' || s.status === filter)
    .filter((s) =>
      search.trim() === ''
      || s.name.toLowerCase().includes(search.toLowerCase())
      || s.address.toLowerCase().includes(search.toLowerCase())
    );

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Камеры</h1>

      <IntegrationsBlock />

      <div className="flex items-center gap-3 mb-4">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-400"
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск"
            className="w-full border border-gray-200 rounded-lg pl-8 pr-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-400"
          />
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="ml-auto bg-sky-500 hover:bg-sky-600 text-white text-sm font-medium px-4 py-2 rounded-lg inline-flex items-center gap-1.5"
        >
          <Plus size={16} /> Добавить
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500 text-xs uppercase tracking-wide">
              <th className="px-4 py-3 font-medium">Время последней проверки</th>
              <th className="px-4 py-3 font-medium">Площадка</th>
              <th className="px-4 py-3 font-medium">Адрес</th>
              <th className="px-4 py-3 font-medium">Тип</th>
              <th className="px-4 py-3 font-medium w-10"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr
                key={s.id}
                className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                onClick={() => navigate(`/cameras/${s.id}`)}
              >
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {new Date(s.created_at).toLocaleString('ru-RU', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                  })}
                </td>
                <td className="px-4 py-3 font-medium text-gray-900">{s.name}</td>
                <td className="px-4 py-3 text-gray-600">{s.address}</td>
                <td className="px-4 py-3"><StatusBadge value={s.status} /></td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/cameras/${s.id}`); }}
                    className="text-gray-400 hover:text-gray-700"
                  >
                    <Pencil size={14} />
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-gray-400 text-sm">
                  Нет камер
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {modalOpen && (
        <AddCameraModal
          onClose={() => setModalOpen(false)}
          onCreated={() => { setModalOpen(false); load(); }}
        />
      )}
    </div>
  );
}

function IntegrationsBlock() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
      <div className="text-sm font-semibold text-gray-900 mb-3">Оповещения</div>
      <div className="space-y-3">
        <IntegrationRow service="MAX" placeholder="Group" connected />
        <IntegrationRow service="Telegram" placeholder="Group" connected />
      </div>
    </div>
  );
}

function IntegrationRow({ service, placeholder, connected }: { service: string; placeholder: string; connected?: boolean }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{service}</div>
      <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2">
        <Link2 size={14} className={connected ? 'text-sky-500' : 'text-gray-400'} />
        <span className="text-sm text-gray-700">{placeholder}</span>
      </div>
    </div>
  );
}

function AddCameraModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('');
  const [rtsp, setRtsp] = useState('');
  const [address, setAddress] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      // MVP: create Site; Camera creation will follow once backend supports
      // the "one-request" camera+site in this view.
      await createSite({ name, address });
      onCreated();
    } catch (err: any) {
      setError(err.message || 'Ошибка');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">Добавление камеры</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-700 mb-1">Название *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">Ссылка *</label>
            <input
              value={rtsp}
              onChange={(e) => setRtsp(e.target.value)}
              placeholder="rtsp://login:password@IP_address:554/path"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400"
              required
            />
            <p className="text-xs text-gray-400 mt-1">RTSP ссылка на камеру</p>
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-1">Адрес *</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full border border-gray-200 rounded-lg pl-8 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                required
              />
            </div>
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-gray-200 text-gray-700 font-medium py-2.5 rounded-lg hover:bg-gray-50"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-sky-500 hover:bg-sky-600 text-white font-medium py-2.5 rounded-lg disabled:opacity-50"
            >
              {saving ? '…' : 'Добавить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
