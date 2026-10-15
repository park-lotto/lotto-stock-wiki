# -*- coding: utf-8 -*-
"""숏템 컨셉 스튜디오 설치팩(.mcpb) 만들기 — Claude 데스크톱 원클릭 설치용(관제 213).

  py tools/concept_studio/build_mcpb.py            → dist/shottem-studio.mcpb

담는 것: 엔진(channelkit·인물형) + 컨셉 스튜디오(core·MCP) + 글꼴 + 얼굴·글자 인식 모델.
안 담는 것: 파이썬·패키지(uv 가 pyproject.toml 로 고객 PC에 깐다), ffmpeg(static-ffmpeg 가 첫 실행에 받는다),
            효과음·배경음·짤(웹 컨셉 스튜디오에서 studio_sync 로 받는다 — 계정별 설정과 짝).
★엔진은 아직 트랙 `칼카피숏템엔진`에만 있다 → ENGINE 폴더에서 복사한다(병합 뒤엔 같은 저장소).
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
ENGINE = os.environ.get("SHOTTEM_ENGINE_ROOT") or os.path.normpath(os.path.join(REPO, "..", "칼카피숏템엔진"))
MODELS = os.environ.get("SHORTEM_MODELS") or os.path.join(os.path.expanduser("~"), ".shortem", "models")
OUT = os.path.join(REPO, "dist")
STAGE = os.path.join(OUT, "shottem-studio")
VERSION = "0.1.0"

# 엔진 쪽에서 가져올 것(엔진이 실제로 import 하는 범위 — 2026-10-15 import 실측: 41모듈)
ENGINE_PARTS = ["shopping_shorts/channelkit", "shopping_shorts/channel_presets/__init__.py",
                "shopping_shorts/channel_presets/brainbulb", "shopping_shorts/channel_presets/hotpeople",
                "shopping_shorts/config.py", "shopping_shorts/typecast_tts.py"]
FONTS = ["BMJUA.ttf", "NanumGothic-Bold.ttf"]          # 인물형이 쓰는 글꼴(spec.SUB_FONT·LOGO_NAME_FONT)
MODEL_FILES = ["face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx", "ppocrv5_server_det.onnx"]

DEPS = ["mcp>=2.3,<3", "google-genai", "pillow", "numpy", "opencv-python-headless>=4.10",
        "onnxruntime", "requests", "python-dotenv", "brotli", "yt-dlp", "static-ffmpeg", "pywin32; sys_platform == 'win32'"]

MAIN = r'''# -*- coding: utf-8 -*-
"""설치팩 시작점 — 경로·도구를 잡고 MCP 서버를 띄운다."""
import os, sys
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(B, "src"))
os.environ.setdefault("SHOTTEM_ENGINE_ROOT", os.path.join(B, "src"))
os.environ.setdefault("SHORTEM_MODELS", os.path.join(B, "models"))
os.environ["PYTHONPATH"] = os.path.join(B, "src") + os.pathsep + os.environ.get("PYTHONPATH", "")
os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")   # yt-dlp.exe
try:
    import static_ffmpeg
    static_ffmpeg.add_paths(weak=True)      # PC 에 ffmpeg 가 있으면 그걸, 없으면 처음 한 번 받는다
except Exception as e:  # noqa: BLE001
    print("[shottem] ffmpeg 준비 실패:", e, file=sys.stderr)
for k in [k for k in os.environ if k.startswith("SHOTTEM_") and not os.environ[k].strip()]:
    del os.environ[k]                       # 설정 칸을 비워 두면 빈 값이 온다 → 없는 것으로
from shopping_shorts.concept_studio.mcp_server import mcp
mcp.run()
'''


def _copy(rel, src_root, dst_root):
    s, d = os.path.join(src_root, rel), os.path.join(dst_root, rel)
    if os.path.isdir(s):
        shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "bench", "baselines"),
                        dirs_exist_ok=True)
    else:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)


def build():
    if not os.path.isdir(os.path.join(ENGINE, "shopping_shorts", "channelkit")):
        sys.exit(f"엔진 폴더가 없다: {ENGINE}")
    shutil.rmtree(STAGE, ignore_errors=True)
    src = os.path.join(STAGE, "src")
    os.makedirs(os.path.join(src, "shopping_shorts"))
    open(os.path.join(src, "shopping_shorts", "__init__.py"), "w").close()
    for p in ENGINE_PARTS:
        _copy(p, ENGINE, src)
    _copy("shopping_shorts/concept_studio", REPO, src)
    os.remove(os.path.join(src, "shopping_shorts", "concept_studio", "server_api.py"))   # 서버 전용
    for f in FONTS:
        _copy(f"shopping_shorts/static/fonts/{f}", ENGINE, src)
    os.makedirs(os.path.join(STAGE, "models"))
    for m in MODEL_FILES:
        p = os.path.join(MODELS, m)
        if not os.path.isfile(p):
            sys.exit(f"모델이 없다: {p}")
        shutil.copy2(p, os.path.join(STAGE, "models", m))
    os.makedirs(os.path.join(STAGE, "server"))
    with open(os.path.join(STAGE, "server", "main.py"), "w", encoding="utf-8") as fh:
        fh.write(MAIN)
    with open(os.path.join(STAGE, "pyproject.toml"), "w", encoding="utf-8") as fh:
        fh.write('[project]\nname = "shottem-studio"\nversion = "%s"\nrequires-python = ">=3.11"\ndependencies = [\n%s\n]\n'
                 % (VERSION, ",\n".join(f'  "{d}"' for d in DEPS)))
    manifest = {
        "manifest_version": "0.4", "name": "shottem-studio", "display_name": "숏템 컨셉 스튜디오",
        "version": VERSION, "author": {"name": "숏템메이커"},
        "description": "웹 컨셉 스튜디오에 저장한 컨셉·팩대로 내 PC에서 숏폼을 만든다.",
        "long_description": "Claude 에게 '스튜디오 설정대로 OO 만들어줘'라고 말하면 대본(내 Claude)·소재·렌더(내 PC)까지 진행한다. 사람 확인은 대본 1회.",
        "server": {"type": "uv", "entry_point": "server/main.py",
                   "mcp_config": {"command": "uv", "args": ["run", "--directory", "${__dirname}", "server/main.py"],
                                  "env": {"SHOTTEM_STUDIO_URL": "${user_config.studio_url}",
                                          "SHOTTEM_STUDIO_TOKEN": "${user_config.studio_token}",
                                          "GEMINI_API_KEY": "${user_config.gemini_api_key}",
                                          "TYPECAST_API_KEY": "${user_config.typecast_api_key}",
                                          "PYTHONUTF8": "1"}}},
        "user_config": {
            "studio_url": {"type": "string", "title": "스튜디오 주소", "description": "숏템메이커 주소",
                           "default": "https://shoppingshorts.duckdns.org", "required": True},
            "studio_token": {"type": "string", "title": "연결 코드", "sensitive": True, "required": True,
                             "description": "웹 컨셉 스튜디오 → '설치팩 연결 코드 받기'에서 받은 코드"},
            "gemini_api_key": {"type": "string", "title": "제미니 API 키", "sensitive": True, "required": True,
                               "description": "장면 고르기·검사에 쓴다(구글 AI 스튜디오에서 발급)"},
            "typecast_api_key": {"type": "string", "title": "타입캐스트 키(선택)", "sensitive": True, "required": False,
                                 "description": "목소리가 들어가는 컨셉에서만 쓴다"}},
        "tools": [{"name": n, "description": d} for n, d in [
            ("studio_make", "한 번에: 설정·팩 받기 → 시작 → 대본 요청까지"),
            ("studio_sync", "웹 스튜디오의 컨셉·내 설정·팩 받기"), ("studio_concepts", "컨셉 목록"),
            ("studio_start", "작업 시작"), ("studio_status", "작업 상태"), ("studio_submit_script", "대본 넣기"),
            ("studio_confirm", "대본 확인"), ("studio_resume", "멈춘 작업 이어 돌리기")]],
        "compatibility": {"platforms": ["win32", "darwin"], "runtimes": {"python": ">=3.11"}},
        "license": "Proprietary"}
    with open(os.path.join(STAGE, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    out = os.path.join(OUT, "shottem-studio.mcpb")
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    r = subprocess.run([npx, "-y", "@anthropic-ai/mcpb", "validate", os.path.join(STAGE, "manifest.json")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip()[-400:], r.stderr.strip()[-400:])
    if r.returncode:
        sys.exit("매니페스트 검사 실패")
    r = subprocess.run([npx, "-y", "@anthropic-ai/mcpb", "pack", STAGE, out],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip()[-800:], r.stderr.strip()[-400:])
    if r.returncode:
        sys.exit("묶기 실패")
    print("→", out, f"{os.path.getsize(out) / 1e6:.1f}MB")


if __name__ == "__main__":
    build()
