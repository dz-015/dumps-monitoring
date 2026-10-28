import { createContext, useContext } from 'react';
import type { Alert, FrameInfo, Reason, Site, Status } from './data';
import type { Settings } from './theme';

export type SiteView = Site & { st: Status; hasCoords: boolean };

export type Route =
  | { page: 'login' }
  | { page: 'dashboard' }
  | { page: 'map' }
  | { page: 'cameras' }
  | { page: 'site'; id: number }
  | { page: 'alerts' };

/** zoomAt — доли кадра (0..1), куда сразу приблизить: просмотр открыт колесом. */
export type LightboxInfo = { frame: FrameInfo; caption: string; zoomAt?: [number, number] };

export type Modal =
  | null
  | { kind: 'profile' }
  | { kind: 'add' }
  | { kind: 'edit'; siteId: number }
  | { kind: 'lightbox'; info: LightboxInfo };

export type AppCtx = {
  settings: Settings;
  isPhone: boolean;
  route: Route;
  go: (path: string) => void;

  sites: SiteView[];
  alerts: Alert[];
  siteAny: (id: number) => Site | undefined;
  loading: boolean;
  failed: boolean;
  retry: () => void;

  modal: Modal;
  setModal: (m: Modal) => void;

  /** Какое оповещение раскрыто на странице «Оповещения». */
  openAlert: number | null;
  setOpenAlert: (id: number | null) => void;

  acceptAlert: (id: number) => void;
  resolveAlert: (id: number, reason: Reason) => void;
  saveSite: (patch: Partial<Site> & { id?: number }) => void;
  deleteSite: (id: number) => void;

  user: { name: string; email: string; initials: string };
  setUserName: (name: string) => void;
  channels: { max: boolean; tg: boolean };
  toggleChannel: (k: 'max' | 'tg') => void;
  logout: () => void;
  login: () => void;
};

export const Ctx = createContext<AppCtx | null>(null);

export function useApp(): AppCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useApp вне провайдера');
  return c;
}
