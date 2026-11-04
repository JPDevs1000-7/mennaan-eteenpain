// Magic State Link codec (schema v=1).
//
// Link:    <base>?v=1&state=<URL-safe Base64, no padding>
// Payload: byte 0      language index (LANGS, append-only)
//          bytes 1-2   start date, days since 2020-01-01 (uint16, big-endian)
//          bytes 3-4   history length in days (uint16, big-endian)
//          byte 5      email length in bytes (0 = no email; Partner Share links always 0)
//          next N      email, UTF-8
//          rest        history, 2 bits per day (0-3), 4 days per byte, day 0 in the lowest bits
//
// Changing this layout requires bumping SCHEMA_VERSION and keeping a decoder for v=1.

import { parseISODate, toISODate } from './dates.js';

export const SCHEMA_VERSION = 1;
export const LANGS = ['fi', 'en']; // index = on-the-wire value; only ever append
export const MAX_STATE_PARAM_LENGTH = 20000;

const EPOCH_MS = Date.UTC(2020, 0, 1);
const DAY_MS = 86400000;
const HEADER = 6;
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });

export class StateError extends Error {}

export function packPayload({ lang, startDate, history, email = '' }) {
  const langIndex = LANGS.indexOf(lang);
  if (langIndex < 0) throw new StateError('Unsupported language');
  const days = Math.round((parseISODate(startDate) - EPOCH_MS) / DAY_MS);
  if (days < 0 || days > 0xffff) throw new StateError('Start date out of range');
  const n = history.length;
  if (n > 0xffff) throw new StateError('History too long');
  for (const s of history) {
    if (!Number.isInteger(s) || s < 0 || s > 3) throw new StateError('Invalid status');
  }
  const emailBytes = encoder.encode(email || '');
  if (emailBytes.length > 255) throw new StateError('Email too long');

  const packed = new Uint8Array(Math.ceil(n / 4));
  history.forEach((s, i) => { packed[i >> 2] |= s << ((i & 3) * 2); });

  const out = new Uint8Array(HEADER + emailBytes.length + packed.length);
  out[0] = langIndex;
  out[1] = days >> 8;
  out[2] = days & 255;
  out[3] = n >> 8;
  out[4] = n & 255;
  out[5] = emailBytes.length;
  out.set(emailBytes, HEADER);
  out.set(packed, HEADER + emailBytes.length);
  return out;
}

export function unpackPayload(bytes) {
  if (bytes.length < HEADER) throw new StateError('Payload too short');
  const lang = LANGS[bytes[0]];
  if (!lang) throw new StateError('Unsupported language');
  const days = (bytes[1] << 8) | bytes[2];
  const n = (bytes[3] << 8) | bytes[4];
  const emailLen = bytes[5];
  if (bytes.length !== HEADER + emailLen + Math.ceil(n / 4)) throw new StateError('Payload length mismatch');
  let email = '';
  try {
    email = decoder.decode(bytes.subarray(HEADER, HEADER + emailLen));
  } catch {
    throw new StateError('Invalid email encoding');
  }
  const packed = bytes.subarray(HEADER + emailLen);
  const history = [];
  for (let i = 0; i < n; i++) history.push((packed[i >> 2] >> ((i & 3) * 2)) & 3);
  return { lang, startDate: toISODate(EPOCH_MS + days * DAY_MS), history, email };
}

export function toBase64Url(bytes) {
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function fromBase64Url(text) {
  if (!/^[A-Za-z0-9_-]*$/.test(text) || text.length % 4 === 1) throw new StateError('Invalid link data');
  const b64 = text.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (text.length % 4)) % 4);
  const bin = atob(b64);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

/** share=true produces a Partner Share state: the email is stripped. */
export function encodeState(state, { share = false } = {}) {
  return toBase64Url(packPayload({ ...state, email: share ? '' : state.email }));
}

export function buildLink(base, state, opts) {
  return `${base}?v=${SCHEMA_VERSION}&state=${encodeState(state, opts)}`;
}

/** Returns the decoded state, or null if the query string has no state parameter. */
export function decodeLink(search) {
  const params = new URLSearchParams(search);
  const state = params.get('state');
  if (state === null) return null;
  if (params.get('v') !== String(SCHEMA_VERSION)) throw new StateError('Unsupported link version');
  if (state.length > MAX_STATE_PARAM_LENGTH) throw new StateError('Link data too long');
  return unpackPayload(fromBase64Url(state));
}
