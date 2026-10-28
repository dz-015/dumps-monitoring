import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Camera, Minus, Plus, Search, Trash, X } from 'lucide-react';
import { useApp, type LightboxInfo } from '../ctx';
import { usePresence } from '../hooks';
import { PickerMap } from '../components/maps';
import { Frame } from '../components/Frame';

function useEscape(onClose: () => void, active = true) {
  useEffect(() => {
    if (!active) return;
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [onClose, active]);
}

/**
 * Окно с плавным появлением и уходом. Закрытие сначала проигрывает анимацию,
 * потом сообщает наружу — поэтому onClose вызывается с задержкой.
 */
function Dialog({ title, width, onClose, children }: { title: string; width: number; onClose: () => void; children: (close: () => void) => ReactNode }) {
  const { isPhone } = useApp();
  const [open, setOpen] = useState(true);
  const { shown } = usePresence(open, 220);
  const close = () => {
    setOpen(false);
    setTimeout(onClose, 220);
  };
  useEscape(close, open);
  return (
    <div className={`overlay ${isPhone ? 'sheet' : ''} ${shown ? 'shown' : ''}`}>
      <button type="button" className="overlay-bg" aria-label="Закрыть" onClick={close} />
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title} style={{ width }} data-lenis-prevent>
        {isPhone && <div className="sheet-grip" />}
        <div className="dialog-head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn sm" onClick={close} aria-label="Закрыть">
            <X size={17} />
          </button>
        </div>
        {children(close)}
      </div>
    </div>
  );
}

export function ProfileModal() {
  const { user, setUserName, channels, toggleChannel, logout, setModal } = useApp();
  const [name, setName] = useState(user.name);
  const id = useId();
  const rows: { k: 'max' | 'tg'; name: string }[] = [
    { k: 'max', name: 'MAX' },
    { k: 'tg', name: 'Telegram' },
  ];
  return (
    <Dialog title="Профиль" width={420} onClose={() => setModal(null)}>
      {(close) => (
        <>
          <div className="profile-top">
            <button type="button" className="avatar lg" aria-label="Сменить аватар" title="Сменить аватар">
              {user.initials}
              <span className="avatar-edit">
                <Camera size={18} />
              </span>
            </button>
            <div>
              <b>{user.name}</b>
              <div className="muted small">{user.email}</div>
            </div>
          </div>
          <div className="field">
            <label htmlFor={id}>Имя</label>
            <input id={id} className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="section-label">Уведомления об оповещениях</div>
          <div className="rows">
            {rows.map(({ k, name: n }) => {
              const on = channels[k];
              return (
                <div key={k} className="row-line">
                  <span className="grow">
                    <b>{n}</b>
                    <span className="muted small">{on ? 'Подключено' : 'Не подключено'}</span>
                  </span>
                  <button type="button" className={`btn sm ${on ? 'btn-ghost' : 'btn-secondary'}`} onClick={() => toggleChannel(k)}>
                    {on ? 'Отключить' : 'Подключить'}
                  </button>
                </div>
              );
            })}
          </div>
          <div className="dialog-actions">
            <button type="button" className="btn btn-ghost danger" onClick={logout}>
              Выйти
            </button>
            <span className="grow" />
            <button type="button" className="btn btn-secondary" onClick={close}>
              Отмена
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setUserName(name.trim() || user.name);
                close();
              }}
            >
              Сохранить
            </button>
          </div>
        </>
      )}
    </Dialog>
  );
}

