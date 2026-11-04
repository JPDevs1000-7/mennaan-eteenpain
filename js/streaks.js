// Completion status and streak logic. Pure functions, no DOM.
// Status codes: 0 Pending, 1 Perfect, 2 On Time, 3 Rescued.

import { diffDays } from './dates.js';

export const STATUS = { PENDING: 0, PERFECT: 1, ON_TIME: 2, RESCUED: 3 };

/** Release day = Perfect; the following day = On Time; later = Rescued. */
export function statusFor(releaseDate, completedDate) {
  const delta = diffDays(releaseDate, completedDate);
  if (delta <= 0) return STATUS.PERFECT;
  if (delta === 1) return STATUS.ON_TIME;
  return STATUS.RESCUED;
}

/** Returns a new history array with day `index` completed today; no-op if already done. */
export function complete(history, index, startDate, today, addDays) {
  const next = history.slice();
  while (next.length <= index) next.push(STATUS.PENDING);
  if (next[index] === STATUS.PENDING) next[index] = statusFor(addDays(startDate, index), today);
  return next;
}

// Tiers are nested: Perfect streak = only Perfect days; Basic streak = Perfect or On Time;
// Rescued streak = any completed day (Rescued days keep a streak alive instead of breaking it).
const TIERS = {
  perfect: (s) => s === STATUS.PERFECT,
  basic: (s) => s === STATUS.PERFECT || s === STATUS.ON_TIME,
  rescued: (s) => s >= STATUS.PERFECT,
};

/** todayIndex: day index of today. An unfinished today does not break a current streak. */
export function computeStreaks(history, todayIndex) {
  const at = (i) => history[i] ?? STATUS.PENDING;
  const result = {};
  for (const [name, ok] of Object.entries(TIERS)) {
    let best = 0, run = 0;
    for (let i = 0; i <= todayIndex; i++) {
      run = ok(at(i)) ? run + 1 : 0;
      if (run > best) best = run;
    }
    let current = 0;
    let i = at(todayIndex) === STATUS.PENDING ? todayIndex - 1 : todayIndex;
    for (; i >= 0 && ok(at(i)); i--) current++;
    result[name] = { current, best };
  }
  return result;
}
