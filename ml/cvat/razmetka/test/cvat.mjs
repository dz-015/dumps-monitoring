// Общее для проверок в браузере: API живого CVAT, временный проект, вход.
//
// LOCAL_TOOLS=1 — вставлять ru.js и tools.js из рабочей копии (для отладки);
// без него проверяется ровно то, что nginx отдаёт разметчикам.

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const BASE = process.env.CVAT_URL || 'https://leti-metla.ru:8443';
const USER = process.env.CVAT_USER;
const PASSWORD = process.env.CVAT_PASSWORD;
export const RAW = path.resolve(HERE, '../../../data/round2/raw');
const AUTH = 'Basic ' + Buffer.from(`${USER}:${PASSWORD}`).toString('base64');

export const LABELS = [
    {
        name: 'bin',
        attributes: [
            {
                name: 'state', mutable: true, input_type: 'select', default_value: 'не указано',
                values: ['не указано', 'не переполнен', 'переполнено'],
            },
            {
                name: 'type', mutable: true, input_type: 'select', default_value: 'не указан',
                values: ['не указан', 'евробак', 'контейнер', 'бутылки'],
            },
        ],
    },
    { name: 'bin_trash', attributes: [] },
    { name: 'ground_trash', attributes: [] },
];

export async function api(method, url, body, headers = {}) {
    const isForm = body instanceof FormData;
    const res = await fetch(BASE + url, {
        method,
        headers: { Authorization: AUTH, ...(body && !isForm ? { 'Content-Type': 'application/json' } : {}), ...headers },
        body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`${method} ${url} → ${res.status}: ${text.slice(0, 300)}`);
    return text ? JSON.parse(text) : null;
}

// Временный проект с метками разметки №2 и заданием из кадров `files` (из RAW).
// Возвращает { project, task, jobId, L }, где L: имя метки → {id, attrs: {имя: id}}.
export async function createTestJob(projectName, files) {
    assert.ok(USER && PASSWORD, 'задайте CVAT_USER и CVAT_PASSWORD');
    const project = await api('POST', '/api/projects', { name: projectName, labels: LABELS });
    const L = {};
    const labels = await api('GET', `/api/labels?project_id=${project.id}&page_size=100`);
    for (const l of labels.results) {
        L[l.name] = { id: l.id, attrs: Object.fromEntries(l.attributes.map((a) => [a.name, a.id])) };
    }

    const task = await api('POST', '/api/tasks', { name: 'тест', project_id: project.id });
    const form = new FormData();
    form.append('image_quality', '70');
    form.append('sorting_method', 'natural');
    files.forEach((name, i) => {
        form.append(`client_files[${i}]`, new Blob([fs.readFileSync(path.join(RAW, name))]), name);
    });
    const { rq_id: rq } = await api('POST', `/api/tasks/${task.id}/data`, form);
    for (let i = 0; ; i++) {
        const r = await api('GET', `/api/requests/${rq}`);
        if (r.status === 'finished') break;
        if (r.status === 'failed' || i > 120) throw new Error(`загрузка кадров: ${JSON.stringify(r).slice(0, 300)}`);
        await new Promise((ok) => setTimeout(ok, 1000));
    }
    const jobId = (await api('GET', `/api/jobs?task_id=${task.id}`)).results[0].id;
    return { project, task, jobId, L };
}

export function box(L, label, frame, points, attrs = {}) {
    return {
        type: 'rectangle', frame, label_id: L[label].id, group: 0, source: 'manual',
        occluded: false, outside: false, rotation: 0, z_order: 0, elements: [], points,
        attributes: Object.entries(attrs).map(([name, value]) => ({ spec_id: L[label].attrs[name], value })),
    };
}

export async function newBrowserPage() {
    const browser = await chromium.launch();
    const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
    if (process.env.LOCAL_TOOLS) {
        await context.addInitScript({ path: path.resolve(HERE, '../ru.js') });
        await context.addInitScript({ path: path.resolve(HERE, '../tools.js') });
    }
    const page = await context.newPage();
    page.on('pageerror', (e) => console.error('ошибка страницы:', e.message));
    return { browser, page };
}

export async function login(page) {
    await page.goto(`${BASE}/auth/login`);
    await page.fill('input[id$="credential"]', USER);
    await page.fill('input[type=password]', PASSWORD);
    await page.click('button[type=submit]');
    await page.waitForURL((u) => !u.pathname.startsWith('/auth'));
}

export async function openJob(page, taskId, jobId) {
    await page.goto(`${BASE}/tasks/${taskId}/jobs/${jobId}`);
    await page.waitForFunction(() => {
        const s = window.__razmetkaTools && window.__razmetkaTools.store();
        return s && s.getState().annotation.annotations.initialized;
    }, null, { timeout: 60000 });
}
