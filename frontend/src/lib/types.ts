export type SiteStatus = 'clean' | 'overflow' | 'contamination';
export type AlertLevel = 'overflow' | 'contamination';
export type AlertStatus = 'new' | 'accepted' | 'resolved';
export type ResolutionReason =
  | 'confirmed_and_cleared'
  | 'false_alarm'
  | 'resolved_externally';

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_admin: boolean;
  organization_id: number | null;
  avatar_path: string | null;
  telegram_connected: boolean;
  max_connected: boolean;
}

// Общая форма для обоих каналов уведомлений (Telegram и MAX).
export interface TelegramStatus {
  enabled: boolean;
  connected: boolean;
  link: string | null;
}

export interface Site {
  id: number;
  name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  status: SiteStatus;
  created_at: string;
  camera_count: number;
  last_checked: string | null;
  active_status: SiteStatus | null;
}

export interface Camera {
  id: number;
  site_id: number;
  site_name: string;
  name: string;
  rtsp_url: string;
  external_key: string | null;
  is_active: boolean;
  last_checked: string | null;
  created_at: string;
}

export interface Detection {
  id: number;
  class_name: string;
  confidence: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Snapshot {
  id: number;
  site_id: number;
  camera_id: number;
  image_path: string;
  taken_at: string;
  detections: Detection[];
}

export interface Alert {
  id: number;
  site_id: number;
  site_name: string;
  snapshot_id: number | null;
  level: AlertLevel;
  status: AlertStatus;
  resolution_reason: ResolutionReason | null;
  created_at: string;
  resolved_at: string | null;
}

export interface DashboardStats {
  total_sites: number;
  active_cameras: number;
  open_alerts: number;
  clean_percent: number;
  status_counts: Record<string, number>;
}

export interface ProblemsPoint {
  day: string;
  count: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface SiteCreate {
  name: string;
  address: string;
  latitude?: number | null;
  longitude?: number | null;
}

export interface CameraCreate {
  site_id: number;
  name: string;
  rtsp_url: string;
  external_key?: string | null;
}

export interface AlertsPage {
  items: Alert[];
  total: number;
}
