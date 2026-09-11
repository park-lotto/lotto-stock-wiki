# -*- coding: utf-8 -*-
"""최종 검수 — MVP는 규칙 검사만(합의). 시청 품질 보증이 아니라 기술적 통과다.

검사(아스트라 3R 반영):
  font_probe        폰트 4종 폴백 대조
  mp4_duration      컨테이너 길이 = total ±tol
  stream_sync       영상·오디오 **스트림** 길이가 서로 ±tol (컨테이너만 보면 한쪽 짧은 걸 놓친다)
  ass_last_end      자막 마지막 End = total
  subtitle_bounds   본문 모든 줄이 100%·108%에서 화면 안(외곽선 포함) / 제목 잉크 ≤ 목표+8
  narration_silence 나레 트랙 안 무음 없음(꼬리 0.1 제외). ffmpeg 실패·파일 없음은 **검사 실패**로 친다(빈 목록 아님)
입력을 수정하지 않는다. 보고서만 낸다.
"""
import os
import re
import subprocess

from . import spec, measure, timing as _timing, ass_gen, layout


def _probe_streams(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"review: ffprobe 실패 {path} — {r.stderr[-200:]}")
    out = {}
    for ln in r.stdout.strip().splitlines():
        parts = ln.split(",")
        if len(parts) >= 2 and parts[1] not in ("", "N/A"):
            out[parts[0]] = float(parts[1])
    return out


def _silences(wav, noise_db, min_sec):
    """→ (ok, [(start,end)]). ffmpeg가 실패하거나 파일이 없으면 ok=False."""
    if not os.path.exists(wav):
        return False, [("파일 없음", wav)]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_sec}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return False, [("ffmpeg 실패", r.stderr[-200:])]
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return True, list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def _subtitle_bounds(ass, fonts_dir):
    bad = []
    for ln in ass_gen.dialogue_lines(ass):
        p = ln.split(",", 9); sty = p[3]; txt = re.sub(r"\{[^}]*\}", "", p[9]).strip()
        if "\\p1" in p[9] or not txt:
            continue
        if sty in spec.BODY_Y:
            ok, info = layout.fits(sty, txt, fonts_dir)
            if not ok:
                bad.append({"style": sty, "text": txt, **info})
        elif sty in ("HL1", "HL2"):
            m = re.search(r"\\fs(\d+)", p[9]); fs = int(m.group(1)) if m else spec.STYLE_FONT[sty][2]
            w = measure.ink_width(spec.STYLE_FONT[sty][0], fs, txt, fonts_dir)
            if w > spec.TITLE_TARGET_INK + 8:
                bad.append({"style": sty, "text": txt, "ink": w})
    return bad


def run(mp4, ass_path, narr_wav, timing, *, fonts_dir=None):
    checks = []
    fp = measure.font_probe(fonts_dir)
    checks.append({"name": "font_probe", "ok": all(v["ok"] for v in fp.values()), "detail": fp})

    try:
        dur = _timing.wav_seconds(mp4)
        checks.append({"name": "mp4_duration", "ok": abs(dur - timing["total"]) <= spec.POLICY_DURATION_TOL,
                       "detail": {"mp4": round(dur, 3), "total": timing["total"]}})
        st = _probe_streams(mp4)
        v, a = st.get("video"), st.get("audio")
        checks.append({"name": "stream_sync", "ok": v is not None and a is not None and abs(v - a) <= spec.POLICY_DURATION_TOL,
                       "detail": {"video": v, "audio": a}})
    except Exception as e:  # noqa: BLE001 — 검수 실패는 사유를 담아 실패로 남긴다(삼키지 않는다)
        checks.append({"name": "mp4_duration", "ok": False, "detail": repr(e)[:200]})

    ass = open(ass_path, encoding="utf-8").read()
    ends = [ln.split(",")[2] for ln in ass_gen.dialogue_lines(ass) if ln.startswith("Dialogue: 4,")]
    checks.append({"name": "ass_last_end", "ok": bool(ends) and ends[-1] == ass_gen.fmt_time(timing["total"]),
                   "detail": {"last_end": ends[-1] if ends else None, "total": ass_gen.fmt_time(timing["total"])}})
    bad = _subtitle_bounds(ass, fonts_dir)
    checks.append({"name": "subtitle_bounds", "ok": not bad, "detail": bad})

    ok, sil = _silences(narr_wav, spec.POLICY_SILENCE_DB, spec.POLICY_SILENCE_SEC)
    body_end = timing["total"] - spec.TAIL_SEC
    inner = [s for s in sil if ok and isinstance(s[0], float) and s[0] < body_end - 0.05]
    checks.append({"name": "narration_silence", "ok": ok and not inner, "detail": {"silences": sil, "body_end": body_end}})
    return {"ok": all(c["ok"] for c in checks), "checks": checks}
