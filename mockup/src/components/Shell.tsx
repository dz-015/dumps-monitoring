import type { ComponentType } from 'react';
import { Bell, LayoutDashboard, Map, PanelLeftClose, PanelLeftOpen, Webcam } from 'lucide-react';
import { useApp } from '../ctx';
import { Logo, Wordmark } from './ui';

type Item = { path: string; page: string; label: string; short: string; Icon: ComponentType<{ size?: number; strokeWidth?: number }> };

const NAV: Item[] = [
  { path: '/', page: 'dashboard', label: 'Панель управления', short: 'Панель', Icon: LayoutDashboard },
  { path: '/map', page: 'map', label: 'Карта', short: 'Карта', Icon: Map },
  { path: '/cameras', page: 'cameras', label: 'Камеры', short: 'Камеры', Icon: Webcam },
  { path: '/alerts', page: 'alerts', label: 'Оповещения', short: 'Оповещения', Icon: Bell },
];

function useActive() {
  const { route } = useApp();
  return (it: Item) => it.page === route.page || (it.page === 'cameras' && route.page === 'site');
}

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { go, alerts, user, setModal } = useApp();
  const isActive = useActive();
  const newCount = alerts.filter((a) => a.status === 'new').length;
  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-head">
        <Logo size={30} />
        <span className="sidebar-brand">
          <Wordmark size={15} />
        </span>
      </div>
      <nav aria-label="Основная навигация" className="sidebar-nav">
                {NAV.map((it) => {
          const on = isActive(it);
          return (
            <a
              key={it.path}
              href={`#${it.path}`}
              onClick={(e) => {
                e.preventDefault();
                go(it.path);
              }}
              className={`nav-item ${on ? 'active' : ''}`}
              title={collapsed ? it.label : undefined}
              aria-current={on ? 'page' : undefined}
            >
              <it.Icon size={18} strokeWidth={1.8} />
              <span className="nav-label">{it.label}</span>
              {it.page === 'alerts' && newCount > 0 && (collapsed ? <span className="nav-dot" /> : <span className="nav-badge">{newCount}</span>)}
            </a>
          );
        })}
      </nav>
      <div className="sidebar-foot">
        <button type="button" className="nav-item subtle" onClick={onToggle} aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'} title={collapsed ? 'Развернуть меню' : undefined}>
          {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          <span className="nav-label">Свернуть меню</span>
        </button>
        <button type="button" className="user-btn" onClick={() => setModal({ kind: 'profile' })} aria-label="Профиль" title={collapsed ? user.name : undefined}>
          <span className="avatar">{user.initials}</span>
          <span className="user-meta">
            <b>{user.name}</b>
            <span>{user.email}</span>
          </span>
        </button>
      </div>
    </aside>
  );
}

export function PhoneTopbar() {
  const { go, alerts } = useApp();
  const newCount = alerts.filter((a) => a.status === 'new').length;
  return (
    <header className="topbar">
      <Logo size={28} />
      <Wordmark size={14} />
      <span style={{ flex: 1 }} />
      <button type="button" className="icon-btn" aria-label="Оповещения" onClick={() => go('/alerts')}>
        <Bell size={21} />
        {newCount > 0 && <span className="topbar-badge">{newCount}</span>}
      </button>
    </header>
  );
}

export function BottomNav() {
  const { go, user, setModal } = useApp();
  const isActive = useActive();
  return (
    <nav aria-label="Нижняя навигация" className="bottom-nav">
      {NAV.map((it) => {
        const on = isActive(it);
        return (
          <button key={it.path} type="button" className={`bn-item ${on ? 'active' : ''}`} onClick={() => go(it.path)} aria-current={on ? 'page' : undefined}>
            <span className="bn-pill">
              <it.Icon size={20} strokeWidth={1.8} />
            </span>
            {it.short}
          </button>
        );
      })}
      <button type="button" className="bn-item" onClick={() => setModal({ kind: 'profile' })}>
        <span className="avatar sm">{user.initials}</span>
        Профиль
      </button>
    </nav>
  );
}
