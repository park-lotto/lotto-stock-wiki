# -*- coding: utf-8 -*-
"""실사 소스 — 검색어 → 유튜브 후보 → 영상만 앞부분 다운로드 → 장면 자르기 → 번호 시트 → AI가 자막마다 장면 선택.

★컷마다 출처(영상 id·URL·시작초)를 남긴다 — 문제 컷만 바꿀 수 있게(설계 §3, 저작권 리스크).
★세로 영상(쇼츠)은 버린다 — 슬롯이 가로 1080×790이라 잘라 넣으면 절반이 날아간다.
"""
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import spec

THUMB_W, THUMB_H = 240, 176          # 슬롯 비율(1.367)
SHEET_COLS, SHEET_ROWS = 6, 5        # 시트 한 장 30칸
MAX_SHEETS = 4                       # 120칸까지


def _run(argv, timeout=900):
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def search(query, n, log=print):
    """→ [{id,title,duration,url}] (가로 긴 영상 우선: 60초~POLICY_FOOTAGE_MAX_SEC)."""
    r = _run(["yt-dlp", "--no-update", "--flat-playlist", "-J", f"ytsearch{max(n * 3, 6)}:{query}"], timeout=120)
    if r.returncode != 0:
        log(f"[footage] 검색 실패 «{query}»: {r.stderr[-200:]}")
        return []
    out = []
    for e in json.loads(r.stdout).get("entries") or []:
        d = e.get("duration") or 0
        url = e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}"
        if "/shorts/" in url or not 60 <= d <= spec.POLICY_FOOTAGE_MAX_SEC:
            continue
        out.append({"id": e["id"], "title": e.get("title") or "", "duration": d,
                    "url": f"https://www.youtube.com/watch?v={e['id']}"})
        if len(out) >= n:
            break
    return out


def _dims(path):
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
              "-of", "json", path], timeout=60)
    j = json.loads(r.stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    return s.get("width") or 0, s.get("height") or 0, float((j.get("format") or {}).get("duration") or 0)


def download(item, vdir, log=print):
    """영상만(소리 없음) 720p 이하, 앞 POLICY_FOOTAGE_HEAD_SEC 초. → 경로 또는 None."""
    os.makedirs(vdir, exist_ok=True)
    out = os.path.join(vdir, f"{item['id']}.mp4")
    if os.path.exists(out) and os.path.getsize(out) > 10000:
        return out
    base = ["yt-dlp", "--no-update", "-f", "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]",
            "--download-sections", f"*0-{spec.POLICY_FOOTAGE_HEAD_SEC}", "--remux-video", "mp4", "-o", out, item["url"]]
    for extra in ([], ["--extractor-args", "youtube:player_client=android"]):
        r = _run(base[:2] + extra + base[2:])
        if r.returncode == 0 and os.path.exists(out):
            w, h, dur = _dims(out)
            if w <= h:
                log(f"[footage] 세로 영상 버림 {item['id']} {w}x{h}")
                os.remove(out)
                return None
            return out
    log(f"[footage] 다운로드 실패 {item['id']}: {r.stderr[-200:]}")
    return None


def scenes(path, vid, thumbs_dir):
    """장면 자르기 → [{vid,path,start,end,thumb}]. 너무 짧거나 어두운 장면·첫 3% 제외."""
    _, _, dur = _dims(path)
    r = _run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"select='gt(scene,{spec.POLICY_SCENE_THRESH})',metadata=print:file=-",
              "-an", "-f", "null", "-"], timeout=900)
    cuts = sorted({round(float(l.split("pts_time:")[1]), 2) for l in r.stdout.splitlines() if "pts_time:" in l})
    bounds = [0.0] + [c for c in cuts if 0 < c < dur] + [dur]
    os.makedirs(thumbs_dir, exist_ok=True)
    out = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < spec.POLICY_SCENE_MIN_SEC or a < dur * 0.03:
            continue
        t = a + min(0.8, (b - a) / 2)
        th = os.path.join(thumbs_dir, f"{vid}_{int(a * 100):06d}.jpg")
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
              "-vf", f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=increase,crop={THUMB_W}:{THUMB_H}", th], timeout=60)
        if not os.path.exists(th):
            continue
        im = Image.open(th).convert("L")
        px = list(im.getdata())
        mean = sum(px) / len(px)
        if mean < 22:                       # 거의 검정(암전·자막 카드)
            continue
        out.append({"vid": vid, "path": path, "start": round(a, 2), "end": round(b, 2), "thumb": th})
    return out


