import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/formatTokens.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { formatTokens, exactTokens } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('M display retains nonzero consumption below one thousand tokens', () => {
  assert.equal(formatTokens(0), '0 M');
  assert.equal(formatTokens(1), '<0.001 M');
  assert.equal(formatTokens(999), '<0.001 M');
  assert.equal(formatTokens(1000), '0.001 M');
});

test('M display scales by one million with at most three decimals', () => {
  assert.equal(formatTokens(1234567), '1.235 M');
  assert.equal(formatTokens(1000000), '1 M');
  assert.equal(formatTokens(1250000000), '1,250 M');
  assert.equal(formatTokens(NaN), '—');
  assert.equal(formatTokens(Infinity), '—');
});

test('exact values stay available without M rounding', () => {
  assert.equal(exactTokens(999), '999 Token');
  assert.equal(exactTokens(1234567), '1,234,567 Token');
  assert.equal(exactTokens(0), '0 Token');
});
