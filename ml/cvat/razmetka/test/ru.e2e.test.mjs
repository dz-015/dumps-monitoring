// Проверка перевода в настоящем браузере на живом CVAT: обходит экраны, которые
// видит разметчик, и ищет оставшиеся английские надписи. Временный проект
// «ТЕСТ перевода» в конце удаляется.
//
//   CVAT_USER=arseniy CVAT_PASSWORD=... [LOCAL_TOOLS=1] npm test

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { BASE, RAW, api, box, createTestJob, newBrowserPage, login, openJob } from './cvat.mjs';

let browser;
let page;
let project;
let task;
let jobId;
let L;

// Что может остаться латиницей: клавиши в [скобках], имена файлов и людей,
// названия программ, размеры рамки.
const ALLOWED = [
    /\[[^\]]*\]/g, /camw\d+_[\d-]+_\d+\.jpg/g, /razmetchik\d+|arseniy/g, /\bCVAT\b|\bOpenCV\b|\bGitHub\b/g,
    /\d+(\.\d+)?x\d+(\.\d+)?px/g, /\b[23]D\b/g, /\b(Shift|Ctrl|Alt|Esc|Space|Del|Enter|F\d+)\b/g,
];

async function english() {
    const strings = await page.evaluate(() => {
        const out = [];
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (!node.parentElement.closest('script, style')) out.push(node.nodeValue.trim());
        }
        for (const el of document.querySelectorAll('[title], [placeholder]')) {
            out.push(el.getAttribute('title') || '', el.getAttribute('placeholder') || '');
        }
        return out;
    });
    const left = strings.filter((s) => /[A-Za-z]{2,}/.test(ALLOWED.reduce((t, re) => t.replace(re, ''), s)));
    return [...new Set(left)].sort();
}

async function assertRussian(where) {
    const left = await english();
    assert.deepEqual(left, [], `${where}: осталось по-английски:\n  ${left.join('\n  ')}`);
}

// Русские надписи длиннее английских: текст не должен вылезать из кнопки.
async function overflowing(selector) {
    return page.locator(selector).evaluateAll((els) => els
        .filter((el) => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)
        .map((el) => el.innerText.trim()));
}

// Пункт меню, перенесённый на вторую строку, наезжает на соседний: высота пунктов фиксирована.
async function wrapped(selector) {
    return page.locator(selector).evaluateAll((els) => els
        .filter((el) => {
            const range = document.createRange();
            range.selectNodeContents(el);
            return new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size > 1;
        })
        .map((el) => el.innerText.trim()));
}

async function hoverAll(selector) {
    for (const el of await page.locator(selector).all()) {
        await el.hover({ timeout: 2000 }).catch(() => {});
        await page.waitForTimeout(300);
        const left = await english();
        if (left.length) return left;
    }
    return [];
}

async function closeOverlays() {
    // окна CVAT (фильтры, сведения) не закрываются по Esc — только крестиком
    for (const x of await page.locator('.ant-modal-wrap .ant-modal-close').all()) {
        if (await x.isVisible()) await x.click();
    }
    await page.keyboard.press('Escape');
    await page.mouse.click(800, 880);
    await page.waitForTimeout(300);
}

before(async () => {
    const files = fs.readdirSync(RAW).filter((n) => n.startsWith('camw41_2026-10-04_1')).sort().slice(0, 3);
    ({ project, task, jobId, L } = await createTestJob('ТЕСТ перевода', files));
    await api('PUT', `/api/jobs/${jobId}/annotations`, {
        version: 0, tags: [], tracks: [],
        shapes: [box(L, 'bin', 0, [100, 100, 400, 400], { state: 'не указано', type: 'не указан' }), box(L, 'ground_trash', 0, [600, 300, 800, 500])],
    });
    ({ browser, page } = await newBrowserPage());
});

after(async () => {
    await browser?.close();
    if (project) await api('DELETE', `/api/projects/${project.id}`);
});

