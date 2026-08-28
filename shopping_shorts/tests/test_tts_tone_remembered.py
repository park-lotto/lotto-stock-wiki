"""톤 고르개가 지금 톤을 기억한다 (2026-08-28 사장님 제보).

제보: "tts 속삭임 누르고 톤바꿔서 다시 눌러도 다시 안정으로 돌아오는데"

뿌리: 화면의 <select id="vpTone{i}">는 다시 그릴 때마다 새로 만들어지는데
      selected를 정해주는 코드가 없어 **늘 첫 옵션(안정)**이 됐다. 어느 톤으로
      뽑았는지 기억하는 곳이 어디에도 없었다(voice_override에는 voice_id·settings·
      speed만 담긴다 — 톤 이름이 없다).
"""
import re
import pathlib

STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"
APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def _produce():
    return (STATIC / "produce.html").read_text(encoding="utf-8")


def test_regen_sends_the_tone_name():
    """톤 이름을 안 보내면 서버가 기록할 게 없다."""
    s = _produce()
    m = re.search(r"function _voiceForTone\(tone\)\{.*?\n\}", s, re.S)
    assert m, "_voiceForTone를 못 찾았다"
    assert "variant:tone" in m.group(0).replace(" ", "")


def test_server_stores_the_tone_on_the_beat():
    s = APP.read_text(encoding="utf-8")
    m = re.search(r"def api_mix_tts_regen\(.*?\n    return \{\"ok\": True\}", s, re.S)
    assert m, "regen 핸들러를 못 찾았다"
    body = m.group(0)
    assert '"tts_tone"' in body, "비트에 톤을 남기지 않으면 화면이 되짚을 수 없다"
    assert "store.update_mix_job" in body, "저장까지 해야 다음에 읽힌다"


def test_tone_is_not_mixed_into_the_synthesis_args():
    """★override에 섞으면 그대로 synthesize_line으로 흘러간다."""
    s = APP.read_text(encoding="utf-8")
    m = re.search(r"def api_mix_tts_regen\(.*?\n    return \{\"ok\": True\}", s, re.S)
    body = m.group(0)
    loop = re.search(r'for k in \(([^)]*)\):', body)
    assert loop and "variant" not in loop.group(1)


def test_select_restores_the_current_tone():
    s = _produce()
    m = re.search(r'<select id="vpTone\$\{i\}".*?</select>', s, re.S)
    assert m, "톤 고르개를 못 찾았다"
    sel = m.group(0)
    assert "selected" in sel, "selected가 없으면 늘 첫 옵션(안정)으로 돌아간다"
    assert "b.tts_tone" in sel, "비트에 남긴 값을 읽어야 한다"


def test_select_falls_back_to_stable():
    """옛 잡에는 tts_tone이 없다 — 그때는 지금까지처럼 안정."""
    s = _produce()
    sel = re.search(r'<select id="vpTone\$\{i\}".*?</select>', s, re.S).group(0)
    assert "'stable'" in sel or '"stable"' in sel


def test_all_four_tones_still_offered():
    s = _produce()
    sel = re.search(r'<select id="vpTone\$\{i\}".*?</select>', s, re.S).group(0)
    # 목록은 VARIANT_LABELS 하나에서 온다(0순위-B) — 이름이 두 벌이 되면 어긋난다
    assert "VARIANT_LABELS" in sel
    labels = re.search(r"const VARIANT_LABELS = \{([^}]*)\}", s).group(1)
    for k in ("stable", "natural", "expressive", "whisper"):
        assert k in labels
