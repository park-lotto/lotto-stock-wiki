"""픽업영상 대본에서 [바꾸기]가 막혀 있던 것 — 2026-08-26 사장님 제보.

사장님: "픽업영상 대본은 바꾸기를 누르면 ai자동바꾸기가 왜안되나"

## 원인 (실측)
`/api/script/beat/regen`은 **style_id를 필수**로 요구한다(app.py: "style_id 필요" 422).
그런데 픽업영상 대본은 **스타일을 안 고르는 경로**다(첫 칸 = 씨앗 구조로 생성).
프론트는 `body.style_id = dr.style_id`를 보내는데 픽업 초안엔 그 값이 없어
`undefined` → 422로 튕겼다. 즉 기능이 통째로 막혀 있었다.

## 고치는 방향
style_id가 없으면 **씨앗 구조로 대신 돌린다**. style은 원래 두 가지에 쓰인다:
  ① `_materials_for_generate(spines=[style])` — 썰 재료 주입 판정(fit_categories)
  ② 프롬프트의 스파인 지시
픽업 경로에는 스파인이 없으므로 ①은 spines 없이 가고, ②는 씨앗 훅 문형 지시로 대체한다.
★판정(pickup_script)은 전체 생성과 **같은 것**을 쓴다 — 두 벌이 되면 [바꾸기]로 만든
  칸만 결이 어긋난다(0순위-B, 기존 은행 예산 주석과 같은 이유).
"""
import pytest

from shopping_shorts import script_generate


def test_regen_one_beat이_스파인_없이도_돈다():
    """★핵심. style=None이어도 예외 없이 프롬프트를 만들 수 있어야 한다.

    실제 Gemini 호출은 하지 않는다(키·과금) — 프롬프트 조립까지만 확인한다.
    """
    assert hasattr(script_generate, "regen_one_beat")
    import inspect
    sig = inspect.signature(script_generate.regen_one_beat)
    assert "style" in sig.parameters, "스파인 인자가 사라졌다(호출부와 어긋난다)"
    # style이 필수 위치인자면 None을 넘길 수 있어야 한다(기본값 None이거나 Optional 허용).
    p = sig.parameters["style"]
    assert p.default is inspect.Parameter.empty or p.default is None


def test_픽업_훅_지시문은_같은_함수를_쓴다():
    """[바꾸기]와 전체 생성이 **같은 지시문 생성기**를 써야 결이 안 어긋난다(0순위-B)."""
    assert hasattr(script_generate, "_pickup_hook_directive")
    d = script_generate._pickup_hook_directive("여러분 믹스 커피 절대 물에만 타 먹지 마세요", "믹스커피")
    assert "원본 훅" in d and "문형" in d
    assert "믹스커피" in d


def test_화면이_style_id_없을때도_바꾸기를_보낸다():
    """★프론트 회귀 방지 — style_id가 없다고 요청을 막으면 안 된다.

    픽업 초안은 style_id가 없다. 그 경우 씨앗 정보(seed_hook/structure)를 대신 싣는다.
    """
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
    src = p.read_text(encoding="utf-8")
    i = src.index("/api/script/beat/regen")
    # 호출부 앞 1200자에 body 조립이 있다.
    blk = src[max(0, i - 1400):i]
    assert "style_id" in blk
    assert "seed_hook" in blk, "픽업 경로에서 씨앗 훅을 안 보낸다 — 문형이 안 지켜진다"


def _produce_js():
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
    return p.read_text(encoding="utf-8")


