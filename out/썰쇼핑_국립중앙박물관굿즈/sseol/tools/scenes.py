# -*- coding: utf-8 -*-
"""소재 고르기 — 후보 영상마다 작은 사본 한 파일을 구독 AGY 가 한 번 보고 «카드마다 맞는 구간»을 답한다. 고르기·겹침·범위는 코드가 정한다.

    python preset.py scenes <프로젝트>          (대본 script.json 뒤 · `media yt` 로 후보를 받은 뒤)
    → <프로젝트>/scenes.json (카드마다 고른 구간 · 다른 후보 · 못 찾은 카드) + `media clip` 명령 줄

왜(2026-10-23 신고): 옛 순서 안내 3번은 `agy --add-dir <P>/cands` 한 번에 후보 영상 12개(720p 통째 · 개당 최대 10분)를 다 보게 했다.
  한 대화에 수백 MB 를 읽히니 두 번 다 답 없이 끝났다(7분 하위 에이전트 대기 · 25분 시간 초과) — 다시 부르면 같은 양이라 같은 결과다.
  그리고 실행기 agy 통로를 거치지 않아 시간 상한·거부 시 전부 멈춤(전역 6-2)·파일 한도(100MB) 대조가 없었다.
이제:
  - 한 대화 = 한 파일(굽기 전 판정 review.py 와 같은 원칙): 후보 영상마다 360p·영상 90kbps·음성 40kbps 사본(전역 6-1 «≈1MB/분»)을 만든다.
    사본 하나가 한 대화 상한(review.LIMIT)을 넘을 수 있는 긴 영상은 PIECE_SEC 초 조각으로 나눈다(조각마다 원본에서 한 번 굽는다).
  - 조각마다 AGY 한 번(실행기 agy_transport_client.invoke · 셸 권한 없음 · 시간 상한 review.TIMEOUT) — 조각끼리는 동시에(실행기 agy 칸 상한까지).
  - 답은 조각 지문(영상 경로·크기·수정 시각 · 조각 구간 · 카드 문장 · 지시 판)으로 scenes.json 에 남긴다 — 다시 돌리면 답이 없는 조각만 묻는다
    (새로 받은 후보 · 카드 문장이 바뀐 것). 답이 없던 조각은 review.ASK_MAX 번까지만 묻는다(고리 상한). 반려 재질문 없음.
  - 거부(한도·로그인·도구 거부)면 이 실행의 agy 요청을 모두 멈춘다(아직 안 보낸 조각은 보내지 않는다 · 자동 재시도 없음).
  - 코드가 맞춘다: 시작 초 < 영상 길이-2 · 시작+필요 초가 조각 안 · AGY 가 본 시간 안 · 같은 영상의 겹치는 구간 두 번 금지(카드끼리) ·
    뉴스 띠면 crop · 맞음 점수 높은 것부터 카드에 배정(결정적 순서). 효과음은 영상을 볼 필요가 없어 여기서 묻지 않는다(순서 안내 6번).
"""
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

import io_utils
from io_utils import probe, run_enc
from review import ASK_MAX, LIMIT, TIMEOUT, find_agy_runner, agy_model
from tts import syllables

