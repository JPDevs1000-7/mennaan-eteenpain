import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { STRINGS, LANG_NAMES, detectLang } from '../js/i18n.js';
import { LANGS } from '../js/codec.js';

test('every UI string exists in every language', () => {
  const reference = Object.keys(STRINGS.en).sort();
  for (const lang of LANGS) {
    assert.deepEqual(Object.keys(STRINGS[lang]).sort(), reference, `keys differ for ${lang}`);
    assert.ok(LANG_NAMES[lang]);
    for (const [k, v] of Object.entries(STRINGS[lang])) assert.ok(v.trim(), `${lang}.${k} is empty`);
  }
});

test('language detection falls back to English', () => {
  assert.equal(detectLang('fi-FI'), 'fi');
  assert.equal(detectLang('en-GB'), 'en');
  assert.equal(detectLang('sv-SE'), 'en');
  assert.equal(detectLang(''), 'en');
});

test('bundled content matches the manifest and the supported languages', () => {
  const manifest = JSON.parse(readFileSync('content/manifest.json', 'utf8'));
  assert.deepEqual(manifest.languages, LANGS);
  for (const week of manifest.weeks) {
    const data = JSON.parse(readFileSync(`content/weeks/${week}.json`, 'utf8'));
    assert.equal(data.week_id, week);
    assert.equal(data.questions.length, 7);
    for (const q of data.questions) {
      for (const lang of manifest.languages) assert.ok(q.translations[lang]?.text?.trim(), `${q.id} missing ${lang}`);
    }
  }
});
