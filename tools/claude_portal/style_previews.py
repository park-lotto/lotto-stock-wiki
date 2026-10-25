"""프리셋(판) 견본 그림 만들기(관제 266) — 판마다 실제 완성본에서 장면 3장(훅·가운데·뒤)을 뽑아 out/assets/style-previews/ 에 둔다.

  py tools/claude_portal/style_previews.py [--src "G:/내 드라이브/칼카피영상"] [--only 재미썸홈판]

왜: 판 틀(styles/*판.json frame)은 장면꾸미기 렌더러 꼴이 아니라 미리보기로 못 그린다. 틀 폴더가 없는 판을 다른 판 틀로
    대신 그렸더니 여러 프리셋이 같은 그림으로 보였다(10-25 사장님 '이상해'). 실제 완성본 장면이 가장 정확한 견본이다.
판 ↔ 완성본 폴더 짝 = 아래 SRC_DIRS 한 곳(구글 드라이브 칼카피영상 폴더 이름, 10-25 실측). 짝 없는 판은 견본을 만들지 않는다
    (화면은 '견본 준비 중' — 엉뚱한 그림을 보여주지 않는다).
고객에게 보이는 그림이므로 벤치 원본이 아니라 **우리 완성본**만 쓴다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "out" / "assets" / "style-previews"
DEFAULT_SRC = Path("G:/내 드라이브/칼카피영상")

# 판 파일 이름(확장자 뺀 것) → 완성본 폴더 이름 앞부분. 썰풀다(도파민썰템 A·B)는 어느 판 편인지 폴더로 못 갈라 비운다.
SRC_DIRS = {
    "썰템홈샷판": "1번 썰템홈샷", "샥탬판": "2번 샥템스토리", "숏템리폿판": "3번 숏템리폿", "썰템쇼판": "4번 썰템쇼",
    "만템판": "5번 얜샷템", "꿀템노트판": "6번 꿀템샷", "맛템썰템판": "6번 맛템썰템", "신박판": "신박리포트",
    "잇썸홈판": "잇썸홈", "잇템로그판": "잇템로그", "재미썸홈판": "재미썸홈", "트롯파파판": "트롯파파",
}
POINTS = (0.06, 0.45, 0.8)   # 훅(제목이 보이는 앞)·가운데·뒤 — 길이 비율


def _dur(mp4: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return float((r.stdout or "0").strip() or 0)


def build(src: Path, only: str | None = None) -> dict:
    from shopping_shorts.claude_studio import style_id
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    for stem, prefix in SRC_DIRS.items():
        if only and stem != only:
            continue
        dirs = sorted(d for d in src.iterdir() if d.is_dir() and d.name.startswith(prefix))
        vids = sorted(p for d in dirs for p in d.glob("*.mp4"))
        if not vids:
            print(f"  {stem}: 완성본 없음 — 건너뜀")
            continue
        mp4 = vids[0]
        dur = _dur(mp4)
        sid = style_id(stem)
        files = []
        for i, p in enumerate(POINTS, 1):
            dst = OUT / f"{sid}-{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.5, dur * p):.2f}", "-i", str(mp4), "-frames:v", "1",
                            "-vf", "scale=360:-2", "-q:v", "4", str(dst)], check=True, stdin=subprocess.DEVNULL)
            files.append(dst.name)
        # 샘플 영상 한 편(사장님 10-25 '샘플 영상 하나씩 재생 가능하게') — 540 폭·가볍게, 웹에서 바로 재생(faststart)
        vdst = OUT / f"{sid}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf", "scale=540:-2", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "30", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(vdst)], check=True, stdin=subprocess.DEVNULL)
        index[sid] = {"files": files, "video": vdst.name, "from": mp4.name}
        print(f"  {stem} → {sid}: {mp4.name} ({dur:.1f}초)")
    old = {}
    if (OUT / "index.json").is_file() and only:
        old = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    (OUT / "index.json").write_text(json.dumps({**old, **index}, ensure_ascii=False, indent=1), encoding="utf-8")
    return index


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--only")
    a = ap.parse_args()
    print(f"견본 {len(build(Path(a.src), a.only))}개 → {OUT}")
