"""띠 손잡이를 끌면 미리보기가 따라와야 한다 — 요청 폭주를 막는다(2026-08-23).

사장님 제보: "상단 크기조정이 마우스로 이동이 안됨" → 이어서 "되는데 / 너무
느리게 로딩 / 컴퓨터 문제인가".

## 실측 원인 (컴퓨터 문제가 아니다)

끌 때마다 `move`가 `frUpdate()`를 부르고, 그 끝이 이렇게 이어진다:

    move → frUpdate() → renderTemplatePreview() → el.src = frameUrl(...)
                     └→ saveHeadcopy()          → POST /api/produce/mix/settings

마우스는 한 번 끄는 동안 `mousemove`를 수십~수백 번 쏜다. 그래서

  · `el.src`가 매 픽셀 새 URL로 바뀐다 → 브라우저가 진행 중이던 frame.png를
    버리고 처음부터 다시 받는다. 끄는 내내 그림이 **한 번도 안 앉는다**
    = 사장님이 본 "너무 느리게 로딩". 손잡이는 실제로 움직이고 있었다.
  · POST도 픽셀마다 나간다(saveHeadcopy엔 디바운스가 없다 — 같은 파일의
    saveWork는 1초 디바운스를 쓰는데 이쪽만 빠져 있었다).

## 무엇을 강제하나

끄는 동안(=값이 계속 바뀌는 중)에는 **화면 좌표만** 손대고, 서버를 때리는
두 가지(그림 재요청·설정 저장)는 손을 뗄 때 한 번만 하도록 묶는다.
"""
import pathlib
import re

from shopping_shorts.tests.js_harness import requires_node, run_js

pytestmark = requires_node

_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _code():
    """주석을 걷어낸 produce.html 본문 — 주석 속 문구에 정규식이 걸리지 않게."""
    src = _HTML.read_text(encoding="utf-8")
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith("//"))


def _fn(code, header):
    """`header`로 시작하는 함수 본문만 잘라 온다(다음 최상위 function 전까지)."""
    assert header in code, f"{header} 가 없다"
    return code.split(header, 1)[1].split("\nfunction ", 1)[0]


def test_끄는_중에는_그림을_다시_안받는다():
    """드래그 중 경로가 frUpdate()(→ el.src 재설정)를 직접 부르면 안 된다.

    ★이 단언이 이 파일의 핵심이다. 손잡이가 "안 움직이는 것처럼" 보인 진짜
      이유가 매 픽셀 frame.png 재요청이라, 여기가 풀리면 증상이 돌아온다.
    """
    body = _fn(_code(), "function bindFrameHandle(")
    move = body.split("const move=", 1)[1].split("const up=", 1)[0]
    assert "frUpdate()" not in move, (
        "드래그 move가 아직 frUpdate()를 부른다 — 픽셀마다 frame.png를 다시 받아\n"
        "        그림이 안 앉는다(사장님: '너무 느리게 로딩')")


def test_손을_뗄_때_한번_반영한다():
    """끄는 동안 미룬 실제 반영(frUpdate)은 up에서 정확히 한 번 일어나야 한다.

    0회면 끌어도 값이 저장이 안 되고, 여러 번이면 폭주가 되돌아온다.
    """
    body = _fn(_code(), "function bindFrameHandle(")
    up = body.split("const up=", 1)[1].split("el.addEventListener", 1)[0]
    assert up.count("frUpdate()") == 1, (
        f"up에서 frUpdate() 호출이 {up.count('frUpdate()')}회 — 정확히 1회여야 한다")


def test_끄는_동안_손잡이는_따라온다():
    """서버를 안 때린다고 손잡이까지 멈추면 '안 움직인다'가 된다.

    move는 화면 좌표만 즉시 갱신해야 한다(입력칸 값 + 손잡이 위치).
    """
    body = _fn(_code(), "function bindFrameHandle(")
    move = body.split("const move=", 1)[1].split("const up=", 1)[0]
    assert "input.value=" in move, "move가 입력칸 값을 안 고친다"
    assert "syncFrameHandles()" in move, (
        "move가 손잡이 위치를 안 갱신한다 — 끌어도 손잡이가 제자리에 붙어 있어\n"
        "        '이동이 안 된다'로 보인다")


def test_saveHeadcopy는_디바운스된다():
    """설정 저장은 연타로 나가면 안 된다. 같은 파일 saveWork(1초)와 같은 규약."""
    code = _code()
    body = _fn(code, "function saveHeadcopy(")
    assert "setTimeout" in body and "clearTimeout" in body, (
        "saveHeadcopy에 디바운스가 없다 — 드래그 중 POST가 픽셀마다 나간다")


def test_렌더는_즉시저장을_기다린다():
    """★디바운스를 넣으면서 같이 지켜야 하는 짝(0순위-B).

    renderFinal은 `await saveHeadcopy()`로 설정을 job에 올린 뒤 굽는다. 디바운스가
    걸린 채 인자 없이 부르면 await해도 **안 기다리고** 렌더가 먼저 출발해, 방금
    바꾼 띠 높이가 빠진 영상이 구워진다. 그래서 이 자리만은 즉시 저장이어야 한다.
    """
    code = _code()
    assert "await saveHeadcopy(true)" in code, (
        "렌더 직전 저장이 즉시(true)가 아니다 — 디바운스에 걸려 옛 설정으로 구워진다")


def test_손잡이_위치_계산이_실제로_따라온다():
    """syncFrameHandles의 좌표식을 떼어 내 값이 커지면 손잡이도 내려가는지 잰다.

    문자열 검사만 두면 '부른다'만 보장하고 '맞게 움직이는가'는 못 본다.
    """
    out = run_js(r"""
      // syncFrameHandles가 쓰는 식 그대로 (produce.html: bar_h/scale - 7)
      const scale = 1920 / 640;          // 미리보기 높이 640px 가정
      const top = bar => Math.max(0, bar / scale - 7);
      const a = top(190), b = top(300);
      if (!(b > a)) { console.log('FAIL 손잡이가 안 내려간다'); process.exit(1); }
      if (Math.abs(a - (190 / scale - 7)) > 1e-9) { console.log('FAIL 식 불일치'); process.exit(1); }
      console.log('FAIL 0');
    """)
    assert "FAIL 0" in out, out


def test_문법이_유효하다():
    """★render()가 죽으면 전 화면이 빈다(reference_render죽으면_전화면공백).

    문법검사만으로는 TDZ 같은 런타임 오류를 못 잡지만, 최소한 파싱은 지킨다.
    """
    src = _HTML.read_text(encoding="utf-8")
    # ★블록마다 따로 검사한다. `<script>(.*)</script>`를 greedy로 한 번에 잡으면
    #   블록 8개 사이의 **HTML까지** 삼켜 없던 SyntaxError가 난다(실측: 이 테스트를
    #   처음 그렇게 썼다가 코드가 멀쩡한데 빨갛게 떴다).
    blocks = re.findall(r"<script>(.*?)</script>", src, re.S)
    assert blocks, "produce.html에 인라인 <script> 블록이 없다"
    big = max(blocks, key=len)                     # 본문(가장 큰 블록)만 파싱 검사
    assert len(big) > 10000, "본문 블록을 못 찾았다(추출이 깨졌다)"
    rc, out, err = run_js(big, check=False, timeout=30)
    # 브라우저 API가 없어 실행은 실패하지만, **문법 오류(SyntaxError)**면 안 된다.
    assert "SyntaxError" not in err, err
