import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link2, Search, Pencil, X, Plus } from 'lucide-react';
import { getSites, createSite, createCamera } from '../lib/api';
import type { Site } from '../lib/types';
import StatusBadge from '../components/StatusBadge';
import Dropdown from '../components/Dropdown';
import CameraForm from '../components/CameraForm';
import type { CameraFormValues } from '../components/CameraForm';

const STATUS_FILTERS = [
  { value: 'all', label: 'Все типы' },
  { value: 'clean', label: 'Чисто', tone: 'green' as const },
  { value: 'overflow', label: 'Переполнение', tone: 'yellow' as const },
  { value: 'contamination', label: 'Загрязнение', tone: 'red' as const },
];

export default function CamerasPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  const load = () => getSites().then(setSites);
  useEffect(() => {
    load();
  }, []);

  const filtered = sites
    .filter((s) => filter === 'all' || (s.active_status ?? s.status) === filter)
    .filter(
      (s) =>
        search.trim() === '' ||
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.address.toLowerCase().includes(search.toLowerCase())
    );

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Камеры</h1>

      <IntegrationsBlock />

      <div className="flex items-center gap-3 mb-4">
        <Dropdown
          value={filter}
          onChange={setFilter}
          options={STATUS_FILTERS}
          ariaLabel="Фильтр по типу"
        />
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
                  {s.last_checked
                    ? new Date(s.last_checked).toLocaleString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : '—'}
                </td>
                <td className="px-4 py-3 font-medium text-gray-900">{s.name}</td>
                <td className="px-4 py-3 text-gray-600">{s.address}</td>
                <td className="px-4 py-3">
                  <StatusBadge value={s.active_status ?? s.status} />
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/cameras/${s.id}`);
                    }}
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
          onCreated={() => {
            setModalOpen(false);
            load();
          }}
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

function IntegrationRow({
  service,
  placeholder,
  connected,
}: {
  service: string;
  placeholder: string;
  connected?: boolean;
}) {
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
  const handleSubmit = async (values: CameraFormValues) => {
    const site = await createSite({
      name: values.name,
      address: values.address,
      latitude: values.latitude,
      longitude: values.longitude,
    });
    await createCamera({
      site_id: site.id,
      name: values.name,
      rtsp_url: values.rtsp_url,
    });
    onCreated();
  };

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">Добавление камеры</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>
        <CameraForm submitLabel="Добавить" onCancel={onClose} onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
