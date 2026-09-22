"""subprocess에 text=True만 주고 encoding을 안 정한 곳을 찾는다 — 한글 경로 함정 전수 검사.

★왜 도구로 남기나(2026-09-22): ffmpeg/ffprobe는 stderr를 UTF-8로 내는데 text=True만 주면
파이썬이 로캘(윈도우=cp949)로 디코드하다 리더 스레드에서 UnicodeDecodeError로 죽는다.
이 저장소는 경로에 '로또의 주식'이 들어가 **항상** 밟는다. 그런데 대부분의 호출부가
`except Exception: return []` 꼴이라 예외가 조용히 삼켜지고 "결과가 없다"로 둔갑한다.

실제 사고: audio_post.detect_silences/detect_edge_silence가 한글 경로에서 늘 []/0.0을
반환했다 — 무음이 없어서가 아니라 **재지도 못하고** 0이었다. video_assemble은 2026-07-16에
같은 함정을 고쳤지만(_FF_TEXT) audio_post는 그 수정을 못 받았다(0순위-B).

쓰기:  py tools/audit_subprocess_encoding.py            (0=깨끗, 1=결함 있음)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".tracks", "node_modules", "__pycache__", "venv", ".venv"}


def _calls(src):
    """subprocess.run/check_output/Popen 호출을 (시작줄, 인자문자열)로 잘라낸다."""
    for m in re.finditer(r"subprocess\.(?:run|check_output|Popen)\s*\(", src):
        i = m.end()
        depth, j = 1, i
        while j < len(src) and depth:
            if src[j] == "(":
                depth += 1
            elif src[j] == ")":
                depth -= 1
            j += 1
        yield src[:m.start()].count("\n") + 1, src[i:j]


def scan(root=ROOT):
    bad = []
    for f in root.rglob("*.py"):
        if any(p in SKIP_DIRS for p in f.parts):
            continue
        if "tests" in f.parts or f.name == Path(__file__).name:
            continue
        try:
            src = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for line, call in _calls(src):
            # text=True(또는 universal_newlines=True)인데 encoding을 안 정했다 → 로캘로 디코드
            texty = "text=True" in call or "universal_newlines=True" in call
            if texty and "encoding" not in call:
                bad.append((f.relative_to(root).as_posix(), line))
    return bad


if __name__ == "__main__":
    # ★이 도구 자신도 한글을 내보낸다 — 콘솔이 cp949면 출력하다 죽는다(이 파일이 잡으려는
    #   함정과 같은 뿌리다). 표준출력을 UTF-8로 못박아 어디서 돌려도 결과가 보이게 한다.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    bad = scan()
    if not bad:
        print("OK - text=True인데 encoding 없는 subprocess 호출: 0건")
        sys.exit(0)
    print(f"결함 {len(bad)}건 - ffmpeg 출력이 한글이면 UnicodeDecodeError로 조용히 죽는다:")
    for path, line in bad:
        print(f"  {path}:{line}")
    print('고치는 법: capture_output/text 대신 encoding="utf-8", errors="replace"를 같이 준다')
    sys.exit(1)
