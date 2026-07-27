import { useCallback, useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  MinusCircle,
  Pencil,
  X,
  XCircle,
} from 'lucide-react';
import {
  getSite,
  getSiteSnapshots,
  getSiteAlerts,
  getSiteProblemsWeek,
  getSiteProblemsMonth,
  updateSite,
  updateCamera,
  createCamera,
  deleteSite,
  getCameras,
} from '../lib/api';
import type { Alert, Camera, ProblemsPoint, Site, Snapshot } from '../lib/types';
import StatusBadge from '../components/StatusBadge';
import BboxOverlay from '../components/BboxOverlay';
import CameraForm from '../components/CameraForm';
import type { CameraFormValues } from '../components/CameraForm';
import ProblemsAreaChart from '../components/ProblemsAreaChart';
import LoadError, { ErrorBanner } from '../components/LoadError';
import { useEscape } from '../lib/useEscape';
import { useRequestGuard } from '../lib/useRequestGuard';

const RESOLUTION_LABELS: Record<string, string> = {
  confirmed_and_cleared: 'Подтверждено и устранено',
  false_alarm: 'Ложная тревога',
  resolved_externally: 'Разрешилось само',
};

function ResolutionCell({ reason }: { reason: string | null }) {
  if (!reason) return <span className="text-gray-400">—</span>;
  const label = RESOLUTION_LABELS[reason] ?? reason;
  if (reason === 'confirmed_and_cleared') {
    return (
      <span className="inline-flex items-center gap-1.5 text-green-700">
        <CheckCircle2 size={16} />
        {label}
      </span>
    );
  }
  if (reason === 'false_alarm') {
    return (
      <span className="inline-flex items-center gap-1.5 text-red-700">
        <XCircle size={16} />
        {label}
      </span>
    );
  }
  if (reason === 'resolved_externally') {
    return (
      <span className="inline-flex items-center gap-1.5 text-gray-500">
        <MinusCircle size={16} />
        {label}
      </span>
    );
  }
  return <span className="text-gray-600">{label}</span>;
}

const ALERTS_PER_PAGE = 10;

type CameraLoadState = 'loading' | 'ready' | 'error';

