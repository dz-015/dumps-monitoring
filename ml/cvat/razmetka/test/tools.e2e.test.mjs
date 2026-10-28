// Проверка горячих клавиш разметки в настоящем браузере на живом CVAT.
//
// Создаёт временный проект «ТЕСТ инструментов разметки» с метками разметки №2,
// задание из 6 кадров (3 камеры w41 + 3 камеры w42), раскладывает рамки,
// жмёт клавиши как человек и сверяет результат; в конце проект удаляется.
//
//   CVAT_USER=arseniy CVAT_PASSWORD=... [LOCAL_TOOLS=1] npm test
//
// LOCAL_TOOLS=1 — вставлять ru.js и tools.js из рабочей копии (см. cvat.mjs).

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { RAW, api, box as makeBox, createTestJob, newBrowserPage, login, openJob } from './cvat.mjs';

let browser;
let page;
let project;
let task;
let jobId;
let L; // имя метки → {id, attrs: {имя: id}}

function frameFiles() {
    const all = fs.readdirSync(RAW).filter((n) => /_2026-10-04_1[0-4]/.test(n)).sort();
    const pick = (cam) => all.filter((n) => n.startsWith(`${cam}_`)).slice(0, 3);
    const files = [...pick('camw41'), ...pick('camw42')];
    assert.equal(files.length, 6, 'нужно по 3 дневных кадра w41 и w42 за 04.10');
    return files;
}

const box = (...args) => makeBox(L, ...args);

// Рамки кадра так, как их видит CVAT в браузере: класс, атрибуты по имени, точки.
async function shapes(frame) {
    return page.evaluate(async (f) => {
        const job = window.__razmetkaTools.store().getState().annotation.job.instance;
        const states = await job.annotations.get(f, false, []);
        return states.filter((s) => s.objectType === 'shape').map((s) => ({
            label: s.label.name,
            attrs: Object.fromEntries(s.label.attributes.map((a) => [a.name, s.attributes[a.id]])),
            points: s.points.map((p) => Math.round(p)),
            clientID: s.clientID,
        })).sort((a, b) => a.points[0] - b.points[0]);
    }, frame);
}

async function currentFrame() {
    return page.evaluate(() => window.__razmetkaTools.store().getState().annotation.player.frame.number);
}

async function goTo(frame) {
    // Как человек: номер кадра в поле верхней панели CVAT и Enter.
    const input = page.locator('.cvat-player-frame-selector input');
    await input.fill(String(frame));
    await input.press('Enter');
    await page.waitForFunction((f) => {
        const a = window.__razmetkaTools.store().getState().annotation;
        return a.player.frame.number === f && !a.player.frame.fetching;
    }, frame);
    await input.blur();
}

async function activate(points0) {
    const id = await page.evaluate((x) => {
        const s = window.__razmetkaTools.store();
        const st = s.getState().annotation.annotations.states.find((o) => Math.round(o.points[0]) === x);
        s.dispatch({ type: 'ACTIVATE_OBJECT', payload: { activatedStateID: st.clientID, activatedElementID: null, activatedAttributeID: null } });
        return st.clientID;
    }, points0);
    assert.ok(id);
}

async function press(key) {
    const before = await page.evaluate(() => (document.getElementById('razmetka-toast') || {}).textContent || '');
    await page.keyboard.press(key);
    return before;
}

async function waitToast(contains) {
    await page.waitForFunction((t) => (document.getElementById('razmetka-toast') || {}).textContent?.includes(t), contains);
    await page.evaluate(() => { document.getElementById('razmetka-toast').textContent = ''; });
}

async function undo() {
    const n = await page.evaluate(() => window.__razmetkaTools.store().getState().annotation.annotations.history.undo.length);
    await page.keyboard.press('Control+z');
    await page.waitForFunction((m) => window.__razmetkaTools.store().getState().annotation.annotations.history.undo.length === m - 1, n);
}

const A = [100, 100, 400, 400];
const B = [600, 300, 800, 500];
const C = [1000, 100, 1200, 300];
const D = [1500, 200, 1700, 400];
const E = [100, 500, 300, 700];
const F = [500, 500, 700, 700];
const G = [900, 500, 1100, 700];

// Цвета баков по состоянию — те же, что в tools.js.
const RED = 'rgb(229, 48, 58)';
const GREEN = 'rgb(34, 177, 76)';
const YELLOW = 'rgb(245, 196, 0)';
const GREY = 'rgb(150, 150, 150)';
const BLUE_GREY = 'rgb(90, 125, 165)';

