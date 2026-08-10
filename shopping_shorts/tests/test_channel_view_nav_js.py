"""index.html 채널 보기 나가기(2026-07-28) — node 슬라이스 그라운딩.

채널명 클릭은 검색어에 아이디를 넣는 것(searchChannel)이라, 예전엔 카테고리를
눌러도 검색어가 남아 "그 채널 안에서 카테고리만 바뀌는" 상태가 됐고 뒤로가기로도
못 나갔다. 사장님 제보(2026-07-28): 카테고리·뒤로가기 둘 다로 전체 목록에 가야 한다.

여기서 보는 것:
  ① 카테고리 클릭 → 검색어·입력칸·히스토리 항목까지 정리
  ② 뒤로가기(popstate) → 같은 정리, 단 history.back()은 다시 안 부른다(한 칸 더 나감)
  ③ 검색창을 직접 고치는 중엔 히스토리를 안 건드린다(치던 글자가 날아가면 안 된다)
  ④ 채널 보기가 아닐 땐 아무것도 안 지운다(일반 검색 중 카테고리 클릭 보호)
"""
import json
import pathlib
import shutil
import subprocess

import pytest

INDEX_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
NODE = shutil.which("node")
_START = "// ── 채널 보기 나가기(2026-07-28) ─── CHANNELVIEW-START"
_END = "// ─── CHANNELVIEW-END"


def _slice():
    src = INDEX_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


# 슬라이스가 기대하는 바깥 것들(STATE·DOM·history·render)을 최소로 세운다.
_DRIVER = r"""
(function(){
  global.window = global;
  const calls = {render:0, back:0};
  const boxes = {rankSearch:{value:""}, channelHistoryWrap:{innerHTML:"x"}};
  global.document = { getElementById: id => boxes[id] || null };
  global.render = () => { calls.render++; };
  global.history = { back: () => { calls.back++; } };
  global.STATE = {q:""};

  const enter = (u) => { CHANNEL_VIEW = u; STATE.q = u; boxes.rankSearch.value = u; };
  const snap = () => ({q:STATE.q, box:boxes.rankSearch.value, ch:CHANNEL_VIEW,
                       wrap:boxes.channelHistoryWrap.innerHTML});

  const out = {};

  // ① 카테고리 클릭 경로: silent(바깥이 곧 render를 부른다) + 히스토리 되감기
  enter("home.in.on"); calls.render=0; calls.back=0;
  out.category = {ret: exitChannelView({silent:true}), state: snap(),
                  render: calls.render, back: calls.back};

  // ② 뒤로가기 경로: 브라우저가 이미 되감았으므로 history.back()을 또 부르면 안 된다
  enter("home.in.on"); calls.render=0; calls.back=0;
  out.popstate = {ret: exitChannelView({fromPopstate:true}), state: snap(),
                  render: calls.render, back: calls.back};

  // ③ 채널 보기가 아닐 때: 아무것도 안 건드린다
  CHANNEL_VIEW = null; STATE.q = "홈인"; boxes.rankSearch.value = "홈인";
  calls.render=0; calls.back=0;
  out.notChannel = {ret: exitChannelView({silent:true}), state: snap(),
                    render: calls.render, back: calls.back};

  // ④ isChannelMode 반영
  CHANNEL_VIEW = null; out.modeOff = isChannelMode();
  CHANNEL_VIEW = "x";  out.modeOn  = isChannelMode();

  console.log(JSON.stringify(out));
})();
"""


def _run(tmp_path):
    js = tmp_path / "t.js"
    js.write_text(_slice() + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_exit_channel_view(tmp_path):
    r = _run(tmp_path)

    # ① 카테고리: 검색어·입력칸·지난한달 영역이 비고, 히스토리는 한 칸 되감는다
    assert r["category"]["ret"] is True
    assert r["category"]["state"] == {"q": "", "box": "", "ch": None, "wrap": ""}
    assert r["category"]["back"] == 1
    assert r["category"]["render"] == 0        # silent — 바깥이 render를 부른다

    # ② 뒤로가기: 같은 정리 + history.back()은 다시 안 부른다(한 칸 더 나가면 페이지를 떠난다)
    assert r["popstate"]["ret"] is True
    assert r["popstate"]["state"] == {"q": "", "box": "", "ch": None, "wrap": ""}
    assert r["popstate"]["back"] == 0
    assert r["popstate"]["render"] == 1        # 스스로 다시 그린다

    # ③ 채널 보기가 아니면 손대지 않는다 — 일반 검색 중 카테고리를 눌렀을 뿐인데
    #    검색어가 날아가면 그것도 사고다
    assert r["notChannel"]["ret"] is False
    assert r["notChannel"]["state"]["q"] == "홈인"
    assert r["notChannel"]["state"]["box"] == "홈인"
    assert r["notChannel"]["back"] == 0 and r["notChannel"]["render"] == 0

    assert r["modeOff"] is False and r["modeOn"] is True


def test_wiring_present():
    """슬라이스 밖 배선 — 진입(pushState)·카테고리·popstate가 실제로 이어져 있나."""
    src = INDEX_HTML.read_text(encoding="utf-8")
    # 진입 시 히스토리 항목을 쌓는다. ★URL은 안 바꾼다 — 주소에 채널을 박으면
    # 새로고침해도 채널 화면이 되살아나는데, 원한 건 "새로고침하면 전체 화면"이다.
    assert 'history.pushState({ssChannel: username}, "", location.href)' in src
    assert "if(CHANNEL_VIEW !== username){" in src            # 같은 채널 재클릭 시 중복 적재 방지
    # 카테고리 두 곳 모두에 걸려 있어야 한다
    assert "function setCtype(k){ exitChannelView({silent:true});" in src
    assert "function setCat(c){ exitChannelView({silent:true});" in src
    # 뒤로가기 배선
    assert "exitChannelView({fromPopstate:true});" in src
    # 검색창 직접 편집 시 플래그만 내린다(히스토리 손대면 치던 글자가 날아간다)
    assert "if(CHANNEL_VIEW && q !== CHANNEL_VIEW) CHANNEL_VIEW = null;" in src
    # 채널을 URL(해시/쿼리)에 박지 않았는지 — 박으면 새로고침이 채널 화면을 되살린다
    assert "#ch=" not in src and "?channel=" not in src
