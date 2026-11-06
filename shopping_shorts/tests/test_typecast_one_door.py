"""11-06 황선희 #11577: 타입캐스트를 직접 부르는 길(옛 길·감정 길·tts_pause)이 낱자 빼기(speakable)를 안 거쳐 'ㄷㄷ·ㅋㅋ'를 소리 내어 읽었다.
엔진(tools/calcopy)의 타입캐스트 합성은 voice_synth.typecast_say 한 문으로만 — 직접 호출이 생기면 이 시험이 잡는다."""
import re
from pathlib import Path

from tools.calcopy.engine import voice_synth as VS

ROOT = Path(__file__).resolve().parents[2]


def test_no_direct_typecast_synthesize_in_engine():
    bad = []
    for p in (ROOT / "tools" / "calcopy").rglob("*.py"):
        if p.name == "voice_synth.py":
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = ln.split("#", 1)[0]
            if re.search(r"typecast_tts\.synthesize\(", code) and '"""' not in ln:
                bad.append(f"{p.relative_to(ROOT)}:{i}")
    assert not bad, f"typecast_tts.synthesize 직접 호출 — voice_synth.typecast_say 를 써라: {bad}"


def test_typecast_say_drops_jamo_and_keeps_text_timing(monkeypatch):
    from shopping_shorts import typecast_tts
    sent = []

    def fake(text, out, **kw):
        sent.append(text)
        n = len(text)
        return {"characters": list(text), "character_start_times_seconds": [i * 0.1 for i in range(n)],
                "character_end_times_seconds": [i * 0.1 + 0.1 for i in range(n)]}
    monkeypatch.setattr(typecast_tts, "synthesize", fake)
    a = VS.typecast_say("이거 진짜 ㄷㄷ 대박", "x.mp3", voice_id="v")
    assert sent == ["이거 진짜 대박"]
    assert "".join(a["characters"]) == "이거 진짜 ㄷㄷ 대박"
