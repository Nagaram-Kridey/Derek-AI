import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readChat, saveChat, stateKey } from './chatState.ts';

test('chat recovery stores only opaque IDs in a token-specific namespace', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    },
  });
  try {
    const key = stateKey('private-auth-token', '');
    assert.ok(!key.includes('private-auth-token'));
    assert.notEqual(key, stateKey('other-token', ''));
    const value = {
      conversation: '12345678-1234-1234-1234-123456789abc',
      pending: {
        id: 'aaaaaaaa-1234-1234-1234-123456789abc',
        commandId: 'bbbbbbbb-1234-1234-1234-123456789abc',
      },
    };
    saveChat(key, value);
    assert.deepEqual(readChat(key), value);
    values.set(key, JSON.stringify({ conversation: 'bad', pending: { id: 'bad' } }));
    assert.deepEqual(readChat(key), { conversation: null, pending: null });
    values.set(key, '{invalid');
    assert.deepEqual(readChat(key), { conversation: null, pending: null });
  } finally {
    if (previous) Object.defineProperty(globalThis, 'localStorage', previous);
    else Reflect.deleteProperty(globalThis, 'localStorage');
  }
});

test('chat recovery tolerates blocked browser storage', () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    get() {
      throw new Error('Blocked');
    },
  });
  try {
    assert.deepEqual(readChat('key'), { conversation: null, pending: null });
    assert.doesNotThrow(() => saveChat('key', { conversation: null, pending: null }));
  } finally {
    if (previous) Object.defineProperty(globalThis, 'localStorage', previous);
    else Reflect.deleteProperty(globalThis, 'localStorage');
  }
});
