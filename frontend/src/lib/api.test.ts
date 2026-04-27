import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { login } from './api';

describe('api', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('login() rejects with the backend detail text on 401 instead of redirecting', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 401,
      ok: false,
      json: async () => ({ detail: 'Неверный email или пароль' }),
    });
    globalThis.fetch = fetchMock as typeof fetch;

    const hrefSetter = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        get href() {
          return originalLocation.href;
        },
        set href(value: string) {
          hrefSetter(value);
        },
      },
    });

    await expect(login('a@b.test', 'wrong')).rejects.toThrow('Неверный email или пароль');
    expect(hrefSetter).not.toHaveBeenCalled();

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });
});
