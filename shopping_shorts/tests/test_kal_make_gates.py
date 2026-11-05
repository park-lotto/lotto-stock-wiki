"""kal make 경로(preset_make·preset_gates·asr_local·encoder·fontmatch) — 개정안 kal v2 채택(관제 319, 11-06).
make-공통-05 공급자 몰래 바꾸기 금지 · common-20 키 돌림 · make-대본-04 훅 같은 어미 · make-화면자막-11 경계 욕 · make-목소리-08 끊김 기호
make-소재-06 늘어짐 · make-렌더-02 짝수 높이 · make-렌더-01 자리 · make-화면자막-06 글리프 관문 · copy-01 공백 폭
make-목소리-13·소리-09·소재-09 = make-00 으로 make_one 이 부르는지
"""
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.calcopy.engine import asr_local, encoder, preset_gates as PG, preset_make as PM


def test_common05_no_silent_whisper(monkeypatch):
    monkeypatch.setattr(asr_local, "pcm", lambda p: [0.0] * 16000)
    monkeypatch.setattr(asr_local, "speechmatics_key", lambda: "")
    monkeypatch.setattr(asr_local, "_whisper", lambda a: pytest.fail("위스퍼로 넘어가면 안 된다"))
    with pytest.raises(RuntimeError, match="키 없음"):
        asr_local.transcribe("x.wav", engine="speechmatics", strict=True)
    monkeypatch.setattr(asr_local, "speechmatics_key", lambda: "k")
    n = []
    monkeypatch.setattr(asr_local, "_speechmatics", lambda p: n.append(1) or (_ for _ in ()).throw(OSError("net")))
    with pytest.raises(RuntimeError, match="2번 실패"):
        asr_local.transcribe("x.wav", engine="speechmatics", strict=True)
    assert len(n) == 2


def test_common05_default_keeps_old_fallback(monkeypatch):
    """감시 A: 회원 라인(runner_ops.asr_cross:1319 — try 없음)·narr_pause·편 make.py 는 기본(strict=False) = 옛 동작(위스퍼 + note)."""
    monkeypatch.setattr(asr_local, "pcm", lambda p: __import__("numpy").zeros(16000, dtype="float32"))
    monkeypatch.setattr(asr_local, "speechmatics_key", lambda: "k")
    monkeypatch.setattr(asr_local, "_speechmatics", lambda p: (_ for _ in ()).throw(OSError("net")))
    monkeypatch.setattr(asr_local, "_whisper", lambda a: {"engine": "whisper:small", "segments": []})
    r = asr_local.transcribe("x.wav", engine="speechmatics")
    assert r["engine"].startswith("whisper") and "speechmatics 실패" in r["note"]


def test_common20_key_rotation(monkeypatch, tmp_path):
    monkeypatch.setenv("SPEECHMATICS_API_KEY", "k1")
    monkeypatch.setenv("SPEECHMATICS_KEY_2", "k2")
    monkeypatch.setattr(asr_local.os.path, "expanduser", lambda p: str(tmp_path / "none"))
    asr_local._SM_DEAD.clear()
    assert asr_local.speechmatics_keys() == ["k1", "k2"]
    seen = []

    def post(url, headers=None, **k):
        seen.append(headers["Authorization"])
        return SimpleNamespace(status_code=402 if "k1" in headers["Authorization"] else 201)
    f = tmp_path / "a.wav"
    f.write_bytes(b"x")
    r, key = asr_local._sm_post(str(f), {}, post)
    assert key == "k2" and seen == ["Bearer k1", "Bearer k2"] and asr_local.speechmatics_key() == "k2"
    asr_local._SM_DEAD.clear()


def test_daebon04_hook_same_ending():
    assert PG.hook_ending_gate([{"text": "이거 몰랐는데"}, {"text": "알고 보니 대박이던데"}])
    assert not PG.hook_ending_gate([{"text": "이거 몰랐는데"}, {"text": "알고 보니 대박이다"}])


def test_jamak11_join_swear():
    assert PG.join_gate([{"text": "오늘 시"}, {"text": "발표가 있다"}])
    assert not PG.join_gate([{"text": "오늘 발표"}, {"text": "가 있다"}])


