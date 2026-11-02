# 프레임을 영상으로 굽기
from .settings import *
from .timing import *
from .footage import *
from .marks import *
from .cards import *
from .typeset import *
from .news import *
from .bridge import *
CARDS = {"typo": card_type, "article": card_news, "quote": card_quote, "bignum": card_number, "bar": card_bars, "table": card_table, "labels": card_chips, "vs": card_versus,
        "cycle": card_loop, "rating": card_grade, "ladder": card_steps, "pct": card_share, "stock": card_photo, "ai": card_photo}

def choose_encoder():
    """NVENC 가 실제로 돌면 GPU, 아니면 CPU."""
    ok = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True).returncode == 0
    return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"] if ok else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

def bake_range(t_from=None, t_to=None, out=None, frames=None):
    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    total = tl["total"]; nfr = int(total * FPS)
    f0 = int((t_from or 0) * FPS); f1 = int((t_to or total) * FPS) if t_to else nfr
    if frames: f0, f1 = frames   # 구간 동시 렌더는 프레임 번호로 끊는다(초로 끊으면 경계에서 한 장이 겹치거나 빠진다)
    out = out or os.path.join(BUILD, "video.mp4" if t_from is None else f"part_{int(t_from)}_{int(t_to or total)}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{CFG['fps_num']}/{CFG['fps_den']}",
                           "-i", "-", *choose_encoder(), "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    shots = tl["shots"]; subs = tl["subs"]; evs = tl["events"]; si = 0
    for fi in range(f0, f1):
        t = fi / FPS
        ev = next((e for e in evs if e["t"] <= t < e["t"] + e["dur"]), None)
        if ev and ev["kind"].startswith("bumper"):
            frame = bridge_screen(t - ev["t"], ev["dur"], ev["kind"] == "bumper_short")
        elif ev and ev["kind"] == "outro":
            frame = closing_screen(t - ev["t"], ev["dur"])
        elif t >= shots[-1]["t1"] and not (ev and ev["kind"] == "wipe"):
            frame = closing_screen(0, 1)
        else:
            s = next((x for x in reversed(shots) if x["t0"] <= t), shots[0])
            lt, T = t - s["t0"], s["t1"] - s["t0"]
            frame = CARDS[s["type"]](s, lt, T, tl)
            if s["type"] != "typo" and lt < 0.2:   # 컷이 바뀔 때 색 띠가 지나간다
                x_ = -420 + (W + 840) * smooth(lt / 0.2); dw = ImageDraw.Draw(frame, "RGBA")
                dw.polygon([(x_ + 150, 0), (x_ + 330, 0), (x_ + 180, H), (x_, H)], fill=C["sub_bar"])
            br = type_is_light(s, lt, tl) if s["type"] == "typo" else is_bright(s)
            if ev and ev["kind"] == "wipe":  # 크림 종이가 대각선으로 지나간다
                p = (t - ev["t"]) / ev["dur"]; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
                x = -W * 0.6 + (W * 2.2) * p
                dl.polygon([(x + 14, 0), (x + W * 0.9 + 14, 0), (x + W * 0.5 + 14, H), (x - W * 0.4 + 14, H)], fill=(0, 0, 0, 60))
                lay = lay.filter(ImageFilter.GaussianBlur(10)); dl = ImageDraw.Draw(lay)
                dl.polygon([(x, 0), (x + W * 0.9, 0), (x + W * 0.5, H), (x - W * 0.4, H)], fill=(245, 239, 224, 255))
                frame.alpha_composite(lay)
            frame.alpha_composite(corner_marks(s["chapter"], br))
            src_bright = br
            if not br:  # 사진이라도 우하단이 밝으면 어두운 글자
                reg = frame.crop((40, H - 150, 760, H - 106)).convert("L"); src_bright = np.asarray(reg).mean() > 135
            if s["type"] != "typo": frame.alpha_composite(source_line(shot_src(s), src_bright))
            so = None if s["type"] == "typo" else next((x for x in subs if x["t0"] <= t < x["t1"] + 0.1), None)
            if so: caption_bar(frame, so["text"], t - so["t0"])
        ff.stdin.write(frame.convert("RGB").tobytes())
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

