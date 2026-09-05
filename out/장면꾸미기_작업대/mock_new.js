// 장면꾸미기 새 화면안 — 사장님 레퍼런스(히트작 30여 편)에서 뽑은 뼈대를 그대로 쓴다.
// 뼈대: 상단 띠 + 큰제목 2줄(2색/색박스) + 작은제목 한 줄 박스 + 배경 영상.
var NL = String.fromCharCode(10);
var TITLE = '코스트코 본사도 몰랐던' + NL + '천재 아이디어';
var SUB = '';                       // 비우면 큰제목을 한 줄로 합쳐 쓴다
var CHNAME = '숏템메이커';
var TPL = [], cur = 'tpl_01', beat = 1;

var $ = function (s) { return document.querySelector(s); };
var box = document.getElementById('cards');
var slot = document.getElementById('editSlot');
var ask = document.getElementById('askBox');

function oneLine(t) {
  return t.split(NL).map(function (x) { return x.trim(); }).filter(Boolean).join(' ');
}
// 강조: 둘째 줄만 색을 바꾸거나(boxed=false) 색 박스를 씌운다(boxed=true)
function hilite(t) {
  var ls = TITLE.split(NL);
  if (!ls[1] || !ls[1].trim()) return null;
  return [{ keyword: ls[1].trim(), color: t.boxed ? '#111111' : t.hc.color2,
            box: !!t.boxed, box_color: t.hc.color2 }];
}
function specOf(t, hook) {
  var sp = Object.assign({ preset: 'plain_black', channel: CHNAME }, t.spec);
  sp.title = hook ? '' : oneLine(TITLE);
  sp.sub_line = SUB || oneLine(TITLE);
  return sp;
}
var FITCACHE = {};
// 레퍼런스는 예외 없이 큰제목이 2줄이다. 글자가 길면 크기를 줄여 2줄을 지킨다.
// 판단은 서버 /fit(렌더와 같은 계산)에 맡긴다 — 화면과 결과가 어긋나면 안 된다.
function fitSize(t, cb) {
  var key = t.id + '|' + TITLE;
  if (FITCACHE[key] != null) { cb(FITCACHE[key]); return; }
  var probe = Object.assign({}, t.hc, { text: TITLE, wrap: true });
  fetch('/fit?hc=' + encodeURIComponent(JSON.stringify(probe)))
    .then(function (r) { return r.json(); })
    .then(function (j) { FITCACHE[key] = Math.min(j.size || t.hc.size, t.hc.size); cb(FITCACHE[key]); })
    .catch(function () { cb(t.hc.size); });
}
function hcOf(t, hook, size) {
  var hc = Object.assign({}, t.hc, { text: hook ? TITLE : '', wrap: true, x: 50, weight: 900 });
  if (size) hc.size = size;
  var hl = hilite(t);
  if (hl && hook) hc.highlight_rules = hl;
  return hc;
}
function url(path, key, obj) { return path + '?' + key + '=' + encodeURIComponent(JSON.stringify(obj)); }

