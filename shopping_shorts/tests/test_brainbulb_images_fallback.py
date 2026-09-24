# -*- coding: utf-8 -*-
"""이미지 생성 거부 대응 — 한 슬롯이 막혀도 편 전체가 멈추지 않는다.

실측 2026-09-12(테이저건 편): 미성년자 + 무기가 한 장면에 있으면 gpt-image-2가 `failed`로 거부한다.
슬롯 4개가 거부됐고, 순화 재시도로 전부 살아났다.
"""
from PIL import Image

from shopping_shorts.brainbulb import images, frames, spec


def _png(path, size=(64, 64), color=(1, 2, 3)):
    Image.new("RGB", size, color).save(path)


def test_soften_retry_saves_refused_slot(tmp_path):
    seen = []

    def gen(prompt, out):
        seen.append(prompt)
        if "no weapons in frame" not in prompt:
            raise RuntimeError("evolink: 생성 실패 failed")
        _png(out)

    out = images.generate_all({"1": spec.IMAGE_PROMPT_PREFIX + "a police officer aiming a taser at students"},
                              str(tmp_path), gen, log=lambda *a: None)
    assert "1" in out and len(seen) == 2                    # 원본 1회 + 순화 1회
    assert "no weapons in frame" in seen[1]


def test_hard_failure_skips_only_that_slot(tmp_path):
    def gen(prompt, out):
        if "2" in prompt:
            raise RuntimeError("evolink: 생성 실패 failed")
        _png(out)

    out = images.generate_all({"1": "slot 1 scene", "2": "slot 2 scene", "3": "slot 3 scene"},
                              str(tmp_path), gen, log=lambda *a: None)
    assert set(out) == {"1", "3"}                            # 2번만 빠지고 나머지는 산다


def test_frames_fills_missing_slot_with_nearest(tmp_path):
    a = tmp_path / "01.png"; _png(a, (600, 400), (255, 0, 0))
    c = tmp_path / "03.png"; _png(c, (600, 400), (0, 0, 255))
    imgs = {"1": str(a), "3": str(c)}
    assert frames._nearest(imgs, 2) in (str(a), str(c))       # 빈 2번은 이웃으로 메운다
    assert frames._nearest(imgs, 1) == str(a)
    assert frames._nearest(imgs, 9) == str(c)
    assert frames._nearest({}, 1) is None
