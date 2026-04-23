import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from './LoginPage';

// Mock API and router navigate — we only want to verify the form wiring.
const loginMock = vi.fn();
const registerMock = vi.fn();
const getMeMock = vi.fn();
const navigateMock = vi.fn();
const setAuthMock = vi.fn();

vi.mock('../lib/api', () => ({
  login: (...args: unknown[]) => loginMock(...args),
  register: (...args: unknown[]) => registerMock(...args),
  getMe: () => getMeMock(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigateMock };
});

vi.mock('../lib/store', () => ({
  useAuthStore: (selector: (s: { setAuth: typeof setAuthMock }) => unknown) =>
    selector({ setAuth: setAuthMock }),
}));

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    loginMock.mockReset();
    registerMock.mockReset();
    getMeMock.mockReset();
    navigateMock.mockReset();
    setAuthMock.mockReset();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('defaults to login mode and submits email+password only', async () => {
    loginMock.mockResolvedValue({ access_token: 'tok' });
    getMeMock.mockResolvedValue({ id: 1, email: 'u@x.test', full_name: 'U' });
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'u@x.test');
    await user.type(screen.getByLabelText('Пароль'), 'pw12345');
    await user.click(screen.getByRole('button', { name: 'Войти' }));

    expect(loginMock).toHaveBeenCalledWith('u@x.test', 'pw12345');
    expect(registerMock).not.toHaveBeenCalled();
  });

  it('switches to register mode and sends organization_name when "create org" is chosen', async () => {
    registerMock.mockResolvedValue({ id: 1, email: 'a@x.test' });
    loginMock.mockResolvedValue({ access_token: 'tok' });
    getMeMock.mockResolvedValue({ id: 1, email: 'a@x.test', full_name: 'A' });
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }));
    await user.type(screen.getByLabelText('Имя'), 'Anna');
    await user.type(screen.getByLabelText('Email'), 'a@x.test');
    await user.type(screen.getByLabelText('Пароль'), 'pw12345678');
    // "Создать организацию" is the default choice after switching to register.
    await user.type(screen.getByLabelText('Название организации'), 'Acme');
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }));

    expect(registerMock).toHaveBeenCalledWith({
      email: 'a@x.test',
      password: 'pw12345678',
      full_name: 'Anna',
      organization_name: 'Acme',
    });
  });

  it('sends join_code instead when "join by code" is chosen', async () => {
    registerMock.mockResolvedValue({ id: 2, email: 'j@x.test' });
    loginMock.mockResolvedValue({ access_token: 'tok' });
    getMeMock.mockResolvedValue({ id: 2, email: 'j@x.test', full_name: 'J' });
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }));
    await user.type(screen.getByLabelText('Имя'), 'Joiner');
    await user.type(screen.getByLabelText('Email'), 'j@x.test');
    await user.type(screen.getByLabelText('Пароль'), 'pw12345678');
    await user.click(screen.getByRole('button', { name: 'По коду приглашения' }));
    await user.type(screen.getByLabelText('Код приглашения'), 'abc123XYZ');
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }));

    expect(registerMock).toHaveBeenCalledWith({
      email: 'j@x.test',
      password: 'pw12345678',
      full_name: 'Joiner',
      join_code: 'abc123XYZ',
    });
  });

  it('surfaces API errors in the form', async () => {
    loginMock.mockRejectedValue(new Error('Invalid credentials'));
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'u@x.test');
    await user.type(screen.getByLabelText('Пароль'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument();
  });
});