def test_moksori08_tts_symbols():
    w = {"lines": [{"tts": "첫 줄 / 둘째", "text": "a"}], "pieces": [{"text": "a", "line": 0}], "cuts": []}
    src = inspect.getsource(PM.plan_rules)
    assert "/¦‖|" in src


def test_sojae06_render02_part_vf_flags(capsys):
    c = {"box": [0, 0, 1080, 1920], "speed": 1.0}
    assert "scale=1080:1920" in PM.part_vf(c, 1080, 1919, {"even_height": True})    # 판 칸 켜면 홀수 → 짝수
    assert "scale=1080:1919" in PM.part_vf(c, 1080, 1919)                           # 기본 = 옛 동작
    sq = {"box": [0, 0, 1080, 1080], "speed": 1.0}
    with pytest.raises(ValueError, match="늘어짐"):
        PM.part_vf(sq, 1080, 1920, {"no_stretch": True})
    PM.part_vf(sq, 1080, 1920)                                                       # 기본 = 경보만(옛 동작)
    assert "늘어짐" in capsys.readouterr().out


def test_text_gate_flags_default_off():
    w = {"lines": [{"text": "이거 몰랐는데", "tts": "a"}, {"text": "대박이던데", "tts": "b"}], "pieces": [{"text": "오늘 시"}, {"text": "발표"}]}
    import tools.calcopy.hybrid.script_audit as SA
    on = PG.text_gate(w, {"checks": {"hook_ending": True, "join_forbid": True}})
    off = PG.text_gate(w, {"checks": {}})
    assert any("같은 어미" in x for x in on) and any("이어 읽으면" in x for x in on)
    assert not any("같은 어미" in x or "이어 읽으면" in x for x in off)


def test_render01_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(encoder, "SLOT_DIR", str(tmp_path))
    with encoder.slot(1) as a:
        assert Path(a).exists()
        with pytest.raises(TimeoutError):
            with encoder.slot(1, timeout=0.6):
                pass
    assert not list(tmp_path.glob("*.lock"))


def test_jamak06_glyph_gate(tmp_path, monkeypatch):
    from tools.calcopy.engine import kal, fontmatch
    fonts = fontmatch.font_paths()
    if not fonts:
        pytest.skip("글꼴 창고 없음")
    f0 = Path(fonts[0])
    (tmp_path / "frame.json").write_text(json.dumps({"layers": [{"font": f0.stem}, {"font": "$per_video"}, {"font": "없는글꼴XYZ"}]}), encoding="utf-8")
    (tmp_path / "대본.json").write_text(json.dumps({"lines": [{"text": "가나 \U0001F99E"}]}, ensure_ascii=False), encoding="utf-8")
    out = kal.glyph_gate(tmp_path, tmp_path)
    assert any("없는글꼴XYZ" in x for x in out)


def test_copy01_space_width(monkeypatch):
    class FakeFont:
        def getlength(self, s):
            return 0
    from tools.calcopy.engine import fontmatch
    monkeypatch.setattr(fontmatch, "_font", lambda p, s: FakeFont())
    monkeypatch.setattr(fontmatch.ImageDraw, "Draw", lambda im: SimpleNamespace(text=lambda *a, **k: None))
    assert fontmatch.missing_glyphs("x.ttf", "가 나")[0] == " "


def test_done_by_make00_make_one_calls_owners():
    """목소리-13·소리-09·소재-09 = 이미 make_one 안에 있던 함수(추가 코드 0). 실제 동작으로 잰다: kal.step_make → make_one 이 timing·encode_final 까지 가는지는
    test_kal_core5::test_make_reaches_real_make_one(진짜 make_one 호출) + 아래 — make_one 을 돌려 timing 이 불리는지(앞 단계는 가짜로 통과)."""
    import types
    calls = []
    PMm = PM
    orig = (PMm.load_preset, PMm.load_work, PMm.plan_check, PMm.tts, PMm.narration, PMm.timing)
    try:
        PMm.load_preset = lambda p: ({}, {"checks": {}, "window": [1080, 1920]})
        PMm.load_work = lambda w, M, c: {"S": {}, "data": Path("."), "lines": [], "pieces": [], "cuts": [], "name": "x", "dir": None}
        PMm.plan_check = lambda w, c: {}
        PMm.tts = lambda *a, **k: Path("n.wav")
        PMm.narration = lambda *a, **k: (Path("n.wav"), 1.0)
        def timing(*a, **k):
            calls.append("timing")
            raise RuntimeError("멈춤(시험)")
        PMm.timing = timing
        PG_ = PG
        o2 = (PG_.text_gate, PG_.voice_gate)
        PG_.text_gate = lambda w, c=None: []
        PG_.voice_gate = lambda *a, **k: []
        a = types.SimpleNamespace(plan=False, allow_tts=True, tts=None, test=True, out=str(Path(__import__("tempfile").mkdtemp())), tag=None, cache=None, desktop_dir=".", results=".")
        with pytest.raises(RuntimeError, match="멈춤"):
            PMm.make_one(Path("."), Path("."), a)
        assert calls == ["timing"]
    finally:
        PMm.load_preset, PMm.load_work, PMm.plan_check, PMm.tts, PMm.narration, PMm.timing = orig
        PG_.text_gate, PG_.voice_gate = o2


