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
        asr_local.transcribe("x.wav", engine="speechmatics")
    monkeypatch.setattr(asr_local, "speechmatics_key", lambda: "k")
    n = []
    monkeypatch.setattr(asr_local, "_speechmatics", lambda p: n.append(1) or (_ for _ in ()).throw(OSError("net")))
    with pytest.raises(RuntimeError, match="2번 실패"):
        asr_local.transcribe("x.wav", engine="speechmatics")
    assert len(n) == 2


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


def test_sojae06_render02_part_vf():
    c = {"box": [0, 0, 1080, 1920], "speed": 1.0}
    assert "scale=1080:1920" in PM.part_vf(c, 1080, 1919)          # 홀수 → 짝수
    with pytest.raises(ValueError, match="늘어짐"):
        PM.part_vf({"box": [0, 0, 1080, 1080], "speed": 1.0}, 1080, 1920)


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
    src = inspect.getsource(PM.make_one)
    for call in ("timing(", "build_cuts(", "encode_final(", "PG.pre_render(", "cover_card("):     # 목소리-13 · 소리-09 · 소재-09(cut_gates ④ = pre_render 안)
        assert call in src
    assert "cut_gates(" in inspect.getsource(PG.pre_render)


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
