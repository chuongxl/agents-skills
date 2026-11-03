'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createStore, route } = require('../src/app');

const alice = { authorization: 'Bearer token-alice' };

test('lists only the caller notes', () => {
  const res = route('GET', '/notes', alice, createStore());
  assert.strictEqual(res.status, 200);
  assert.deepStrictEqual(res.body.map((n) => n.id), ['1']);
});

test('reads own note', () => {
  const res = route('GET', '/notes/1', alice, createStore());
  assert.strictEqual(res.status, 200);
});

test('cannot delete another user note', () => {
  const res = route('DELETE', '/notes/2', alice, createStore());
  assert.strictEqual(res.status, 404);
});

test('rejects missing token', () => {
  assert.strictEqual(route('GET', '/notes', {}, createStore()).status, 401);
});
