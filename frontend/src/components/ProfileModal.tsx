import { useRef, useState } from 'react';
import { Camera, Link2, LogOut, X } from 'lucide-react';
import type { User } from '../lib/types';
import { updateMe, uploadAvatar } from '../lib/api';
import { useAuthStore } from '../lib/store';

interface Props {
  user: User;
  onClose: () => void;
}

export default function ProfileModal({ user, onClose }: Props) {
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);

  const [fullName, setFullName] = useState(user.full_name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAvatarPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    try {
      const updated = await uploadAvatar(file);
      setUser(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить аватар');
    }
  };

  const handleSave = async () => {
    if (fullName.trim() === user.full_name) {
      onClose();
      return;
    }
    setSaving(true);
    setError('');
    try {
      const updated = await updateMe({ full_name: fullName.trim() });
      setUser(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения');
    } finally {
      setSaving(false);
    }
  };

  const initial = user.full_name?.[0] || user.email[0].toUpperCase();

  return (
    <div
      className="fixed inset-0 bg-black/30 flex items-center justify-center z-[1000] p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">Профиль</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-col items-center mb-5">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="relative group w-24 h-24 rounded-full bg-gray-200 flex items-center justify-center overflow-hidden"
            aria-label="Сменить аватар"
          >
            {user.avatar_path ? (
              <img
                src={`/uploads/${user.avatar_path}`}
                alt=""
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-2xl font-medium text-gray-500">{initial}</span>
            )}
            <span className="absolute inset-0 bg-black/40 flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
              <Camera size={20} />
            </span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            onChange={handleAvatarPick}
            className="hidden"
          />
          <p className="text-xs text-gray-400 mt-2">Кликните, чтобы сменить аватар</p>
        </div>

        <div className="space-y-3 mb-5">
          <div>
            <label className="block text-sm text-gray-700 mb-1">Имя</label>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Email</label>
            <div className="text-sm text-gray-900">{user.email}</div>
          </div>
        </div>

        <div className="space-y-3 mb-5 pt-4 border-t border-gray-100">
          <div className="text-sm font-semibold text-gray-900">Уведомления</div>
          <NotificationRow service="MAX" placeholder="Group" />
          <NotificationRow service="Telegram" placeholder="Group" />
        </div>

        {error && <p className="text-red-500 text-sm mb-3">{error}</p>}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 border border-gray-200 text-gray-700 font-medium py-2.5 rounded-lg hover:bg-gray-50 text-sm"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex-1 bg-sky-500 hover:bg-sky-600 text-white font-medium py-2.5 rounded-lg text-sm disabled:opacity-50"
          >
            {saving ? '…' : 'Сохранить'}
          </button>
        </div>

        <button
          type="button"
          onClick={() => {
            logout();
            onClose();
          }}
          className="mt-4 w-full text-sm text-gray-500 hover:text-red-600 transition-colors flex items-center justify-center gap-1.5 py-2"
        >
          <LogOut size={14} />
          Выйти из аккаунта
        </button>
      </div>
    </div>
  );
}

function NotificationRow({ service, placeholder }: { service: string; placeholder: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{service}</div>
      <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2">
        <Link2 size={14} className="text-sky-500" />
        <span className="text-sm text-gray-700">{placeholder}</span>
      </div>
    </div>
  );
}
