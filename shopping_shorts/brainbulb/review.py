# -*- coding: utf-8 -*-
"""최종 검수 — MVP는 규칙 검사만(합의). 시청 품질 보증이 아니라 기술적 통과다.

검사: 폰트 폴백 · mp4 길이 = total ±tol · 자막 마지막 End = total · 나레 트랙 안 무음(꼬리 0.1 제외, 효과음이 가리지 않게 narr.wav를 본다)
입력을 수정하지 않는다. 보고서만 낸다.
"""
import re
import subprocess

from . import spec, measure, timing as _timing, ass_gen


def _probe_dur(path):
    return _timing.wav_seconds(path)


def _silences(wav, noise_db, min_sec):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_sec}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    out = []
    for m in re.finditer(r"silence_start: ([\d.]+)", r.stderr):
        out.append(float(m.group(1)))
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(out, ends + [None] * (len(out) - len(ends))))


def run(mp4, ass_path, narr_wav, timing, *, fonts_dir=None):
    checks = []
    fp = measure.font_probe(fonts_dir)
    checks.append({"name": "font_probe", "ok": all(v["ok"] for v in fp.values()), "detail": fp})
    dur = _probe_dur(mp4)
    checks.append({"name": "mp4_duration", "ok": abs(dur - timing["total"]) <= spec.POLICY_DURATION_TOL,
                   "detail": {"mp4": round(dur, 3), "total": timing["total"]}})
    ass = open(ass_path, encoding="utf-8").read()
    ends = [ln.split(",")[2] for ln in ass_gen.dialogue_lines(ass) if ln.startswith("Dialogue: 4,")]
    checks.append({"name": "ass_last_end", "ok": bool(ends) and ends[-1] == ass_gen.fmt_time(timing["total"]),
                   "detail": {"last_end": ends[-1] if ends else None, "total": ass_gen.fmt_time(timing["total"])}})
    sil = _silences(narr_wav, spec.POLICY_SILENCE_DB, spec.POLICY_SILENCE_SEC)
    body_end = timing["total"] - spec.TAIL_SEC
    inner = [s for s in sil if s[0] < body_end - 0.05]
    checks.append({"name": "narration_silence", "ok": not inner, "detail": {"silences": sil, "body_end": body_end}})
    return {"ok": all(c["ok"] for c in checks), "checks": checks}