before(async () => {
    ({ project, task, jobId, L } = await createTestJob('ТЕСТ инструментов разметки', frameFiles()));

    await api('PUT', `/api/jobs/${jobId}/annotations`, {
        version: 0, tags: [], tracks: [],
        shapes: [
            box('bin', 0, A, { state: 'не указано', type: 'евробак' }),
            box('ground_trash', 0, B),
            box('bin', 1, C, { state: 'переполнено', type: 'контейнер' }),
            box('bin', 3, D, { state: 'не переполнен', type: 'бутылки' }),
            box('bin', 4, E, { state: 'переполнено', type: 'евробак' }),
            box('bin', 4, F, { state: 'не переполнен', type: 'контейнер' }),
            box('bin', 4, G, { state: 'не указано', type: 'не указан' }),
            box('bin_trash', 4, [1300, 500, 1500, 700]),
        ],
    });

    ({ browser, page } = await newBrowserPage());
    await login(page);
    await openJob(page, task.id, jobId);
});

after(async () => {
    await browser?.close();
    if (project) await api('DELETE', `/api/projects/${project.id}`);
});

test('файлы кадров разложены по камерам: 0–2 = w41, 3–5 = w42', async () => {
    const names = await page.evaluate(async () => {
        const job = window.__razmetkaTools.store().getState().annotation.job.instance;
        const out = [];
        for (let f = job.startFrame; f <= job.stopFrame; f++) out.push((await job.frames.get(f)).filename);
        return out;
    });
    assert.deepEqual(names.map((n) => n.split('_')[0]), ['camw41', 'camw41', 'camw41', 'camw42', 'camw42', 'camw42']);
});

test('C копирует все рамки на N следующих кадров, заменяя их, и не переходит на другую камеру', async () => {
    await goTo(0);
    page.once('dialog', (d) => d.accept('5'));
    await press('KeyC');
    await waitToast('Скопировано на 2');

    const src = (await shapes(0)).map(({ label, attrs, points }) => ({ label, attrs, points }));
    for (const f of [1, 2]) {
        assert.deepEqual((await shapes(f)).map(({ label, attrs, points }) => ({ label, attrs, points })), src, `кадр ${f}`);
    }
    assert.deepEqual((await shapes(3)).map((s) => s.points), [D], 'кадр 3 — другая камера, не тронут');
});

test('Ctrl+Z отменяет массовое копирование одним нажатием', async () => {
    await undo();
    assert.deepEqual((await shapes(1)).map((s) => [s.label, s.attrs.state, s.points]), [['bin', 'переполнено', C]]);
    assert.deepEqual(await shapes(2), []);
});

test('R удаляет все рамки кадра и остаётся на нём; Ctrl+Z возвращает', async () => {
    await goTo(1);
    await press('KeyR');
    await waitToast('Удалено рамок: 1');
    assert.equal(await currentFrame(), 1, 'R не должна переключать кадр');
    assert.deepEqual(await shapes(1), []);
    await undo();
    assert.deepEqual((await shapes(1)).map((s) => s.points), [C]);
});

test('R работает и в русской раскладке (клавиша «к»)', async () => {
    await page.evaluate(() => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'к', code: 'KeyR', bubbles: true }));
    });
    await waitToast('Удалено рамок: 1');
    assert.deepEqual(await shapes(1), []);
    await undo();
});

test('D и F — штатное листание CVAT: назад и вперёд, рамки не трогают', async () => {
    await goTo(1);
    await page.keyboard.press('KeyF');
    await page.waitForFunction(() => window.__razmetkaTools.store().getState().annotation.player.frame.number === 2);
    await page.keyboard.press('KeyD');
    await page.waitForFunction(() => window.__razmetkaTools.store().getState().annotation.player.frame.number === 1);
    assert.deepEqual((await shapes(1)).map((s) => s.points), [C]);
});

