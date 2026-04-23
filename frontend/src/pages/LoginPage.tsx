import { useId, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { login, getMe, register } from '../lib/api';
import { useAuthStore } from '../lib/store';

type Mode = 'login' | 'register';
type OrgChoice = 'create' | 'join';

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [orgChoice, setOrgChoice] = useState<OrgChoice>('create');
  const [orgName, setOrgName] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const finishLogin = async (e: string, p: string) => {
    const { access_token } = await login(e, p);
    localStorage.setItem('token', access_token);
    const user = await getMe();
    setAuth(access_token, user);
    navigate('/');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await finishLogin(email, password);
      } else {
        const payload =
          orgChoice === 'create'
            ? { email, password, full_name: fullName, organization_name: orgName }
            : { email, password, full_name: fullName, join_code: joinCode };
        await register(payload);
        await finishLogin(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white rounded-2xl shadow-sm p-8 w-full max-w-sm border border-gray-100">
        <div className="text-center mb-6">
          <div className="inline-flex w-12 h-12 rounded-xl bg-gray-900 text-white items-center justify-center mb-3">
            <Trash2 size={22} />
          </div>
          <h1 className="text-xl font-bold tracking-tight">НЭКОБАК</h1>
          <p className="text-sm font-semibold text-gray-900 mt-3">Добро пожаловать!</p>
          <p className="text-xs text-gray-500 mt-1">
            {mode === 'login' ? 'Войдите или зарегистрируйтесь' : 'Создайте учётную запись'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === 'register' && (
            <Field label="Имя">
              {(id) => (
                <input
                  id={id}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                  required
                />
              )}
            </Field>
          )}
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
              <input
                id={id}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={mode === 'register' ? 8 : undefined}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                required
              />
            )}
          </Field>

          {mode === 'register' && (
            <>
              <div className="flex gap-2 text-sm pt-1">
                <ChoiceButton
                  active={orgChoice === 'create'}
                  onClick={() => setOrgChoice('create')}
                >
                  Создать организацию
                </ChoiceButton>
                <ChoiceButton active={orgChoice === 'join'} onClick={() => setOrgChoice('join')}>
                  По коду приглашения
                </ChoiceButton>
              </div>
              {orgChoice === 'create' ? (
                <Field label="Название организации">
                  {(id) => (
                    <input
                      id={id}
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      placeholder="ЖЭК №12"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
                      required
                    />
                  )}
                </Field>
              ) : (
                <Field label="Код приглашения">
                  {(id) => (
                    <input
                      id={id}
                      value={joinCode}
                      onChange={(e) => setJoinCode(e.target.value)}
                      placeholder="abc123XYZ"
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-400"
                      required
                    />
                  )}
                </Field>
              )}
            </>
          )}

          {mode === 'login' && (
            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input type="checkbox" className="rounded" /> Запомнить меня
              </label>
              <button type="button" className="text-sm text-sky-500 hover:underline">
                Забыли пароль?
              </button>
            </div>
          )}

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-sky-500 hover:bg-sky-600 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? '…' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login');
            setError('');
          }}
          className="w-full mt-3 border border-gray-200 text-gray-700 font-medium py-2.5 rounded-lg hover:bg-gray-50 text-sm"
        >
          {mode === 'login' ? 'Зарегистрироваться' : 'Уже есть аккаунт — войти'}
        </button>
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

function ChoiceButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
        active
          ? 'bg-gray-900 text-white border-gray-900'
          : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
      }`}
    >
      {children}
    </button>
  );
}
