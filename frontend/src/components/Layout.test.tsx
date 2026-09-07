import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
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
    const sidebar = screen.getByRole('navigation', { name: 'Основная навигация' });
    const expected = ['Панель управления', 'Карта', 'Камеры', 'Оповещения'];
    for (const label of expected) {
      expect(within(sidebar).getByRole('link', { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(within(sidebar).queryByRole('link', { name: /Площадки/ })).toBeNull();
  });

  it('renders a mobile bottom bar with the same 4 links plus profile', () => {
    mockState = {
      token: 'tok',
      user: { full_name: 'Ivan', email: 'i@x.test' },
      logout: vi.fn(),
    };
    renderAt('/');
    const bottom = screen.getByRole('navigation', { name: 'Нижняя навигация' });
    expect(within(bottom).getAllByRole('link')).toHaveLength(4);
    expect(within(bottom).getByRole('button', { name: /Профиль/ })).toBeInTheDocument();
    // Скрыта на десктопе, видна на мобильном.
    expect(bottom.className).toMatch(/md:hidden/);
  });

  it('marks the active nav item based on the URL', () => {
    mockState = {
      token: 'tok',
      user: { full_name: 'Ivan', email: 'i@x.test' },
      logout: vi.fn(),
    };
    renderAt('/cameras');
    const sidebar = screen.getByRole('navigation', { name: 'Основная навигация' });
    const camerasLink = within(sidebar).getByRole('link', { name: /Камеры/ });
    expect(camerasLink.className).toMatch(/bg-gray-100/);
    const bottom = screen.getByRole('navigation', { name: 'Нижняя навигация' });
    const bottomCameras = within(bottom).getByRole('link', { name: /Камеры/ });
    expect(bottomCameras.className).toMatch(/text-sky-600/);
  });

  it('hides nav labels when sidebar is collapsed and persists across renders', async () => {
    mockState = {
      token: 'tok',
      user: { full_name: 'Ivan', email: 'i@x.test' },
      logout: vi.fn(),
    };
    const ue = userEvent.setup();
    const { unmount } = renderAt('/');
    const sidebar = () => screen.getByRole('navigation', { name: 'Основная навигация' });

    expect(within(sidebar()).getByText('Камеры')).toBeInTheDocument();

    await ue.click(screen.getByRole('button', { name: 'Свернуть меню' }));
    expect(within(sidebar()).queryByText('Камеры')).toBeNull();
    expect(localStorage.getItem('sidebar-collapsed')).toBe('1');

    unmount();
    renderAt('/');
    expect(within(sidebar()).queryByText('Камеры')).toBeNull();
    expect(screen.getByRole('button', { name: 'Развернуть меню' })).toBeInTheDocument();
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
