"""완성본이 까닭 없이 다시 렌더되지 않는다 + 완성본에 탐색바가 있다 (2026-09-03 사장님 제보).

제보 ②: "완성본 만들기하고 다시 미리보기 왔다가 다시 완성본으로 가면 다시 렌더가 된다"
  → applyServer가 "저장이 돌았나"로 판정해 편성이 그대로여도 완성본을 버렸다.
    autoApply는 1.2초 디바운스로 수시로 도니 탭만 오가도 20초짜리 유료 렌더가 다시 돈다.
제보 ③: "중간 구간으로 이동해서 클릭할 수 있는 바가 없다"
  → <video controls>의 네이티브 막대는 재생 중 숨는다. 늘 보이는 막대를 밖에 둔다.
"""
import pathlib

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"


def _code(name):
    """주석을 걷어낸 소스 — 주석에 든 단어를 코드로 오인하지 않게(기존 테스트와 같은 방식)."""
    src = (_STATIC / name).read_text(encoding="utf-8")
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith("//"))


def _fn(code, name):
    """함수 하나의 본문만 잘라낸다(다음 최상위 function 전까지)."""
    assert f"function {name}(" in code, f"{name}이 없다"
    return code.split(f"function {name}(")[1].split("\nfunction ")[0]


# ── ② 재렌더 ────────────────────────────────────────────────────────────────
def test_저장만으로는_완성본을_버리지_않는다():
    body = _fn(_code("scene_lab.html"), "applyServer")
    assert "RENDERED_SIG" in body, "편성 지문을 대조하지 않는다 — 저장만 하면 또 버린다"
    assert "clearConfirm()" in body, "진짜 바뀌었을 때 버리는 길이 사라졌다"
    # 지문 대조 없이 innerHTML만 보고 버리던 옛 판정이 남아 있으면 안 된다
    assert "_stale" in body, "달라졌는지 판정(_stale)이 없다"


def test_편성이_바뀌면_여전히_버린다():
    """반대 방향 회귀 — 2026-08-25 '소재를 바꿨는데 옛 영상 그대로'를 되살리면 안 된다."""
    body = _fn(_code("scene_lab.html"), "applyServer")
    assert "_sig !== RENDERED_SIG" in body, "달라졌을 때 버리는 조건이 없다"


def test_지문은_한_곳에서_만든다():
    """저장과 판정이 각자 payload를 조립하면 언젠가 어긋난다(0순위-B)."""
    code = _code("scene_lab.html")
    assert "function _editPayload(" in code, "payload를 만드는 곳이 하나로 안 모였다"
    assert code.count("beat_idx: b.beat_idx") == 1, "payload 조립이 두 벌이다"
    assert "_editPayload()" in _fn(code, "applyServer"), "applyServer가 공용 payload를 안 쓴다"


def test_지문은_렌더_출발_시점에_찍는다():
    """완료 시점에 찍으면 렌더 도는 20초 사이의 편집까지 '들어간 것'으로 오기록된다."""
    code = _code("scene_lab.html")
    assert "PENDING_SIG" in _fn(code, "_askRender"), "_askRender가 출발 지문을 안 찍는다"
    assert "RENDERED_SIG = PENDING_SIG" in _fn(code, "showConfirmVideo"), \
        "showConfirmVideo가 찍어둔 지문을 확정하지 않는다"


def test_완성본을_비우면_지문도_비운다():
    body = _fn(_code("scene_lab.html"), "clearConfirm")
    assert "RENDERED_SIG = ''" in body, "영상은 지웠는데 지문이 남으면 다음 판정이 틀어진다"


# ── ③ 탐색바 ────────────────────────────────────────────────────────────────
def test_완성본에_탐색바가_있다():
    code = _code("scene_lab.html")
    body = _fn(code, "showConfirmVideo")
    assert 'id="cfSeek"' in body, "탐색바가 없다"
    assert "_cfWire()" in body, "탐색바를 배선하지 않는다"
    assert "#confirmBody .cfSeek" in (_STATIC / "scene_lab.html").read_text(encoding="utf-8"), \
        "탐색바 CSS가 없다"


def test_탐색바가_그_지점으로_건너뛴다():
    body = _fn(_code("scene_lab.html"), "_cfWire")
    assert "v.currentTime =" in body, "클릭해도 그 지점으로 안 간다"
    assert "getBoundingClientRect" in body, "누른 위치를 시간으로 환산하지 않는다"
    assert "isFinite(d)" in body, "길이를 모를 때(NaN) 가드가 없다"


def test_소리를_켤_수_있다():
    """자동재생 정책으로 muted 시작이라, 켜는 길이 없으면 영영 무음으로 본다."""
    body = _fn(_code("scene_lab.html"), "_cfWire")
    assert "v.muted = !v.muted" in body, "음소거 해제 버튼이 동작하지 않는다"


# ── ① 전체재생 멈춤 ─────────────────────────────────────────────────────────
def test_소재를_못_열어도_멈추지_않는다():
    """`else v.onloadedmetadata = go;` 한 줄만 있으면 이벤트가 안 올 때 그 컷에서 통째로 멈춘다."""
    body = _fn(_code("scene_play.js"), "step")
    assert "v.onerror" in body, "소재 로드 실패를 안 본다 — 그 컷에서 멈춘다"
    assert "giveUp" in body, "여는 단계 안전핀이 없다"
    assert "cutWaitMs(c)" in body, "안전핀이 컷 길이 기준을 안 쓴다"


def test_못_열어도_컷_시간은_그대로_쓴다():
    """컷을 건너뛰면 화면이 음성보다 빨라져 싱크가 통째로 어긋난다."""
    body = _fn(_code("scene_play.js"), "step")
    give = body.split("const giveUp =")[1].split("};")[0]
    assert "schedStep(c.dur * 1000)" in give, "못 열었다고 컷 시간을 건너뛰면 싱크가 깨진다"
    assert "holdShot(c, true)" in give, "검은 화면 대신 썸네일을 깔지 않는다"


def test_여는_콜백은_한_번만_돈다():
    """metadata와 안전핀이 겹쳐 go()가 두 번 돌면 컷이 앞질러 간다."""
    body = _fn(_code("scene_play.js"), "step")
    assert "if (opened) return;" in body, "중복 실행 가드가 없다"
