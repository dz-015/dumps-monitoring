import { create } from 'zustand';
import type { User } from './types';
import { clearToken, getToken, setToken } from './tokenStorage';

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User, remember: boolean) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: getToken(),
  user: null,
  setAuth: (token, user, remember) => {
    setToken(token, remember);
    set({ token, user });
  },
  setUser: (user) => set({ user }),
  logout: () => {
    clearToken();
    set({ token: null, user: null });
  },
}));