test('1/2 — состояние бака, Q/W/E — вид; каждое отменяется одним Ctrl+Z', async () => {
    await goTo(0);
    await activate(A[0]);
    await press('Digit1');
    await waitToast('Переполнено');
    await activate(A[0]);
    await press('KeyE');
    await waitToast('бутылки');
    let a = (await shapes(0)).find((s) => s.points[0] === A[0]);
    assert.deepEqual(a.attrs, { state: 'переполнено', type: 'бутылки' });

    await undo();
    a = (await shapes(0)).find((s) => s.points[0] === A[0]);
    assert.deepEqual(a.attrs, { state: 'переполнено', type: 'евробак' });
    await activate(A[0]);
    await press('Digit2');
    await waitToast('Не переполнен');
    await activate(A[0]);
    await press('KeyW');
    await waitToast('контейнер');
    a = (await shapes(0)).find((s) => s.points[0] === A[0]);
    assert.deepEqual(a.attrs, { state: 'не переполнен', type: 'контейнер' });
});

test('3 больше не ставит «пусто»: у бака рамка превращается в мусор бака', async () => {
    await activate(A[0]);
    await press('Digit3');
    await waitToast('Мусор бака');
    const a = (await shapes(0)).find((s) => s.points[0] === A[0]);
    assert.equal(a.label, 'bin_trash');
    await undo();
    assert.equal((await shapes(0)).find((s) => s.points[0] === A[0]).label, 'bin');
});

test('1/2 на рамке мусора сразу делают её баком с этим состоянием; Ctrl+Z возвращает мусор', async () => {
    await activate(B[0]);
    await press('Digit2');
    await waitToast('Не переполнен');
    let b = (await shapes(0)).find((s) => s.points[0] === B[0]);
    assert.deepEqual([b.label, b.attrs, b.points], ['bin', { state: 'не переполнен', type: 'не указан' }, B]);
    assert.equal((await shapes(0)).length, 2, 'смена класса не плодит рамки');
    await undo();
    b = (await shapes(0)).find((s) => s.points[0] === B[0]);
    assert.equal(b.label, 'ground_trash');
});

test('Q/W/E на рамке мусора делают её баком этого вида, состояние «не указано»', async () => {
    await activate(B[0]);
    await press('KeyW');
    await waitToast('контейнер');
    const b = (await shapes(0)).find((s) => s.points[0] === B[0]);
    assert.deepEqual([b.label, b.attrs], ['bin', { state: 'не указано', type: 'контейнер' }]);
    await undo();
    assert.equal((await shapes(0)).find((s) => s.points[0] === B[0]).label, 'ground_trash');
});

test('3 — мусор бака, 4 — мусор на земле; смена отменяется одним Ctrl+Z и не плодит рамки', async () => {
    await activate(B[0]);
    await press('Digit3');
    await waitToast('Мусор бака');
    let b = (await shapes(0)).find((s) => s.points[0] === B[0]);
    assert.deepEqual([b.label, b.attrs], ['bin_trash', {}]);

    await activate(B[0]);
    await press('Digit4');
    await waitToast('Мусор на земле');
    b = (await shapes(0)).find((s) => s.points[0] === B[0]);
    assert.equal(b.label, 'ground_trash');

    await undo();
    b = (await shapes(0)).find((s) => s.points[0] === B[0]);
    assert.equal(b.label, 'bin_trash');
    assert.equal((await shapes(0)).length, 2, 'смена класса не плодит рамки');
});

test('без выделенной рамки 1/Q ничего не меняют и подсказывают', async () => {
    await page.evaluate(() => window.__razmetkaTools.store().dispatch({
        type: 'ACTIVATE_OBJECT', payload: { activatedStateID: null, activatedElementID: null, activatedAttributeID: null },
    }));
    const before = JSON.stringify(await shapes(0));
    await press('Digit1');
    await waitToast('Наведите курсор');
    assert.equal(JSON.stringify(await shapes(0)), before);
});

// Цвет рамки бака на холсте и полоски его карточки справа.
async function colors(points0) {
    return page.evaluate((x) => {
        const st = window.__razmetkaTools.store().getState().annotation.annotations.states
            .find((o) => Math.round(o.points[0]) === x);
        const rect = document.getElementById(`cvat_canvas_shape_${st.clientID}`);
        const card = document.getElementById(`cvat-objects-sidebar-state-item-${st.clientID}`);
        return {
            stroke: getComputedStyle(rect).stroke,
            card: card ? getComputedStyle(card).getPropertyValue('--state-item-background').trim() : null,
        };
    }, points0);
}

test('бак окрашен по состоянию: переполнено — красный, не переполнен — зелёный, не указано — жёлтый', async () => {
    await goTo(4);
    await page.waitForFunction(() => document.querySelectorAll('#cvat_canvas_content rect.cvat_canvas_shape').length === 4);
    await page.waitForTimeout(300);
    assert.equal((await colors(E[0])).stroke, RED);
    assert.equal((await colors(F[0])).stroke, GREEN);
    assert.equal((await colors(G[0])).stroke, YELLOW);
    assert.equal((await colors(E[0])).card, '229, 48, 58');
    assert.equal((await colors(G[0])).card, '245, 196, 0');
});

