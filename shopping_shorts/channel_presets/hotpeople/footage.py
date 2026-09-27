# -*- coding: utf-8 -*-
"""실사 소스 — 검색어 → 유튜브 후보 → 영상만 앞부분 다운로드 → 장면 자르기 → 번호 시트 → AI가 자막마다 장면 선택.

★컷마다 출처(영상 id·URL·시작초)를 남긴다 — 문제 컷만 바꿀 수 있게(설계 §3, 저작권 리스크).
★세로 영상(쇼츠)은 버린다 — 슬롯이 가로 1080×790이라 잘라 넣으면 절반이 날아간다.
★소스 자(우상혁 v001 사고): 받은 영상마다 주인공이 얼마나 나오나 재고, 낮으면 버리고 더 찾는다(gather_sources).
★후보 태깅: 장면 후보마다 누가(주인공/다른사람…)·박힌 자막을 channelkit.vision 으로 재서 고르기(fits)와 프롬프트에 넣는다.
"""
import json
import math
import os
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from shopping_shorts.channelkit import vision
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


def scene_changes(path, x=None, a=None, b=None):
    """소스의 장면 변화 시각(초, 소스 기준). ★렌더와 같은 픽셀 사슬(render.clip_vf: 크롭 창 x + 프레임률 섞기)을
    절반 크기로 돌린다 — 검수 자(scene>0.3)보다 낮은 문턱. x = render.crop_x(path, face_cx, 절반 크기), None 이면 가운데."""
    from . import render
    vf = (f"{render.clip_vf(spec.SCENE_DETECT_W, spec.SCENE_DETECT_H, x)},"
          f"select='gt(scene,{spec.SCENE_DETECT_THRESH})',metadata=print:file=-")
    win = (["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}"] if a is not None else [])
    r = _run(["ffmpeg", "-v", "error"] + win + ["-i", path, "-vf", vf, "-an", "-f", "null", "-"], timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"footage.scene_changes: {os.path.basename(path)} — {r.stderr[-200:]}")
    off = a or 0.0
    return sorted({round(off + float(l.split("pts_time:")[1]), 3) for l in r.stdout.splitlines() if "pts_time:" in l})


def split_spans(changes, lo, hi):
    """★장면 변화 → 쓸 수 있는 구간 [(a,b)] — 유일한 판단(처음 자르기·크롭 뒤 다시 자르기 둘 다).
    SCENE_BURST_GAP 초 안에 이어지는 변화는 한 덩어리(깜빡임·플래시·빠른 편집)로 보고 그 덩어리 전체를 뺀다.
    앞뒤 CLIP_INSET_SEC 는 안 쓴다."""
    ch = sorted(c for c in changes if lo < c < hi)
    clusters = []
    for c in ch:
        if clusters and c - clusters[-1][1] < spec.SCENE_BURST_GAP:
            clusters[-1][1] = c
        else:
            clusters.append([c, c])
    edges = [(lo, lo)] + [tuple(k) for k in clusters] + [(hi, hi)]
    out = []
    for (_, e0), (s1, _) in zip(edges, edges[1:]):
        a, b = e0 + spec.CLIP_INSET_SEC, s1 - spec.CLIP_INSET_SEC
        if b > a:
            out.append((math.ceil(round(a * 100, 6)) / 100, math.floor(round(b * 100, 6)) / 100))   # 경계 밖 프레임이 안 들어오게
    return out


def scenes(path, vid, thumbs_dir):
    """장면 자르기 → [{vid,path,start,end,thumb,t}]. 너무 짧거나 어두운 장면·첫 3% 제외. (가운데 크롭으로 한 번 —
    얼굴 크롭이 정해지면 tag_candidates 가 그 크롭으로 다시 자른다.) start/end = 쓸 수 있는 구간."""
    from . import render
    _, _, dur = _dims(path)
    os.makedirs(thumbs_dir, exist_ok=True)
    out = []
    for a, b in split_spans(scene_changes(path), 0.0, dur):
        if b - a < spec.POLICY_SCENE_MIN_SEC or a < dur * 0.03:
            continue
        t = a + min(0.8, (b - a) / 2)
        th = os.path.join(thumbs_dir, f"{vid}_{int(a * 100):06d}.jpg")
        # 썸네일 = 렌더와 같은 슬롯 크롭(아래 18% 버림). 태깅 뒤 얼굴 중심 크롭으로 다시 쓴다(tag_candidates)
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
              "-vf", render.slot_vf(THUMB_W, THUMB_H), th], timeout=60)
        if not os.path.exists(th):
            continue
        im = Image.open(th).convert("L")
        if float(np.asarray(im).mean()) < 22:           # 거의 검정(암전·자막 카드)
            continue
<<<<<<< HEAD
        out.append({"vid": vid, "path": path, "start": a, "end": b, "thumb": th, "t": round(t, 2)})
=======
        # start 는 올림, end 는 내림 — 반올림으로 경계 밖 프레임이 들어오지 않게
        out.append({"vid": vid, "path": path, "start": math.ceil(a * 100) / 100, "end": math.floor(b * 100) / 100, "thumb": th,
                    "t": round(t, 2)})
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
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


