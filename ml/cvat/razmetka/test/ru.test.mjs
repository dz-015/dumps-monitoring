// Проверка словаря перевода без браузера: ru.js выполняется в пустом окружении.
//
//   node --test test/ru.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync(path.resolve(HERE, '../ru.js'), 'utf-8'), sandbox);
const { translate } = sandbox.window.__razmetkaRu;

test('простые надписи переводятся целиком', () => {
    assert.equal(translate('Jobs'), 'Задания');
    assert.equal(translate('Finish the job'), 'Завершить задание');
});

test('пробелы вокруг надписи сохраняются', () => {
    assert.equal(translate('  Save '), '  Сохранить ');
});

test('русский текст, имена файлов и неизвестные надписи не трогаются', () => {
    assert.equal(translate('Пачка 1 — razmetchik1'), null);
    assert.equal(translate('camw41_2026-10-04_105116.jpg'), null);
    assert.equal(translate('razmetchik1'), null);
    assert.equal(translate('Something new from CVAT'), null);
});

test('метки и атрибуты — по-русски', () => {
    assert.equal(translate('bin'), 'бак');
    assert.equal(translate('ground_trash'), 'мусор на земле');
    assert.equal(translate('bin_trash'), 'мусор бака');
    assert.equal(translate('state'), 'состояние');
    assert.equal(translate('type:'), 'вид:');
});

test('подписи рамок на кадре', () => {
    assert.equal(translate('bin 12 (manual)'), 'бак 12 (вручную)');
    assert.equal(translate('ground_trash 3 (auto)'), 'мусор на земле 3 (модель)');
    assert.equal(translate('bin_trash 7 (manual)'), 'мусор бака 7 (вручную)');
    assert.equal(translate('state: переполнено'), 'состояние: переполнено');
    assert.equal(translate('type: евробак'), 'вид: евробак');
});

test('подсказка с клавишей: переводится текст, клавиша остаётся', () => {
    assert.equal(translate('Go back [D]'), 'Предыдущий кадр [D]');
    assert.equal(translate('Cursor [Esc]'), 'Курсор [Esc]');
});

test('C больше не листает назад — в подсказке её нет', () => {
    assert.equal(translate('Go back with a step [C]'), 'Назад на несколько кадров');
});

test('даты и «сколько времени назад»', () => {
    assert.equal(translate('Created by arseniy on October 5th 2026'), 'Автор: arseniy, 5 октября 2026');
    assert.equal(translate('Oct 5th 2026 17:27'), '5 окт. 2026 17:27');
    assert.equal(translate('Last updated 2 hours ago'), 'Обновлено 2 часа назад');
    assert.equal(translate('Last updated an hour ago'), 'Обновлено час назад');
    assert.equal(translate('Last updated 5 minutes ago'), 'Обновлено 5 минут назад');
    assert.equal(translate('Last updated a few seconds ago'), 'Обновлено несколько секунд назад');
    assert.equal(translate('a few seconds'), 'несколько секунд');
    assert.equal(translate('21 days'), '21 день');
});

test('составные надписи списков', () => {
    assert.equal(translate('Job #23'), 'Задание №23');
    assert.equal(translate('Task #23 Created by arseniy on October 5th 2026'), 'Задача №23. Автор: arseniy, 5 октября 2026');
    assert.equal(translate('• 1 annotating'), '• в разметке: 1');
    assert.equal(translate('• 8 total'), '• всего: 8');
    assert.equal(translate('annotation new'), 'разметка, новое');
    assert.equal(translate('Items: 2'), 'Рамок: 2');
    assert.equal(translate('10 / page'), '10 / стр.');
});

test('подсказки отмены и повтора: действие по-русски, клавиши как есть', () => {
    assert.equal(translate('Undo: Changed attributes [Ctrl+Z]'), 'Отменить: смена атрибутов [Ctrl+Z]');
    assert.equal(translate('Redo: Commit annotations [Ctrl+Shift+Z, Ctrl+Y]'), 'Повторить: правка рамок [Ctrl+Shift+Z, Ctrl+Y]');
});
