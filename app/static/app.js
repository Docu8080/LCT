'use strict';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = (x) =>
  String(x ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
const money = (x) => Number(x || 0).toLocaleString('ru-RU');
const salary = (p) => `${money(p.salary_from)}–${money(p.salary_to)} ₽`;
const date = (x) =>
  new Date(x * 1000).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
const fmt = { remote: 'Удалённо', hybrid: 'Гибрид', office: 'В офисе' };
const candidateFormats = { ...fmt, any: 'Любой формат' };
const specs = { backend: 'Бэкенд-разработка', frontend: 'Фронтенд-разработка' };
const statusText = {
  sent: 'Отправлено',
  viewed: 'Просмотрено',
  accepted: 'Принято',
  declined: 'Отклонено',
  withdrawn: 'Отозвано',
  expired: 'Истекло',
  assigned: 'К выполнению',
  submitted: 'На проверке',
  reviewed: 'Проверено',
};
const paths = {
  menu: 'M4 7h16M4 12h16M4 17h16',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  list: 'M8 5h13M8 12h13M8 19h13M3 5h1M3 12h1M3 19h1',
  home: 'M3 10 12 3l9 7M5 9v11h14V9M9 20v-7h6v7',
  profile: 'M20 21v-2a7 7 0 0 0-14 0v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
  test: 'M9 5H6v16h14V5h-3M9 3h8v4H9zM9 12h7M9 16h4',
  mail: 'M3 6h18v13H3zM3 6l9 7 9-7',
  tasks: 'M4 5h16v15H4zM4 9h16M8 3v4M16 3v4M8 13h3M8 16h6',
  jobs: 'M3 7h18v13H3zM8 7V3h8v4M3 12h18M10 12v3h4v-3',
  settings:
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M9 3h6l1 3 3 1 2 5-2 4-3 1-1 4H9l-1-4-3-1-2-4 2-5 3-1z',
  search: 'M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15M16 16l5 5',
  bell: 'M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zM10 21h4',
  arrow: 'M4 12h16M14 6l6 6-6 6',
  check: 'M5 12l4 4L19 6',
  shield: 'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6',
  logout: 'M10 4H4v16h6M10 12h11M17 8l4 4-4 4',
  close: 'M6 6l12 12M6 18 18 6',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 7v5l3 2',
  download: 'M12 3v12M7 10l5 5 5-5M4 16v5h16v-5',
  star: 'm12 3 3 6 6 1-4 5 1 6-6-3-6 3 1-6-4-5 6-1z',
  plus: 'M12 4v16M4 12h16',
  chart: 'M4 20V9M10 20V4M16 20v-7M22 20H2',
  company: 'M4 21V3h12v18M16 9h5v12M8 7h4M8 11h4M8 15h4',
  lock: 'M5 10h14v11H5zM8 10V7a4 4 0 0 1 8 0v3',
  code: 'M8 6l-6 6 6 6M16 6l6 6-6 6M14 3l-4 18',
  refresh: 'M20 8a8 8 0 1 0 1 7M20 3v5h-5',
};
const icon = (n) =>
  `<svg class="svgicon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[n] || paths.star}"/></svg>`;
const brand = (cls = '') =>
  `<a class="brand ${cls}" href="/#home" aria-label="Таланты ФСП — главная"><img src="/static/mark.svg?v=20261011-icon1" width="40" height="40" alt=""><span>таланты<span class="brand-dot">/</span><small>КАРЬЕРНАЯ ПЛАТФОРМА ФСП</small></span></a>`;
const btn = (label, action, style = 'secondary', data = '', ic = '') =>
  `<button type="button" class="${style}" data-action="${action}" ${data}>${ic ? icon(ic) : ''}${label}</button>`;
const chips = (skills, verified = []) =>
  `<div class="chips">${(skills || []).map((s) => `<span class="chip ${verified.includes(s) ? 'verified' : ''}">${esc(s)}</span>`).join('')}</div>`;
const badge = (text, cls = '') => `<span class="pill ${cls}">${esc(text)}</span>`;
const stateBadge = (s) => badge(statusText[s] || s, 'status-' + s);
const empty = (title, description = '', action = '') =>
  `<div class="empty"><div class="emptyicon">${icon('search')}</div><h3>${esc(title)}</h3><p>${esc(description)}</p>${action}</div>`;
const notice = (text, cls = '') => `<div class="notice ${cls}">${text}</div>`;
const field = (label, name, value = '', type = 'text', extra = '') =>
  `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
const area = (label, name, value = '', extra = '') =>
  `<label>${label}<textarea name="${name}" ${extra}>${esc(value)}</textarea></label>`;
const select = (label, name, values, selected = '', extra = '') =>
  `<label>${label}<select name="${name}" ${extra}>${Object.entries(values)
    .map(
      ([v, t]) =>
        `<option value="${esc(v)}" ${String(selected) === v ? 'selected' : ''}>${esc(t)}</option>`
    )
    .join('')}</select></label>`;
const check = (label, name, checked = false, extra = '') =>
  `<label class="check"><input type="checkbox" name="${name}" ${checked ? 'checked' : ''} ${extra}><span>${label}</span></label>`;
const formError = '<div class="formerror" role="alert"></div>';
const pagehead = (eyebrow, title, sub = '', actions = '') =>
  `<div class="pagehead between"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p class="subtitle">${sub}</p></div>${actions ? `<div class="flex wrap">${actions}</div>` : ''}</div>`;
const metric = (title, value, sub, ic = 'chart') =>
  `<div class="card metric"><div><p>${title}</p><strong>${value}</strong><small>${sub}</small></div><div class="metricicon">${icon(ic)}</div></div>`;
let demoEnabled = false;
let user = null,
  route = '',
  authMode = 'login',
  authRole = 'candidate',
  verifyEmail = '',
  verifyCode = '',
  profileData = null,
  needs = [],
  matches = [],
  invitationsData = [],
  tasks = [],
  attempt = null,
  questionIndex = 0,
  timer = null,
  renderGeneration = 0,
  saveQueue = Promise.resolve(),
  pendingSaves = 0;
let toastTimer;
function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 4500);
}
async function api(path, options = {}) {
  const res = await fetch('/api' + path, {
    credentials: 'same-origin',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(user ? { 'X-CSRF-Token': user.csrf } : {}),
      ...options.headers,
    },
    ...(options.body && typeof options.body !== 'string' && !(options.body instanceof Blob)
      ? { body: JSON.stringify(options.body) }
      : {}),
  });
  const data = await res.json().catch(() => {
    throw new Error('Сервер вернул неожиданный ответ. Повторите попытку.');
  });
  if (!res.ok) {
    const message = Array.isArray(data.detail)
      ? data.detail.map((x) => `${x.loc.at(-1)}: ${x.msg}`).join(';')
      : data.detail || 'Не удалось выполнить действие';
    throw new Error(message);
  }
  return data;
}
const post = (path, body = {}) => api(path, { method: 'POST', body });
const put = (path, body) => api(path, { method: 'PUT', body });
const patch = (path, body) => api(path, { method: 'PATCH', body });
const del = (path) => api(path, { method: 'DELETE' });
function modal(title, body) {
  $('#modal').innerHTML =
    `<div class="modalhead"><h2 id="dialog-title">${title}</h2>${btn('', 'close', '', '', 'close').replace('<button', '<button aria-label="Закрыть"')}</div><div class="modalbody">${body}</div>`;
  $('#modal').setAttribute('aria-labelledby', 'dialog-title');
  $('#modal').showModal();
}
function closeModal() {
  $('#modal').close();
}
function go(path) {
  location.hash = path;
}
function initials(name) {
  return name
    .split(/\s+/)
    .filter((x) => /[a-zа-яё]/i.test(x))
    .slice(0, 2)
    .map((x) => x[0])
    .join('')
    .toUpperCase();
}
function getRoute() {
  return (
    location.hash.slice(1).split('?')[0] ||
    (location.pathname !== '/'
      ? location.pathname.replace(/^\/|\/$/g, '')
      : user
        ? user.role === 'employer'
          ? 'matching'
          : 'overview'
        : 'home')
  );
}
const candidateNav = [
  ['overview', 'Обзор', 'home'],
  ['profile', 'Мой профиль', 'profile'],
  ['tests', 'Подтвердить навыки', 'test'],
  ['invitations', 'Приглашения', 'mail'],
  ['tasks', 'Задания недели', 'tasks'],
  ['jobs', 'Вакансии', 'jobs'],
  ['settings', 'Приватность', 'settings'],
];
const employerNav = [
  ['matching', 'Подбор талантов', 'search'],
  ['needs', 'Потребности', 'jobs'],
  ['invitations', 'Приглашения', 'mail'],
  ['tasks', 'Задания недели', 'tasks'],
  ['company', 'Компания', 'company'],
  ['settings', 'Данные аккаунта', 'settings'],
];
function shell() {
  const candidate = user.role === 'candidate';
  const nav = candidate ? candidateNav : employerNav;
  const title = nav.find((x) => x[0] === route)?.[1] || 'Страница';
  $('#app').innerHTML =
    `<a href="#main-content" class="skip-link">К содержимому</a><div class="app-layout"><aside class="sidebar" id="workspace-nav">${brand()}<div class="workspace-label"><span class="workspace-mark">${icon(candidate ? 'profile' : 'company')}</span><div>${candidate ? 'Личный кабинет' : 'Кабинет компании'}<small>${candidate ? 'Ваш профессиональный рост' : 'Люди для вашей команды'}</small></div></div><div class="navlabel">${candidate ? 'МОЯ КАРЬЕРА' : 'РАБОЧЕЕ ПРОСТРАНСТВО'}</div><nav aria-label="Основная навигация">${nav.map(([r, t, i]) => `<a class="navlink ${route === r ? 'active' : ''}" ${route === r ? 'aria-current="page"' : ''} href="#${r}">${icon(i)}<span>${t}</span>${route === r ? '<span class="nav-dot"></span>' : ''}</a>`).join('')}</nav><div class="sidebottom"><div class="sidehint">${icon('shield')}<strong>Навыки говорят за вас</strong><p>${candidate ? 'Подтвердите категорию и откройте новые возможности.' : 'Приглашайте специалистов с подтверждёнными навыками.'}</p><a href="#${candidate ? 'tests' : 'needs'}">${candidate ? 'Пройти тест' : 'Создать потребность'} ${icon('arrow')}</a></div><a class="side-help" href="#help">${icon('code')} Помощь и ответы</a><div class="sideuser flex"><div class="avatar">${esc(initials(user.name))}</div><div><div class="name">${esc(user.name)}</div><small>${candidate ? 'Участник' : 'Работодатель'}</small></div>${btn('', 'logout', 'side-logout', 'aria-label="Выйти"', 'logout')}</div></div></aside><main class="mainarea" id="main-content" tabindex="-1"><header class="topbar">${btn('', 'mobile-menu', 'iconbtn menu-toggle', 'aria-label="Открыть меню" aria-controls="workspace-nav" aria-expanded="false"', 'menu')}${brand('mobilebrand')}<div class="breadcrumb">${candidate ? 'Моя карьера' : 'Рабочее пространство'}<span>/</span><strong>${title}</strong></div><div class="topright">${user.browser_demo ? `<span class="demobadge">Личное демо</span>${btn('Сменить роль', 'demo-switch', 'linkbutton')}${btn('Начать заново', 'demo-reset', 'linkbutton')}` : user.demo ? '<span class="demobadge">Демо-версия</span>' : ''}<a class="top-help" href="#help">Помощь</a>${btn('', 'notifications', 'iconbtn', 'aria-label="Уведомления"', 'bell')}<div class="topavatar">${esc(initials(user.name))}</div>${btn('', 'logout', 'iconbtn mobilelogout', 'aria-label="Выйти"', 'logout')}</div></header><div class="content" id="content"><div class="loading-skeleton" role="status" aria-label="Загрузка страницы"><span></span><span></span><span></span></div></div><footer class="workspace-footer"><span>© 2026 Таланты / ФСП ${user.demo ? '· Демо-данные' : ''}</span><nav aria-label="Правовая информация"><a href="#terms">Условия</a><a href="#privacy">Приватность</a><a href="#help">Помощь</a><a href="#operator">Реквизиты</a><button class="linkbutton" type="button" data-cookie-settings>Cookie</button></nav></footer></main></div>`;
}

function landing() {
  clearInterval(timer);
  const register = authMode === 'register',
    verify = authMode === 'verify';
  const auth = `<section class="authcard"><h2>${verify ? 'Подтвердите email' : register ? 'Первый шаг к возможностям' : 'С возвращением.'}</h2><p>${verify ? `Код для ${esc(verifyEmail)}` : register ? 'Создайте профиль и начните с навыков.' : 'Войдите в своё рабочее пространство.'}</p>${!verify ? `<div class="authtabs">${btn('Участник', 'auth-role', authRole === 'candidate' ? 'active' : '', `data-role="candidate" aria-pressed="${authRole === 'candidate'}"`)}${btn('Работодатель', 'auth-role', authRole === 'employer' ? 'active' : '', `data-role="employer" aria-pressed="${authRole === 'employer'}"`)}</div>` : ''}<form data-form="${verify ? 'verify' : register ? 'register' : 'login'}">${formError}${verify ? `${verifyCode ? `<div class="demo-code"><small>В демо-среде письмо не отправляется. Ваш код:</small><strong>${esc(verifyCode)}</strong></div>` : ''}${field('Код подтверждения', 'code', '', 'text', 'required pattern="[0-9]{6}" inputmode="numeric" autocomplete="one-time-code" maxlength="6"')}` : `${register ? field('Как вас зовут', 'name', '', 'text', 'required minlength="2" maxlength="100" autocomplete="name"') : ''}${field('Email', 'email', '', 'email', 'required autocomplete="email"')}${field('Пароль', 'password', '', 'password', `required minlength="8" maxlength="128" autocomplete="${register ? 'new-password' : 'current-password'}"`)}${register ? `<fieldset class="consent-fields"><legend>Подтверждения для регистрации</legend>${check('Мне исполнилось 18 лет. Дату рождения мы не запрашиваем.', 'age_confirmed', false, 'required')}${check('Принимаю <a href="/terms" target="_blank" rel="noopener">условия использования (новая вкладка)</a>.', 'terms_accepted', false, 'required')}${check('Отдельно соглашаюсь на <a href="/consent" target="_blank" rel="noopener">обработку персональных данных (новая вкладка)</a> для работы аккаунта.', 'consent', false, 'required')}<small>Публикация профиля и передача контактов компаниям включаются отдельно. Рекламная рассылка не подключена.</small></fieldset>` : ''}`}<button>${verify ? 'Подтвердить и войти' : register ? 'Создать аккаунт' : 'Войти'}${icon('arrow')}</button></form><div class="authswitch">${verify ? btn('Вернуться ко входу', 'auth-mode', 'linkbutton', 'data-mode="login"') : `${register ? 'Уже есть аккаунт?' : 'Ещё нет аккаунта?'} ${btn(register ? 'Войти' : 'Зарегистрироваться', 'auth-mode', 'linkbutton', `data-mode="${register ? 'login' : 'register'}"`)}`}</div>${!verify ? `<div class="authswitch">${btn('Не пришёл код подтверждения?', 'resend-code', 'linkbutton')}</div><div class="demologins" ${demoEnabled ? '' : 'hidden'}><small>Посмотреть, как всё работает</small><div class="flex">${btn(authRole === 'candidate' ? 'Кабинет участника' : 'Кабинет компании', 'demo-login', 'secondary', `data-role="${authRole}"`)}${authRole === 'candidate' ? btn('Новый участник', 'demo-login', 'outline', 'data-role="fresh"') : btn('Новый сценарий', 'demo-login', 'outline', 'data-role="employer" data-reset="true"')}</div><div class="spacer"></div><div class="formnote">Личный сценарий этого браузера. Данные и реестр ФСП синтетические.</div></div>` : ''}</section>`;
  $('#app').innerHTML = publicFrame(authPage(auth, register, verify));
}

function categoriesHTML(p) {
  return p.categories.length
    ? p.categories
        .map(
          (c) =>
            `<div class="category"><div class="between">${badge('✓ Подтверждено', 'green')}${badge(c.grade)}</div><h3>${specs[c.specialization]}</h3><small>Тест ${c.score}% · ${date(c.verified_at)}</small><div class="spacer"></div>${chips(c.verified_skills)}${c.source ? `<small>${esc(c.source)}</small>` : ''}</div>`
        )
        .join('')
    : empty(
        'Пока нет подтверждённой категории',
        'Пройдите первый тест, чтобы попасть в подбор.',
        `<a class="button secondary" href="#tests">Начать тест</a>`
      );
}
function topicsHTML(topics) {
  return (topics || [])
    .map(
      (t) =>
        `<div class="topic"><span>${esc(t.name)}</span><strong>${t.score}%</strong></div><div class="bar"><span style="width:${t.score}%"></span></div>`
    )
    .join('');
}
const heroVisual = (cat) =>
  `<div class="hero-visual" aria-hidden="true"><div class="visual-card"><div class="verifiedseal">${icon('check')}</div><div class="flex"><div class="avatar lime">АМ</div><div><h3>${cat ? 'Ваши навыки' : 'Первый тест'}</h3><small>${cat ? 'Подтверждены тестом' : 'Ваш следующий шаг'}</small></div></div><div class="mini-line"></div><div class="mini-line short"></div><div class="visual-score">${cat ? cat.grade : '15'}<small>${cat ? '✓' : 'заданий'}</small></div>${badge(cat ? 'Категория подтверждена' : 'Начните с навыков', cat ? 'green' : '')}</div></div>`;
async function overview() {
  const [p, inv, notes] = await Promise.all([
    api('/candidate/profile'),
    api('/invitations'),
    api('/notifications'),
  ]);
  profileData = p;
  const active = inv.filter((i) => ['sent', 'viewed'].includes(i.status));
  const cat = p.categories[0];
  return `<div class="editorial-heading"><div><div class="eyebrow">ЛИЧНЫЙ КАБИНЕТ</div><h1>Ваши навыки.<br><em>Ваш следующий шаг.</em></h1><p>${esc(p.name.split(' ')[0])}, здесь ваши навыки превращаются в возможности.</p></div><a class="button outline" href="/api/candidate/profile.pdf" target="_blank">${icon('download')} Скачать профиль</a></div><div class="overview-layout"><section class="career-feature"><span class="eyebrow">${cat ? 'ВАШ ПАСПОРТ НАВЫКОВ' : 'НАЧНИТЕ С ГЛАВНОГО'}</span><div class="career-feature-main"><div><h2>${cat ? `${cat.grade}<br><em>${specs[cat.specialization]}</em>` : 'Покажите,<br><em>что вы умеете.</em>'}</h2><p>${cat ? 'Категория подтверждена. Следующая возможность уже может быть рядом.' : '15 заданий, чтобы превратить знания в подтверждённую категорию.'}</p></div><div class="career-seal" aria-hidden="true">${icon('shield')}</div></div><div class="career-feature-foot"><span>${cat ? `Тест · ${cat.score}%` : '30 минут / 3 темы'}</span><a href="#${active.length ? 'invitations' : 'tests'}">${active.length ? 'Открыть приглашения' : 'Подтвердить навыки'} ${icon('arrow')}</a></div></section><section class="career-stats"><div><span>Личные приглашения</span><strong>${String(active.length).padStart(2, '0')}</strong><a href="#invitations">${active.length ? 'Вас ждут в команде' : 'Новые знакомства впереди'} ↗</a></div><div><span>Категории / достижения ФСП</span><strong>${p.categories.length}<small> / ${p.achievements.length}</small></strong><a href="#profile">Открыть паспорт навыков ↗</a></div></section></div><div class="grid2 overview-details"><section class="card"><div class="section-heading">${icon('profile')}<h2>Профиль возможностей</h2>${badge(p.published ? 'В подборе' : 'Черновик', p.published ? 'green' : 'gray')}</div>${[
    ['Заполните профиль', 'Опыт, стек и ожидания', p.title && p.skills.length, 'profile'],
    ['Подтвердите категорию', 'Ваши знания на единой шкале', p.categories.length, 'tests'],
    ['Подключите достижения', 'История участия в ФСП', p.fsp_id, 'profile'],
    ['Откройтесь командам', 'Управляйте видимостью профиля', p.published, 'settings'],
  ]
    .map(
      ([t, d, done, r], i) =>
        `<a class="step" href="#${r}"><div class="stepnum ${done ? 'done' : ''}">${done ? icon('check') : String(i + 1).padStart(2, '0')}</div><div><strong>${t}</strong><small>${d}</small></div><span class="step-arrow">↗</span></a>`
    )
    .join(
      ''
    )}</section><section class="card"><div class="section-heading">${icon('chart')}<h2>Ваши сильные стороны</h2></div>${cat ? `${topicsHTML(cat.topics)}<div class="divider"></div>${chips(p.skills, cat.verified_skills)}<p class="formnote" style="margin-top:16px">Зелёным отмечены навыки, подтверждённые тестом.</p>` : empty('История начинается с вас', 'Пройдите первый тест — здесь появятся сильные стороны.', `<a class="button secondary" href="#tests">Начать</a>`)}</section></div><section class="activity-section"><div class="section-heading">${icon('bell')}<h2>Последние события</h2>${btn('Все события', 'notifications', 'linkbutton')}</div>${
    notes
      .slice(0, 3)
      .map(
        (n) =>
          `<div class="activity-row"><div class="activity-icon">${icon('bell')}</div><div><h3>${esc(n.title)}</h3><p>${esc(n.body)}</p></div><small>${date(n.created)}</small></div>`
      )
      .join('') || empty('Всё спокойно', 'Здесь появятся приглашения и результаты.')
  }</section>`;
}
async function profilePage() {
  const p = await api('/candidate/profile');
  profileData = p;
  return `${pagehead('ВАШ ПРОФИЛЬ', 'То, что делает вас сильнее', 'Компании видят навыки и достижения. Контакты доступны по вашему разрешению.', `<a class="button outline" href="/api/candidate/profile.pdf" target="_blank">${icon('download')} PDF</a>`)}<div class="grid2"><div class="card"><div class="profilebanner"><div class="avatar big">${esc(initials(p.name))}</div><div><h2>${esc(p.name)}</h2><p>${esc(p.title || 'Расскажите о своей специализации')}</p></div></div><form data-form="profile">${formError}<label>Предзаполнить из PDF-резюме<input type="file" accept="application/pdf,.pdf" data-resume-pdf aria-describedby="resume-help"></label><p class="formnote" id="resume-help">Текстовый PDF до 2 МБ, до 10 страниц. Проверьте найденные поля перед применением. Файл не сохраняется.</p><div class="spacer"></div><div class="formgrid">${field('Имя и фамилия', 'name', p.name, 'text', 'required minlength="2" maxlength="100"')}${field('Профессиональный заголовок', 'title', p.title, 'text', 'maxlength="120" placeholder="Python-разработчик"')}<div class="full">${area('О себе', 'about', p.about, 'maxlength="3000" placeholder="Какие задачи вам интересны и чем вы гордитесь?"')}</div><div class="full">${field('Навыки через запятую', 'skills', p.skills.join(', '), 'text', 'maxlength="1500" placeholder="Python, FastAPI, PostgreSQL"')}</div><div class="full">${field('Отрасль', 'industry', p.industry || 'Информационные технологии', 'text', 'maxlength="100" placeholder="ИТ, финтех, образование…"')}</div>${select('Специализация', 'specialization', specs, p.specialization)}${select('Уровень по вашей оценке', 'declared_grade', { Junior: 'Junior', Middle: 'Middle', Senior: 'Senior' }, p.declared_grade)}${field('Город', 'city', p.city, 'text', 'maxlength="100"')}${field('Опыт, лет', 'experience', p.experience, 'number', 'min="0" max="60" required')}${field('Ожидаемая зарплата, ₽/мес.', 'salary', p.salary, 'number', 'min="0" max="10000000" required')}${select('Формат работы', 'work_format', candidateFormats, p.work_format)}${field('Телефон', 'phone', p.contacts.phone, 'tel', 'maxlength="40"')}${field('Telegram', 'telegram', p.contacts.telegram, 'text', 'maxlength="100"')}<div class="full">${field('Командная роль', 'team_role', p.team_role, 'text', 'maxlength="100"')}</div><div class="full">${area('Гибкие навыки', 'soft_skills', p.soft_skills, 'maxlength="1000"')}</div><div class="full">${check('Публиковать профиль в подборе работодателей', 'published', p.published)}</div><div class="full">${check('Показывать достижения ФСП в опубликованном профиле', 'show_fsp', p.show_fsp)}</div></div><div class="formactions"><button>Сохранить профиль ${icon('check')}</button><small>Самооценка не заменяет тест</small></div></form></div><div class="stack"><section class="card"><div class="cardhead"><h2>Подтверждённые категории</h2><p class="subtitle">Отдельная категория для каждой специализации.</p></div>${categoriesHTML(p)}</section><section class="card"><div class="cardhead between"><h2>Достижения ФСП</h2>${badge('Демо-адаптер', 'gold')}</div>${
    p.fsp_id
      ? `${notice('Подключён ID <strong>' + esc(p.fsp_id) + '</strong>', 'good')}<div class="spacer"></div>${p.achievements.map((a) => `<div class="category"><div class="flex">${icon('star')}<strong>${esc(a.result)}</strong></div><p class="subtitle">${esc(a.event)}</p><small>${esc(a.discipline)} · ${esc(a.source)}</small></div>`).join('') || '<p>Достижения скрыты настройкой публикации.</p>'}<div class="spacer"></div>${btn('Отключить ID', 'unlink-fsp', 'outline tiny')}`
      : `<p>Свяжите ID участника с профилем. Отсутствие истории ФСП не мешает подбору.</p><div class="spacer"></div><form data-form="fsp-link">${formError}${select(
          'Выберите ID демо-участника',
          'fsp_id',
          Object.fromEntries(
            Array.from({ length: 6 }, (_, i) => {
              let v = 'FSP-DEMO-' + String(i + 1).padStart(3, '0');
              return [v, v];
            })
          )
        )}<div class="formactions"><button class="secondary">Подключить ID ${icon('arrow')}</button></div></form>`
  }<div class="divider"></div><small>Реальное API организаторов не предоставлено. В демо используется синтетический реестр с подтверждением кода.</small></section></div></div>`;
}
async function testsPage() {
  const data = await api('/candidate/tests');
  if (data.active) {
    attempt = data.active;
    questionIndex = Math.min(questionIndex, attempt.questions.length - 1);
    setTimeout(renderQuestion, 0);
    return testFrame();
  }
  attempt = null;
  clearInterval(timer);
  return `${pagehead('ОЦЕНКА ПО ЗАДАНИЯМ', 'Навыки, подтверждённые делом', 'Вы выбираете специализацию и уровень. Неудачная попытка не снижает вашу текущую категорию.')}<div class="card testintro"><section><div class="eyebrow">ВАША СЛЕДУЮЩАЯ КАТЕГОРИЯ</div><div class="spacer"></div><h2>Разные задания. Единая шкала.</h2><p class="subtitle">Каждый тест создаётся из параметрических шаблонов. Оценка учитывает сложность заданий, а результаты показывают сильные стороны и темы для развития.</p><div class="testfacts"><div class="fact">${icon('test')}<div><strong>15 заданий, 3 области</strong><p>Сбалансированная форма для выбранного уровня</p></div></div><div class="fact">${icon('clock')}<div><strong>30 минут на попытку</strong><p>Можно обновить страницу: ответы сохраняются</p></div></div><div class="fact">${icon('shield')}<div><strong>Результат с объяснением</strong><p>Баллы, оценка способности и уверенность решения</p></div></div></div></section><form data-form="start-test">${formError}${select('Специализация', 'specialization', specs, 'backend', 'data-test-spec')}<div class="spacer"></div><label>Выберите уровень</label><div class="spacer"></div><div class="radiolevels" id="test-levels">${levelsHTML(data.eligibility, 'backend')}</div><div class="spacer"></div>${notice('Повтор одного теста — через 30 дней. Смена подтверждённой категории — через 90 дней. Уверенный результат открывает следующий уровень на 14 дней.')}<div class="spacer"></div><button>Начать тест ${icon('arrow')}</button><div class="spacer"></div><small>Банк 1.0: экспертные параметры сложности. Психометрическая калибровка на реальных участниках ещё не проведена.</small></form></div><div class="spacer"></div><section class="card"><h2>История попыток</h2>${data.history.length ? data.history.map((r) => `<div class="history"><div><strong>${specs[r.specialization]} · ${r.grade}</strong><small style="display:block">${date(r.created)}</small></div><div class="flex">${r.status === 'finished' ? badge(`${r.result.score}%`, r.result.passed ? 'green' : 'gray') : badge('Время истекло', 'gray')}${r.status === 'finished' ? btn('Результат', 'result', 'outline tiny', `data-id="${esc(r.id)}"`) : ''}</div></div>`).join('') : empty('Вы ещё не проходили тесты', 'Первая попытка станет началом вашего паспорта навыков.')}</section>`;
}
let testEligibility = [];
function levelsHTML(eligibility, spec) {
  testEligibility = eligibility;
  return ['Junior', 'Middle', 'Senior']
    .map((g, i) => {
      const e = eligibility.find((x) => x.specialization === spec && x.grade === g);
      const first = eligibility.filter((x) => x.specialization === spec && x.allowed)[0]?.grade;
      return `<label title="${esc(e.reason)}"><div class="flex"><input type="radio" name="grade" value="${g}" ${g === first ? 'checked' : ''} ${e.allowed ? '' : 'disabled'} required>${g}</div><small>${['Базовые навыки', 'Самостоятельная работа', 'Сложные задачи'][i]}</small></label>`;
    })
    .join('');
}
function testFrame() {
  return `${pagehead('ПОДТВЕРЖДЕНИЕ КАТЕГОРИИ', `${specs[attempt.specialization]} · ${attempt.grade}`, 'Отвечайте самостоятельно. Ответы сохраняются после каждого изменения.')}<div class="testwork"><aside class="card testnav"><small>До завершения</small><div class="timer" id="timer">30:00</div><div class="questiondots" id="questiondots"></div><div class="save-state" id="save-state" role="status" aria-live="polite" aria-atomic="true">Ответы загружены с сервера</div><div class="divider"></div>${btn('Завершить тест', 'finish-test', 'outline tiny')}</aside><section class="card question" id="question"></section></div>`;
}
function renderQuestion() {
  if (!attempt || !$('#question')) return;
  const q = attempt.questions[questionIndex];
  $('#questiondots').innerHTML = attempt.questions
    .map((x, i) =>
      btn(
        String(i + 1),
        'question',
        `${i === questionIndex ? 'selected' : ''} ${attempt.answers[x.id] ? 'done' : ''}`,
        `data-index="${i}" ${i === questionIndex ? 'aria-current="step"' : ''} aria-label="Задание ${i + 1}, ${attempt.answers[x.id] ? 'ответ указан' : 'без ответа'}"`
      )
    )
    .join('');
  $('#question').innerHTML =
    `<div class="between">${badge(q.topic)}<small>Задание ${questionIndex + 1} из ${attempt.questions.length}</small></div><h2 id="question-title" tabindex="-1">${esc(q.prompt)}</h2>${q.code ? `<pre>${esc(q.code)}</pre>` : ''}${q.options ? `<div role="radiogroup" aria-labelledby="question-title">${q.options.map((o) => `<label class="option"><input type="radio" name="answer" value="${esc(o)}" data-answer="${esc(q.id)}" ${attempt.answers[q.id] === o ? 'checked' : ''}>${esc(o)}</label>`).join('')}</div>` : `<label>Ваш ответ<input type="text" data-answer="${esc(q.id)}" value="${esc(attempt.answers[q.id] || '')}" maxlength="256" autocomplete="off" placeholder="Введите число или короткий ответ"></label>`}<div class="questionfooter">${btn('← Назад', 'question', 'outline', `data-index="${Math.max(0, questionIndex - 1)}" ${questionIndex === 0 ? 'disabled' : ''}`)}${questionIndex < attempt.questions.length - 1 ? btn('Следующее', 'question', '', `data-index="${questionIndex + 1}"`, 'arrow') : btn('Завершить тест', 'finish-test', '', '', 'check')}</div>`;
  clearInterval(timer);
  const tick = () => {
    if (!$('#timer') || !attempt) return;
    const left = Math.max(0, Math.floor(attempt.deadline - Date.now() / 1000));
    $('#timer').textContent =
      String(Math.floor(left / 60)).padStart(2, '0') + ':' + String(left % 60).padStart(2, '0');
    if (!left) {
      clearInterval(timer);
      $('#save-state').textContent = 'Время истекло. Завершите тест для получения результата.';
      $$('[data-answer]').forEach((x) => (x.disabled = true));
    }
  };
  tick();
  timer = setInterval(tick, 1000);
}
let saveFailed = false;
function saveAnswer(id, value) {
  if (!attempt || attempt.answers[id] === value) return;
  attempt.answers[id] = value;
  pendingSaves++;
  $('#save-state').textContent = 'Сохраняем…';
  const activeAttempt = attempt;
  saveQueue = saveQueue
    .then(async () => {
      try {
        const res = await put(`/candidate/tests/${activeAttempt.id}/answers`, {
          version: activeAttempt.version,
          answers: { ...activeAttempt.answers },
        });
        activeAttempt.version = res.version;
        saveFailed = false;
      } catch (error) {
        saveFailed = true;
        toast(error.message);
        if ($('#save-state'))
          $('#save-state').textContent = 'Не сохранено. Обновите страницу для восстановления.';
        throw error;
      } finally {
        pendingSaves--;
        if (!pendingSaves && !saveFailed && $('#save-state'))
          $('#save-state').textContent = '✓ Все ответы сохранены';
      }
    })
    .catch(() => {});
}
function resultHTML(r) {
  return `<section class="resultsummary"><div class="eyebrow">РЕЗУЛЬТАТ ПОПЫТКИ</div><div class="resultcircle ${r.passed ? '' : 'fail'}">${r.score}%</div><h2>${r.passed ? 'Категория ' + r.grade + ' подтверждена' : 'Пока не подтверждено'}</h2><p>${r.passed ? 'Работодатели увидят вашу новую категорию и подтверждённые навыки.' : 'Ранее подтверждённые категории сохранены. Темы ниже помогут подготовиться к следующей попытке.'}</p></section><div class="statline"><div><strong>${r.correct}/${r.total}</strong><small>верных ответов</small></div><div><strong>${r.theta}</strong><small>оценка θ</small></div><div><strong>${r.confidence}%</strong><small>уверенность решения</small></div></div>${topicsHTML(r.topics)}<div class="spacer"></div>${r.strong ? notice('Уверенный результат! Следующий уровень доступен в течение 14 дней.', 'good') : notice('Параметры IRT пока экспертные; уверенность — оценка модели, а не гарантия уровня на реальной работе.')}<div class="modalfoot">${btn('Продолжить', 'close', '')}</div>`;
}
let matchingSpec = 'backend';
function talentCard(p) {
  const c = p.categories.find((c) => c.specialization === matchingSpec);
  return `<article class="talent-card"><div class="talent-top"><div class="talent-avatar tone-${p.id % 4}" aria-hidden="true"><span>${String(p.id).padStart(2, '0')}</span><i></i></div><div class="talent-identity"><small>${p.contacts_open ? 'КОНТАКТЫ ОТКРЫТЫ' : 'ПОДТВЕРЖДЁННЫЙ ПРОФИЛЬ'}</small><h3>${esc(p.name)}</h3></div><div class="score-ring" style="--score:${p.match.score}%" aria-label="Совпадение ${p.match.score}%"><span>${p.match.score}<small>%</small></span></div></div><div class="talent-body"><div class="talent-category">${matchingSpec === 'backend' ? 'BACKEND' : 'FRONTEND'}<span>/</span>${esc(c?.grade || '—')}</div><h2 class="talent-title">${esc(p.title || specs[matchingSpec])}</h2><div class="talent-meta"><span>${esc(p.city)}</span><span>${candidateFormats[p.work_format]}</span><span>Опыт ${p.experience} г.</span></div><div class="talent-skills">${chips(p.skills.slice(0, 5), c?.verified_skills)}</div><div class="talent-evidence"><span>${icon('shield')} Тест ${c?.score || 0}%</span><span>${icon('star')} ${p.achievements.length ? 'ФСП · ' + p.achievements.length + ' достиж.' : 'Без истории ФСП'}</span>${btn('Почему подходит ↗', 'match-explain', 'linkbutton', `data-id="${p.id}"`)}</div></div><div class="talent-bottom"><div class="talent-salary">${money(p.salary)} ₽<small>/ месяц</small></div><div class="flex">${btn('Профиль', 'candidate-detail', 'outline', `data-id="${p.id}"`)}${btn('Пригласить', 'invite', '', `data-id="${p.id}"`, 'arrow')}</div></div></article>`;
}
function matchingResults() {
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const sort = params.get('sort') || 'match';
  const ordered = [...matches].sort((a, b) =>
    sort === 'salary'
      ? a.salary - b.salary
      : sort === 'experience'
        ? b.experience - a.experience
        : b.match.score - a.match.score
  );
  const pages = Math.max(1, Math.ceil(ordered.length / 6));
  const page = Math.min(pages, Math.max(1, Math.floor(Number(params.get('page'))) || 1));
  return `<div class="resulthead between"><div class="flex"><h2>Кандидаты</h2><span class="count-badge">${matches.length}</span></div>${select('Порядок', 'sort', { match: 'По совпадению', experience: 'По опыту', salary: 'По зарплате' }, sort, 'data-match-sort aria-label="Порядок"')}<div class="view-switch" aria-label="Вид каталога">${btn('', 'match-view', 'iconbtn', `data-view="grid" aria-label="Карточки" aria-pressed="${params.get('view') !== 'list'}"`, 'grid')}${btn('', 'match-view', 'iconbtn', `data-view="list" aria-label="Список" aria-pressed="${params.get('view') === 'list'}"`, 'list')}</div></div>${
    ordered.length
      ? `<div class="talent-grid ${params.get('view') === 'list' ? 'talent-list' : ''}">${ordered
          .slice((page - 1) * 6, page * 6)
          .map(talentCard)
          .join(
            ''
          )}</div><div class="pagination"><small>Показано ${(page - 1) * 6 + 1}–${Math.min(page * 6, ordered.length)} из ${ordered.length}</small><nav aria-label="Страницы кандидатов">${Array.from({ length: pages }, (_, i) => btn(String(i + 1), 'match-page', page === i + 1 ? 'page-current' : 'outline', `data-page="${i + 1}" aria-label="Страница ${i + 1}" ${page === i + 1 ? 'aria-current="page"' : ''}`)).join('')}</nav></div>`
      : empty(
          'Никого не нашли',
          'Измените стек или отключите фильтр достижений ФСП.',
          btn('Сбросить фильтры', 'clear-filters', 'secondary')
        )
  }`;
}
function updateMatchingQuery(key, value) {
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  params.set(key, value);
  if (key !== 'page') params.delete('page');
  go('matching?' + params);
}
async function matchingPage() {
  needs = await api('/employer/needs');
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  let id = params.get('need');
  if (id && !needs.some((n) => n.id == id)) id = null;
  if (!id && needs.length) id = needs.at(-1).id;
  const result = await api(
    '/employer/candidates?' +
      new URLSearchParams({
        ...(id
          ? { need_id: id }
          : {
              specialization: params.get('spec') || 'backend',
              grade: params.get('grade') || 'Middle',
            }),
        q: params.get('q') || '',
        fsp: params.get('fsp') || 'false',
      })
  );
  matches = result.candidates;
  matchingSpec = result.need.specialization;
  const need = needs.find((n) => n.id == id);
  return `<div class="editorial-heading matching-heading"><div><div class="eyebrow">ПОДБОР ПО ПОДТВЕРЖДЁННЫМ НАВЫКАМ</div><h1>Найдите своих <em>людей.</em></h1><p>Сравните навыки кандидатов с требованиями вашей позиции.</p></div><div class="heading-aside"><div class="match-orbit" aria-hidden="true">${icon('code')}</div><span>Талант + команда<br><strong>Возможности без границ</strong></span></div></div><div class="discovery-strip"><div>${icon('shield')}<span>Навыки подтверждены тестом</span></div><div>${icon('chart')}<span>Понятные факторы подбора</span></div><div>${icon('lock')}<span>Знакомство по взаимному согласию</span></div></div><div class="discovery-layout"><aside class="search-panel"><div class="search-panel-head"><span class="section-index">ПАРАМЕТРЫ ПОИСКА</span><h2>Кого ищем?</h2></div><form data-form="filters" class="matching-filters">${formError}${needs.length ? select('Позиция в команде', 'need', Object.fromEntries(needs.map((n) => [n.id, n.title + ' · ' + n.grade])), String(id || '')) : select('Специализация', 'spec', specs, params.get('spec') || 'backend')}${!needs.length ? select('Уровень', 'grade', { Junior: 'Junior', Middle: 'Middle', Senior: 'Senior' }, params.get('grade') || 'Middle') : ''}${field('Навыки и опыт', 'q', params.get('q') || '', 'search', 'placeholder="Python, SQL, API…" maxlength="100"')}<div class="filter-options">${check('С достижениями ФСП', 'fsp', params.get('fsp') === 'true')}</div><button>${icon('search')} Найти кандидатов</button></form>${need ? `<div class="need-summary"><small>УСЛОВИЯ ПОЗИЦИИ</small><strong>${money(need.salary_from)}–${money(need.salary_to)} ₽</strong><p>${fmt[need.work_format]} · ${esc(need.city)}</p>${chips(need.skills)}</div>` : ''}<div class="filter-footer">${btn('Новая потребность', 'need-new', 'outline', '', 'plus')}<a href="#needs">Все потребности команды ↗</a></div><div class="privacy-note">${icon('lock')}<p>Имя и контакты скрыты до согласия кандидата на знакомство.</p></div></aside><section class="discovery-results" aria-label="Результаты подбора"><div id="matching-results">${matchingResults()}</div></section></div>`;
}
function explainMatch(p) {
  const m = p.match;
  modal(
    `Совпадение ${m.score}%`,
    `${notice('Рейтинг — сумма вкладов доступных факторов. Пропущенные факторы исключаются, остальные веса нормируются.')}<div class="spacer"></div><h3>${esc(p.name)}</h3><div class="scorebreak">${m.breakdown.map((x) => `<div class="scoreitem"><span>${esc(x.name)}</span><div class="bar"><span style="width:${x.value}%"></span></div><strong>${x.points.toFixed(1)}</strong></div>`).join('')}</div><div class="spacer"></div><small>Справа — вклад в итоговые ${m.score} баллов из 100.</small><div class="divider"></div>${m.reasons.map((x) => `<p>✓ ${esc(x)}</p>`).join('')}<div class="modalfoot">${btn('Посмотреть профиль', 'candidate-detail', 'secondary', `data-id="${p.id}"`)}</div>`
  );
}
async function candidateModal(id) {
  const p = await api('/employer/candidates/' + id);
  modal(
    'Профиль кандидата',
    `<div class="profilebanner"><div class="avatar big">${p.contacts_open ? esc(initials(p.name)) : icon('code')}</div><div><h2>${esc(p.name)}</h2><p>${esc(p.title)}</p></div></div>${p.contacts_open ? notice('Контакты доступны по разрешению кандидата.', 'good') : notice('Имя и контакты скрыты до принятия приглашения или самостоятельного отклика.')}<p class="plainline">${esc(p.about)}</p><div class="statline"><div><strong>${p.experience}</strong><small>лет опыта</small></div><div><strong>${money(p.salary)}</strong><small>ожидания, ₽/мес.</small></div></div>${chips(
      p.skills,
      p.categories.flatMap((c) => c.verified_skills)
    )}<p>${esc(p.city)} · ${candidateFormats[p.work_format]}</p>${categoriesHTML(p)}<div class="divider"></div><h3>Достижения ФСП</h3>${p.achievements.map((a) => `<p>${esc(a.event)} · ${esc(a.result)}</p>`).join('') || '<p>История отсутствует или скрыта кандидатом.</p>'}${
      p.contacts_open
        ? `<div class="contactbox">${Object.entries(p.contacts)
            .filter(([, v]) => v)
            .map(([k, v]) => `<div>${esc(k)}: ${esc(v)}</div>`)
            .join('')}</div>`
        : ''
    }<div class="modalfoot"><a class="button outline" href="/api/employer/candidates/${p.id}/profile.pdf" target="_blank">${icon('download')} PDF</a>${btn('Пригласить', 'invite', '', `data-id="${p.id}"`)}</div>`
  );
}
async function inviteModal(id) {
  const c = await api('/employer/company');
  const selected = new URLSearchParams(location.hash.split('?')[1] || '').get('need');
  const n = needs.find((x) => x.id == selected) || needs.at(-1) || {};
  closeModal();
  modal(
    'Пригласить в команду',
    `${notice('Приглашение будет адресовано выбранному кандидату. Контакты откроются после его согласия.')}<div class="spacer"></div><form data-form="invite" data-id="${id}">${formError}<div class="formgrid"><div class="full">${field('Позиция или задача', 'title', n.title || '', 'text', 'required minlength="3" maxlength="120"')}</div><div class="full">${area('Личное сообщение и описание задач', 'description', n.description || '', 'required minlength="20" maxlength="3000"')}</div>${field('Зарплата от, ₽/мес.', 'salary_from', n.salary_from || 180000, 'number', 'required min="1" max="10000000"')}${field('Зарплата до, ₽/мес.', 'salary_to', n.salary_to || 260000, 'number', 'required min="1" max="10000000"')}${select('Формат', 'work_format', fmt, n.work_format || 'remote')}${field('Способ связи с компанией', 'contact', c.contact, 'text', 'required minlength="3" maxlength="200"')}</div><div class="modalfoot"><button>Отправить приглашение ${icon('mail')}</button></div></form>`
  );
}
async function invitationsPage() {
  invitationsData = await api('/invitations');
  const candidate = user.role === 'candidate';
  const applications = await api('/applications');
  return `${pagehead(candidate ? 'ПРЯМЫЕ ПРЕДЛОЖЕНИЯ' : 'ДИАЛОГ С КАНДИДАТАМИ', candidate ? 'Вас хотят в команде' : 'Ваши приглашения', candidate ? 'Решайте сами, с кем продолжить знакомство.' : 'Личные приглашения работают лучше массовых откликов.')}<div class="rowlist">${invitationsData.length ? invitationsData.map((i) => `<article class="card invitation"><div class="between"><div class="rowtitle"><div class="avatar">${icon(candidate ? 'company' : 'profile')}</div><div><h3>${esc(candidate ? i.company.name : i.candidate.name)}</h3><p>${esc(i.title)}</p></div></div>${stateBadge(i.status)}</div><div class="salary">${salary(i)} <small>в месяц</small></div><p>${fmt[i.work_format]} · ${date(i.created)}</p><div class="spacer"></div><div class="plainline">${esc(i.description)}</div><div class="invite-actions">${candidate ? `${['sent', 'viewed'].includes(i.status) ? `${btn('Подробнее', 'invitation-detail', 'outline', `data-id="${i.id}"`)}${btn('Отклонить', 'decline-invite', 'secondary', `data-id="${i.id}"`)}${btn('Принять приглашение', 'accept-invite', '', `data-id="${i.id}"`, 'check')}` : i.status === 'accepted' ? `<small>${i.contacts_open ? 'Вы открыли контакты этой компании' : 'Разрешение на контакты отозвано'}</small>` : ''}` : `${btn('Профиль', 'candidate-detail', 'outline', `data-id="${i.candidate_id}"`)}${['sent', 'viewed'].includes(i.status) ? btn('Отозвать', 'withdraw-invite', 'secondary', `data-id="${i.id}"`) : ''}${i.contacts_open ? badge('Контакты открыты', 'green') : ''}`}</div>${candidate && i.status === 'accepted' ? `<div class="contactbox"><strong>Как связаться с командой</strong>${esc(i.contact)}</div>` : ''}</article>`).join('') : empty(candidate ? 'Приглашения ещё впереди' : 'Пока нет отправленных приглашений', candidate ? 'Подтвердите категорию и опубликуйте профиль.' : 'Выберите кандидата в подборе.', `<a class="button secondary" href="#${candidate ? 'tests' : 'matching'}">${candidate ? 'Подтвердить навыки' : 'Перейти к подбору'}</a>`)}</div><div class="spacer"></div><div class="spacer"></div><section class="card"><h2>${candidate ? 'Мои отклики' : 'Самостоятельные отклики'}</h2>${applications.length ? applications.map((a) => `<div class="history"><div><strong>${esc(a.need.title)}</strong><small style="display:block">${esc(candidate ? a.need.company.name : a.candidate.name)} · ${date(a.created)}</small></div>${candidate ? badge('Отклик отправлен', 'green') : btn('Профиль', 'candidate-detail', 'outline tiny', `data-id="${a.candidate.id}"`)}</div>`).join('') : empty('Откликов пока нет', candidate ? 'Вы можете самостоятельно откликнуться на вакансию.' : 'Здесь появятся отклики на опубликованные потребности.')}</section>`;
}
async function invitationModal(id) {
  const i = invitationsData.find((x) => x.id == id);
  if (i.status === 'sent') {
    await patch('/invitations/' + id, { status: 'viewed' });
    await render();
  }
  modal(
    'Приглашение от ' + esc(i.company.name),
    `${badge(i.title)}<p>${esc(i.company.description)}</p><div class="salary">${salary(i)} / месяц</div><p class="plainline">${esc(i.description)}</p><div class="divider"></div><h3>Контакт компании</h3><p>${esc(i.contact)}</p>${notice('Ваши имя и контакты откроются этой компании только после принятия с отдельным разрешением.')}<div class="modalfoot">${btn('Принять приглашение', 'accept-invite', '', `data-id="${id}"`)}</div>`
  );
}
function acceptModal(id) {
  closeModal();
  modal(
    'Продолжить знакомство',
    `<p>После принятия компания получит ваше имя, email, телефон и Telegram из профиля. Вы сможете отозвать разрешение в разделе «Приватность».</p><form data-form="accept" data-id="${id}">${formError}${check('Разрешаю передать мои контакты этой компании для обсуждения работы.', 'share_contacts', false, 'required')}<div class="modalfoot"><button>Принять и открыть контакты ${icon('check')}</button></div></form>`
  );
}
async function needsPage() {
  needs = await api('/employer/needs');
  return `${pagehead('ПОТРЕБНОСТИ КОМАНДЫ', 'Кого вы ищете?', 'Потребность задаёт критерии подбора. Её можно дополнительно опубликовать как вакансию.', btn('Новая потребность', 'need-new', '', '', 'plus'))}<div class="grid2">${needs.map((n) => `<article class="card"><div class="between">${badge(n.grade + ' · ' + specs[n.specialization])}${badge(n.published ? 'Опубликована' : 'Только подбор', n.published ? 'green' : 'gray')}</div><div class="spacer"></div><h2>${esc(n.title)}</h2><p class="subtitle plainline">${esc(n.description)}</p><div class="spacer"></div>${chips(n.skills)}<div class="divider"></div><div class="salary">${salary(n)}</div><p>${fmt[n.work_format]} · ${esc(n.city)}</p><div class="formactions"><a class="button" href="#matching?need=${n.id}">${icon('search')} Подобрать</a>${btn('Изменить', 'need-edit', 'outline', `data-id="${n.id}"`)}</div></article>`).join('') || empty('Создайте первую потребность', 'Укажите категорию, стек и задачи команды.', btn('Создать', 'need-new'))}</div>`;
}
function needModal(n = {}) {
  modal(
    n.id ? 'Редактировать потребность' : 'Новая потребность',
    `<form data-form="need" data-id="${n.id || ''}">${formError}<div class="formgrid"><div class="full">${field('Название позиции', 'title', n.title || '', 'text', 'required minlength="3" maxlength="120"')}</div>${select('Специализация', 'specialization', specs, n.specialization || 'backend')}${select('Категория', 'grade', { Junior: 'Junior', Middle: 'Middle', Senior: 'Senior' }, n.grade || 'Middle')}<div class="full">${field('Стек через запятую', 'skills', (n.skills || []).join(', '), 'text', 'maxlength="1000" placeholder="Python, PostgreSQL"')}</div><div class="full">${area('Задачи и требования', 'description', n.description || '', 'required minlength="20" maxlength="5000"')}</div>${field('Зарплата от, ₽/мес.', 'salary_from', n.salary_from || 120000, 'number', 'required min="1" max="10000000"')}${field('Зарплата до, ₽/мес.', 'salary_to', n.salary_to || 200000, 'number', 'required min="1" max="10000000"')}${select('Формат', 'work_format', fmt, n.work_format || 'remote')}${field('Город', 'city', n.city || '', 'text', 'maxlength="100"')}<div class="full">${check('Опубликовать для самостоятельных откликов', 'published', n.published)}</div></div><div class="modalfoot"><button>Сохранить потребность ${icon('check')}</button></div></form>`
  );
}
async function companyPage() {
  const c = await api('/employer/company');
  return `${pagehead('ПРЕДСТАВЬТЕ КОМАНДУ', 'Компания, в которую захочется прийти', 'Эта информация будет доступна кандидату в приглашении.')}<div class="grid2"><section class="card"><form data-form="company">${formError}<div class="stack">${field('Название компании', 'name', c.name, 'text', 'required minlength="2" maxlength="100"')}${area('О команде и продукте', 'description', c.description, 'maxlength="3000"')}${field('Способ связи с вами', 'contact', c.contact, 'text', 'required minlength="3" maxlength="200"')}${field('Сайт компании', 'website', c.website, 'url', 'maxlength="200"')}${field('Отрасль', 'industry', c.industry, 'text', 'maxlength="100"')}<div><button>Сохранить компанию ${icon('check')}</button></div></div></form></section><section class="card" style="align-self:start"><div class="avatar big">${icon('company')}</div><div class="spacer"></div><h2>${esc(c.name)}</h2><p class="subtitle plainline">${esc(c.description)}</p><div class="divider"></div><p>${esc(c.industry)}</p><p>${esc(c.contact)}</p><div class="spacer"></div>${notice('В подборе контакты кандидатов скрыты. Для знакомства отправьте приглашение с описанием задач и зарплатной вилкой.')}</section></div>`;
}
async function tasksPage() {
  tasks = await api('/tasks');
  const candidate = user.role === 'candidate';
  return `${pagehead('ПРАКТИКА КАЖДУЮ НЕДЕЛЮ', candidate ? 'Небольшая задача. Заметный рост.' : 'Задания вашей команды', candidate ? 'Реальные ситуации от компаний для развития навыков. Оценка по открытой рубрике.' : 'Публикуйте короткие ситуации из практики и оценивайте решения.', candidate ? '' : btn('Создать задание', 'task-new', '', '', 'plus'))}${candidate ? notice('Новое задание назначается при входе в этот раздел, не чаще раза в неделю. Ручная оценка не меняет подтверждённую категорию.') : ''}<div class="spacer"></div><div class="rowlist">${tasks.length ? tasks.map((t) => `<article class="card task-card"><div class="between">${badge(t.grade + ' · ' + specs[t.specialization])}${candidate ? stateBadge(t.status) : badge(t.submissions.length + ' ответов', 'gray')}</div><div class="spacer"></div><h2>${esc(t.title)}</h2>${candidate ? `<p class="reason">${esc(t.company.name)} · до ${date(t.deadline)}<br>${esc(t.reason)}</p>` : ''}<p class="plainline">${esc(t.description)}</p>${chips(t.rubric)}<div class="divider"></div>${candidate ? `${t.answer ? `<h3>Ваш ответ</h3><p class="plainline">${esc(t.answer.answer)}</p>${t.answer.score !== null ? `${notice(`<strong>${t.answer.score}%</strong> · ${esc(t.answer.feedback)}`, 'good')}` : notice('Решение отправлено работодателю. Оценка появится после проверки.')}` : `<form data-form="task-answer" data-id="${t.id}">${formError}${area('Как бы вы решили эту задачу?', 'answer', '', 'required minlength="20" maxlength="8000" placeholder="Опишите ход решения, ограничения и важные детали…"')}<div class="formactions"><button ${t.deadline < Date.now() / 1000 ? 'disabled' : ''}>Отправить решение ${icon('arrow')}</button></div></form>`}` : `${t.submissions.length ? t.submissions.map((a) => `<section class="category"><div class="between"><h3>${esc(a.candidate.name)}</h3>${a.score !== null ? badge(a.score + '%', 'green') : badge('Нужна проверка', 'gold')}</div><p class="plainline">${esc(a.answer)}</p>${a.feedback ? `<p>${esc(a.feedback)}</p>` : ''}${btn(a.score === null ? 'Оценить' : 'Изменить оценку', 'review-task', 'secondary tiny', `data-id="${a.id}"`)} ${btn('Профиль', 'candidate-detail', 'outline tiny', `data-id="${a.candidate.id}"`)}</section>`).join('') : empty('Ответов пока нет', 'Задание появится у кандидатов подходящей категории.')}`}</article>`).join('') : empty(candidate ? 'Практика появится после теста' : 'Начните с короткой задачи', candidate ? 'Подтвердите категорию, чтобы получать подходящие задания.' : 'Опишите ситуацию и критерии оценки.')}</div>`;
}
function taskModal() {
  modal(
    'Короткое практическое задание',
    `<form data-form="task">${formError}<div class="formgrid"><div class="full">${field('Название', 'title', '', 'text', 'required minlength="3" maxlength="120"')}</div>${select('Специализация', 'specialization', specs, 'backend')}${select('Категория', 'grade', { Junior: 'Junior', Middle: 'Middle', Senior: 'Senior' }, 'Middle')}<div class="full">${area('Ситуация и вопрос кандидату', 'description', '', 'required minlength="30" maxlength="5000"')}</div><div class="full">${select('Тема для адресного назначения', 'topic', { '': 'Практика в целом', Алгоритмы: 'Алгоритмы', 'Данные и SQL': 'Данные и SQL', 'API и архитектура': 'API и архитектура', JavaScript: 'JavaScript', Интерфейсы: 'Интерфейсы', 'Веб-платформа': 'Веб-платформа' }, '')}</div></div><div class="spacer"></div>${notice('Рубрика: корректность, полнота, обоснование — по 0–2 балла. Проверку выполняет работодатель.')}<div class="modalfoot"><button>Создать задание</button></div></form>`
  );
}
function reviewModal(id) {
  modal(
    'Проверка по рубрике',
    `<form data-form="review" data-id="${id}">${formError}<div class="formgrid">${['correctness', 'completeness', 'reasoning'].map((key, i) => select(['Корректность', 'Полнота', 'Обоснование'][i], key, { 0: '0 · Не раскрыто', 1: '1 · Частично', 2: '2 · Полностью' }, '1')).join('')}<div class="full">${area('Комментарий кандидату', 'feedback', '', 'required minlength="10" maxlength="3000"')}</div></div><div class="modalfoot"><button>Сохранить оценку</button></div></form>`
  );
}
async function jobsPage() {
  const jobs = await api('/jobs');
  return `${pagehead('ОТКРЫТЫЕ ВОЗМОЖНОСТИ', 'Вакансии команд', 'Можно ждать личного приглашения или начать разговор самостоятельно.')}${notice('Откликаясь, вы отдельно разрешаете передать контакты выбранной компании.')}<div class="spacer"></div><div class="grid2">${jobs.map((n) => `<article class="card"><div class="between">${badge(n.company.name, 'gray')}${badge(n.grade)}</div><div class="spacer"></div><h2>${esc(n.title)}</h2><div class="salary" style="margin:15px 0">${salary(n)}</div><p>${fmt[n.work_format]} · ${esc(n.city)}</p><p class="subtitle plainline">${esc(n.description)}</p><div class="spacer"></div>${chips(n.skills)}<div class="divider"></div>${n.applied ? badge('Отклик отправлен', 'green') : btn('Откликнуться', 'job-apply', '', `data-id="${n.id}"`)}</article>`).join('') || empty('Вакансии скоро появятся', 'Подтверждённый профиль уже доступен для личных приглашений.')}</div>`;
}
function accountPrivacyHTML(a) {
  const missingAcceptance =
    a.consent.record_source === 'synthetic_demo'
      ? 'Синтетический демо-аккаунт'
      : 'Подтверждение в прежней версии не записывалось';
  const recorded = (t) => (t ? date(t) : 'не записано в прежней версии');
  return `<div class="stack"><section class="card"><h2>Подтверждения аккаунта</h2><p class="subtitle">Согласия, условия и возраст фиксируются отдельно. Сохранённые записи можно проверить здесь.</p><dl class="account-records"><div><dt>Обработка данных</dt><dd>${a.consent.active ? (a.consent.accepted ? 'Согласие действует' : missingAcceptance) : 'Согласие отозвано'} · ${esc(a.consent.version || 'версия не записана')}<small>Принято: ${recorded(a.consent.accepted_at)}</small></dd></div><div><dt>Условия использования</dt><dd>${a.terms.accepted ? 'Приняты' : missingAcceptance}<small>${a.terms.version ? esc(a.terms.version) + ' · ' : ''}${recorded(a.terms.accepted_at)}</small></dd></div><div><dt>Возраст 18+</dt><dd>${a.age.confirmed ? 'Подтверждён пользователем' : missingAcceptance}</dd></div></dl><div class="flex wrap"><a href="#consent">Текст согласия</a><a href="#terms">Условия</a><a href="#operator">Оператор</a></div><div class="divider"></div>${btn('Отозвать согласие и деактивировать', 'revoke-consent', 'outline')}<p class="formnote">Отзыв закрывает профиль и завершает сеансы. Чтобы удалить данные, используйте отдельную кнопку ниже или форму удаления деактивированного аккаунта.</p></section><section class="card"><h2>Письма и cookie</h2><p class="subtitle">Рекламная рассылка и сторонняя аналитика не подключены. Email используется для кода подтверждения аккаунта.</p><div class="privacyrow"><div><h3>Рекламные письма отключены</h3><p>${a.marketing.opted_out_at ? 'Отказ записан: ' + date(a.marketing.opted_out_at) : 'Подписки по умолчанию нет.'}</p></div>${btn('Зафиксировать отказ от рассылок', 'marketing-opt-out', 'outline')}</div><button type="button" class="linkbutton" data-cookie-settings>Информация об использовании cookie</button></section><section class="card"><h2>Удаление аккаунта и данных</h2><p class="subtitle">Удаляются аккаунт, профиль, попытки теста, согласия, приглашения, отклики и связанные записи из рабочей базы. Для компании также удаляются её потребности и задания.</p><div class="divider"></div>${notice('Это действие необратимо. Внешние копии у компаний и резервные копии владельца стенда автоматически не удаляются.', 'warn')}<div class="formactions">${user.browser_demo ? btn('Очистить личное демо', 'demo-reset', 'danger') : btn('Удалить аккаунт и данные', 'delete-account', 'danger')}<a href="#deletion">Порядок удаления</a></div></section></div>`;
}
async function settingsPage() {
  const a = await api('/account/privacy');
  const heading = pagehead(
    'КОНТРОЛЬ У ВАС',
    'Ваши данные. Ваши решения.',
    'Настройки публикации, контактов и обработки данных действуют независимо.'
  );
  if (user.role === 'employer')
    return `${heading}<div class="account-settings">${accountPrivacyHTML(a)}</div>`;
  const [p, grants] = await Promise.all([api('/candidate/profile'), api('/candidate/contacts')]);
  profileData = p;
  return `${heading}<div class="grid2"><div class="stack"><section class="card"><h2>Видимость профиля</h2><div class="privacyrow"><div><h3>${p.published ? 'Профиль опубликован' : 'Профиль скрыт'}</h3><p>Навыки и достижения видны в подборе.</p></div>${btn(p.published ? 'Скрыть' : 'Опубликовать', 'toggle-publication', 'secondary')}</div><div class="privacyrow"><div><h3>Достижения ФСП</h3><p>${p.show_fsp ? 'Показываются в профиле' : 'Скрыты от работодателей'}</p></div>${btn(p.show_fsp ? 'Скрыть' : 'Показывать', 'toggle-fsp', 'outline')}</div><div class="spacer"></div>${notice('Имя, email, телефон и Telegram скрыты от компаний без разрешения. Текст, который вы сами написали в «О себе», видят работодатели после публикации профиля.')}</section><section class="card"><h2>Разрешения на контакты</h2><p class="subtitle">Вы можете отозвать доступ каждой компании отдельно.</p>${grants.length ? grants.map((g) => `<div class="privacyrow"><div><h3>${esc(g.name)}</h3><p>Разрешение от ${date(g.created)}</p></div>${btn('Отозвать', 'revoke-contact', 'outline tiny', `data-id="${g.employer}"`)}</div>`).join('') : empty('Контакты закрыты для всех', 'Разрешение появится после принятия приглашения или отклика.')}</section></div>${accountPrivacyHTML(a)}</div>`;
}
function deletionModal(deactivated = false) {
  modal(
    'Удалить аккаунт и данные?',
    `<p>Данные аккаунта и связанные записи будут удалены из рабочей базы. Восстановить их через приложение нельзя. Копии у компаний и резервные копии владельца стенда не удаляются этой командой.</p><div class="spacer"></div><form data-form="${deactivated ? 'erase-deactivated' : 'delete-account'}">${formError}${deactivated ? field('Email деактивированного аккаунта', 'email', '', 'email', 'required autocomplete="email"') : ''}${field('Пароль аккаунта для подтверждения', 'password', '', 'password', 'required minlength="8" maxlength="128" autocomplete="current-password"')}<div class="modalfoot">${btn('Отмена', 'close', 'outline')}<button class="danger">Удалить аккаунт и данные</button></div></form>`
  );
}
async function notificationModal() {
  const items = await api('/notifications');
  modal(
    'Ваши уведомления',
    `${items.map((n) => `<div class="notification ${n.seen ? '' : 'unread'}"><h3>${esc(n.title)}</h3><p>${esc(n.body)}</p><small>${date(n.created)}</small></div>`).join('') || empty('Уведомлений пока нет')}<div class="modalfoot">${btn('Отметить прочитанными', 'read-notifications', 'secondary')}</div>`
  );
}
async function render() {
  const generation = ++renderGeneration;
  if (route === 'tests' && attempt) {
    try {
      await waitForSavedAnswers();
    } catch (error) {
      if (generation === renderGeneration) {
        history.replaceState(null, '', '#tests');
        toast(error.message);
      }
      return;
    }
    if (generation !== renderGeneration) return;
  }
  clearInterval(timer);
  const nextRoute = getRoute(),
    routeChanged = route !== nextRoute;
  const focusPage = () => {
    if (routeChanged && generation === renderGeneration) {
      const main = $('#main-content') || $('#public-content');
      main?.focus({ preventScroll: true });
    }
  };
  if (routeChanged) window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  route = nextRoute;
  const pages = {
    overview,
    profile: profilePage,
    tests: testsPage,
    matching: matchingPage,
    needs: needsPage,
    invitations: invitationsPage,
    company: companyPage,
    tasks: tasksPage,
    jobs: jobsPage,
    settings: settingsPage,
  };
  document.title =
    (publicTitles[route] ||
      { login: 'Вход', register: 'Регистрация' }[route] ||
      (user?.role === 'employer' ? employerNav : candidateNav).find((x) => x[0] === route)?.[1] ||
      'Страница не найдена') + ' · Таланты ФСП';
  if (['login', 'register'].includes(route) && user) {
    go(workspaceLink());
    return;
  }
  if (['login', 'register'].includes(route) && !user) {
    if (authMode !== 'verify') authMode = route;
    landing();
    focusPage();
    return;
  }
  if (Object.hasOwn(publicTitles, route)) {
    $('#app').innerHTML = publicFrame(publicPage(route));
    focusPage();
    if (route === 'operator') loadLegalOperator();
    return;
  }
  if (!Object.hasOwn(pages, route)) {
    $('#app').innerHTML = publicFrame(errorPage('404'));
    focusPage();
    return;
  }
  if (!user) {
    authMode = 'login';
    landing();
    focusPage();
    return;
  }
  if (!(user.role === 'employer' ? employerNav : candidateNav).some((x) => x[0] === route)) {
    $('#app').innerHTML = publicFrame(errorPage('403'));
    focusPage();
    return;
  }
  shell();
  try {
    const html = await pages[route]();
    if (generation === renderGeneration) {
      $('#content').innerHTML = html;
      if (route === 'tests' && attempt) renderQuestion();
      focusPage();
    }
  } catch (error) {
    if (generation === renderGeneration)
      $('#content').innerHTML =
        `<section class="card errorpage">${icon('refresh')}<h1>Не удалось загрузить данные</h1><p>${esc(error.message)}</p><p>Проверьте подключение и попробуйте ещё раз.</p><div class="flex wrap">${btn('Повторить', 'refresh')}<a class="button outline" href="#help">Открыть помощь</a></div></section>`;
  }
}

async function login(email, password) {
  user = await post('/auth/login', { email, password });
  const next = user.role === 'candidate' ? 'overview' : 'matching';
  if (location.hash === '#' + next) await render();
  else go(next);
}
async function waitForSavedAnswers() {
  let queued;
  do {
    queued = saveQueue;
    await queued;
  } while (queued !== saveQueue);
  if (saveFailed)
    throw new Error('Есть несохранённые ответы. Повторите сохранение или обновите страницу.');
}
async function demoLogin(role, reset = false) {
  const fields = $$('[data-answer]').map((input) => ({ input, disabled: input.disabled }));
  for (const { input } of fields) input.disabled = true;
  try {
    if (reset) await saveQueue;
    else await waitForSavedAnswers();
    user = await post('/auth/demo', { role, reset });
  } catch (error) {
    for (const { input, disabled } of fields) {
      if (input.isConnected) input.disabled = disabled || attempt?.deadline <= Date.now() / 1000;
    }
    throw error;
  }
  saveFailed = false;
  attempt = null;
  questionIndex = 0;
  closeModal();
  const next = user.role === 'candidate' ? 'overview' : 'matching';
  if (location.hash === '#' + next) await render();
  else go(next);
}
function profileBody(p) {
  return { ...p, phone: p.contacts?.phone || '', telegram: p.contacts?.telegram || '' };
}
function numberFields(data, keys) {
  for (const k of keys) data[k] = Number(data[k]);
  return data;
}
const splitSkills = (s) =>
  s
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
document.addEventListener('submit', async (e) => {
  const form = e.target;
  if (!form.dataset.form) return;
  e.preventDefault();
  const type = form.dataset.form;
  const data = Object.fromEntries(new FormData(form));
  const submit = $('button[type="submit"],button:not([type])', form);
  if (submit) submit.disabled = true;
  const errorBox = $('.formerror', form);
  if (errorBox) errorBox.textContent = '';
  try {
    if (type === 'login') await login(data.email, data.password);
    if (type === 'resend') {
      const r = await post('/auth/resend', data);
      verifyEmail = r.email;
      verifyCode = r.dev_code || '';
      authMode = 'verify';
      closeModal();
      landing();
    }
    if (type === 'register') {
      const r = await post('/auth/register', {
        ...data,
        role: authRole,
        consent: !!data.consent,
        terms_accepted: !!data.terms_accepted,
        age_confirmed: !!data.age_confirmed,
      });
      verifyEmail = r.email;
      verifyCode = r.dev_code || '';
      authMode = 'verify';
      landing();
    }
    if (type === 'verify') {
      user = await post('/auth/verify', { email: verifyEmail, code: data.code });
      authMode = 'login';
      go(user.role === 'candidate' ? 'overview' : 'matching');
      await render();
    }
    if (type === 'profile') {
      const body = numberFields(
        {
          ...data,
          skills: splitSkills(data.skills),
          published: !!data.published,
          show_fsp: !!data.show_fsp,
        },
        ['salary', 'experience']
      );
      profileData = await put('/candidate/profile', body);
      user.name = body.name;
      toast('Профиль сохранён');
      await render();
    }
    if (type === 'resume-preview') {
      const profile = $('form[data-form="profile"]');
      if (!profile) throw new Error('Откройте анкету заново');
      for (const [key, value] of Object.entries(data)) {
        if (key === 'skills') {
          profile.elements.namedItem(key).value = [
            ...new Set([
              ...splitSkills(profile.elements.namedItem(key).value),
              ...splitSkills(value),
            ]),
          ].join(', ');
        } else if (value !== '') profile.elements.namedItem(key).value = value;
      }
      closeModal();
      toast('Поля добавлены в анкету. Проверьте их и сохраните профиль.');
    }
    if (type === 'fsp-link') {
      const r = await post('/candidate/fsp/link', data);
      modal(
        'Подтвердите ID ФСП',
        `${r.dev_code ? `<div class="demo-code"><small>Код из демо-реестра</small><strong>${esc(r.dev_code)}</strong></div>` : ''}<div class="spacer"></div><form data-form="fsp-confirm">${formError}${field('Код подтверждения', 'code', '', 'text', 'required pattern="[0-9]{6}" maxlength="6"')}<div class="modalfoot"><button>Подтвердить связь</button></div></form>`
      );
    }
    if (type === 'fsp-confirm') {
      await post('/candidate/fsp/confirm', data);
      closeModal();
      toast('ID связан с профилем');
      await render();
    }
    if (type === 'start-test') {
      attempt = await post('/candidate/tests', data);
      questionIndex = 0;
      toast('Тест начался. Удачи!');
      await render();
    }
    if (type === 'filters') {
      const previous = new URLSearchParams(location.hash.split('?')[1] || '');
      const params = new URLSearchParams({ ...data, fsp: !!data.fsp });
      for (const key of ['sort', 'view']) if (previous.has(key)) params.set(key, previous.get(key));
      if (location.hash === '#matching?' + params) await render();
      else go('matching?' + params);
    }
    if (type === 'invite') {
      await post(
        '/employer/invitations',
        numberFields({ ...data, candidate_id: Number(form.dataset.id) }, [
          'salary_from',
          'salary_to',
        ])
      );
      closeModal();
      toast('Приглашение отправлено кандидату');
      await render();
    }
    if (type === 'accept') {
      await patch('/invitations/' + form.dataset.id, {
        status: 'accepted',
        share_contacts: !!data.share_contacts,
      });
      closeModal();
      toast('Приглашение принято. Контакты открыты этой компании.');
      await render();
    }
    if (type === 'need') {
      const body = numberFields(
        { ...data, skills: splitSkills(data.skills), published: !!data.published },
        ['salary_from', 'salary_to']
      );
      if (form.dataset.id) await put('/employer/needs/' + form.dataset.id, body);
      else await post('/employer/needs', body);
      closeModal();
      toast('Потребность сохранена');
      await render();
    }
    if (type === 'company') {
      await put('/employer/company', data);
      toast('Информация о компании сохранена');
      await render();
    }
    if (type === 'task') {
      await post('/employer/tasks', data);
      closeModal();
      toast('Задание опубликовано');
      await render();
    }
    if (type === 'task-answer') {
      await post('/tasks/' + form.dataset.id + '/answer', data);
      toast('Решение отправлено на проверку');
      await render();
    }
    if (type === 'review') {
      await put(
        '/employer/task-answers/' + form.dataset.id,
        numberFields(data, ['correctness', 'completeness', 'reasoning'])
      );
      closeModal();
      toast('Оценка отправлена кандидату');
      await render();
    }
    if (type === 'job-apply') {
      await post('/jobs/' + form.dataset.id + '/apply', { share_contacts: !!data.share_contacts });
      closeModal();
      toast('Отклик отправлен');
      await render();
    }
    if (type === 'revoke-consent') {
      await post('/account/consent/revoke');
      closeModal();
      user = null;
      attempt = null;
      authMode = 'login';
      go('home');
      await render();
      toast('Согласие отозвано. Аккаунт деактивирован.');
    }
    if (type === 'delete-account' || type === 'erase-deactivated') {
      if (type === 'delete-account')
        await api('/account', { method: 'DELETE', body: { password: data.password } });
      else await post('/account/erasure', { email: data.email, password: data.password });
      closeModal();
      user = null;
      attempt = null;
      authMode = 'login';
      go('home');
      await render();
      toast('Аккаунт и связанные данные удалены из рабочей базы.');
    }
  } catch (error) {
    const err = $('.formerror', form);
    if (err && form.isConnected) err.textContent = error.message;
    else toast(error.message);
  } finally {
    if (submit) submit.disabled = false;
  }
});
document.addEventListener('click', async (e) => {
  if (e.target.closest('.skip-link')) {
    e.preventDefault();
    ($('#main-content') || $('#public-content')).focus();
    return;
  }
  const target = e.target.closest('[data-action]');
  if (!target) return;
  const a = target.dataset.action,
    id = target.dataset.id;
  e.preventDefault();
  try {
    if (a === 'close') closeModal();
    if (a === 'mobile-menu') {
      const open = $('.app-layout').classList.toggle('menu-open');
      target.setAttribute('aria-expanded', String(open));
      target.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
      if (open) $('#workspace-nav .navlink')?.focus();
    }
    if (a === 'match-view') updateMatchingQuery('view', target.dataset.view);
    if (a === 'match-page') updateMatchingQuery('page', target.dataset.page);
    if (a === 'clear-filters') {
      const params = new URLSearchParams(location.hash.split('?')[1] || '');
      params.delete('q');
      params.delete('fsp');
      params.delete('page');
      go('matching?' + params);
    }

    if (a === 'refresh') await render();
    if (a === 'auth-mode') {
      authMode = target.dataset.mode;
      if (location.hash === '#' + authMode) {
        await render();
        $('#public-content')?.focus({ preventScroll: true });
      } else go(authMode);
    }
    if (a === 'auth-role') {
      authRole = target.dataset.role;
      landing();
      $(`[data-role="${authRole}"]`)?.focus();
    }
    if (a === 'demo-login') {
      target.disabled = true;
      await demoLogin(target.dataset.role, target.dataset.reset === 'true');
    }
    if (a === 'demo-switch') {
      target.disabled = true;
      await demoLogin(user.role === 'candidate' ? 'employer' : 'candidate');
    }
    if (a === 'demo-reset')
      modal(
        'Начать личное демо заново?',
        `<p>Будут удалены только профили и действия вашего сценария. Другие браузеры сохранят свои данные.</p><div class="modalfoot">${btn('Отмена', 'close', 'outline')}${btn('Начать заново', 'demo-reset-confirm')}</div>`
      );
    if (a === 'demo-reset-confirm') {
      target.disabled = true;
      await demoLogin(user.role, true);
    }
    if (a === 'resend-code')
      modal(
        'Повторить подтверждение email',
        `<form data-form="resend">${formError}${field('Email', 'email', verifyEmail, 'email', 'required')}${field('Пароль аккаунта', 'password', '', 'password', 'required minlength="8"')}<div class="modalfoot"><button>Получить новый код</button></div></form>`
      );
    if (a === 'logout') {
      await waitForSavedAnswers();
      await post('/auth/logout');
      user = null;
      attempt = null;
      closeModal();
      authMode = 'login';
      go('home');
      await render();
    }
    if (a === 'notifications') await notificationModal();
    if (a === 'delete-account') deletionModal();
    if (a === 'erase-deactivated') deletionModal(true);
    if (a === 'marketing-opt-out') {
      await post('/account/marketing/opt-out');
      toast('Отказ от рекламных рассылок записан');
      await render();
    }
    if (a === 'read-notifications') {
      await post('/notifications/read');
      closeModal();
      toast('Уведомления прочитаны');
    }
    if (a === 'unlink-fsp') {
      await del('/candidate/fsp');
      toast('ID отключён');
      await render();
    }
    if (a === 'question') {
      questionIndex = Number(target.dataset.index);
      renderQuestion();
      $('#question-title')?.focus();
    }
    if (a === 'finish-test') {
      await waitForSavedAnswers();
      const unanswered =
        attempt.questions.length -
        Object.keys(attempt.answers).filter((k) => attempt.answers[k]).length;
      modal(
        'Завершить попытку?',
        `<p>${unanswered ? `Осталось ${unanswered} заданий без ответа. Они будут считаться неверными.` : 'Вы ответили на все задания.'} После завершения изменить ответы нельзя.</p><div class="modalfoot">${btn('Продолжить тест', 'close', 'outline')}${btn('Получить результат', 'finish-confirm', '')}</div>`
      );
    }
    if (a === 'finish-confirm') {
      await waitForSavedAnswers();
      target.disabled = true;
      const r = await post('/candidate/tests/' + attempt.id + '/finish');
      attempt = null;
      closeModal();
      await render();
      modal('Результат тестирования', resultHTML(r));
    }
    if (a === 'result') {
      const d = await api('/candidate/tests');
      modal('Результат тестирования', resultHTML(d.history.find((x) => x.id === id).result));
    }
    if (a === 'candidate-detail') {
      closeModal();
      await candidateModal(id);
    }
    if (a === 'match-explain') explainMatch(matches.find((p) => p.id == id));
    if (a === 'invite') await inviteModal(id);
    if (a === 'invitation-detail') await invitationModal(id);
    if (a === 'accept-invite') acceptModal(id);
    if (a === 'decline-invite' || a === 'withdraw-invite') {
      await patch('/invitations/' + id, {
        status: a === 'decline-invite' ? 'declined' : 'withdrawn',
      });
      toast('Статус обновлён');
      await render();
    }
    if (a === 'need-new') needModal();
    if (a === 'need-edit') needModal(needs.find((n) => n.id == id));
    if (a === 'task-new') taskModal();
    if (a === 'review-task') reviewModal(id);
    if (a === 'job-apply')
      modal(
        'Откликнуться на вакансию',
        `<p>Компания увидит ваш профиль и контакты для обсуждения вакансии.</p><form data-form="job-apply" data-id="${id}">${formError}${check('Разрешаю передать этой компании имя, email, телефон и Telegram из профиля.', 'share_contacts', false, 'required')}<div class="modalfoot"><button>Отправить отклик</button></div></form>`
      );
    if (a === 'toggle-publication' || a === 'toggle-fsp') {
      const p = profileBody(profileData);
      if (a === 'toggle-publication') p.published = !p.published;
      else p.show_fsp = !p.show_fsp;
      await put('/candidate/profile', p);
      toast('Настройки обновлены');
      await render();
    }
    if (a === 'revoke-contact') {
      await del('/candidate/contacts/' + id);
      toast('Доступ к контактам закрыт');
      await render();
    }
    if (a === 'revoke-consent')
      modal(
        'Деактивировать аккаунт?',
        `<p>Профиль будет скрыт, контакты закрыты, сеансы завершены. Войти повторно будет нельзя.</p><form data-form="revoke-consent">${formError}${check('Понимаю последствия и хочу отозвать согласие на обработку данных.', 'confirm', false, 'required')}<div class="modalfoot"><button class="danger">Отозвать и деактивировать</button></div></form>`
      );
  } catch (error) {
    toast(error.message);
  } finally {
    if (target.isConnected) target.disabled = false;
  }
});
document.addEventListener('change', async (e) => {
  if (e.target.matches('[data-resume-pdf]')) {
    const input = e.target,
      file = input.files[0];
    if (!file) return;
    input.disabled = true;
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error('PDF должен быть не больше 2 МБ');
      const result = await api('/candidate/resume/preview', {
        method: 'POST',
        body: file,
        headers: { 'Content-Type': 'application/pdf' },
      });
      const fields = result.suggestions;
      const labels = {
        name: 'Имя и фамилия',
        phone: 'Телефон',
        telegram: 'Telegram',
        experience: 'Опыт, лет',
        skills: 'Навыки через запятую',
      };
      modal(
        'Проверьте поля из резюме',
        `<p>Распознавание может ошибаться. Применение заполняет анкету; публикация и категория остаются под вашим контролем.</p><form data-form="resume-preview">${formError}${Object.entries(
          fields
        )
          .map(([key, value]) =>
            field(
              labels[key],
              key,
              Array.isArray(value) ? value.join(', ') : value,
              key === 'experience' ? 'number' : 'text',
              key === 'experience' ? 'min="0" max="60"' : 'maxlength="1500"'
            )
          )
          .join(
            ''
          )}<div class="modalfoot">${btn('Отмена', 'close', 'outline')}<button>Применить к анкете</button></div></form>`
      );
    } catch (error) {
      toast(error.message);
    } finally {
      input.disabled = false;
      input.value = '';
    }
    return;
  }
  if (e.target.matches('[data-match-sort]')) updateMatchingQuery('sort', e.target.value);
  if (e.target.matches('[data-test-spec]'))
    $('#test-levels').innerHTML = levelsHTML(testEligibility, e.target.value);
  if (e.target.matches('[data-answer]')) {
    saveAnswer(e.target.dataset.answer, e.target.value);
    if (attempt) {
      $$('#questiondots button').forEach((b, i) => {
        const answered = !!attempt.answers[attempt.questions[i].id];
        b.classList.toggle('done', answered);
        b.setAttribute(
          'aria-label',
          `Задание ${i + 1}, ${answered ? 'ответ указан' : 'без ответа'}`
        );
      });
    }
  }
});
document.addEventListener('input', (e) => {
  if (e.target.matches('[data-answer][type="text"]'))
    saveAnswer(e.target.dataset.answer, e.target.value);
});
$('#modal').addEventListener('click', (e) => {
  if (e.target === $('#modal')) {
    const r = $('#modal').getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)
      closeModal();
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && $('.menu-open')) {
    $('.app-layout').classList.remove('menu-open');
    const toggle = $('.menu-toggle');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Открыть меню');
    toggle.focus();
  }
});
window.addEventListener('hashchange', render);
window.addEventListener('beforeunload', (e) => {
  if (pendingSaves || (attempt && saveFailed)) {
    e.preventDefault();
    e.returnValue = '';
  }
});
(async () => {
  const [session, references] = await Promise.allSettled([api('/auth/me'), api('/references')]);
  user = session.status === 'fulfilled' ? session.value : null;
  demoEnabled = references.status === 'fulfilled' && references.value.demo;
  await render();
})();
