import { Link, useLocation, Outlet, Navigate } from 'react-router-dom';
import { LayoutDashboard, Map, Camera, Bell, LogOut } from 'lucide-react';
import { useAuthStore } from '../lib/store';

const NAV = [
  { to: '/', label: 'Панель управления', Icon: LayoutDashboard },
  { to: '/map', label: 'Карта', Icon: Map },
  { to: '/cameras', label: 'Камеры', Icon: Camera },
  { to: '/alerts', label: 'Оповещения', Icon: Bell },
];

export default function Layout() {
  const location = useLocation();
  const { token, user, logout } = useAuthStore();

  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gray-900 text-white flex items-center justify-center font-bold text-sm">
              N
            </div>
            <span className="font-bold text-lg tracking-tight">НЭКОБАК</span>
          </div>
        </div>
        <nav className="flex-1 p-2">
          {NAV.map(({ to, label, Icon }) => {
            const active =
              to === '/' ? location.pathname === '/' : location.pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-0.5 transition-colors ${
                  active
                    ? 'bg-gray-100 text-gray-900 font-medium'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon size={18} strokeWidth={active ? 2.2 : 1.8} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-gray-200">
          <div className="flex items-center gap-2 px-2">
            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium">
              {user?.full_name?.[0] || '?'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">
                {user?.full_name || 'Пользователь'}
              </div>
              <div className="text-xs text-gray-500 truncate">{user?.email || ''}</div>
            </div>
          </div>
          <button
            onClick={logout}
            className="mt-2 w-full text-xs text-gray-500 hover:text-red-600 transition-colors text-left px-2 flex items-center gap-1.5"
          >
            <LogOut size={14} />
            Выйти
          </button>
        </div>
      </aside>

      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
