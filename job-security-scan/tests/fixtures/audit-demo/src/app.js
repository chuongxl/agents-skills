'use strict';

const { execFileSync } = require('node:child_process');

function createStore() {
  return {
    tokens: { 'token-alice': 'alice', 'token-bob': 'bob' },
    notes: [
      { id: '1', owner: 'alice', text: 'alice private note' },
      { id: '2', owner: 'bob', text: 'bob private note' },
    ],
  };
}

function authenticate(headers, store) {
  const header = headers.authorization || '';
  const match = /^Bearer (\S+)$/.exec(header);
  return match ? store.tokens[match[1]] || null : null;
}

function findNote(store, id) {
  return store.notes.find((n) => n.id === id) || null;
}

function route(method, path, headers, store) {
  const user = authenticate(headers, store);
  if (!user) return { status: 401, body: { error: 'unauthenticated' } };

  if (method === 'GET' && path === '/notes') {
    return { status: 200, body: store.notes.filter((n) => n.owner === user) };
  }

  const m = /^\/notes\/([^/]+)$/.exec(path);
  if (m && method === 'GET') {
    const note = findNote(store, m[1]);
    if (!note) return { status: 404, body: { error: 'not found' } };
    return { status: 200, body: note };
  }

  if (m && method === 'DELETE') {
    const note = findNote(store, m[1]);
    if (!note || note.owner !== user) return { status: 404, body: { error: 'not found' } };
    store.notes = store.notes.filter((n) => n.id !== note.id);
    return { status: 204, body: null };
  }

  if (method === 'GET' && path === '/version') {
    const rev = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { encoding: 'utf8' }).trim();
    return { status: 200, body: { rev } };
  }

  return { status: 404, body: { error: 'not found' } };
}

module.exports = { createStore, route };
