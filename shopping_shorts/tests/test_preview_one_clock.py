# -*- coding: utf-8 -*-
"""편집 화면의 시계는 **합본 하나** — 다음 사람이 둘로 되돌리지 못하게 잠근다.

배경 (2026-09-21 사장님 "앞으로 발생 안 하면 된다고")
  편집 화면은 시계가 둘이었다: 영상 한 벌(<video>), 음성 한 벌(<audio>).
  되감을 때마다 손으로 맞췄는데 mp3 는 요청한 자리에 못 앉는다(프레임 경계로만 앉는다) —
  실측 2026-09-21: 13개 컷 전부에서 음성이 화면보다 +0.14~0.19초 앞섰다.
  없앨 수 없는 오차를 맞추려 드니 같은 자리에서 여섯 번 터졌다:
      08-14 다음 칸 첫 장면이 잠깐 보인다      08-20 음성이 죽으면 0초로 튕김
      08-15 재생돼도 화면이 안 움직인다        09-02 그림만 정지한다
      08-17 마우스로 시간 이동이 안 된다        09-18 되감으면 다음다음 컷이 낀다
  매번 **가리는 방법만** 바꿨고 구조는 그대로였다. 그래서 구조를 뽑았다.

★여기서 지키는 것은 두 가지다.
  ① 합본에 음성이 같이 구워진다 (-an 을 되살리면 시계가 다시 둘이 된다)
  ② 화면이 합본 위치를 **짐작하지 않는다** (서버가 잰 값을 쓴다)
     짐작이 되살아나면 전체 재생이 칸에 멈춘다 — 실측: 화면 5.52 vs 합본 5.60.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
JS = (ROOT / "static" / "scene_play.js").read_text(encoding="utf-8")


def _strip_js_comments(js):
    """주석을 걷는다 — **왜 없앴는지 적은 글**이 금칙어에 걸리면 안 된다."""
    return "\n".join((ln.split("//")[0] if "//" in ln else ln) for ln in js.splitlines())


def _build_body():
    i = APP.index("def _pvproxy_build(")
    return APP[i:APP.index("\n@app.", i)]


# ── ① 시계가 하나인가 ────────────────────────────────────────────────────
def test_proxy_carries_audio():
    """합본에 음성이 같이 구워져야 한다 — 이게 시계를 하나로 만드는 지점."""
    b = _build_body()
    assert '"-map", "1:a:0"' in b, "합본에 음성을 안 넣는다(시계가 다시 둘이 된다)"
    assert '"-c:a", "aac"' in b, "음성 트랙이 없다"


def test_beat_audio_is_padded_to_video():
    """칸 음성을 그 칸 영상 길이에 맞춰야 누적 밀림이 0이 된다(실측 6칸에 0.131초)."""
    assert '"-af", "apad"' in _build_body(), "칸 길이를 안 맞춘다(뒤로 갈수록 자막이 밀린다)"


def test_cut_boundaries_get_keyframes():
    """컷 경계마다 되감을 수 있는 지점이 있어야 컷으로 되감는 동작이 정확히 앉는다."""
    assert "-force_key_frames" in _build_body(), "컷 경계에 키프레임이 없다(되감으면 밀린다)"


def test_proxy_is_not_downscaled():
    """소재 원본이 720 이다. 줄이면 화질만 잃고 **더 느리다**(실측 5.08초 vs 4.11초)."""
    assert "scale=360:640" not in APP, "합본을 360 으로 줄인다(화질 손실 + 더 느림)"


# ── ② 짐작이 되살아나지 않았나 ───────────────────────────────────────────
def test_server_measures_positions():
    """칸 시작·칸 안 컷 경계를 **서버가 재서** 준다 — 화면이 짐작하면 어긋난다."""
    b = _build_body()
    assert '"offs"' in b and '"cuts"' in b, "서버가 잰 위치를 안 준다(화면이 짐작하게 된다)"


def test_client_uses_measured_positions():
    """화면은 서버가 준 값을 쓴다. 없을 때만 예전처럼 짐작한다(폴백)."""
    js = _strip_js_comments(JS)
    assert "PVX.cuts" in js, "화면이 서버가 잰 컷 경계를 안 쓴다"
    assert "r.j.offs" in js, "화면이 서버가 잰 칸 시작을 안 쓴다"


def test_cut_timer_uses_measured_length():
    """컷을 넘기는 시간도 실측 길이여야 한다 — 짐작이면 칸 끝 전에 멈춰 세운다."""
    js = _strip_js_comments(JS)
    i = js.index("function pvxStep(")
    body = js[i:js.index("\n}", i)]
    assert "_pdur" in body, "컷 넘김이 짐작 길이를 쓴다(전체 재생이 칸에 멈춘다)"


def test_proxy_is_not_paused_at_cut_end():
    """합본은 한 파일이라 칸 끝까지 이어져야 한다. 벽시계가 먼저 멈춰 세우면 칸에 선다."""
    js = _strip_js_comments(JS)
    i = js.index("function step()")
    body = js[i:i + 1200]
    assert "_px0" in body, "합본을 컷 타이머로 멈춰 세운다(전체 재생이 칸에 멈춘다)"


# ── ③ 칸별 재생도 같은 길인가 ────────────────────────────────────────────
def test_beat_play_uses_proxy():
    """칸별 재생·되감기도 합본을 쓴다 — 예전엔 전체 재생만 써서 조각 경로가 남아 있었다."""
    js = _strip_js_comments(JS)
    i = js.index("function playBeat(")
    body = js[i:js.index("\n}", i)]
    assert "pvxAttach" in body, "칸별 재생이 조각 경로로 돈다(재생기를 나눠 쓴다)"


def test_no_double_audio():
    """합본이 붙었으면 별도 음성을 또 틀지 않는다 — 틀면 같은 말이 두 번 들린다."""
    js = _strip_js_comments(JS)
    i = js.index("function playTts(")
    body = js[i:js.index("\n  const a = seatTts", i)]
    assert "pvxAudio()" in body, "합본과 별도 음성이 같이 돈다(소리가 두 번 난다)"


# ── ④ 합본이 **항상 있게** 하는 장치 (2026-09-21 사장님 "1 2 를 어떻게 없애냐고") ──
#
#   합본이 없는 동안에는 옛 경로(재생기를 컷끼리 나눠 쓰고 다음 컷을 미리 앉히는)로 돈다.
#   튐이 나던 그 길이다. 그래서 '합본이 없는 순간'을 줄이는 장치를 셋 넣었다:
#     · 컷·칸을 곳간에 두고 바뀐 것만 다시 만든다 (8.9초 → 1.8초, 실측)
#     · 그래서 버튼 없이 **자동으로** 다시 굽는다 (버튼을 안 누른 동안 합본이 낡던 것을 없앴다)
#     · 음성이 다 되면 **미리** 구워 둔다 (처음 열 때 18.5초 → 9.5초, 실측)
#   하나라도 되돌리면 그 구간이 되살아난다.

def test_cut_pieces_are_kept():
    """컷 조각을 지우지 않고 곳간에 둔다 — 지우면 매번 통째로 다시 굽는다(8.9초)."""
    b = _build_body()
    assert 'cache = d / "cuts"' in b, "컷 곳간이 없다(매번 전부 다시 굽게 된다)"
    assert "if keep.exists()" in b, "곳간에 있어도 다시 굽는다"


def test_beat_pieces_are_kept():
    """칸도 곳간에 둔다 — 칸 만들기가 굽기의 44%였다(칸영상 2.17초 + 칸음성 1.16초)."""
    assert "bkey = _hash(" in _build_body(), "칸 곳간이 없다(장면 하나 바꿔도 칸을 전부 다시 만든다)"


def test_cut_key_is_quantized():
    """곳간 키는 0.01초로 뭉뚱그린다.

    컷 계산이 두 벌(화면 planClips / 서버 plan_beat_clips_for)이라 부동소수 반올림이
    미세하게 갈린다. 그대로 두면 **한 조각도 재사용되지 않는다**(실측: 1.67 vs 1.669 로
    37조각이 전부 헛것이 됐다). 영상 한 프레임이 0.033초라 0.01 차이는 같은 그림이다.
    """
    b = _build_body()
    i = b.index("def _cut_key(")
    assert "_q(" in b[i:i + 1400], "곳간 키가 미세한 차이로 갈린다(재사용이 안 된다)"


def test_durations_are_memoized():
    """길이를 매번 다시 재지 않는다 — 재는 데만 44%를 쓰고 있었다(ffprobe 49번 3.31초)."""
    b = _build_body()
    assert "def _dur(" in b, "길이 메모가 없다"
    assert 'memo.write_text("%.6f,%d"' in b, "길이를 적어 두지 않는다"
    assert "st_mtime >= path.stat().st_mtime" not in b, \
        "날짜로 판정하면 안 된다 — 곳간 파일은 touch 하므로 메모가 늘 낡아 보인다"


def test_prewarm_exists_and_is_wired():
    """음성이 다 되면 미리 굽는다 — 편집 화면을 열었을 때 이미 있게."""
    assert "def _pvproxy_prewarm(" in APP, "미리 굽기가 없다"
    i = APP.index("def api_mix_voice(")
    assert "_pvproxy_prewarm" in APP[i:i + 3000], "음성 생성 뒤에 미리 굽기가 안 걸려 있다"


def test_no_manual_rebake_button():
    """장면을 바꾸면 자동으로 굽는다 — 버튼을 두면 안 누른 동안 합본이 낡는다."""
    js = _strip_js_comments(JS)
    i = js.index("function pvxTick(")
    body = js[i:i + 1800]
    assert "if (stable) PVX.want = p.key;" in body, "장면이 바뀌어도 자동으로 안 굽는다"
    assert "'stale'" not in body, "버튼을 눌러야 굽는 옛 방식이 남아 있다"
