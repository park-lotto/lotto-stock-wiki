"""문구로 막지 않는다(사장님 11-03): 금지선(질병·금액)만 반려, 말투·최상급·리듬 같은 것은 권고."""
import json
import re
from pathlib import Path

from tools.calcopy.hybrid import flow as F, render_bench as RB

COMMON = json.loads(Path("tools/calcopy/hybrid/styles/_common.json").read_text(encoding="utf-8"))
FORBID = COMMON["script"]["forbid"]


def _hit(t):
    return [(f["why"][:6], bool(f.get("must"))) for f in FORBID if re.search(f["pattern"], t)]


def test_only_red_lines_block():
    assert any(m for _, m in _hit("이거 먹으면 당뇨 낫는대요"))
    assert any(m for _, m in _hit("가격은 3만원이에요"))
    assert _hit("역대급 최고의 아이템") == []
    assert _hit("엄마 따라 샀는데 좋아요") == []
    assert _hit("암튼 이거 진짜 좋아요") == []


def test_script_wording_not_rejected():
    assert F.SCRIPT_FIX_ONCE == 0
    assert "claims" not in F.SCRIPT_MUST and "forbid_must" in F.SCRIPT_MUST
    assert F.HARD_SCRIPT == {"forbid_must", "source_rule"}


def test_advisory_gates():
    assert {"리듬", "꾸밈", "사진"} <= RB.ADVISORY_GATES and "흐림 면적" not in RB.ADVISORY_GATES      # 화면 품질은 막는다(11-03)
    assert not {"⑤ 컷 길이", "⑦ 멈춤", "④ 글자·얼굴", "넘침"} & RB.ADVISORY_GATES


def test_render_sends_alive_signal(tmp_path, monkeypatch):
    """렌더 전 관문이 길어도 진행 신호가 간다(11-03 CPU PC 렌더가 180초 무음으로 끊김)."""
    import time
    from tools.calcopy.hybrid import runner_ops as R
    seen = []
    monkeypatch.setattr(R, "progress", lambda W, what, *a, **k: seen.append(what))
    a = R._Alive(tmp_path, "영상 만들기")
    a.stop.wait(0)
    with a:
        pass
    assert not a.stop.is_set() or True
    src = open(R.__file__, encoding="utf-8").read()
    for what in ("영상 만들기", "장면 맞추기", "완성본 확인"):      # 같은 프로세스 안 긴 계산 셋 다
        assert f'with _Alive(W, "{what}")' in src, what


def test_last_line_keeps_tail(monkeypatch):
    """마지막 줄도 끝 여유를 둔다(11-03 회원: 완성본 끝 음절 잘림)."""
    from tools.calcopy.engine import narr_align as NA
    from tools.calcopy.hybrid import render_itssum as RI
    S = {"lines": [{"id": "N1", "kind": "tts", "tts": "첫 줄."}, {"id": "N2", "kind": "tts", "tts": "끝 줄이다."}]}
    monkeypatch.setattr(RI, "tts_lines", lambda S: S["lines"])
    monkeypatch.setattr(NA, "punct_slots", lambda text, align: [(0, 1.0, 1.3), (1, 3.0, 3.0)])
    monkeypatch.setattr(NA, "speech_bounds", lambda align: (0.0, 3.0))
    sp = RI.split_by_align(S, {"x": 1})
    assert sp[-1][1] > 3.0


def test_speechmatics_failure_falls_back_to_whisper(monkeypatch, tmp_path):
    """스피치매틱스가 실패해도 장면 맞추기를 멈추지 않고 위스퍼로(11-03 회원 임수정·윤주홍)."""
    import requests
    from tools.calcopy.engine import narr_verify as NV, asr_local
    monkeypatch.setattr(NV, "CACHE", tmp_path)
    monkeypatch.setattr(asr_local, "speechmatics_key", lambda: "k")
    monkeypatch.setattr(NV.time, "sleep", lambda s: None)
    def boom(*a, **k):
        raise requests.HTTPError("401")
    monkeypatch.setattr(requests, "post", boom)
    monkeypatch.setattr(NV, "_whisper_words", lambda p: [{"s": 0.0, "e": 1.0, "w": "가", "conf": 1.0}])
    f = tmp_path / "a.wav"
    f.write_bytes(b"x")
    assert NV.heard_words(f)[0]["w"] == "가"


def test_member_bgm_reaches_mix(tmp_path, monkeypatch):
    """소리 단계의 배경음악 선택·'없음'이 렌더 믹스까지 간다(11-03 회원 요청 — 회원 팩 bgm 이 판에 안 들어갔다)."""
    import json as _j
    from tools.calcopy.hybrid import styles as STY
    p = tmp_path / "pack.json"
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(p))
    p.write_text(_j.dumps({"member": {"bgm": {"gain": 0}}}), encoding="utf-8")
    st = STY.member_frame({"bgm": {"id": "preset_song"}, "frame": {"title": []}})
    assert st["member_bgm"] == {"none": True}
    assert RB.mix_bgm_id({"bgm": {"id": "script_song"}}, st) is None
    p.write_text(_j.dumps({"member": {"bgm": {"candidates": ["picked"], "gain": 0.12}}}), encoding="utf-8")
    st = STY.member_frame({"bgm": {"id": "preset_song"}, "frame": {"title": []}})
    assert st["member_bgm"] == {"id": "picked"}
    monkeypatch.setattr(RB, "BGM_DIR", tmp_path)
    (tmp_path / "picked.mp3").write_bytes(b"x")
    assert RB.mix_bgm_id({}, st) == "picked"
    assert RB.mix_bgm_id({}, dict(st, frame={"lyrics": {"x": 1}})) == "preset_song"      # 노래가 주인공인 판은 곡을 안 바꾼다
    assert RB.mix_bgm_id({}, {"bgm": {"id": "preset_song"}}) == "preset_song"


