"""TTS 결과물 검사 — 관제 049 (2026-10-01). 작업 폴더의 tts/ 를 보고 새 규칙대로 만들어졌는지 잰다.

잰다:
  ① 통째 합성인가     tts/_joined.mp3 가 있나(없으면 문장별 합성 = 끊김의 뿌리)
  ② 추임새가 없나     합성에 보낸 글(_joined.mp3.align.json)에 "음,"·"아," 같은 단독 추임새가 있나
  ③ 배속이 맞나       원음(_joined) 말 구간 ÷ 조각 합 말 구간 ≈ atempo 배율(기대값과 ±6%)
  ④ 문장 안 무음컷    조각별 cuts.json 구간 수(옛 규칙은 문장당 최대 12개였다)

    python tools/tts_speed_audit.py <작업폴더> [--expect 1.35]
종료코드 0 = 전부 통과, 1 = 하나라도 실패.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

_FILLER = re.compile(r"(?:^|[\s\]….!?])(음|아|어|그|뭐|자),\s")
_TAG = re.compile(r"\[[^\]]*\]")


def _voiced(path, thr="-40dB", d="0.05"):
    """말한 시간(초) = 전체 − silencedetect 무음 합."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", f"silencedetect=noise={thr}:d={d}",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                path], capture_output=True, text=True).stdout or 0)
    ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    sil = sum(e - s for s, e in zip(ss, se + [dur] * (len(ss) - len(se))))
    return dur - sil, dur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir")
    ap.add_argument("--expect", type=float, default=None, help="기대 배속(미나 1.35 / 그 외 1.25)")
    a = ap.parse_args()
    tts = os.path.join(a.job_dir, "tts")
    fails = []
    joined = os.path.join(tts, "_joined.mp3")
    pieces = sorted(p for p in glob.glob(os.path.join(tts, "beat_*.mp3")) if re.search(r"beat_\d+_[0-9a-f]+\.mp3$", p))
    print(f"조각 {len(pieces)}개")
    if not os.path.exists(joined):
        fails.append("① 통째 합성 흔적(_joined.mp3) 없음 — 문장별 합성")
        print("① 통째 합성: 아니오")
    else:
        print("① 통째 합성: 예")
        al = os.path.join(tts, "_joined.mp3.align.json")
        if os.path.exists(al):
            text = "".join(json.load(open(al, encoding="utf-8"))["characters"])
            hits = _FILLER.findall(" " + text)
            print(f"② 추임새: {len(hits)}개 {hits[:5]}")
            if hits:
                fails.append(f"② 추임새 {len(hits)}개")
        else:
            fails.append("② 합성 글(align.json) 없음")
        if pieces:
            v_raw, _ = _voiced(joined)
            v_out = sum(_voiced(p)[0] for p in pieces)
            ratio = v_raw / v_out if v_out else 0
            msg = f"③ 배속(말 구간 비): {ratio:.3f}"
            if a.expect:
                ok = abs(ratio / a.expect - 1) <= 0.06
                msg += f" (기대 {a.expect}, {'통과' if ok else '실패'})"
                if not ok:
                    fails.append(f"③ 배속 {ratio:.3f} ≠ {a.expect}")
            print(msg)
    cuts = []
    for p in pieces:
        cj = p + ".cuts.json"
        cuts.append(len(json.load(open(cj))) if os.path.exists(cj) else 0)
    print(f"④ 조각별 무음컷: {cuts} (최대 {max(cuts) if cuts else 0})")
    print("판정:", "통과" if not fails else "실패 — " + " / ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
