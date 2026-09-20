// 장면꾸미기 — 틀이 계속 늘어나도 고르기가 복잡해지지 않게.
// 사장님 질문(2026-09-05): "템플릿을 여러 개 계속 만들 건데 어떻게 골라서 배치할 거냐".
// 답: ①tpl 폴더에 HTML을 넣으면 자동 등록  ②자리(후킹/본문)를 먼저 고르고 틀을 고른다
//     ③보통 2개만 고르면 26컷이 다 채워진다  ④많아지면 묶음 칩으로 좁힌다
var NL = String.fromCharCode(10);
var TPL = [], CUTS = 26, HOOK = 1, cut = 1, curSlot = 'hook';
var PICK = { hook: null, body: null, spot: {} };   // spot = {컷번호: 틀id}
var TITLE = ['일본 천재가 만들어', '떼돈번 제품의 정체'];
var SUB = '일본 천재가 만들어 떼돈번 제품 정체?';

function $(id) { return document.getElementById(id); }
function url(id, v) {
  var q = 'tpl=' + encodeURIComponent(id) + '&v=' + encodeURIComponent(JSON.stringify(v));
  return '/tpl_png?' + q;
}
function vals() {
  return { LINE1: TITLE[0], LINE2: TITLE[1], SUB: SUB,
           COLOR1: '#FFE600', COLOR2: '#FFFFFF', SCALEX: '0.94', SKEW: '-7' };
}
// 이 컷에 실제로 쓰이는 틀 — 자리 규칙을 여기 한 곳에서만 정한다
function tplForCut(n) {
  var keys = Object.keys(PICK.spot).map(Number).filter(function (k) { return k <= n; });
  if (keys.length) return PICK.spot[Math.max.apply(null, keys)];
  return n <= HOOK ? PICK.hook : PICK.body;
}
function drawPhone() {
  var id = tplForCut(cut);
  $('ovl').src = id ? url(id, vals()) : '';
  $('no').textContent = cut + ' / ' + CUTS + ' 컷';
  $('part').textContent = cut <= HOOK ? '후킹' : '본문';
}
function drawPlan() {
  var box = $('plan'), h = '';
  var seen = {}, colors = ['#2563eb', '#16a34a', '#d97706', '#9333ea', '#dc2626'], ci = 0;
  for (var n = 1; n <= CUTS; n++) {
    var id = tplForCut(n) || '(없음)';
    if (!(id in seen)) { seen[id] = colors[ci % colors.length]; ci++; }
  }
  var runStart = 1, prev = tplForCut(1);
  for (var m = 2; m <= CUTS + 1; m++) {
    var now = m <= CUTS ? tplForCut(m) : '__end';
    if (now !== prev) {
      var span = m - runStart, nm = (prev || '(안 고름)');
      h += '<div style="flex:' + span + ';background:' + (seen[prev || '(없음)'] || '#9ca3af') + '">'
         + (span >= 3 ? nm.split('_').pop() : '') + '</div>';
      runStart = m; prev = now;
    }
  }
  box.innerHTML = h;
}
function slot(s) {
  curSlot = s;
  var bs = document.querySelectorAll('.slot button');
  for (var i = 0; i < bs.length; i++) bs[i].classList.toggle('on', bs[i].dataset.s === s);
  $('slotlbl').textContent = '지금 고르는 자리: '
    + { hook: '후킹 (앞 ' + HOOK + '컷)', body: '본문 (나머지)', spot: '이 컷(' + cut + ')부터' }[s];
  drawCards();
}
function mv(d) {
  cut = Math.min(CUTS, Math.max(1, cut + d));
  if (curSlot === 'spot') slot('spot');
  drawPhone();
}
function drawCards() {
  var box = $('cards'), h = '';
  var cur = curSlot === 'spot' ? PICK.spot[cut] : PICK[curSlot];
  for (var i = 0; i < TPL.length; i++) {
    var t = TPL[i];
    h += '<div class="card' + (t.id === cur ? ' on' : '') + '" data-id="' + t.id + '">'
       + '<div class="pv"><img src="bg.jpg"><img src="' + url(t.id, vals()) + '"></div>'
       + '<b>' + t.name + '</b><i>' + (t.desc || '') + '</i></div>';
  }
  box.innerHTML = h;
  $('cnt').textContent = TPL.length + '개';
}
$('cards').addEventListener('click', function (e) {
  var c = e.target.closest('.card');
  if (!c) return;
  if (curSlot === 'spot') PICK.spot[cut] = c.dataset.id;
  else PICK[curSlot] = c.dataset.id;
  drawCards(); drawPhone(); drawPlan();
});
(function () {
  fetch('/tpl_list?_=' + Date.now()).then(function (r) { return r.json(); }).then(function (j) {
    TPL = j;
    PICK.hook = TPL[0] ? TPL[0].id : null;
    PICK.body = TPL[1] ? TPL[1].id : PICK.hook;
    // 묶음 칩 — 이름 앞머리로 자동으로 묶는다. 틀이 100개가 돼도 이걸로 좁힌다.
    var groups = {}, chips = '<button class="on" data-g="">전체 ' + TPL.length + '</button>';
    for (var i = 0; i < TPL.length; i++) {
      var g = TPL[i].id.split('_')[0];
      groups[g] = (groups[g] || 0) + 1;
    }
    for (var k in groups) chips += '<button data-g="' + k + '">' + k + ' ' + groups[k] + '</button>';
    $('chips').innerHTML = chips;
    $('chips').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      var bs = $('chips').querySelectorAll('button');
      for (var m = 0; m < bs.length; m++) bs[m].classList.toggle('on', bs[m] === b);
      var g = b.dataset.g;
      var cards = $('cards').querySelectorAll('.card');
      for (var n = 0; n < cards.length; n++)
        cards[n].style.display = (!g || cards[n].dataset.id.indexOf(g) === 0) ? '' : 'none';
    });
    slot('hook'); drawCards(); drawPhone(); drawPlan();
  });
})();
