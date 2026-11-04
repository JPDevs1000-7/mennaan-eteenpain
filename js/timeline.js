// Maps a user's personal day numbers to the global question sequence. Pure functions, no DOM.
//
// Rules (ASSUMED, see docs/product-spec.md section 9):
//  - All published weeks are flattened, in ISO week order, into one sequence of questions.
//  - A user's Day 1 is the first question of the ISO week containing their start date
//    (or the first later published week), so weekly themes stay intact.
//  - Day i is released on startDate + i. Questions before the offset form the Bonus queue.

import { diffDays, addDays, isoWeekId } from './dates.js';

export function buildSequence(weeks) {
  const sorted = [...weeks].sort((a, b) => a.week_id.localeCompare(b.week_id));
  return sorted.flatMap((w) =>
    [...w.questions]
      .sort((a, b) => a.day_of_week - b.day_of_week)
      .map((q) => ({ id: q.id, week_id: w.week_id, theme: w.theme, translations: q.translations })),
  );
}

export function startOffset(sequence, startDate) {
  const startWeek = isoWeekId(startDate);
  const i = sequence.findIndex((q) => q.week_id >= startWeek);
  return i < 0 ? sequence.length : i;
}

export function getTimeline(sequence, startDate, today) {
  const offset = startOffset(sequence, startDate);
  const todayIndex = diffDays(startDate, today);
  const available = Math.max(0, sequence.length - offset);
  const last = Math.max(-1, Math.min(todayIndex, available - 1));
  const days = [];
  for (let i = 0; i <= last; i++) {
    days.push({ index: i, releaseDate: addDays(startDate, i), question: sequence[offset + i] });
  }
  return {
    todayIndex,
    // Last day that actually has a question. Streaks are measured up to here, so days with no
    // published content never count against the user.
    lastIndex: last,
    days,
    bonus: sequence.slice(0, offset),
    contentExhausted: todayIndex >= 0 && todayIndex > last,
  };
}
