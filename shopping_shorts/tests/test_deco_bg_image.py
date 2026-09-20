"""이미지 틀(bg_image) — 캔바 등에서 만든 그림을 **그대로** 깐다.

★왜 생겼나(2026-08-31 사장님): "너가 코드로 다시그리면 느낌이 안나와".
  틀을 코드로 재현하면 색·간격은 맞춰도 질감이 죽는다. 그래서 그림 자체를 깐다.

여기서 잠그는 계약:
  1. 값은 **id(16자 hex)만** — 경로가 섞이면 폴더 밖 파일을 읽는다
  2. 그림이 바뀌면 캐시키가 갈린다(안 갈리면 "바꿨는데 화면은 그대로"가 된다)
  3. 깨진 파일·없는 id에도 렌더가 죽지 않는다(그림 한 장이 화면 전체를 막으면 안 된다)
  4. 투명 영역은 살아 있다 — 영상이 비쳐야 한다
"""
import hashlib

import pytest
from PIL import Image

from shopping_shorts import deco_frame as df


@pytest.fixture
def bg_id(tmp_path, monkeypatch):
    """반투명 테두리 + 가운데 투명인 그림을 이미지 틀로 등록한다."""
    monkeypatch.setattr(df, "_BG_DIR", tmp_path)
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    im.paste((17, 34, 51, 255), (0, 0, 1080, 300))       # 위쪽 띠만 불투명
    iid = hashlib.sha1(im.tobytes()).hexdigest()[:16]
    im.save(tmp_path / f"{iid}.png")
    return iid


def test_id_only_no_path_escape(tmp_path, monkeypatch):
    """★경로를 받으면 폰트와 같은 사고(폴더 밖 읽기)가 난다 — id 형식만 통과시킨다."""
    monkeypatch.setattr(df, "_BG_DIR", tmp_path)
    for bad in ("../../app", "abc", "0123456789abcdef0", "../../../etc/passwd",
                "a" * 16 + "/x", "", None):
        assert df.bg_image_path(bad) is None, f"{bad!r}가 통과했다"
        assert df.normalize({"bg_image": bad})["bg_image"] == ""


def test_image_is_laid_down_as_is(bg_id):
    """그림이 실제로 깔린다 — 위쪽은 그림 색, 가운데는 투명(영상이 비친다)."""
    im = df.render({"preset": "plain_black", "bar_h": 0, "bg_image": bg_id})
    assert im.getpixel((540, 150))[:3] == (17, 34, 51), "이미지 틀이 안 깔렸다"
    assert im.getpixel((540, 1000))[3] == 0, "가운데가 막히면 영상이 안 보인다"


def test_cache_key_changes_with_image(bg_id):
    """★id가 내용 해시라 그림이 바뀌면 키가 갈린다 — 안 갈리면 옛 그림이 되살아난다."""
    assert (df.cache_key({"preset": "plain_black", "bg_image": bg_id})
            != df.cache_key({"preset": "plain_black"}))


def test_missing_or_broken_image_does_not_kill_render(tmp_path, monkeypatch):
    """★그림 한 장 때문에 미리보기가 통째로 안 나오면 안 된다(fail-open)."""
    monkeypatch.setattr(df, "_BG_DIR", tmp_path)
    broken = "b" * 16
    (tmp_path / f"{broken}.png").write_bytes(b"not a png")
    for iid in (broken, "c" * 16):
        im = df.render({"preset": "plain_black", "bar_h": 120, "bg_image": iid})
        assert im.size == (df.W, df.H)


def test_any_ratio_fills_the_frame(tmp_path, monkeypatch):
    """★가로 그림을 넣어도 여백이 남으면 안 된다 — 여백으로 영상이 새어 나온다."""
    monkeypatch.setattr(df, "_BG_DIR", tmp_path)
    wide = Image.new("RGBA", (1920, 1080), (200, 30, 30, 255))
    iid = hashlib.sha1(wide.tobytes()).hexdigest()[:16]
    wide.save(tmp_path / f"{iid}.png")
    im = df.render({"preset": "plain_black", "bar_h": 0, "bg_image": iid})
    for y in (5, 960, 1915):
        assert im.getpixel((540, y))[3] == 255, f"y={y}에 여백이 남았다"


