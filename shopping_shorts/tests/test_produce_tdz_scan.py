"""produce.html 전 함수 TDZ 스캔 — 화면 통째 공백 재발 차단(2026-08-19).

## 왜

2026-08-18에 index.html의 `render()`가 `let` 선언 전 변수를 읽어(TDZ) 던지는 바람에
**레퍼런스 랭킹이 전 플랫폼에서 빈 화면**이 됐다(730003b39). 그 사고 뒤
`test_ranking_render_tdz.py`가 생겼지만 **index.html의 render() 하나만** 본다.

정작 손이 제일 많이 가는 파일은 **produce.html**이다 — 30일간 250커밋으로
app.py 다음으로 뜨겁고, 최상위 함수만 349개다. 여기서 같은 사고가 나면
제작소 화면이 통째로 빈다.

★`node --check`는 이걸 못 잡는다. 문법은 완전히 유효하고 **런타임** 오류다
  (memory `reference_render죽으면_전화면공백`).
★파일을 통째로 실행하는 건 현실적이지 않다(560KB·DOM 의존). 그래서 정적으로
  **함수 본문 안에서 `let`/`const` 선언보다 위에서 그 이름을 읽는 자리**를 찾는다.

## 오탐을 어떻게 피하나

- 주석(`//`, `*`) 줄은 건너뛴다.
- 중첩 함수·콜백 안에서 쓰는 건 실행 시점이 달라 TDZ가 아닐 수 있다 →
  **선언과 같은 깊이의 직선 코드만** 본다(중괄호 깊이 추적).
- 문자열 안의 이름은 세지 않는다(따옴표 구간 제거 후 검사).
- 애매하면 **통과**시킨다 — 가드가 시끄러우면 아무도 안 본다.
"""
import pathlib
import re

import pytest

STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"

#: 검사 대상 — 제작소 화면과 랭킹 화면(사고가 난 곳 + 가장 뜨거운 곳)
TARGETS = ["produce.html", "index.html"]

_FN = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
_DECL = re.compile(r"\b(?:let|const)\s+([A-Za-z_$][\w$]*)")
_STR = re.compile(r"""(['"`])(?:\\.|(?!\1).)*\1""", re.S)


def _strip_noise(line):
    """문자열 리터럴과 줄주석을 지운다 — 그 안의 이름은 실행되지 않는다."""
    s = _STR.sub('""', line)
    i = s.find("//")
    return s[:i] if i >= 0 else s


