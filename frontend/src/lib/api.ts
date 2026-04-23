import type {
  Alert,
  AlertsPage,
  Camera,
  CameraCreate,
  DashboardStats,
  LoginResponse,
  ProblemsPoint,
  Site,
  SiteCreate,
  Snapshot,
  User,
} from './types';

const BASE = '/api';

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {
    ...((opts.headers as Record<string, string>) || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────
export const login = (email: string, password: string) =>
  request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });

export type RegisterPayload =
  | { email: string; password: string; full_name: string; organization_name: string }
  | { email: string; password: string; full_name: string; join_code: string };

export const register = (payload: RegisterPayload) =>
  request<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const getMe = () => request<User>('/auth/me');

// ── Dashboard ─────────────────────────────────────────────────────────
export const getDashboardStats = () => request<DashboardStats>('/dashboard/stats');
export const getProblemsWeek = () => request<ProblemsPoint[]>('/dashboard/problems-week');
export const getProblemsMonth = () => request<ProblemsPoint[]>('/dashboard/problems-month');

// ── Sites ─────────────────────────────────────────────────────────────
export const getSites = () => request<Site[]>('/sites');
export const getSite = (id: number) => request<Site>(`/sites/${id}`);
export const createSite = (data: SiteCreate) =>
  request<Site>('/sites', { method: 'POST', body: JSON.stringify(data) });
export const updateSite = (id: number, data: Partial<SiteCreate>) =>
  request<Site>(`/sites/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const deleteSite = (id: number) => request<void>(`/sites/${id}`, { method: 'DELETE' });
export const getSiteSnapshots = (id: number, limit = 20) =>
  request<Snapshot[]>(`/sites/${id}/snapshots?limit=${limit}`);
export const getSiteAlerts = (id: number) => request<Alert[]>(`/sites/${id}/alerts`);

// ── Cameras ───────────────────────────────────────────────────────────
export const getCameras = () => request<Camera[]>('/cameras');
export const createCamera = (data: CameraCreate) =>
  request<Camera>('/cameras', { method: 'POST', body: JSON.stringify(data) });
export const deleteCamera = (id: number) => request<void>(`/cameras/${id}`, { method: 'DELETE' });

// ── Alerts ────────────────────────────────────────────────────────────
export interface AlertsQuery {
  level?: string;
  status?: string;
  page?: number;
  per_page?: number;
}

export const getAlerts = (params: AlertsQuery = {}) => {
  const sp = new URLSearchParams();
  if (params.level) sp.set('level', params.level);
  if (params.status) sp.set('status', params.status);
  if (params.page) sp.set('page', String(params.page));
  if (params.per_page) sp.set('per_page', String(params.per_page));
  return request<AlertsPage>(`/alerts?${sp}`);
};

export const updateAlert = (id: number, status: string) =>
  request<Alert>(`/alerts/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
