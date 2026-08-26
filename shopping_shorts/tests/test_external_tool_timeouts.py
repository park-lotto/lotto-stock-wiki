# -*- coding: utf-8 -*-
"""외부 도구 호출에 상한이 걸려 있는지 (2026-08-23 점검).

★왜 필요한가: node(remotion)·ffmpeg 호출에 timeout이 없으면, 그 프로세스가
   멈췄을 때 호출한 스레드가 **영원히** 붙잡힌다. 렌더 워커는 개수가 정해져
   있어서 하나가 물리면 뒤 작업이 통째로 굶는다 — 고객 눈에는 "제작이 안 끝남"
   으로만 보이고 아무 에러도 안 뜬다.

★값은 config 한 곳에서만 정한다(0순위-B). 파일마다 숫자를 박으면 어긋난다.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]

# (파일, 그 파일에서 상한이 꼭 필요한 호출의 표식)
GUARDED = [
    ("remotion_render.py", "render-scene.mjs"),     # node 렌더 — 제일 길다
    ("scene_cut.py", "showinfo"),                   # 장면 경계 검출
    ("scene_assets.py", "ffmpeg 구간컷 실패"),        # 클립 컷
    ("frame_extract.py", "ffmpeg 프레임 추출 실패"),   # 프레임 추출
]


def _text(name):
    return (SRC / name).read_text(encoding="utf-8")


def test_config_defines_timeouts_in_one_place():
    """상한 값은 config에만 있어야 한다."""
    from shopping_shorts import config
    for attr in ("FFMPEG_TIMEOUT_SEC", "MEDIA_CLIP_TIMEOUT_SEC", "REMOTION_TIMEOUT_SEC"):
        v = getattr(config, attr, None)
        assert isinstance(v, int) and v > 0, f"config.{attr}가 없거나 값이 이상하다: {v!r}"


def test_every_long_running_call_has_a_timeout():
    """★표식이 있는 파일의 subprocess.run에 timeout이 붙어 있어야 한다."""
    missing = []
    for name, marker in GUARDED:
        t = _text(name)
        assert marker in t, f"{name}: 표식({marker})이 사라졌다 — 이 테스트를 고쳐라"
        for m in re.finditer(r"subprocess\.run\(", t):
            # 호출 한 덩이(다음 닫는 괄호까지 대략)를 본다
            chunk = t[m.start(): m.start() + 700]
            head = chunk.split("\n\n")[0]
            if "timeout=" not in head:
                line = t[: m.start()].count("\n") + 1
                missing.append(f"{name}:{line}")
    assert not missing, "상한 없는 외부 호출: %s" % missing


def test_timeouts_use_config_not_literals():
    """숫자를 직접 박으면 값이 흩어진다 — config를 참조해야 한다."""
    for name, _ in GUARDED:
        t = _text(name)
        for m in re.finditer(r"timeout=([^,\)\s]+)", t):
            val = m.group(1)
            assert not val.isdigit(), (
                f"{name}: timeout에 숫자 리터럴({val})이 박혔다 — config 상수를 써라")


def test_remotion_timeout_is_longer_than_clip_timeout():
    """렌더는 클립 처리보다 훨씬 오래 걸린다 — 상한이 뒤집히면 정상 렌더가 잘린다."""
    from shopping_shorts import config
    assert config.REMOTION_TIMEOUT_SEC > config.MEDIA_CLIP_TIMEOUT_SEC
    assert config.MEDIA_CLIP_TIMEOUT_SEC > config.FFMPEG_TIMEOUT_SEC
