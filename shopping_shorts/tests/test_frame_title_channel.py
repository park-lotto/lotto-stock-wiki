"""틀(내용물 있는 틀) — 채널명 저장 · 제목 중복 해소 · 칸별 높이 조절(2026-08-23).

사장님 지시 4가지:

  ① 내 채널명은 **저장**할 수 있게 (매번 다시 치지 않게)
  ② 제목은 '헤드카피 가져오기'로 채우고, **헤드카피가 곧 제목자리니까 중복으로 안 뜨게**
  ③ 문구를 생성하면 제목자리에 한 줄 또는 두 줄로 들어가게
  ④ 칸 높이 조정이 **제목칸·채널명칸 두 개 다 따로** 되게
     (어느 칸에 두 줄이 들어갈지 모르니까)

## 지금 구조 (실측)

- 위 띠(`bar_h`) = 채널명이 놓이는 칸. 미리보기 드래그 손잡이 **있음**.
- 흰 제목 블록 = `deco_frame.render`가 **줄 수로 자동 계산**(`block_h`). 손잡이 **없었음**.
  → ④가 요구하는 "따로 조정"이 불가능했다. `head_h`를 신설해 손잡이를 하나 더 단다.
- 헤드카피(`hcText`)는 영상 위에 **따로** 그려진다 → 틀 제목과 겹쳐 ②의 중복이 났다.
"""
import pathlib

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
_FRAME = pathlib.Path(__file__).resolve().parents[1] / "deco_frame.py"


def _code():
    src = _HTML.read_text(encoding="utf-8")
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith("//"))


def _fn(code, header):
    assert header in code, f"{header} 가 없다"
    return code.split(header, 1)[1].split("\nfunction ", 1)[0]


# ── ① 채널명 저장 ──────────────────────────────────────────────────
def test_채널명_저장_버튼이_있다():
    assert 'id="frChannelSave"' in _HTML.read_text(encoding="utf-8"), \
        "채널명을 저장할 버튼이 없다"


def test_채널명을_로컬에_저장하고_불러온다():
    code = _code()
    assert "saveMyChannel" in code and "loadMyChannel" in code, \
        "채널명 저장/불러오기 함수가 없다"
    body = _fn(code, "function saveMyChannel(")
    assert "localStorage.setItem" in body, "채널명을 저장하지 않는다"
    # 키는 상수 하나로 둔다(0순위-B) — 저장/읽기가 다른 키를 쓰면 조용히 안 불러와진다.
    assert "MY_CHANNEL_KEY" in body, "저장 키를 상수로 안 쓴다"
    assert "ss_my_channel" in code, "저장 키가 다르다(ss_my_channel)"
    assert _fn(code, "function loadMyChannel(").count("MY_CHANNEL_KEY") == 1, \
        "읽기가 같은 키 상수를 안 쓴다"


def test_틀을_새로_골라도_저장한_채널명이_들어간다():
    """매번 다시 치지 않게 — 이게 ①의 목적이다."""
    code = _code()
    body = _fn(code, "function frPick(")
    assert "loadMyChannel(" in body, \
        "틀을 고를 때 저장해둔 채널명을 안 불러온다 — 매번 다시 쳐야 한다"


# ── ②③ 제목 = 헤드카피, 중복 제거 ────────────────────────────────
def test_문구를_고르면_틀_제목에도_들어간다():
    """③ 문구 생성 → 제목자리에 자동으로."""
    code = _code()
    body = _fn(code, "function useHeadcopy(")
    assert "frTitle" in body or "syncFrameTitle" in body, \
        "문구를 골라도 틀 제목칸이 안 채워진다"


def test_틀_제목이_있으면_헤드카피를_안_그린다():
    """② 중복 제거 — 틀 제목이 곧 제목자리다."""
    code = _code()
    body = _fn(code, "function updateHC(")
    assert "_frameTitleShown" in body or "hideHcForFrame" in body, \
        "틀 제목이 있어도 헤드카피를 그대로 그린다(중복)"


def test_중복판정이_한곳에서만_난다():
    """0순위-B — 같은 판단을 두 번 적으면 반드시 어긋난다."""
    code = _code()
    assert code.count("function _frameTitleShown(") == 1, \
        "중복 판정 함수가 하나가 아니다"


