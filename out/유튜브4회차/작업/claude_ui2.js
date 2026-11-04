// 4회차 오프닝 — 클로드 창에서 한 줄 → 숏클 13단계(8배속) → 완성 카드 ▶ 클릭
// 단계 이름·"OO 완료 → OO" 문구 = tools/calcopy/hybrid/flow.py FORMAT_STAGES["해외원본형"]·_stage_msg 그대로
// 썸네일·대본 줄 = 실제 완성 쇼츠(src/tattoo.mp4) 프레임·박힌 자막에서
var V = window.V || {};   // 편마다 바꾸는 값(쇼츠 세로판 11-04: uiv/<이름>/v.js) — 없으면 타투 편 그대로
var MSG = V.MSG || "외국인 한국화장품 영상 만들어줘..";
var BOT = V.BOT || "숏클로 만들게요. 외국인이 한국 화장품을 써 보는 쇼츠 — 해외 원본 영상부터 찾겠습니다.";
var BOT2 = "완성됐습니다. 쇼츠 한 편과 썸네일이 준비됐어요.";
var STAGES = V.STAGES || ["준비 확인", "영상 확인", "해외 원본 찾기", "제품 확인", "자료 조사", "원본 정리", "원음 정리", "대본 쓰기", "대본 확인", "장면 맞추기", "글자 지우기·영상 만들기", "완성본 검사", "완성"];
var SCRIPT = V.SCRIPT || ["온몸 타투를 가린 외국인이 있는데요", "한번 보자, 쓱 발라 보더니", "바로 두 겹째 — 이게 두 겹이야", "세 겹을 바르자… 이게 세 겹이야", "타투를 가린 외국인은 엄마 반응 보자", "아~ 나도 올려 봐야겠다"];
var F = function (i) { return (V.DIR || "ui") + "/f" + i + ".jpg"; };
// 단계 이름 → 화면 모양(형식마다 단계 수가 달라 번호 대신 이름으로 고른다 — 이름 = flow.py FORMAT_STAGES)
var KIND = {"준비 확인": 0, "영상 확인": 1, "소재 확인": 1, "해외 원본 찾기": 2, "원본 영상 찾기": 2, "제품 확인": 3, "자료 조사": 4, "원본 정리": 5, "재료 영상 모으기": 5,
  "원음 정리": 6, "대본 쓰기": 7, "대본 확인": 8, "장면 맞추기": 9, "글자 지우기·영상 만들기": 10, "목소리·영상 만들기": 10, "완성본 검사": 11, "완성": 12};

// ── 시간표 ──
var _r = 7; function rnd() { _r = (_r * 16807) % 2147483647; return _r / 2147483647; }
function nkeys(ch) { var c = ch.charCodeAt(0) - 0xAC00; if (c < 0 || c > 11171) return 1; var jung = Math.floor(c / 28) % 21, jong = c % 28;
  var n = 2 + (jong ? 1 : 0); if ([9, 10, 11, 14, 15, 16, 19].indexOf(jung) >= 0) n++; if ([3, 5, 6, 9, 10, 11, 12, 13, 14, 15, 18].indexOf(jong) >= 0) n++; return n; }
var T0 = 0.8, KEYS = [], CHT = [], t_ = T0;
for (var i = 0; i < MSG.length; i++) { var ch = MSG[i];
  if (ch === ' ') { t_ += 0.16 + rnd() * 0.10; KEYS.push(t_); t_ += 0.05; CHT.push(t_); continue; }
  if (ch === '.' && i > 0 && MSG[i - 1] !== '.') t_ += 0.22;
  var k = nkeys(ch); for (var j = 0; j < k; j++) { KEYS.push(t_); t_ += 0.058 + rnd() * 0.035; } CHT.push(t_); }
var SEND = t_ + 0.55, B1 = SEND + 0.45, FF = B1 + 1.6, STEP = 1.25, S0 = FF + 0.25;
var DONE = S0 + STAGES.length * STEP, CARD = DONE + 0.9, PLAY = CARD + 1.6, END = PLAY + 0.5;
window.TL = { T0: T0, SEND: SEND, B1: B1, FF: FF, S0: S0, STEP: STEP, DONE: DONE, CARD: CARD, PLAY: PLAY, END: END, N: STAGES.length, KEYS: KEYS };

