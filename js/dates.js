// Date helpers. All dates are plain 'YYYY-MM-DD' strings (device-local calendar days).
// Arithmetic goes through UTC midnight so DST never shifts a day.

const DAY_MS = 86400000;
const pad2 = (n) => String(n).padStart(2, '0');

export function parseISODate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s));
  if (!m) throw new Error(`Invalid date: ${s}`);
  const y = +m[1], mo = +m[2], d = +m[3];
  const t = Date.UTC(y, mo - 1, d);
  const dt = new Date(t);
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) {
    throw new Error(`Invalid date: ${s}`);
  }
  return t;
}

export const toISODate = (t) => new Date(t).toISOString().slice(0, 10);
export const addDays = (s, n) => toISODate(parseISODate(s) + n * DAY_MS);
export const diffDays = (a, b) => Math.round((parseISODate(b) - parseISODate(a)) / DAY_MS);

/** Today's date on the device's local calendar (decision: user-local midnight). */
export function localISODate(now = new Date()) {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

/** ISO 8601 week id, e.g. '2026-W45'. */
export function isoWeekId(s) {
  const t = parseISODate(s);
  const weekday = (new Date(t).getUTCDay() + 6) % 7; // Monday = 0
  const thursday = t + (3 - weekday) * DAY_MS;
  const year = new Date(thursday).getUTCFullYear();
  const week = Math.floor((thursday - Date.UTC(year, 0, 1)) / DAY_MS / 7) + 1;
  return `${year}-W${pad2(week)}`;
}
