"""renderSourceAnalysis가 **빈 shortcode를 서버와 같은 규칙으로 채우는지**.

2026-09-02 라이브 실측 사고:
  「🔗 URL 직접 추가」로 담으면 confirmMixUrls가 shortcode:'' 로 넣는다.
  서버(app.py api_produce_autoload)는 빈 값을 sha1(url.strip())[:12]로 채워 저장하는데,
  화면은 '' 그대로 조회해 **서로 다른 키**를 봤다 → 서버엔 brief가 다 있는데
  화면은 "0/3개 읽음 · 분석 중"에 영구 고정 → 2단계 씨앗 카드가 안 생겨 고객이 막혔다.
  (0순위-B: 같은 판단을 두 곳에서 따로 지으면 반드시 어긋난다)

이 테스트는 그 사고를 **되살려** 잡는다:
  - 보정 대상이 footage URL로 좁혀지면(옛 코드) 인스타 URL은 ''로 남아 FAIL
  - trim을 빼면 서버(sha1(url.strip()))와 키가 갈리므로 FAIL
"""
import hashlib, json, pathlib, shutil, subprocess, pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "async function renderSourceAnalysis(){"
_END = "  const items = HANDOFF.filter(h => h.useFootage);"

# 실제로 막혔던 그 모양 — 외부 URL(인스타)과 내 파일 올리기(footage) 둘 다.
# 앞뒤 공백을 일부러 넣어 서버의 .strip()과 어긋나는지도 같이 본다.
_URLS = [
    "https://www.instagram.com/reel/Dcrc2mMT0RK/",
    "  https://www.instagram.com/reel/Dcp3P-WyMFe/  ",
    "https://shoppingshorts.duckdns.org/api/produce/footage/abc.mp4",
]

_HARNESS = r"""
'use strict';
const { webcrypto } = require('crypto');
global.crypto = webcrypto;
global.HANDOFF = URLS.map(u => ({shortcode:'', url:u, useFootage:true}));
global._SRC_BUSY = 0; global._SRC_QUEUED = 0;
global._SRC_BRIEF = {}; global._SRC_INFLIGHT = new Set();
global.saveWork = ()=>{};
global.document = { getElementById: ()=>({ innerHTML:'', style:{} }) };
global.setTimeout = ()=>0; global.clearTimeout = ()=>{};
"""

_DRIVER = r"""
(async function(){
  try{ await renderSourceAnalysis(); }catch(e){}
  console.log(JSON.stringify(global.HANDOFF.map(h=>h.shortcode)));
})();
"""


def _expected(url: str) -> str:
    """서버가 짓는 코드 — app.py: sha1(url.strip())[:12]."""
    return hashlib.sha1(url.strip().encode()).hexdigest()[:12]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_empty_shortcode_filled_like_server(tmp_path):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    sl = src[src.index(_START):src.index(_END)]
    js = tmp_path / "t.js"
    js.write_text("const URLS = " + json.dumps(_URLS) + ";\n"
                  + _HARNESS + sl + "}\n" + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])

    # ① 빈 채로 남은 것이 하나도 없어야 한다(옛 코드는 인스타 2건이 '' 로 남았다)
    assert all(got), f"빈 shortcode가 남았다 → 그 영상은 화면에서 영영 '분석 중': {got}"
    # ② 서버가 짓는 코드와 **정확히** 같아야 조회 키가 맞는다(공백 포함 URL 주의)
    assert got == [_expected(u) for u in _URLS], f"서버 규칙과 다른 코드: {got}"
