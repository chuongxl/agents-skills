'use strict';
const http = require('node:http');
const { createStore, route } = require('./app');

const store = createStore();

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const { status, body } = route(req.method, url.pathname, req.headers, store);
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(body === null ? '' : JSON.stringify(body));
});

server.listen(process.env.PORT || 3000);
