"""🎬 '이 장면에만' 가림막(2026-09-10 사장님 "장면에만 하는걸 만들고 오류없이 되게").

★계약 셋:
  1) 장면 지정이 **없는** 가림막은 지금까지와 한 글자도 다르지 않다(캐시키·그림·ffmpeg 명령).
  2) 장면 지정이 있으면 틀 그림(영상 전체)에서 빠지고, 그 장면 시간에만 따로 얹힌다.
  3) 장면 시각은 미리보기 장면 목록과 **같은 함수**(final_clip_pairs)에서 온다.
"""
import shutil
import subprocess

import pytest

from shopping_shorts import deco_frame, mix_pipeline, video_assemble

RED = {"l": 0, "t": 0, "w": 100, "h": 100, "shape": "rect", "fx": "solid",
       "color": "#FF0000", "op": 100, "soft": 0, "rot": 0}


def _spec(masks):
    return {"preset": "plain_black", "bar_h": 0, "bottom_h": 0, "masks": masks}


# ── 1) 옛 동작 무변경 ────────────────────────────────────────────────────────
def test_장면지정_없으면_정규화결과에_키가_안붙는다():
    out = deco_frame._norm_masks([RED])
    assert "beat" not in out[0] and "cut" not in out[0]


def test_장면지정_없으면_split이_원본을_그대로():
    sp = _spec([RED])
    g, scenes = deco_frame.split_scene_masks(sp)
    assert g is sp and scenes == {}


def test_장면지정_없으면_캐시키가_같다():
    sp = _spec([RED])
    g, _ = deco_frame.split_scene_masks(sp)
    assert deco_frame.cache_key(g) == deco_frame.cache_key(sp)


def test_장면지정_없으면_장면레이어가_없다():
    assert mix_pipeline._scene_mask_layers({"frame": _spec([RED])}, {}, {}, {}) == []


# ── 2) 가르기 ────────────────────────────────────────────────────────────────
def test_정규화가_beat_cut을_보존한다():
    out = deco_frame._norm_masks([dict(RED, beat=3, cut=1), dict(RED, beat="2"),
                                  dict(RED, beat=-1), dict(RED, beat="x"), dict(RED, beat=True)])
    assert (out[0]["beat"], out[0]["cut"]) == (3, 1)
    assert (out[1]["beat"], out[1]["cut"]) == (2, None)
    for m in out[2:]:
        assert "beat" not in m, "이상한 장면 번호는 전체 장면으로 물러선다"


def test_split이_전체와_장면을_가른다():
    g, scenes = deco_frame.split_scene_masks(
        _spec([RED, dict(RED, beat=1, cut=0), dict(RED, beat=1, cut=0, l=10, w=10), dict(RED, beat=2)]))
    assert len(g["masks"]) == 1 and "beat" not in g["masks"][0]
    assert set(scenes) == {(1, 0), (2, None)}
    assert len(scenes[(1, 0)]) == 2


def test_전체틀그림엔_장면전용이_안그려진다():
    g, _ = deco_frame.split_scene_masks(_spec([dict(RED, beat=0)]))
    im = deco_frame.render(g)
    assert im.getpixel((540, 960))[:3] != (255, 0, 0)


def test_장면그림은_투명바탕에_막만():
    p = deco_frame.render_scene_masks_to([dict(RED, l=0, t=0, w=50, h=50, beat=0)])
    from PIL import Image
    im = Image.open(p)
    assert im.getpixel((100, 100)) == (255, 0, 0, 255)
    assert im.getpixel((1000, 1800))[3] == 0


def test_흐림만_있으면_색그림은_없다():
    assert deco_frame.render_scene_masks_to([dict(RED, fx="blur", beat=0)]) is None


# ── 3) 시간 창 ───────────────────────────────────────────────────────────────
def _fake_cuts(monkeypatch):
    cuts = [{"beat_idx": 0, "fin": 0.0, "dur": 1.0}, {"beat_idx": 1, "fin": 1.0, "dur": 0.5},
            {"beat_idx": 1, "fin": 1.5, "dur": 0.7}, {"beat_idx": 2, "fin": 2.2, "dur": 1.0}]
    monkeypatch.setattr(mix_pipeline, "final_clip_pairs", lambda *a, **k: cuts)


def test_컷지정이면_그_컷시간만(monkeypatch):
    _fake_cuts(monkeypatch)
    lay = mix_pipeline._scene_mask_layers({"frame": _spec([dict(RED, beat=1, cut=1)])}, {}, {}, {})
    assert len(lay) == 1
    assert lay[0]["start"] == pytest.approx(1.5) and lay[0]["dur"] == pytest.approx(0.7)


