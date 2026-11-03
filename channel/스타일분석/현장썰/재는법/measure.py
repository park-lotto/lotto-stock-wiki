# -*- coding: utf-8 -*-
"""현장썰 강점 1차 — 편마다 원음·교대·자막·컷·대본·소리 숫자를 한 표로 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/스타일분석/현장썰/재는법/measure.py

입력은 이미 잰 것을 먼저 쓴다(다시 재지 않는다):
  뜯기.json(engine_뜯기3 · 참고_hqGynmRWxpY/뜯기) = 컷·자막 시각·OCR·LUFS·받아쓰기·소리 구성
  썰풀다 새 4편은 뜯기 받아쓰기가 한도(quota)로 실패 → style50/<id>.json measure.audio(같은 ASR_PROMPT, gemini-3.5-flash) 를 쓴다
  MuskLab 은 screen/<id>.json(같은 ASR_PROMPT, gemini-2.5-flash — 고정 모델 한도라 대체) + 뜯기(받아쓰기 빼고)
새로 재는 것: 구간별 소리 크기(나레만 / 원음만 / 겹침 / 말 없음) = ffmpeg 16k 모노 → 50ms RMS dBFS 중앙값.
원음 구절 = 받아쓰기 구절 중 lang≠ko 또는 kind=source. 나레 구절 = lang=ko 이고 kind=narration.
출력: channel/스타일분석/현장썰/비교표.json
"""
from __future__ import annotations

import json
import statistics as st
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "비교표.json"
C = Path("C:/숏템_칼카피")

# (id, 채널, 묶음) — 묶음: 현장썰 / 대조(나레썰)
HYUNJANG = [("w-Ygny1f8O8", "sseolpulda"), ("t-xMApVctB0", "sseolpulda"), ("m4nffB05HNU", "sseolpulda"),
            ("LqPm7k1Aqek", "sseolpulda"), ("rMXGuFJEWDE", "sseolpulda"),
            ("a06yYTgpa_c", "hottemreport"), ("IRFN5B_2LMo", "hottemreport"), ("OE-11wb7vdY", "hottemreport"),
            ("ZqVgAg99gRI", "hottemreport"), ("i1Xj1A73zFI", "yummyknow"), ("hqGynmRWxpY", "땅콩쿠키"),
            ("Mp6LPm9qbLo", "hyunjang_ref")]   # 기준 편(사장님 지정, 썰풀다 2026-10-07)


def views_of() -> dict:
    v = {}
    for p in (C / "sseolpulda/style50").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        v[d["id"]] = d.get("views")
    root = Path(__file__).resolve().parents[4]
    for s in ("hottemreport", "yummyknow"):
        for it in json.loads((root / f"channel/{s}/원자료/top50.json").read_text(encoding="utf-8")):
            v[it["id"]] = it.get("views")
    m = json.loads((C / "sseolpulda/참고_hqGynmRWxpY/meta.json").read_text(encoding="utf-8"))
    v["hqGynmRWxpY"] = m.get("view_count")
    for ml in C.glob("*/views.json"):   # 새로 받은 편 조회수(yt-dlp 2026-10-18)
        v.update(json.loads(ml.read_text(encoding="utf-8")))
    return v


def ddir(vid: str, ch: str) -> Path:
    if ch == "땅콩쿠키":
        return C / "sseolpulda/참고_hqGynmRWxpY/뜯기"
    return C / ch / "engine_뜯기3" / vid


def mp4_of(vid: str, ch: str) -> Path:
    if ch == "땅콩쿠키":
        return C / "sseolpulda/참고_hqGynmRWxpY/hqGynmRWxpY.mp4"
    return C / ch / "mp4" / f"{vid}.mp4"


def audio_of(vid: str, ch: str, d: dict) -> tuple[dict, str]:
    """(transcript+asr_extra dict, 출처)"""
    a = d.get("audio") or {}
    if (a.get("transcript") or {}).get("segments"):
        return {"segments": a["transcript"]["segments"], "ambient": a["transcript"].get("ambient", ""),
                "bgm": (a.get("asr_extra") or {}).get("bgm"), "model": a["transcript"].get("model"),
                "duck_db": (a.get("composition") or {}).get("duck_db"), "kind": (a.get("composition") or {}).get("kind")}, "뜯기"
    if ch == "sseolpulda":
        s = json.loads((C / "sseolpulda/style50" / f"{vid}.json").read_text(encoding="utf-8"))
        ma = s["measure"]["audio"]
        return {"segments": ma["transcript"]["segments"], "ambient": ma["transcript"].get("ambient", ""),
                "bgm": (ma.get("asr_extra") or {}).get("bgm"), "model": ma["transcript"].get("model"),
                "duck_db": (ma.get("composition") or {}).get("duck_db"), "kind": (ma.get("composition") or {}).get("kind")}, "style50"
    if ch in ("musklab", "hyunjang_ref", "geuraeseo", "hermes"):
        r = json.loads((C / ch / "screen" / f"{vid}.json").read_text(encoding="utf-8"))["d"] or {}
        seg = [s for s in r.get("segments") or [] if str(s.get("text", "")).strip()]
        for s in seg:
            s["lang"] = str(s.get("lang") or "").lower(); s["kind"] = str(s.get("kind") or "").lower()
        return {"segments": sorted(seg, key=lambda s: float(s["start"])), "ambient": r.get("ambient", ""), "bgm": r.get("bgm"),
                "model": r.get("_model"), "duck_db": None, "kind": None}, "screen"
    return {"segments": []}, "없음"


