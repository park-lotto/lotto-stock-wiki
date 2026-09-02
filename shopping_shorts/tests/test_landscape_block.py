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


# ── 거의 정사각인 소스를 막던 오판 (2026-08-31 cid110 이준연 제보) ──────────
# job adb9eb74362e: 인스타 릴 **736x718**(비율 1.025)이 "가로형(롱폼)"으로 막혔다.
# 18px 차이는 사람 눈엔 정사각이고, 세로 화면에 넣어도 좌우가 잘려 나가지 않는다.
# 함수 docstring은 원래부터 "정사각(1:1)은 가로형으로 치지 않는다"라고 적혀 있었는데
# 코드가 `w > h`라 1픽셀만 넓어도 걸렸다 — 의도와 코드가 어긋나 있었다.
#
# 실측(서버 script_extracts 399건): 비율 1.0~1.5 구간은 **0건**, 진짜 롱폼(1.5+)만
# 3건이다. 그래서 문턱을 둬도 막아야 할 것은 그대로 막힌다.

def test_near_square_is_not_landscape(wh):
    """736x718(1.025) — 고객이 실제로 막힌 크기. 막으면 안 된다."""
    wh.update({"near_sq.mp4": (736, 718)})
    assert mp._is_landscape("near_sq.mp4") is False


def test_near_square_variants_pass(wh):
    """정사각 근처(±10%)는 전부 통과해야 한다."""
    wh.update({"a.mp4": (1080, 1080),      # 정확한 1:1
               "b.mp4": (736, 718),        # 1.025 — 제보 건
               "c.mp4": (1100, 1000),      # 1.10
               "d.mp4": (1080, 1000)})     # 1.08
    for p in ("a.mp4", "b.mp4", "c.mp4", "d.mp4"):
        assert mp._is_landscape(p) is False, f"{p}를 가로형으로 오판했다"
    mp._block_landscape({"s0": "a.mp4", "s1": "b.mp4",
                         "s2": "c.mp4", "s3": "d.mp4"})     # 통과해야 한다


def test_real_landscape_still_blocked(wh):
    """★가드: 진짜 가로형은 여전히 막혀야 한다(문턱을 넣다 구멍내지 않게)."""
    wh.update({"fhd.mp4": (1920, 1080),    # 1.78 — 유튜브 롱폼
               "uhd.mp4": (3840, 2160),    # 1.78 — 실사고 그 영상
               "w43.mp4": (1440, 1080)})   # 1.33 — 4:3도 가로다
    for p in ("fhd.mp4", "uhd.mp4", "w43.mp4"):
        assert mp._is_landscape(p) is True, f"{p}를 놓쳤다"
    with pytest.raises(RuntimeError):
        mp._block_landscape({"s0": "fhd.mp4"})


def test_screen_and_block_agree():
    """★화면(source_brief.landscape)과 실제 차단이 **같은 함수**를 써야 한다.

    전엔 app.py가 `_w > _h`를 따로 적어, 문턱을 한쪽만 고치면
    "화면은 괜찮다는데 제작은 실패"가 난다(0순위-B). 여기서 그걸 막는다.
    """
    import inspect
    from shopping_shorts import app as ss_app
    src = inspect.getsource(ss_app.api_produce_source_brief)
    assert "is_landscape_wh" in src, "화면이 공용 판정 함수를 안 쓴다"
    assert "_w > _h" not in src, "화면이 판정식을 또 적고 있다(두 곳이 되면 어긋난다)"


def test_ratio_threshold_is_sane():
    """문턱이 실수로 뒤집히지 않게 — 1:1은 통과, 16:9는 차단이어야 한다."""
    assert mp.is_landscape_wh(1080, 1080) is False
    assert mp.is_landscape_wh(1920, 1080) is True
    assert mp.is_landscape_wh(0, 0) is None          # 못 재면 막지 않는다
    assert 1.0 < mp.LANDSCAPE_RATIO < 1.5