test('страница входа', async () => {
    await page.goto(`${BASE}/auth/login`);
    await page.waitForSelector('input[id$="credential"]');
    await page.waitForTimeout(1000);
    await assertRussian('вход');
    await page.fill('input[id$="credential"]', 'кто-то');
    await page.waitForTimeout(500);
    await assertRussian('вход после ввода логина');
    await login(page);
});

test('списки задач, заданий, проектов и страница задачи', async () => {
    for (const url of ['/tasks', `/tasks/${task.id}`, '/jobs', '/projects']) {
        await page.goto(BASE + url);
        await page.waitForTimeout(3000);
        await assertRussian(url);
    }
    await page.locator('.cvat-header-menu-user-dropdown').click();
    await page.waitForTimeout(800);
    await assertRussian('меню пользователя');
    await closeOverlays();
});

test('экран разметки: панели и подписи рамок', async () => {
    await openJob(page, task.id, jobId);
    await page.waitForTimeout(1500);
    await assertRussian('экран разметки');
    assert.deepEqual(await overflowing('.cvat-annotation-header-button'), [], 'кнопки верхней панели');
    assert.deepEqual(await overflowing('.cvat-workspace-selector .ant-select-selection-item'), [], 'режим работы');
});

test('подсказки кнопок верхней и левой панели', async () => {
    const left = [
        ...await hoverAll('.cvat-canvas-controls-sidebar [class*="cvat-"]'),
        ...await hoverAll('.cvat-annotation-header .anticon, .cvat-annotation-header button'),
    ];
    assert.deepEqual(left, [], `подсказки:\n  ${left.join('\n  ')}`);
    await page.mouse.move(800, 880);
});

test('окно «нарисовать рамку»', async () => {
    await page.locator('.cvat-draw-rectangle-control').click();
    await page.waitForTimeout(800);
    await assertRussian('рисование рамки');
    assert.deepEqual(await overflowing('.cvat-draw-shape-popover .ant-radio-button-wrapper, .cvat-draw-shape-popover .ant-btn'), [], 'кнопки окна рисования');
    await page.locator('.cvat-cursor-control').click(); // окно рисования закрывается только так
});

test('рамка в боковой панели: подробности, списки, меню ⋮, кнопки', async () => {
    const item = page.locator('.cvat-objects-sidebar-state-item').first();
    await item.locator('.ant-collapse-header').click();
    await page.waitForTimeout(500);
    await assertRussian('подробности рамки');
    for (const select of await item.locator('.ant-select').all()) {
        await select.click();
        await page.waitForTimeout(500);
        await assertRussian('выпадающий список рамки');
        await closeOverlays();
    }
    const left = await hoverAll('.cvat-objects-sidebar-state-item .anticon');
    assert.deepEqual(left, [], `кнопки рамки:\n  ${left.join('\n  ')}`);
    await item.locator('.cvat-object-item-menu-button, .anticon-more').first().click();
    await page.waitForTimeout(500);
    await assertRussian('меню рамки');
    await closeOverlays();
});

test('вкладки боковой панели', async () => {
    for (const tab of await page.locator('.cvat-objects-sidebar .ant-tabs-tab').all()) {
        await tab.click();
        await page.waitForTimeout(500);
        await assertRussian('вкладка боковой панели');
    }
    await page.locator('.cvat-objects-sidebar .ant-tabs-tab').first().click();
});

test('меню задания, смена состояния и режимы работы', async () => {
    await page.locator('.cvat-annotation-header-menu-button').click();
    await page.waitForTimeout(500);
    await assertRussian('меню задания');
    assert.deepEqual(await wrapped('.cvat-annotation-menu .ant-dropdown-menu-title-content'), [], 'пункты меню задания');
    await page.locator('.cvat-annotation-menu-job-state-submenu, .ant-dropdown-menu-submenu').first().hover();
    await page.waitForTimeout(800);
    await assertRussian('смена состояния');
    await closeOverlays();
    await page.locator('.cvat-workspace-selector').click();
    await page.waitForTimeout(500);
    await assertRussian('режимы работы');
    await closeOverlays();
});

