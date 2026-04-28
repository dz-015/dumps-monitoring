import { useState } from 'react';
import { Search } from 'lucide-react';
import MapPicker from './MapPicker';

export interface CameraFormValues {
  name: string;
  address: string;
  rtsp_url: string;
  latitude: number | null;
  longitude: number | null;
}

interface Props {
  initial?: Partial<CameraFormValues>;
  submitLabel: string;
  onCancel: () => void;
  onSubmit: (values: CameraFormValues) => Promise<void>;
  onDelete?: () => Promise<void>;
}

export default function CameraForm({
  initial,
  submitLabel,
  onCancel,
  onSubmit,
  onDelete,
}: Props) {
  const [name, setName] = useState(initial?.name ?? '');
  const [address, setAddress] = useState(initial?.address ?? '');
  const [rtsp, setRtsp] = useState(initial?.rtsp_url ?? '');
  const [latitude, setLatitude] = useState<number | null>(initial?.latitude ?? null);
  const [longitude, setLongitude] = useState<number | null>(initial?.longitude ?? null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (latitude === null || longitude === null) {
      setError('Укажите точку на карте');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onSubmit({ name, address, rtsp_url: rtsp, latitude, longitude });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    setDeleting(true);
    setError('');
    try {
      await onDelete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка удаления');
      setDeleting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm text-gray-700 mb-1">Название площадки *</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
          required
        />
      </div>
      <div>
        <label className="block text-sm text-gray-700 mb-1">RTSP-ссылка *</label>
        <input
          value={rtsp}
          onChange={(e) => setRtsp(e.target.value)}
          placeholder="rtsp://login:password@IP:554/path"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400"
          required
        />
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
      <div>
        <label className="block text-sm text-gray-700 mb-1">Точка на карте *</label>
        <MapPicker
          latitude={latitude}
          longitude={longitude}
          onChange={(lat, lng) => {
            setLatitude(lat);
            setLongitude(lng);
          }}
        />
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="flex gap-2 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 border border-gray-200 text-gray-700 font-medium py-2.5 rounded-lg hover:bg-gray-50"
        >
          Отмена
        </button>
        <button
          type="submit"
          disabled={saving || deleting}
          className="flex-1 bg-sky-500 hover:bg-sky-600 text-white font-medium py-2.5 rounded-lg disabled:opacity-50"
        >
          {saving ? '…' : submitLabel}
        </button>
      </div>

      {onDelete && (
        <div className="pt-2 border-t border-gray-100">
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-700 flex-1">Удалить камеру со всей историей?</span>
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5"
              >
                Нет
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="bg-red-500 hover:bg-red-600 text-white text-sm font-medium px-3 py-1.5 rounded-lg disabled:opacity-50"
              >
                {deleting ? '…' : 'Да, удалить'}
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Удалить камеру
            </button>
          )}
        </div>
      )}
    </form>
  );
}
