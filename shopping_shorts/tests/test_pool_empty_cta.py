"""빈 영상풀 = 재료를 가지러 갈 두 버튼(2026-08-24 사장님).

사장님 요청: "이게 여기 누르면 레퍼런스랭킹으로 갈지 영상즐겨찾기로 갈지 버튼 두개 만들어줘"

종전역 빈 상태엔 "즐겨찾기에서 영상을 보내거나…"라는 **글만** 있어서,
어디로 가야 하는지 알아도 사이드바까지 손이 한 번 더 갔다.

재료가 들어오는 길은 실제로 둘뿐이고 양쪽 다 sendToProduce()가 붙어 있다:
  레퍼런스 랭킹 `/`(static/index.html) · 영상 즐겨찾기 `/collection`(static/collection.html)

브라우저 실측(playwright — 이 테스트가 대신 지키는 것):
  - 1600px: 두 버튼 44px 높이, 가로 나란히
  - 390px:  세로로 쌓이고 46px, body.scrollWidth == 390 (가로 넘침 없음)
  - 클릭 → 각각 `/`, `/collection`으로 이동
  - HANDOFF에 재료를 넣고 renderPool() → display:none, 비우면 다시 block

★버튼은 반드시 **poolEmpty 안**에 있어야 한다. 밖으로 새면 재료를 담은 뒤에도
버튼이 남아 화면을 어지럽힌다(renderPool은 poolEmpty 하나만 숨긴다) —
그래서 문자열 검색이 아니라 **파서로 부분트리를 잘라** 검사한다.
"""
import pathlib
from html.parser import HTMLParser

_PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


# 공태그(닫는 태그가 없다) — 깊이 계산에서 뺀다.
# ★이걸 빼면 <input>·<img>에서 depth가 오르기만 하고 안 내려가 부분트리가
#   영영 안 닫힌다 — 실측으로 버튼 2개 대신 **57개**가 잡혔다.
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
         "link", "meta", "param", "source", "track", "wbr"}


class _Subtree(HTMLParser):
    """id=target 요소의 **부분트리**만 모으는 파서.

    ★끝났으면 done으로 확실히 멈춰야 한다. 음수 센티넬로만 표시하면
      handle_starttag이 그걸 몰라 계속 모은다 — 실측으로 버튼 2개 대신 57개.
    """

    def __init__(self, target):
        super().__init__(convert_charrefs=True)
        self.target = target
        self.depth = 0          # 0 = 아직 안 들어감
        self.done = False
        self.buttons, self.attrs, self.text = [], {}, []

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        d = dict(attrs)
        if not self.depth:
            if d.get("id") == self.target:
                self.attrs, self.depth = d, 1
            return
        if tag == "button":
            self.buttons.append(d)
        if tag not in _VOID:
            self.depth += 1

    # <div/> 같은 자기닫기는 열고 바로 닫힌다
    def handle_startendtag(self, tag, attrs):
        if self.done or not self.depth:
            return
        if tag == "button":
            self.buttons.append(dict(attrs))

    def handle_endtag(self, tag):
        if self.done or not self.depth or tag in _VOID:
            return
        self.depth -= 1
        if self.depth == 0:
            self.done = True

    def handle_data(self, data):
        if self.depth and not self.done:
            self.text.append(data)


def _empty():
    p = _Subtree("poolEmpty")
    p.feed(_PRODUCE.read_text(encoding="utf-8"))
    assert p.attrs, "poolEmpty 요소를 못 찾았다"
    return p


def test_ranking_button_is_inside_the_empty_state():
    """레퍼런스 랭킹(/)으로 가는 버튼 — poolEmpty **안**에."""
    e = _empty()
    hits = [b for b in e.buttons if b.get("onclick") == "location.href='/'"]
    assert len(hits) == 1, e.buttons


def test_collection_button_is_inside_the_empty_state():
    """영상 즐겨찾기(/collection)으로 가는 버튼 — poolEmpty **안**에."""
    e = _empty()
    hits = [b for b in e.buttons if b.get("onclick") == "location.href='/collection'"]
    assert len(hits) == 1, e.buttons


def test_exactly_two_buttons():
    """세 개째가 늘면 빈 자리가 지저분해진다 — 의도한 때만 이 수를 고쳐라."""
    assert len(_empty().buttons) == 2, _empty().buttons


def test_buttons_use_shared_styles():
    """<button class=btn-next/btn-prev> — 모바일 44px 터치타겟 규칙(line 627/762)을 탄다."""
    cls = sorted((b.get("class") or "") for b in _empty().buttons)
    assert cls == ["btn-next", "btn-prev"], cls


def test_empty_state_is_hidden_by_default():
    """renderPool()이 켜기 전까지는 숨어 있어야 한다 — 재료가 있으면 안 보인다."""
    assert "display:none" in (_empty().attrs.get("style") or "")


def test_hint_text_still_explains_what_to_do():
    """버튼만 달고 설명을 지우면 '눌렀는데 왜 안 쌓이나'가 된다."""
    txt = "".join(_empty().text)
    assert "제작소로 보내기" in txt, txt
