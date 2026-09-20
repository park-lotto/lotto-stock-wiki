// 장면꾸미기 — 왼쪽 템플릿 · 가운데 미리보기 · 오른쪽 설정(제목/자막/효과).
// 미리보기는 실제 렌더 PNG라 여기서 본 그대로 영상에 들어간다.
var NL = String.fromCharCode(10);
var TPL = [], CUTS = 26, HOOK = 1, cut = 1, curTpl = null;
var CAPLINES = {}, capPosV = 'bot';
var FX = { ad: 1, badge: 0, profile: 0, icons: 0, progress: 0, shorts: 0 };
var DEF = { t1: '역발상으로 돈방석앉은', t2: '육아천재의 발명품',
            t3: '역발상으로 돈방석앉은 육아천재의 발명품', ch: '숏템메이커',
            c1: '#ffe600', c2: '#ffffff', s1: 126, s2: 126, s3: 46,
            sk: -7, sx: 94, ol: 14, ls: -5, sh: 10,
            ct: '여러분 다이어트할 때 히카마는 무조건', cc: '#ffffff', cs: 52, co: 6, cok: '#000000',
            badgetxt: '진짜 봐야할 것', badgec: '#ff2d55', profc: '#e8452c', pg: 38 };
function $(id) { return document.getElementById(id); }

