# -*- coding: utf-8 -*-
"""영상 관문이 서버에 올리고(PATCH_DIR) 도구가 얹는 **제작 라인 모듈 목록과 적재 방법의 정본**(2026-10-03 관제 085).

전에는 같은 목록이 6벌이었다 — video_gate.PATCH_RELS · gate_video.json watch_files · editor_vs_final_video ·
final_audio_audit · capcut_export_audit · clean_left_audit. 실측으로 이미 어긋나 있었다:
seg_snap 이 캡컷·자막남음 도구에 없고, clean_left_audit.py 가 감시 목록에 없고, 경로 되돌리기(_FONT_DIR·_ROOT)가
편집화면 대조 도구에만 있었다. 모듈 하나를 새로 만들면 여기 **한 곳**에만 적는다.

서버에서는 _tool/ 폴더에 도구와 함께 올라가고(video_gate.TOOL_RELS), 도구는 같은 폴더에서 import 한다.
"""
import importlib.util
import os
import sys
from pathlib import Path

# 얹는 순서 = import 의존 순서. config 가 맨 앞(video_assemble 이 config.MAX_SLOWMO 를 import 때 읽는다, 관제 020),
# 음성 라인이 mix_pipeline 앞(관제 049), 캡컷·내보내기는 맨 뒤.
# tts_timestamps 는 audio_post 뒤·tts 앞(자기는 audio_post 만 import, tts·video_assemble 이 이것을 부른다). 2026-10-04 관제 102 실측:
#   video_assemble._beat_timeline 이 새 함수 tts_timestamps.words_relative 를 부르는데 이 목록에 없어 서버의 옛 파일이 쓰였고,
#   병합본 작업 6개가 전부 AttributeError 로 건너뛰어 관문이 한 칸도 못 쟀다.
PATCH_MODULES = ("config", "voice_presets", "typecast_tts", "fish_tts", "audio_post", "tts_timestamps", "tts", "tts_joined",
                 "frame_match", "seg_snap", "screen_clips", "video_assemble", "clean_base", "mix_pipeline",
                 "export_bundle", "capcut_draft")

# 모듈 말고 같이 올릴 것: screen_clips 가 자기 옆(_HERE)의 러너·화면 코드를 부른다 / app 은 굽기 함수만 바꿔 끼운다.
PATCH_EXTRA = {
    "screen_clips_runner.js": "shopping_shorts/screen_clips_runner.js",
    "static/scene_play.js": "shopping_shorts/static/scene_play.js",
    "app.py": "shopping_shorts/app.py",
}

# 서버 PATCH_DIR 안의 자리 ← 저장소 경로
PATCH_RELS = dict([("%s.py" % n, "shopping_shorts/%s.py" % n) for n in PATCH_MODULES] + list(PATCH_EXTRA.items()))

# 서버 _tool/ 에 올리는 도구(병합본) — 이 파일도 도구들이 import 하므로 함께 간다.
TOOL_RELS = ("tools/editor_vs_final_video.py", "tools/evf_run.py", "tools/capcut_export_audit.py",
             "tools/final_audio_audit.py", "tools/clean_left_audit.py", "tools/gate_modules.py")

# 바뀌면 영상 관문을 돌리는 파일 — app.py 는 따로(함수 단위 판정, video_gate.app_change_decision).
WATCH_FILES = [rel for rel in PATCH_RELS.values() if rel != PATCH_EXTRA["app.py"]] + list(TOOL_RELS)

# PATCH_DIR 에서 얹으면 파일 위치 기준이 /tmp 를 가리키는 값 → 저장소 값으로 되돌린다(2026-09-27 실측:
# 폰트 폴더를 못 찾아 '폰트 미해결 — 자막·BGM 전부 스킵'으로 구워졌고, clean_base._ROOT 가 /tmp 를 가리켰다).
def _repo_path_overrides():
    pkg = Path("shopping_shorts").resolve()
    return (("_FONT_DIR", pkg / "static" / "fonts"),
            ("_BUNDLED_FONT", str(pkg / "assets" / "NanumGothic.ttf")),
            ("_ROOT", pkg.parent))


def load_patch_modules(pd=None):
    """PATCH_DIR(또는 pd)의 병합본 모듈을 shopping_shorts.<이름> 으로 먼저 얹는다(app 을 import 하기 전에).
    없으면 None. 저장소 폴더(cwd)에서 돈다고 가정한다 — 도구들이 모두 그렇다."""
    pd = pd or os.getenv("PATCH_DIR")
    if not pd:
        return None
    pdp = Path(pd)
    import shopping_shorts
    pd_res = str(pdp.resolve())
    for n in PATCH_MODULES:
        f = pdp / ("%s.py" % n)
        if not f.exists():
            continue
        sp = importlib.util.spec_from_file_location("shopping_shorts." + n, str(f))
        m = importlib.util.module_from_spec(sp)
        sys.modules["shopping_shorts." + n] = m
        sp.loader.exec_module(m)
        setattr(shopping_shorts, n, m)
        if n == "config":
            # config 를 얹으면 DB_PATH 등 파일 위치 기준 경로가 /tmp/gate_…/data 를 가리켜 DB 가 빈 것처럼 보인다
            # (2026-10-01 관문 실측: 6작업 전부 '데이터 없음') → 경로 상수는 저장소 config 값으로.
            rs = importlib.util.spec_from_file_location("_repo_config", str(Path("shopping_shorts/config.py").resolve()))
            rc = importlib.util.module_from_spec(rs)
            rs.loader.exec_module(rc)
            for k in dir(m):
                v = getattr(m, k)
                if isinstance(v, Path) and str(v.resolve()).startswith(pd_res) and hasattr(rc, k):
                    setattr(m, k, getattr(rc, k))
        for attr, val in _repo_path_overrides():
            if hasattr(m, attr):
                setattr(m, attr, val)
    return pdp
