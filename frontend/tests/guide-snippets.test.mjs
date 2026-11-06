import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/guideSnippets.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { guideModels, buildGuideSnippets } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const route = { public_name: 'team-code-low', upstream_model: 'private-name', active: true, api_mode: 'both', max_output_tokens: 1024, reasoning_effort: 'low' };

test('guides only expose active authorized models for the chosen protocol', () => {
  const models = [route, { ...route, public_name: 'chat-only', api_mode: 'chat' }, { ...route, public_name: 'disabled', active: false }];
  assert.deepEqual(guideModels(models, 'codex').map(x => x.public_name), ['team-code-low']);
  assert.equal(guideModels(models, 'chat').length, 2);
  assert.deepEqual(guideModels([], 'responses'), []);
  assert.equal(buildGuideSnippets('https://relay.example'), null);
});

test('templates use current origin, public alias, bounded output and stateless transport', () => {
  const code = buildGuideSnippets('https://relay.example/', route);
  assert.equal(code.base, 'https://relay.example/v1');
  assert.ok(!Object.values(code).join('\n').includes('private-name'));
  assert.match(code.verify, /store=False, max_output_tokens=1024/);
  assert.match(code.codex, /model_reasoning_effort = "low"/);
  assert.match(code.codex, /env_key = "TOKEN_STATION_KEY"/);
  assert.match(code.codex, /supports_websockets = false/);
  assert.match(code.codex, /remote_compaction = "unsupported"/);
  assert.match(code.codex, /web_search = "disabled"/);
  assert.match(code.ccSwitch, /\[model_providers\.custom\]/);
  assert.match(code.ccSwitch, /experimental_bearer_token = "替换为你的中转 Key"/);
  assert.ok(!code.ccSwitch.includes('env_key'));
});

test('unfixed routes do not invent an unsupported reasoning level; string values are escaped', () => {
  const code = buildGuideSnippets('https://relay.example', { ...route, public_name: 'alias\'"\\line\nnext', reasoning_effort: null, max_output_tokens: 8192 });
  assert.ok(!code.codex.includes('model_reasoning_effort'));
  assert.match(code.codex, /\\nnext/);
  assert.equal(code.budget, 4096);
  assert.ok(code.curl.includes(`'"'"'`));
});