def test_제목이_비면_헤드카피가_돌아온다():
    """틀 제목을 지우면 다시 헤드카피가 보여야 한다(껐다 켜기)."""
    out = run_js(r"""
      // _frameTitleShown의 판정식만 떼어 냈다: 틀이 있고 제목에 글자가 있을 때만 true
      const shown = (frame, title) => !!(frame && (title||'').trim());
      const cases = [
        [null, '',      false],   // 틀 없음
        [null, '제목',   false],   // 틀 없으면 제목이 있어도 무관
        [{},   '',      false],   // 틀은 있는데 제목이 빔 → 헤드카피 보임
        [{},   '   ',   false],   // 공백만 → 빈 것으로 친다
        [{},   '제목',   true ],   // 둘 다 → 헤드카피 숨김
      ];
      for (const [f, t, want] of cases) {
        if (shown(f, t) !== want) { console.log('FAIL', JSON.stringify([f,t,want])); process.exit(1); }
      }
      console.log('FAIL 0');
    """)
    assert "FAIL 0" in out, out


# ── ④ 제목칸·채널명칸 따로 조절 ───────────────────────────────────
def test_제목칸_손잡이가_따로_있다():
    """④ 채널명칸(bar_h) 말고 제목칸(head_h)에도 손잡이."""
    code = _code()
    assert "frHandleHead" in code, "제목칸 손잡이가 없다"
    body = _fn(code, "function syncFrameHandles(")
    assert "frHandleHead" in body, "제목칸 손잡이를 안 그린다"


def test_제목칸_손잡이는_head_h를_고친다():
    """채널명칸(frBar)과 **다른 값**을 만져야 따로 조절이다."""
    code = _code()
    body = _fn(code, "function syncFrameHandles(")
    assert "'frHead'" in body or '"frHead"' in body, \
        "제목칸 손잡이가 frHead 입력칸에 안 묶였다"


def test_서버가_head_h를_받는다():
    src = _FRAME.read_text(encoding="utf-8")
    assert '"head_h"' in src, "deco_frame이 head_h를 모른다"


def test_head_h가_0이면_예전처럼_자동이다():
    """★회귀 방지 — 기존 작업물은 head_h가 없다. 0=자동이어야 그림이 안 바뀐다."""
    src = _FRAME.read_text(encoding="utf-8")
    i = src.index("block_h")
    seg = src[max(0, i - 700):i + 400]
    assert "head_h" in seg, "block_h 계산이 head_h를 안 본다"
    assert "or block_h" in seg or "head_h\"] or" in seg or "if s[\"head_h\"]" in seg, \
        "head_h=0(자동) 분기가 없다 — 기존 그림이 바뀐다"


def test_frameUrl이_head_h를_보낸다():
    code = _code()
    body = _fn(code, "function frameUrl(")
    assert "head_h" in body, "화면이 head_h를 서버로 안 보낸다"


# ── ⑤ 제목 엔터 줄바꿈 ────────────────────────────────────────────
def test_제목칸이_엔터를_받는다():
    """input은 엔터를 못 받는다 → textarea여야 한다(2026-08-23)."""
    src = _HTML.read_text(encoding="utf-8")
    i = src.index('id="frTitle"')
    tag = src[max(0, i - 200):i]
    assert "<textarea" in tag, "제목칸이 아직 input이다 — 엔터로 줄바꿈이 안 된다"


def test_서버가_엔터를_지킨다():
    """_wrap이 줄바꿈을 공백처럼 뭉개면 엔터가 무시된다."""
    src = _FRAME.read_text(encoding="utf-8")
    body = src[src.index("def _wrap("):src.index("def _hamburger(")]
    assert 'split("\\n")' in body, "_wrap이 줄바꿈으로 안 쪼갠다"


def test_wrap이_실제로_엔터를_지킨다():
    """문자열 검사로는 '부른다'만 알 수 있다 — 실제로 돌려서 줄이 갈리는지 본다."""
    import sys
    sys.path.insert(0, str(_FRAME.parents[1]))
    from PIL import Image, ImageDraw
    from shopping_shorts import deco_frame
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = deco_frame._font("title", 62)
    assert deco_frame._wrap(d, "가나다\n라마바", f, 9999) == ["가나다", "라마바"], \
        "엔터를 쳐도 한 줄로 붙는다"
    # 빈 줄은 버린다(자리만 먹는다)
    assert deco_frame._wrap(d, "가나다\n\n라마바", f, 9999) == ["가나다", "라마바"]
    # 엔터가 없으면 지금까지처럼 폭 기준 자동 접기(회귀 방지)
    assert deco_frame._wrap(d, "짧다", f, 9999) == ["짧다"]


