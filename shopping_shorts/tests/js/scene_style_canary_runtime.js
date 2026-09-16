const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const panel = {
  classList: {
    values: new Set(),
    add(value) { this.values.add(value); },
    remove(value) { this.values.delete(value); },
    contains(value) { return this.values.has(value); },
  },
};
const elements = {
  sceneStyleCanary: { hidden: true },
  sceneStyleCanaryStatus: { textContent: '' },
  sceneStyleCanaryFrame: { style: {}, dataset: {}, src: '' },
  sceneStyleStatus: { textContent: '' },
};
const context = {
  URLSearchParams,
  structuredClone,
  localStorage: {
    values: new Map(),
    setItem(key, value) { this.values.set(key, value); },
    getItem(key) { return this.values.get(key) || null; },
    removeItem(key) { this.values.delete(key); },
  },
  location: { search: '?scene_style_canary=1', origin: 'http://local.test' },
  MIX_JOB: 'exact-job',
  document: {
    head: { append() {} },
    createElement() { return { textContent: '' }; },
    querySelector(selector) { return selector === '.panel[data-step="3"]' ? panel : null; },
    getElementById(id) { return elements[id] || null; },
  },
  addEventListener() {},
  setTimeout() { return 0; },
  fetch: async () => ({
    ok: true,
    json: async () => ({ jobs: [{ job_id: 'exact-job', title: '현재 작업' }] }),
  }),
  console,
};
context.window = context;
vm.createContext(context);
const source = fs.readFileSync(
  path.resolve(__dirname, '../../static/scene-style-produce.js'),
  'utf8',
);
vm.runInContext(source, context);

(async () => {
  assert.equal(await context.syncSceneStyleCanary(), true);
  assert.equal(panel.classList.contains('scene-style-canary-active'), true);
  assert.equal(elements.sceneStyleCanaryFrame.dataset.jobId, 'exact-job');
  assert.match(elements.sceneStyleCanaryFrame.src, /job=exact-job$/);

  context.MIX_JOB = 'different-job';
  assert.equal(await context.syncSceneStyleCanary(), false);
  assert.equal(panel.classList.contains('scene-style-canary-active'), false);
  assert.equal(elements.sceneStyleCanaryFrame.style.display, 'none');
  assert.match(elements.sceneStyleCanaryStatus.textContent, /다른 작업으로 대신 열지 않습니다/);
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
