import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/loadAdminSection.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { loadAdminSection } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('one 500 does not prevent five successful admin sections from updating', async () => {
  const state = { users: ['last-known-user'] };
  const names = ['总览', '上游', '模型', '用户列表', '调用日志', '审计日志'];
  const result = await Promise.all(names.map((label, index) => loadAdminSection(label, async () => {
    if (index === 3) throw new Error('请求失败（500）');
    return index;
  }, value => { state[label] = value; })));
  assert.equal(result.filter(Boolean).length, 1);
  assert.equal(result[3], '用户列表：请求失败（500）');
  assert.equal(state['调用日志'], 4);
  assert.equal(state['总览'], 0);
  assert.equal(Object.keys(state).length, 6);
  assert.deepEqual(state.users, ['last-known-user']);
});

test('fast sections update without waiting for a slow request; retry clears the failure', async () => {
  let release;
  const values = [];
  const slow = loadAdminSection('慢请求', () => new Promise(resolve => { release = resolve; }), value => values.push(value));
  assert.equal(await loadAdminSection('快请求', async () => 'fast', value => values.push(value)), '');
  assert.deepEqual(values, ['fast']);
  release('slow');
  assert.equal(await slow, '');
  assert.deepEqual(values, ['fast', 'slow']);
  assert.equal(await loadAdminSection('用户列表', async () => { throw 'offline'; }, () => assert.fail()), '用户列表：加载失败');
  assert.equal(await loadAdminSection('用户列表', async () => ['recovered'], value => values.push(value)), '');
  assert.deepEqual(values.at(-1), ['recovered']);
});