SCENES = "scenes.json"
SCHEMA = "sseol-scenes-v1"
PROMPT_V = 1                         # 지시 글이 바뀌면 올린다(옛 답을 새 지시의 답으로 쓰지 않는다)
VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".m4v")
PH = 360                             # 전역 6-1: 360p · 영상 90kbps · 음성 40kbps ≈ 1MB/분
VBR, ABR = 90_000, 40_000
PFPS = 8                             # 굽기 전 미리보기(review.PFPS)와 같은 초당 장면 수
#: 조각 길이 상한 — 영상 비트 상한(maxrate = 2×VBR · 인코더 자리 slot 과 같은 규칙)+음성으로도 한 대화 상한 LIMIT 을 넘지 않는 길이.
PIECE_SEC = int(LIMIT * 8 // (2 * VBR + ABR))
#: 카드 말 길이 추정 — 순서 안내 2번 «약 330~360음절(40~50초)» 의 가운데(345음절/45초). 렌더 뒤가 아니라 고르기 앞이라 추정이다.
SYL_PER_SEC = 345 / 45
END_ROOM = 2.0                       # 순서 안내 3번 «시작 초 < 길이-2» 와 같은 여유 — 클립 길이도 필요 초 + 이 여유
FRAME_BOX = "1080x880"               # 영상 칸(렌더 MEDIA 칸)

PROMPT = """Do not run commands, do not edit or create files, do not open any other file or folder.
Use your file-reading tool (read_file; older builds call it view_file) to open ONLY this file, once, and watch and listen to all of it
from 0s to the end (about {dur:.1f}s): {name}
It is a small low-resolution copy of a candidate source video ("{title}") for a Korean vertical short about: {topic}
The footage will be shown in a wide landscape box ({box}). News footage gets its top 12% and bottom 25% cropped, so what matters must be in the middle.
Cards (number; seconds the cut must last; the Korean sentence shown over it):
{cards}
For each card where some part of THIS file clearly fits the card's sentence, give the best start second (seconds in this file) of a cut
that lasts at least that card's seconds, stays inside the file, and has no black or frozen picture and no burned subtitles in the middle area.
Leave a card out if nothing in this file fits it. Do not give the same part of the file to two cards.
Answer with ONE JSON object only:
{{"watched_seconds": <number>, "picks": [{{"card": <card number>, "start": <seconds in this file>, "fit": <1-5, 5 = fits perfectly>,
"news_band": <true if the picture has a news ticker/subtitle band at the top or bottom>, "audio": <true only if the clip's own sound
(eating, breaking, crowd, machine) helps; human speech is false>, "what": "<what is seen, a few words>"}}]}}"""


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def need_of(card):
    """카드 컷이 버텨야 하는 초(추정) — 말 음절 수 / SYL_PER_SEC, 0.5초 단위 올림."""
    return math.ceil(2 * syllables(" ".join(card.get("lines") or [])) / SYL_PER_SEC) / 2


def candidates(proj):
    """[(상대 경로, 제목, 길이)] — cands/*/_list.json 의 영상(media yt 가 적은 목록). 이름 정렬로 결정적."""
    root, out = os.path.join(proj, "cands"), []
    for d in sorted(os.listdir(root)) if os.path.isdir(root) else ():
        lp = os.path.join(root, d, "_list.json")
        if not os.path.isfile(lp):
            continue
        with open(lp, encoding="utf-8") as fh:
            for e in json.load(fh):
                p = e.get("file") or ""
                if os.path.splitext(p)[1].lower() in VIDEO_EXT and os.path.isfile(p):
                    out.append((os.path.relpath(p, proj).replace("\\", "/"), str(e.get("title") or ""), float(e.get("duration") or 0)))
    return out


def pieces(proj, vids, cards_sha):
    """[조각] — 영상마다 길이를 한 번 재서(ffprobe) PIECE_SEC 이하 조각으로. 조각 지문 = 영상 경로·크기·수정 시각·구간·카드 문장·지시 판."""
    out = []
    for rel, title, _listed in vids:
        path = os.path.join(proj, rel)
        st = os.stat(path)
        w, h, dur, _fps = probe(path)
        n = max(1, math.ceil(dur / PIECE_SEC))
        step = dur / n
        for k in range(n):
            a, b = round(k * step, 3), round(dur if k + 1 == n else (k + 1) * step, 3)
            key = _sha({"v": PROMPT_V, "file": rel, "size": st.st_size, "mtime": st.st_mtime_ns, "a": a, "b": b, "cards": cards_sha})
            out.append({"key": key, "video": rel, "title": title, "a": a, "b": b, "video_dur": dur, "w": w, "h": h})
    return out


def shrink(src, a, b, w, h, out):
    """원본의 [a, b) 를 360p 사본으로 — 인코더 자리(GPU 먼저 · 실패면 CPU 한 번)는 실행기 video_encoder 한 곳."""
    sw = max(2, int(round(w * PH / h / 2)) * 2) if h > PH else w - w % 2
    sh = PH if h > PH else h - h % 2
    cpu = ["-c:v", "libx264", "-preset", "veryfast", "-b:v", str(VBR), "-maxrate", str(2 * VBR), "-bufsize", str(2 * VBR)]
    run_enc(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", src, "-t", f"{b - a:.3f}", "-vf", f"scale={sw}:{sh},fps={PFPS}",
             io_utils.video_encoder.slot(cpu, VBR, program="ffmpeg"), "-c:a", "aac", "-b:a", str(ABR), "-ac", "1", out], check=True)


