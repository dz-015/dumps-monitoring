import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Layout from './Layout';

let mockState: { token: string | null; user: unknown; logout: () => void } = {
  token: null,
  user: null,
  logout: vi.fn(),
};

vi.mock('../lib/store', () => ({
  useAuthStore: () => mockState,
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<div>Dash</div>} />
          <Route path="/map" element={<div>Map</div>} />
          <Route path="/cameras" element={<div>Cams</div>} />
          <Route path="/alerts" element={<div>Alerts</div>} />
        </Route>
        <Route path="/login" element={<div>Login screen</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('Layout', () => {
  beforeEach(() => {
    mockState = { token: null, user: null, logout: vi.fn() };
  });

  it('redirects to /login when no token is present', () => {
    renderAt('/');
    expect(screen.getByText('Login screen')).toBeInTheDocument();
  });

  it('renders exactly 4 primary nav items when authenticated', () => {
    mockState = {
      token: 'tok',
      user: { full_name: 'Ivan', email: 'i@x.test' },
      logout: vi.fn(),
    };
    renderAt('/');
    const expected = ['Панель управления', 'Карта', 'Камеры', 'Оповещения'];
    for (const label of expected) {
      expect(screen.getByRole('link', { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(screen.queryByRole('link', { name: /Площадки/ })).toBeNull();
  });

  it('marks the active nav item based on the URL', () => {
    mockState = {
      token: 'tok',
      user: { full_name: 'Ivan', email: 'i@x.test' },
      logout: vi.fn(),
    };
    renderAt('/cameras');
    const camerasLink = screen.getByRole('link', { name: /Камеры/ });
    expect(camerasLink.className).toMatch(/bg-gray-100/);
  });

  it('shows the user full name and email in the footer', () => {
    mockState = {
      token: 'tok',
      user: { full_name: 'Иван Иванович', email: 'ivan@test.local' },
      logout: vi.fn(),
    };
    renderAt('/');
    expect(screen.getByText('Иван Иванович')).toBeInTheDocument();
    expect(screen.getByText('ivan@test.local')).toBeInTheDocument();
  });
});
