import { test } from 'node:test';
import assert from 'node:assert/strict';
import { targetUrl } from '../js/migrate.js';

test('redirect keeps state parameters', () => {
  assert.equal(
    targetUrl('https://new.example/app/', '?v=1&state=AbC_-', '#x'),
    'https://new.example/app/?v=1&state=AbC_-#x',
  );
});

test('non-https targets are refused', () => {
  assert.throws(() => targetUrl('http://new.example/', '', ''));
  assert.throws(() => targetUrl('javascript:alert(1)', '', ''));
});