export function CameraFormModal({ siteId }: { siteId?: number }) {
  const { siteAny, saveSite, deleteSite, setModal, go, route } = useApp();
  const existing = siteId != null ? siteAny(siteId) : undefined;
  const [f, setF] = useState({
    name: existing?.name ?? '',
    rtsp: existing?.rtsp ?? '',
    address: existing?.address ?? '',
    lat: existing?.lat ?? null,
    lng: existing?.lng ?? null,
  });
  const [err, setErr] = useState('');
  const [confirmDel, setConfirmDel] = useState(false);
  const ids = { name: useId(), rtsp: useId(), addr: useId() };
  const upd = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setF({ ...f, [k]: e.target.value });
    setErr('');
  };

  return (
    <Dialog title={existing ? 'Изменить камеру' : 'Новая камера'} width={560} onClose={() => setModal(null)}>
      {(close) => {
        const submit = () => {
          if (!f.name.trim() || !f.rtsp.trim() || !f.address.trim()) return setErr('Заполните поля, отмеченные звёздочкой');
          if (f.lat == null || f.lng == null) return setErr('Укажите точку на карте');
          saveSite({ id: siteId, name: f.name.trim(), rtsp: f.rtsp.trim(), address: f.address.trim(), lat: f.lat, lng: f.lng });
          close();
        };
        return (
          <div className="form">
            <div className="field">
              <label htmlFor={ids.name}>Название площадки *</label>
              <input id={ids.name} className="input" value={f.name} onChange={upd('name')} />
            </div>
            <div className="field">
              <label htmlFor={ids.addr}>Адрес *</label>
              <div className="input-wrap">
                <Search size={15} className="input-icon" />
                <input id={ids.addr} className="input with-icon" value={f.address} onChange={upd('address')} />
              </div>
            </div>
            <div className="field">
              <span className="field-label">Точка на карте *</span>
              <PickerMap
                lat={f.lat}
                lng={f.lng}
                onPick={(lat, lng) => {
                  setF({ ...f, lat, lng });
                  setErr('');
                }}
              />
              <span className="muted small mono">{f.lat != null && f.lng != null ? `${f.lat.toFixed(5)}, ${f.lng.toFixed(5)}` : 'Точка не выбрана'}</span>
            </div>
            <div className="field">
              <label htmlFor={ids.rtsp}>RTSP-ссылка *</label>
              <input id={ids.rtsp} className="input mono" value={f.rtsp} onChange={upd('rtsp')} placeholder="rtsp://login:password@IP:554/path" />
            </div>
            {err && <div className="form-error">{err}</div>}
            <div className="dialog-actions">
              {existing &&
                (confirmDel ? (
                  <span className="confirm-inline">
                    Удалить вместе с историей?
                    <button
                      type="button"
                      className="btn sm btn-danger"
                      onClick={() => {
                        deleteSite(existing.id);
                        close();
                        if (route.page === 'site') go('/cameras');
                      }}
                    >
                      Удалить
                    </button>
                    <button type="button" className="btn sm btn-ghost" onClick={() => setConfirmDel(false)}>
                      Нет
                    </button>
                  </span>
                ) : (
                  <button type="button" className="btn btn-ghost danger" onClick={() => setConfirmDel(true)}>
                    <Trash size={15} /> Удалить
                  </button>
                ))}
              <span className="grow" />
              <button type="button" className="btn btn-secondary" onClick={close}>
                Отмена
              </button>
              <button type="button" className="btn btn-primary" onClick={submit}>
                {existing ? 'Сохранить' : 'Добавить'}
              </button>
            </div>
          </div>
        );
      }}
    </Dialog>
  );
}

const MAX_ZOOM = 5;
type View = { z: number; x: number; y: number };

/**
 * Просмотр снимка. Колесо приближает к точке под курсором; масштаб догоняет цель
 * плавно (каждый кадр — часть оставшегося пути). Прокрутка «от себя» при
 * масштабе 100% закрывает просмотр.
 */
