"""실사풍 재연 그림 생성 (agy 구독 generate_image — 유료 API 아님).

참고 채널 원본의 정지 컷은 전부 생성형 실사풍 재연 그림이다(찰떡파이 편 41컷 중 7컷: 연구부장 빼돌림·도망, 판사 시식, 망한 대표).
실제 영상이 있을 수 없는 사건 장면에만 쓰고, 같은 인물은 같은 외모 설명을 붙여 2~4컷 이어 그린다.

  python aiimg.py <프로젝트> <이름> "<장면 설명(영문 권장)>" [참고그림경로]
  → media/ai/<이름>.jpg|.png   (참고그림을 주면 같은 인물·같은 장소로 그리게 함)

★그리기는 볼케이노 실행기의 agy 그림 부품(runner/cardnews_agyimage.generate) 하나로 한다(2026-10-22 · 전역 규칙 6-1).
  예전 판은 agy 를 셸 권한 우회 플래그(--dangerously-skip-permissions)로 불러 에이전트가 셸 명령을 쓸 수 있었다. 부품은 셸 권한 없이
  generate_image 하나만 시키고(참고그림 폴더만 --add-dir) · 이 PC 공용 agy 그림 줄 · 같은 지시·참고그림이면 그리지 않고 캐시 ·
  한도 글(429·QUOTA)이면 이 실행의 agy 요청을 모두 멈춘다(전역 6-2 · 자동 재시도 없음). 받은 바이트는 그림인지 끝까지 풀어 본다.
  아래 find_agy_runner 는 정본 volcano-mcp tools/agy_lookup.py 를 글자 그대로 복사한 것(tests/test_agy_lookup.py 가 대조) — 여기서 고치지 않는다.
"""
import json
import os
import sys

BASE = ("Photorealistic news-style photograph, natural lighting, wide landscape framing, "
        "absolutely no text, no letters, no numbers, no logos, no watermark. ")
ASPECT = "16:9"                 # BASE 의 «wide landscape framing» 과 같은 비율(agy generate_image 가 받는 7개 중 하나)
EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
#: agy 그림 요청 간격 표 — 볼케이노 사전 점검(sseol_seed)이 팩 뿌리에 적는다(서버 sseol.spec.AGY_IMAGE_PACING_FILE 과 같은 이름).
PACING_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agy_image_pacing.json")


def find_agy_runner(module="agy_transport_client"):
    """(실행기 폴더 Path, 모듈) — 실행기 agy 통로(와 그 위 부품 module)를 읽는다 · 못 찾으면 사유를 보이고 멈춘다 · 정본 volcano-mcp tools/agy_lookup.py · 글자 그대로 복사."""
    import importlib.util
    import os
    import sys
    from pathlib import Path
    folder = Path(os.environ.get("VOLCANO_RUNNER_DIR") or Path.home() / ".volcano" / "runner")
    names = ("agy_transport_codes", "agy_transport_proc", "agy_transport_refusal", "agy_transport_pc_env", "agy_transport_client")
    for name in names + tuple(n for n in (module,) if n not in names):
        if name in sys.modules:
            continue
        path = folder / f"{name}.py"
        if not path.is_file():
            raise SystemExit(f"볼케이노 실행기의 agy 부품이 없습니다: {path}\n"
                             "볼케이노 실행기(작업 폴더의 runner/volcano_drive.py)를 한 번 돌리면(사전 점검 단계) 이 자리에 설치됩니다. "
                             "그 뒤 같은 명령을 다시 실행하세요.")
        spec = importlib.util.spec_from_file_location(name, str(path))
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[name] = loaded
        try:
            spec.loader.exec_module(loaded)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return folder, sys.modules[module]


def main():
    proj, name, desc = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3]
    ref = os.path.abspath(sys.argv[4]) if len(sys.argv) > 4 else None
    out_dir = os.path.join(proj, "media", "ai"); os.makedirs(out_dir, exist_ok=True)
    prompt = ((f"Same person(s) and same place as the reference image. " if ref else "") + BASE + desc)
    try:
        with open(PACING_FILE, encoding="utf-8") as f:
            pacing = json.load(f)
    except (OSError, ValueError) as e:
        raise SystemExit(f"agy 그림 요청 간격 표를 못 읽었습니다({PACING_FILE}: {e}) — 볼케이노 sseol_seed(사전 점검)를 다시 부르면 "
                         "서버가 적어 줍니다. 간격 없이 보내지 않습니다.")
    _folder, image = find_agy_runner("cardnews_agyimage")
    model = sys.modules["agy_transport_pc_env"].agy_model()   # 팩의 agy 모델 한 자리(review.agy_model 과 같은 실행기 함수 · env INFO3D_AGY_MODEL 먼저)
    image.set_pacing(pacing)
    part = os.path.join(out_dir, name + ".part")
    try:
        image.generate(ref, prompt, ASPECT, name, part, model, out_dir)
    except image.AgyImageError as e:
        raise SystemExit(f"그림 생성 실패: {e}")
    except sys.modules["agy_transport_refusal"].RunServiceRefused as e:
        code = (getattr(e, "provider_result", None) or {}).get("code") or e.code
        raise SystemExit(f"agy 가 거부했다({code} — 한도·로그인·도구 거부). 이 실행의 agy 요청을 모두 멈췄다(자동 재시도 없음). "
                         "원인을 확인한 뒤(한도면 풀리는 시각 뒤) 같은 명령을 다시 한다.") from e
    from PIL import Image
    with Image.open(part) as im:
        ext = EXT.get(im.format, "." + str(im.format or "img").lower())
    out = os.path.join(out_dir, name + ext)
    os.replace(part, out); print(out)

if __name__ == "__main__":
    main()
