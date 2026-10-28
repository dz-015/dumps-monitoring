import { useState, type ReactNode } from 'react';
import { Check, Copy, Monitor, Moon, RotateCcw, SlidersHorizontal, Smartphone, Sun, X } from 'lucide-react';
import { DEFAULTS, FONTS, PALETTES, PRIMARY_SWATCHES, buildVars, varsAsCss, type PaletteKey, type Settings } from '../theme';

// Панель настройки макета. Она не часть продукта — поэтому своё нейтральное
// оформление, не зависящее от выбранной темы.

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="tp-row">
      <div className="tp-label">{label}</div>
      {children}
    </div>
  );
}

function Seg<T extends string>({ value, options, onChange }: { value: T; options: { v: T; label: ReactNode }[]; onChange: (v: T) => void }) {
  return (
    <div className="tp-seg">
      {options.map((o) => (
        <button key={o.v} type="button" aria-pressed={value === o.v} className={value === o.v ? 'on' : ''} onClick={() => onChange(o.v)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Swatches({ value, options, onChange, name }: { value: string; options: string[]; onChange: (v: string) => void; name: string }) {
  const custom = !options.some((o) => o.toLowerCase() === value.toLowerCase());
  return (
    <div className="tp-swatches">
      {options.map((c) => (
        <button key={c} type="button" aria-label={`${name}: ${c}`} aria-pressed={value.toLowerCase() === c.toLowerCase()} className={`tp-swatch ${value.toLowerCase() === c.toLowerCase() ? 'on' : ''}`} style={{ background: c }} onClick={() => onChange(c)} />
      ))}
      <label className={`tp-swatch tp-custom ${custom ? 'on' : ''}`} style={custom ? { background: value } : undefined} title="Свой цвет">
        <input type="color" value={value} onChange={(e) => onChange(e.target.value.toUpperCase())} aria-label={`${name}: свой цвет`} />
        {!custom && <span>+</span>}
      </label>
      <code className="tp-hex">{value.toUpperCase()}</code>
    </div>
  );
}

export function SettingsPanel({ settings, onChange }: { settings: Settings; onChange: (s: Settings) => void }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => onChange({ ...settings, [k]: v });

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(varsAsCss(buildVars(settings)));
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* буфер обмена недоступен — молча ничего не делаем */
    }
  };

  if (!open) {
    return (
      <button type="button" className="tp-fab" onClick={() => setOpen(true)}>
        <SlidersHorizontal size={18} /> Настройки макета
      </button>
    );
  }

  return (
    <aside className="tool-panel" aria-label="Настройки макета">
      <div className="tp-head">
        <b>Настройки макета</b>
        <button type="button" className="tp-close" aria-label="Закрыть настройки" onClick={() => setOpen(false)}>
          <X size={18} />
        </button>
      </div>
      <div className="tp-body">
        <div className="tp-section">Экран</div>
        <Row label="Устройство">
          <Seg value={settings.device} onChange={(v) => set('device', v)} options={[{ v: 'desktop', label: <><Monitor size={14} /> Десктоп</> }, { v: 'phone', label: <><Smartphone size={14} /> Телефон</> }]} />
        </Row>
        <Row label="Тема">
          <Seg value={settings.theme} onChange={(v) => set('theme', v)} options={[{ v: 'light', label: <><Sun size={14} /> Светлая</> }, { v: 'dark', label: <><Moon size={14} /> Тёмная</> }]} />
        </Row>
        <Row label="Состояние данных">
          <Seg value={settings.dataState} onChange={(v) => set('dataState', v)} options={[{ v: 'normal', label: 'Данные' }, { v: 'loading', label: 'Загрузка' }, { v: 'error', label: 'Ошибка' }, { v: 'empty', label: 'Пусто' }]} />
        </Row>

        <div className="tp-section">Цвета</div>
        <Row label="Акцент — небесно-голубой">
          <Swatches name="Акцентный цвет" value={settings.primary} options={PRIMARY_SWATCHES} onChange={(v) => set('primary', v)} />
        </Row>
        <Row label="Палитра статусов — только сигналы и графики">
          <div className="tp-palettes">
            {(Object.keys(PALETTES) as PaletteKey[]).map((k) => (
              <button key={k} type="button" aria-pressed={settings.palette === k} className={settings.palette === k ? 'on' : ''} onClick={() => set('palette', k)}>
                <span className="tp-pal-dots">
                  <i style={{ background: PALETTES[k].clean }} />
                  <i style={{ background: PALETTES[k].overflow }} />
                  <i style={{ background: PALETTES[k].contamination }} />
                </span>
                {PALETTES[k].label}
              </button>
            ))}
          </div>
        </Row>
        <Row label="Боковая панель">
          <Seg value={settings.sidebar} onChange={(v) => set('sidebar', v)} options={[{ v: 'gray', label: 'Серая' }, { v: 'light', label: 'Белая' }]} />
        </Row>
        <Row label="Метки статуса">
          <Seg value={settings.badges} onChange={(v) => set('badges', v)} options={[{ v: 'dot', label: 'Точка' }, { v: 'soft', label: 'С подложкой' }]} />
        </Row>
        <Row label="Подложка карты">
          <Seg value={settings.mapStyle} onChange={(v) => set('mapStyle', v)} options={[{ v: 'calm', label: 'Приглушённая' }, { v: 'osm', label: 'Цветная' }]} />
        </Row>

        <div className="tp-section">Форма</div>
        <Row label="Шрифт">
          <div className="tp-fonts">
            {FONTS.map((f) => (
              <button key={f} type="button" aria-pressed={settings.font === f} className={settings.font === f ? 'on' : ''} style={{ fontFamily: `'${f}'` }} onClick={() => set('font', f)}>
                {f}
              </button>
            ))}
          </div>
        </Row>
        <Row label={`Скругление углов: ${settings.radius} px`}>
          <input className="tp-range" type="range" min={4} max={24} step={2} value={settings.radius} onChange={(e) => set('radius', Number(e.target.value))} aria-label="Скругление углов" />
        </Row>
        <Row label="Анимации и плавная прокрутка">
          <Seg value={settings.motion ? 'on' : 'off'} onChange={(v) => set('motion', v === 'on')} options={[{ v: 'on', label: 'Включены' }, { v: 'off', label: 'Выключены' }]} />
        </Row>
        <Row label="Плотность">
          <Seg value={settings.density} onChange={(v) => set('density', v)} options={[{ v: 'comfortable', label: 'Просторно' }, { v: 'compact', label: 'Компактно' }]} />
        </Row>
      </div>
      <div className="tp-foot">
        <button type="button" className="tp-btn" onClick={() => onChange(DEFAULTS)}>
          <RotateCcw size={15} /> Сбросить
        </button>
        <button type="button" className="tp-btn primary" onClick={copy} title="CSS-переменные текущей темы — для переноса в настоящий фронтенд">
          {copied ? <Check size={15} /> : <Copy size={15} />} {copied ? 'Скопировано' : 'Скопировать токены'}
        </button>
      </div>
    </aside>
  );
}