export function Lightbox({ info }: { info: LightboxInfo }) {
  const { setModal } = useApp();
  const [open, setOpen] = useState(true);
  const { shown } = usePresence(open, 220);
  const [pct, setPct] = useState(100);
  const [boxes, setBoxes] = useState(true);
  const stage = useRef<HTMLDivElement>(null);
  const layer = useRef<HTMLDivElement>(null);
  const target = useRef<View>({ z: 1, x: 0, y: 0 });
  const cur = useRef<View>({ z: 1, x: 0, y: 0 });
  const raf = useRef(0);
  const atMinSince = useRef(0);
  const drag = useRef<{ x: number; y: number } | null>(null);
  const closing = useRef(false);

  const close = () => {
    if (closing.current) return;
    closing.current = true;
    setOpen(false);
    setTimeout(() => setModal(null), 220);
  };
  useEscape(close, open);

  const paint = () => {
    const v = cur.current;
    if (layer.current) layer.current.style.transform = `translate(${v.x}px, ${v.y}px) scale(${v.z})`;
  };
  const tick = () => {
    const c = cur.current;
    const t = target.current;
    const k = 0.22;
    c.z += (t.z - c.z) * k;
    c.x += (t.x - c.x) * k;
    c.y += (t.y - c.y) * k;
    const done = Math.abs(t.z - c.z) < 0.001 && Math.abs(t.x - c.x) < 0.2 && Math.abs(t.y - c.y) < 0.2;
    if (done) Object.assign(c, t);
    paint();
    raf.current = done ? 0 : requestAnimationFrame(tick);
  };
  const animate = () => {
    if (!raf.current) raf.current = requestAnimationFrame(tick);
  };

  /** Не даём увести снимок за край: при масштабе z сдвиг не больше (z−1)·половина размера. */
  const clamp = (v: View): View => {
    const r = stage.current?.getBoundingClientRect();
    if (!r) return v;
    const mx = ((v.z - 1) * r.width) / 2;
    const my = ((v.z - 1) * r.height) / 2;
    return { z: v.z, x: Math.max(-mx, Math.min(mx, v.x)), y: Math.max(-my, Math.min(my, v.y)) };
  };

  /** Новый масштаб так, чтобы точка (px, py) — смещение от центра сцены — осталась на месте. */
  const zoomTo = (z: number, px = 0, py = 0, instant = false) => {
    const t = target.current;
    const nz = Math.min(MAX_ZOOM, Math.max(1, z));
    const next = clamp({ z: nz, x: px - ((px - t.x) * nz) / t.z, y: py - ((py - t.y) * nz) / t.z });
    if (t.z > 1 && nz === 1) atMinSince.current = performance.now();
    target.current = next;
    setPct(Math.round(nz * 100));
    if (instant) {
      cur.current = { ...next };
      paint();
    } else animate();
  };

  const fromCenter = (e: { clientX: number; clientY: number }) => {
    const r = stage.current!.getBoundingClientRect();
    return [e.clientX - r.left - r.width / 2, e.clientY - r.top - r.height / 2] as const;
  };

  const onWheel = (deltaY: number, deltaMode: number, clientX: number, clientY: number) => {
    const z = target.current.z;
    // Отдаление при 100%: закрываем, но не от «хвоста» той же прокрутки,
    // которая только что довела масштаб до 100%.
    if (deltaY > 0 && z <= 1) {
      if (performance.now() - atMinSince.current > 250) close();
      return;
    }
    const delta = deltaMode === 1 ? deltaY * 33 : deltaY;
    const [px, py] = fromCenter({ clientX, clientY });
    zoomTo(z * Math.exp(-delta * 0.0025), px, py);
  };
  const wheelRef = useRef(onWheel);
  wheelRef.current = onWheel;

  // Колесо — нативный слушатель: React вешает wheel пассивным, и preventDefault не сработал бы.
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const onNative = (e: WheelEvent) => {
      e.preventDefault();
      wheelRef.current(e.deltaY, e.deltaMode, e.clientX, e.clientY);
    };
    // Та же прокрутка, начатая над кадром на странице (см. useWheelToOpen).
    const onForwarded = (e: Event) => {
      const d = (e as CustomEvent).detail;
      wheelRef.current(d.deltaY, d.deltaMode, d.clientX, d.clientY);
    };
    el.addEventListener('wheel', onNative, { passive: false });
    window.addEventListener('lb-wheel', onForwarded);
    // Открыли колесом — сразу приближаем к той точке, над которой был курсор.
    if (info.zoomAt) {
      const r = el.getBoundingClientRect();
      zoomTo(1.4, (info.zoomAt[0] - 0.5) * r.width, (info.zoomAt[1] - 0.5) * r.height);
    }
    return () => {
      el.removeEventListener('wheel', onNative);
      window.removeEventListener('lb-wheel', onForwarded);
      cancelAnimationFrame(raf.current);
      raf.current = 0; // иначе после повторного монтирования (StrictMode) анимация не запустится
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`lightbox ${shown ? 'shown' : ''}`} role="dialog" aria-modal="true" aria-label="Просмотр снимка" data-lenis-prevent>
      <div className="lb-top">
        <span>{info.caption}</span>
        <button type="button" className="lb-btn" onClick={close} aria-label="Закрыть">
          <X size={20} />
        </button>
      </div>
      <div
        ref={stage}
        className="lb-stage"
        onDoubleClick={(e) => {
          const [px, py] = fromCenter(e);
          zoomTo(target.current.z > 1 ? 1 : 2.5, px, py);
        }}
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY };
          (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (!drag.current || target.current.z <= 1) return;
          const dx = e.clientX - drag.current.x;
          const dy = e.clientY - drag.current.y;
          drag.current = { x: e.clientX, y: e.clientY };
          const t = target.current;
          target.current = clamp({ z: t.z, x: t.x + dx, y: t.y + dy });
          cur.current = { ...cur.current, x: target.current.x, y: target.current.y };
          paint();
        }}
        onPointerUp={() => (drag.current = null)}
        style={{ cursor: pct > 100 ? 'grab' : 'zoom-in' }}
      >
        <div className="lb-zoom" ref={layer}>
          <Frame frame={info.frame} boxes={boxes} labels="all" />
        </div>
      </div>
      <div className="lb-bar">
        <label className="switch dark">
          <input type="checkbox" checked={boxes} onChange={(e) => setBoxes(e.target.checked)} />
          <span className="switch-track" />
          Рамки
        </label>
        <span className="lb-sep" />
        <button type="button" className="lb-btn" disabled={pct <= 100} onClick={() => zoomTo(target.current.z / 1.5)} aria-label="Отдалить">
          <Minus size={17} />
        </button>
        <span className="lb-pct">{pct}%</span>
        <button type="button" className="lb-btn" disabled={pct >= MAX_ZOOM * 100} onClick={() => zoomTo(target.current.z * 1.5)} aria-label="Приблизить">
          <Plus size={17} />
        </button>
      </div>
    </div>
  );
}
