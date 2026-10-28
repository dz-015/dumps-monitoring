import { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { MapContainer, Marker } from 'react-leaflet';
import { useApp } from '../ctx';
import { baseAlerts, baseSites, MAP_CENTER, statusOf } from '../data';
import { useStatusColors } from '../hooks';
import { AutoResize, pinIcon, Tiles } from '../components/maps';
import { Logo, Wordmark } from '../components/ui';

export default function Login() {
  const { login, isPhone } = useApp();
  const colors = useStatusColors();
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(true);
  const [err, setErr] = useState('');
  const emailId = useId();
  const pwId = useId();
  const alerts = baseAlerts();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !pw) {
      setErr('Введите email и пароль');
      return;
    }
    login();
  };

  return (
    <div className="login">
      <div className="login-form-wrap">
        <form className="login-form" onSubmit={submit} noValidate>
          <div className="login-brand">
            <Logo size={36} />
            <Wordmark size={17} />
          </div>
          <div>
            <h1>Вход</h1>
            <p className="muted">Аккаунт вашей организации</p>
          </div>
          <div className="field">
            <label htmlFor={emailId}>Email</label>
            <input id={emailId} type="email" className="input" value={email} placeholder="name@organization.ru" onChange={(e) => { setEmail(e.target.value); setErr(''); }} autoComplete="username" />
          </div>
          <div className="field">
            <label htmlFor={pwId}>Пароль</label>
            <div className="input-wrap">
              <input id={pwId} type={show ? 'text' : 'password'} className="input with-btn" value={pw} onChange={(e) => { setPw(e.target.value); setErr(''); }} autoComplete="current-password" />
              <button type="button" className="input-btn" onClick={() => setShow((v) => !v)} aria-label={show ? 'Скрыть пароль' : 'Показать пароль'}>
                {show ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </div>
          <label className="check">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
            Запомнить меня
          </label>
          {err && <div className="form-error">{err}</div>}
          <button type="submit" className="btn btn-primary btn-block">
            Войти
          </button>
          <p className="login-hint">Макет: подойдут любые email и пароль</p>
        </form>
      </div>
      {!isPhone && (
        <div className="login-side">
          <MapContainer center={MAP_CENTER} zoom={14} zoomControl={false} dragging={false} scrollWheelZoom={false} doubleClickZoom={false} attributionControl={false} style={{ width: '100%', height: '100%' }}>
            <Tiles />
            {baseSites()
              .filter((s) => s.lat != null && s.lng != null)
              .map((s) => (
                <Marker key={s.id} position={[s.lat!, s.lng!]} icon={pinIcon(colors[statusOf(alerts, s.id)])} />
              ))}
            <AutoResize />
          </MapContainer>
        </div>
      )}
    </div>
  );
}
