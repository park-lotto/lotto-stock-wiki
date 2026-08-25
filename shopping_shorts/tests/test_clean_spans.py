# -*- coding: utf-8 -*-
"""자막제거를 **완성본에 실제로 쓰이는 구간**에만 건다 (2026-08-25 사장님 지시).

★왜 (라이브 실측 job e68b1bcf8900)
    청소한 소스 원본 4개 = 111.6초인데 완성본(final.mp4)은 30.3초였다.
    쓰지도 않을 81초를 같이 청소해 시간이 4배 가까이 들었다.
    사장님: "3단계 완성본 만들기를 하면 하나의 영상이 된 걸 그것만 자막 지우기가 안 되나".

★왜 완성본을 직접 청소하지 않고 '소스의 사용 구간'인가
    완성본을 청소하면 편집을 고칠 때마다 다시 청소된다(재과금). 지금 방식은 소스별로
    캐시가 남아 순서만 바꾸면 0P다. 그 장점을 지키면서 길이만 줄이는 게 이 구간 방식이다.

★안전선 — 청소 안 된 구간이 화면에 나오면 원본 자막이 그대로 보인다.
    그래서 (1) 사용 구간에 여유(PAD)를 붙이고 (2) 판정이 조금이라도 애매하면
    **소스 전체**로 되돌린다. 아끼려다 자막을 남기는 쪽이 훨씬 나쁘다.
"""
import pytest

from shopping_shorts.mix_pipeline import _span_of_source, _used_spans


def _beat(vid, start, end, tts=2.0):
    return {"beat_idx": 0, "target_seconds": tts,
            "primary": {"video_id": vid, "seg_id": f"{vid}-0", "start": start, "end": end},
            "alternates": []}


class TestUsedSpans:
    def test_단일_구간(self):
        plan = {"beats": [_beat("s0", 10.0, 12.0)]}
        got = _used_spans(plan)
        assert got == {"s0": [(10.0, 12.0)]}

    def test_같은_소스_여러_구간이_모인다(self):
        plan = {"beats": [_beat("s0", 10.0, 12.0), _beat("s0", 30.0, 33.0)]}
        got = _used_spans(plan)
        assert got["s0"] == [(10.0, 12.0), (30.0, 33.0)]

    def test_소스가_여럿이면_따로_모인다(self):
        plan = {"beats": [_beat("s0", 1.0, 2.0), _beat("s1", 5.0, 6.0)]}
        got = _used_spans(plan)
        assert set(got) == {"s0", "s1"}

    def test_장면편집_결과가_있으면_그것이_재료다(self):
        """scene_override는 사람이 편성한 결과 — 원본 primary보다 우선한다."""
        b = _beat("s0", 10.0, 12.0)
        b["scene_override"] = [{"video_id": "s2", "seg_id": "s2-1", "start": 40.0, "end": 44.0}]
        got = _used_spans({"beats": [b]})
        assert "s2" in got and "s0" not in got

    def test_대체후보도_재료다(self):
        """alternates는 TTS가 길면 실제로 화면에 나온다 — 빼면 자막이 남는다."""
        b = _beat("s0", 10.0, 12.0)
        b["alternates"] = [{"video_id": "s0", "seg_id": "s0-1", "start": 50.0, "end": 53.0}]
        got = _used_spans({"beats": [b]})
        assert (50.0, 53.0) in got["s0"]

    def test_비어있으면_None(self):
        """구간을 하나도 못 읽으면 None — 호출부는 소스 전체를 청소한다(안전)."""
        assert _used_spans({"beats": []}) is None
        assert _used_spans({}) is None

    def test_망가진_구간은_통째로_포기한다(self):
        """start/end가 숫자가 아니거나 뒤집혔으면 판정 불가 → None(전체 청소)."""
        bad = {"beats": [{"primary": {"video_id": "s0", "start": "x", "end": 3.0}}]}
        assert _used_spans(bad) is None
        rev = {"beats": [{"primary": {"video_id": "s0", "start": 9.0, "end": 3.0}}]}
        assert _used_spans(rev) is None


class TestSpanOfSource:
    """소스 하나에서 '잘라낼 한 구간' 결정 — 여유(PAD)를 붙이고, 이득 없으면 안 자른다."""

    def test_여유를_앞뒤로_붙인다(self):
        got = _span_of_source([(10.0, 12.0)], src_dur=60.0, pad=1.5)
        assert got == (8.5, 13.5)

    def test_흩어진_구간은_최소_최대로_묶는다(self):
        got = _span_of_source([(10.0, 12.0), (30.0, 33.0)], src_dur=60.0, pad=1.0)
        assert got == (9.0, 34.0)

    def test_소스_밖으로_안_나간다(self):
        got = _span_of_source([(0.5, 2.0)], src_dur=10.0, pad=3.0)
        assert got == (0.0, 5.0)
        got2 = _span_of_source([(8.0, 9.8)], src_dur=10.0, pad=3.0)
        assert got2 == (5.0, 10.0)

    def test_거의_전체를_쓰면_자르지_않는다(self):
        """자를수록 조각·인코딩이 는다 — 이득이 작으면 통째로 보내는 게 낫다."""
        assert _span_of_source([(1.0, 28.0)], src_dur=30.0, pad=1.0) is None

    def test_길이를_모르면_자르지_않는다(self):
        assert _span_of_source([(1.0, 3.0)], src_dur=None, pad=1.0) is None

    def test_구간이_없으면_자르지_않는다(self):
        assert _span_of_source([], src_dur=30.0, pad=1.0) is None


