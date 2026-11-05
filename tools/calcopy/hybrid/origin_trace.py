# -*- coding: utf-8 -*-
"""G10 원본 추적(판단 주인 한 곳, 관제 319 2026-11-06) — 클립 채널(남의 영상을 재편집하는 벤치 채널) 소재 편 → 원 출처 영상.

규칙(사장님 고정 규칙 '원본에서만 · 남의 재편집본 금지'):
  · 벤치 편 자체(bench_ids)는 소재·재료가 아니다 → 거절
  · 설명란의 원 출처(링크 또는 ＠핸들)를 읽어 원 출처 영상을 찾는다 — 찾은 원본만 재료(받기는 worker_steps.step_source 'url:' 갈래)
  · 못 찾으면 그 편은 소재 후보에서 뺀다(조용히 클립 편으로 되돌아가지 않는다 — 이유를 남긴다)
부르는 곳: engine/topic_find.channel_candidates(채널 행 role='bench') · 재료 검사 hybrid/rules.source_rule_static ①(bench_ids)
같은 영상 판정 = origin_find.judge_same(씨앗 장면 + 후보 썸네일 → Claude 눈). 핸들 목록 = yt-dlp flat(틱톡·유튜브, 인스타 프로필은 yt-dlp 고장 — 실측 11-06).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

MADE_BY = "origin_trace v1 (G10 · 관제 319)"
SRC_WORD = r"(?:원본|원출처|출처|원작|source|credit|cr|via|from|영상\s*제공)"
URL_RX = re.compile(r"https?://(?:www\.|m\.|vm\.)?(?:instagram\.com/(?:reel|reels|p)/[0-9A-Za-z_-]{5,}|tiktok\.com/@[^/\s]{1,60}/video/\d{8,25}|vm\.tiktok\.com/[0-9A-Za-z]+"
                    r"|youtube\.com/(?:shorts/|watch\?v=)[0-9A-Za-z_-]{11}|youtu\.be/[0-9A-Za-z_-]{11})[^\s]*", re.I)
HANDLE_RX = re.compile(SRC_WORD + r"[^\n@＠]{0,12}[@＠]([0-9A-Za-z_.]{2,40})", re.I)
LIST_N = 60          # 핸들 목록에서 볼 최근 편 수
PLATFORMS = (("tiktok", "https://www.tiktok.com/@{h}"), ("youtube", "https://www.youtube.com/@{h}/shorts"))


def refs_of(desc: str) -> list[dict]:
    """설명란 → 원 출처 표시 목록. 영상 링크 [{kind:'url', url}] 먼저, 그다음 '출처/원본/source… @핸들' [{kind:'handle', handle}]."""
    desc = str(desc or "")
    out, seen = [], set()
    for m in URL_RX.finditer(desc):
        u = m.group(0).rstrip(").,]")
        if u not in seen:
            seen.add(u)
            out.append({"kind": "url", "url": u})
    for m in HANDLE_RX.finditer(desc):
        h = m.group(1).strip(".")
        if h and h.lower() not in seen:
            seen.add(h.lower())
            out.append({"kind": "handle", "handle": h})
    return out


def _yt_id(url: str) -> str:
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([0-9A-Za-z_-]{11})", url or "")
    return m.group(1) if m else ""


def _desc(url: str) -> dict:
    r = subprocess.run(["yt-dlp", "--skip-download", "--no-warnings", "-J", url], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        j = json.loads(r.stdout)
    except ValueError:
        j = None
    if not isinstance(j, dict):        # yt-dlp 추출 실패 = stdout 'null'(11-06 실측) → 이유를 남긴다
        return {"error": (r.stderr or "")[-200:] or "yt-dlp 답 없음"}
    return {"description": j.get("description") or "", "channel_id": j.get("channel_id"), "duration": j.get("duration")}


def _list(url: str, n: int = LIST_N) -> list[dict]:
    r = subprocess.run(["yt-dlp", "--flat-playlist", "--no-warnings", "--playlist-end", str(n), "-J", url], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=240)
    try:
        j = json.loads(r.stdout)
    except ValueError:
        j = None
    ents = (j.get("entries") or []) if isinstance(j, dict) else []      # 'null' = 목록 추출 실패(틱톡 secondary user ID 등) → 빈 목록, trace 가 '목록 없음' 으로 남긴다
    out = []
    for e in ents:
        th = e.get("thumbnail") or next((t.get("url") for t in reversed(e.get("thumbnails") or []) if t.get("url")), None)
        u = e.get("url") or e.get("webpage_url")
        if u and e.get("id"):
            out.append({"key": str(e["id"]), "url": u, "thumb": th, "duration": e.get("duration"), "title": (e.get("title") or "")[:80]})
    return out


def _seed_frames(url: str, d: Path) -> list:
    from tools.calcopy import origin_find as OF
    return OF.frames(url, d)


def _judge(seed: list, cands: list, d: Path, log) -> dict:
    from tools.calcopy import origin_find as OF
    return OF.judge_same(seed, cands, d, log)


def trace(video: dict, bench_ids=(), work: Path | None = None, deps: dict | None = None, log=print) -> dict:
    """소재 편 하나({id, url}) → {id, ok, origin_url, refs, tried, why, made_by}. deps = 시험용 가짜(desc·list·seed·judge)."""
    D = {"desc": _desc, "list": _list, "seed": _seed_frames, "judge": _judge, **(deps or {})}
    vid = str(video.get("id") or _yt_id(video.get("url") or ""))
    res = {"id": vid, "ok": False, "origin_url": None, "refs": [], "tried": [], "made_by": MADE_BY}
    if vid and vid in set(bench_ids or ()):
        return {**res, "why": "벤치 편 자체 — 소재·재료가 아니다"}
    info = D["desc"](video.get("url") or f"https://www.youtube.com/shorts/{vid}")
    if info.get("error"):
        return {**res, "why": "설명란을 못 읽음: " + str(info["error"])[:160]}
    refs = refs_of(info.get("description"))
    res["refs"] = refs
    if not refs:
        return {**res, "why": "설명란에 원 출처(링크·@핸들)가 없다"}
    for r in refs:
        if r["kind"] == "url":
            if _yt_id(r["url"]) and (_yt_id(r["url"]) == vid or _yt_id(r["url"]) in set(bench_ids or ())):
                res["tried"].append({"ref": r, "why": "자기 자신·벤치 편 링크"})
                continue
            return {**res, "ok": True, "origin_url": r["url"], "how": "설명란 링크"}
    wd = Path(work or Path.cwd() / "_origin_trace") / (vid or "x")
    seed = None
    for r in refs:
        if r["kind"] != "handle":
            continue
        for plat, tpl in PLATFORMS:
            lu = tpl.format(h=r["handle"])
            cands = D["list"](lu)
            if not cands:
                res["tried"].append({"ref": r, "list": lu, "why": "목록 없음"})
                continue
            if seed is None:
                seed = D["seed"](video.get("url") or f"https://www.youtube.com/shorts/{vid}", wd / "seed")
            if not seed:
                return {**res, "why": "소재 편 장면을 못 뽑음(받기 실패)"}
            dur = info.get("duration")
            if dur:          # 클립은 원본보다 짧거나 같다 — 원본이 클립보다 많이 짧으면 다른 영상
                cands = [c for c in cands if not c.get("duration") or c["duration"] >= 0.6 * dur] or cands
            same = D["judge"](seed, cands, wd, log)
            hit = next((c for c in cands if same.get(c["key"])), None)
            res["tried"].append({"ref": r, "list": lu, "n": len(cands), "judged": len(same), "hit": hit and hit["url"]})
            if hit:
                return {**res, "ok": True, "origin_url": hit["url"], "how": f"{plat} @{r['handle']} 목록 + 같은 영상 판정"}
    return {**res, "why": "원 출처 핸들의 목록에서 같은 영상을 못 찾음"}
