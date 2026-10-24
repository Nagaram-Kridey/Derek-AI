import { test } from 'node:test';
import assert from 'node:assert/strict';
import { desktopLaunchCode, exchangeDesktopLaunch } from './desktopSession.ts';
import { Api } from './api.ts';

test('desktop handoff accepts an exact short code and shares one exchange', async () => {
  const code = 'a'.repeat(43);
  assert.equal(desktopLaunchCode('#desktop-session=' + code), code);
  for (const bad of ['#desktop-session=short', '#desktop-session='+code+'&redirect=evil', '#chat']) assert.equal(desktopLaunchCode(bad), null);
  const api = new Api('');
  let calls = 0;
  api.post = async <T>() => { calls++; return { token: 'test', username: 'test' } as T; };
  const first=exchangeDesktopLaunch(api,code), second=exchangeDesktopLaunch(api,code);
  assert.equal(first,second);
  await first;
  assert.equal(calls,1);
});
