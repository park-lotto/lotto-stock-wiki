"""이미지 틀은 자막·글자 **밑에** 깔린다 (2026-08-31).

★사장님 제보: "그림위로 올라가는게 해드카피만있고 자막 제목등 다 안된다."
  뿌리: 틀은 지금까지 **맨 마지막**에 얹혔다(video_assemble의 motion_layers).
  기존 20종은 띠 말고 전부 투명이라 덮을 게 없어 문제가 안 보였을 뿐이고,
  화면을 꽉 채우는 이미지 틀에선 자막·헤드카피가 통째로 묻힌다.

여기서 잠그는 계약:
  1. under_text인 틀만 미리 깔린다 — 기존 틀은 옛 순서 그대로(그림 무변경)
  2. 미리 깔았으면 **틀 슬롯을 비운다** — 안 비우면 뒤에서 또 얹어 결국 덮는다
  3. 실패해도 원본을 그대로 돌려준다(틀 하나가 렌더를 죽이면 안 된다)
  4. 표시를 붙이는 곳은 mix_pipeline 한 곳 — bg_image가 있을 때만
"""
import subprocess

import pytest
from PIL import Image

from shopping_shorts import video_assemble as va

W, H = va._OUT_W, va._OUT_H


def _blue_video(work):
    p = work / "in.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s={W}x{H}:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                   capture_output=True, check=True)
    return p


def _mid_color(path, work):
    f = work / "frame.png"
    subprocess.run(["ffmpeg", "-y", "-i", str(path), "-frames:v", "1", str(f)],
                   capture_output=True, check=True)
    with Image.open(f) as im:
        return im.convert("RGB").getpixel((W // 2, H // 2))


def test_marked_frame_is_composited_before_captions(tmp_path):
    vid = _blue_video(tmp_path)
    png = tmp_path / "tpl.png"
    Image.new("RGBA", (W, H), (0, 200, 0, 255)).save(png)      # 화면을 꽉 채우는 불투명 틀
    out, deco = va._pre_compose_under_text(
        str(vid), {"template": {"_abspath": str(png), "under_text": True}}, tmp_path)
    assert out != str(vid), "미리 까는 패스가 안 돌았다"
    r, g, b = _mid_color(out, tmp_path)
    assert g > 150 and b < 80, f"틀이 영상 위에 안 깔렸다({r},{g},{b})"
    # ★두 번 그리기 금지 — 뒤에서 또 얹으면 결국 자막을 덮는다
    assert "_abspath" not in (deco["template"] or {}), "틀 슬롯을 안 비웠다"


def test_plain_frame_keeps_the_old_order(tmp_path):
    """★기존 틀은 안 탄다 — 옛 작업의 그림이 한 픽셀도 바뀌면 안 된다."""
    vid = _blue_video(tmp_path)
    png = tmp_path / "tpl.png"
    Image.new("RGBA", (W, H), (0, 200, 0, 255)).save(png)
    deco_in = {"template": {"_abspath": str(png)}}              # under_text 없음
    out, deco = va._pre_compose_under_text(str(vid), deco_in, tmp_path)
    assert out == str(vid) and deco is deco_in, "기존 틀까지 순서가 바뀌었다"


def test_broken_png_does_not_kill_the_render(tmp_path):
    vid = _blue_video(tmp_path)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    out, _ = va._pre_compose_under_text(
        str(vid), {"template": {"_abspath": str(bad), "under_text": True}}, tmp_path)
    assert out == str(vid), "깨진 그림에 렌더가 끌려갔다"
    out2, _ = va._pre_compose_under_text(
        str(vid), {"template": {"_abspath": str(tmp_path / "none.png"), "under_text": True}}, tmp_path)
    assert out2 == str(vid)


def test_only_image_frames_get_the_mark():
    """★표시를 붙이는 곳은 mix_pipeline 한 곳 — bg_image가 있을 때만."""
    from shopping_shorts import deco_frame, mix_pipeline
    ids = [x["id"] for x in deco_frame.builtin_frames()]
    if not ids:
        pytest.skip("기본 제공 틀이 없다")
    img = mix_pipeline._template_layer({"frame": {"preset": "plain_black", "bar_h": 0,
                                                  "bg_image": ids[0]}})
    assert img and img.get("under_text") is True, "이미지 틀에 표시가 안 붙었다"
    plain = mix_pipeline._template_layer({"frame": {"preset": "sul_museun"}})
    assert plain and "under_text" not in plain, "기존 틀에 표시가 붙었다"
