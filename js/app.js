// UI layer. Builds DOM with textContent only (never innerHTML): link data is untrusted input.

import { LANGS, StateError, buildLink, decodeLink } from './codec.js';
import { addDays, diffDays, localISODate, parseISODate } from './dates.js';
import { LANG_NAMES, detectLang, t } from './i18n.js';
import { STATUS, complete, computeStreaks } from './streaks.js';
import { buildSequence, getTimeline } from './timeline.js';

const STATE_KEY = 'cdp.state.v1';
const META_KEY = 'cdp.meta.v1';
const NUDGE_AFTER_DAYS = 7;
const NUDGE_SNOOZE_DAYS = 3;
const DAY_MS = 86400000;
const GLYPHS = { 0: '○', 1: '★', 2: '✓', 3: '+' };

const root = document.getElementById('app');
const live = document.getElementById('live');

let sequence = [];
let state = null;
let meta = {};
let lastLink = '';

// ---------- helpers ----------
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function readJSON(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}
function writeJSON(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable: keep running in memory */ }
}

function validState(s) {
  try {
    return s && LANGS.includes(s.lang) && parseISODate(s.startDate) !== undefined
      && Array.isArray(s.history) && s.history.every((x) => Number.isInteger(x) && x >= 0 && x <= 3)
      && typeof (s.email ?? '') === 'string';
  } catch { return false; }
}

const L = (key) => t(state?.lang ?? detectLang(), key);
const announce = (msg) => { live.textContent = ''; setTimeout(() => { live.textContent = msg; }, 50); };
const saveState = () => writeJSON(STATE_KEY, state);
const saveMeta = () => writeJSON(META_KEY, meta);
const questionText = (q) => (q.translations[state.lang] ?? q.translations.en)?.text ?? '';

// ---------- views ----------
function statusBadge(code) {
  return h('span', { class: `badge s${code}` },
    h('span', { 'aria-hidden': 'true', class: 'glyph' }, GLYPHS[code]),
    ' ', L(`status${code}`));
}

function renderOnboarding() {
  const lang = detectLang();
  document.documentElement.lang = lang;
  const choose = (chosen) => {
    state = { lang: chosen, startDate: localISODate(), history: [], email: '' };
    saveState();
    meta = { firstUseAt: Date.now() };
    saveMeta();
    render();
  };
  const order = [lang, ...LANGS.filter((l) => l !== lang)];
  root.replaceChildren(
    h('h1', {}, t(lang, 'appName')),
    h('p', { class: 'lead' }, t(lang, 'tagline')),
    h('h2', {}, t(lang, 'chooseLanguage')),
    h('div', { class: 'row', role: 'group', 'aria-label': t(lang, 'language') },
      order.map((l) => h('button', { class: 'btn big', type: 'button', lang: l, onclick: () => choose(l) }, LANG_NAMES[l]))),
  );
  root.focus();
}

function renderHeader() {
  return h('header', { class: 'top' },
    h('h1', {}, L('appName')),
    h('div', { class: 'row', role: 'group', 'aria-label': L('language') },
      LANGS.map((l) => h('button', {
        class: `btn small${l === state.lang ? ' on' : ''}`, type: 'button', lang: l,
        'aria-pressed': String(l === state.lang),
        onclick: () => { state.lang = l; saveState(); document.documentElement.lang = l; render(); },
      }, LANG_NAMES[l]))));
}

function completeDay(index) {
  state.history = complete(state.history, index, state.startDate, localISODate(), addDays);
  saveState();
  render();
  announce(L('completedAnnounce'));
}

function dayCard(day, { isToday }) {
  const status = state.history[day.index] ?? STATUS.PENDING;
  return h('article', { class: `card${isToday ? ' today' : ''}` },
    h('p', { class: 'meta' }, `${L('day')} ${day.index + 1} · ${L('theme')}: ${day.question.theme} · ${L('released')} ${day.releaseDate}`),
    h('p', { class: 'question', lang: state.lang }, questionText(day.question)),
    h('p', {}, statusBadge(status)),
    status === STATUS.PENDING && h('button', {
      class: 'btn big', type: 'button', onclick: () => completeDay(day.index),
    }, isToday ? L('markCompleted') : L('markCompletedLate')));
}

function streakCell(label, { current, best }) {
  return h('li', { class: 'streak' },
    h('strong', {}, label),
    h('span', {}, `${current} ${L('days')} (${L('current')}) · ${best} ${L('days')} (${L('best')})`));
}

function nudgeDue() {
  if (!state.history.some((s) => s !== STATUS.PENDING)) return false;
  const since = meta.lastBackupAt ?? meta.firstUseAt ?? Date.now();
  if (Date.now() - since < NUDGE_AFTER_DAYS * DAY_MS) return false;
  return !(meta.nudgeDismissedAt && Date.now() - meta.nudgeDismissedAt < NUDGE_SNOOZE_DAYS * DAY_MS);
}

function renderNudge() {
  if (!nudgeDue()) return null;
  return h('section', { class: 'nudge', 'aria-label': L('backupHeading') },
    h('p', {}, L('nudge')),
    h('div', { class: 'row' },
      h('a', { class: 'btn', href: '#backup' }, L('nudgeAction')),
      h('button', {
        class: 'btn secondary', type: 'button',
        onclick: () => { meta.nudgeDismissedAt = Date.now(); saveMeta(); render(); },
      }, L('nudgeDismiss'))));
}

