# 사진·영상 바탕과 움직임
from .settings import *
random.seed(7)
from .motion import night as page

_vig = None
def edge_shade():
    global _vig
    if _vig is None:
        y, x = np.mgrid[0:H, 0:W]; r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
        a = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 0.62
        _vig = Image.fromarray((a * 255).astype(np.uint8))
    return _vig
def tone(im, dark=0.0):
    im = ImageEnhance.Color(im).enhance(0.85); im = ImageEnhance.Contrast(im).enhance(1.08)
    if dark: im = ImageEnhance.Brightness(im).enhance(1 - dark)
    black = Image.new("RGB", (W, H), (0, 0, 0)); return Image.composite(black, im, edge_shade())

_img = {}
def base_picture(k):
    if k in _img: return _img[k]
    p = None
    for c in (E("material", "video", f"s{k:03d}.jpg"), E("material", "img", f"s{k:03d}.png"), E("material", "img", f"s{k:03d}.jpg")):
        if os.path.exists(c): p = c; break
    if p is None:
        print(f"[경고] 문장 {k} 샷 그림 없음 — 종이 배경으로 대신함", flush=True)
        im = page()
    else:
        im = Image.open(p).convert("RGB"); r = max(W / im.width, H / im.height) * 1.0
        im = im.resize((math.ceil(im.width * r), math.ceil(im.height * r)), Image.LANCZOS)
        l, t = (im.width - W) // 2, (im.height - H) // 2; im = im.crop((l, t, l + W, t + H))
    _img[k] = im; return im
def stock_video_frame(k, t):
    p = E("material", "video", f"s{k:03d}.mp4")
    return None if not os.path.exists(p) else p

class VideoFeed:
    """실사 영상(assets/stock/sNNN.mp4)을 샷 길이만큼 순서대로 읽는다(렌더는 앞에서부터 진행)."""
    cur = None
    def __init__(self, path, dur):
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={CFG['fps_num']}/{CFG['fps_den']},setpts=PTS*{1.0}"
        self.p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-stream_loop", "-1", "-i", path, "-t", f"{dur + 0.5:.3f}", "-vf", vf,
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.path, self.n, self.last = path, 0, None
    def frame(self, idx):
        while self.n <= idx:
            b = self.p.stdout.read(W * H * 3)
            if len(b) < W * H * 3: break
            self.last = Image.frombytes("RGB", (W, H), b); self.n += 1
        return self.last
    def close(self):
        try: self.p.kill()
        except Exception: pass
def video_frame(s, lt, T):
    path = E("material", "video", f"s{s.get('clip', s['s'][0]):03d}.mp4")
    if not os.path.exists(path): return None
    key = (path, s["t0"])
    if VideoFeed.cur is None or VideoFeed.cur[0] != key:
        if VideoFeed.cur: VideoFeed.cur[1].close()
        VideoFeed.cur = (key, VideoFeed(path, T))
    return VideoFeed.cur[1].frame(int(lt * FPS))
