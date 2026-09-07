import { X } from 'lucide-react';
import { updateSite, updateCamera, createCamera, deleteSite } from '../lib/api';
import type { Camera, Site } from '../lib/types';
import CameraForm from './CameraForm';
import type { CameraFormValues } from './CameraForm';
import { useEscape } from '../lib/useEscape';

/**
 * Site+camera edit dialog, shared by the site detail page and the cameras
 * list. Callers must pass the loaded camera (or null for a site that has
 * none) — opening the form before the camera record is known silently loses
 * the RTSP URL (BUG-24).
 */
export default function EditCameraModal({
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
        external_key: values.external_key || null,
      });
    } else if (values.rtsp_url.trim()) {
      // Site had no camera yet — create one instead of silently discarding
      // the RTSP URL the user typed (BUG-24).
      await createCamera({
        site_id: site.id,
        name: values.name,
        rtsp_url: values.rtsp_url,
        external_key: values.external_key || null,
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
            external_key: camera?.external_key ?? '',
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