function vals() {
  return { LINE1: $('t1').value, LINE2: $('t2').value, SUB: $('t3').value, CH: $('ch').value,
           COLOR1: $('c1').value, COLOR2: $('c2').value,
           SIZE1: $('s1').value, SIZE2: $('s2').value, SIZE3: $('s3').value,
           SCALEX: ($('sx').value / 100).toFixed(2), SKEW: $('sk').value,
           OL: $('ol').value, LS: $('ls').value, SH: $('sh').value,
           CAP: curLines().join('|'), CAPC: $('cc').value, CAPSZ: $('cs').value,
           CAPO: $('co').value, CAPOC: $('cok').value, CAPPOS: capPosV,
           AD: FX.ad, BADGE: FX.badge ? $('badgetxt').value : '', BADGEC: $('badgec').value,
           PROFILE: FX.profile ? ($('ch').value || '숏')[0] : '', PROFC: $('profc').value,
           ICONS: FX.icons, PROGRESS: FX.progress ? $('pg').value : 0, SHORTS: FX.shorts };
}
function url(id) {
  return '/tpl_png?tpl=' + encodeURIComponent(id) + '&v=' + encodeURIComponent(JSON.stringify(vals()));
}
function tab(n) {
  var bs = document.querySelectorAll('.tabs button');
  for (var i = 0; i < bs.length; i++) bs[i].classList.toggle('on', bs[i].dataset.t === n);
  var ps = document.querySelectorAll('.pane');
  for (var j = 0; j < ps.length; j++) ps[j].classList.toggle('on', ps[j].id === 'p-' + n);
}
function fx(k) {
  FX[k] = FX[k] ? 0 : 1;
  var e = document.querySelector('.sw[data-k="' + k + '"]');
  if (e) e.classList.toggle('on', !!FX[k]);
  draw();
}
// ── 자막 (렌더와 같은 14자 기준)
function autoLines(t) {
  var w = (t || '').trim().split(/\s+/), out = [], cur = '';
  for (var i = 0; i < w.length; i++) {
    if ((cur + ' ' + w[i]).trim().length > 14) { if (cur.trim()) out.push(cur.trim()); cur = w[i]; }
    else cur += ' ' + w[i];
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}
function curLines() { return CAPLINES[cut] || autoLines($('ct') ? $('ct').value : ''); }
function drawLines() {
  var ls = curLines(), h = '';
  for (var i = 0; i < ls.length; i++)
    h += '<input type="text" data-i="' + i + '" value="' + ls[i].replace(/"/g, '&quot;') + '">';
  $('lines').innerHTML = h;
  var ins = $('lines').querySelectorAll('input');
  for (var k = 0; k < ins.length; k++) (function (inp) {
    inp.addEventListener('keydown', function (e) {
      var i = +inp.dataset.i, l = curLines().slice();
      if (e.key === 'Enter') {
        e.preventDefault();
        var p = inp.selectionStart;
        l.splice(i, 1, inp.value.slice(0, p).trim(), inp.value.slice(p).trim());
        CAPLINES[cut] = l.filter(Boolean); drawLines(); draw();
      } else if (e.key === 'Backspace' && inp.selectionStart === 0 && i > 0) {
        e.preventDefault();
        l[i - 1] = (l[i - 1] + ' ' + l[i]).trim(); l.splice(i, 1);
        CAPLINES[cut] = l; drawLines(); draw();
      }
    });
    inp.addEventListener('input', function () {
      var l = curLines().slice(); l[+inp.dataset.i] = inp.value; CAPLINES[cut] = l; draw();
    });
  })(ins[k]);
}
function capAuto() { delete CAPLINES[cut]; drawLines(); draw(); }
function capAll() { alert('이 자막 설정을 ' + CUTS + '컷 전체에 적용했습니다'); }
function capPos(p) { capPosV = p; draw(); }
function mv(d) {
  cut = Math.min(CUTS, Math.max(1, cut + d));
  $('no').textContent = cut + ' / ' + CUTS;
  $('part').textContent = cut <= HOOK ? '후킹' : '본문';
  drawLines(); draw();
}
function playAll() {
  var n = 1;
  var t = setInterval(function () {
    cut = n; $('no').textContent = cut + ' / ' + CUTS;
    $('part').textContent = cut <= HOOK ? '후킹' : '본문';
    drawLines(); draw();
    if (++n > CUTS) clearInterval(t);
  }, 600);
}
// ── 그리기
var tmr = null;
function draw() {
  for (var i = 1; i <= 3; i++) {
    var e = $('n' + i);
    if (e) e.textContent = $('t' + i).value.length + '/' + (i === 3 ? 30 : 20);
  }
  var units = { sk: '°', sx: '%', pg: '%' };
  var keys = ['sk', 'sx', 'ol', 'ls', 'sh', 'co', 'pg'];
  for (var m = 0; m < keys.length; m++) {
    var v = $(keys[m] + 'v');
    if (v && $(keys[m])) v.textContent = $(keys[m]).value + (units[keys[m]] || 'px');
  }
  if (!curTpl) return;
  clearTimeout(tmr);
  tmr = setTimeout(function () { $('ovl').src = url(curTpl); }, 240);
}
function drawCards() {
  var b = $('chips').querySelector('button.on');
  var f = b ? b.dataset.g : '';
  var q = ($('q').value || '').trim();
  var h = '';
  for (var i = 0; i < TPL.length; i++) {
    var x = TPL[i];
    if (f && f !== '__mine' && x.id.indexOf(f) !== 0) continue;
    if (q && x.name.indexOf(q) < 0 && (x.desc || '').indexOf(q) < 0) continue;
    h += '<div class="tcard' + (x.id === curTpl ? ' on' : '') + '" data-id="' + x.id + '">'
       + '<div class="tpv"><img src="bg.jpg"><img src="' + url(x.id) + '"></div>'
       + '<b>' + x.name + '</b></div>';
  }
  h += '<div class="newt" onclick="alert(\'tpl 폴더에 HTML을 넣으면 여기에 자동으로 뜹니다\')">＋<span>직접 만들기</span></div>';
  $('grid').innerHTML = h;
}
function saveTpl() {
  fetch('/state', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ studio: { tpl: curTpl, vals: vals(), caps: CAPLINES, fx: FX },
                           _saved: new Date().toISOString() }) })
    .then(function () { alert('내 틀로 저장했습니다'); });
}
function go() {
  alert('고른 틀: ' + (curTpl || '없음') + NL + CUTS + '컷을 이 틀로 만듭니다.' + NL
        + '(제작 파이프라인 연결은 다음 단계입니다)');
}
(function () {
  for (var k in DEF) if ($(k)) $(k).value = DEF[k];
  $('grid').addEventListener('click', function (e) {
    var c = e.target.closest('.tcard'); if (!c) return;
    curTpl = c.dataset.id;
    var cs = $('grid').querySelectorAll('.tcard');
    for (var i = 0; i < cs.length; i++) cs[i].classList.toggle('on', cs[i] === c);
    draw();
  });
  $('q').addEventListener('input', drawCards);
  $('file').addEventListener('change', function (e) {
    var f = e.target.files[0]; if (!f) return;
    var u = URL.createObjectURL(f), old = $('vid');
    var el = f.type.indexOf('video') === 0 ? document.createElement('video') : document.createElement('img');
    el.className = 'vid'; el.id = 'vid'; el.src = u;
    if (el.tagName === 'VIDEO') { el.autoplay = el.loop = el.muted = el.playsInline = true; }
    old.parentNode.replaceChild(el, old);
  });
  fetch('/tpl_list?_=' + Date.now()).then(function (r) { return r.json(); }).then(function (j) {
    TPL = j; curTpl = TPL[0] && TPL[0].id;
    var groups = {};
    for (var i = 0; i < TPL.length; i++) {
      var g = TPL[i].id.split('_')[0];
      groups[g] = (groups[g] || 0) + 1;
    }
    var ch = '<button class="on" data-g="">전체 ' + TPL.length + '</button>';
    for (var g2 in groups) ch += '<button data-g="' + g2 + '">' + g2 + ' ' + groups[g2] + '</button>';
    ch += '<button data-g="__mine">내 것</button>';
    $('chips').innerHTML = ch;
    $('chips').addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      var bs = $('chips').querySelectorAll('button');
      for (var m = 0; m < bs.length; m++) bs[m].classList.toggle('on', bs[m] === b);
      drawCards();
    });
    $('cntlbl').textContent = TPL.length + '개';
    drawCards(); drawLines(); draw();
  });
  var ins = document.querySelectorAll('.panel input');
  for (var i = 0; i < ins.length; i++) {
    if (ins[i].id === 'ct' || ins[i].type === 'file') continue;
    ins[i].addEventListener('input', draw);
  }
  $('ct').addEventListener('input', function () { delete CAPLINES[cut]; drawLines(); draw(); });
})();