def rms_track(mp4: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    n = len(x) // 800
    x = x[: n * 800].reshape(n, 800)
    return 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-9)   # 50ms 칸


def mask(segs, n, dt=0.05):
    m = np.zeros(n, bool)
    for s in segs:
        m[int(float(s["start"]) / dt): int(np.ceil(float(s["end"]) / dt))] = True
    return m


def one(vid: str, ch: str, group: str, views: dict) -> dict:
    dd = ddir(vid, ch)
    if (dd / "뜯기.json").exists():
        d = json.loads((dd / "뜯기.json").read_text(encoding="utf-8"))
    else:   # 뜯기 안 한 편(기준 편 등) — 길이만 ffprobe, 컷·자막은 없음
        du = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4_of(vid, ch))], capture_output=True, text=True).stdout
        d = {"probe": {"duration": float(du.strip())}}
    dur = d["probe"]["duration"]
    A, asrc = audio_of(vid, ch, d)
    seg = [{**s, "start": float(s["start"]), "end": min(float(s["end"]), dur)} for s in A["segments"]]
    narr = [s for s in seg if s.get("lang") == "ko" and s.get("kind") == "narration"]
    src = [s for s in seg if not (s.get("lang") == "ko" and s.get("kind") == "narration")]
    rms = rms_track(mp4_of(vid, ch))
    n = len(rms)
    mn, ms = mask(narr, n), mask(src, n)
    loud = rms > -50
    def med(m):   # 구간 소리 크기 = 50ms 칸 힘(power) 평균의 dB (중앙값은 말 사이 쉼에 끌려 내려가서 평균 힘으로)
        return round(float(10 * np.log10(np.mean(10 ** (rms[m] / 10)))), 1) if m.sum() >= 4 else None
    gaps = []   # 나레 없는 구간(≥0.5s) — 원음·BGM 만 들리는 곳
    t = 0.0
    for s in narr + [{"start": dur, "end": dur}]:
        if s["start"] - t >= 0.5:
            gaps.append((round(t, 2), round(s["start"], 2)))
        t = max(t, s["end"])
    src_sec = float(ms.sum() * 0.05)
    over = float((mn & ms).sum() * 0.05)
    # 원음 구절 앞 나레 한 줄(원음을 불러내는 말)
    callers = []
    for s in src:
        prev = [x for x in narr if x["end"] <= s["start"] + 0.3]
        if prev:
            callers.append({"src_t": round(s["start"], 1), "src": s["text"][:60], "src_lang": s.get("lang"), "src_kind": s.get("kind"),
                            "before": prev[-1]["text"][-40:], "gap_s": round(s["start"] - prev[-1]["end"], 2)})
        else:
            callers.append({"src_t": round(s["start"], 1), "src": s["text"][:60], "src_lang": s.get("lang"), "src_kind": s.get("kind"), "before": None})
    cap = d.get("captions") or {}
    items = cap.get("items") or []
    cap_in_src = [it for it in items if ms[min(n - 1, int(((it["t0"] + it["t1"]) / 2) / 0.05))]]
    cap_in_gap = [it for it in items if any(a <= (it["t0"] + it["t1"]) / 2 <= b for a, b in gaps)]
    ko_chars = sum(len(s["text"].replace(" ", "")) for s in narr)
    ko_sec = sum(s["end"] - s["start"] for s in narr)
    cuts = d.get("cuts") or {}
    bench = (d.get("audio") or {}).get("bench") or {}
    return {
        "id": vid, "channel": ch, "group": group, "views": views.get(vid), "dur": round(dur, 2), "audio_from": asrc, "asr_model": A.get("model"),
        "kind_engine": A.get("kind"),
        "src_n": len(src), "src_sec": round(src_sec, 2), "src_share": round(src_sec / dur, 3),
        "src_first_t": round(src[0]["start"], 2) if src else None,
        "src_hook_le3s": bool(src and src[0]["start"] <= 3.0),
        "src_kinds": sorted({f"{s.get('lang')}:{s.get('kind')}" for s in src}),
        "src_lens": [round(s["end"] - s["start"], 2) for s in src],
        "ambient": A.get("ambient", ""),
        "narr_n": len(narr), "narr_sec": round(ko_sec, 2), "narr_share": round(ko_sec / dur, 3),
        "narr_over_src_sec": round(over, 2), "narr_over_src_frac": round(over / src_sec, 3) if src_sec else None,
        "no_narr_gaps": gaps, "no_narr_sec": round(sum(b - a for a, b in gaps), 2), "no_narr_share": round(sum(b - a for a, b in gaps) / dur, 3),
        "db_narr_only": med(mn & ~ms & loud), "db_src_only": med(ms & ~mn & loud), "db_no_speech": med(~mn & ~ms & loud),
        "src_minus_narr_db": (round(med(ms & ~mn & loud) - med(mn & ~ms & loud), 1) if med(ms & ~mn & loud) is not None and med(mn & ~ms & loud) is not None else None),
        "duck_db_engine": A.get("duck_db"),
        "hook_text": narr[0]["text"] if narr else None, "hook_t0": round(narr[0]["start"], 2) if narr else None,
        "last_text": narr[-1]["text"] if narr else None,
        "callers": callers,
        "cps": round(ko_chars / ko_sec, 2) if ko_sec else None, "ko_chars": ko_chars,
        "cap_n": len(items), "cap_in_src_n": len(cap_in_src), "cap_in_src_text": [" ".join(it.get("text") or []) for it in cap_in_src][:12],
        "cap_in_gap_n": len(cap_in_gap), "cap_in_gap_text": [" ".join(it.get("text") or []) for it in cap_in_gap][:12],
        "cap_ocr_ok": bool(sum(1 for it in items if it.get("text"))),
        "shots": cuts.get("shots"), "shot_med": (cuts.get("shot_len") or {}).get("median"), "cut_per_min": cuts.get("cut_per_min"),
        "materials": (d.get("materials") or {}).get("share_by_time"),
        "lufs_I": bench.get("I"), "bgm": A.get("bgm"),
    }