test('цвет меняется сразу после 1/2 и после Ctrl+Z', async () => {
    await activate(G[0]);
    await press('Digit1');
    await waitToast('Переполнено');
    await page.waitForTimeout(300);
    assert.equal((await colors(G[0])).stroke, RED);
    await undo();
    await page.waitForTimeout(300);
    assert.equal((await colors(G[0])).stroke, YELLOW);
});

// Точка вида в середине рамки бака: цвет, радиус, совпадение с центром рамки.
async function dot(points0) {
    return page.evaluate((x) => {
        const st = window.__razmetkaTools.store().getState().annotation.annotations.states
            .find((o) => Math.round(o.points[0]) === x);
        const rect = document.getElementById(`cvat_canvas_shape_${st.clientID}`);
        const d = document.getElementById(`razmetka-dot-${st.clientID}`);
        if (!d) return null;
        const cx = +rect.getAttribute('x') + +rect.getAttribute('width') / 2;
        const cy = +rect.getAttribute('y') + +rect.getAttribute('height') / 2;
        return {
            fill: getComputedStyle(d).fill,
            r: +d.getAttribute('r'),
            centered: Math.abs(+d.getAttribute('cx') - cx) < 1 && Math.abs(+d.getAttribute('cy') - cy) < 1,
            clickThrough: getComputedStyle(d).pointerEvents === 'none',
        };
    }, points0);
}

test('точка вида в середине бака: евробак — зелёная, контейнер — серо-синяя, не указан — серая и крупнее', async () => {
    await goTo(4);
    await page.waitForFunction(() => document.querySelectorAll('[id^="razmetka-dot-"]').length === 3);
    const e = await dot(E[0]);
    const f = await dot(F[0]);
    const g = await dot(G[0]);
    assert.deepEqual([e.fill, f.fill, g.fill], [GREEN, BLUE_GREY, GREY]);
    assert.ok(e.centered && f.centered && g.centered, 'точка в центре рамки');
    assert.ok(e.clickThrough, 'точка не мешает наводить курсор на рамку');
    assert.ok(g.r > e.r, 'серая точка крупнее');
    const trash = await page.evaluate(() => {
        const st = window.__razmetkaTools.store().getState().annotation.annotations.states.find((o) => o.label.name === 'bin_trash');
        return document.getElementById(`razmetka-dot-${st.clientID}`);
    });
    assert.equal(trash, null, 'у мусора точки нет');
});

test('точка меняет цвет сразу после Q/W/E; бутылки — жёлтая', async () => {
    await activate(G[0]);
    await press('KeyE');
    await waitToast('бутылки');
    await page.waitForTimeout(300);
    assert.equal((await dot(G[0])).fill, YELLOW);
    await undo();
    await page.waitForTimeout(300);
    assert.equal((await dot(G[0])).fill, GREY);
});

test('мусор бака красится цветом своей метки, не цветом состояния', async () => {
    const stroke = await page.evaluate(() => {
        const st = window.__razmetkaTools.store().getState().annotation.annotations.states.find((o) => o.label.name === 'bin_trash');
        return [getComputedStyle(document.getElementById(`cvat_canvas_shape_${st.clientID}`)).stroke, st.label.color];
    });
    const hex = stroke[1].replace('#', '');
    const rgb = `rgb(${parseInt(hex.slice(0, 2), 16)}, ${parseInt(hex.slice(2, 4), 16)}, ${parseInt(hex.slice(4, 6), 16)})`;
    assert.equal(stroke[0], rgb);
});

test('Ctrl+S сохраняет изменения на сервер', async () => {
    await goTo(0);
    await page.keyboard.press('Control+s');
    await page.waitForFunction(() => !window.__razmetkaTools.store().getState().annotation.annotations.saving.uploading);
    await page.waitForTimeout(1000);
    const saved = await api('GET', `/api/jobs/${jobId}/annotations`);
    const onFrame0 = saved.shapes.filter((s) => s.frame === 0).map((s) => s.label_id).sort();
    assert.deepEqual(onFrame0, [L.bin.id, L.bin_trash.id].sort());   // B после отмены — мусор бака
});