test('завершение задания, сведения, фильтры', async () => {
    await page.locator('.cvat-annotation-header-menu-button').click();
    await page.locator('.ant-dropdown-menu-item').filter({ hasText: /Завершить задание|Finish the job/ }).click();
    await page.waitForTimeout(800);
    await assertRussian('подтверждение завершения');
    await page.locator('.ant-modal-confirm .ant-btn').first().click(); // «Отмена»
    await page.waitForTimeout(500);

    await page.locator('.cvat-annotation-header-info-button').click();
    await page.waitForTimeout(1500);
    await assertRussian('сведения о задании');
    await page.locator('.ant-modal .ant-btn-primary').click(); // «ОК»

    await page.locator('.cvat-annotation-header-filters-button').click();
    await page.waitForTimeout(800);
    await assertRussian('фильтры');
    await closeOverlays();
});

test('настройки: просмотр и рабочая область', async () => {
    await page.locator('.cvat-header-menu-user-dropdown').click();
    await page.locator('.cvat-header-menu-settings-item, .ant-dropdown-menu-item').filter({ hasText: /Настройки|Settings/ }).click();
    await page.waitForTimeout(1000);
    await assertRussian('настройки: просмотр');
    await page.locator('.ant-modal .ant-tabs-tab').nth(1).click();
    await page.waitForTimeout(500);
    await assertRussian('настройки: рабочая область');
    await page.locator('.ant-modal .ant-btn').filter({ hasText: /Закрыть|Close/ }).click();
    await page.waitForTimeout(500);
});

test('выбор «переполнено» в списке рамки записывается в разметку', async () => {
    const item = page.locator('.cvat-objects-sidebar-state-item').first();
    await item.locator('.ant-select').nth(1).click(); // атрибут «состояние»
    await page.locator('.ant-select-item-option').filter({ hasText: /^переполнено$/ }).click();
    await page.waitForTimeout(800);
    const value = await page.evaluate(async () => {
        const job = window.__razmetkaTools.store().getState().annotation.job.instance;
        const [bin] = (await job.annotations.get(0, false, [])).filter((s) => s.label.name === 'bin');
        const spec = bin.label.attributes.find((a) => a.name === 'state');
        return bin.attributes[spec.id];
    });
    assert.equal(value, 'переполнено');
    await page.waitForTimeout(500);
    const left = await hoverAll('.cvat-annotation-header .anticon');
    assert.deepEqual(left, [], `подсказки после правки:\n  ${left.join('\n  ')}`);
});

test('шаги из инструкции: «Фигура» и два щелчка рисуют рамку, N — следующую, Delete удаляет выделенную', async () => {
    const count = () => page.evaluate(async () => {
        const job = window.__razmetkaTools.store().getState().annotation.job.instance;
        return (await job.annotations.get(0, false, [])).length;
    });
    const before = await count();
    const canvas = await page.locator('.cvat-canvas-container').boundingBox();
    const at = (fx, fy) => [canvas.x + canvas.width * fx, canvas.y + canvas.height * fy];

    await page.locator('.cvat-draw-rectangle-control').click();
    await page.locator('.cvat-draw-shape-popover .ant-btn').filter({ hasText: 'Фигура' }).click();
    await page.mouse.click(...at(0.70, 0.60));
    await page.mouse.click(...at(0.80, 0.75));
    await page.waitForFunction((n) => window.__razmetkaTools.store().getState().annotation.annotations.states.length === n, before + 1);

    await page.keyboard.press('KeyN');
    await page.waitForTimeout(300);
    await page.mouse.click(...at(0.82, 0.60));
    await page.mouse.click(...at(0.92, 0.75));
    await page.waitForFunction((n) => window.__razmetkaTools.store().getState().annotation.annotations.states.length === n, before + 2);
    assert.equal(await count(), before + 2);

    await page.mouse.move(...at(0.87, 0.68));
    await page.waitForTimeout(300);
    await page.keyboard.press('Delete');
    await page.waitForFunction((n) => window.__razmetkaTools.store().getState().annotation.annotations.states.length === n, before + 1);
    assert.equal(await count(), before + 1);
});
