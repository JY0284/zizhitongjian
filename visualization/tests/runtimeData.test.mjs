import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fetchRuntimeData } from '../src/utils/runtimeData.ts';

test('valid artifacts retain their payload and pass the abort signal', async (t) => {
  const signal = new AbortController().signal;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/preview/data/example.json');
    assert.equal(options.signal, signal);
    return Response.json({ roles: {} });
  });
  assert.deepEqual(await fetchRuntimeData('/preview/data/example.json', signal), { roles: {} });
});

test('missing data reports a useful error even when the dev server returns HTML 200', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<!doctype html>', {
    headers: { 'content-type': 'text/html' },
  }));
  await assert.rejects(fetchRuntimeData('/data/missing.json', new AbortController().signal), /准备运行时数据/);
});

test('malformed JSON and array roots are rejected', async (t) => {
  for (const body of ['{', '[]', 'null']) {
    t.mock.method(globalThis, 'fetch', async () => new Response(body, {
      headers: { 'content-type': 'application/json' },
    }));
    await assert.rejects(fetchRuntimeData('/data/broken.json', new AbortController().signal), /不是有效的 JSON 对象/);
    t.mock.restoreAll();
  }
});

test('aborted requests preserve the abort error', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => { throw new DOMException('Aborted', 'AbortError'); });
  await assert.rejects(fetchRuntimeData('/data/example.json', new AbortController().signal), { name: 'AbortError' });
});
