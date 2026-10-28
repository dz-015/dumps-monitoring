// Горячие клавиши разметки (схема от 13.10.2026) для CVAT 2.77.
//
// nginx вставляет этот файл в страницу CVAT (sub_filter), ставить разметчикам
// ничего не нужно. Скрипт работает через хранилище интерфейса (redux) и
// cvat-core — те же объекты, что и сам CVAT, поэтому все действия попадают
// в его историю и штатный Ctrl+Z их отменяет; массовые действия идут одним
// commit() и отменяются одним нажатием.
//
//   C      — скопировать все рамки кадра на N следующих кадров той же камеры
//            (N спрашивается; рамки на целевых кадрах ЗАМЕНЯЮТСЯ)
//   R      — удалить все рамки с кадра
//   D / F  — штатное листание CVAT назад / вперёд, скрипт их не трогает
//   1/2    — рамка под курсором — бак: переполнено / не переполнен
//            («пусто» не ставится: пустой бак — бак без рамки мусора)
//   3      — рамка под курсором — мусор бака
//   4      — рамка под курсором — мусор на земле
//   Q/W/E  — рамка под курсором — бак: евробак / контейнер / бутылки
//   Ctrl+Z — штатная отмена CVAT
//
// Клавиши 1/2 и Q/W/E на рамке мусора сразу делают её баком: класс рамки
// меняется без меню справа.
//
// Бак на холсте и полоска его карточки справа окрашены по состоянию:
// переполнено — красный, не переполнен — зелёный, не указано — жёлтый.
// В середине бака — точка вида: евробак — зелёная, контейнер — серо-синяя,
// бутылки — жёлтая, вид не указан — серая и крупнее.
// Это только вид экрана, данные рамки не меняются.
//
// Клавиши ловятся по физической клавише (event.code) — работают и в русской
// раскладке. Привязано к внутреннему устройству CVAT 2.77: не обновлять CVAT
// до конца разметки.
(() => {
    'use strict';

    if (window.__razmetkaTools) return;
    // store() — для проверки в браузере (ml/cvat/razmetka/test).
    window.__razmetkaTools = { version: '2.2', store: () => store || (store = findStore()) };

    const BIN = 'bin';
    const BIN_TRASH = 'bin_trash';
    const GROUND_TRASH = 'ground_trash';
    const STATE_ATTR = 'state';
    const TYPE_ATTR = 'type';
    const UNSET_STATE = 'не указано';
    const STATE_COLORS = {            // состояние бака → [метка для CSS, r, g, b]
        'переполнено': ['over', 229, 48, 58],
        'не переполнен': ['ok', 34, 177, 76],
        [UNSET_STATE]: ['unset', 245, 196, 0],
    };
    const TYPE_DOTS = {               // вид бака → [цвет, радиус в толщинах обводки]
        'евробак': ['rgb(34, 177, 76)', 7],
        'контейнер': ['rgb(90, 125, 165)', 7],
        'бутылки': ['rgb(245, 196, 0)', 7],
        'не указан': ['rgb(150, 150, 150)', 9],
    };
    const SVG_NS = 'http://www.w3.org/2000/svg';

    let lastN = 1;
    let busy = false;
    let store = null;

    // ── доступ к CVAT ────────────────────────────────────────────────────

    function findStore() {
        const root = document.getElementById('root');
        if (!root) return null;
        const key = Object.keys(root).find((k) => k.startsWith('__reactContainer$'));
        if (!key) return null;
        const stack = [root[key]];
        for (let guard = 0; stack.length && guard < 50000; guard++) {
            const fiber = stack.pop();
            if (!fiber) continue;
            const candidate = fiber.memoizedProps && fiber.memoizedProps.store;
            if (candidate && typeof candidate.getState === 'function' && typeof candidate.dispatch === 'function') {
                return candidate;
            }
            if (fiber.sibling) stack.push(fiber.sibling);
            if (fiber.child) stack.push(fiber.child);
        }
        return null;
    }

    function context() {
        if (!store) store = findStore();
        if (!store) return null;
        const st = store.getState();
        const ann = st.annotation;
        const job = ann && ann.job && ann.job.instance;
        if (!job || !ann.annotations.initialized) return null;
        if (ann.workspace !== 'Standard') return null; // в режиме атрибутов цифры — штатные
        if (ann.canvas && ann.canvas.activeControl && ann.canvas.activeControl !== 'cursor') return null; // идёт рисование
        return {
            st,
            job,
            frame: ann.player.frame.number,
            filters: ann.annotations.filters,
            activatedID: ann.annotations.activatedStateID,
            showAll: Boolean(st.settings && st.settings.workspace && st.settings.workspace.showAllInterpolationTracks),
        };
    }

    // Перечитать рамки текущего кадра и историю — так же, как fetchAnnotationsAsync в CVAT.
    async function refresh(c) {
        const states = await c.job.annotations.get(c.frame, c.showAll, c.filters);
        const history = await c.job.actions.get();
        store.dispatch({ type: 'FETCH_ANNOTATIONS_SUCCESS', payload: { states, intervals: [], history } });
    }

    async function shapesOn(job, frame) {
        const states = await job.annotations.get(frame, false, []);
        return states.filter((s) => s.objectType === 'shape');
    }

    const cameraCache = new Map();
    // Камера кадра — префикс имени файла: camw41_2026-10-04_105000.jpg → camw41.
    async function cameraOf(job, frame) {
        const key = `${job.id}:${frame}`;
        if (!cameraCache.has(key)) {
            const data = await job.frames.get(frame);
            const name = String(data.filename || '').split('/').pop();
            cameraCache.set(key, name.split('_')[0]);
        }
        return cameraCache.get(key);
    }

    function serialize(state, frame) {
        return {
            type: state.shapeType,
            frame,
            label_id: state.label.id,
            group: 0,
            source: 'manual',
            attributes: Object.entries(state.attributes)
                .map(([id, value]) => ({ spec_id: Number(id), value: String(value) })),
            elements: [],
            occluded: Boolean(state.occluded),
            outside: false,
            points: state.points.slice(),
            rotation: state.rotation || 0,
            z_order: state.zOrder || 0,
        };
    }

    function labelByName(job, name) {
        return job.labels.find((l) => l.name === name) || null;
    }

    function activeState(c) {
        if (c.activatedID === null || c.activatedID === undefined) return null;
        const state = c.st.annotation.annotations.states.find((s) => s.clientID === c.activatedID);
        return state && state.objectType === 'shape' ? state : null;
    }

    // ── действия ─────────────────────────────────────────────────────────

    async function copyForward(c) {
        const source = await shapesOn(c.job, c.frame);
        if (!source.length) return toast('На кадре нет рамок — копировать нечего');

        const answer = window.prompt(
            `Скопировать ${source.length} рамк(и) на сколько следующих кадров?\n` +
            'Рамки на этих кадрах будут заменены. Отменить потом — Ctrl+Z.',
            String(lastN),
        );
        if (answer === null) return null;
        const n = Number.parseInt(answer, 10);
        if (!(n >= 1)) return toast('Нужно целое число от 1');
        lastN = n;

        const camera = await cameraOf(c.job, c.frame);
        const targets = [];
        for (let f = c.frame + 1; f <= c.job.stopFrame && targets.length < n; f++) {
            if ((await cameraOf(c.job, f)) !== camera) break;
            targets.push(f);
        }
        if (!targets.length) return toast('Дальше нет кадров этой камеры');

        const appended = [];
        const removed = [];
        for (const f of targets) {
            for (const s of await shapesOn(c.job, f)) removed.push({ clientID: s.clientID });
            for (const s of source) appended.push(serialize(s, f));
        }
        await c.job.annotations.commit({ shapes: appended }, { shapes: removed }, c.frame);
        await refresh(c);
        const tail = targets.length < n ? ' (дальше — другая камера или конец задания)' : '';
        return toast(`Скопировано на ${targets.length} кадр(ов)${tail}. Отменить — Ctrl+Z`);
    }

    async function deleteAll(c) {
        const shapes = await shapesOn(c.job, c.frame);
        if (!shapes.length) return toast('На кадре нет рамок');
        await c.job.annotations.commit({}, { shapes: shapes.map((s) => ({ clientID: s.clientID })) }, c.frame);
        await refresh(c);
        return toast(`Удалено рамок: ${shapes.length}. Отменить — Ctrl+Z`);
    }

    // Сменить класс рамки одним commit (удалить + добавить), чтобы Ctrl+Z
    // отменял за одно нажатие; у нового класса атрибуты — по умолчанию,
    // кроме явно заданных.
    async function relabel(c, state, label, values) {
        const shape = serialize(state, c.frame);
        shape.label_id = label.id;
        shape.attributes = label.attributes.map((a) => ({
            spec_id: a.id,
            value: a.name in values ? values[a.name] : a.defaultValue,
        }));
        await c.job.annotations.commit({ shapes: [shape] }, { shapes: [{ clientID: state.clientID }] }, c.frame);
    }

    async function setAttribute(c, state, name, value) {
        const spec = state.label.attributes.find((a) => a.name === name);
        state.attributes = { [spec.id]: value };
        await state.save();
    }

    // Поставить баку атрибут; рамку мусора сначала сделать баком (одним commit).
    async function setBinAttribute(c, state, name, value) {
        if (state.label.name === BIN) return setAttribute(c, state, name, value);
        const bin = labelByName(c.job, BIN);
        if (!bin) throw new Error('В этом проекте нет метки «бак»');
        return relabel(c, state, bin, { [name]: value });
    }

    function setBinState(value, title) {
        return async (c) => {
            const state = activeState(c);
            if (!state) return toast('Наведите курсор на рамку');
            await setBinAttribute(c, state, STATE_ATTR, value);
            await refresh(c);
            return toast(title);
        };
    }

    // Превратить рамку под курсором в рамку мусора (бака или на земле).
    function setLabel(name, title) {
        return async (c) => {
            const state = activeState(c);
            if (!state) return toast('Наведите курсор на рамку');
            const label = labelByName(c.job, name);
            if (!label) return toast(`В этом проекте нет метки «${title}»`, true);
            if (state.label.id === label.id) return toast(`Уже «${title}»`);
            await relabel(c, state, label, {});
            await refresh(c);
            return toast(title);
        };
    }

    function setBinType(value) {
        return async (c) => {
            const state = activeState(c);
            if (!state) return toast('Наведите курсор на рамку');
            await setBinAttribute(c, state, TYPE_ATTR, value);
            await refresh(c);
            return toast(`Вид: ${value}`);
        };
    }

    const ACTIONS = {
        KeyC: copyForward,
        KeyR: deleteAll,
        Digit1: setBinState('переполнено', 'Переполнено'),
        Numpad1: setBinState('переполнено', 'Переполнено'),
        Digit2: setBinState('не переполнен', 'Не переполнен'),
        Numpad2: setBinState('не переполнен', 'Не переполнен'),
        Digit3: setLabel(BIN_TRASH, 'Мусор бака'),
        Numpad3: setLabel(BIN_TRASH, 'Мусор бака'),
        Digit4: setLabel(GROUND_TRASH, 'Мусор на земле'),
        Numpad4: setLabel(GROUND_TRASH, 'Мусор на земле'),
        KeyQ: setBinType('евробак'),
        KeyW: setBinType('контейнер'),
        KeyE: setBinType('бутылки'),
    };

    // ── цвет баков по состоянию ──────────────────────────────────────────
    //
    // CVAT красит рамку цветом метки (атрибуты stroke/fill у <rect>) и карточку
    // справа — переменной --state-item-background. Скрипт помечает их
    // data-razmetka-state, а цвет задаёт таблица стилей ниже: она сильнее
    // атрибутов CVAT и переживает его перерисовку.

    const style = document.createElement('style');
    style.textContent = Object.values(STATE_COLORS).map(([key, r, g, b]) => (
        `#cvat_canvas_content [data-razmetka-state="${key}"] { stroke: rgb(${r}, ${g}, ${b}) !important; fill: rgb(${r}, ${g}, ${b}) !important; }\n` +
        `.cvat-objects-sidebar-state-item[data-razmetka-state="${key}"] { --state-item-background: ${r}, ${g}, ${b} !important; }`
    )).join('\n') + '\n.razmetka-dot { pointer-events: none; stroke: #fff; }';

    function mark(el, key) {
        if (!el) return;
        if (key === null) el.removeAttribute('data-razmetka-state');
        else if (el.getAttribute('data-razmetka-state') !== key) el.setAttribute('data-razmetka-state', key);
    }

    // Точка вида в центре рамки бака. Радиус — в толщинах обводки: CVAT
    // сам меняет толщину при приближении, так точка на экране одного размера.
    function placeDot(rect, clientID, type) {
        const id = `razmetka-dot-${clientID}`;
        let d = document.getElementById(id);
        if (!rect || rect.classList.contains('cvat_canvas_hidden')) {
            if (d) d.remove();
            return;
        }
        if (!d || d.parentNode !== rect.parentNode) {
            if (d) d.remove();
            d = document.createElementNS(SVG_NS, 'circle');
            d.id = id;
            d.setAttribute('class', 'razmetka-dot');
            rect.parentNode.appendChild(d);
        }
        const [color, k] = TYPE_DOTS[type] || TYPE_DOTS['не указан'];
        const sw = +rect.getAttribute('stroke-width') || 2;
        const want = {
            cx: String(+rect.getAttribute('x') + +rect.getAttribute('width') / 2),
            cy: String(+rect.getAttribute('y') + +rect.getAttribute('height') / 2),
            r: String(sw * k),
            'stroke-width': String(sw * 0.6),
            fill: color,
        };
        for (const [name, value] of Object.entries(want)) {
            if (d.getAttribute(name) !== value) d.setAttribute(name, value);
        }
    }

    function paint() {
        painting = false;
        if (!store) store = findStore();
        if (!store) return;
        const ann = store.getState().annotation;
        if (!ann || !ann.annotations || !ann.annotations.states) return;
        const dots = new Set();
        for (const s of ann.annotations.states) {
            let key = null;
            const rect = document.getElementById(`cvat_canvas_shape_${s.clientID}`);
            if (s.objectType === 'shape' && s.label && s.label.name === BIN) {
                const value = (name, unset) => {
                    const spec = s.label.attributes.find((a) => a.name === name);
                    return spec ? s.attributes[spec.id] : unset;
                };
                key = (STATE_COLORS[value(STATE_ATTR, UNSET_STATE)] || STATE_COLORS[UNSET_STATE])[0];
                placeDot(rect, s.clientID, value(TYPE_ATTR, 'не указан'));
                dots.add(`razmetka-dot-${s.clientID}`);
            }
            mark(rect, key);
            mark(document.getElementById(`cvat-objects-sidebar-state-item-${s.clientID}`), key);
        }
        for (const d of document.querySelectorAll('.razmetka-dot')) {
            if (!dots.has(d.id)) d.remove();
        }
    }

    let painting = false;
    function schedulePaint() {
        if (painting) return;
        painting = true;
        requestAnimationFrame(paint);
    }

    let subscribed = null;
    function startPainting() {
        (document.head || document.documentElement).appendChild(style);
        new MutationObserver(() => {
            if (!store) store = findStore();
            if (store && subscribed !== store) {
                store.subscribe(schedulePaint);
                subscribed = store;
            }
            schedulePaint();
        }).observe(document.documentElement, {
            childList: true, subtree: true,
            attributes: true, attributeFilter: ['x', 'y', 'width', 'height', 'stroke-width', 'class'],
        });
    }
    // Скрипт может выполниться раньше, чем браузер разобрал страницу.
    if (document.documentElement) startPainting();
    else document.addEventListener('DOMContentLoaded', startPainting, { once: true });

    // ── клавиатура и подсказки ───────────────────────────────────────────

    window.addEventListener('keydown', (event) => {
        if (event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
        const action = ACTIONS[event.code];
        if (!action) return;
        const { target } = event;
        if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
        const c = context();
        if (!c) return;

        // Перехватываем до CVAT: у него на C — «назад на шаг», на Q — «перекрыт».
        event.preventDefault();
        event.stopImmediatePropagation();
        if (event.repeat || busy) return;
        busy = true;
        Promise.resolve()
            .then(() => action(c))
            .catch((error) => toast(`Ошибка: ${error && error.message ? error.message : error}`, true))
            .finally(() => { busy = false; });
    }, true);

    let toastTimer = null;
    function toast(text, isError = false) {
        let el = document.getElementById('razmetka-toast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'razmetka-toast';
            el.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);' +
                'z-index:100000;padding:8px 14px;border-radius:6px;font:14px/1.3 sans-serif;' +
                'color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.3);pointer-events:none;transition:opacity .2s';
            document.body.appendChild(el);
        }
        el.textContent = text;
        el.style.background = isError ? '#b42318' : 'rgba(30,30,30,.92)';
        el.style.opacity = '1';
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { el.style.opacity = '0'; }, isError ? 6000 : 2500);
        return text;
    }
})();
