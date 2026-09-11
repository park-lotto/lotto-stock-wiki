# -*- coding: utf-8 -*-
"""컷 시각표 — 컷 길이 = 그 컷 TTS 길이, 카드 = 카드 문장 TTS 길이, 무음 0, 꼬리 +0.1초 (8편 실측).

입력은 wav 길이(초)뿐이다. 정렬(alignment)에 의존하지 않는다 — 아스트라 (3): 파일 실측으로 경계를 정한다.
"""
from . import spec


def build(card_sec, cut_secs, groups, *, card_img=None, region=None, slug=None):
    """card_sec: 카드 문장 wav 길이 / cut_secs: 컷별 wav 길이 리스트 / groups: 대본 컷 리스트
    → 볼케이노 timing.json과 같은 모양 {groups:[{i,t,d,color,lines,text,role,img|meme}], total, card_end, ...}"""
    if len(cut_secs) != len(groups):
        raise ValueError(f"timing: 컷 수 불일치 — wav {len(cut_secs)} vs 대본 {len(groups)}")
    card_end = round(float(card_sec), 3)
    t = card_end
    out = []
    for i, (sec, g) in enumerate(zip(cut_secs, groups), start=1):
        d = round(float(sec), 3)
        row = {"i": i, "t": round(t, 3), "d": d, "color": g["color"], "lines": list(g.get("lines") or [g["text"]]),
               "text": g["text"], "role": g["role"]}
        if g.get("img") is not None:
            row["img"] = g["img"]
        if g.get("meme") is not None:
            row["meme"] = g["meme"]
        out.append(row)
        t = round(t + d, 3)
    total = round(t + spec.TAIL_SEC, 3)
    res = {"groups": out, "total": total, "card_end": card_end}
    if card_img is not None:
        res["card_img"] = card_img
    if region is not None:
        res["region"] = region
    if slug is not None:
        res["slug"] = slug
    return res


def wav_seconds(path):
    """wav/mp3 길이(초) — ffprobe. 정렬 응답 대신 파일을 잰다."""
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"timing: ffprobe 실패 {path} — {r.stderr[-200:]}")
    return float(r.stdout.strip())