def _even(items, k):
    if len(items) <= k:
        return items
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def sheets(cands, out_dir):
    """번호 붙인 썸네일 시트 → [png 경로]. cands 순서 = 번호."""
    os.makedirs(out_dir, exist_ok=True)
    per = SHEET_COLS * SHEET_ROWS
    font = ImageFont.truetype(spec.LOGO_NAME_FONT, 26)
    paths = []
    for si in range(0, len(cands), per):
        chunk = cands[si:si + per]
        sh = Image.new("RGB", (SHEET_COLS * (THUMB_W + 6), SHEET_ROWS * (THUMB_H + 6)), "white")
        d = ImageDraw.Draw(sh)
        for j, c in enumerate(chunk):
            x, y = (j % SHEET_COLS) * (THUMB_W + 6), (j // SHEET_COLS) * (THUMB_H + 6)
            sh.paste(Image.open(c["thumb"]).convert("RGB"), (x, y))
            n = str(si + j)
            d.rectangle([x, y, x + 16 + 15 * len(n), y + 32], fill="black")
            d.text((x + 6, y + 2), n, font=font, fill="yellow")
        p = os.path.join(out_dir, f"sheet_{si // per:02d}.png")
        sh.save(p)
        paths.append(p)
    return paths


def _pick_prompt(groups, n_cands, person):
    subs = "\n".join(f"{i}. 자막 «{g.get('text')}» / 원하는 화면: {g.get('scene', '')}" for i, g in enumerate(groups))
    return (f"숏폼 편집자다. 주인공은 {person}. 아래 시트의 번호 붙은 장면 0~{n_cands - 1} 중에서 자막마다 가장 맞는 장면 번호를 골라라.\n"
            "규칙: 같은 번호를 두 번 쓰지 마라. 주인공이 실제로 나오는 장면을 우선. 글자가 화면 대부분인 장면·로고·검은 화면은 피하라.\n"
            "★화면 아래에 자막(한글·영어 문장)이 박힌 장면은 가능한 한 피하라 — 우리 자막과 겹친다. 요리·먹방 등 주제와 무관한 장면은 쓰지 마라.\n"
            "맞는 게 없으면 분위기가 맞는 장면을 골라라(비워두지 마라).\n"
            f"[자막]\n{subs}\n\n출력 JSON: {{\"picks\": [자막0의 번호, 자막1의 번호, …]}} (자막 수 {len(groups)}개와 길이가 같아야 한다)")


def pick(groups, cands, sheet_paths, reader, person, log=print):
    """→ 자막마다 장면 index 리스트. 모델 답이 틀리면(범위 밖·중복·개수) 남는 장면으로 순서대로 메운다."""
    picks = []
    if reader is not None and cands:
        import time
        from shopping_shorts.channelkit.prompt import parse_any
        readers = reader if isinstance(reader, (list, tuple)) else [reader]
        for ri, rd in enumerate(readers):
            for wait in (0, 10, 30):                 # 503(과부하)은 잠깐 뒤 풀린다 — 2026-09-25 실측 첫 시도 503
                if wait:
                    time.sleep(wait)
                try:
                    raw = rd(_pick_prompt(groups, len(cands), person), sheet_paths)
                    picks = list((parse_any(raw) or {}).get("picks") or [])
                    break
                except Exception as e:  # noqa: BLE001
                    log(f"[footage] 장면 선택 모델{ri} 실패({wait}s 뒤 재시도): {repr(e)[:160]}")
            if picks:
                break
    used, out, fixed = set(), [], 0
    for i in range(len(groups)):
        p = picks[i] if i < len(picks) else None
        if not isinstance(p, int) or not 0 <= p < len(cands) or p in used:
            p = next((k for k in range(len(cands)) if k not in used), None)
            fixed += 1
            if p is None:                   # 장면이 자막보다 적다 — 재사용
                p = i % max(1, len(cands))
        used.add(p)
        out.append(p)
    if fixed:
        log(f"[footage] 모델 답 {fixed}/{len(groups)}개를 순서대로 메움")
    return out, fixed


def collect(script, wd, reader=None, log=print):
    """→ {"videos":[…], "cands":[…], "cuts":[{…}], "sheets":[…], "fixed":n}. 컷 = 자막 순서."""
    vdir, tdir = os.path.join(wd, "footage", "videos"), os.path.join(wd, "footage", "thumbs")
    seen, videos = set(), []
    # 재개: 이미 받아 둔 영상을 먼저 쓴다(검색 결과 순서가 바뀌어도 다시 받지 않게)
    for f in sorted(os.listdir(vdir)) if os.path.isdir(vdir) else []:
        if f.endswith(".mp4") and len(videos) < spec.POLICY_FOOTAGE_MAX_VIDEOS:
            vid = f[:-4]
            seen.add(vid)
            videos.append({"id": vid, "title": "", "duration": 0, "query": "(받아 둔 것)",
                           "url": f"https://www.youtube.com/watch?v={vid}", "path": os.path.join(vdir, f)})
    for q in (script.get("queries") or [])[:spec.POLICY_FOOTAGE_QUERIES]:
        if len(videos) >= spec.POLICY_FOOTAGE_MAX_VIDEOS:
            break
        for it in search(q, spec.POLICY_FOOTAGE_PER_QUERY + 1, log=log):
            if it["id"] in seen or len(videos) >= spec.POLICY_FOOTAGE_MAX_VIDEOS:
                continue
            seen.add(it["id"])
            p = download(it, vdir, log=log)
            if p:
                it["path"] = p; it["query"] = q
                videos.append(it)
                log(f"[footage] 받음 {it['id']} «{it['title'][:40]}» ({q})")
    if not videos:
        raise RuntimeError("footage: 받은 영상이 없다 — 검색어(queries)를 바꿔 script부터")
    cands = []
    for v in videos:
        cands += scenes(v["path"], v["id"], tdir)
    cands = _even(cands, SHEET_COLS * SHEET_ROWS * MAX_SHEETS)
    log(f"[footage] 영상 {len(videos)}편 · 장면 후보 {len(cands)}개")
    sp = sheets(cands, os.path.join(wd, "footage"))
    groups = script.get("groups") or []
    idx, fixed = pick(groups, cands, sp, reader, script.get("person", ""), log=log)
    if reader is not None and fixed > len(groups) * 0.3:
        # ★조용히 순서대로 메운 영상을 "완료"로 내보내지 마라(2026-09-25: 503으로 27/27 순서 메움 → 요리 장면이 섞였다)
        raise RuntimeError(f"footage: 장면 선택 모델이 {fixed}/{len(groups)}개를 못 골랐다 — 잠시 뒤 footage부터 다시")
    url = {v["id"]: v["url"] for v in videos}
    cuts = [{"scene": k, "src": cands[k]["path"], "start": cands[k]["start"], "end": cands[k]["end"],
             "vid": cands[k]["vid"], "url": url.get(cands[k]["vid"]), "thumb": cands[k]["thumb"]} for k in idx]
    return {"videos": [{k: v[k] for k in ("id", "title", "url", "query", "duration")} for v in videos],
            "n_cands": len(cands), "cuts": cuts, "sheets": sp, "fixed": fixed}
