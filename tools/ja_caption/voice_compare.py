"""성우별 일본어 TTS 를 듣기 엔진으로 일괄 검수해 표로 낸다(관제 254, 2026-10-23).

index.json([{preset,i,sent,file}]) → 각 mp3 에 voice_listen.listen → 성우별 평균(읽기 일치·억양 폭·빠르기·문제 수).
  py tools/ja_caption/voice_compare.py <index.json> [<index.json> ...]
  → 첫 index.json 옆에 listen.json(줄마다) + 표 출력
"""
import json, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main(indexes):
    from shopping_shorts.voice_listen import listen
    rows = []
    for ix in indexes:
        rows += json.loads(Path(ix).read_text(encoding="utf-8"))
    by = defaultdict(list)
    for r in rows:
        x = listen(r["file"], r["sent"], "ja")
        r.update(match=x["reading"]["match"], pitch=x["prosody"].get("pitch_semitones"),
                 speed=x["prosody"].get("syl_per_sec"), issues=x["issues"])
        by[r["preset"]].append(r)
        print(r["preset"], r["i"], r["match"], r["pitch"], r["speed"], "; ".join(x["issues"])[:120], flush=True)
    Path(indexes[0]).with_name("listen.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n성우 | 읽기일치 | 억양폭(반음, 원어민 11~17) | 빠르기(모라/초, 7.0~9.6) | 문제 줄")
    for p, rs in sorted(by.items(), key=lambda kv: -statistics.mean(r["pitch"] or 0 for r in kv[1])):
        print(f"{p} | {statistics.mean(r['match'] for r in rs):.2f} | {min(r['pitch'] for r in rs)}~{max(r['pitch'] for r in rs)} "
              f"| {min(r['speed'] for r in rs)}~{max(r['speed'] for r in rs)} | {sum(1 for r in rs if r['issues'])}/{len(rs)}")


if __name__ == "__main__":
    main(sys.argv[1:])
