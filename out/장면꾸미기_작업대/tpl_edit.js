// 템플릿 편집 — 미리보기는 실제 렌더와 같은 CSS를 쓴다(화면=결과물).
// 사장님 요구(2026-09-05): 패널을 좁게 · 자막도 · 줄 나누기 · 장면 넘기기.
// 기능이 늘어도 복잡해지지 않게 탭으로 갈라 한 번에 하나만 보인다.
var $ = function (id) { return document.getElementById(id); };
var NL = String.fromCharCode(10);
var DEF = { t1: '역발상으로 돈방석앉은', t2: '육아천재의 발명품',
  t3: '역발상으로 돈방석앉은 육아천재의 발명품',
  c1: '#ffe600', c2: '#ffffff', s1: 126, s2: 126, s3: 46,
  sk: -7, sx: 94, ol: 14, ls: -5, sh: 10,
  ct: '여러분 다이어트할 때 히카마는 무조건', cc: '#ffffff', cs: 52, co: 6, cok: '#000000' };
var beat = 1, capPosV = 'bot';
var CAPS = {};          // 장면별 줄나눔(손으로 고친 것만 저장)

function tab(n) {
  var bs = document.querySelectorAll('.tabs button');
  for (var i = 0; i < bs.length; i++) bs[i].classList.toggle('on', bs[i].dataset.t === n);
  var ps = document.querySelectorAll('.pane');
  for (var j = 0; j < ps.length; j++) ps[j].classList.toggle('on', ps[j].id === 'p-' + n);
}
// 자동 줄나눔 — 렌더 규칙과 같은 14자 기준
function autoLines(t) {
  var w = (t || '').trim().split(/\s+/), out = [], cur = '';
  for (var i = 0; i < w.length; i++) {
    if ((cur + ' ' + w[i]).trim().length > 14) { if (cur.trim()) out.push(cur.trim()); cur = w[i]; }
    else cur += ' ' + w[i];
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}
function curLines() { return CAPS[beat] || autoLines($('ct').value); }

function drawLines() {
  var box = $('lines'), ls = curLines(), h = '';
  for (var i = 0; i < ls.length; i++)
    h += '<div><input type="text" data-i="' + i + '" value="' + ls[i].replace(/"/g, '&quot;') + '"></div>';
  box.innerHTML = h;
  var ins = box.querySelectorAll('input');
  for (var k = 0; k < ins.length; k++) {
    (function (inp) {
      inp.addEventListener('keydown', function (e) {
        var i = +inp.dataset.i, l = curLines().slice();
        if (e.key === 'Enter') {                       // 여기서 끊기
          e.preventDefault();
          var p = inp.selectionStart;
          var a = inp.value.slice(0, p).trim(), b = inp.value.slice(p).trim();
          l.splice(i, 1, a, b);
          CAPS[beat] = l.filter(Boolean); drawLines(); draw();
        } else if (e.key === 'Backspace' && inp.selectionStart === 0 && i > 0) {   // 윗줄과 붙이기
          e.preventDefault();
          l[i - 1] = (l[i - 1] + ' ' + l[i]).trim(); l.splice(i, 1);
          CAPS[beat] = l; drawLines(); draw();
        }
      });
      inp.addEventListener('input', function () {
        var l = curLines().slice(); l[+inp.dataset.i] = inp.value; CAPS[beat] = l; draw();
      });
    })(ins[k]);
  }
}
function capSave() { CAPS[beat] = curLines(); draw(); }
function capAuto() { delete CAPS[beat]; drawLines(); draw(); }
function capPos(p) { capPosV = p; draw(); }
function mv(d) {
  beat = Math.min(12, Math.max(1, beat + d));
  $('no').textContent = beat + ' / 12';
  drawLines(); draw();
}
function draw() {
  var v = function (k) { return $(k).value; };
  $('l1').textContent = v('t1'); $('l2').textContent = v('t2'); $('sub').textContent = v('t3');
  var tr = 'scaleX(' + (v('sx') / 100) + ') skewX(' + v('sk') + 'deg)';
  var set = [[$('l1'), 's1', 'c1'], [$('l2'), 's2', 'c2']];
  for (var i = 0; i < set.length; i++) {
    var el = set[i][0];
    el.style.cssText = 'color:' + v(set[i][2]) + ';font-size:' + v(set[i][1]) + 'px;'
      + 'letter-spacing:' + v('ls') + 'px;transform:' + tr + ';'
      + '-webkit-text-stroke:' + v('ol') + 'px #000;text-shadow:0 ' + v('sh') + 'px 0 #000;'
      + 'display:block;padding:0 3%;line-height:1.02;white-space:nowrap;paint-order:stroke fill;'
      + (el.id === 'l2' ? 'margin-top:14px;' : '');
    var s = parseInt(el.style.fontSize, 10);
    while (el.scrollWidth > 1080 && s > 40) { s -= 2; el.style.fontSize = s + 'px'; }
  }
  $('sub').style.fontSize = v('s3') + 'px';
  $('bar').style.top = $('head').offsetHeight + 'px';
  $('bar').style.height = '128px';
  var cap = $('cap');
  cap.textContent = curLines().join(NL);
  cap.style.color = v('cc');
  cap.style.fontSize = v('cs') + 'px';
  cap.style.webkitTextStroke = v('co') + 'px ' + v('cok');
  cap.style.top = { top: '22%', mid: '47%', bot: '78%' }[capPosV];
  var units = { sk: '°', sx: '%' };
  var keys = ['sk', 'sx', 'ol', 'ls', 'sh', 'co'];
  for (var m = 0; m < keys.length; m++) {
    var e = $(keys[m] + 'v');
    if (e) e.textContent = $(keys[m]).value + (units[keys[m]] || 'px');
  }
}
function save() {
  var o = {};
  for (var k in DEF) o[k] = $(k).value;
  o.capPos = capPosV; o.capLines = CAPS;
  fetch('/state', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tpl_preset: o, _saved: new Date().toISOString() }) })
    .then(function () { alert('저장했습니다 — 다음부터 이 느낌으로 열립니다'); })
    .catch(function () { alert('저장 실패'); });
}
(function () {
  var ins = document.querySelectorAll('input');
  for (var i = 0; i < ins.length; i++) {
    if (ins[i].id === 'ct') continue;
    ins[i].addEventListener('input', draw);
  }
  $('ct').addEventListener('input', function () { delete CAPS[beat]; drawLines(); draw(); });
  $('file').addEventListener('change', function (e) {
    var f = e.target.files[0];
    if (f) $('vid').src = URL.createObjectURL(f);
  });
  drawLines(); draw();
})();
