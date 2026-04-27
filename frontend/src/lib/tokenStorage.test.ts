import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { clearToken, getToken, setToken } from './tokenStorage';

describe('tokenStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('getToken returns null when neither storage has a token', () => {
    expect(getToken()).toBeNull();
  });

  it('getToken returns the localStorage value when present', () => {
    localStorage.setItem('token', 'abc');
    expect(getToken()).toBe('abc');
  });

  it('getToken falls back to sessionStorage when localStorage is empty', () => {
    sessionStorage.setItem('token', 'xyz');
    expect(getToken()).toBe('xyz');
  });

  it('setToken(t, true) writes to localStorage and clears sessionStorage', () => {
    sessionStorage.setItem('token', 'old');
    setToken('new', true);
    expect(localStorage.getItem('token')).toBe('new');
    expect(sessionStorage.getItem('token')).toBeNull();
  });

  it('setToken(t, false) writes to sessionStorage and clears localStorage', () => {
    localStorage.setItem('token', 'old');
    setToken('new', false);
    expect(sessionStorage.getItem('token')).toBe('new');
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('clearToken wipes both storages', () => {
    localStorage.setItem('token', 'a');
    sessionStorage.setItem('token', 'b');
    clearToken();
    expect(localStorage.getItem('token')).toBeNull();
    expect(sessionStorage.getItem('token')).toBeNull();
  });
});