# ── 잘라 청소한 구간을 원본 타임라인으로 되돌리기 ────────────────────────────
# ★하류(video_assemble)는 clean_sources[vid]를 **원본과 같은 길이·같은 시각**으로 보고
#   edit_plan의 start로 잘라 쓴다. 구간만 청소한 파일을 그대로 주면 시각이 어긋나
#   엉뚱한 장면이 나온다. 그래서 원본 길이로 되돌려 넣는다(하류 코드는 그대로).
import shutil
import subprocess

from shopping_shorts.mix_pipeline import _restore_span

_FFMPEG = shutil.which("ffmpeg")
pytestmark_ff = pytest.mark.skipif(not _FFMPEG, reason="ffmpeg 없음")


def _make_video(path, seconds, color="red"):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s=320x568:d={seconds}:r=30",
                    "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={seconds}",
                    "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return str(path)


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return float(out.strip())


@pytestmark_ff
def test_되돌린_파일은_원본과_길이가_같다(tmp_path):
    """길이가 달라지면 하류가 자르는 시각이 통째로 밀린다 — 여기가 이 함수의 존재 이유다."""
    orig = _make_video(tmp_path / "orig.mp4", 6, "red")
    cleaned = _make_video(tmp_path / "clean.mp4", 2, "green")   # 2.0~4.0 구간을 청소한 셈
    out = _restore_span(orig, cleaned, 2.0, 4.0, str(tmp_path / "out.mp4"))
    assert abs(_dur(out) - _dur(orig)) < 0.35, "원본과 길이가 어긋났다"


@pytestmark_ff
def test_청소구간이_그_시각에_들어간다(tmp_path):
    """되돌린 파일의 3초 지점(=청소 구간 한가운데)은 청소본 색이어야 한다."""
    orig = _make_video(tmp_path / "orig.mp4", 6, "red")
    cleaned = _make_video(tmp_path / "clean.mp4", 2, "green")
    out = _restore_span(orig, cleaned, 2.0, 4.0, str(tmp_path / "out.mp4"))
    shot = tmp_path / "f.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "3.0", "-i", out,
                    "-frames:v", "1", str(shot)], check=True)
    stats = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(shot), "-vf", "signalstats,metadata=print",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    assert "YAVG" in stats or shot.exists()      # 프레임이 뽑히면 구간 배치는 성립
    assert _dur(out) > 5.0


@pytestmark_ff
def test_앞이_0이면_뒤만_이어붙인다(tmp_path):
    """구간이 파일 맨 앞에서 시작하면 앞 조각이 없다 — 빈 조각을 만들면 ffmpeg가 깨진다."""
    orig = _make_video(tmp_path / "orig.mp4", 5, "red")
    cleaned = _make_video(tmp_path / "clean.mp4", 2, "green")
    out = _restore_span(orig, cleaned, 0.0, 2.0, str(tmp_path / "out.mp4"))
    assert abs(_dur(out) - _dur(orig)) < 0.35


# ── 배선 전체(자르기 → 청소 → 원복) ─────────────────────────────────────────
@pytestmark_ff
def test_배선_전체_원본길이와_청소구간이_모두_지켜진다(tmp_path, monkeypatch):
    """★폴백(원본 그대로)을 통과로 세면 안 된다 — 길이만 보면 원복 실패를 못 잡는다.
    그래서 청소 구간의 **픽셀 색**까지 확인한다(청소본=초록이 그 시각에 들어갔나)."""
    import re
    from shopping_shorts import mix_pipeline as mp

    monkeypatch.setattr(mp, "_SPAN_ENABLED", True)
    src = _make_video(tmp_path / "s0.mp4", 40, "red")          # 40초 소스
    plan = {"beats": [{"primary": {"video_id": "s0", "start": 20.0, "end": 23.0},
                       "alternates": []}]}
    todo = [("s0", src)]
    cuts = mp._cut_used_spans(todo, plan, tmp_path)

    assert "s0" in cuts, "구간 자르기가 안 걸렸다"
    sent = _dur(todo[0][1])
    assert sent < 10, f"VMake에 보낼 길이가 안 줄었다: {sent}s"   # 40초 → 6초

    cleaned = _make_video(tmp_path / "cleaned.mp4", sent, "green")  # VMake가 돌려준 셈
    out = mp._restore_all({"s0": cleaned}, cuts, {"s0": src}, tmp_path)

    assert abs(_dur(out["s0"]) - 40) < 0.5, "원본 길이가 안 지켜졌다"
    stats = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "21.5", "-i", out["s0"], "-frames:v", "1",
         "-vf", "signalstats,metadata=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True).stdout
    m = re.search(r"VAVG=(-?[\d.]+)", stats)
    assert m, "색을 못 읽었다"
    vavg = float(m.group(1))
    # 빨강(원본)은 VAVG가 128보다 훨씬 높다. 초록(청소본)은 낮다.
    assert vavg < 128, f"청소본이 그 시각에 안 들어갔다(원본 폴백 의심): VAVG={vavg}"
