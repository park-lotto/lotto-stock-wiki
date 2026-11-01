# -*- coding: utf-8 -*-
"""칼카피 1차 분석 — 채널 조회 상위 50편을 편마다 통째로 판독한다 (관제 097, 2026-10-15 사장님 "상위 50편 1차").

    PYTHONUTF8=1 py tools/calcopy/analyze50.py C:/숏템_칼카피/sseolpulda [--only judge|bench|asr]

입력: <폴더>/mp4/*.mp4, <폴더>/top50.json(id·views·title)
출력: judge/<id>.json(제미니 영상 판독: 갈래·박자·대본·말투·화면 틀·효과·효과음)
      bench_main/(channelkit.bench 숫자 자) · asr/<id>.json(스피치매틱스)
판독은 사람 판정을 대신하지 않는다 — 숫자 자(bench·asr)와 맞춰 보는 재료다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PROMPT = """너는 한국어 유튜브 쇼츠를 칼같이 복제하려는 편집자다. 이 영상(소리 포함)을 처음부터 끝까지 보고 아래 JSON만 출력하라.
시각은 초(소수 1자리). 보이지/들리지 않은 것은 지어내지 말고 null·빈 목록.
{
 "style": "이 영상 형식의 짧은 갈래 이름(예: 제품 이야기썰형, 역할극형, 뉴스 해설형 …)",
 "style_why": "그 갈래로 본 근거 한 줄",
 "voice": {"narration": true/false, "kind": "TTS|사람|없음", "gender": "남|여|섞임|없음", "roles": ["나레", "사장" …], "speed": "느림|보통|빠름"},
 "hook": {"text": "첫 문장(들리는 그대로)", "t_end": 0.0, "why": "왜 손을 멈추게 하나"},
 "beats": [{"t0":0.0,"t1":0.0,"fn":"훅|상황|의문|정체공개|원리|반전|덤|결말|댓글유도|기타","text":"그 구간 말 요약"}],
 "script": "들리는 나레이션·대사 전문(화자 바뀌면 '사장: …' 처럼 표시)",
 "tone": {"ending": ["자주 쓴 문장 끝 꼴 3개"], "honorific": "반말|존댓말|섞임", "person": "1인칭|3인칭|섞임", "slang": ["ㄷㄷ 같은 표현"]},
 "frame": {"bg": "배경 설명/색", "title_band": "제목 띠 위치·색·글자색", "video_box": "영상 창 위치·크기 비율", "logo": "로고/채널명 위치", "other": "고정 요소"},
 "subtitle": {"pos": "위치", "lines": 1, "color": "글자색", "outline": "외곽선/그림자", "highlight": "강조 방식(색·박스 등)", "appear": "등장 방식(팝·타자·그냥)", "matches_voice": true},
 "effects": [{"t":0.0,"kind":"zoom|shake|flash|transition|sticker|meme|emoji|arrow|bubble|text_pop|split|other","desc":"무엇이 어떻게"}],
 "sfx": [{"t":0.0,"desc":"효과음 종류(뿅·딩·휙·웃음 등)","alone": true}],
 "bgm": {"present": true, "mood": "분위기", "ducking": "말할 때 줄어드나"},
 "scenes_from": "장면 출처 추정(제품 광고·해외 쇼츠·직접 촬영·뉴스·이미지 등)",
 "length_note": "영상 길이·결말 처리 한 줄"
}
alone = 그 효과음이 목소리·배경음악 없이(또는 거의 없이) 단독으로 깨끗하게 들리면 true."""


def judge_one(mp4: Path, out: Path, ask=None) -> str:
    """영상 1편 통째 판독 — 제미나이 창구는 gemini_free.ask 한 곳(무료 공용 풀·429 장부·서버 대체. 10-18: 옛 providers._gemini_client 는
    버텍스 우선 + gemini-2.5-flash(새 키 404)라 깨져 있었다). 20MB 넘는 영상은 video_part 가 480p 로 줄인다."""
    if out.exists():
        return "skip"
    from tools.calcopy.engine import gemini_free
    ask = ask or gemini_free.ask
    t0 = time.time()
    try:
        part = gemini_free.video_part(str(mp4))
    except Exception as e:  # noqa: BLE001 — 줄이기 실패는 실패로 남긴다
        out.with_suffix(".err").write_text(f"{type(e).__name__}: {e}", encoding="utf-8")
        return "fail"
    d, err = ask([part], PROMPT, f"judge:{mp4.stem}")
    if err or not d:
        out.with_suffix(".err").write_text(f"gemini: {err}", encoding="utf-8")
        return "fail"
    d["_sec"] = round(time.time() - t0, 1)
    out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return "ok"


def run_judge(base: Path, workers: int = 4):
    os.makedirs(base / "judge", exist_ok=True)
    vids = sorted((base / "mp4").glob("*.mp4"))
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda p: judge_one(p, base / "judge" / f"{p.stem}.json"), vids))
    print("judge", {k: res.count(k) for k in set(res)})


def run_bench(base: Path):
    from shopping_shorts.channelkit import bench
    b = bench.run(base.name, str(base / "mp4"), str(base / "bench_main"))
    print("bench variants", b["layout"]["variants"].keys() if isinstance(b["layout"]["variants"], dict) else b["layout"]["variants"])


def run_asr(base: Path):
    tool = ROOT / "tools/hotpeople/measure/asr_speechmatics.py"
    files = [str(p) for p in sorted((base / "mp4").glob("*.mp4"))]
    subprocess.run([sys.executable, str(tool), *files], cwd=str(base), check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--only", choices=["judge", "bench", "asr"])
    a = ap.parse_args()
    base = Path(a.base)
    for name, fn in (("judge", run_judge), ("asr", run_asr), ("bench", run_bench)):
        if a.only in (None, name):
            fn(base)


if __name__ == "__main__":
    main()
