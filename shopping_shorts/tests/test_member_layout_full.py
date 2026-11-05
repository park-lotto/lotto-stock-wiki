"""11-05 박은숙(썰템쇼판·프리셋 p_3b6f601651): 9:16 전체 화면 요구 — 회원 Claude 가 엔진 styles.py 를 손으로 고쳐(_member_fullscreen) 갱신 때마다 지워졌다.
회원 설정 칸 text.layout('full')·text.caption_stack({y,pitch,break}) 로 옮김. 주인 = styles._member_layout(member_frame 이 부름), 저장 관문 = preview_request.check.
렌더 길(render_bench.frame_png 틀 그림 · frame_segments · stack_rows 자막 자리)로 잰다."""
import json

from PIL import Image

from tools.calcopy import preview_request as PR
from tools.calcopy.hybrid import render_bench as RB, styles as STY

V = "썰템쇼판"
S = {"lines": [{"id": "L1", "kind": "tts", "tts": "a", "caps": [{"text": "a"}]}], "title_lines": [["첫째 줄 제목"], ["둘째 줄 제목"]]}
T = {"lines": {"L1": [0.0, 1.0]}, "end": 10.0}
FULL = {"layout": "full", "caption_stack": {"y": 1340, "pitch": 120, "break": "line"}}


def _load(tmp_path, monkeypatch, text):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"member": {"brand": {"channel_name": "테스트채널"}, "text": text}}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(p))
    return STY.load(V)


def _clear_px(st, out):
    """틀 그림에서 투명한(영상이 보이는) 픽셀 수."""
    RB.frame_png(S, st, out)
    return sum(1 for a in Image.open(out).getchannel("A").getdata() if a == 0)


def test_전체화면_칸이_판_틀을_바꾼다(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTEM_MEMBER_PACK", raising=False)
    base = STY.load(V)
    assert base["frame"]["kind"] == "post" and base["frame"].get("segments")
    st = _load(tmp_path, monkeypatch, FULL)
    F = st["frame"]
    assert F["kind"] == "full"
    for k in ("window", "window_radius", "post", "band", "credit", "segments"):
        assert k not in F
    assert len(F["title"]) == 2 and F["title"][0]["center"] == 250
    assert st["caption"]["stack"]["y"] == 1340 and st["caption"]["stack"]["pitch"] == 120 and st["caption"]["stack"]["break"] == "line"
    assert st["caption"]["stack"]["lines"] == base["caption"]["stack"]["lines"]      # 안 정한 칸은 판 값
    assert STY.frame_window(F) == [0, 0, 1080, 1920]
    assert RB.frame_segments(S, T, st) == []                                          # 구간 틀이 없으니 훅 카드 없음(길이·자막 hide 없음)
    # 렌더 길: 틀 그림의 영상 자리(투명)가 판 창(1080×878)보다 훨씬 넓다 — 화면 전체에서 제목·채널명 글자만 남는다
    before, after = _clear_px(base, tmp_path / "a.png"), _clear_px(st, tmp_path / "b.png")
    assert before < 1080 * 900 and after > 1080 * 1920 * 0.85, (before, after)
    # 자막 자리: stack_rows 가 회원 y·pitch 로 세운다(1340 → 69.792%, 둘째 줄 덧붙음 = 1340+60)
    rows = RB.stack_rows([{"text": "가", "line": "L1"}, {"text": "나", "line": "L1"}], st)
    assert rows[0]["place"]["y"] == round(1340 / 1920 * 100, 3) and rows[1]["place"]["y"] == round(1400 / 1920 * 100, 3)


def test_회원_제목_칸이_전체화면_제목을_덮는다(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, {**FULL, "title_colors": ["#FF0000", "#00FF00"], "title_font": "BlackHanSans", "title_scale": 1.1})
    t0, t1 = st["frame"]["title"]
    assert t0["color"] == "#FF0000" and t1["color"] == "#00FF00"
    assert t0["font"] == STY.member_font_file("BlackHanSans") and t0["px"] == round(104 * 1.1)


def test_자막쌓기만_바꾸기(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, {"caption_stack": {"y": 900, "pitch": 90}})
    assert st["frame"]["kind"] == "post"                        # 틀은 그대로
    assert st["caption"]["stack"]["y"] == 900 and st["caption"]["stack"]["break"] == "line"


def test_layout_빈값은_그대로(tmp_path, monkeypatch):
    assert _load(tmp_path, monkeypatch, {"layout": ""})["frame"]["kind"] == "post"


def test_저장_관문():
    cat = PR.catalog()
    assert PR.check({"text": FULL}, cat) == []
    assert PR.check({"text": {"layout": None}}, cat) == []
    assert PR.check({"text": {"layout": "window"}}, cat)
    assert PR.check({"text": {"caption_stack": {"y": 100, "pitch": 120}}}, cat)
    assert PR.check({"text": {"caption_stack": {"y": 1340, "pitch": 500}}}, cat)
    assert PR.check({"text": {"caption_stack": {"y": 1340, "pitch": 120, "break": "page"}}}, cat)
    assert PR.check({"text": {"caption_stack": {"y": 1340}}}, cat)
    assert PR.check({"text": {"caption_stack": {"y": 1340, "pitch": 120, "lines": 3}}}, cat)