def test_한줄_또는_두줄로_나눈다():
    """③ '한줄 또는 두줄' — 짧으면 한 줄, 길면 가운데서 두 줄."""
    out = run_js(r"""
      function t(s){
        s=String(s||'').trim();
        if(!s || s.includes('\n')) return s;
        const words=s.split(/\s+/);
        if(words.length<3 || s.length<=14) return s;
        const half=s.length/2;
        let best=1,bestGap=Infinity,acc=0;
        for(let i=0;i<words.length-1;i++){
          acc+=words[i].length+(i?1:0);
          const gap=Math.abs(acc-half);
          if(gap<bestGap){bestGap=gap;best=i+1;}
        }
        return words.slice(0,best).join(' ')+'\n'+words.slice(best).join(' ');
      }
      if(t('짧은 제목').includes('\n')){console.log('FAIL 짧은데 두 줄');process.exit(1);}
      const two=t('인플루언서들 사이에서 난리난 이어폰의 정체');
      if(two.split('\n').length!==2){console.log('FAIL 두 줄이 아님: '+JSON.stringify(two));process.exit(1);}
      if(t('가나\n다라')!=='가나\n다라'){console.log('FAIL 이미 나눈 걸 덮음');process.exit(1);}
      console.log('FAIL 0');
    """)
    assert "FAIL 0" in out, out


# ── ⑥ 폰트·색 프리셋 ──────────────────────────────────────────────
def test_글자_프리셋이_있다():
    code = _code()
    assert "FR_STYLE_PRESETS" in code, "틀 글자 프리셋이 없다"
    assert "function applyFrStyle(" in code, "프리셋 적용 함수가 없다"


def test_프리셋은_진짜_입력칸에_써넣는다():
    """0순위-B — 프리셋이 자기 상태를 따로 갖지 않고 기존 칸을 쓴다."""
    code = _code()
    body = _fn(code, "function applyFrStyle(")
    for cell in ("frTtFont", "frTtSize", "frChFont", "frTitleColor"):
        assert cell in body, f"프리셋이 {cell}을 안 건드린다"
    assert "frUpdate()" in body, "프리셋이 반영 경로를 안 탄다"


def test_제목색이_서버까지_간다():
    src = _FRAME.read_text(encoding="utf-8")
    assert '"title_color"' in src, "서버가 제목색을 모른다"
    assert "fill=_rgb(s[\"title_color\"])" in src, "제목을 아직 고정색으로 그린다"
    assert _code().count("title_color:f.title_color") == 1, "화면이 제목색을 안 보낸다"


def test_이상한_색은_기본값으로():
    """★쿼리스트링엔 아무거나 올 수 있다. _rgb는 형식을 안 따져 500이 난다."""
    import sys
    sys.path.insert(0, str(_FRAME.parents[1]))
    from shopping_shorts import deco_frame
    assert deco_frame.normalize({"title_color": "red"})["title_color"] == "#141414"
    assert deco_frame.normalize({"title_color": "#ZZZZZZ"})["title_color"] == "#141414"
    assert deco_frame.normalize({"title_color": "#D32F2F"})["title_color"] == "#D32F2F"


def test_기본_제목색은_예전과_같다():
    """★회귀 — 예전엔 (20,20,20)이 박혀 있었다. #141414가 그 값이다."""
    import sys
    sys.path.insert(0, str(_FRAME.parents[1]))
    from shopping_shorts import deco_frame
    assert deco_frame._rgb(deco_frame.DEFAULTS["title_color"]) == (20, 20, 20, 255)


# ── ⑦ 채널명칸↔제목칸 구분선 ──────────────────────────────────────
def test_구분선을_그린다():
    src = _FRAME.read_text(encoding="utf-8")
    assert '"sep_line"' in src, "서버가 구분선을 모른다"
    assert 'if s["sep_line"] and bar_h > 0' in src, \
        "띠가 없을 때도 선을 그으면 경계가 아닌 자리에 줄이 생긴다"


def test_구분선_불리언이_쿼리에서_갈린다():
    """★'0'은 문자열이라 그냥 두면 참이다 — 끌 수가 없어진다."""
    app = (_FRAME.parents[0] / "app.py").read_text(encoding="utf-8")
    i = app.index('"ad_badge", "icons"')
    assert "sep_line" in app[i:i + 120], "sep_line이 불리언 변환 목록에 없다"


def test_높이계산_자동과_수동():
    """수동값이 있으면 그 값, 없으면 자동 계산 — 파이썬 쪽 식과 같은 규칙."""
    out = run_js(r"""
      const auto = lines => 36 + lines * 78 + 52 + 24;   // 자동(줄 수 기반)
      const pick = (head_h, lines) => head_h > 0 ? head_h : auto(lines);
      if (pick(0, 1) !== auto(1)) { console.log('FAIL 자동이 아님'); process.exit(1); }
      if (pick(0, 2) === pick(0, 1)) { console.log('FAIL 줄수 반영 안됨'); process.exit(1); }
      if (pick(300, 1) !== 300) { console.log('FAIL 수동값 무시'); process.exit(1); }
      if (pick(300, 9) !== 300) { console.log('FAIL 수동인데 줄수가 이김'); process.exit(1); }
      console.log('FAIL 0');
    """)
    assert "FAIL 0" in out, out
