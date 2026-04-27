import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from './LoginPage';

const loginMock = vi.fn();
const getMeMock = vi.fn();
const navigateMock = vi.fn();
const setAuthMock = vi.fn();

vi.mock('../lib/api', () => ({
  login: (...args: unknown[]) => loginMock(...args),
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
    getMeMock.mockReset();
    navigateMock.mockReset();
    setAuthMock.mockReset();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('submits email+password and navigates on success (remember=false by default)', async () => {
    loginMock.mockResolvedValue({ access_token: 'tok' });
    const user = { id: 1, email: 'u@x.test', full_name: 'U' };
    getMeMock.mockResolvedValue(user);
    const ue = userEvent.setup();
    renderLogin();

    await ue.type(screen.getByLabelText('Email'), 'u@x.test');
    await ue.type(screen.getByLabelText('Пароль'), 'pw12345');
    await ue.click(screen.getByRole('button', { name: 'Войти' }));

    expect(loginMock).toHaveBeenCalledWith('u@x.test', 'pw12345');
    expect(setAuthMock).toHaveBeenCalledWith('tok', user, false);
    expect(navigateMock).toHaveBeenCalledWith('/');
  });

  it('passes remember=true to setAuth when "Запомнить меня" is checked', async () => {
    loginMock.mockResolvedValue({ access_token: 'tok' });
    const user = { id: 1, email: 'u@x.test', full_name: 'U' };
    getMeMock.mockResolvedValue(user);
    const ue = userEvent.setup();
    renderLogin();

    await ue.type(screen.getByLabelText('Email'), 'u@x.test');
    await ue.type(screen.getByLabelText('Пароль'), 'pw12345');
    await ue.click(screen.getByLabelText('Запомнить меня'));
    await ue.click(screen.getByRole('button', { name: 'Войти' }));

    expect(setAuthMock).toHaveBeenCalledWith('tok', user, true);
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

  it('keeps email but clears password after a failed login', async () => {
    loginMock.mockRejectedValue(new Error('Invalid credentials'));
    const user = userEvent.setup();
    renderLogin();

    const emailInput = screen.getByLabelText('Email') as HTMLInputElement;
    const passwordInput = screen.getByLabelText('Пароль') as HTMLInputElement;

    await user.type(emailInput, 'u@x.test');
    await user.type(passwordInput, 'wrong');
    await user.click(screen.getByRole('button', { name: 'Войти' }));

    await screen.findByText('Invalid credentials');

    expect(emailInput.value).toBe('u@x.test');
    expect(passwordInput.value).toBe('');
  });

  it('toggles password visibility when the eye button is clicked', async () => {
    const user = userEvent.setup();
    renderLogin();

    const passwordInput = screen.getByLabelText('Пароль') as HTMLInputElement;
    expect(passwordInput.type).toBe('password');

    const showButton = screen.getByRole('button', { name: 'Показать пароль' });
    await user.click(showButton);

    expect(passwordInput.type).toBe('text');
    expect(screen.getByRole('button', { name: 'Скрыть пароль' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Скрыть пароль' }));
    expect(passwordInput.type).toBe('password');
  });
});