def take(body, piece, need):
    """AGY 답 → 이 조각의 후보 [{card, start(원본 초), fit, …}] — 규칙에 안 맞는 답은 코드가 버린다(다시 묻지 않는다)."""
    try:
        seen = float(body.get("watched_seconds") or 0)
    except (TypeError, ValueError):
        seen = 0.0
    span = piece["b"] - piece["a"]
    got = []
    for r in body.get("picks") or []:
        try:
            ci, s, fit = int(r["card"]), float(r["start"]), int(r.get("fit") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if ci not in need or not 1 <= fit <= 5 or s < 0:
            continue
        end = s + need[ci]
        start = piece["a"] + s
        if end > span or end > seen + 1 or start >= piece["video_dur"] - END_ROOM:   # 조각 밖 · 안 본 구간 · 영상 끝 2초 안
            continue
        got.append({"card": ci, "video": piece["video"], "start": round(start, 2), "fit": fit,
                    "news_band": r.get("news_band") is True, "audio": r.get("audio") is True, "what": str(r.get("what") or "")[:120]})
    return got


def assign(cands, need, cards):
    """카드마다 하나 — 맞음 점수 높은 후보부터(같으면 카드·영상·시작 순 · 결정적) 같은 영상의 이미 쓴 구간과 겹치지 않는 것만. 한 번 정렬·한 번 훑기."""
    used, picked = {}, {}
    for c in sorted(cands, key=lambda c: (-c["fit"], c["card"], c["video"], c["start"])):
        if c["card"] in picked:
            continue
        a, b = c["start"], c["start"] + need[c["card"]] + END_ROOM
        if any(a < y and x < b for x, y in used.get(c["video"], ())):   # 영상마다 쓴 구간은 카드 수 이하
            continue
        used.setdefault(c["video"], []).append((a, b))
        picked[c["card"]] = c
    by_card = {}
    for c in cands:                                                    # 카드별 후보 — 한 번 훑기
        by_card.setdefault(c["card"], []).append(c)
    out = []
    for ci, card in enumerate(cards, 1):
        c = picked.get(ci)
        out.append({"card": ci, "lines": card.get("lines"), "need": need[ci],
                    "pick": None if c is None else dict(c, length=round(need[ci] + END_ROOM, 2),
                                                        crop=[0, 0.12, 1, 0.75] if c["news_band"] else None),
                    "others": [x for x in by_card.get(ci, ()) if x is not c][:3]})
    return out


def scenes(proj):
    proj = os.path.abspath(proj)
    with open(os.path.join(proj, "script.json"), encoding="utf-8") as fh:
        script = json.load(fh)
    cards = script.get("cards") or []
    if not cards:
        raise SystemExit("script.json 에 카드가 없습니다 — 순서 안내 2번(대본)부터")
    need = {i: need_of(c) for i, c in enumerate(cards, 1)}
    vids = candidates(proj)
    if not vids:
        raise SystemExit(f"후보 영상이 없습니다 — 먼저 `python preset.py media yt {proj} g1 \"<검색어>\" 3`")
    rp = os.path.join(proj, SCENES)
    try:
        with open(rp, encoding="utf-8") as fh:
            old = json.load(fh)
        done = old.get("pieces") if old.get("schema") == SCHEMA else {}
    except (OSError, ValueError, AttributeError):
        done = {}
    done = dict(done or {})
    cards_sha = _sha([c.get("lines") for c in cards])
    plan = pieces(proj, vids, cards_sha)
    todo = [p for p in plan if (done.get(p["key"]) or {}).get("answer") is None and int((done.get(p["key"]) or {}).get("asks") or 0) < ASK_MAX]
    _folder, agy = find_agy_runner()
    model = agy_model()
    card_txt = "\n".join(f"{i}. {need[i]:g}s - " + " / ".join(c.get("lines") or []) for i, c in enumerate(cards, 1))
    stop, lock, refused = threading.Event(), threading.Lock(), []

    def one(p):
        if stop.is_set():
            return
        box = tempfile.mkdtemp(prefix="agy-scenes-", dir=proj)   # 한 대화 = 한 파일: 사본 하나만 든 새 폴더
        try:
            clip = os.path.join(box, "piece.mp4")
            shrink(os.path.join(proj, p["video"]), p["a"], p["b"], p["w"], p["h"], clip)
            size = os.path.getsize(clip)
            entry = {"video": p["video"], "a": p["a"], "b": p["b"], "bytes": size, "asks": int((done.get(p["key"]) or {}).get("asks") or 0) + 1,
                     "answer": None, "why": ""}
            if size > LIMIT:
                entry.update(asks=ASK_MAX, why=f"사본 {size} 바이트가 한 대화 상한 {LIMIT} 을 넘음")   # 코드가 잰 것 — 다시 묻지 않는다
            elif not stop.is_set():
                path = agy.plain_path(clip)
                prompt = PROMPT.format(dur=p["b"] - p["a"], name=os.path.basename(clip), title=p["title"], topic=script.get("title", ""),
                                       box=FRAME_BOX, cards=card_txt)
                try:
                    res = agy.invoke(prompt, kind="view", files=[path], model=model, timeout_s=TIMEOUT, cwd=box)
                except agy.RUN_REFUSAL.RunServiceRefused as e:
                    stop.set()
                    with lock:
                        refused.append((getattr(e, "provider_result", None) or {}).get("code") or e.code)
                    return
                why, _used = agy.opened_exactly(res.get("tools"), [path]) if res.get("ok") else (f"{res.get('code')}: {str(res.get('message') or '')[:160]}", None)
                text = str(res.get("text") or "")
                if not why:
                    try:
                        body = json.loads(text[text.index("{"):text.rindex("}") + 1])
                        entry["answer"] = take(body, p, need) if isinstance(body, dict) else None
                        why = "" if isinstance(body, dict) else "답이 JSON 객체가 아님"
                    except ValueError:
                        why = f"답을 JSON 으로 못 읽음: {text[:120]!r}"
                entry["why"] = why
            else:
                return
            with lock:
                done[p["key"]] = entry
        finally:
            shutil.rmtree(box, ignore_errors=True)

    if todo:
        with ThreadPoolExecutor(max_workers=min(len(todo), agy.max_parallel())) as ex:   # 기계 전체 agy 칸 상한(실행기 표 maxParallel)
            list(ex.map(one, todo))
    keys = {p["key"] for p in plan}
    cands = [c for p in plan for c in ((done.get(p["key"]) or {}).get("answer") or ())]
    rows = assign(cands, need, cards)
    rec = {"schema": SCHEMA, "model": model, "cards_sha256": cards_sha, "pieces": {k: v for k, v in done.items() if k in keys},
           "cards": rows, "missing": [r["card"] for r in rows if r["pick"] is None],
           "unanswered": [{"video": p["video"], "a": p["a"], "b": p["b"], "why": (done.get(p["key"]) or {}).get("why") or "보내지 않음"}
                          for p in plan if (done.get(p["key"]) or {}).get("answer") is None]}
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    for r in rows:
        c = r["pick"]
        if c:
            print(f"카드 {r['card']}: python preset.py media clip \"{proj}\" \"{os.path.join(proj, c['video'])}\" {c['start']:g} {c['length']:g} c{r['card']:02d}"
                  + (f"   (crop {c['crop']})" if c["crop"] else "") + ("   (audio)" if c["audio"] else ""))
    print(json.dumps({"scenes": rp, "asked": len(todo), "missing": rec["missing"], "unanswered": len(rec["unanswered"])}, ensure_ascii=False))
    if refused:
        raise SystemExit(f"agy 가 거부했습니다({refused[0]} — 한도·로그인·도구 거부). 이 실행의 agy 요청을 모두 멈췄습니다(자동 재시도 없음). "
                         "받은 답은 scenes.json 에 남겼습니다 — 원인을 확인한 뒤(한도면 풀리는 시각 뒤) 같은 scenes 명령을 다시 하면 남은 조각만 묻습니다.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("사용법: python preset.py scenes <프로젝트>")
    sys.exit(scenes(sys.argv[1]))
