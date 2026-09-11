# -*- coding: utf-8 -*-
"""2단계(사진·밈·프레임) — 가짜 이미지로 프레임 조립과 이미지 단계 재사용을 검사한다. EvoLink는 부르지 않는다."""
import json
import re
import shutil
from pathlib import Path

import pytest
from PIL import Image

from shopping_shorts.brainbulb import frames, images, spec, timing as tmod, pipeline

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _png(path, size, color):
    Image.new("RGB", size, color).save(path)


def test_compose_places_photo_in_slot_and_meme_by_height(tmp_path):
    photo = tmp_path / "p.png"; _png(photo, (1248, 832), (200, 30, 30))
    meme = tmp_path / "m.png"; Image.new("RGBA", (231, 218), (30, 200, 30, 255)).save(meme)
    out1 = frames.compose(str(photo), str(tmp_path / "a.jpg"))
    im = Image.open(out1); assert im.size == (spec.CANVAS_W, spec.CANVAS_H)
    # 슬롯 안은 사진색, 슬롯 밖(제목 영역·자막 영역)은 검정
    assert im.getpixel((spec.SLOT_X + 10, spec.SLOT_Y + 10))[0] > 150
    assert im.getpixel((540, 200)) == (0, 0, 0) and im.getpixel((540, 1400)) == (0, 0, 0)
    assert im.getpixel((spec.SLOT_X - 5, spec.SLOT_Y + 100)) == (0, 0, 0)
    out2 = frames.compose(str(meme), str(tmp_path / "b.jpg"), kind="meme")
    im2 = Image.open(out2)
    # 밈은 슬롯 높이에 맞춰 가운데: 슬롯 좌우 끝은 검정, 가운데는 밈색
    assert im2.getpixel((540, spec.SLOT_Y + spec.SLOT_H // 2))[1] > 150
    assert im2.getpixel((spec.SLOT_X + 5, spec.SLOT_Y + 100)) == (0, 0, 0)


def test_frames_build_timeline_sums_to_total_and_uses_memes(tmp_path):
    meme_dir = tmp_path / "pepe"; meme_dir.mkdir()
    for n in ("013", "008"):
        Image.new("RGBA", (300, 300), (0, 0, 255, 255)).save(meme_dir / f"{n}.png")
    img = tmp_path / "01.png"; _png(img, (600, 400), (255, 255, 255))
    groups = [{"text": "하나", "color": "WHITE", "role": "NARR", "img": 1},
              {"text": "둘", "color": "RED", "role": "CHAR", "meme": "경악/충격"},
              {"text": "셋", "color": "RED", "role": "PUNCH", "meme": "무표정/멍"}]
    t = tmod.build(1.0, [1.0, 0.8, 1.2], groups)
    r = frames.build(str(tmp_path), t, {"groups": groups}, {"1": str(img)}, meme_dir=str(meme_dir))
    kinds = [x["kind"] for x in r["timeline"]]
    assert kinds == ["card", "img", "meme", "meme"]
    assert all(x["src"] for x in r["timeline"])                       # 카드는 슬롯1 사진, 밈 둘 다 파일 매핑됨
    s = open(r["list"], encoding="utf-8").read()
    durs = [float(x) for x in re.findall(r"duration ([\d.]+)", s)]
    assert abs(sum(durs) - t["total"]) < 1e-6


def test_generate_all_reuses_same_prompt(tmp_path):
    calls = []
    def gen(prompt, out):
        calls.append(prompt); _png(out, (64, 64), (1, 2, 3))
    p = {"1": "a", "2": "b"}
    images.generate_all(p, str(tmp_path), gen, log=lambda *a: None)
    images.generate_all(p, str(tmp_path), gen, log=lambda *a: None)          # 같은 프롬프트 → 재생성 없음
    assert len(calls) == 2
    images.generate_all({"1": "a", "2": "b2"}, str(tmp_path), gen, log=lambda *a: None)
    assert calls[-1] == "b2" and len(calls) == 3


def test_make_prompts_prepends_cast_when_keys_are_names():
    script = {"groups": [{"text": "x", "color": "WHITE", "role": "NARR", "img": 1}, {"text": "y", "color": "WHITE", "role": "NARR", "img": 2}]}
    raw = json.dumps({"cast": {"protagonist": "a Korean man in his 50s"}, "prompts": {"1": "the protagonist on a plane", "2": "the protagonist in a studio"}})
    r = images.make_prompts(script, "소재", lambda _: raw, log=lambda *a: None)
    assert all("a Korean man in his 50s" in v for v in r["prompts"].values())
    assert all(v.startswith(spec.IMAGE_PROMPT_PREFIX) for v in r["prompts"].values())


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")
def test_pipeline_with_fake_images_and_memes_renders(tmp_path):
    import subprocess
    meme_dir = tmp_path / "pepe"; meme_dir.mkdir()
    Image.new("RGBA", (300, 300), (0, 0, 255, 255)).save(meme_dir / "013.png")
    s = {"title": {"h1": "제목 하나", "h2": "숫자 2개 들어간 둘째", "card": "오프닝 카드 문장은 이렇게 한 문장으로 간다"},
         "groups": [{"text": "첫 컷은 끝내지 않고", "color": "WHITE", "role": "NARR", "img": 1},
                    {"text": "둘째 컷이다", "color": "WHITE", "role": "NARR", "img": 1},
                    {"text": "진짜 대단하다", "color": "RED", "role": "CHAR", "meme": "경악/충격"},
                    {"text": "끝났다", "color": "RED", "role": "PUNCH", "meme": "경악/충격"}]}
    def tts(text, out):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={0.4 + 0.07 * len(text):.3f}",
                        "-ar", "44100", "-ac", "2", out], check=True, stdin=subprocess.DEVNULL)
    def gen(prompt, out): _png(out, (1248, 832), (120, 120, 200))
    llm_calls = []
    def llm(p):
        llm_calls.append(p)
        if "이미지 디렉터" in p:
            return json.dumps({"cast": {"1": "a man"}, "prompts": {"1": "a man on a plane"}})
        return json.dumps(s, ensure_ascii=False)
    r = pipeline.run_all(str(tmp_path / "job"), source_text="소재", llm=llm, tts=tts, imagegen=gen, meme_dir=str(meme_dir), log=lambda *a: None)
    assert r["status"] == "ok", r
    d = pipeline.load(str(tmp_path / "job"))["data"]
    assert d["images"]["files"]["1"].endswith("01.png")
    assert [x["kind"] for x in d["frames"]["timeline"]] == ["card", "img", "img", "meme", "meme"]
    assert d["review"]["ok"], d["review"]