def _as_int(v):
    """모델이 번호를 "108"(문자열)로 주기도 한다(3.1-flash-lite 실측) — 정수로."""
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def describe(cands, sheet_paths, reader, log=print):
    """시트 한 장씩 → {번호: 짧은 장면 설명}. 그림 보는 일은 이것만 시킨다.

    ★왜 나눴나(2026-09-25 실측): 120칸 시트 4장 + 자막 26개를 한 번에 주면 두 모델 모두
      picks 를 10,11,12,…처럼 **순서대로 찍었다** — 대조를 안 한다. 한 장(30칸)씩 '무엇이 보이나'만
      묻고, 자막과의 짝짓기는 글 대조로 따로 한다."""
    per = SHEET_COLS * SHEET_ROWS
    desc = {}
    for si, sp in enumerate(sheet_paths):
        lo, hi = si * per, min(len(cands), (si + 1) * per) - 1
        prompt = (f"그림은 번호(노란 숫자 {lo}~{hi}) 붙은 영상 장면 썸네일이다. 각 번호마다 **보이는 것**을 영어 10단어 이내로 적어라: "
                  "누가(여자 배드민턴 선수/코치/관중/아이…) · 무엇을(경기 중 스매시/시상대/우는/인터뷰/훈련/걷는…) · 어디(경기장/시장/부엌/거리…). "
                  "화면에 문장 자막이 박혀 있으면 끝에 [TEXT]. 로고·검은 화면이면 [JUNK].\n"
                  f"출력 JSON: {{\"desc\": {{\"{lo}\": \"...\", …, \"{hi}\": \"...\"}}}}")
        r = _call(reader, prompt, [sp], log, "desc") or {}
        for k, v in (r.get("desc") or {}).items():
            n = _as_int(k)
            if n is not None and lo <= n <= hi:
                desc[n] = str(v)
    log(f"[footage] 장면 설명 {len(desc)}/{len(cands)}개")
    return desc


def need_sec(g):
    """자막 하나가 화면에 떠 있는 시간 = 그 자막이 쓸 장면의 최소 길이. 판단은 rules.sub_seconds 하나."""
    from . import rules
    return rules.sub_seconds(g.get("text") or " ".join(g.get("lines") or []))


def fits(c, g):
    """★장면 c 를 자막 g 에 써도 되나 — **유일한 판단 자리**(pick 의 모델 답 검사·메우기, check_and_repick 이 다 이것).
    ① 칼카피 1: 장면 경계 안에서 자막 시간을 다 채우나(길이 정보 없는 후보 = 테스트 더미는 통과).
<<<<<<< HEAD
    ② 규칙 10: 주인공 자막(rules.subject == main)엔 "다른사람" 얼굴 장면 금지.
    ③ 규칙 8: 자막꼴 박힌 글자 장면은 **모든 자막에** 금지 — 관문은 편 전체 ≤1컷이다. 주인공 자막만 막았더니
       우상혁 v2에서 scene 자막(컷14)에 박힌 자막 후보가 골려 관문에 걸렸다(고르기와 관문이 다른 규칙). 태깅 안 된 후보는 통과."""
