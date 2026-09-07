import { useId, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff } from 'lucide-react';
import { login, getMe } from '../lib/api';
import { useAuthStore } from '../lib/store';
import { clearToken, setToken } from '../lib/tokenStorage';
import { brandName, logoSrc as logo } from '../lib/logo';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { access_token } = await login(email.trim(), password);
      setToken(access_token, remember);
      try {
        const user = await getMe();
        setAuth(access_token, user, remember);
        navigate('/');
      } catch (meErr) {
        clearToken();
        throw meErr;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
      setPassword('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white rounded-2xl shadow-sm p-8 w-full max-w-sm border border-gray-100">
        <div className="flex flex-col items-center text-center mb-6">
          <img src={logo} alt="ТКО | Мониторинг" className="w-12 h-12 mb-3" />
          <h1 className="text-xl font-bold tracking-tight">{brandName}</h1>
          <h2 className="text-2xl font-semibold text-gray-900 mt-4">Добро пожаловать</h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <Field label="Email">
            {(id) => (
              <input
                id={id}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                required
              />
            )}
          </Field>
          <Field label="Пароль">
            {(id) => (
              <div className="relative">
                <input
                  id={id}
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  className="absolute inset-y-0 right-0 px-3 flex items-center text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            )}
          </Field>

          <div className="flex items-center pt-1">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="rounded"
              />
              Запомнить меня
            </label>
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-sky-500 hover:bg-sky-600 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? '…' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: (id: string) => React.ReactNode;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm text-gray-700 mb-1">
        {label}
      </label>
      {children(id)}
    </div>
  );
}