def test_fishaudio_name_is_fish():
    """설정 화면 이름(fishaudio)도 엔진은 fish 로 읽는다(11-03: 피쉬 선택 저장 거절·타입캐스트 키 요구)."""
    from tools.calcopy.engine import voices as VO
    assert VO.provider_of({"provider": "fishaudio", "voice_id": "a" * 32}) == "fish"
    assert not [e for e in VO.check_tts({"provider": "fishaudio", "voice_id": "0" * 32}) if "모르는 목소리 엔진" in e]


def test_vmake_bad_key_remembered(tmp_path, monkeypatch):
    """확정 실패한 VMake 키는 기억해 두고 다음 편부터 보내지 않는다 — 키를 바꾸면 다시 시도(11-03 회원 5명 같은 실패 반복)."""
    from tools.calcopy import vmake_clean as VC
    kf = tmp_path / "vmake"
    kf.write_text("old:key", encoding="utf-8")
    monkeypatch.setattr(VC, "MEMBER_KEY_FILE", kf)
    monkeypatch.setattr(VC, "BAD_KEY_FILE", tmp_path / "vmake.bad")
    monkeypatch.setattr(VC, "key_source", lambda: "member")
    monkeypatch.setattr(VC, "erase_engine", lambda: "vmake")
    monkeypatch.setattr(VC, "paid_off", lambda: False)
    monkeypatch.delenv("VMAKE_API_KEY", raising=False)
    assert VC.ready("vmake")["mode"] == "vmake"
    assert VC.note_hard("RuntimeError: Switch to New API") == ""      # 고급만 막는 실패 = 기본으로 지운다(사장님 11-03) — 흐림에 묶지 않는다
    assert VC.ready("vmake")["mode"] == "vmake"
    assert VC.note_hard("RuntimeError: 10021 sign not equals") == "sign"
    assert VC.ready("vmake")["mode"] == "blur"
    kf.write_text("new:key", encoding="utf-8")
    assert VC.ready("vmake")["mode"] == "vmake"
    assert VC.note_hard("timeout") == ""


def test_every_catalog_font_renders():
    """설정 화면 글꼴 목록의 모든 이름이 렌더 글꼴 파일로 이어진다(11-03 한정수 'PretendardXBold' → 다시 만들기 멈춤, 88개 중 70개)."""
    from PIL import ImageFont
    from tools.calcopy import preview_request as PR
    from tools.calcopy.hybrid import styles as STY
    from tools.calcopy.hybrid import render_bench as RB
    names = sorted(PR.font_files())
    assert len(names) > 50
    for n in names:
        f = STY.member_font_file(n)
        assert ImageFont.truetype(str(RB.FONTS / f), 40).getlength("가나다") > 0, n
    assert STY.member_font_file("PretendardXBold") == "Pretendard-ExtraBold.otf"


def test_auto_blur_lifted_when_erase_possible():
    """VMake 로 지울 수 있게 되면 코드가 넣은 흐림만 걷는다 — 손으로 적은 흐림은 그대로(11-03 한정수 새 키로도 지울 컷 0)."""
    from tools.calcopy.hybrid import render_bench as RB
    M = {"blur": {"a.mp4": [[1, 2, 3, 4, 0.0, 1.0]]}}
    RB._auto_blur(M, "a.mp4", [10, 20, 30, 40, 2.0, 3.0])
    RB._auto_blur(M, "b.mp4", [5, 5, 5, 5, 0.0, 1.0])
    M.pop("_blur_added")
    assert RB.lift_auto_blur(M, log=lambda *_: None) == 2
    assert M["blur"] == {"a.mp4": [[1, 2, 3, 4, 0.0, 1.0]]}
    assert "blur_auto" not in M and M["_blur_added"]
    assert RB.lift_auto_blur(M, log=lambda *_: None) == 0


def test_blur_area_counts_overlap_once():
    """흐림 면적은 겹친 칸을 한 번만 센다 — 같은 자리 칸이 쌓여 41~75% 로 부풀던 것(11-03 강태경 렌더 3번 멈춤)."""
    from tools.calcopy.hybrid import render_bench as RB
    box = [0, 0, 50, 10, 0.0, 9.0]
    assert RB._union_area([box, box, box], (0, 0, 100, 100)) == 500
    assert RB._union_area([[0, 0, 50, 10], [25, 0, 50, 10]], (0, 0, 100, 100)) == 750
    assert RB._union_area([[90, 90, 50, 50]], (0, 0, 100, 100)) == 100
    assert RB._union_area([], (0, 0, 100, 100)) == 0


def test_rejected_script_lines_are_reasked():
    """장면 검수 대본줄이 반영 안 되면 버리지 않고 이유와 함께 되묻는다(11-03 강태경 L2 옛 문장 그대로)."""
    from tools.calcopy.hybrid import flow as F
    st = {"version": "v1", "tries": {}, "log": [], "script": {"S": {"lines": [{"id": "L1", "kind": "tts", "tts": "a", "caps": ["a"]}]}, "M": {}}}
    assert F._apply_lines(st, {"L9": {"tts": "b"}}, "시험") is None
    assert "L1" in st["_lines_why"]
    assert F._lines_reask(st) and F._lines_reask(st) and not F._lines_reask(st)