// ── 단계 블록 만들기 ──
var col = document.getElementById('col');
function el(tag, cls, html) { var d = document.createElement(tag); if (cls) d.className = cls; if (html != null) d.innerHTML = html; return d; }
var BLK = [];
STAGES.forEach(function (name, i) {
  var m = el('div', 'msg', i ? '<b>' + STAGES[i - 1] + '</b> 완료 → ' + name : '숏클 시작 → ' + name);
  var c = el('div', 'call');
  c.appendChild(el('div', 'h', '<span class="ic">숏</span>숏클 · ' + name + ' <span class="nm">shortcl_step</span><span class="ok"></span>'));
  var bd = el('div', 'bd'), body = null, k = KIND[name];
  if (k === 0) body = '<div class="chips"><span>타입캐스트 키 ✓</span><span>작업 폴더 ✓</span><span>영상 도구 ✓</span></div>';
  if (k === 1) body = '<div class="prog"><img src="' + F(0) + '"><div>' + (V.D1 || '해외 원본형 · 제품 장면 있음') + '<br><span style="color:#8a8577;font-size:14px">' + (V.D2 || '외국인이 한국 파운데이션을 바르는 영상') + '</span></div></div>';
  if (k === 2) { body = '<div>유튜브 · 틱톡 · 인스타 · 구글 렌즈 동시 검색 중…</div><div class="grid">'; for (var g = 0; g < 12; g++) body += '<img src="' + F(g) + '">'; body += '</div>'; }
  if (k === 3) body = '<div class="prog"><img src="' + F(3) + '"><div>' + (V.PROD || '제품 화면 확인 — 빨간 병 파운데이션') + '</div></div>';
  if (k === 4) body = '<div class="lines"><div>원본 설명 읽기</div><div>댓글 반응 읽기</div><div>제품 정보 확인</div></div>';
  if (k === 5) { body = '<div class="strip">'; for (var g = 0; g < 10; g++) body += '<img src="' + F(g + 2) + '">'; body += '</div>'; }
  if (k === 6) { body = '<div class="wave">'; for (var g = 0; g < 90; g++) body += '<i></i>'; body += '</div>'; }
  if (k === 7) { body = '<div class="lines">'; SCRIPT.forEach(function (s) { body += '<div>' + s + '</div>'; }); body += '</div>'; }
  if (k === 8) body = '<div class="chk"><div>문장 끝·맞춤법</div><div>지어낸 사실 없음</div><div>금지어 없음</div></div>';
  if (k === 9) { body = '<div class="match">'; SCRIPT.slice(0, 4).forEach(function (s, q) { body += '<div><img src="' + F(q * 3 + 1) + '">' + s.slice(0, 10) + '…</div>'; }); body += '</div>'; }
  if (k === 10) body = '<div class="prog"><img id="pv" src="' + F(0) + '"><div style="flex:1"><div>' + (V.RENDER || '원본 글자 지우기 · 목소리 · 자막 · 영상 합치기') + ' <span class="pc" id="pc">0%</span></div><div class="bar"><i id="pb"></i></div></div></div>';
  if (k === 11) body = '<div class="chk"><div>자막 겹침 없음</div><div>소리 크기</div><div>멈춘 장면 없음</div><div>썸네일</div></div>';
  if (body) { bd.innerHTML = body; c.appendChild(bd); }
  col.appendChild(m); col.appendChild(c);
  BLK.push({ k: k, m: m, c: c, ok: c.querySelector('.ok'), bd: body ? bd : null });
});
var b2 = el('div', 'bot'); b2.id = 'b2'; col.appendChild(b2);
var card = el('div', 'card', '<img src="' + (V.THUMB || 'tattoo_thumb.jpg') + '"><div><div class="t1">' + (V.TITLE || '한국 파데로 타투 가려 본 외국인') + '</div><div class="t2">쇼츠 · 9:16 · 완성본 + 썸네일</div><span class="pl" id="pl">▶ 재생</span></div>');
col.appendChild(card);

function on(list, t, t0, gap) { [].forEach.call(list, function (e, q) { e.classList.toggle('on', t >= t0 + q * gap); }); }