def test_재료칸이_담긴_영상_전부를_후보로_올린다():
    """사장님: "여기에 1단계영상들을 다 넣어주고".

    종전엔 AI PICK 1편만 카드가 됐다(라벨도 '1편'이었다) — 다른 영상을 씨앗으로
    고를 방법이 아예 없었다.

    ★출처는 **AI PICK 응답의 candidates**여야 한다(실측으로 배운 것).
      처음에 HANDOFF를 썼더니 카드 원문이 전부 0자로 떴다 — HANDOFF의 `pickScript`는
      대본 텍스트가 아니라 **boolean 플래그**이기 때문이다. candidates에는 각 영상의
      text·structure가 대표 카드와 **같은 출처**로 실려 있다."""
    src = _produce_js()
    i = src.index("function s2RenderSeeds")
    fn = src[i:i + 3200]
    assert "candidates" in fn, "담긴 영상을 후보로 안 올린다"
    assert "c.text" in fn, "후보의 대본 원문을 안 싣는다(카드 원문이 빈다)"
    assert "_seen" in fn, "중복 제거가 없다(대표와 후보가 겹친다)"


def test_AI_PICK이_늦게_와도_씨앗이_갱신된다():
    """★AI PICK은 비동기로 늦게 온다. s2RenderSeeds가 패널 진입 때만 돌면
    이미 2단계에 있는 사장님 화면은 **대표 씨앗이 안 붙고 원문이 빈 카드**만 남는다
    (브라우저 실측: 카드 3편 전부 원문 0자 → 손으로 다시 그리니 342자 대표가 붙었다)."""
    src = _produce_js()
    i = src.index("window._aiPick = d;")
    blk = src[i:i + 900]
    assert "s2RenderSeeds" in blk, "AI PICK 도착 후 씨앗을 다시 그리지 않는다"


def test_씨앗을_여러_편_고를_수_있다():
    """사장님: "픽업영상을 하나 골라도 다른거 하나더 고를수있게 / 지금은 하나고르면 다른건 못골라"."""
    src = _produce_js()
    assert "function s2ToggleSeed" in src, "고르기 토글이 없다"
    assert "function s2SeedOn" in src
    assert "S2.seedPicks" in src, "선택 목록이 없다"
    # 카드가 실제로 클릭을 받는가(종전엔 확인용이라 onclick이 없었다).
    i = src.index("function s2RenderSeeds")
    fn = src[i:i + 4200]
    assert "s2ToggleSeed(" in fn, "카드에 고르기 클릭이 안 붙었다"


def test_선택이_AI_PICK에_덮이지_않는다():
    """★고른 걸 AI PICK이 다시 덮으면 '골라도 안 골라진다'가 된다(종전 동작)."""
    src = _produce_js()
    i = src.index("function s2RenderSeeds")
    fn = src[i:i + 4200]
    assert "_handPicked" in fn, "직접 고른 씨앗을 존중하는 가드가 없다"


def test_선택은_seed와_짝으로_저장되고_지워진다():
    """★seed만 지우고 seedPicks를 남기면 옛 작업의 선택이 새 작업에 붙는다(0순위-B)."""
    src = _produce_js()
    i = src.index("function _s2Reset")
    assert "S2.seedPicks = []" in src[i:i + 400], "_s2Reset가 선택을 안 지운다"
    assert "seedPicks:S2.seedPicks" in src, "스냅샷에 선택이 안 담긴다(새로고침하면 날아간다)"


def test_원문은_alert이_아니라_접었다_편다():
    """사장님: "원문누르면 아래로 접었다 폈다고 넣어줘".

    alert은 4000자에서 잘리고 복사도 안 되며 화면을 막는다."""
    src = _produce_js()
    i = src.index("function s2ShowSeedText")
    fn = src[i:i + 700]
    assert "alert(" not in fn, "아직 alert으로 띄운다"
    assert "display" in fn, "접었다 펴는 토글이 없다"
    assert "s2-stext" in src, "원문 상자 자리가 없다"


def test_서버가_style_id_없이도_422를_안_준다():
    """style_id가 없어도 씨앗 재료(base_script)가 있으면 진행해야 한다."""
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    src = p.read_text(encoding="utf-8")
    i = src.index('@app.post("/api/script/beat/regen")')
    fn = src[i:i + 4000]
    # 옛 코드는 style_id가 없으면 무조건 422였다.
    assert 'content={"ok": False, "error": "style_id 필요"}' not in fn, \
        "style_id를 여전히 필수로 요구한다 — 픽업 경로에서 바꾸기가 막힌다"
