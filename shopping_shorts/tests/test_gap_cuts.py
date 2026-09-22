"""문장 중간 무음 잘라내기(gap_cuts) — 감지·잘라내기·자막 당김·렌더 배선.

★왜 이 기능이 필요한가(2026-09-22 실측, job 409f894230c6 비트 5개):
    앞뒤 끝 무음 = 0.00초 (pace_mode가 이미 걷어냄)
    문장 중간 무음 = 12구간 2.59초  ← 자를 것이 전부 여기 있다
  즉 끝만 자르는 기능은 이 환경에서 아무 일도 하지 않는다.
"""
import shutil
import subprocess

import pytest

from shopping_shorts.audio_post import _audio_dur, cut_gaps, find_gaps
from shopping_shorts.video_assemble import _adjust_caps_for_trim

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


@pytest.fixture
def mid_gap_mp3(tmp_path):
    """소리 1초 + **중간 무음 0.8초** + 소리 1초 = 2.8초. 끝에는 무음이 없다."""
    out = tmp_path / "mid.mp3"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=0.8",
         "-filter_complex", "[0][1][0]concat=n=3:v=0:a=1", "-q:a", "4", str(out)],
        stdin=subprocess.DEVNULL, capture_output=True, check=True)
    return out


def test_find_gaps_finds_middle_silence(mid_gap_mp3):
    gaps = find_gaps(str(mid_gap_mp3))
    assert len(gaps) == 1, f"중간 무음 1구간이 나와야 하는데 {gaps}"
    g = gaps[0]
    assert 0.9 < g["start"] < 1.15, f"시작이 1초 근처여야 한다: {g}"
    assert g["drop"] > 0.6, f"0.8초 중 대부분을 지워야 한다: {g}"


def test_find_gaps_ignores_edge_silence(tmp_path):
    """앞뒤 끝 무음은 head_trim/tail_trim의 몫 — 여기서 또 세면 두 번 잘린다."""
    out = tmp_path / "edge.mp3"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=1",
         "-filter_complex", "[1][0][1]concat=n=3:v=0:a=1", "-q:a", "4", str(out)],
        stdin=subprocess.DEVNULL, capture_output=True, check=True)
    assert find_gaps(str(out)) == [], "끝 무음을 중간 쉼으로 잘못 셌다"


def test_cut_gaps_shortens_audio(mid_gap_mp3, tmp_path):
    """실제로 짧아져야 한다 — 길이를 재서 확인한다(계획이 아니라 결과물)."""
    before = _audio_dur(str(mid_gap_mp3))
    gaps = find_gaps(str(mid_gap_mp3))
    out = tmp_path / "cut.mp3"
    made = cut_gaps(str(mid_gap_mp3), str(out), gaps)
    assert made, "잘라낸 파일이 안 만들어졌다"
    after = _audio_dur(made)
    drop = sum(g["drop"] for g in gaps)
    assert after < before - 0.5, f"{before:.2f}초 → {after:.2f}초 (안 줄었다)"
    assert abs((before - after) - drop) < 0.15, \
        f"예측 {drop:.2f}초 vs 실제 {before-after:.2f}초 — 어긋나면 자막도 어긋난다"


def test_cut_gaps_removes_the_silence(mid_gap_mp3, tmp_path):
    """자른 뒤에는 그 쉼이 실제로 없어야 한다(길이만 맞고 엉뚱한 데를 자르면 안 된다)."""
    out = tmp_path / "cut.mp3"
    cut_gaps(str(mid_gap_mp3), str(out), find_gaps(str(mid_gap_mp3)))
    assert find_gaps(str(out)) == [], "자른 뒤에도 중간 무음이 남아 있다"


def test_cut_gaps_noop_without_gaps(mid_gap_mp3, tmp_path):
    out = tmp_path / "x.mp3"
    assert cut_gaps(str(mid_gap_mp3), str(out), []) is None
    assert not out.exists(), "자를 게 없는데 파일을 만들었다"


def test_cut_gaps_does_not_fade_the_outer_ends(mid_gap_mp3, tmp_path):
    """★바깥쪽 끝(문장의 앞/뒤)에는 페이드를 걸지 않는다 (2026-09-23 "5초가 뚝끊김").

    실사고: 조각마다 페이드를 걸면서 **마지막 조각의 끝**에도 걸었다. 거기는 원래 문장의
    끝이라 말이 살아있는데, 페이드가 그 말을 깎아 0.141 -> 0.000 절벽을 만들었다.
    → 페이드는 **잘린 이음매에만**. 바깥쪽 끝은 원본 그대로 둔다.

    ⚠️첫 시도의 테스트는 "끝 음량이 절반 이상"이라는 느슨한 기준이라 옛 코드도 통과했다
      (12ms 페이드는 10ms 해상도에서 거의 안 보인다). 그래서 **필터 문자열을 직접 검사**한다 —
      의도가 코드에 있는지를 보는 것이 음량 비교보다 정확하다."""
    import shopping_shorts.audio_post as ap

    seen = {}

    orig = ap.subprocess.run

    def fake_run(cmd, **kw):
        # ⚠️cut_gaps는 _audio_dur(ffprobe)도 부른다 — 그건 통과시켜야 한다.
        #   전부 가로채면 길이가 0이 돼 필터를 만들기 전에 빠져나간다(첫 시도에서 이걸로 실패).
        if "-filter_complex" in cmd:
            seen["fc"] = cmd[cmd.index("-filter_complex") + 1]
        return orig(cmd, **kw)

    ap.subprocess.run = fake_run
    try:
        cut_gaps(str(mid_gap_mp3), str(tmp_path / "x.mp3"), find_gaps(str(mid_gap_mp3)))
    finally:
        ap.subprocess.run = orig

    fc = seen.get("fc", "")
    assert fc, "filter_complex를 못 잡았다"
    pieces = fc.split(";")
    first = next(p for p in pieces if p.endswith("[p0]"))
    last_i = max(int(p.split("[p")[-1].rstrip("]")) for p in pieces if "[p" in p and p.endswith("]") and p.split("[p")[-1].rstrip("]").isdigit())
    last = next(p for p in pieces if p.endswith(f"[p{last_i}]"))
    assert "afade=t=in" not in first, f"첫 조각 시작에 페이드가 걸렸다: {first}"
    assert "afade=t=out" not in last, f"★마지막 조각 끝에 페이드가 걸렸다(말이 깎인다): {last}"
    # 이음매 쪽에는 있어야 한다
    assert "afade=t=out" in first, "이음매(첫 조각 끝)에 페이드가 없다"
    assert "afade=t=in" in last, "이음매(마지막 조각 시작)에 페이드가 없다"


