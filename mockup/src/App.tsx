import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Lenis from 'lenis';
import { Ctx, type AppCtx, type Modal, type Route } from './ctx';
import { baseAlerts, baseSites, day, statusOf, type Alert, type Site } from './data';
import { buildVars, DEFAULTS, varsStyle, type Settings } from './theme';
import { BottomNav, PhoneTopbar, Sidebar } from './components/Shell';
import { SettingsPanel } from './components/SettingsPanel';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import MapPage from './pages/MapPage';
import Cameras from './pages/Cameras';
import SitePage from './pages/Site';
import Alerts, { AlertDrawerHost } from './pages/Alerts';
import { CameraFormModal, Lightbox, ProfileModal } from './modals/Modals';

// Номер растёт, когда меняются значения по умолчанию: старые сохранённые настройки не подхватываем.
const SETTINGS_KEY = 'tko-mockup-settings-v3';

/** Сохранённые настройки, поверх них — параметры из адреса (?device=phone&theme=dark&primary=0EA5E9). */
function loadSettings(): Settings {
  let s: Settings = DEFAULTS;
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) s = { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    /* нет доступа к localStorage — берём значения по умолчанию */
  }
  const q = new URLSearchParams(location.search);
  const over: Partial<Record<keyof Settings, string | number>> = {};
  for (const k of Object.keys(DEFAULTS) as (keyof Settings)[]) {
    const v = q.get(k);
    if (v == null) continue;
    if (k === 'motion') (over as Record<string, unknown>)[k] = v !== 'false' && v !== '0';
    else over[k] = k === 'radius' ? Number(v) : k === 'primary' && !v.startsWith('#') ? `#${v}` : v;
  }
  return { ...s, ...(over as Partial<Settings>) };
}

function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/';
  if (path === '/login') return { page: 'login' };
  if (path === '/map') return { page: 'map' };
  if (path === '/cameras') return { page: 'cameras' };
  if (path === '/alerts' || /^\/alerts\/\d+$/.test(path)) return { page: 'alerts' };
  const m = path.match(/^\/cameras\/(\d+)$/);
  if (m) return { page: 'site', id: Number(m[1]) };
  return { page: 'dashboard' };
}

