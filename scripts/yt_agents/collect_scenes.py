"""저장한 인용(quotes.json) → 각 발언 타임스탬프의 장면 수집 (로컬 전용).

정지 프레임(PNG, 배경용) + 짧은 클립(MP4, 결정적 순간용)을 발언 시각마다 뽑는다.
긴 영상도 통째로 안 받고 yt-dlp --download-sections로 그 시각 주변 구간만 받아 효율적.

서버(데이터센터 IP)는 유튜브 봇차단 + ffmpeg 없음 → 이 스크립트는 사장님 로컬 PC 전용.
(로컬은 봇차단 없고 ffmpeg 설치돼 있음.)

사용:  python scripts/yt_agents/collect_scenes.py <quotes.json> [--clip 5]
결과:  out/scenes/<video_id>/  아래 frame_*.png / clip_*.mp4,
       입력 json의 각 quote에 media {frame, clip} 채워 <..>_scenes.json으로 저장.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys

try:  # Windows 콘솔(cp949)에서 한글·이모지 print 깨짐 방지
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "yt_agents"))
import quote_extractor as qe  # noqa: E402  (parse_video_id, _ts_to_sec)


def _grab_section(url: str, start: float, dur: float, out_mp4: str) -> str | None:
    """ts 주변 [start, start+dur] 구간만 다운로드. 파일 타임라인은 0부터 시작."""
    end = start + dur
    cmd = [sys.executable, "-m", "yt_dlp", "-f", "best[height<=720]/best",
           "--download-sections", f"*{start}-{end}", "--force-keyframes-at-cuts",
           "--no-warnings", "-o", out_mp4, url]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    if r.returncode != 0 or not os.path.exists(out_mp4):
        print(f"  구간 다운로드 실패 @ {start:.0f}s: {r.stderr[-200:]}", file=sys.stderr)
        return None
    return out_mp4


def _frame(section_mp4: str, offset: float, out_png: str) -> str | None:
    """구간 파일에서 offset 지점 프레임 1장."""
    subprocess.run(["ffmpeg", "-y", "-ss", f"{offset}", "-i", section_mp4,
                    "-frames:v", "1", "-q:v", "2", out_png],
                   capture_output=True, timeout=60)
    return out_png if os.path.exists(out_png) else None


def collect(quotes_json_path: str, clip_sec: float = 5.0,
            lead: float = 1.0, out_root: str | None = None) -> str:
    """quotes.json → 각 발언 장면 수집. 갱신된 json 경로 반환."""
    doc = json.load(open(quotes_json_path, encoding="utf-8"))
    url = (doc.get("source") or "").strip()
    if not url:
        raise SystemExit("quotes.json에 source(영상 URL)가 없음")
    vid = qe.parse_video_id(url) or "unknown"
    out_root = out_root or os.path.join(ROOT, "out", "scenes")
    scene_dir = os.path.join(out_root, vid)
    os.makedirs(scene_dir, exist_ok=True)

    quotes = doc.get("quotes", [])
    print(f"영상 {vid} — 인용 {len(quotes)}개 장면 수집 시작 (클립 {clip_sec}s)")
    ok = 0
    for i, q in enumerate(quotes):
        ts = q.get("ts_sec")
        if ts is None:
            ts = qe._ts_to_sec(q.get("ts", 0))
        start = max(0.0, float(ts) - lead)          # 발언 살짝 앞부터
        section = os.path.join(scene_dir, f"clip_{i:02d}.mp4")
        frame = os.path.join(scene_dir, f"frame_{i:02d}.png")
        got = _grab_section(url, start, clip_sec + lead, section)
        media = {}
        if got:
            media["clip"] = os.path.relpath(section, ROOT).replace("\\", "/")
            if _frame(section, lead, frame):        # 클립 내 발언 시작 지점 프레임
                media["frame"] = os.path.relpath(frame, ROOT).replace("\\", "/")
            ok += 1
            print(f"  [{i:02d}] {q.get('ts','?')} ✅ {q.get('text','')[:30]}")
        else:
            print(f"  [{i:02d}] {q.get('ts','?')} ❌ 수집 실패")
        q["media"] = media or None

    out_json = quotes_json_path.replace(".json", "_scenes.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"\n완료: {ok}/{len(quotes)} 장면 수집 → {scene_dir}\n갱신 json: {out_json}")
    return out_json


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("quotes_json", help="저장한 인용 json (source=영상URL, quotes[].ts_sec)")
    ap.add_argument("--clip", type=float, default=5.0, help="클립 길이(초)")
    ap.add_argument("--lead", type=float, default=1.0, help="발언 앞 여유(초)")
    a = ap.parse_args()
    collect(a.quotes_json, clip_sec=a.clip, lead=a.lead)
