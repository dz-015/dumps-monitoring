// Порядок работы из памятки разметчика — только клавишами, в новом окне
// браузера, где панель рисования ни разу не открывали.
//
//   CVAT_USER=arseniy CVAT_PASSWORD=... [LOCAL_TOOLS=1] npm test

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { RAW, api, createTestJob, newBrowserPage, login, openJob } from './cvat.mjs';

let browser;
let page;
let project;

before(async () => {
    const files = fs.readdirSync(RAW).filter((n) => n.startsWith('camw42_2026-10-04_1')).sort().slice(0, 2);
    const created = await createTestJob('ТЕСТ памятки', files);
    project = created.project;
    ({ browser, page } = await newBrowserPage());
    await login(page);
    await openJob(page, created.task.id, created.jobId);
});

after(async () => {
    await browser?.close();
    if (project) await api('DELETE', `/api/projects/${project.id}`);
});

async function boxes() {
    return page.evaluate(async () => {
        const job = window.__razmetkaTools.store().getState().annotation.job.instance;
        const states = await job.annotations.get(0, false, []);
        return states.map((s) => ({
            label: s.label.name,
            attrs: Object.fromEntries(s.label.attributes.map((a) => [a.name, s.attributes[a.id]])),
        }));
    });
}

async function drawWithN(fx1, fy1, fx2, fy2) {
    const c = await page.locator('.cvat-canvas-container').boundingBox();
    const n = (await boxes()).length;
    await page.keyboard.press('KeyN');
    await page.waitForTimeout(300);
    await page.mouse.click(c.x + c.width * fx1, c.y + c.height * fy1);
    await page.mouse.click(c.x + c.width * fx2, c.y + c.height * fy2);
    await page.waitForFunction((k) => window.__razmetkaTools.store().getState().annotation.annotations.states.length === k, n + 1);
    await page.waitForTimeout(300);
}

test('N и два щелчка рисуют бак: состояние «не указано», вид «не указан»', async () => {
    await drawWithN(0.10, 0.20, 0.25, 0.45);
    assert.deepEqual(await boxes(), [{ label: 'bin', attrs: { state: 'не указано', type: 'не указан' } }]);
});

async function hoverInside(fx, fy) {
    const c = await page.locator('.cvat-canvas-container').boundingBox();
    await page.mouse.move(c.x + c.width * fx, c.y + c.height * fy, { steps: 5 });
    await page.waitForTimeout(300);
}

test('курсор на новую рамку — 1 и W отмечают её', async () => {
    await hoverInside(0.17, 0.33);
    await page.keyboard.press('Digit1');
    await page.waitForTimeout(500);
    await page.keyboard.press('KeyW');
    await page.waitForTimeout(500);
    assert.deepEqual(await boxes(), [{ label: 'bin', attrs: { state: 'переполнено', type: 'контейнер' } }]);
});

test('вторая рамка через N и 4 становится мусором на земле, первая не меняется', async () => {
    await drawWithN(0.50, 0.60, 0.65, 0.80);
    await hoverInside(0.57, 0.70);
    await page.keyboard.press('Digit4');
    await page.waitForTimeout(500);
    const labels = (await boxes()).map((b) => b.label).sort();
    assert.deepEqual(labels, ['bin', 'ground_trash']);
    assert.deepEqual((await boxes()).find((b) => b.label === 'bin').attrs, { state: 'переполнено', type: 'контейнер' });
});

test('третья рамка через N и 3 становится мусором бака', async () => {
    await drawWithN(0.30, 0.10, 0.40, 0.20);
    await hoverInside(0.35, 0.15);
    await page.keyboard.press('Digit3');
    await page.waitForTimeout(500);
    assert.deepEqual((await boxes()).map((b) => b.label).sort(), ['bin', 'bin_trash', 'ground_trash']);
});