/** #/alerts/3 — открыть страницу оповещений сразу с панелью оповещения №3. */
function alertFromHash(hash: string): number | null {
  const m = hash.match(/^#\/alerts\/(\d+)$/);
  return m ? Number(m[1]) : null;
}

function useNarrow(limit: number) {
  const [narrow, setNarrow] = useState(() => window.innerWidth < limit);
  useEffect(() => {
    const h = () => setNarrow(window.innerWidth < limit);
    window.addEventListener('resize', h);
    return () => window.removeEventListener('resize', h);
  }, [limit]);
  return narrow;
}

export default function App() {
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [route, setRoute] = useState<Route>(() => parseRoute(location.hash));
  const [sites, setSites] = useState<Site[]>(baseSites);
  const [alerts, setAlerts] = useState<Alert[]>(baseAlerts);
  const [modal, setModal] = useState<Modal>(null);
  const [openAlert, setOpenAlert] = useState<number | null>(() => alertFromHash(location.hash));
  const [collapsed, setCollapsed] = useState(false);
  const [retried, setRetried] = useState(false);
  const [userName, setUserName] = useState('Иван Иванович');
  const [channels, setChannels] = useState({ max: true, tg: false });
  const narrow = useNarrow(760);
  const isPhone = settings.device === 'phone' || narrow;

  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch {
      /* приватный режим браузера — настройки просто не запомнятся */
    }
  }, [settings]);
  useEffect(() => setRetried(false), [settings.dataState]);
  useEffect(() => {
    const h = () => {
      setRoute(parseRoute(location.hash));
      setModal(null);
      const a = alertFromHash(location.hash);
      if (a != null) setOpenAlert(a);
    };
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);
  // Плавная (инерционная) прокрутка основной области. Выключается настройкой
  // «Анимации» и системным «уменьшить движение».
  const mainRef = useRef<HTMLElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const lenisRef = useRef<Lenis | null>(null);
  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const smooth = settings.motion && !reduced;
  useEffect(() => {
    if (!smooth || !mainRef.current || !contentRef.current) return;
    const lenis = new Lenis({ wrapper: mainRef.current, content: contentRef.current, lerp: 0.12, wheelMultiplier: 0.9, smoothWheel: true });
    lenisRef.current = lenis;
    let id = 0;
    const loop = (t: number) => {
      lenis.raf(t);
      id = requestAnimationFrame(loop);
    };
    id = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(id);
      lenis.destroy();
      lenisRef.current = null;
    };
  }, [smooth, isPhone, route.page === 'login']); // eslint-disable-line react-hooks/exhaustive-deps

  // При переходе — в начало страницы, без анимации прокрутки.
  useEffect(() => {
    if (lenisRef.current) lenisRef.current.scrollTo(0, { immediate: true });
    else mainRef.current?.scrollTo({ top: 0 });
  }, [route]);

  const go = useCallback((path: string) => {
    location.hash = path;
  }, []);

  const loading = settings.dataState === 'loading';
  const failed = settings.dataState === 'error' && !retried;
  const noData = settings.dataState === 'empty' || failed;

  const ctx: AppCtx = useMemo(() => {
    const visibleSites = noData ? [] : sites;
    const visibleAlerts = noData ? [] : alerts;
    const initials =
      userName
        .split(' ')
        .filter(Boolean)
        .map((w) => w[0])
        .join('')
        .slice(0, 2)
        .toUpperCase() || '?';
    return {
      settings,
      isPhone,
      route,
      go,
      sites: visibleSites.map((s) => ({ ...s, st: statusOf(alerts, s.id), hasCoords: s.lat != null && s.lng != null })),
      alerts: visibleAlerts,
      siteAny: (id) => sites.find((s) => s.id === id),
      loading,
      failed,
      retry: () => setRetried(true),
      modal,
      setModal,
      openAlert,
      setOpenAlert,
      acceptAlert: (id) => setAlerts((as) => as.map((a) => (a.id === id ? { ...a, status: 'accepted' } : a))),
      resolveAlert: (id, reason) => {
        const now = new Date();
        const rt = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
        setAlerts((as) => as.map((a) => (a.id === id ? { ...a, status: 'resolved', reason, rd: 0, rt } : a)));
      },
      saveSite: (patch) =>
        setSites((ss) => {
          if (patch.id != null) return ss.map((s) => (s.id === patch.id ? { ...s, ...patch } : s));
          const id = Math.max(0, ...ss.map((s) => s.id)) + 1;
          return [...ss, { name: '', address: '', lat: null, lng: null, key: '—', rtsp: '', active: true, checked: `${day(0)}, —`, ...patch, id }];
        }),
      deleteSite: (id) => {
        setSites((ss) => ss.filter((s) => s.id !== id));
        setAlerts((as) => as.filter((a) => a.siteId !== id));
      },
      user: { name: userName, email: 'operator@example.ru', initials },
      setUserName,
      channels,
      toggleChannel: (k) => setChannels((c) => ({ ...c, [k]: !c[k] })),
      logout: () => {
        setModal(null);
        go('/login');
      },
      login: () => go('/'),
    };
  }, [settings, isPhone, route, go, sites, alerts, noData, loading, failed, modal, openAlert, userName, channels]);

  const vars = useMemo(() => buildVars(settings), [settings]);
  const rootCls = [
    'app',
    settings.theme === 'dark' ? 'dark' : 'light',
    `b-${settings.badges}`,
    `sb-${settings.sidebar}`,
    `sb-${settings.sidebar}`,
    settings.density,
    isPhone ? 'phone' : 'desk',
    settings.device === 'phone' && !narrow ? 'framed' : '',
    smooth ? '' : 'no-motion',
  ].join(' ');

  let page;
  switch (route.page) {
    case 'map':
      page = <MapPage />;
      break;
    case 'cameras':
      page = <Cameras />;
      break;
    case 'site':
      page = <SitePage key={route.id} id={route.id} />;
      break;
    case 'alerts':
      page = <Alerts />;
      break;
    default:
      page = <Dashboard />;
  }

  const app = (
    <div className={rootCls} style={varsStyle(vars)}>
      {route.page === 'login' ? (
        <Login />
      ) : (
        <div className="shell">
          {isPhone ? <PhoneTopbar /> : <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />}
          <main className="main" ref={mainRef}>
            <div ref={contentRef}>
              <div key={route.page === 'site' ? `site-${route.id}` : route.page} className="page-anim">
                {page}
              </div>
            </div>
          </main>
          {isPhone && <BottomNav />}
        </div>
      )}
      {route.page !== 'login' && <AlertDrawerHost />}
      {modal?.kind === 'profile' && <ProfileModal />}
      {modal?.kind === 'add' && <CameraFormModal />}
      {modal?.kind === 'edit' && <CameraFormModal key={modal.siteId} siteId={modal.siteId} />}
      {modal?.kind === 'lightbox' && <Lightbox info={modal.info} />}
    </div>
  );

  return (
    <Ctx.Provider value={ctx}>
      {settings.device === 'phone' && !narrow ? (
        <div className="stage">
          <div className="phone-frame">{app}</div>
        </div>
      ) : (
        app
      )}
      <SettingsPanel settings={settings} onChange={setSettings} />
    </Ctx.Provider>
  );
}
