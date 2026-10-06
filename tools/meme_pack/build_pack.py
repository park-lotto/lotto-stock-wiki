"""감정짤 밈팩 — 남긴 후보마다 '2초 안팎 하이라이트'만 잘라 팩으로 만든다.

    py tools/meme_pack/build_pack.py <작업폴더> [--only id1,id2] [--redo] [--workers 4]

하이라이트 구간의 주인은 이 파일이다(0순위-C):
  find_peak()   Gemini 가 시각 격자를 보고 "표정이 가장 센 순간(초)"을 고른다
  window()      그 순간을 품은 한 컷(shot) 안에서 CLIP_SEC 길이 창을 잡는다(컷이 바뀌는 지점을 안 넘긴다)
  cut()         그 창을 잘라 library/clips/<id>.mp4 로 쓴다 — 뷰어의 '앞으로/뒤로' 조정도 이 함수를 부른다
  build_manifest()  state.json(지움·감정) + highlights.json(구간) → library/manifest.json

highlights.json = { id: {start, dur, peak, usable, what, shot:[a,b], method: gemini|whole|manual, rule} }
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # 저장소 루트(shopping_shorts)

CLIP_SEC = 2.0          # 사장님 2026-10-05: "2초 내외로 하이라이트만 딱"
MIN_SEC = 1.0           # 이보다 짧은 컷은 짤로 못 쓴다(표시만 하고 남긴다)
LEAD = 0.7              # 창에서 피크 앞에 두는 시간 — 표정이 터지기 직전부터 보여야 '변하는' 짤이 된다
RULE = "peak-gemini+shot-clamp v1"
MAX_TILES, TILE_W, COLS = 96, 200, 8
_LOCK = threading.Lock()


MODELS = ("gemini-3.5-flash", "gemini-3.1-flash-lite")
_KEYS, _CLIENTS, _RR = [], {}, {"i": 0}


def _keys():
    """내부 도구용 키 — 저장소 루트 .env 의 GEMINI_API_KEY, _2, _3 …
    (제품 키풀 SHORTS_GEMINI_KEY 는 서버에만 있어 로컬에서는 0개다 — 2026-10-05 실측)."""
    if not _KEYS:
        env = os.path.join(os.path.dirname(os.path.dirname(HERE)), ".env")
        if os.path.exists(env):
            for line in open(env, encoding="utf-8", errors="replace"):
                m = re.match(r"\s*GEMINI_API_KEY(?:_\d+)?\s*=\s*(\S+)", line)
                if m:
                    _KEYS.append(m.group(1).strip("\"'"))
    return _KEYS


def _next_key():
    with _LOCK:
        ks = _keys()
        if not ks:
            return None
        _RR["i"] += 1
        return ks[_RR["i"] % len(ks)]


def _client(key):
    from google import genai
    with _LOCK:
        if key not in _CLIENTS:
            _CLIENTS[key] = genai.Client(api_key=key)
        return _CLIENTS[key]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def shots(path, dur):
    """컷 경계(초) 목록 → [(시작, 끝), …]."""
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"])
    cuts = sorted({float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)})
    edges = [0.0] + [c for c in cuts if 0.05 < c < dur - 0.05] + [dur]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b - a > 0.02]


def grid(path, dur):
    """시각을 적은 프레임 격자(JPEG bytes)와 칸 간격(초)."""
    fps = min(4.0, MAX_TILES / max(dur, 0.1))
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps:.4f},scale={TILE_W}:-2",
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5", "-"], capture_output=True)
    frames = [b"\xff\xd8" + p for p in r.stdout.split(b"\xff\xd8") if p][:MAX_TILES]
    if not frames:
        raise RuntimeError("프레임을 못 뽑았다: " + r.stderr.decode("utf-8", "replace")[-200:])
    ims = [Image.open(io.BytesIO(f)).convert("RGB") for f in frames]
    w, h = ims[0].size
    rows = (len(ims) + COLS - 1) // COLS
    sheet = Image.new("RGB", (w * COLS, h * rows), "black")
    dr = ImageDraw.Draw(sheet)
    for k, im in enumerate(ims):
        x, y = (k % COLS) * w, (k // COLS) * h
        sheet.paste(im, (x, y))
        label = f"{k / fps:.2f}s"
        dr.rectangle([x, y, x + 8 * len(label) + 4, y + 14], fill="black")
        dr.text((x + 2, y + 1), label, fill="yellow")
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=82)
    return buf.getvalue(), 1 / fps


def find_peak(path, dur, emotion, title):
    """Gemini 에게 '표정이 가장 센 순간'을 묻는다 → {peak, usable, what} / 실패는 예외(조용히 넘기지 않는다)."""
    from google.genai import types
    img, step = grid(path, dur)
    prompt = (
        f"이 그림은 영상 한 편(길이 {dur:.1f}초)을 {step:.2f}초 간격으로 뽑아 왼쪽→오른쪽, 위→아래 순서로 놓은 것이다. "
        "각 칸 왼쪽 위의 노란 숫자가 그 칸의 시각(초)이다.\n"
        f"우리는 이 영상에서 '{emotion.replace('_', '·')}' 감정의 리액션 짤로 쓸 2초를 고른다. "
        "쇼츠에서 반전·고조 문장에 1~2초 끼워 넣는 용도라, 사람(또는 캐릭터)의 얼굴·상반신이 크게 보이고 "
        "그 감정 표정·몸짓이 가장 강하게 터지는 순간이어야 한다.\n"
        "- peak: 그 표정이 가장 센 칸의 시각(초). 반드시 칸에 적힌 숫자 중 하나.\n"
        "- usable: 그런 리액션 장면이 실제로 있으면 true. 사람·캐릭터의 감정 표정이 안 보이거나(풍경·글자·게임 화면 등) "
        "감정이 전혀 다르면 false.\n"
        "- what: 그 순간 화면에 보이는 것을 한국어 한 줄로(누구인지 이름을 추측해 적지 말고 모습·행동만).\n"
        f"참고용 제목: {title}\n"
        '출력은 JSON 객체 {"peak": 12.5, "usable": true, "what": "..."} 만.')
    part = types.Part.from_bytes(data=img, mime_type="image/jpeg")

    last = "키 없음(.env 의 GEMINI_API_KEY*)"
    for attempt in range(len(_keys()) * len(MODELS) or 1):
        key = _next_key()
        if not key:
            break
        model = MODELS[(attempt // max(len(_keys()), 1)) % len(MODELS)]
        try:
            resp = _client(key).models.generate_content(
                model=model, contents=[prompt, part],
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            d = json.loads(resp.text)
            if isinstance(d, list) and d:
                d = d[0]
            return {"peak": max(0.0, min(float(d["peak"]), dur)), "usable": bool(d.get("usable")),
                    "what": str(d.get("what") or "").strip()}
        except Exception as e:  # 다음 키·모델로 넘어가되, 마지막 오류는 결과에 남긴다
            last = f"{model}: {e!r}"[:300]
            if any(c in last for c in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                time.sleep(4)
    raise RuntimeError("Gemini 실패 — " + last)


def window(peak, shot_list, dur):
    """피크를 품은 컷 안에서 CLIP_SEC 창 → (start, length, (컷 시작, 컷 끝))."""
    shot = next(((a, b) for a, b in shot_list if a <= peak < b), shot_list[-1] if shot_list else (0.0, dur))
    a, b = shot[0] + 0.04, shot[1] - 0.04     # 이웃 컷이 한 프레임 새어 들지 않게
    if b - a <= CLIP_SEC:
        return round(a, 2), round(max(b - a, 0.1), 2), shot
    start = min(max(peak - LEAD, a), b - CLIP_SEC)
    return round(start, 2), CLIP_SEC, shot


def cut(work, cid, start, length):
    """raw/<id>.mp4 의 [start, start+length] 를 library/clips/<id>.mp4 로(프레임 정확 — 재인코딩)."""
    src = os.path.join(work, "raw", f"{cid}.mp4")
    out_dir = os.path.join(work, "library", "clips")
    os.makedirs(out_dir, exist_ok=True)
    out, tmp = os.path.join(out_dir, f"{cid}.mp4"), os.path.join(out_dir, f"{cid}.tmp.mp4")
    r = run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", src, "-t", f"{length:.2f}",
             "-vf", "scale=-2:'min(720,ih)':flags=lanczos,setsar=1", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-threads", "2",  # 2026-10-06 사장님 "CPU 많이 안 먹게"
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", tmp])
    if r.returncode != 0 or not os.path.exists(tmp):
        raise RuntimeError("자르기 실패: " + r.stderr.strip()[-300:])
    os.replace(tmp, out)
    thumb_dir = os.path.join(work, "library", "thumbs")
    os.makedirs(thumb_dir, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{min(LEAD, length / 2):.2f}", "-i", out, "-frames:v", "1",
         "-vf", "scale=-2:260", os.path.join(thumb_dir, f"{cid}.jpg")])
    return out


def set_highlight(work, cid, entry):
    path = os.path.join(work, "highlights.json")
    with _LOCK:
        h = _load(path, {})
        h[cid] = entry
        _save(path, h)


def nudge(work, cid, delta, dur_total):
    """뷰어의 앞으로/뒤로 조정 — 시작점을 delta 초 옮겨 다시 자른다(길이는 그대로)."""
    h = _load(os.path.join(work, "highlights.json"), {}).get(cid)
    if not h:
        raise RuntimeError("아직 하이라이트가 없는 영상")
    start = round(min(max(h["start"] + delta, 0.0), max(dur_total - h["dur"], 0.0)), 2)
    cut(work, cid, start, h["dur"])
    h.update(start=start, method="manual")
    set_highlight(work, cid, h)
    return h


def process(work, it, redo):
    cid, dur = it["id"], float(it["duration"])
    if not redo and cid in _load(os.path.join(work, "highlights.json"), {}) \
            and os.path.exists(os.path.join(work, "library", "clips", f"{cid}.mp4")):
        return cid, "있음"
    src = os.path.join(work, "raw", f"{cid}.mp4")
    try:
        sl = shots(src, dur)
        if dur <= CLIP_SEC + 0.3 and len(sl) <= 1:      # 이미 짧은 한 컷 → 통째로
            entry = {"peak": round(dur / 2, 2), "usable": True, "what": "", "method": "whole"}
            start, length, shot = 0.0, round(dur, 2), (0.0, dur)
        else:
            entry = find_peak(src, dur, it["emotion"], it["title"])
            entry["method"] = "gemini"
            start, length, shot = window(entry["peak"], sl, dur)
        cut(work, cid, start, length)
        entry.update(start=start, dur=length, shot=[round(shot[0], 2), round(shot[1], 2)], rule=RULE)
        set_highlight(work, cid, entry)
        return cid, "잘림" + ("" if length >= MIN_SEC else "(짧음)") + ("" if entry["usable"] else "(리액션 불분명)")
    except Exception as e:  # 한 편 실패가 전체를 멈추지 않게 — 실패는 결과 표에 그대로 남긴다
        return cid, f"실패: {e}"


def build_manifest(work):
    """지금 남아 있는 짤(지움 제외) + 하이라이트 → library/manifest.json. '어느 감정에 어느 짤'의 유일한 표."""
    import serve
    serve.WORK = work
    hl = _load(os.path.join(work, "highlights.json"), {})
    clips = []
    for it in serve.items():
        h = hl.get(it["id"])
        f = os.path.join(work, "library", "clips", f'{it["id"]}.mp4')
        if it["deleted"] or not h or not os.path.exists(f):
            continue
        clips.append({"id": it["id"], "emotion": it["emotion"], "file": f'clips/{it["id"]}.mp4',
                      "dur": h["dur"], "src_start": h["start"], "source": it["source"], "title": it["title"],
                      "what": h.get("what", ""), "usable": h.get("usable", True), "method": h.get("method"),
                      "rule": h.get("rule")})
    out = {"rule": RULE, "clip_sec": CLIP_SEC, "count": len(clips), "clips": clips}
    os.makedirs(os.path.join(work, "library"), exist_ok=True)
    _save(os.path.join(work, "library", "manifest.json"), out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--only", default="")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    import serve
    serve.WORK = work
    todo = [it for it in serve.items() if not it["deleted"]]
    if a.only:
        want = set(a.only.split(","))
        todo = [it for it in todo if it["id"] in want]
    results = {}
    with ThreadPoolExecutor(a.workers) as ex:
        for cid, note in ex.map(lambda it: process(work, it, a.redo), todo):
            results[cid] = note
            if note != "있음":
                print(cid, note, flush=True)
    m = build_manifest(work)
    fails = {k: v for k, v in results.items() if v.startswith("실패")}
    _save(os.path.join(work, "build_log.json"), results)
    print(f"대상 {len(todo)} · manifest {m['count']} · 실패 {len(fails)}")


if __name__ == "__main__":
    main()
