import { test } from 'node:test';
import assert from 'node:assert/strict';
import { shape } from '../server/firewall.js';
test('설정 get 의 자막 등장·강조 값이 잘리지 않는다(11-05 문인석 #7895)', () => {
  const r = shape({ info: { settings: { text: { caption: { enter: { kind: 'pop', ms: 200 }, emphasis: { words: 'auto', style: 'color', rgb: [255, 214, 0] } } } } } });
  assert.deepEqual(r.info.settings.text.caption.enter, { kind: 'pop', ms: 200 });
  assert.deepEqual(r.info.settings.text.caption.emphasis.rgb, [255, 214, 0]);
});
