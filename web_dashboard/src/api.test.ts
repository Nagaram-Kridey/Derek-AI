import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Api, safeHttpUrl} from './api.ts';

test('API confines credentials and handles authentication errors', async()=>{
  const previous = globalThis.fetch;
  let loggedOut = false;
  const api = new Api('secret','',()=>{loggedOut=true;});
  globalThis.fetch = async(_url,options)=>{assert.equal(new Headers(options?.headers).get('Authorization'),'Token secret');return new Response(JSON.stringify({detail:'Invalid token'}),{status:401});};
  try {await assert.rejects(()=>api.request('/v1/status/'),/Invalid token/);assert.equal(loggedOut,true);await assert.rejects(()=>api.request('https://evil.com'),/Invalid API path/);}
  finally {globalThis.fetch=previous;}
});
test('citation URLs reject executable schemes',()=>{
  assert.equal(safeHttpUrl('javascript:alert(1)'),undefined);
  assert.equal(safeHttpUrl('file:///secret'),undefined);
  assert.equal(safeHttpUrl('https://example.com'),'https://example.com/');
});