function render(t) {
  // 입력
  var typed = 0; while (typed < MSG.length && t >= CHT[typed] - 0.03) typed++;
  var sent = t >= SEND;
  document.getElementById('in').innerHTML = sent || !typed ? '<span class="ph">Claude에게 메시지 보내기</span>' : MSG.slice(0, typed);
  document.getElementById('caret').style.visibility = (Math.floor(t * 2) % 2 === 0 || (typed && !sent && typed < MSG.length)) ? 'visible' : 'hidden';
  document.getElementById('send').className = 'send' + (typed && !sent ? ' on' : '');
  var u = document.getElementById('u'); u.style.display = sent ? 'block' : 'none'; u.textContent = MSG;
  var b = document.getElementById('b'); b.style.display = t >= B1 ? 'block' : 'none'; b.textContent = BOT.slice(0, Math.max(0, Math.floor((t - B1) / 0.02)));
  // 8배속 표시
  var ffOn = t >= FF && t < DONE + 0.3;
  document.getElementById('ff').style.display = ffOn ? 'flex' : 'none';
  document.getElementById('ff').style.opacity = ffOn ? (0.75 + 0.25 * Math.abs(Math.sin(t * 6))) : 0;
  var fl = document.getElementById('ffline'); fl.style.width = ffOn ? (Math.min(1, (t - FF) / (DONE - FF)) * 100) + '%' : '0';
  // 단계
  BLK.forEach(function (B, i) {
    var s0 = S0 + i * STEP, s1 = s0 + STEP;
    B.m.style.display = t >= s0 ? 'block' : 'none';
    B.c.style.display = t >= s0 + 0.08 ? 'block' : 'none';
    B.ok.className = 'ok ' + (t >= s1 - 0.1 ? 'done' : 'run');
    B.ok.textContent = t >= s1 - 0.1 ? '✓ 완료' : ['◐', '◓', '◑', '◒'][Math.floor(t * 12) % 4] + ' 진행 중';
    if (!B.bd) return;
    var a = s0 + 0.15, bd = B.bd;
    if (B.k === 2) { var im = bd.querySelectorAll('img'); on(im, t, a, 0.06);
      [].forEach.call(im, function (e, q) { var pk = (q === 0 || q === 9); e.classList.toggle('pick', t >= s0 + 0.95 && pk); e.classList.toggle('dim', t >= s0 + 0.95 && !pk); }); }
    if (B.k === 4 || B.k === 7 || B.k === 8 || B.k === 11) on(bd.querySelectorAll('.lines div,.chk div'), t, a, B.k === 7 ? 0.16 : 0.22);
    if (B.k === 5) on(bd.querySelectorAll('img'), t, a, 0.08);
    if (B.k === 6) [].forEach.call(bd.querySelectorAll('i'), function (e, q) { var v = q / 90 < (t - a) / 0.9 ? 8 + 44 * Math.abs(Math.sin(q * 0.7) * Math.cos(q * 0.23)) : 2; e.style.height = v + 'px'; });
    if (B.k === 9) on(bd.querySelectorAll('.match div'), t, a, 0.2);
    if (B.k === 10) { var p = Math.max(0, Math.min(1, (t - a) / (STEP - 0.3))); document.getElementById('pb').style.width = (p * 100) + '%';
      document.getElementById('pc').textContent = Math.round(p * 100) + '%'; document.getElementById('pv').src = F(Math.min(15, Math.floor(p * 15))); }
  });
  b2.style.display = t >= DONE ? 'block' : 'none'; b2.textContent = BOT2.slice(0, Math.max(0, Math.floor((t - DONE) / 0.025)));
  card.style.display = t >= CARD ? 'flex' : 'none';
  // 화면 아래로 따라가기(입력창 위까지)
  var avail = 864 - 64 - 34 - 190, h = col.offsetHeight;
  col.style.transform = 'translateY(' + Math.min(0, avail - h) + 'px)';
  // 마우스 → ▶ 재생 클릭
  var cur = document.getElementById('cur'), fx = document.getElementById('clickfx');
  if (t >= CARD + 0.3) { var pl = document.getElementById('pl').getBoundingClientRect(), tx = pl.left + pl.width / 2, ty = pl.top + pl.height / 2;
    var p = Math.min(1, (t - CARD - 0.3) / (PLAY - CARD - 0.3)), e = 1 - Math.pow(1 - p, 3);
    cur.style.display = 'block'; cur.style.left = (1300 + (tx - 1300) * e) + 'px'; cur.style.top = (760 + (ty - 760) * e) + 'px';
    var q = (t - PLAY) / 0.4; fx.style.display = q >= 0 && q < 1 ? 'block' : 'none';
    fx.style.left = tx + 'px'; fx.style.top = ty + 'px'; fx.style.opacity = 1 - q; fx.style.width = fx.style.height = (30 + 50 * q) + 'px';
    document.getElementById('pl').style.background = t >= PLAY ? '#b85c3e' : '#d97757';
  } else { cur.style.display = 'none'; fx.style.display = 'none'; }
}
if (V.TOPIC) { var its = document.querySelectorAll('.item'), first = its[0].textContent;
  [].forEach.call(its, function (e, q) { if (q && e.textContent === V.TOPIC) e.textContent = first; }); its[0].textContent = V.TOPIC; document.querySelector('.top').textContent = V.TOPIC; }
window.render = render; render(0);