def _functions(html):
    """(이름, 본문) 목록 — 중괄호 균형으로 각 함수의 끝을 찾는다."""
    out = []
    for m in _FN.finditer(html):
        try:
            start = html.index("{", m.end() - 1)
        except ValueError:
            continue
        depth = 0
        for j in range(start, min(len(html), start + 60000)):
            c = html[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    out.append((m.group(1), html[start:j + 1]))
                    break
    return out


def _reads(var, line):
    """이 줄이 `var`를 **값으로 읽는가**. 오탐의 대부분을 여기서 거른다.

    아래는 읽기가 아니다(실측으로 걸러낸 것들):
      · 객체 키 `{size: 1}` / 라벨 `size:`   ← thumbFit()이 이걸로 오탐났다
      · 속성 접근 `L.size` / 옵셔널 `L?.size`
      · 화살표 함수 본문 `() => later`(실행 시점이 다르다)
    """
    if "=>" in line:                       # 콜백 본문 — 나중에 실행된다
        return False
    for m in re.finditer(r"\b%s\b" % re.escape(var), line):
        before = line[:m.start()].rstrip()
        after = line[m.end():].lstrip()
        if before.endswith(".") or before.endswith("?."):
            continue                       # 속성 접근
        if after.startswith(":"):
            continue                       # 객체 키 / 라벨
        return True
    return False


def _tdz_hits(name, body):
    """이 함수 본문에서 '선언보다 먼저 같은 깊이에서 읽는' 자리를 찾는다."""
    lines = body.split("\n")
    clean = [_strip_noise(l) for l in lines]
    # 줄마다 중괄호 깊이(그 줄 시작 시점)를 계산
    depth_at, d = [], 0
    for c in clean:
        depth_at.append(d)
        d += c.count("{") - c.count("}")
    # ★콜백 파라미터로 같은 이름이 쓰이는 구간은 통째로 건너뛴다.
    #   실측 오탐: `.map((L, i) => ` 안의 L은 **다른 스코프**인데, 화살표가 첫 줄에만
    #   있어서 줄 단위 `=>` 검사로는 걸러지지 않았다(renderThumbLayers).
    #   백틱 템플릿이 여러 줄로 이어지는 것도 같은 문제라 함께 막는다.
    shadowed = set()
    for c in clean:
        for m in re.finditer(r"\(\s*([A-Za-z_$][\w$]*)\s*(?:,\s*[A-Za-z_$][\w$]*\s*)*\)\s*=>", c):
            shadowed.update(re.findall(r"[A-Za-z_$][\w$]*", m.group(0).split("=>")[0]))
        for m in re.finditer(r"\b([A-Za-z_$][\w$]*)\s*=>", c):
            shadowed.add(m.group(1))

    decl = {}                       # 이름 -> (선언 줄, 그 줄의 깊이)
    for n, c in enumerate(clean):
        for m in _DECL.finditer(c):
            decl.setdefault(m.group(1), (n, depth_at[n]))
    hits = []
    for var, (dline, ddepth) in decl.items():
        if var in shadowed:            # 콜백 파라미터와 이름이 겹친다 — 판정 불가, 통과
            continue
        for n in range(dline):
            if depth_at[n] != ddepth:      # 다른 블록/콜백 = 실행 시점이 다르다
                continue
            if _reads(var, clean[n]):
                hits.append(f"{name}(): {var} — {n + 1}행에서 읽고 {dline + 1}행에서 선언")
                break
    return hits


@pytest.mark.parametrize("fname", TARGETS)
def test_선언보다_먼저_읽는_변수가_없다(fname):
    """TDZ가 있으면 그 함수가 첫 줄부터 죽어 화면이 통째로 빈다."""
    path = STATIC / fname
    if not path.exists():
        pytest.skip(f"{fname} 없음")
    html = path.read_text(encoding="utf-8")
    bad = []
    for name, body in _functions(html):
        bad.extend(_tdz_hits(name, body))
    assert not bad, (
        f"{fname}: 선언 전에 읽는 변수가 있습니다 — TDZ로 그 함수가 통째로 죽습니다"
        f"(화면 공백).\n★node --check로는 안 잡힙니다(문법은 유효, 런타임 오류).\n  "
        + "\n  ".join(bad[:20]))


def test_스캐너가_진짜_TDZ를_잡는다():
    """★가드가 실제로 작동하는지 고정 — 안 그러면 '통과'가 무의미하다."""
    bad_js = """function boom(){
  if (_cap > 0) { return 1; }
  let _cap = 0;
  return _cap;
}"""
    hits = _tdz_hits("boom", bad_js[bad_js.index("{"):])
    assert hits and "_cap" in hits[0], f"진짜 TDZ를 못 잡는다: {hits}"


def test_정상코드는_오탐하지_않는다():
    """선언 후 사용·다른 블록 사용은 TDZ가 아니다 — 시끄러우면 아무도 안 본다."""
    ok_js = """function fine(){
  let _n = 0;
  if (_n > 0) { return 1; }
  const cb = () => _later;      // 콜백: 실행 시점이 다르다
  let _later = 2;
  return _n + _later;
}"""
    assert _tdz_hits("fine", ok_js[ok_js.index("{"):]) == []


def test_문자열_속_이름은_세지_않는다():
    ok_js = """function s(){
  console.log("_x 는 문자열일 뿐");
  let _x = 1;
  return _x;
}"""
    assert _tdz_hits("s", ok_js[ok_js.index("{"):]) == []