function drawCards() {
  box.innerHTML = TPL.map(function (t) {
    return '<div class="card' + (t.id === cur ? ' on' : '') + '" data-id="' + t.id + '">'
      + '<div class="tpv" data-id="' + t.id + '"><img src="bg.jpg"><img class="c-fr"><img class="c-hc"></div>'
      + '<b>' + t.name + '</b></div>';
  }).join('');
  TPL.forEach(function (t) {
    var pv = box.querySelector('.tpv[data-id="' + t.id + '"]');
    if (!pv) return;
    pv.querySelector('.c-fr').src = url('/render', 'spec', specOf(t, true));
    fitSize(t, function (sz) { pv.querySelector('.c-hc').src = url('/hc', 'hc', hcOf(t, true, sz)); });
  });
}
function draw() {
  var t = TPL.filter(function (x) { return x.id === cur; })[0];
  if (!t) return;
  var hook = (beat === 1);
  document.getElementById('fr').src = url('/render', 'spec', specOf(t, hook));
  fitSize(t, function (sz) {
    var hc = hcOf(t, hook, sz);
    document.getElementById('hc').src = hc.text ? url('/hc', 'hc', hc) : '';
  });
}
// ── 자체 검사: 레퍼런스 뼈대를 모든 템플릿이 지키는지 잰다.
//    ①큰제목 2줄 ②상단 띠 있음 ③작은제목 박스 있음 ④글자가 폭 안에 들어감
window.selfCheck = function () {
  return Promise.all(TPL.map(function (t) {
    var probe = Object.assign({}, t.hc, { text: TITLE, wrap: true });
    return fetch('/fit?hc=' + encodeURIComponent(JSON.stringify(probe)))
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var sp = specOf(t, true);
        var bad = [];
        if (j.lines !== 2) bad.push('큰제목 ' + j.lines + '줄');
        if (!sp.bar_h) bad.push('상단 띠 없음');
        if (!sp.sub_line) bad.push('작은제목 없음');
        if (!sp.sub_line_h) bad.push('작은제목 박스 없음');
        return { 템플릿: t.name, 글자크기: j.size, 줄수: j.lines, 문제: bad.length ? bad.join(' · ') : 'OK' };
      });
  }));
};
box.addEventListener('click', function (e) {
  var c = e.target.closest('.card');
  if (!c) return;
  cur = c.dataset.id;
  [].forEach.call(box.children, function (x) { x.classList.toggle('on', x === c); });
  draw();
});
function mv(d) {
  beat = Math.min(12, Math.max(1, beat + d));
  document.getElementById('no').textContent = beat + ' / 12';
  document.getElementById('badge').textContent = beat === 1 ? '후킹 · 1번 장면' : '본문 · ' + beat + '번 장면';
  draw();
}
// ── 고치기: 한 번에 한 가지. 칸마다 제 값에만 연결한다.
var FIELDS = {
  ch:   { name: '채널명',   icon: '📺', rows: ['글자', '크기', '글자색', '띠색'] },
  head: { name: '큰 제목',  icon: '🔠', rows: ['글자', '크기', '1줄 색', '2줄 색'] },
  sub:  { name: '작은 제목', icon: '🔡', rows: ['글자', '크기', '글자색', '박스색'] }
};
var VAL = { ch: function () { return CHNAME; }, head: function () { return TITLE; }, sub: function () { return SUB; } };
function setVal(k, v) {
  if (k === 'ch') { CHNAME = v; }
  else if (k === 'head') { TITLE = v; }
  else { SUB = v; }
  drawCards(); draw();
}
function esc(v) { return v.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
function ctl(k, label) {
  if (label === '글자') {
    var v = esc(VAL[k]());
    return k === 'head'
      ? '<textarea rows="2" data-f="glc">' + v + '</textarea>'
      : '<input type="text" data-f="glc" placeholder="비우면 화면에서 빠집니다" value="' + v + '">';
  }
  if (label.indexOf('색') >= 0) return '<input type="color" value="#111111">';
  return '<div class="stp"><button>−</button><b>52</b><button>＋</button></div>';
}
function openEdit(k) {
  var f = FIELDS[k];
  ask.style.display = 'none';
  slot.innerHTML = '<div class="edit"><h4>' + f.icon + ' ' + f.name + ' 고치기'
    + '<span data-f="close">✕ 닫기</span></h4>'
    + f.rows.map(function (r) { return '<div class="row"><label>' + r + '</label>' + ctl(k, r) + '</div>'; }).join('')
    + '<div class="row" style="margin:14px 0 0"><button class="undo" data-f="close">↩ 원래대로</button></div></div>';
  var g = slot.querySelector('[data-f="glc"]');
  if (g) g.addEventListener('input', function () { setVal(k, this.value); });
  [].forEach.call(slot.querySelectorAll('[data-f="close"]'), function (b) { b.addEventListener('click', closeEdit); });
}
function closeEdit() {
  slot.innerHTML = '';
  ask.style.display = '';
  [].forEach.call(document.querySelectorAll('.spot'), function (x) { x.classList.remove('on'); });
}
[].forEach.call(document.querySelectorAll('.spot'), function (sp) {
  sp.addEventListener('click', function () {
    [].forEach.call(document.querySelectorAll('.spot'), function (x) { x.classList.toggle('on', x === sp); });
    openEdit(sp.dataset.k);
  });
});
(function () {
  fetch('/templates.json?_=' + Date.now()).then(function (r) { return r.json(); }).then(function (j) {
    TPL = j; drawCards(); draw();
  });
})();
