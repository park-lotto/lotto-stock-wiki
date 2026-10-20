"""대본 칼카피 엔진 — 채널 하나의 쇼츠 대본을 전부 받아 줄 단위로 뜯고, 스토리 전개 유형별로 묶어 '그대로 베껴 쓸 수 있는' 칼카피 카드를 만든다.
(화면·편집 칼카피는 tools/calcopy/engine 뜯기. 이 엔진은 말 — 대본만 본다.)

단계(모두 재개 가능 — 끝난 편은 건너뛴다):
  list        채널 쇼츠 목록(yt-dlp --flat-playlist)        → <out>/list.tsv
  pull        음성만 받기(m4a, 공개 클라이언트·쿠키 없음)     → <out>/audio/<id>.m4a   (커밋 안 함)
  transcribe  받아쓰기(faster-whisper, 이 PC에서 — 버텍스 0)  → <out>/transcripts.json
  tag         줄별 상세 태깅(버텍스 묶음 호출, 기본 8편/회)   → <out>/tags.jsonl
  cluster     전개 패턴으로 유형 묶기(태그만으로 — 버텍스 0)   → <out>/types.json
  card        유형별 칼카피 카드(빈도표는 태그 집계 그대로)     → <out>/cards/<유형>.json·md
  report      보고 HTML                                        → <out>/report.html
사용:
  py script_calcopy.py list --url https://www.youtube.com/@두유노홈디노/shorts --slug homedesignnote
  py script_calcopy.py pull --slug homedesignnote
  <faster-whisper 있는 python> script_calcopy.py transcribe --slug homedesignnote
  py script_calcopy.py tag --slug homedesignnote [--batch 8] [--limit N]
  py script_calcopy.py cluster|card|report --slug homedesignnote
"""
import argparse, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT_BASE = os.path.join(ROOT, "out", "script_calcopy")


def out_dir(slug):
    d = os.path.join(OUT_BASE, slug)
    os.makedirs(d, exist_ok=True)
    return d


def read_list(slug):
    rows = []
    for ln in open(os.path.join(out_dir(slug), "list.tsv"), encoding="utf-8"):
        p = ln.rstrip("\n").split("\t")
        if len(p) >= 4 and p[0]:
            rows.append({"id": p[0], "views": int(p[1]) if p[1].isdigit() else 0, "duration": p[2], "title": p[3]})
    return rows


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ── list ──────────────────────────────────────────────────────────────
def cmd_list(a):
    d = out_dir(a.slug)
    r = subprocess.run(["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(view_count)s\t%(duration)s\t%(title)s", a.url],
                       capture_output=True, text=True, encoding="utf-8")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    open(os.path.join(d, "list.tsv"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    meta = load_json(os.path.join(d, "meta.json"), {})
    meta.update(url=a.url, listed_at=time.strftime("%Y-%m-%d %H:%M"), n=len(lines))
    save_json(os.path.join(d, "meta.json"), meta)
    print("목록 %d편 → %s" % (len(lines), os.path.join(d, "list.tsv")))


# ── pull ──────────────────────────────────────────────────────────────
def cmd_pull(a):
    d = out_dir(a.slug)
    ad = os.path.join(d, "audio")
    os.makedirs(ad, exist_ok=True)
    have = {f.split(".")[0] for f in os.listdir(ad)}
    todo = [r["id"] for r in read_list(a.slug) if r["id"] not in have]
    print("받을 것 %d편(이미 %d)" % (len(todo), len(have)), flush=True)
    done_mark = os.path.join(d, "_pull_done")
    if os.path.exists(done_mark):
        os.remove(done_mark)
    if not todo:
        open(done_mark, "w").write(time.strftime("%Y-%m-%d %H:%M"))
        return
    lst = os.path.join(d, "_pull_ids.txt")
    open(lst, "w", encoding="utf-8").write("\n".join("https://www.youtube.com/shorts/" + i for i in todo))
    subprocess.run(["yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio", "--sleep-requests", "1", "--sleep-interval", "1",
                    "--ignore-errors", "--no-progress", "-o", os.path.join(ad, "%(id)s.%(ext)s"), "-a", lst])
    print("받음 %d편" % len(os.listdir(ad)))
    open(done_mark, "w").write(time.strftime("%Y-%m-%d %H:%M"))   # transcribe --follow 가 이걸 보고 끝낸다


# ── transcribe ────────────────────────────────────────────────────────
def cmd_transcribe(a):
    """--follow: pull 과 동시에 돌린다 — 새 음성이 생기면 받아쓰고, pull 이 끝났고(_pull_done) 남은 게 없으면 끝낸다."""
    from faster_whisper import WhisperModel   # 이 단계만 무거운 패키지가 필요하다
    m = WhisperModel(a.model, device="cpu", compute_type="int8")
    while True:
        n = _transcribe_pass(a, m)
        if not a.follow or (n == 0 and os.path.exists(os.path.join(out_dir(a.slug), "_pull_done"))):
            break
        if n == 0:
            time.sleep(30)


def _transcribe_pass(a, m):
    d = out_dir(a.slug)
    path = os.path.join(d, "transcripts.json")
    done = load_json(path, {})
    ad = os.path.join(d, "audio")
    files = sorted(f for f in os.listdir(ad) if f.split(".")[0] not in done and not f.endswith(".part"))
    files = [f for f in files if not f.endswith((".ytdl", ".temp"))]
    print("받아쓸 것 %d편(이미 %d)" % (len(files), len(done)), flush=True)
    for i, f in enumerate(files):
        vid = f.split(".")[0]
        try:
            segs, _ = m.transcribe(os.path.join(ad, f), language="ko", vad_filter=False)
            segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
        except Exception as e:      # noqa: BLE001 — 깨진 파일은 기록하고 넘어간다
            segs = [{"error": repr(e)[:200]}]
        done[vid] = {"text": " ".join(s.get("text", "") for s in segs).strip(), "segments": segs}
        if i % 5 == 4 or i == len(files) - 1:
            save_json(path, done)
        print("%d/%d %s %s" % (i + 1, len(files), vid, done[vid]["text"][:40]), flush=True)
    save_json(path, done)
    return len(files)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("list"); p.add_argument("--url", required=True); p.add_argument("--slug", required=True)
    p = sp.add_parser("pull"); p.add_argument("--slug", required=True)
    p = sp.add_parser("transcribe"); p.add_argument("--slug", required=True)
    p.add_argument("--follow", action="store_true", help="pull 과 동시에 — 새 음성을 기다리며 계속")
    p.add_argument("--model", default=os.environ.get("FASTER_WHISPER_MODEL", "deepdml/faster-whisper-large-v3-turbo-ct2"))
    for name in ("tag", "cluster", "card", "report"):
        p = sp.add_parser(name); p.add_argument("--slug", required=True)
        p.add_argument("--batch", type=int, default=8); p.add_argument("--limit", type=int, default=0)
        p.add_argument("--workers", type=int, default=1); p.add_argument("--follow", action="store_true")
        p.add_argument("--hit", type=int, default=100000, help="잘된 편 기준 조회수"); p.add_argument("--flop", type=int, default=20000, help="안된 편 기준 조회수(미만)")
    a = ap.parse_args()
    if a.cmd in ("tag", "cluster", "card", "report"):
        import script_calcopy_stages as ST
        return getattr(ST, "cmd_" + a.cmd)(a)
    {"list": cmd_list, "pull": cmd_pull, "transcribe": cmd_transcribe}[a.cmd](a)


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