async function copyLink(link, { backup }) {
  lastLink = link;
  if (backup) { meta.lastBackupAt = Date.now(); saveMeta(); }
  let ok = false;
  try { await navigator.clipboard.writeText(link); ok = true; } catch { /* fall back to manual copy */ }
  const box = document.getElementById('link-box');
  if (box) { box.value = link; box.select(); }
  announce(ok ? L('copied') : L('copyFailed'));
}

function renderBackup() {
  const base = location.origin + location.pathname; // runtime origin: domain agnostic
  const email = h('input', {
    id: 'email', type: 'email', autocomplete: 'email', value: state.email ?? '', maxlength: '120',
  });
  const readEmail = () => { state.email = email.value.trim(); saveState(); };
  return h('section', { id: 'backup', 'aria-labelledby': 'backup-h' },
    h('h2', { id: 'backup-h' }, L('backupHeading')),
    h('p', {}, L('backupIntro')),
    h('label', { for: 'email' }, L('emailLabel')),
    email,
    h('div', { class: 'row' },
      h('button', {
        class: 'btn', type: 'button',
        onclick: () => { readEmail(); copyLink(buildLink(base, state), { backup: true }); },
      }, L('copyBackup')),
      h('button', {
        class: 'btn secondary', type: 'button',
        onclick: () => { readEmail(); copyLink(buildLink(base, state, { share: true }), { backup: false }); },
      }, L('copyShare'))),
    h('p', { class: 'note' }, L('shareNote')),
    h('label', { for: 'link-box' }, L('linkLabel')),
    h('textarea', { id: 'link-box', readonly: true, rows: '3' }, lastLink));
}

function render() {
  document.documentElement.lang = state.lang;
  const today = localISODate();
  const tl = getTimeline(sequence, state.startDate, today);
  const streaks = computeStreaks(state.history, Math.max(0, tl.todayIndex));
  const latest = tl.days[tl.days.length - 1];
  const earlier = tl.days.slice(0, -1).reverse();

  let todayBlock;
  if (!sequence.length) todayBlock = h('p', {}, L('noContent'));
  else if (!latest) todayBlock = h('p', {}, L('moreSoon'));
  else todayBlock = [dayCard(latest, { isToday: latest.index === tl.todayIndex }), tl.contentExhausted && h('p', { class: 'note' }, L('moreSoon'))];

  root.replaceChildren(...[
    renderHeader(),
    renderNudge(),
    h('section', { 'aria-labelledby': 'today-h' }, h('h2', { id: 'today-h' }, L('todayHeading')), todayBlock),
    h('section', { 'aria-labelledby': 'streak-h' },
      h('h2', { id: 'streak-h' }, L('streaksHeading')),
      h('ul', { class: 'streaks' },
        streakCell(`${GLYPHS[1]} ${L('streakPerfect')}`, streaks.perfect),
        streakCell(`${GLYPHS[2]} ${L('streakBasic')}`, streaks.basic),
        streakCell(`${GLYPHS[3]} ${L('streakRescued')}`, streaks.rescued))),
    h('section', { 'aria-labelledby': 'earlier-h' },
      h('h2', { id: 'earlier-h' }, L('earlierHeading')),
      earlier.length ? earlier.map((d) => dayCard(d, { isToday: false })) : h('p', {}, L('noEarlier'))),
    renderBackup(),
    tl.bonus.length > 0 && h('details', {},
      h('summary', {}, `${L('bonusHeading')} (${tl.bonus.length})`),
      h('p', {}, L('bonusIntro')),
      h('ul', { class: 'bonus' }, tl.bonus.map((q) => h('li', { lang: state.lang }, questionText(q))))),
  ].filter(Boolean)); // null/false would otherwise be rendered as the text "null"/"false"
}

// ---------- boot ----------
async function loadContent() {
  const manifest = await (await fetch('content/manifest.json')).json();
  const weeks = await Promise.all(manifest.weeks.map(async (id) => (await fetch(`content/weeks/${id}.json`)).json()));
  return buildSequence(weeks);
}

function applyIncomingLink() {
  let incoming;
  try {
    incoming = decodeLink(location.search);
  } catch (e) {
    if (!(e instanceof StateError)) throw e;
    history.replaceState(null, '', location.pathname);
    return 'error';
  }
  if (!incoming) return null;
  history.replaceState(null, '', location.pathname); // keep state out of the address bar and history
  const lang = state?.lang ?? detectLang();
  if (state && !window.confirm(t(lang, 'linkConfirm'))) return null;
  state = incoming;
  saveState();
  meta = { ...meta, firstUseAt: meta.firstUseAt ?? Date.now(), lastBackupAt: Date.now() };
  saveMeta();
  return 'restored';
}

async function boot() {
  const stored = readJSON(STATE_KEY);
  state = validState(stored) ? stored : null;
  meta = readJSON(META_KEY) ?? {};

  const linkResult = applyIncomingLink();
  try {
    sequence = await loadContent();
  } catch {
    root.replaceChildren(h('p', { role: 'alert' }, t(state?.lang ?? detectLang(), 'loadError')));
    return;
  }
  if (!state) renderOnboarding();
  else render();
  if (linkResult === 'restored') announce(L('restored'));
  if (linkResult === 'error') {
    root.prepend(h('p', { role: 'alert', class: 'alert' }, t(state?.lang ?? detectLang(), 'linkError')));
  }
}

boot();
