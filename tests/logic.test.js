import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isoWeekId, addDays, diffDays, parseISODate } from '../js/dates.js';
import {
  packPayload, unpackPayload, encodeState, buildLink, decodeLink, fromBase64Url, StateError,
} from '../js/codec.js';
import { statusFor, complete, computeStreaks } from '../js/streaks.js';
import { buildSequence, getTimeline, startOffset } from '../js/timeline.js';

const hex = (b) => Buffer.from(b).toString('hex');

// ---- dates ----
test('isoWeekId handles year boundaries', () => {
  assert.equal(isoWeekId('2026-11-04'), '2026-W45');
  assert.equal(isoWeekId('2026-01-01'), '2026-W01');
  assert.equal(isoWeekId('2021-01-03'), '2020-W53');
  assert.equal(isoWeekId('2024-12-30'), '2025-W01');
});

test('date arithmetic is DST safe and validates input', () => {
  assert.equal(addDays('2026-03-28', 3), '2026-03-31');
  assert.equal(addDays('2026-12-31', 1), '2027-01-01');
  assert.equal(diffDays('2026-10-24', '2026-10-26'), 2);
  assert.throws(() => parseISODate('2026-02-30'));
  assert.throws(() => parseISODate('nope'));
});

// ---- codec ----
test('payload layout is pinned (test vector)', () => {
  const bytes = packPayload({ lang: 'fi', startDate: '2026-08-01', history: [1, 2, 3, 0, 1] });
  assert.equal(hex(bytes), '000964' + '0005' + '00' + '3901');
});

test('payload with email layout', () => {
  const bytes = packPayload({ lang: 'en', startDate: '2020-01-01', history: [], email: 'a@b.c' });
  assert.equal(hex(bytes), '01' + '0000' + '0000' + '05' + Buffer.from('a@b.c').toString('hex'));
});

test('round trip with email, unicode and long history', () => {
  const history = Array.from({ length: 1000 }, (_, i) => i % 4);
  const state = { lang: 'en', startDate: '2026-08-01', history, email: 'jäsen@example.fi' };
  assert.deepEqual(unpackPayload(packPayload(state)), state);
});

test('partner share strips the email, self backup keeps it', () => {
  const state = { lang: 'fi', startDate: '2026-08-01', history: [1, 1], email: 'me@example.com' };
  const self = decodeLink(new URL(buildLink('https://x.test/', state)).search);
  const share = decodeLink(new URL(buildLink('https://x.test/', state, { share: true })).search);
  assert.equal(self.email, 'me@example.com');
  assert.equal(share.email, '');
  assert.deepEqual(share.history, [1, 1]);
});

test('link carries v=1 and is URL safe', () => {
  const state = { lang: 'fi', startDate: '2026-08-01', history: Array(400).fill(3), email: '' };
  const link = buildLink('https://x.test/', state);
  assert.match(link, /^https:\/\/x\.test\/\?v=1&state=[A-Za-z0-9_-]+$/);
});

test('decoder rejects bad input', () => {
  assert.equal(decodeLink('?foo=1'), null);
  assert.throws(() => decodeLink('?state=AAAA'), StateError); // missing v
  assert.throws(() => decodeLink('?v=2&state=AAAA'), StateError); // unknown version
  assert.throws(() => decodeLink('?v=1&state=***'), StateError);
  assert.throws(() => decodeLink('?v=1&state=AAAA'), StateError); // too short
  const good = encodeState({ lang: 'fi', startDate: '2026-08-01', history: [1, 2, 3, 0, 1] });
  assert.throws(() => decodeLink(`?v=1&state=${good}AA`), StateError); // trailing bytes
  assert.throws(() => fromBase64Url('A'), StateError);
});

test('encoder rejects invalid state', () => {
  const base = { lang: 'fi', startDate: '2026-08-01', history: [] };
  assert.throws(() => packPayload({ ...base, lang: 'xx' }), StateError);
  assert.throws(() => packPayload({ ...base, history: [4] }), StateError);
  assert.throws(() => packPayload({ ...base, startDate: '2019-12-31' }), StateError);
  assert.throws(() => packPayload({ ...base, email: 'x'.repeat(256) }), StateError);
});