def test_컷없으면_칸전체(monkeypatch):
    _fake_cuts(monkeypatch)
    lay = mix_pipeline._scene_mask_layers({"frame": _spec([dict(RED, beat=1)])}, {}, {}, {})
    assert lay[0]["start"] == pytest.approx(1.0) and lay[0]["dur"] == pytest.approx(1.2)


def test_없는_장면이면_안얹는다(monkeypatch):
    _fake_cuts(monkeypatch)
    lay = mix_pipeline._scene_mask_layers({"frame": _spec([dict(RED, beat=9), dict(RED, beat=1, cut=5)])},
                                          {}, {}, {})
    assert lay == []


def test_흐림은_마스크로_실린다(monkeypatch):
    _fake_cuts(monkeypatch)
    lay = mix_pipeline._scene_mask_layers({"frame": _spec([dict(RED, fx="blur", soft=50, beat=0)])},
                                          {}, {}, {})
    assert lay and lay[0].get("blur_mask") and lay[0]["blur_sigma"] > 0 and "_abspath" not in lay[0]


def test_template_layer는_장면전용을_틀에서_뺀다():
    both = mix_pipeline._template_layer({"frame": _spec([RED, dict(RED, beat=0, l=10, w=10)])})
    only = mix_pipeline._template_layer({"frame": _spec([RED])})
    assert both["id"] == only["id"], "틀 그림은 전체 가림막만으로 정해져야 한다"


# ── 4) 굽기(ffmpeg 명령) ────────────────────────────────────────────────────
def _cmd(deco, tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(video_assemble, "_run_ffmpeg", lambda cmd, cwd=None: seen.setdefault("cmd", cmd))
    monkeypatch.setattr(video_assemble, "_resolve_font", lambda *a, **k: str(tmp_path / "f.ttf"))
    monkeypatch.setattr(video_assemble, "_probe_duration", lambda *a, **k: 3.0)
    monkeypatch.setattr(video_assemble, "shutil", type("S", (), {"copyfile": staticmethod(lambda *a: None),
                                                                 "copy": staticmethod(lambda *a: None)}))
    plan = {"beats": [{"beat_idx": 0, "role": "hook", "narration": "훅"}]}
    video_assemble._burn_captions("in.mp4", plan, {0: "a.mp3"}, str(tmp_path / "o.mp4"),
                                  tmp_path, headcopy=None, caption_style=None, deco=deco)
    return seen["cmd"]


def test_장면가림막_없으면_명령이_종전과_같다(tmp_path, monkeypatch):
    a = _cmd({}, tmp_path, monkeypatch)
    b = _cmd({"scene_masks": []}, tmp_path, monkeypatch)
    assert a == b and "-vf" in a


def test_장면가림막은_enable창으로_얹힌다(tmp_path, monkeypatch):
    png = deco_frame.render_scene_masks_to([dict(RED, beat=0)])
    cmd = _cmd({"scene_masks": [{"_abspath": str(png), "start": 1.0, "dur": 0.5}]}, tmp_path, monkeypatch)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "enable='between(t,1.000,1.500)'" in fc
    assert str(png) in cmd


# ── 5) 진짜 ffmpeg로 구워서 픽셀을 본다 ────────────────────────────────────
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_실제로_그_구간에만_덮인다(tmp_path):
    src = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=3:r=30",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
    png = deco_frame.render_scene_masks_to([dict(RED, beat=0)])
    work = tmp_path / "w"
    work.mkdir()
    plan = {"beats": [{"beat_idx": 0, "role": "hook", "narration": ""}]}
    out = tmp_path / "out.mp4"
    tts = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "3", str(tts)], check=True)
    video_assemble._burn_captions(str(src), plan, {0: str(tts)}, str(out), work, headcopy=None,
                                  caption_style=None,
                                  deco={"scene_masks": [{"_abspath": str(png), "start": 1.0, "dur": 1.0}]})

    def px(t):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1",
                              "-vf", "crop=2:2:540:960,format=rgb24", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        return tuple(raw[:3])

    before, during, after = px(0.5), px(1.5), px(2.6)
    assert before[2] > 150 and before[0] < 80, f"장면 전엔 원래 파랑이어야: {before}"
    assert during[0] > 150 and during[2] < 80, f"그 장면엔 빨강으로 덮여야: {during}"
    assert after[2] > 150 and after[0] < 80, f"장면 뒤엔 다시 파랑: {after}"
