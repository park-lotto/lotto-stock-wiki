"""성우 말 빠르기 실측 도구 — 결과 음성의 '초당 글자수'(공백·문장부호 뺀 글자 / 초).

왜: 같은 배속(default_speed)이라도 성우마다 원래 말 빠르기가 달라 결과가 다르다(관제 123, 2026-10-05).
기본 속도를 정할 땐 배수가 아니라 **결과 말 빠르기**를 맞춘다. 이 도구가 그 자다.

두 가지 모드
  jobs  : 실제 job 의 비트 대사(mix_jobs.edit_plan_json beats[].narration) ↔ 최종 비트 mp3(beats[].tts_path)
          job 의 성우는 mix_jobs.voice_json(preset_id·model_id). 프리셋별·엔진별 중앙값을 낸다.
          서버에서 읽기 전용으로:  python3 /tmp/measure_rate.py jobs --db .../reference.db --limit 400
  files : 로컬 mp3 + 대사 텍스트 짝(JSON: [{"label":..,"text":..,"mp3":..}, ...]) 을 같은 자로 잰다.

잣대
  rate_total  = 글자수 / 파일 길이(ffprobe)
  rate_speech = 글자수 / (파일 길이 - 무음 구간 합)   ← 무음 제외(ffmpeg silencedetect -35dB, 0.15초)
  ★비교는 rate_speech 중앙값으로 한다(문장 사이 쉼·앞뒤 여백 차이에 덜 흔들림).

검사: 비트 파일명 해시(beat_<idx>_<md5(narration)[:10]>.mp3)가 지금 대사와 다르면 버린다
      (다른 대본의 음성 — mix_pipeline._beat_tts_path 와 같은 규칙).
"""
import argparse
import hashlib
import json
import re
import sqlite3
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_TAG = re.compile(r"\[[^\]]*\]")
_KEEP = re.compile(r"[0-9A-Za-z\uac00-\ud7a3\u3131-\u318e]")


def count_chars(text):
    """공백·문장부호·[감정태그] 뺀 글자수."""
    return len(_KEEP.findall(_TAG.sub("", text or "")))


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True).stdout
    return float(out.strip())


def silence_total(path, noise="-35dB", d=0.15):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                          f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return sum(float(x) for x in re.findall(r"silence_duration: ([0-9.]+)", err))


def measure(text, mp3):
    n = count_chars(text)
    dur = duration(mp3)
    sp = max(0.05, dur - silence_total(mp3))
    return {"chars": n, "dur": round(dur, 3), "speech": round(sp, 3),
            "rate_total": round(n / dur, 3), "rate_speech": round(n / sp, 3)}


def engine_of(model_id, preset_id=""):
    m = (model_id or "")
    if m.startswith("fish") or preset_id.startswith("fs-"):
        return "fish"
    if m.startswith("ssfm") or preset_id.startswith("tc-"):
        return "typecast"
    return "eleven"


def _summ(vals):
    vals = sorted(vals)
    return {"n": len(vals), "median": round(statistics.median(vals), 2),
            "p10": round(vals[int(len(vals) * 0.1)], 2), "p90": round(vals[int(len(vals) * 0.9) - 1 if len(vals) > 1 else 0], 2),
            "min": round(vals[0], 2), "max": round(vals[-1], 2)}


def run_jobs(db, limit, min_chars):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = c.execute("SELECT job_id, voice_json, edit_plan_json FROM mix_jobs "
                     "WHERE voice_json IS NOT NULL AND edit_plan_json IS NOT NULL "
                     "ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    per = []
    for job_id, vj, pj in rows:
        try:
            v = json.loads(vj) or {}
            beats = (json.loads(pj) or {}).get("beats") or []
        except Exception:
            continue
        pid = v.get("preset_id") or ""
        if not pid:
            continue
        for b in beats:
            t, p = b.get("narration") or "", b.get("tts_path")
            if not p or count_chars(t) < min_chars or not Path(p).exists():
                continue
            m = re.fullmatch(r"beat_(\d+)_([0-9a-f]{10})\.mp3", Path(p).name)
            if not m or m.group(2) != hashlib.md5(t.encode("utf-8")).hexdigest()[:10]:
                continue
            try:
                r = measure(t, p)
            except Exception:
                continue
            per.append({"job": job_id, "preset": pid, "engine": engine_of(v.get("model_id"), pid),
                        "speed": v.get("speed"), **r})
    return per


def report(per, key="rate_speech"):
    by_p, by_e = defaultdict(list), defaultdict(list)
    jobs_p = defaultdict(set)
    for r in per:
        by_p[r["preset"]].append(r[key])
        by_e[r["engine"]].append(r[key])
        jobs_p[r["preset"]].add(r.get("job", ""))
    out = {"key": key, "all": _summ([r[key] for r in per]) if per else None,
           "engine": {e: _summ(v) for e, v in by_e.items()},
           "preset": {p: {**_summ(v), "jobs": len(jobs_p[p])}
                      for p, v in sorted(by_p.items(), key=lambda kv: -len(kv[1]))}}
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    j = sub.add_parser("jobs")
    j.add_argument("--db", required=True)
    j.add_argument("--limit", type=int, default=400)
    j.add_argument("--min-chars", type=int, default=8)
    j.add_argument("--raw", default=None, help="비트별 원자료 JSON 저장 경로")
    f = sub.add_parser("files")
    f.add_argument("pairs", help='[{"label","text","mp3"}] JSON')
    a = ap.parse_args()
    if a.mode == "jobs":
        per = run_jobs(a.db, a.limit, a.min_chars)
        if a.raw:
            Path(a.raw).write_text(json.dumps(per, ensure_ascii=False), encoding="utf-8")
    else:
        per = []
        for it in json.loads(Path(a.pairs).read_text(encoding="utf-8")):
            per.append({"preset": it["label"], "engine": it.get("engine", "?"), **measure(it["text"], it["mp3"])})
    print(json.dumps({"speech": report(per), "total": report(per, "rate_total")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
