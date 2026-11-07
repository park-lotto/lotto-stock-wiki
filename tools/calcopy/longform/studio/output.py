# 프레임을 영상으로 굽기
from .settings import *
from .timing import *
from .footage import *
from .marks import *
from .cards import *
from .typeset import *
from .news import *
from .bridge import *
from .motion import *
from .direction import direct
CARDS = {"typo": card_type, "article": card_news, "quote": card_quote, "bignum": card_number, "bar": card_bars, "table": card_table, "labels": card_chips, "vs": card_versus,
        "cycle": card_loop, "rating": card_grade, "ladder": card_steps, "pct": card_share, "stock": card_photo, "ai": card_photo}

def choose_encoder():
    """NVENC 가 실제로 돌면 GPU, 아니면 CPU."""
    ok = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True).returncode == 0
    return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"] if ok else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

def shot_at(t, tl):
    shots = tl["shots"]; return next((x for x in reversed(shots) if x["t0"] <= t), shots[0])

_held = {}
def scene_at(t, tl):
    """시각 t 의 장면 그림(로고·자막·출처를 얹기 전). (그림, 샷, 전환 종류, 전환 뒤 지난 초)"""
    s = shot_at(t, tl); lt, T = t - s["t0"], s["t1"] - s["t0"]
    frame = CARDS[s["type"]](s, lt, T, tl).convert("RGBA")
    if s["type"] in ("bar", "vs", "labels", "bignum", "quote"):
        rv = (reveal_time(tl, s) - s["t0"]) if s.get("reveal") else None
        frame = living(frame, lt / max(T, 0.1), max(0.0, 1 - (lt - rv) / 0.25) if rv is not None and lt >= rv else 0.0).convert("RGBA")
    since, kind = lt, s.get("cut", "none")
    for a, c in [(b[0], b[3]) for b in s.get("beats", [])[1:]] + [(w[0], w[2]) for w in s.get("swaps", [])]:
        if lt >= a: since, kind = lt - a, c
    if "dissolve" in CFG["cuts"]: _held["last"] = (int(round(t * FPS)), frame.copy())   # 다음 디졸브의 나가는 화면 후보(얹기 전 그림)
    return frame, s, kind, since

def make_frame(t, tl):
    """시각 t 의 한 장. 렌더와 견본 시트가 함께 쓴다."""
    direct(tl); shots = tl["shots"]; subs = tl["subs"]; evs = tl["events"]
    ev = next((e for e in evs if e["t"] <= t < e["t"] + e["dur"]), None)
    if ev and ev["kind"].startswith("bumper"): return bridge_screen(t - ev["t"], ev["dur"], ev["kind"] == "bumper_short", ev.get("look", "lines"))
    if ev and ev["kind"] == "outro" and CFG["outro_style"] == "cards": return closing_screen(t - ev["t"], ev["dur"])
    if t >= shots[-1]["t1"] and not (ev and ev["kind"] == "wipe"): return closing_screen(0, 1)
    prev = _held.get("last")
    frame, s, kind, since = scene_at(t, tl); lt = t - s["t0"]
    if kind == "dissolve" and since < CUT_SEC:
        # 나가는 화면 = 전환 바로 앞 프레임. 차례로 구우면 방금 그린 것을 쓰고, 구간 렌더가 전환 한가운데서 시작하면 한 번 그린다
        f0 = int(round((t - since) * FPS)) - 1; out = _held.get("out")
        if not (out and out[0] == f0):
            _held["out"] = (f0, prev[1] if prev and prev[0] == f0 else scene_at(f0 / FPS, tl)[0])
        frame = blend_cut(_held["out"][1], frame, since / CUT_SEC)
    else: frame = cut_in(frame, kind, since / CUT_SEC)
    if ev and ev["kind"] == "wipe": chapter_wipe(frame, ev.get("look", "diagonal"), (t - ev["t"]) / ev["dur"])
    br = type_is_light(s, lt, tl) if s["type"] == "typo" else False
    frame.alpha_composite(corner_marks(s["chapter"], br))
    if s["type"] != "typo" or CFG["caption_all_shots"]:
        if s["type"] != "typo": source_mark(frame, s, shot_src(s), ART_BOX if s["type"] == "article" else None)
        so = next((x for x in subs if x["t0"] <= t < x["t1"] + 0.1), None)
        if so: caption_bar(frame, so["text"], t - so["t0"])
    return frame

def bake_range(t_from=None, t_to=None, out=None, frames=None):
    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    total = tl["total"]; nfr = int(total * FPS)
    f0 = int((t_from or 0) * FPS); f1 = int((t_to or total) * FPS) if t_to else nfr
    if frames: f0, f1 = frames   # 구간 동시 렌더는 프레임 번호로 끊는다(초로 끊으면 경계에서 한 장이 겹치거나 빠진다)
    out = out or os.path.join(BUILD, "video.mp4" if t_from is None else f"part_{int(t_from)}_{int(t_to or total)}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{CFG['fps_num']}/{CFG['fps_den']}",
                           "-i", "-", *choose_encoder(), "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        t = fi / FPS; frame = make_frame(t, tl)
        ff.stdin.write(film_grain(frame, t).tobytes())
        if fi % 300 == 0: print(f"{t/60:.2f}분 / {total/60:.2f}분", flush=True)
    ff.stdin.close(); ff.wait(); print("영상:", out)

def bake_all(n=6):
    """구간 n개를 프로세스로 나눠 그린 뒤 다시 인코딩 없이 잇는다. 프레임 수가 안 맞으면 멈춘다."""
    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    nfr = int(tl["total"] * FPS); cuts = [nfr * k // n for k in range(n + 1)]
    parts = [os.path.join(BUILD, f"gpu_{k}.mp4") for k in range(n)]
    def start(k):
        log = open(os.path.join(BUILD, f"gpu_{k}.log"), "w", encoding="utf-8")   # 왜 죽었는지 남긴다(11-02 2번 구간이 까닭 없이 끊겼다)
        return subprocess.Popen([sys.executable, "-X", "utf8", "-m", "studio", "part", str(cuts[k]), str(cuts[k + 1]), parts[k]],
                                cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
    ps = [start(k) for k in range(n)]
    bad = [k for k, p in enumerate(ps) if p.wait()]
    for k in bad:   # 혼자 다시 돌리면 대개 지나간다 — 한 번만
        print(f"구간 {k} 다시", flush=True)
        if start(k).wait(): raise SystemExit(f"구간 {k} 렌더 실패 — build/gpu_{k}.log")
    lst = os.path.join(BUILD, "gpu_list.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '" + p.replace(chr(92), "/") + "'" + chr(10) for p in parts))
    out = os.path.join(BUILD, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    got = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", out],
                             capture_output=True, text=True).stdout.strip().rstrip(","))
    if got != nfr: raise SystemExit(f"프레임 수 불일치: {got} != {nfr}")
    for p in parts: os.remove(p)
    print("영상:", out, got, "프레임")

def finish_file():
    out = E("result", CFG.get("output_name", "완성본.mp4")); os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(BUILD, "video.mp4"), "-i", os.path.join(BUILD, "mix.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    print("완성:", os.path.abspath(out))

