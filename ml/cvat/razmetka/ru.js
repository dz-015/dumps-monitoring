// Русские надписи интерфейса CVAT 2.77 для разметки (октябрь 2026).
//
// У CVAT нет русского языка. Скрипт подменяет только видимый текст
// (текстовые узлы страницы и подсказки title/placeholder) на месте, не
// пересоздавая элементы: React продолжает работать со своими узлами, а
// значения в данных остаются прежними — в выгрузке разметки будут bin,
// bin_trash и ground_trash.
//
// Переводятся только надписи из словаря ниже — их собрал обход экранов,
// которые видит разметчик (test/ru.e2e.test.mjs). Новая надпись CVAT
// останется английской, а не сломается.
//
// nginx отдаёт этот файл вместе с tools.js одним файлом: npm run bundle.
(() => {
    'use strict';

    if (window.__razmetkaRu) return;

    // Метки и атрибуты — в подписях рамок, боковой панели, списках.
    const LABELS = { bin: 'бак', bin_trash: 'мусор бака', ground_trash: 'мусор на земле' };
    const ATTRS = { state: 'состояние', type: 'вид' };
    const SOURCES = {
        manual: 'вручную', auto: 'модель', 'semi-auto': 'модель, исправлено', file: 'файл', consensus: 'консенсус',
    };
    // Действия в истории правок — для подсказок «Отменить: …» и «Повторить: …».
    const HISTORY = {
        'Changed label': 'смена метки',
        'Changed attributes': 'смена атрибутов',
        'Changed points': 'перемещение рамки',
        'Object rotated': 'поворот рамки',
        'Changed outside': 'смена «вне кадра»',
        'Changed occluded': 'смена «перекрыта»',
        'Changed z-order': 'смена слоя',
        'Changed keyframe': 'смена ключевого кадра',
        'Changed lock': 'закрепление',
        'Changed pinned': 'запрет перемещения',
        'Changed color': 'смена цвета',
        'Changed hidden': 'скрытие',
        'Changed source': 'смена источника',
        'Merged objects': 'объединение',
        'Grouped objects': 'группировка',
        'Created objects': 'новые рамки',
        'Removed object': 'удаление рамки',
        'Removed frame': 'удаление кадра',
        'Restored frame': 'возврат кадра',
        'Commit annotations': 'правка рамок',
    };
    const STAGES = { annotation: 'разметка', validation: 'проверка', acceptance: 'приёмка' };
    const STATES = { new: 'новое', 'in progress': 'в работе', rejected: 'отклонено', completed: 'завершено' };

    const TEXT = {
        ...LABELS,
        ...ATTRS,
        ...STAGES,
        ...STATES,
        ...Object.fromEntries(Object.entries(ATTRS).map(([k, v]) => [`${k}:`, `${v}:`])),

        // вход
        'Connecting...': 'Подключение…',
        'Sign in': 'Войти',
        'Email or username': 'Почта или логин',
        Password: 'Пароль',
        'Forgot password?': 'Забыли пароль?',
        Next: 'Войти',
        'New user?': 'Нет аккаунта?',
        'Create an account': 'Зарегистрироваться',
        'Open Data Annotation Platform': 'Платформа разметки данных',

        // верхнее меню и меню пользователя
        Projects: 'Проекты',
        Tasks: 'Задачи',
        Jobs: 'Задания',
        'Cloud Storages': 'Облачные хранилища',
        Requests: 'Запросы',
        Models: 'Модели',
        Settings: 'Настройки',
        Logout: 'Выйти',
        Profile: 'Профиль',
        About: 'О программе',
        Organization: 'Организация',
        'Press [F2] to switch': 'Переключить — [F2]',
        'Personal workspace': 'Личное пространство',
        'Admin page': 'Администрирование',

        // списки задач, заданий, проектов
        'Search ...': 'Поиск…',
        'Select all': 'Выбрать все',
        'Sort by': 'Сортировка',
        'Quick filters': 'Быстрые фильтры',
        Filter: 'Фильтр',
        'Clear filters': 'Сбросить фильтры',
        Actions: 'Действия',
        Open: 'Открыть',
        'Next Page': 'Следующая страница',
        'Go to': 'Перейти на',
        Page: 'стр.',
        'Previous Page': 'Предыдущая страница',
        'No results matched your search...': 'Ничего не найдено',
        'No data': 'Нет данных',
        'Stage and state': 'Этап и состояние',
        Frames: 'Кадров',
        Assignee: 'Исполнитель',

        // страница задачи
        'Back to project': 'Назад к проекту',
        'Assigned to': 'Исполнитель',
        'Issue Tracker': 'Трекер ошибок',
        'Subset:': 'Подмножество:',
        'Input subset': 'Подмножество',
        'Assignee:': 'Исполнитель:',
        'Created:': 'Создано:',
        Created: 'Автор:',
        'Updated:': 'Обновлено:',
        'Stage:': 'Этап:',
        'State:': 'Состояние:',
        'Duration:': 'Длительность:',
        'Frame count:': 'Кадров:',
        'Frame range:': 'Диапазон кадров:',

        // экран разметки: верхняя панель
        Menu: 'Меню',
        Save: 'Сохранить',
        Undo: 'Отменить',
        Redo: 'Повторить',
        Fullscreen: 'Весь экран',
        Info: 'Сведения',
        Filters: 'Фильтры',
        Standard: 'Обычный',
        'Attribute annotation': 'Разметка атрибутов',
        'Single shape': 'По одной фигуре',
        'Tag annotation': 'Разметка тегов',
        Review: 'Проверка',
        'Go back': 'Предыдущий кадр',
        // C занята копированием рамок (tools.js), поэтому без клавиши
        'Go back with a step [C]': 'Назад на несколько кадров',
        'Go next': 'Следующий кадр',
        'Go next with a step': 'Вперёд на несколько кадров',
        'Go to the first frame': 'К первому кадру',
        'Go to the last frame': 'К последнему кадру',
        Play: 'Воспроизвести',
        Pause: 'Пауза',
        'Save current changes': 'Сохранить изменения',
        'Copy frame filename': 'Скопировать имя файла',
        'Create frame URL': 'Скопировать ссылку на кадр',
        'Delete the frame': 'Удалить кадр из задания',
        'Restore the frame': 'Вернуть кадр',
        'Search frame by name': 'Найти кадр по имени',

        // меню задания
        'Change job state': 'Изменить состояние задания',
        'Export job dataset': 'Выгрузить разметку задания',
        'Finish the job': 'Завершить задание',
        'Open the task': 'Открыть задачу',
        'Remove annotations': 'Удалить всю разметку',
        'Run actions': 'Запустить действия',
        'Upload annotations': 'Загрузить разметку из файла',
        'Would you like to finish the job?': 'Завершить задание?',
        'It will save annotations and set the job state to "completed"':
            'Разметка сохранится, задание получит состояние «завершено»',
        Cancel: 'Отмена',
        Continue: 'Продолжить',
        OK: 'ОК',
        Close: 'Закрыть',

        Circle: 'Круг',
        Hide: 'Скрыть',

        // левая панель инструментов
        Cursor: 'Курсор',
        'Move the image': 'Двигать изображение',
        'Rotate the image': 'Повернуть изображение',
        'Fit the image [Double Click]': 'Вписать изображение [двойной щелчок]',
        'Select a region of interest': 'Увеличить выбранную область',
        'Draw a rectangle': 'Нарисовать рамку',
        'Draw a polygon': 'Нарисовать многоугольник',
        'Draw a polyline': 'Нарисовать ломаную',
        'Draw points': 'Поставить точки',
        'Draw an ellipse': 'Нарисовать эллипс',
        'Draw a cuboid': 'Нарисовать кубоид',
        'Draw a mask': 'Нарисовать маску',
        'Create a tag': 'Поставить тег',
        'OpenCV tools': 'Инструменты OpenCV',
        'AI Tools': 'Инструменты ИИ',
        'Snap tools': 'Привязка к точкам',
        'Merge shapes/tracks': 'Объединить фигуры',
        'Group shapes [G] Select and press [Shift+G] to reset a group.':
            'Сгруппировать фигуры [G]. Чтобы сбросить группу — выделить и нажать [Shift+G]',
        'Split a track': 'Разделить трек',
        'Join tool': 'Склеить маски',
        'Slice a mask/polygon shape': 'Разрезать маску или многоугольник',

        // окно «нарисовать рамку»
        'Draw new rectangle': 'Новая рамка',
        'Drawing method': 'Как рисовать',
        '2 Points': '2 угла',
        '4 Points': '4 точки',
        Rotated: 'Повёрнутая',
        Shape: 'Фигура',
        Track: 'Трек',

        // правая панель
        Objects: 'Объекты',
        Labels: 'Метки',
        Issues: 'Замечания',
        'ID - ascent': 'Номер ↑',
        'ID - descent': 'Номер ↓',
        'Updated time': 'Время изменения',
        'Z Order': 'Слой',
        'RECTANGLE SHAPE': 'РАМКА',
        'RECTANGLE TRACK': 'РАМКА-ТРЕК',
        DETAILS: 'ПОДРОБНО',
        Details: 'Подробно',
        Appearance: 'Вид',
        'Color by': 'Цвет',
        Label: 'Метка',
        Instance: 'Объект',
        Group: 'Группа',
        Opacity: 'Непрозрачность',
        'Selected opacity': 'Непрозрачность выделенной',
        'Outlined borders': 'Обвести рамки',
        'Show bitmap': 'Растровый вид',
        'Show projections': 'Проекции',
        'Hold Shift to snap angle': 'Удерживайте Shift, чтобы поворачивать с шагом',
        'Switch lock property': 'Закрепить рамку',
        'Switch lock property for all': 'Закрепить все рамки',
        // Q занята видом бака (tools.js), поэтому без клавиши
        'Switch occluded property [Q]': 'Рамка перекрыта другим объектом',
        'Switch occluded property [Q, /]': 'Рамка перекрыта другим объектом [/]',
        'Switch hidden property': 'Скрыть рамку',
        'Switch hidden property for all': 'Скрыть все рамки',
        'Switch pinned property': 'Запретить перемещение',
        'Switch outside property': 'Объект вне кадра',
        'Switch keyframe property': 'Ключевой кадр',
        'Expand/collapse all': 'Развернуть или свернуть все',
        'Change color': 'Сменить цвет',

        // меню рамки (⋮)
        'Create object URL': 'Скопировать ссылку на рамку',
        'Make a copy': 'Сделать копию',
        'Move to layer ...': 'Переместить на слой…',
        Orientation: 'Ориентация',
        Propagate: 'Размножить на кадры',
        Remove: 'Удалить',
        'Run annotation action': 'Запустить действие',
        'To background': 'На задний план',
        'To foreground': 'На передний план',
        'To one layer backward': 'На слой назад',
        'To one layer forward': 'На слой вперёд',

        // сведения о задании
        Overview: 'Обзор',
        'Annotations statistics': 'Статистика разметки',
        'Start frame': 'Первый кадр',
        'Stop frame': 'Последний кадр',
        Total: 'Всего',
        Rectangle: 'Рамки',
        Polygon: 'Многоугольники',
        Polyline: 'Ломаные',
        Points: 'Точки',
        Ellipse: 'Эллипсы',
        Cuboid: 'Кубоиды',
        Skeleton: 'Скелеты',
        Mask: 'Маски',
        Tag: 'Теги',
        Manually: 'Вручную',
        Interpolated: 'Интерполировано',
        Nobody: 'никто',
        'Select a user': 'Выберите исполнителя',

        // окно фильтров
        'Add group': 'Добавить группу',
        'Add rule': 'Добавить условие',
        Elements: 'Элементы',
        'Recently used': 'Недавние',
        Submit: 'Применить',
        AND: 'И',
        OR: 'ИЛИ',
        NOT: 'НЕ',
        'ID:': 'Номер:',

        // настройки
        Player: 'Просмотр',
        Workspace: 'Рабочая область',
        Shortcuts: 'Горячие клавиши',
        'Fit image after changing frame': 'Вписывать изображение при смене кадра',
        'Number of frames skipped when selecting': 'Сколько кадров пропускать при переходе',
        'Player speed': 'Скорость воспроизведения',
        'Player step': 'Шаг перехода',
        'Reset zoom': 'Сбрасывать масштаб',
        'Rotate all images': 'Поворачивать все изображения',
        'Rotate all images simultaneously': 'Поворачивать все изображения разом',
        'Select canvas background color': 'Цвет фона под кадром',
        'Show deleted frames': 'Показывать удалённые кадры',
        'You will be able to navigate and restore deleted frames': 'Удалённые кадры можно будет открыть и вернуть',
        'Smooth image': 'Сглаживать изображение',
        'Smooth image when zoom-in it': 'Сглаживать изображение при увеличении',
        Usual: 'Обычная',
        or: 'или',
        minutes: 'мин',
        'Enable auto save': 'Автосохранение',
        'Auto save every': 'Сохранять каждые',
        'Show all interpolation tracks': 'Показывать все интерполированные треки',
        'Show hidden interpolated objects in the side panel': 'Показывать скрытые интерполированные объекты на панели',
        'Always show object details': 'Всегда показывать подписи рамок',
        'Show text for an object on the canvas not only when the object is activated':
            'Подписи рамок видны не только у выделенной рамки',
        'Content of a text': 'Что писать в подписи',
        'Position of a text': 'Где писать подпись',
        Auto: 'Авто',
        'Font size of a text': 'Размер шрифта подписи',
        ID: 'Номер',
        Attributes: 'Атрибуты',
        Source: 'Источник',
        Descriptions: 'Описания',
        Dimensions: 'Размеры',
        'Adaptive zoom algorithm': 'Плавный масштаб',
        'Enable smoother version of zooming, compatible with a trackpad and pinch gestures':
            'Плавное масштабирование, удобно на тачпаде',
        'Focused object padding': 'Отступ вокруг рамки при наведении',
        'Adds extra space in pixels around an object when it gets fitted': 'Сколько пикселей оставить вокруг рамки',
        'Control points size': 'Размер угловых точек',
        'Default polygon simplification threshold': 'Порог упрощения многоугольников',
        'Higher values preserve more polygon detail. Used for serverless interactors, OpenCV scissors, and polygon simplification':
            'Чем больше, тем точнее многоугольник',
        'Intelligent polygon cropping': 'Умная обрезка многоугольников',
        'Try to crop polygons automatically when editing': 'Обрезать многоугольники при правке',
        'Show tags on frame': 'Показывать теги на кадре',
        'Show frame tags in the corner of the workspace': 'Теги кадра — в углу рабочей области',
        'Restore Defaults': 'Вернуть по умолчанию',
        General: 'Общие',
        'Search for a shortcut here...': 'Поиск клавиши…',
    };

    // ── составные надписи ────────────────────────────────────────────────

    const MONTHS = [
        ['January', 'Jan', 'января', 'янв.'], ['February', 'Feb', 'февраля', 'февр.'], ['March', 'Mar', 'марта', 'мар.'],
        ['April', 'Apr', 'апреля', 'апр.'], ['May', 'May', 'мая', 'мая'], ['June', 'Jun', 'июня', 'июн.'],
        ['July', 'Jul', 'июля', 'июл.'], ['August', 'Aug', 'августа', 'авг.'], ['September', 'Sep', 'сентября', 'сент.'],
        ['October', 'Oct', 'октября', 'окт.'], ['November', 'Nov', 'ноября', 'нояб.'], ['December', 'Dec', 'декабря', 'дек.'],
    ];
    const DATE = '(January|February|March|April|May|June|July|August|September|October|November|December|' +
        'Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\\d{1,2})(?:st|nd|rd|th) (\\d{4})';

    function date(month, day, year) {
        const m = MONTHS.find(([full, short]) => month === full || month === short);
        return `${day} ${month === m[0] ? m[2] : m[3]} ${year}`;
    }

    function plural(n, one, few, many) {
        const d10 = n % 10;
        const d100 = n % 100;
        if (d10 === 1 && d100 !== 11) return one;
        if (d10 >= 2 && d10 <= 4 && (d100 < 12 || d100 > 14)) return few;
        return many;
    }

    // Длительность в духе moment.humanize(): «a few seconds», «an hour», «2 hours».
    const UNITS = {
        second: ['секунда', 'секунды', 'секунд'], minute: ['минута', 'минуты', 'минут'], hour: ['час', 'часа', 'часов'],
        day: ['день', 'дня', 'дней'], month: ['месяц', 'месяца', 'месяцев'], year: ['год', 'года', 'лет'],
    };
    const DURATION = '(a few seconds|an? (?:second|minute|hour|day|month|year)|\\d+ (?:seconds|minutes|hours|days|months|years))';

    function duration(text) {
        if (text === 'a few seconds') return 'несколько секунд';
        const one = text.match(/^an? (\w+)$/);
        if (one) return UNITS[one[1]][0];
        const [, n, unit] = text.match(/^(\d+) (\w+?)s$/);
        return `${n} ${plural(Number(n), ...UNITS[unit])}`;
    }

    const SOURCE_RE = Object.keys(SOURCES).join('|');
    const LABEL_RE = Object.keys(LABELS).join('|');
    const ATTR_RE = Object.keys(ATTRS).join('|');
    const STAGE_RE = Object.keys(STAGES).join('|');
    const STATE_RE = Object.keys(STATES).join('|');

    const PATTERNS = [
        [new RegExp(`^${DURATION}$`), (m) => duration(m[1])],
        [new RegExp(`^Last updated ${DURATION} ago$`), (m) => `Обновлено ${duration(m[1])} назад`],
        [new RegExp(`^Created by (.+) on ${DATE}$`), (m) => `Автор: ${m[1]}, ${date(m[2], m[3], m[4])}`],
        [new RegExp(`^Task #(\\d+) Created by (.+) on ${DATE}$`),
            (m) => `Задача №${m[1]}. Автор: ${m[2]}, ${date(m[3], m[4], m[5])}`],
        [new RegExp(`^${DATE}( \\d{1,2}:\\d{2})?$`), (m) => date(m[1], m[2], m[3]) + (m[4] || '')],
        [/^Job #(\d+)$/, (m) => `Задание №${m[1]}`],
        [/^Task #(\d+)$/, (m) => `Задача №${m[1]}`],
        [/^Items: (\d+)$/, (m) => `Рамок: ${m[1]}`],
        [/^(\d+) \/ page$/, (m) => `${m[1]} / стр.`],
        [/^• (\d+) annotating$/, (m) => `• в разметке: ${m[1]}`],
        [/^• (\d+) validation$/, (m) => `• на проверке: ${m[1]}`],
        [/^• (\d+) completed$/, (m) => `• завершено: ${m[1]}`],
        [/^• (\d+) total$/, (m) => `• всего: ${m[1]}`],
        [new RegExp(`^(${STAGE_RE}) (${STATE_RE})$`), (m) => `${STAGES[m[1]]}, ${STATES[m[2]]}`],
        // подпись рамки на кадре: «bin 12 (manual)», «state: ok»
        [new RegExp(`^(${LABEL_RE}) (\\d+) \\((${SOURCE_RE})\\)$`), (m) => `${LABELS[m[1]]} ${m[2]} (${SOURCES[m[3]]})`],
        [new RegExp(`^(${ATTR_RE}): (.*)$`), (m) => `${ATTRS[m[1]]}: ${m[2]}`],
        [/^(Undo|Redo): (.+?) (\[[^\]]+\])$/,
            (m) => `${m[1] === 'Undo' ? 'Отменить' : 'Повторить'}: ${HISTORY[m[2]] || m[2]} ${m[3]}`],
        // «Created» и «by arseniy» на карточке проекта — два отдельных куска текста
        [/^by (\S+)$/, (m) => m[1]],
        // подсказка с клавишей: «Go back [D]» — текст по словарю, клавиша как есть
        [/^(.+?) (\[[^\]]+\])$/, (m) => (m[1] in TEXT ? `${TEXT[m[1]]} ${m[2]}` : null)],
    ];

    function translate(value) {
        const text = value.trim();
        if (!/[A-Za-z]/.test(text)) return null;
        let out = Object.prototype.hasOwnProperty.call(TEXT, text) ? TEXT[text] : null;
        for (let i = 0; out === null && i < PATTERNS.length; i++) {
            const m = text.match(PATTERNS[i][0]);
            if (m) out = PATTERNS[i][1](m);
        }
        if (out === null) return null;
        const start = value.indexOf(text);
        return value.slice(0, start) + out + value.slice(start + text.length);
    }

    window.__razmetkaRu = { translate };
    if (typeof document === 'undefined') return;

    // ── страница ─────────────────────────────────────────────────────────

    const ATTRIBUTES = ['title', 'placeholder'];

    // Кнопки верхней панели (48px) и меню задания (248px) у CVAT по ширине
    // английских слов. Русские длиннее, поэтому они растягиваются под текст.
    const STYLE = '.cvat-annotation-header-button{width:auto!important;min-width:48px;padding:0 4px!important}' +
        '.cvat-annotation-menu{width:auto!important}' +
        '.cvat-annotation-menu .ant-dropdown-menu-item,.cvat-annotation-menu .ant-dropdown-menu-submenu-title{white-space:nowrap}';

    function fixText(node) {
        const parent = node.parentElement;
        if (!parent || parent.closest('script, style, textarea, [contenteditable="true"]')) return;
        const out = translate(node.nodeValue);
        if (out !== null) node.nodeValue = out;
    }

    function fixAttributes(el) {
        for (const name of ATTRIBUTES) {
            const value = el.getAttribute(name);
            const out = value && translate(value);
            if (out) el.setAttribute(name, out);
        }
    }

    function fixTree(root) {
        if (root.nodeType === Node.TEXT_NODE) return fixText(root);
        if (root.nodeType !== Node.ELEMENT_NODE) return null;
        fixAttributes(root);
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (node.nodeType === Node.TEXT_NODE) fixText(node);
            else fixAttributes(node);
        }
        return null;
    }

    function start() {
        const style = document.createElement('style');
        style.id = 'razmetka-ru-style';
        style.textContent = STYLE;
        document.head.appendChild(style);
        fixTree(document.body);
        new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.type === 'characterData') fixText(m.target);
                else if (m.type === 'attributes') fixAttributes(m.target);
                else m.addedNodes.forEach(fixTree);
            }
        }).observe(document.body, {
            subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTES,
        });
    }

    if (document.body) start();
    else document.addEventListener('DOMContentLoaded', start);
})();