PJ = json.loads((HERE / "제품판독.json").read_text(encoding="utf-8"))


def product_of(vid: str) -> tuple[str | None, str | None, str | None]:
    """(제품명, 판매 가능, 제외 사유) — 제품판독.json(Claude 판독)"""
    if vid in PJ["flow_set"]:
        f = PJ["flow_set"][vid]
        return f["product"], f["sell"], None
    if vid in PJ["excluded"]:
        return None, "아니오", PJ["excluded"][vid]
    if vid in PJ["sseolpulda50"]:
        name, sell = PJ["sseolpulda50"][vid]
        return name, sell, ("제외: 제품 없음" if sell == "아니오" else None)
    return None, None, None


def main():
    views = views_of()
    rows = []
    jobs = [(i, c, "현장썰") for i, c in HYUNJANG]
    # 대조 = 같은 채널의 '나레 1명'(나레썰) 편 중 원작에 제품 있는 편 + 그래서리뷰(제품 나레썰 채널) 선별 편
    style50 = {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8"))["classify"]["style"]
               for p in (C / "sseolpulda/style50").glob("*.json")}
    for ch in ("sseolpulda", "hottemreport"):
        for p in sorted((C / ch / "engine_뜯기3").glob("*/뜯기.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            vid = p.parent.name
            if ((d.get("audio") or {}).get("composition") or {}).get("kind") != "나레 1명":
                continue
            if ch == "sseolpulda" and style50.get(vid) != "나레만":     # 역할극(피치 보정)은 빼기
                continue
            jobs.append((vid, ch, "나레썰"))
    for p in sorted((C / "geuraeseo/screen").glob("*.json")):
        jobs.append((p.stem, "geuraeseo", "나레썰"))
    for vid, ch, g in jobs:
        name, sell, excl = product_of(vid)
        if ch in ("hottemreport", "geuraeseo") and name is None and not excl:
            name, sell = "(제목상 제품 — 시트 확인 안 함)", "예"
        try:
            r = one(vid, ch, g, views)
        except Exception as e:  # noqa: BLE001 — 편 하나 실패는 표에 남기고 계속
            r = {"id": vid, "channel": ch, "group": g, "failed": f"{type(e).__name__}: {e}"}
        r.update({"product": name, "sell": sell, "excluded": excl})
        rows.append(r)
    OUT.write_text(json.dumps({"made": "2026-10-18", "by": "channel/스타일분석/현장썰/재는법/measure.py", "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        if "failed" in r:
            print(r["id"], r["failed"]); continue
        print(f"{r['group']}	{r['channel'][:6]}	{r['id']}	{r['views']}	{r['sell']}	{r['excluded'] or ''}	{r['dur']}s src{r['src_n']}/{r['src_share']} first{r['src_first_t']} "
              f"over{r['narr_over_src_frac']} gap{r['no_narr_share']} dB n{r['db_narr_only']} s{r['db_src_only']} cps{r['cps']} shots{r['shots']}/{r['shot_med']} I{r['lufs_I']}")


if __name__ == "__main__":
    main()