export default function SiteDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [site, setSite] = useState<Site | null>(null);
  const [siteCamera, setSiteCamera] = useState<Camera | null>(null);
  const [cameraState, setCameraState] = useState<CameraLoadState>('loading');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertsTotal, setAlertsTotal] = useState(0);
  const [weekData, setWeekData] = useState<ProblemsPoint[]>([]);
  const [monthData, setMonthData] = useState<ProblemsPoint[]>([]);
  const [snapIndex, setSnapIndex] = useState(0);
  const [alertsPage, setAlertsPage] = useState(1);
  const [editOpen, setEditOpen] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [partialError, setPartialError] = useState('');
  const begin = useRequestGuard();
  const beginAlerts = useRequestGuard();

  // Reset paginations when switching between sites — render-phase adjustment
  // (not a sync setState inside an effect), otherwise the previous site's
  // index can land out-of-bounds on the new (potentially shorter) list.
  const [prevId, setPrevId] = useState(id);
  if (id !== prevId) {
    setPrevId(id);
    setSnapIndex(0);
    setAlertsPage(1);
    setCameraState('loading');
    setLoadError('');
    setPartialError('');
  }

  // The route keeps this component mounted when only :id changes, so every
  // response is guarded against out-of-order arrival — a slow response for
  // the previous site must never clobber the current one (BUG-10).
  const reload = useCallback(() => {
    if (!id) return;
    const numId = Number(id);
    const fresh = begin();
    getSite(numId)
      .then((s) => {
        if (!fresh()) return;
        setSite(s);
        setLoadError('');
      })
      .catch(() => {
        if (fresh()) setLoadError('Не удалось загрузить площадку');
      });
    getCameras()
      .then((cams) => {
        if (!fresh()) return;
        setSiteCamera(cams.find((c) => c.site_id === numId) ?? null);
        setCameraState('ready');
      })
      .catch(() => {
        if (fresh()) setCameraState('error');
      });
    getSiteSnapshots(numId)
      .then((snaps) => {
        if (fresh()) setSnapshots(snaps);
      })
      .catch(() => {
        if (fresh()) setPartialError('Часть данных не загрузилась');
      });
    getSiteProblemsWeek(numId)
      .then((d) => {
        if (fresh()) setWeekData(d);
      })
      .catch(() => {
        if (fresh()) setPartialError('Часть данных не загрузилась');
      });
    getSiteProblemsMonth(numId)
      .then((d) => {
        if (fresh()) setMonthData(d);
      })
      .catch(() => {
        if (fresh()) setPartialError('Часть данных не загрузилась');
      });
  }, [id, begin]);

  // Server-side pagination of the alert history (BUG-40) — a separate loader
  // so flipping pages doesn't refetch the whole site.
  const loadAlerts = useCallback(() => {
    if (!id) return;
    const numId = Number(id);
    const fresh = beginAlerts();
    getSiteAlerts(numId, alertsPage, ALERTS_PER_PAGE)
      .then((res) => {
        if (!fresh()) return;
        const lastPage = Math.max(1, Math.ceil(res.total / ALERTS_PER_PAGE));
        if (alertsPage > lastPage) {
          setAlertsPage(lastPage);
          return;
        }
        setAlerts(res.items);
        setAlertsTotal(res.total);
      })
      .catch(() => {
        if (fresh()) setPartialError('Часть данных не загрузилась');
      });
  }, [id, alertsPage, beginAlerts]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  // Event-handler entry point: clears error state before refetching (effects
  // themselves must stay free of sync setState).
  const retryAll = () => {
    setLoadError('');
    setPartialError('');
    setCameraState('loading');
    reload();
    loadAlerts();
  };

  if (!site) {
    if (loadError) {
      return (
        <div>
          <Link to="/cameras" className="text-gray-400 hover:text-gray-600 text-sm">
            ← Камеры
          </Link>
          <LoadError message={loadError} onRetry={retryAll} />
        </div>
      );
    }
    return <div className="text-gray-400 p-4">Загрузка...</div>;
  }

  // Clamp snapIndex against the current snapshot list length — guards a brief
  // window after `reload` where snapshots[] is repopulating.
  const safeSnapIndex = Math.min(snapIndex, Math.max(0, snapshots.length - 1));
  const selectedSnap = snapshots[safeSnapIndex] ?? null;

  const totalAlertPages = Math.max(1, Math.ceil(alertsTotal / ALERTS_PER_PAGE));
  const pageAlerts = alerts;

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <Link to="/cameras" className="text-gray-400 hover:text-gray-600 text-sm">
          ← Камеры
        </Link>
      </div>
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-2xl font-bold text-gray-900">{site.name}</h1>
        <StatusBadge value={site.active_status ?? site.status} />
        {/* Editing needs the camera record: opening the form before it loads
            would silently drop or overwrite the RTSP URL (BUG-24). */}
        <button
          type="button"
          onClick={() => setEditOpen(true)}
          disabled={cameraState !== 'ready'}
          title={cameraState === 'loading' ? 'Данные камеры загружаются…' : undefined}
          className="ml-auto inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Pencil size={14} />
          Изменить
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-6">{site.address}</p>

      {cameraState === 'error' && (
        <ErrorBanner
          message="Не удалось загрузить данные камеры — редактирование недоступно"
          onRetry={retryAll}
        />
      )}
      {partialError && <ErrorBanner message={partialError} onRetry={retryAll} />}

      {/* Snapshot viewer with carousel */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900">Последний снимок</h2>
          {selectedSnap && (
            <a
              href={`/uploads/${selectedSnap.image_path}`}
              download
              className="inline-flex items-center gap-1.5 text-sm text-sky-600 hover:text-sky-700 font-medium"
            >
              <Download size={14} />
              Скачать
            </a>
          )}
        </div>

        {selectedSnap ? (
          <>
            <div className="flex items-center gap-3 mb-3">
              <button
                type="button"
                onClick={() => setSnapIndex((i) => Math.max(0, i - 1))}
                disabled={safeSnapIndex === 0}
                aria-label="Предыдущий снимок"
                className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <ChevronLeft size={18} />
              </button>
              <div className="flex-1">
                <BboxOverlay
                  imageUrl={`/uploads/${selectedSnap.image_path}`}
                  detections={selectedSnap.detections || []}
                  width={640}
                  height={480}
                />
              </div>
              <button
                type="button"
                onClick={() => setSnapIndex((i) => Math.min(snapshots.length - 1, i + 1))}
                disabled={safeSnapIndex >= snapshots.length - 1}
                aria-label="Следующий снимок"
                className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <ChevronRight size={18} />
              </button>
            </div>
            <div className="text-xs text-gray-400">
              {new Date(selectedSnap.taken_at).toLocaleString('ru-RU')}
              {selectedSnap.camera_id && ` · Камера #${selectedSnap.camera_id}`}
              {snapshots.length > 1 && ` · ${safeSnapIndex + 1} из ${snapshots.length}`}
            </div>
          </>
        ) : (
          <div className="text-gray-400 text-sm py-12 text-center">Нет снимков</div>
        )}
      </div>

      {/* Two charts side by side */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <ProblemsChart title="Проблемы за последние 7 дней" data={weekData} />
        <ProblemsChart title="Проблемы за последний месяц" data={monthData} />
      </div>

      {/* Alert history table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <h2 className="font-semibold text-gray-900 px-5 pt-5 pb-3">История оповещений</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-gray-500 text-xs uppercase tracking-wide">
              <th className="px-4 py-3 font-medium">Время</th>
              <th className="px-4 py-3 font-medium">Уровень</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3 font-medium">Итог</th>
            </tr>
          </thead>
          <tbody>
            {pageAlerts.map((a) => (
              <tr key={a.id} className="border-b border-gray-50 last:border-0">
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {new Date(a.created_at).toLocaleString('ru-RU', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge value={a.level} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge value={a.status} />
                </td>
                <td className="px-4 py-3 text-sm">
                  <ResolutionCell reason={a.resolution_reason} />
                </td>
              </tr>
            ))}
            {alertsTotal === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-gray-400 text-sm">
                  Нет оповещений
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {alertsTotal > ALERTS_PER_PAGE && (
          <div className="flex items-center justify-end gap-1 px-4 py-3 border-t border-gray-100 text-sm">
            <PagerButton
              disabled={alertsPage <= 1}
              onClick={() => setAlertsPage((p) => p - 1)}
            >
              <ChevronLeft size={14} />
            </PagerButton>
            <span className="px-2 text-gray-500">
              {alertsPage} / {totalAlertPages}
            </span>
            <PagerButton
              disabled={alertsPage >= totalAlertPages}
              onClick={() => setAlertsPage((p) => p + 1)}
            >
              <ChevronRight size={14} />
            </PagerButton>
          </div>
        )}
      </div>

      {editOpen && (
        <EditCameraModal
          site={site}
          camera={siteCamera}
          onClose={() => setEditOpen(false)}
          onSaved={() => {
            setEditOpen(false);
            retryAll();
          }}
          onDeleted={() => navigate('/cameras')}
        />
      )}
    </div>
  );
}

function EditCameraModal({
  site,
  camera,
  onClose,
  onSaved,
  onDeleted,
}: {
  site: Site;
  camera: Camera | null;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  useEscape(onClose);
  const handleSubmit = async (values: CameraFormValues) => {
    await updateSite(site.id, {
      name: values.name,
      address: values.address,
      latitude: values.latitude,
      longitude: values.longitude,
    });
    if (camera) {
      await updateCamera(camera.id, {
        name: values.name,
        rtsp_url: values.rtsp_url,
      });
    } else if (values.rtsp_url.trim()) {
      // Site had no camera yet — create one instead of silently discarding
      // the RTSP URL the user typed (BUG-24).
      await createCamera({
        site_id: site.id,
        name: values.name,
        rtsp_url: values.rtsp_url,
      });
    }
    onSaved();
  };

  const handleDelete = async () => {
    await deleteSite(site.id);
    onDeleted();
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
          <h2 className="text-base font-semibold text-gray-900">Изменить камеру</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>
        <CameraForm
          submitLabel="Сохранить"
          initial={{
            name: site.name,
            address: site.address,
            rtsp_url: camera?.rtsp_url ?? '',
            latitude: site.latitude,
            longitude: site.longitude,
          }}
          onCancel={onClose}
          onSubmit={handleSubmit}
          onDelete={handleDelete}
        />
      </div>
    </div>
  );
}

function ProblemsChart({ title, data }: { title: string; data: ProblemsPoint[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h2 className="font-semibold text-gray-900 mb-3">{title}</h2>
      <ProblemsAreaChart data={data} height={180} xTickFontSize={10} />
    </div>
  );
}

function PagerButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="min-w-[28px] h-7 px-1.5 rounded text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}
