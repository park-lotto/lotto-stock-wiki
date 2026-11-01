// 대본 린터 — 규칙표 판정 결과를 "고칠 방향 문장"으로만 돌려준다(설계 §4-4: 규칙 원문·임계값·규칙 id 비노출).
//   규칙 값은 bundle.rules.script(없으면 아래 기본값). 판단 주인 = lintScript() 한 곳.
export const DEFAULT_SCRIPT_RULES = Object.freeze({
  slots: [
    { role: '훅', length: '짧게' }, { role: '상황', length: '보통' }, { role: '전개', length: '보통' },
    { role: '반전', length: '보통' }, { role: '반응', length: '짧게' }, { role: '덤', length: '짧게' },
  ],
  extra_lines: 3,          // 칸 수보다 몇 줄까지 더 써도 되나
  line_max: 40,            // 한 줄 글자 수(공백 뺌) 상한
  line_min: 5,
  title_lines: 2,
  title_line_max: 15,
  speech: null,            // 'banmal' | 'jondaet' | null(섞지만 않으면 됨)
  numbers_need_source: true,
  last_line_statement: true,
});

const JON = /(요|니다|니까|세요|셔요|죠|십시오|에요|예요|까요|군요|네요)[\s.!?~…"'”’)]*$/;
const BAN = /(다|야|어|아|지|네|냐|자|라|거든|잖아|음|함|임|듯|걸|래|군|니|나|까)[\s.!?~…"'”’)]*$/;
const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
const URLISH = /(https?:\/\/|www\.|#[^\s#]+)/;
const bare = s => String(s || '').replace(/\s+/g, '');

export function speechOf(line) {
  const s = String(line || '').trim();
  if (JON.test(s)) return 'jondaet';
  if (BAN.test(s)) return 'banmal';
  return null;
}

const numbersIn = s => (String(s || '').match(/\d[\d,.]*/g) || []).map(n => n.replace(/[,.]+$/, '').replace(/,/g, ''));

export function rulesFrom(bundleRules) {
  const r = { ...DEFAULT_SCRIPT_RULES, ...((bundleRules && bundleRules.script) || {}) };
  // 실서버 모양: rules.roles = 칸 역할 문장 목록(괄호 안은 쓰는 법 안내) — 칸으로 쓴다
  if (bundleRules && Array.isArray(bundleRules.roles) && bundleRules.roles.length && !(bundleRules.script && bundleRules.script.slots)) r.slots = bundleRules.roles.filter(x => typeof x === 'string').slice(0, 12).map(x => ({ role: x, length: '보통' }));
  if (!Array.isArray(r.slots) || !r.slots.length) r.slots = DEFAULT_SCRIPT_RULES.slots;
  r.slots = r.slots.map(s => (typeof s === 'string' ? { role: s, length: '보통' } : { role: String(s.role || '칸'), length: s.length || '보통' }));
  return r;
}

// 사람 자리 ② 에 보여 줄 칸 안내(수치 없음)
export function scriptNeed(rules, titleLines) {
  return {
    kind: 'script',
    slots: rules.slots.map(s => ({ role: s.role, length: s.length })),
    title_lines: titleLines || rules.title_lines,
    speech: rules.speech === 'banmal' ? '반말' : rules.speech === 'jondaet' ? '존댓말' : undefined,
    form: "payload 에 {title: '제목 1줄\\n제목 2줄', lines: ['칸1 문장', '칸2 문장', …]} 로 주세요. 칸 역할 순서대로, 줄마다 한 문장.",
    ask: '아래 data(소재)를 읽고 칸 역할에 맞춰 대본을 써 주세요. 소재에 없는 숫자·사실은 쓰지 마세요.',
  };
}

// 반환 {ok, hints:[방향 문장], title, lines}
export function lintScript(input, rules, corpus = '', titleLines = 2) {
  const hints = [];
  const title = String((input && input.title) || '').replace(/\r/g, '').trim();
  const lines = Array.isArray(input && input.lines) ? input.lines.map(l => String(l || '').replace(/\s+/g, ' ').trim()).filter(Boolean) : [];
  const nSlots = rules.slots.length;
  if (!lines.length) return { ok: false, hints: ['대본 줄이 없습니다 — payload.lines 에 칸마다 한 문장씩 넣어 주세요'], title, lines };
  if (lines.length < Math.max(1, nSlots - 1)) hints.push(`줄이 모자랍니다 — 칸 ${nSlots}개 역할마다 한 줄씩 써 주세요`);
  if (lines.length > nSlots + rules.extra_lines) hints.push('줄이 너무 많습니다 — 칸 역할마다 한 줄로 묶어 주세요');
  const tl = title.split('\n').map(s => s.trim()).filter(Boolean);
  if (!tl.length) hints.push('제목이 없습니다 — payload.title 에 제목을 넣어 주세요');
  else if (tl.length !== titleLines) hints.push(titleLines > 1 ? `제목을 ${titleLines}줄로 나눠 주세요(줄바꿈 \\n)` : '제목을 한 줄로 써 주세요');
  tl.forEach((t, i) => { if (bare(t).length > rules.title_line_max) hints.push(`제목 ${i + 1}번째 줄을 더 짧게`); });
  lines.forEach((l, i) => {
    const n = bare(l).length;
    if (n > rules.line_max) hints.push(`${i + 1}번 줄을 더 짧게(두 줄로 나눠도 됩니다)`);
    else if (n < rules.line_min) hints.push(`${i + 1}번 줄을 조금 더 길게`);
    if (EMOJI.test(l) || URLISH.test(l)) hints.push(`${i + 1}번 줄에서 이모지·해시태그·링크를 빼 주세요`);
  });
  // 말투 — 규칙이 정해져 있으면 그 말투로, 아니면 섞이지 않게
  const sp = lines.map(speechOf);
  const want = rules.speech || (() => { const b = sp.filter(x => x === 'banmal').length, j = sp.filter(x => x === 'jondaet').length; return b === j ? null : b > j ? 'banmal' : 'jondaet'; })();
  if (want) sp.forEach((s, i) => { if (s && s !== want) hints.push(`${i + 1}번 줄 말투를 ${want === 'banmal' ? '반말' : '존댓말'}로`); });
  // 근거 없는 숫자
  if (rules.numbers_need_source) {
    const src = String(corpus || '').replace(/,/g, '');
    const check = (s, where) => { for (const num of numbersIn(s)) if (num && !src.includes(num)) { hints.push(`${where} 숫자에 근거가 없다 — 빼거나 소재에 있는 숫자로`); break; } };
    lines.forEach((l, i) => check(l, `${i + 1}번 줄`));
    tl.forEach((t, i) => check(t, `제목 ${i + 1}번째 줄`));
  }
  if (rules.last_line_statement && /[?？]\s*$/.test(lines[lines.length - 1])) hints.push('마지막 줄은 질문 말고 단정문으로');
  return { ok: hints.length === 0, hints: [...new Set(hints)], title: tl.join('\n'), lines };
}
