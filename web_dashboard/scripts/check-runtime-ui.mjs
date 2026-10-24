// Render the actual Settings component with stale/fresh API values; no browser,
// network requests or installation credentials are involved.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const server = await createServer({ root, optimizeDeps: { noDiscovery: true, entries: [] }, server: { middlewareMode: true }, appType: 'custom' });
try {
  const { Settings } = await server.ssrLoadModule('/src/Workspace.tsx');
  for (const value of [null, undefined, true, false]) {
    const status = { integrations: {}, runtime: { managed: true, start_at_login: value, note: '', services: [] } };
    const api = { request() { throw new Error('Render must not make API calls'); } };
    const html = renderToStaticMarkup(React.createElement(Settings, { api, refresh: 0, changed() {}, status }));
    const button = html.match(/Start at Windows sign-in[\s\S]*?<button([^>]*)>([\s\S]*?)<\/button>/);
    assert.ok(button);
    if (typeof value !== 'boolean') {
      assert.match(button[1], /disabled/);
      assert.match(button[2], /Checking/);
    } else {
      assert.doesNotMatch(button[1], /disabled/);
      assert.match(button[2], value ? /Turn off/ : /Turn on/);
    }
  }
  console.log('Settings startup controls: stale/null/undefined and fresh booleans passed.');
} finally {
  await server.close();
}