def test_cut_fade_long_enough():
    """이음매 페이드가 너무 짧으면 낙차를 못 감춘다(12ms로는 한 칸에 떨어진다)."""
    from shopping_shorts.audio_post import _CUT_FADE
    assert _CUT_FADE >= 0.02, f"이음매 페이드가 너무 짧다({_CUT_FADE}s)"


def test_cut_gaps_keeps_original_file(mid_gap_mp3, tmp_path):
    """원본은 절대 안 건드린다 — 되돌리기가 원본에 기대고 있다."""
    before = _audio_dur(str(mid_gap_mp3))
    cut_gaps(str(mid_gap_mp3), str(tmp_path / "c.mp3"), find_gaps(str(mid_gap_mp3)))
    assert abs(_audio_dur(str(mid_gap_mp3)) - before) < 1e-6


# ── 자막 타이밍 ──────────────────────────────────────────────────────────
def test_captions_shift_for_gap_cuts():
    """중간을 자르면 그 뒤 구절이 당겨져야 한다 — 안 그러면 자막이 뒤로 밀린다."""
    beat = {"cap_lead": 0.0, "cap_durs": [1.0, 1.0, 1.0],
            "gap_cuts": [{"start": 1.0, "end": 1.5, "drop": 0.44}]}
    lead, durs = _adjust_caps_for_trim(beat)
    assert abs(sum(durs) - (3.0 - 0.44)) < 1e-6, \
        f"총 자막시간이 잘라낸 만큼 줄어야 한다: {durs}"


def test_captions_unchanged_without_gap_cuts():
    """gap_cuts가 없으면 지금까지와 완전히 같아야 한다(기존 동작 보존)."""
    beat = {"cap_lead": 0.3, "cap_durs": [1.0, 2.0]}
    assert _adjust_caps_for_trim(beat) == (0.3, [1.0, 2.0])


def test_captions_apply_both_head_trim_and_gaps():
    """앞트림과 중간컷이 **함께** 걸려도 둘 다 반영돼야 한다.
    ★한쪽만 반영하고 return하면 다른 쪽이 통째로 죽는다(0순위-B)."""
    beat = {"cap_lead": 0.5, "cap_durs": [1.0, 1.0], "head_trim": 0.2,
            "gap_cuts": [{"start": 1.2, "end": 1.6, "drop": 0.3}]}
    lead, durs = _adjust_caps_for_trim(beat)
    assert abs(lead - 0.3) < 1e-6, f"앞트림 0.2가 리드인에서 빠져야 한다: lead={lead}"
    assert abs(sum(durs) - (2.0 - 0.3)) < 1e-6, f"중간컷 0.3도 빠져야 한다: {durs}"


# ── 렌더 배선 ────────────────────────────────────────────────────────────
def test_apply_gap_cuts_swaps_path(mid_gap_mp3, tmp_path):
    """렌더가 받는 tts_paths가 잘린 파일로 바뀌어야 한다."""
    from shopping_shorts.video_assemble import _apply_gap_cuts
    plan = {"beats": [{"beat_idx": 0, "gap_cuts": find_gaps(str(mid_gap_mp3))}]}
    work = tmp_path / "w"
    work.mkdir()
    out = _apply_gap_cuts(plan, {0: str(mid_gap_mp3)}, work)
    assert out[0] != str(mid_gap_mp3), "경로가 안 바뀌었다 — 렌더가 원본을 쓴다"
    assert _audio_dur(out[0]) < _audio_dur(str(mid_gap_mp3))


def test_apply_gap_cuts_leaves_others_alone(mid_gap_mp3, tmp_path):
    """gap_cuts가 없는 비트는 원본 경로 그대로(기존 동작 보존)."""
    from shopping_shorts.video_assemble import _apply_gap_cuts
    plan = {"beats": [{"beat_idx": 0}]}
    work = tmp_path / "w"
    work.mkdir()
    out = _apply_gap_cuts(plan, {0: str(mid_gap_mp3)}, work)
    assert out[0] == str(mid_gap_mp3)
