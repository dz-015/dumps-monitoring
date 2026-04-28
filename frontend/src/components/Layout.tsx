import { useEffect, useState } from 'react';
import { Link, useLocation, Outlet, Navigate } from 'react-router-dom';
import { LayoutDashboard, Map, Bell, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuthStore } from '../lib/store';
import { getMe } from '../lib/api';
import ProfileModal from './ProfileModal';
import logo from '../assets/logo.svg';
import camerasIcon from '../assets/sidebar-cameras.svg';

type NavItem = {
  to: string;
  label: string;
  Icon?: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  iconSrc?: string;
};

const NAV: NavItem[] = [
  { to: '/', label: 'Панель управления', Icon: LayoutDashboard },
  { to: '/map', label: 'Карта', Icon: Map },
  { to: '/cameras', label: 'Камеры', iconSrc: camerasIcon },
  { to: '/alerts', label: 'Оповещения', Icon: Bell },
];

const COLLAPSE_KEY = 'sidebar-collapsed';

export default function Layout() {
  const location = useLocation();
  const { token, user } = useAuthStore();
  const setUser = useAuthStore((s) => s.setUser);
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem(COLLAPSE_KEY) === '1'
  );
  const [profileOpen, setProfileOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  // Hydrate user from /me on first mount when we have a token but no profile yet
  // (e.g. page reload — token in storage, store.user is null).
  useEffect(() => {
    if (token && !user) {
      getMe().then(setUser).catch(() => {});
    }
  }, [token, user, setUser]);

  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside
        className={`${collapsed ? 'w-16' : 'w-56'} bg-white border-r border-gray-200 flex flex-col transition-[width] duration-150`}
      >
        <div className="p-4 border-b border-gray-200">
          {collapsed ? (
            <div className="flex flex-col items-center gap-2">
              <img src={logo} alt="НЭКОБАК" className="w-8 h-8" />
              <button
                type="button"
                onClick={() => setCollapsed(false)}
                aria-label="Развернуть меню"
                className="p-1 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <img src={logo} alt="НЭКОБАК" className="w-8 h-8 flex-shrink-0" />
              <span className="font-bold text-lg tracking-tight">НЭКОБАК</span>
              <button
                type="button"
                onClick={() => setCollapsed(true)}
                aria-label="Свернуть меню"
                className="ml-auto p-1 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100"
              >
                <ChevronLeft size={16} />
              </button>
            </div>
          )}
        </div>
        <nav className="flex-1 p-2">
          {NAV.map(({ to, label, Icon, iconSrc }) => {
            const active =
              to === '/' ? location.pathname === '/' : location.pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                title={collapsed ? label : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-0.5 transition-colors ${
                  active
                    ? 'bg-gray-100 text-gray-900 font-medium'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                {iconSrc ? (
                  <img src={iconSrc} alt="" className="w-[18px] h-[18px] flex-shrink-0" />
                ) : (
                  Icon && <Icon size={18} strokeWidth={active ? 2.2 : 1.8} />
                )}
                {!collapsed && label}
              </Link>
            );
          })}
        </nav>
        <button
          type="button"
          onClick={() => setProfileOpen(true)}
          title={collapsed ? user?.full_name || user?.email : undefined}
          className="p-3 border-t border-gray-200 text-left hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2 px-2">
            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium flex-shrink-0 overflow-hidden">
              {user?.avatar_path ? (
                <img
                  src={`/uploads/${user.avatar_path}`}
                  alt=""
                  className="w-full h-full object-cover"
                />
              ) : (
                user?.full_name?.[0] || user?.email?.[0]?.toUpperCase() || '?'
              )}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">
                  {user?.full_name || 'Пользователь'}
                </div>
                <div className="text-xs text-gray-500 truncate">{user?.email || ''}</div>
              </div>
            )}
          </div>
        </button>
      </aside>

      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>

      {profileOpen && user && (
        <ProfileModal user={user} onClose={() => setProfileOpen(false)} />
      )}
    </div>
  );
}