// ---- statuses and streaks ----
test('status by timing', () => {
  assert.equal(statusFor('2026-11-04', '2026-11-04'), 1);
  assert.equal(statusFor('2026-11-04', '2026-11-05'), 2);
  assert.equal(statusFor('2026-11-04', '2026-11-06'), 3);
});

test('complete only sets pending days', () => {
  const h = complete([], 2, '2026-11-01', '2026-11-03', addDays);
  assert.deepEqual(h, [0, 0, 1]);
  assert.deepEqual(complete(h, 2, '2026-11-01', '2026-11-09', addDays), [0, 0, 1]);
  assert.deepEqual(complete(h, 0, '2026-11-01', '2026-11-03', addDays), [3, 0, 1]);
});

test('streaks: nested tiers, unfinished today does not break', () => {
  // days:      0  1  2  3  4(today, pending)
  const s = computeStreaks([1, 1, 2, 3, 0], 4);
  assert.deepEqual(s.perfect, { current: 0, best: 2 });
  assert.deepEqual(s.basic, { current: 0, best: 3 });
  assert.deepEqual(s.rescued, { current: 4, best: 4 });
  const t = computeStreaks([1, 1, 1], 2);
  assert.deepEqual(t.perfect, { current: 3, best: 3 });
  assert.deepEqual(computeStreaks([], 0).rescued, { current: 0, best: 0 });
});

// ---- timeline ----
const mkWeek = (week_id, theme) => ({
  week_id, theme,
  questions: [1, 2, 3, 4, 5, 6, 7].map((d) => ({
    day_of_week: d, id: `q-${week_id}-${d}`, translations: { en: { text: 't' } },
  })),
});
const seq = buildSequence([mkWeek('2026-W46', 'b'), mkWeek('2026-W45', 'a')]);

test('sequence is ordered across weeks', () => {
  assert.equal(seq.length, 14);
  assert.equal(seq[0].id, 'q-2026-W45-1');
  assert.equal(seq[7].id, 'q-2026-W46-1');
});

test('Day 1 is the first question of the start date week', () => {
  assert.equal(startOffset(seq, '2026-11-04'), 0); // W45 (Wednesday)
  assert.equal(startOffset(seq, '2026-11-09'), 7); // W46
  assert.equal(startOffset(seq, '2026-12-01'), 14); // beyond content
  const tl = getTimeline(seq, '2026-11-10', '2026-11-12'); // starts in W46
  assert.equal(tl.bonus.length, 7);
  assert.equal(tl.days.length, 3);
  assert.equal(tl.days[0].question.id, 'q-2026-W46-1');
  assert.equal(tl.days[2].releaseDate, '2026-11-12');
});

test('streak survives days with no published content', () => {
  const tl = getTimeline(seq, '2026-11-09', '2026-11-25'); // 16 days in, only 7 questions
  assert.equal(tl.lastIndex, 6);
  const history = [1, 1, 1, 1, 1, 1, 1];
  assert.equal(computeStreaks(history, tl.todayIndex).perfect.current, 0); // the old, wrong input
  assert.equal(computeStreaks(history, tl.lastIndex).perfect.current, 7); // what the app now passes
  assert.equal(getTimeline(seq, '2026-11-09', '2026-11-04').lastIndex, -1); // start in the future
  assert.deepEqual(computeStreaks([], -1).rescued, { current: 0, best: 0 });
});

test('timeline stops when content runs out and flags it', () => {
  const tl = getTimeline(seq, '2026-11-09', '2026-11-25');
  assert.equal(tl.days.length, 7);
  assert.equal(tl.contentExhausted, true);
  assert.equal(getTimeline(seq, '2026-11-09', '2026-11-09').contentExhausted, false);
});
