import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Pencil, X, Plus } from 'lucide-react';
import { getSites, getCameras, createSite, createCamera, deleteSite } from '../lib/api';
import type { Camera, Site } from '../lib/types';
import StatusBadge from '../components/StatusBadge';
import Dropdown from '../components/Dropdown';
import CameraForm from '../components/CameraForm';
import type { CameraFormValues } from '../components/CameraForm';
import EditCameraModal from '../components/EditCameraModal';
import { ErrorBanner } from '../components/LoadError';
import { useEscape } from '../lib/useEscape';

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
  const [error, setError] = useState('');
  // Pencil-edit state: the modal needs the site's camera record first (BUG-24),
  // so opening goes through a short loading step.
  const [editingSite, setEditingSite] = useState<Site | null>(null);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [editLoadingId, setEditLoadingId] = useState<number | null>(null);
  const navigate = useNavigate();

  const load = useCallback(() => {
    getSites()
      .then((s) => {
        setSites(s);
        setError('');
      })
      .catch(() => setError('Не удалось загрузить список камер'));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const handleEditClick = (site: Site) => {
    setEditLoadingId(site.id);
    getCameras()
      .then((cams) => {
        setEditingCamera(cams.find((c) => c.site_id === site.id) ?? null);
        setEditingSite(site);
      })
      .catch(() => setError('Не удалось загрузить данные камеры'))
      .finally(() => setEditLoadingId(null));
  };

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

      {error && <ErrorBanner message={error} onRetry={load} />}

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <Dropdown
          value={filter}
          onChange={setFilter}
          options={STATUS_FILTERS}
          ariaLabel="Фильтр по типу"
        />
        <div className="relative flex-1 max-w-sm min-w-[160px]">
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

      {/* На телефоне таблица уходит в горизонтальную прокрутку — это админский
          экран, карточный вид ему не нужен */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
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
                      handleEditClick(s);
                    }}
                    disabled={editLoadingId === s.id}
                    aria-label={`Изменить ${s.name}`}
                    className="text-gray-400 hover:text-gray-700 disabled:opacity-40"
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

      {editingSite && (
        <EditCameraModal
          site={editingSite}
          camera={editingCamera}
          onClose={() => setEditingSite(null)}
          onSaved={() => {
            setEditingSite(null);
            load();
          }}
          onDeleted={() => {
            setEditingSite(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function AddCameraModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  useEscape(onClose);
  const handleSubmit = async (values: CameraFormValues) => {
    const site = await createSite({
      name: values.name,
      address: values.address,
      latitude: values.latitude,
      longitude: values.longitude,
    });
    try {
      await createCamera({
        site_id: site.id,
        name: values.name,
        rtsp_url: values.rtsp_url,
        external_key: values.external_key || null,
      });
    } catch (err) {
      // Roll the orphan site back so the user doesn't see a half-created
      // entry on the list. Best-effort — if the rollback itself fails we
      // still surface the original error to the form.
      await deleteSite(site.id).catch(() => {});
      throw err;
    }
    onCreated();
  };

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-[1000] p-4"
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