def test_m03_timing_words_flag(monkeypatch, tmp_path):
    from tools.calcopy import narr_video as N
    calls = []
    monkeypatch.setattr(N, "time_steps", lambda steps, narr, lines=None, log=None, asr=False: calls.append(asr) or ([{"t0": 0, "t1": 1, "line": 0}], 1.0))
    monkeypatch.setattr(PM, "find_asr_cache", lambda narr, data: "")
    monkeypatch.setattr(PM, "timing_broken", lambda t, d: "")
    w = {"pieces": [{"text": "a", "chars": 1, "line": 0}], "lines": [{"tts": "a"}], "data": tmp_path}
    log = {}
    PM.timing(w, tmp_path / "n.wav", log, {"checks": {"timing_words": True}})
    assert calls == [True] and "받아쓰기 1순위" in log["line_timing"]["way"]
    calls.clear()
    PM.timing(w, tmp_path / "n.wav", {}, {"checks": {}})                 # 기본(칸 없음) = 종전 그대로
    assert calls == [False]


def _sound_graph(monkeypatch, tmp_path, master, sfx=None):
    seen = []
    monkeypatch.setattr(PM, "run", lambda cmd: seen.append([str(x) for x in cmd]))
    monkeypatch.setattr(PM, "lufs", lambda p: (-20.0, -1.0) if "mix" not in str(p) else (-14.0, -1.0))
    if sfx:
        from shopping_shorts import sfx_pack as SP
        monkeypatch.setattr(SP, "pack_for", lambda *a, **k: ("p", str(tmp_path)))
        monkeypatch.setattr(SP, "events", lambda stl, pack: [(str(tmp_path / "ding.wav"), 0.5, 0.3)])
    cfg = {"master": {"gain_start": 0, "tp_limit_db": -1.5, "lufs": -14, **master}, **({"sfx": sfx} if sfx else {})}
    w = {"lines": [{"slot": "s"}], "pieces": [{"line": 0, "f0": 0, "f1": 30, "text": "a"}]}
    log = {}
    PM.sound(w, cfg, tmp_path / "narr.wav", 1.0, tmp_path, log)
    return seen, log


def test_moksori05_limiter_bus_flag(monkeypatch, tmp_path):
    seen, log = _sound_graph(monkeypatch, tmp_path, {"limiter_bus": "bed"}, sfx={"density": "normal"})
    fc = next(c for c in seen if "-filter_complex" in c)
    assert "alimiter" in fc[fc.index("-filter_complex") + 1].split("[bed]")[0] and log["master"]["limiter_bus"] == "bed"
    assert "alimiter" not in " ".join(next(c for c in seen if str(tmp_path / "mix.wav") in c))
    seen, log = _sound_graph(monkeypatch, tmp_path, {})
    assert "alimiter" in " ".join(next(c for c in seen if str(tmp_path / "mix.wav") in c))     # 기본 = 종전(전체 리미터)


def test_m02_sfx_gain_from_narr(monkeypatch, tmp_path):
    seen, log = _sound_graph(monkeypatch, tmp_path, {}, sfx={"density": "normal", "db_below_voice": 6})
    fc = next(c for c in seen if "-filter_complex" in c)
    assert "volume=0.5012" in fc[fc.index("-filter_complex") + 1] and log["sfx_gain"]["rule"].endswith("6dB")   # (-20-6)-(-20) = -6dB → 0.5012
