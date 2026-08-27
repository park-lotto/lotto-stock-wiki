"""가로형(롱폼) 소스 차단 — 2026-08-27 실사고에서 나온 것.

job 6070eddd8a73: 세로 3편(720x1280·1080x1920·720x1280)에 유튜브 롱폼 가로 4K
1편이 섞였다. 붙임 캔버스가 그 한 편에 끌려가 세로 영상들이 가로로 늘어났고,
최종 세로 렌더에서 크게 잘려 고객에겐 "원본은 일반영상인데 결과물이 줌한 것처럼
크다"로 보였다. 비율 보존만으로는 부족하다 — 가로 영상은 세로 숏폼에 안 맞으므로
**시작할 때 분명히 실패**시킨다(사장님 지시).
"""
import pytest

from shopping_shorts import mix_pipeline as mp


@pytest.fixture()
def wh(monkeypatch):
    """경로 → (w, h)를 정해두고 _probe_wh_dur를 그걸로 답하게 한다."""
    table = {}

    def _fake(path):
        if path not in table:
            raise RuntimeError("못 잼")
        w, h = table[path]
        return w, h, 10.0

    monkeypatch.setattr(mp, "_probe_wh_dur", _fake)
    return table


def test_landscape_is_detected(wh):
    wh.update({"h.mp4": (1920, 1080), "v.mp4": (1080, 1920), "sq.mp4": (1080, 1080)})
    assert mp._is_landscape("h.mp4") is True
    assert mp._is_landscape("v.mp4") is False
    # 정사각은 가로형이 아니다 — 세로 화면에 넣어도 좌우가 잘려 나가지 않는다.
    assert mp._is_landscape("sq.mp4") is False


def test_unmeasurable_is_not_blocked(wh):
    """못 재는 걸 막을 근거로 쓰지 않는다 — 멀쩡한 영상을 막으면 그게 더 나쁘다."""
    assert mp._is_landscape("없는파일.mp4") is None
    mp._block_landscape({"s0": "없는파일.mp4"})      # 예외가 나면 안 된다


def test_block_names_the_offending_url(wh):
    """실사고 그대로: 세로 3편 + 가로 롱폼 1편.

    사유에 **어느 영상인지**가 있어야 한다 — "실패했습니다"만으론 고객이 뭘 빼야
    할지 모른다.
    """
    wh.update({"a.mp4": (720, 1280), "b.mp4": (1080, 1920),
               "c.mp4": (3840, 2160), "d.mp4": (720, 1280)})
    paths = {"s0": "a.mp4", "s1": "b.mp4", "s2": "c.mp4", "s3": "d.mp4"}
    urls = {"s0": "https://insta/1", "s1": "https://yt/2",
            "s2": "https://yt/롱폼", "s3": "https://tiktok/4"}
    with pytest.raises(RuntimeError) as e:
        mp._block_landscape(paths, urls)
    msg = str(e.value)
    assert "1개" in msg
    assert "https://yt/롱폼" in msg and "3840x2160" in msg
    assert "https://insta/1" not in msg          # 멀쩡한 소스는 지목하지 않는다


def test_all_portrait_passes(wh):
    wh.update({"a.mp4": (720, 1280), "b.mp4": (1080, 1920)})
    mp._block_landscape({"s0": "a.mp4", "s1": "b.mp4"})     # 통과해야 한다


def test_fit_box_keeps_aspect_and_is_even():
    """붙임 캔버스에 넣을 자리 계산 — ffmpeg의 scale/pad와 같은 값이어야 한다.

    짝수로 맞추는 것도 함께 본다: libx264(yuv420p)는 홀수 크기를 못 받는다.
    """
    cw, ch, cx, cy, ow, oh = mp._fit_box(720, 1280, 1920, 1920)
    assert (ow, oh) == (720, 1280)               # 되돌릴 원본 크기
    assert cw % 2 == 0 and ch % 2 == 0
    assert abs(cw / ch - 720 / 1280) < 0.01      # 비율이 유지된다
    assert cx == (1920 - cw) // 2 and cy == (1920 - ch) // 2   # 가운데
    # 가로 소스도 같은 규칙
    cw2, ch2, _cx2, _cy2, _ow2, _oh2 = mp._fit_box(1920, 1080, 1920, 1920)
    assert (cw2, ch2) == (1920, 1080)
