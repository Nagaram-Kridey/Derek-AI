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

test('API rejects normalized and encoded path escapes before sending credentials', async()=>{
  const previous = globalThis.fetch;
  let called = false;
  globalThis.fetch = async()=>{called=true; throw new Error('Unexpected network');};
  try {
    const api = new Api('test-token');
    for (const path of ['/v1/../../outside', '/v1/%2e%2e/outside', '/v1/..\\outside', '//evil.com/v1/']) {
      await assert.rejects(()=>api.request(path),/Invalid API path/);
    }
    assert.equal(called,false);
  } finally {globalThis.fetch=previous;}
});

test('API fixes its credential header and refuses redirects', async()=>{
  const previous = globalThis.fetch;
  globalThis.fetch = async(url,options)=>{
    assert.equal(url,'/v1/tasks/');
    assert.equal(new Headers(options?.headers).get('Authorization'),'Token intended');
    assert.equal(options?.redirect,'error');
    assert.equal(options?.credentials,'same-origin');
    return new Response(null,{status:204});
  };
  try {assert.equal(await new Api('intended').request('/v1/tasks/',{headers:{Authorization:'Token unrelated'}}),undefined);}
  finally {globalThis.fetch=previous;}
});

test('API preserves aborts and sanitizes transport errors', async()=>{
  const previous = globalThis.fetch;
  const api = new Api('private-test-token');
  try {
    globalThis.fetch=async()=>{throw new DOMException('Stopped','AbortError');};
    await assert.rejects(()=>api.request('/v1/status/'),{name:'AbortError'});
    globalThis.fetch=async()=>{throw new Error('sensitive transport detail');};
    await assert.rejects(()=>api.request('/v1/status/'),/Cannot reach the assistant service/);
  } finally {globalThis.fetch=previous;}
});

test('API reads structured errors and does not sign out for a server failure', async()=>{
  const previous = globalThis.fetch;
  let signedOut=false;
  globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Try later'}),{status:503});
  try {
    await assert.rejects(()=>new Api('token','',()=>{signedOut=true;}).request('/v1/status/'),/Try later/);
    assert.equal(signedOut,false);
  } finally {globalThis.fetch=previous;}
});