=======
    ② 규칙 8·10: 주인공 자막(rules.subject == main)엔 "다른사람" 얼굴·자막꼴 박힌 글자 장면 금지. 태깅 안 된 후보는 통과."""
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
    from . import rules
    if not isinstance(c, dict):
        return True
    if "end" in c and "start" in c and c["end"] - c["start"] < need_sec(g):
        return False
<<<<<<< HEAD
    if c.get("subtitle_like"):
        return False
    if rules.subject(g) == "main" and c.get("who") == vision.WHO_OTHER:
=======
    if rules.subject(g) == "main" and (c.get("who") == vision.WHO_OTHER or c.get("subtitle_like")):
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
        return False
    return True


def cand_tags(c):
    """후보 태깅 → 프롬프트 표식. 그림 모델에게 누가 나오는지 묻지 않는다 — 자(vision)가 잰 것을 글로 준다."""
    if not isinstance(c, dict) or "who" not in c:
        return ""
    t = {vision.WHO_MAIN: "[주인공 얼굴 큼]", vision.WHO_OTHER: "[다른 사람]", vision.WHO_UNSURE: "[누군지 불확실]",
         vision.WHO_SMALL: "[얼굴 작음]", vision.WHO_NONE: "[얼굴 없음]"}.get(c["who"], "")
    return t + ("[박힌 자막]" if c.get("subtitle_like") else "")


_SUBJECT_NOTE = {"main": "[주인공 장면 필수]", "other": "[다른 인물 가능]", "scene": "[사람 없어도 됨]"}


def _match_prompt(groups, desc, person, cands=None):
    from . import rules
    subs = "\n".join(f"{i}. {_SUBJECT_NOTE[rules.subject(g)]} 자막 «{g.get('text')}» ({need_sec(g)}초 이상 장면) / 원하는 화면: {g.get('scene', '')}"
                     for i, g in enumerate(groups))

    def ln(k):
        c = cands[k] if cands and 0 <= k < len(cands) else None
        tg = cand_tags(c)
        return (f" ({c['end'] - c['start']:.1f}초)" if isinstance(c, dict) and "end" in c else "") + (f" {tg}" if tg else "")
    scenes_ = "\n".join(f"{k}{ln(k)}: {v}" for k, v in sorted(desc.items()))
    return (f"숏폼 편집자다. 주인공 {person}. [자막]마다 [장면 목록]에서 **내용이 가장 맞는** 장면 번호를 골라라.\n"
            "규칙: 같은 번호 두 번 금지. 장면 길이(초)가 자막이 요구하는 초보다 짧으면 쓰지 마라. 경기·결승·메달 자막엔 경기장/시상대 장면, 어린 시절·가족 자막엔 그에 맞는 장면. "
            "[TEXT]·[JUNK] 장면은 다른 게 정말 없을 때만. 시장·부엌 등 주제와 무관한 장면은 쓰지 마라. 번호를 순서대로 찍지 마라.\n"
<<<<<<< HEAD
            "장면 표식은 얼굴 인식기가 잰 것이다: [박힌 자막] 장면은 어느 자막에도, [다른 사람] 장면은 [주인공 장면 필수] 자막에 **절대** 쓰지 마라(골라도 버려진다). "
=======
            "장면 표식은 얼굴 인식기가 잰 것이다: [주인공 장면 필수] 자막엔 [다른 사람]·[박힌 자막] 장면을 **절대** 쓰지 마라(골라도 버려진다). "
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
            "[주인공 얼굴 큼] 장면을 우선하라. [얼굴 작음]·[얼굴 없음]은 경기장·풍경처럼 넓은 화면에만.\n"
            f"[장면 목록]\n{scenes_}\n\n[자막]\n{subs}\n\n"
            f"출력 JSON: {{\"picks\": [자막0의 장면번호, 자막1의 장면번호, …]}} (정확히 {len(groups)}개)")


def pick(groups, cands, sheet_paths, reader, person, log=print):
    """→ (자막마다 장면 index, 보정 수). 설명(그림) → 짝짓기(글). 모델 답이 틀리면 남는 장면으로 순서대로 메운다."""
    picks = []
    if reader is not None and cands:
        # 503(과부하)은 잠깐 뒤 풀린다 — 2026-09-25 실측 첫 시도 503. 재시도·대체 모델은 _call 한 곳에서
        desc = describe(cands, sheet_paths, reader, log=log)
        if desc:
            r = _call(reader, _match_prompt(groups, desc, person, cands), [], log, "picks") or {}
            picks = [_as_int(p) for p in (r.get("picks") or [])]
    used, out, fixed = set(), [], 0
    for i in range(len(groups)):
        p = picks[i] if i < len(picks) else None
        if not isinstance(p, int) or not 0 <= p < len(cands) or p in used or not fits(cands[p], groups[i]):
            p = next((k for k in range(len(cands)) if k not in used and fits(cands[k], groups[i])), None)
            fixed += 1
            if p is None:                   # 맞는 길이의 장면이 없다 — 재사용하지 않고 멈춘다(자막 안 컷이 생긴다)
                raise RuntimeError(f"footage: 자막 {i}({need_sec(groups[i])}초)에 맞는 길이의 남은 장면이 없다 — 영상을 더 받아라")
        used.add(p)
        out.append(p)
    if fixed:
        log(f"[footage] 모델 답 {fixed}/{len(groups)}개를 순서대로 메움")
    seq = sum(1 for a_, b_ in zip(out, out[1:]) if b_ == a_ + 1)
    log(f"[footage] 연속 번호 비율 {seq}/{max(1, len(out) - 1)} — 높으면 대조 안 하고 순서대로 찍은 것")
    return out, fixed


# ── 소스 자 ─────────────────────────────────────────────────────────────────
def source_queries(script):
    """검색어 = 인물명+한국어(경기·인터뷰·하이라이트·다큐)와 대본 검색어를 번갈아. v001은 영어 3개뿐이라 종합 하이라이트가 잡혔다."""
    person = (script.get("person") or "").strip()
    ko = [f"{person} {s}" for s in spec.POLICY_SOURCE_KO_QUERIES] if person else []
    sq = [q for q in (script.get("queries") or []) if isinstance(q, str) and q.strip()]
    out = []
    for i in range(max(len(ko), len(sq))):
        for q in ko[i:i + 1] + sq[i:i + 1]:
            if q not in out:
                out.append(q)
    return out


def title_blocked(title):
    """제목으로 먼저 버릴 소스(토크쇼·리액션·팟캐스트·Day N Highlights·모음) → 걸린 말 또는 None."""
    m = re.search(spec.POLICY_SOURCE_TITLE_BLOCK, title or "")
    return m.group(0) if m else None


def source_faces(path, log=print):
    """소스 한 편 → {"n": 표본 프레임 수, "faces": [[프레임번호, x, y, w, h], …], "emb": (N,128)}.
    표본 = 덮개 그림(render.cover_vf, 슬롯 절반 크기)에서 POLICY_SOURCE_SAMPLE_SEC 초마다 한 장. 결과는 옆에 .faces.npz 로 둔다."""
    from . import render
    cache = path[:-4] + ".faces.npz"
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
        z = np.load(cache)
        return {"n": int(z["n"]), "faces": z["faces"].tolist(), "emb": z["emb"]}
    W, H = spec.POLICY_SOURCE_SAMPLE_W, spec.POLICY_SOURCE_SAMPLE_H
    ch, cw = render.cover_frame(path, 0.0, W, H).shape[:2]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          f"{render.cover_vf(W, H)},fps=1/{spec.POLICY_SOURCE_SAMPLE_SEC}", "-an",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    n, faces, embs, size = 0, [], [], cw * ch * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(ch, cw, 3)
        for f, e in vision.faces_all(fr, min_h=0):
            if e is not None:
                faces.append([n, f["x"], f["y"], f["w"], f["h"]])
                embs.append(e)
        n += 1
    err = p.stderr.read().decode("utf-8", "replace")
    if p.wait() != 0 or n == 0:
        raise RuntimeError(f"footage.source_faces: {os.path.basename(path)} 표본 실패(프레임 {n}) — {err[-200:]}")
    emb = np.asarray(embs, np.float32).reshape(-1, 128)
    np.savez(cache, n=n, faces=np.asarray(faces, np.float32).reshape(-1, 5), emb=emb)
    log(f"[footage] 소스 표본 {os.path.basename(path)}: 프레임 {n} · 얼굴 {len(faces)}")
    return {"n": n, "faces": faces, "emb": emb}


def source_ruler(videos, wd=None, log=print):
    """소스들 → {"anchor": 주인공 임베딩, "support": 짝 수, "anchor_from": [vid, 초], "per": {vid: {main_ratio, face_h, frames}}}.
    주인공 = 판정 가능 얼굴(높이 ≥ vision.JUDGE_H) 중 **여러 영상에 공통으로** 가장 많이 짝지어지는 얼굴.
    main_ratio = 주인공(vision.who == 주인공)이 보인 표본 프레임 비율. face_h = 얼굴 있는 프레임의 가장 큰 얼굴 높이 평균."""
    data = {v["id"]: source_faces(v["path"], log=log) for v in videos}
    embs, groups, where = [], [], []
    for vid, d in data.items():
        for (fi, x, y, w, h), e in zip(d["faces"], d["emb"]):
            if h >= vision.JUDGE_H:
                embs.append(e)
                groups.append(vid)
                where.append((vid, int(fi), x, y, w, h))
    k, anc, support = vision.protagonist_embedding(embs, groups)
    if k is None or support == 0:
        raise RuntimeError(f"footage: 소스 {len(videos)}편에서 주인공 얼굴을 못 정했다(판정 가능 얼굴 {len(embs)}개, 짝 {support}) "
                           "— 인물 얼굴이 나오는 영상이 없다. 검색어를 바꿔 script부터")
    per = {}
    for vid, d in data.items():
        main, judged, big = set(), set(), {}
        for (fi, x, y, w, h), e in zip(d["faces"], d["emb"]):
            big[fi] = max(big.get(fi, 0.0), h)
            if h >= vision.JUDGE_H:
                judged.add(fi)
            if vision.who({"h": h}, e, anc) == vision.WHO_MAIN:
                main.add(fi)
        per[vid] = {"main_ratio": round(len(main) / max(1, d["n"]), 3), "judged_ratio": round(len(judged) / max(1, d["n"]), 3),
                    "frames": d["n"], "face_h": round(float(np.mean(list(big.values()))), 3) if big else 0.0}
    avid, afi, ax, ay, aw, ah = where[k]
    out = {"anchor": anc, "support": support, "anchor_from": [avid, round(afi * spec.POLICY_SOURCE_SAMPLE_SEC, 1)], "per": per}
    if wd:
        from . import render
        fd = os.path.join(wd, "footage")
        os.makedirs(fd, exist_ok=True)
        np.save(os.path.join(fd, "anchor.npy"), anc)
        src = next(v["path"] for v in videos if v["id"] == avid)
        fr = render.cover_frame(src, afi * spec.POLICY_SOURCE_SAMPLE_SEC, spec.POLICY_SOURCE_SAMPLE_W, spec.POLICY_SOURCE_SAMPLE_H)
        Hh, Ww = fr.shape[:2]
        x0, y0 = max(0, int((ax - aw * 0.3) * Ww)), max(0, int((ay - ah * 0.3) * Hh))
        x1, y1 = min(Ww, int((ax + aw * 1.3) * Ww)), min(Hh, int((ay + ah * 1.3) * Hh))
        Image.fromarray(np.ascontiguousarray(fr[y0:y1, x0:x1, ::-1])).save(os.path.join(fd, "anchor.png"))   # 사람이 볼 주인공 얼굴
    return out


def judge_sources(per, cap=None):
    """★소스를 쓸지 버릴지의 유일한 판단 → (쓸 id 목록(per 순서 = 받은 순서, 상한 cap), {id: 버린 사유}).
    버림 = 큰 얼굴(판정 가능)이 POLICY_SOURCE_WIDE_JUDGED_MAX 이상 나오는데 주인공 비율이 POLICY_SOURCE_MIN_MAIN_RATIO 미만
    (= 다른 사람 영상: 대회 종합 하이라이트·토크쇼). 넓은 경기 중계(큰 얼굴 거의 없음)는 증거가 없으니 둔다.
    ★상한은 받은 순서(검색 순위)로 자른다 — 주인공 비율 순으로 자르면 넓은 화면 결승 중계가 먼저 잘린다."""
    cap = spec.POLICY_FOOTAGE_MAX_VIDEOS if cap is None else cap
    ok, why = [], {}
    for v, p in per.items():
        if p["main_ratio"] >= spec.POLICY_SOURCE_MIN_MAIN_RATIO or p.get("judged_ratio", 1.0) < spec.POLICY_SOURCE_WIDE_JUDGED_MAX:
            ok.append(v)
        else:
            why[v] = (f"큰 얼굴 {p.get('judged_ratio', 1.0):.0%} 중 주인공 {p['main_ratio']:.1%} < "
                      f"{spec.POLICY_SOURCE_MIN_MAIN_RATIO:.0%} — 다른 사람 영상")
    why.update({v: f"상한 {cap}편 초과" for v in ok[cap:]})
    return ok[:cap], why


def gather_sources(script, wd, log=print):
    """검색 → 제목 거르기 → 받기 → 소스 자 → 버리고 더 찾기. → (쓸 소스 [meta…], ruler, 기록 표).
    쓸 소스가 상한(POLICY_FOOTAGE_MAX_VIDEOS)에 차면 멈추고, 검색어를 다 써도 POLICY_SOURCE_MIN_USABLE 미만이면 **에러**.
    기록: footage/sources.json (영상마다 제목·검색어·상태·주인공 비율) — 문제 소스를 사람이 볼 수 있게."""
    vdir = os.path.join(wd, "footage", "videos")
    os.makedirs(vdir, exist_ok=True)
    mp = os.path.join(wd, "footage", "sources.json")
    meta = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    # 재개: 받아 둔 mp4 중 기록이 없는 것(옛 작업 폴더) — 제목을 모르니 제목 거르기는 못 한다
    for f in sorted(os.listdir(vdir)):
        if f.endswith(".mp4") and f[:-4] not in meta:
            meta[f[:-4]] = {"id": f[:-4], "title": "", "duration": 0, "query": "(받아 둔 것)",
                            "url": f"https://www.youtube.com/watch?v={f[:-4]}", "path": os.path.join(vdir, f), "status": "받음"}
    cap = spec.POLICY_FOOTAGE_MAX_VIDEOS

    def save():
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)

    def measure():
        got = [m for m in meta.values() if m.get("path") and os.path.exists(m["path"])]
        if len(got) < 2:                        # 주인공 = "여러 영상에 공통인 얼굴" — 한 편으로는 못 정한다
            save()
            return [], None
        r = source_ruler(got, wd=wd, log=log)
        keep, why = judge_sources(r["per"], cap)
        for m in got:
            m.update(r["per"][m["id"]])
            m["status"] = "씀" if m["id"] in keep else f"버림({why[m['id']]})"
        save()
        return keep, r

    keep, ruler = measure()
    tries = sum(1 for m in meta.values() if not str(m.get("status", "")).startswith("제목 차단"))
    for q in source_queries(script):
        if len(keep) >= cap or tries >= spec.POLICY_SOURCE_MAX_DOWNLOADS:
            break
        new = 0
        for it in search(q, spec.POLICY_FOOTAGE_PER_QUERY + 1, log=log):
            if it["id"] in meta:
                continue
            blk = title_blocked(it["title"])
            if blk:
                meta[it["id"]] = dict(it, query=q, path=None, status=f"제목 차단({blk})")
                log(f"[footage] 제목 차단 «{it['title'][:50]}» ({blk})")
                continue
            if tries >= spec.POLICY_SOURCE_MAX_DOWNLOADS:
                break
            tries += 1
            p = download(it, vdir, log=log)
            meta[it["id"]] = dict(it, query=q, path=p, status="받음" if p else "다운로드 실패")
            if p:
                new += 1
                log(f"[footage] 받음 {it['id']} «{it['title'][:40]}» ({q})")
        if new:
            keep, ruler = measure()
            log(f"[footage] 소스 자: 쓸 소스 {len(keep)}/{cap} — " + ", ".join(
                f"{m['id']} {m['main_ratio']:.0%}" for m in meta.values() if m.get("main_ratio") is not None))
    save()
    table = [{k: m.get(k) for k in ("id", "title", "query", "status", "main_ratio", "judged_ratio", "face_h", "frames")} for m in meta.values()]
    if len(keep) < spec.POLICY_SOURCE_MIN_USABLE:
        raise RuntimeError(f"footage: 주인공이 나오는 소스 {len(keep)}편 < {spec.POLICY_SOURCE_MIN_USABLE}편 (받아 본 것 {tries}편) — "
                           f"footage/sources.json 참고. 표: {json.dumps(table, ensure_ascii=False)[:1500]}")
    return [meta[k] for k in keep], ruler, table


<<<<<<< HEAD
def tag_times(start, end):
    """태깅 프레임 시각 — 렌더가 쓰는 창(앞에서 최대 SUB_SEC_MAX초)의 시작+0.3 · 가운데 · 끝−0.3.
    관문은 렌더된 컷의 가운데(시작+0.65~1.55초)를 보므로 그 앞뒤를 덮는다."""
    L = min(end - start, spec.SUB_SEC_MAX)
    e = spec.TAG_EDGE_SEC
    return sorted({round(start + min(e, L / 2), 2), round(start + L / 2, 2), round(start + max(L - e, L / 2), 2)})


def combine_tags(frames, anchor):
    """★여러 프레임 → 후보 하나의 표식 — 유일한 판단. frames = [(t, vision.look 결과)].
    박힌 자막 = 한 장이라도 있으면. 누구 = 가장 큰 얼굴 프레임의 판정, **단 한 장이라도 '다른사람'이면 다른사람**
    (관문은 그 창 안 아무 한 장을 본다 — 큰 얼굴이 주인공이어도 다른 장에 다른 사람이 크게 나오면 ⑩에 걸린다).
    → {who, face_h, cx_off, subtitle_like, sub_t, who_t: [(t, who)]}"""
    whos = [(t, vision.who(lk["box"], lk["emb"], anchor)) for t, lk in frames]
    faced = [(lk["face_h"], t, lk, w) for (t, lk), (_, w) in zip(frames, whos) if lk["face"]]
    if faced:
        _, _, lk, w = max(faced, key=lambda q: q[0])
    else:
        lk, w = {"face_h": None, "cx_off": None}, vision.WHO_NONE
    other_t = [t for t, x in whos if x == vision.WHO_OTHER]
    sub_t = [t for t, lk_ in frames if lk_["sub_like"]]
    return {"who": vision.WHO_OTHER if other_t else w, "face_h": lk["face_h"], "cx_off": lk["cx_off"],
            "subtitle_like": bool(sub_t), "sub_t": sub_t, "who_t": whos}


def tag_candidates(cands, anchor, min_len=0.0, log=print):
    """★후보마다 ① 쓸 창 세 프레임의 덮개 그림에서 가장 큰 얼굴 → face_cx ② **그 크롭 창으로** 장면을 다시 자른다
    (render.clip_vf·render.crop_x — 렌더와 같은 그림; 가운데 크롭에선 안 보이던 변화가 창을 옮기면 들어온다)
    ③ 다시 자른 창의 세 프레임을 자(vision)로 재서 combine_tags. 다시 자른 조각 중 min_len 이상인 가장 앞 조각을 쓰고, 없으면 버린다.
    썸네일은 가운데 프레임 슬롯 그림(시트 = 렌더 화면). → 남은 후보 목록."""
    from collections import Counter
    from . import render
    out, dropped = [], 0
    for i, c in enumerate(cands):
        covers = [(t, render.cover_frame(c["path"], t)) for t in tag_times(c["start"], c["end"])]
        bigs = [f for _, cv in covers for f in [vision.biggest(vision.faces(cv))] if f]
        big = max(bigs, key=lambda f: f["h"]) if bigs else None
        c["face_cx"] = round(big["x"] + big["w"] / 2, 4) if big else None
        xh = render.crop_x(c["path"], c["face_cx"], spec.SCENE_DETECT_W, spec.SCENE_DETECT_H)
        lo, hi = c["start"] - spec.CLIP_INSET_SEC, c["end"] + spec.CLIP_INSET_SEC
        spans = split_spans(scene_changes(c["path"], xh, lo, hi), lo, hi)
        need = max(min_len, spec.POLICY_SCENE_MIN_SEC)
        # 쓸 만한 조각 중 **가장 앞**(모델이 본 썸네일·설명이 앞쪽 프레임이다)
        best = next((ab for ab in spans if ab[1] - ab[0] >= need), None)
        if not best:
            dropped += 1
            log(f"[footage] 후보 버림 {c['vid']} {c['start']}~{c['end']}: 크롭 창으로 다시 자르니 {spans} — 자막 최소 {need}초 미만")
            continue
        if best != (c["start"], c["end"]):
            c["coarse"] = [c["start"], c["end"]]
            c["start"], c["end"] = best
        x = render.crop_x(c["path"], c["face_cx"])
        ts = tag_times(c["start"], c["end"])
        slots = [render.slot_from_cover(render.cover_frame(c["path"], t), x) for t in ts]
        frames = [(t, vision.look(sl)) for t, sl in zip(ts, slots)]
        mid = slots[len(slots) // 2]
        tg = combine_tags(frames, anchor)
        c.update(crop_x=x, **tg)
        Image.fromarray(np.ascontiguousarray(mid[:, :, ::-1])).resize((THUMB_W, THUMB_H)).save(c["thumb"])
        out.append(c)
        if i % 20 == 19:
            log(f"[footage] 후보 태깅 {i + 1}/{len(cands)}")
    log(f"[footage] 후보 태깅: {dict(Counter(c['who'] for c in out))} · 박힌 자막 {sum(c['subtitle_like'] for c in out)} · "
        f"크롭 창 다시 자르기로 버림 {dropped} · 창이 줄어든 후보 {sum(1 for c in out if 'coarse' in c)}")
    return out
=======
def tag_candidates(cands, anchor, log=print):
    """★후보마다 렌더와 같은 그림(cover_frame → face_crop_x → slot_from_cover)을 만들어 자(vision)로 잰다.
    c 에 crop_x·who·face_h·cx_off·subtitle_like 를 넣고 썸네일을 그 슬롯 그림으로 다시 쓴다(시트 = 렌더 화면)."""
    from collections import Counter
    from . import render
    for i, c in enumerate(cands):
        cover = render.cover_frame(c["path"], c.get("t", c["start"]))
        big = vision.biggest(vision.faces(cover))
        x = render.face_crop_x(cover.shape[1], spec.SLOT_W, (big["x"] + big["w"] / 2) if big else None)
        slot = render.slot_from_cover(cover, x)
        lk = vision.look(slot)
        c.update(crop_x=x, who=vision.who(lk["box"], lk["emb"], anchor), face_h=lk["face_h"], cx_off=lk["cx_off"],
                 subtitle_like=bool(lk["sub_like"]))
        Image.fromarray(np.ascontiguousarray(slot[:, :, ::-1])).resize((THUMB_W, THUMB_H)).save(c["thumb"])
        if i % 20 == 19:
            log(f"[footage] 후보 태깅 {i + 1}/{len(cands)}")
    log(f"[footage] 후보 태깅: {dict(Counter(c['who'] for c in cands))} · 박힌 자막 {sum(c['subtitle_like'] for c in cands)}")
    return cands
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f


def collect(script, wd, reader=None, log=print):
    """→ {"videos", "sources", "anchor"(npy), "cuts":[{…}], "sheets", "fixed", "verify"}. 컷 = 자막 순서."""
    tdir = os.path.join(wd, "footage", "thumbs")
    videos, ruler, table = gather_sources(script, wd, log=log)
    cands = []
    for v in videos:
        cands += scenes(v["path"], v["id"], tdir)
    groups = script.get("groups") or []
    shortest = min((need_sec(g) for g in groups), default=spec.SUB_SEC_MIN)
    cands = [c for c in cands if c["end"] - c["start"] >= shortest]     # 어떤 자막도 못 채우는 장면은 시트에서 뺀다
    cands = _even(cands, SHEET_COLS * SHEET_ROWS * MAX_SHEETS)
    log(f"[footage] 영상 {len(videos)}편 · 장면 후보 {len(cands)}개")
<<<<<<< HEAD
    cands = tag_candidates(cands, ruler["anchor"], min_len=shortest, log=log)
=======
    tag_candidates(cands, ruler["anchor"], log=log)
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
    sp = sheets(cands, os.path.join(wd, "footage"))
    idx, fixed = pick(groups, cands, sp, reader, script.get("person", ""), log=log)
    if reader is not None and fixed > len(groups) * 0.3:
        # ★조용히 순서대로 메운 영상을 "완료"로 내보내지 마라(2026-09-25: 503으로 27/27 순서 메움 → 요리 장면이 섞였다)
        raise RuntimeError(f"footage: 장면 선택 모델이 {fixed}/{len(groups)}개를 못 골랐다 — 잠시 뒤 footage부터 다시")
    verify = {"bad": [], "repicked": 0}
    if reader is not None:
        idx, verify = check_and_repick(groups, cands, idx, sp, reader, script.get("person", ""), wd, log=log)
    url = {v["id"]: v["url"] for v in videos}
    # 컷 = 자막 1:1, 각 컷은 한 장면 [start, start+자막초] 안(render.build 가 넘으면 멈춘다)
    cuts = [{"scene": k, "src": cands[k]["path"], "start": cands[k]["start"], "end": cands[k]["end"],
             "vid": cands[k]["vid"], "url": url.get(cands[k]["vid"]), "thumb": cands[k]["thumb"],
<<<<<<< HEAD
             "crop_x": cands[k]["crop_x"], "face_cx": cands[k]["face_cx"], "who": cands[k]["who"],
             "subtitle_like": cands[k]["subtitle_like"], "sub_t": cands[k]["sub_t"], "who_t": cands[k]["who_t"]} for k in idx]
=======
             "crop_x": cands[k]["crop_x"], "who": cands[k]["who"], "subtitle_like": cands[k]["subtitle_like"]} for k in idx]
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
    return {"videos": [{k: v.get(k) for k in ("id", "title", "url", "query", "duration", "main_ratio")} for v in videos],
            "sources": table, "anchor": os.path.join(wd, "footage", "anchor.npy"), "anchor_from": ruler["anchor_from"],
            "n_cands": len(cands), "cuts": cuts, "sheets": sp, "fixed": fixed, "verify": verify}


def _call(readers, prompt, images, log, key):
    """모델 여러 개를 순서대로, 503이면 잠깐 쉬고 재시도. 답에 `key`가 없으면 **실패로 치고** 다음으로.
    → 파싱된 dict 또는 None.

    ★2026-09-25 실측: 에러 없이 돌아온 답을 모양 확인 없이 받아 `picks`가 비었고, 대체 모델로 안 넘어가
      26/26개를 못 골랐다(대체 모델은 멀쩡히 응답하던 때)."""
    import time
    from shopping_shorts.channelkit.prompt import parse_any
    for ri, rd in enumerate(readers if isinstance(readers, (list, tuple)) else [readers]):
        for wait in (0, 10, 30):
            if wait:
                time.sleep(wait)
            try:
                raw = rd(prompt, images)
                r = parse_any(raw) or {}
                if isinstance(r, dict) and key in r:
                    return r
                log(f"[footage] 모델{ri} 답에 «{key}» 없음 — 다시: {str(raw)[:160]!r}")
            except Exception as e:  # noqa: BLE001
                log(f"[footage] 모델{ri} 실패({wait}s 뒤 재시도): {repr(e)[:160]}")
    return None


def picked_sheet(groups, cands, idx, out_png):
    """고른 장면을 자막 번호·자막 글과 함께 한 장에 — 검사용."""
    font = ImageFont.truetype(spec.LOGO_NAME_FONT, 18)
    big = ImageFont.truetype(spec.LOGO_NAME_FONT, 26)
    tw, th = THUMB_W, THUMB_H + 48
    sh = Image.new("RGB", (SHEET_COLS * (tw + 6), ((len(idx) + SHEET_COLS - 1) // SHEET_COLS) * (th + 6)), "white")
    d = ImageDraw.Draw(sh)
    for i, k in enumerate(idx):
        x, y = (i % SHEET_COLS) * (tw + 6), (i // SHEET_COLS) * (th + 6)
        sh.paste(Image.open(cands[k]["thumb"]).convert("RGB"), (x, y))
        d.rectangle([x, y, x + 40, y + 32], fill="black"); d.text((x + 5, y + 2), str(i), font=big, fill="yellow")
        d.text((x + 2, y + THUMB_H + 2), (groups[i].get("text") or "")[:26], font=font, fill="black")
    sh.save(out_png)
    return out_png


def verify_picks(groups, cands, idx, reader, person, wd, name="picked.png", log=print):
    """고른 장면을 자막과 함께 한 장에 그려 모델에게 **자막 내용과 안 맞는 칸**을 묻는다 → 틀린 자막 번호 목록.
    ★답이 없으면 에러 — 검사 없이 통과시키지 않는다(예전엔 None 을 "틀린 칸 없음"으로 읽었다)."""
    chk = picked_sheet(groups, cands, idx, os.path.join(wd, "footage", name))
    prompt = (f"숏폼 검수자다. 주인공 {person}. 그림의 각 칸 = 자막 번호(노란 숫자)와 그 자막 글(칸 아래).\n"
              "장면이 **자막 내용과 안 맞는** 칸만 골라라 — 예: 경기·결승·메달 얘기인데 시장·요리·일상 장면, "
              "주인공 얘기인데 다른 선수·토크쇼·로고 화면. 어린 시절 얘기인데 성인 경기 장면은 괜찮다(비슷하면 통과). 확실히 틀린 것만.\n"
              "출력 JSON: {\"bad\": [번호, …]}")
    r = _call(reader, prompt, [chk], log, "bad")
    if r is None:
        raise RuntimeError("footage: 장면 검사 모델이 답을 못 줬다 — 검사 없이 넘기지 않는다(잠시 뒤 footage부터)")
    return sorted({b for b in (_as_int(x) for x in (r.get("bad") or [])) if b is not None and 0 <= b < len(idx)})


def check_and_repick(groups, cands, idx, sheet_paths, reader, person, wd, log=print):
    """고른 뒤 **자막 내용과 맞는지** 한 번 더 본다 → 틀린 자막만 남은 장면에서 다시 고른다 → **다시 고른 결과를 또 검사**.
    → (idx, {"bad": 첫 검사 틀림, "repicked": 바꾼 수, "bad_final": 최종 틀림}). 관문(review.content_gate)은 bad_final 을 본다.

    ★왜: 2026-09-25 안세영 편 — "허빙자오를 2-0으로 꺾고 금메달"에 **본인 브이로그의 시장 장면**이 골렸다.
    ★2026-09-28 우상혁 v001 — 첫 검사 23/23 틀림, 21개를 다시 골랐지만 **다시 검사하지 않고** 렌더했다(토크쇼·다른 선수).
    """
    bad = verify_picks(groups, cands, idx, reader, person, wd, "picked.png", log=log)
    if not bad:
        log("[footage] 장면 검사: 틀린 칸 없음")
        return idx, {"bad": [], "repicked": 0, "bad_final": []}
    used = set(idx)
    free = [k for k in range(len(cands)) if k not in used]
    subs = "\n".join(f"{b}. 자막 «{groups[b].get('text')}» ({need_sec(groups[b])}초 이상 장면) / 원하는 화면: {groups[b].get('scene', '')}"
                     for b in bad)
    tags = "\n".join(f"{k}: {cand_tags(cands[k])}" for k in free if cand_tags(cands[k]))
    prompt2 = (f"숏폼 편집자다. 주인공 {person}. 아래 자막들에 맞는 장면을 시트에서 다시 골라라.\n"
               f"쓸 수 있는 번호: {free}\n같은 번호 두 번 금지. 자막 내용(경기·메달·훈련 등)에 맞는 장면으로.\n"
<<<<<<< HEAD
               + (f"얼굴 인식기 표식([박힌 자막]은 모든 자막에, [다른 사람]은 주인공 자막에 금지):\n{tags}\n" if tags else "") +
=======
               + (f"얼굴 인식기 표식(주인공 자막엔 [다른 사람]·[박힌 자막] 금지):\n{tags}\n" if tags else "") +
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
               f"[자막]\n{subs}\n출력 JSON: {{\"picks\": {{\"자막번호\": 장면번호, …}}}}")
    r2 = _call(reader, prompt2, sheet_paths, log, "picks") or {}
    new, n = list(idx), 0
    for b in bad:
        k = _as_int((r2.get("picks") or {}).get(str(b)))
        if k is not None and k in free and fits(cands[k], groups[b]):
            new[b] = k; free.remove(k); n += 1
    if not r2:
        log("[footage] 다시 고르기 모델이 답을 못 줬다 — 틀린 칸이 그대로 남는다(최종 검사 → 관문이 막는다)")
    bad_final = verify_picks(groups, cands, new, reader, person, wd, "picked_final.png", log=log)
    log(f"[footage] 장면 검사: 틀린 칸 {bad} → 다시 고름 {n}개 → 최종 틀림 {bad_final}")
    return new, {"bad": bad, "repicked": n, "bad_final": bad_final}