# ── 글자칸 세로위치 + 바탕 끄기 (이미지 틀과 짝, 2026-08-31) ────────────────
def test_zero_means_untouched_old_drawing_is_identical():
    """★0 = '안 정했음' 규약 — 새 값을 안 주면 지금까지의 그림과 **픽셀까지 같아야** 한다."""
    base = {"preset": "sul_museun", "channel": "채널명", "title": "제목이 여기 들어가요",
            "views": "264만", "comments": "587"}
    a = df.render(base)
    b = df.render({**base, "ch_y": 0, "title_y": 0, "head_block": True})
    assert a.tobytes() == b.tobytes(), "기본값인데 그림이 달라졌다"


def test_title_block_moves_vertically():
    base = {"preset": "plain_black", "bar_h": 0, "title": "여기 제목", "head_bg": "#FFFFFF"}
    top = df.render({**base, "title_y": 10})
    low = df.render({**base, "title_y": 70})
    assert top.getpixel((540, 200))[3] > 0 and top.getpixel((540, 1400))[3] == 0
    assert low.getpixel((540, 1400))[3] > 0 and low.getpixel((540, 200))[3] == 0


def test_head_block_off_leaves_the_image_visible():
    """★바탕을 끄면 글자만 얹힌다 — 켜져 있으면 캔바 그림이 통째로 덮인다."""
    base = {"preset": "plain_black", "bar_h": 0, "title": "여기 제목", "title_y": 40}
    on, off = df.render({**base}), df.render({**base, "head_block": False})
    band_on = sum(on.getpixel((x, 790))[3] > 0 for x in range(0, df.W, 20))
    band_off = sum(off.getpixel((x, 790))[3] > 0 for x in range(0, df.W, 20))
    assert band_on > band_off, "바탕을 껐는데 덮인 넓이가 안 줄었다"


def test_channel_name_draws_without_a_bar():
    """★띠가 없으면(이미지 틀) 채널명이 통째로 사라지던 자리 — ch_y를 주면 그려야 한다."""
    im = df.render({"preset": "plain_black", "bar_h": 0, "channel": "숏템메이커",
                    "ch_y": 30, "ch_size": 60})
    band = sum(im.getpixel((x, int(df.H * 0.30)))[3] > 0 for x in range(0, df.W, 10))
    assert band > 0, "띠 없이 채널명이 안 그려졌다"


# ── 기본 제공 이미지 틀 (2026-08-31 "너가 만든거 없어?") ─────────────────────
def test_builtin_frames_ship_with_the_product():
    """★올린 게 없어도 목록이 비면 안 된다 — 빈 통이면 기능이 없는 것과 같다."""
    items = df.builtin_frames()
    assert len(items) >= 5, f"기본 제공 틀이 너무 적다({len(items)}종)"
    for it in items:
        p = df.bg_image_path(it["id"])
        assert p, f"{it['id']}: 목록에 있는데 파일이 없다"
        with Image.open(p) as im:
            assert im.size == (df.W, df.H), f"{it['id']}: 출력 규격이 아니다 {im.size}"
            assert im.mode == "RGBA" and im.getpixel((df.W // 2, 1300))[3] == 0, (
                f"{it['id']}: 영상 자리가 막혀 있다 — 영상이 안 보인다")


def test_builtin_id_cannot_escape_its_folder():
    """★기본 제공은 이름(hex가 아님)이라 경로검사가 따로 필요하다."""
    for bad in ("../deco_frame", "a/b", "..", "AB", "x" * 40, "../../app"):
        assert df.bg_image_path(bad) is None, f"{bad!r}가 통과했다"


def test_builtin_frame_actually_renders():
    items = df.builtin_frames()
    im = df.render({"preset": "plain_black", "bar_h": 0, "icons": False,
                    "bg_image": items[0]["id"]})
    assert im.getpixel((df.W // 2, 60))[3] > 0, "띠가 안 그려졌다"
    assert im.getpixel((df.W // 2, 1300))[3] == 0, "영상 자리가 막혔다"
