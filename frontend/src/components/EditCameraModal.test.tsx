import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import EditCameraModal from './EditCameraModal';
import type { Camera, Site } from '../lib/types';

const site: Site = {
  id: 1,
  name: 'Площадка ЦУМ',
  address: 'ул. Карла Маркса, 12',
  latitude: 44.951,
  longitude: 34.1,
  status: 'clean',
  created_at: '2026-01-01T00:00:00+00:00',
  camera_count: 1,
  last_checked: null,
  active_status: 'clean',
};

const camera: Camera = {
  id: 5,
  site_id: 1,
  site_name: 'Площадка ЦУМ',
  name: 'Камера 1',
  rtsp_url: 'rtsp://cam.example/stream',
  external_key: null,
  is_active: true,
  last_checked: null,
  created_at: '2026-01-01T00:00:00+00:00',
};

describe('EditCameraModal', () => {
  it('prefills the existing RTSP url (BUG-24 guard)', () => {
    render(
      <EditCameraModal
        site={site}
        camera={camera}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onDeleted={vi.fn()}
      />
    );
    expect(screen.getByDisplayValue('rtsp://cam.example/stream')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Площадка ЦУМ')).toBeInTheDocument();
  });

  it('renders with empty RTSP for a site without a camera', () => {
    render(
      <EditCameraModal
        site={site}
        camera={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onDeleted={vi.fn()}
      />
    );
    expect(screen.queryByDisplayValue('rtsp://cam.example/stream')).not.toBeInTheDocument();
  });
});
