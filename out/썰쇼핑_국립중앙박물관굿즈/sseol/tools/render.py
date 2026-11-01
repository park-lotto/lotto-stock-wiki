"""썰쇼핑 쇼츠 렌더러 (1080x1920, 30fps).

사용법:
  python render.py <프로젝트폴더>                 -> <프로젝트>/out.mp4  (굽기 전 판정 review.json 이 지금 대본·타이밍·소재로 통과여야 굽는다)
  python render.py <프로젝트폴더> --still 5.0     -> 해당 시각 한 장 PNG

좌표·색·글꼴은 참고 채널 최신 5편 픽셀 실측값이다(docs/MEASURE.md).
렌더할 때는 아래 상수만 쓴다 — 글꼴 탐색·반복 검증 없음.
"""
import bisect, errno, json, os, re, subprocess, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from io_utils import VideoReader, enc_attempts, enc_failed, gpu_slot, imwrite, x264

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30
CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))

# ---------------- 레이아웃 (실측) ----------------
NAVY = (16, 49, 115)
HEADER_EDGE = {218: (19, 44, 90), 219: (0, 3, 50), 220: (242, 246, 244), 221: (224, 228, 226)}  # 헤더 아래 끝 4줄
HEADER_H = 218
NAME_FONT, NAME_SIZE, NAME_BASE = "DoHyeon-Regular.ttf", 120, 150     # 채널명 (원본은 로고 글자 — 채널 고유)
NAME_CX = (315.5, 760.0)                                              # 왼쪽 글자 / 오른쪽 글자 가운데
ICON_BOX = (454, 26, 625, 190)                                        # 가운데 아이콘 칸
TITLE_FONT, TITLE_MAX, TITLE_MAXW, TITLE_CY = "Paperlogy-7Bold.ttf", 80, 992, 324
DIVIDER = {432: 126, 433: 152, 434: 152, 435: 152, 436: 110}          # 회색 선, x 30~1050
DIV_X = (30, 1050)
SUB_FONT, SUB_SIZE, SUB_BASE = "Paperlogy-6SemiBold.ttf", 60.3, (539, 610)  # 자막 1줄·2줄 기준선
MEDIA_Y, MEDIA_H = 670, 880                                           # 본편 영상 칸 (가로 꽉)
# 컷 움직임 (원본 찰떡파이 편 실측 — 그림 7컷·영상 8컷 모두 같은 규칙, 가운데 기준·이동/회전 없음)
#  등장: 컷 첫 프레임부터 1.063 → 1.025 → 1.002 → 1.0 배로 튕기듯 자리 잡음
#  자막 줄이 바뀌면(컷이 그대로일 때): 그 프레임부터 1.006 → 1.056 → 1.093 → 1.117 → 1.121 → 1.122 배 «툭» 밀고 들어감, 여러 번이면 곱해짐
ENTRY = (1.063, 1.025, 1.002)
PUNCH = (1.006, 1.056, 1.093, 1.117, 1.121, 1.122)
# 인트로
INTRO_DIM = 0.643                                                     # y 0~435 어둡게 (원본 바탕 164/255)
INTRO_MEDIA_Y = 436
HOOK_FONT, HOOK_SIZE, HOOK_BASE = "Paperlogy-9Black.ttf", (105, 110), (305, 418)
HOOK_COLORS = ((255, 255, 255), (0, 166, 238))
HOOK_STROKE, HOOK_SHADOW = 8, (10, 12)
HOOK_MAXW = 1000
BOX = (78, 592, 1000, 740)                                            # 흰 상자 + 제목
BOX_FONT, BOX_SIZE, BOX_MAXW = "Paperlogy-7Bold.ttf", 70, 890

_fonts = {}
def font(name, size):
    if (name, size) not in _fonts:
        _fonts[(name, size)] = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", name), size)
    return _fonts[(name, size)]

def text_w(f, t):
    return sum(f.getlength(c) for c in t)

def draw_line(d, text, fname, size, cx, base, fill, maxw=None, **kw):
    f = font(fname, size)
    w = text_w(f, text)
    if maxw and w > maxw:
        size = size * maxw / w; f = font(fname, size); w = text_w(f, text)
    x = cx - w / 2
    for c in text:
        d.text((x, base), c, font=f, fill=fill, anchor="ls", **kw); x += f.getlength(c)
    return size

def clean(line):
    return re.sub(r"(?<!\d)[.,]|[.,](?!\d)|[\"“”'‘’!?]", "", line).strip()   # 원본 자막엔 문장부호 없음

# ---------------- 고정 화면 ----------------
def draw_icon(img):
    x0, y0, x1, y1 = ICON_BOX
    p = CFG.get("header_icon_path")
    if p:  # 내 채널 로고 PNG
        ic = Image.open(os.path.join(ROOT, p)).convert("RGBA")
        ic.thumbnail((x1 - x0, y1 - y0), Image.LANCZOS)
        img.paste(ic, ((x0 + x1 - ic.width) // 2, (y0 + y1 - ic.height) // 2), ic)
        return
    s = 4; w, h = x1 - x0, y1 - y0       # 기본: 직접 그린 아이스바 (4배 그려 축소)
    big = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
    S = lambda *v: [c * s for c in v]
    for cx in (66, 106):
        d.rounded_rectangle(S(cx - 9, 120, cx + 9, 162), radius=9 * s, fill=(255, 255, 255))
    for bx in (36, 86):
        d.rounded_rectangle(S(bx, 10, bx + 50, 130), radius=24 * s, fill=(255, 255, 255))
        d.rounded_rectangle(S(bx + 7, 17, bx + 43, 123), radius=18 * s, fill=(247, 147, 106))
    big = big.resize((w, h), Image.LANCZOS); img.paste(big, (x0, y0), big)

def build_base(title, with_title=True):
    """본편 고정 화면. with_title=False 는 인트로 바탕 — 원본 인트로엔 제목 칸이 비어 있고 그 위에 훅이 얹힘."""
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, HEADER_H - 1), fill=NAVY)
    for y, c in HEADER_EDGE.items():
        d.line((0, y, W, y), fill=c)
    name = CFG.get("channel_name", "먹보")
    half = (len(name) + 1) // 2
    for part, cx in zip((name[:half], name[half:]), NAME_CX):
        draw_line(d, part, NAME_FONT, NAME_SIZE, cx, NAME_BASE, (255, 255, 255), maxw=200)
    draw_icon(img)
    if with_title:
        size = TITLE_MAX * min(1.0, TITLE_MAXW / text_w(font(TITLE_FONT, TITLE_MAX), title))
        draw_line(d, title, TITLE_FONT, size, W / 2, TITLE_CY + 0.4 * size, (0, 0, 0))
    for y, v in DIVIDER.items():
        d.line((DIV_X[0], y, DIV_X[1], y), fill=(v, v, v))
    return np.array(img)[:, :, ::-1].copy()

def build_intro_overlay(base_bgr, title, hook):
    """인트로: 위쪽(0~435) 어둡게 + 훅 2줄(테두리·그림자) + 흰 상자 제목. 영상 자리는 비워 둔다."""
    top = Image.fromarray((base_bgr[:INTRO_MEDIA_Y, :, ::-1].astype(np.float32) * INTRO_DIM).astype(np.uint8))
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0)); canvas.paste(top, (0, 0))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    tx = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dt = ImageDraw.Draw(tx)
    for line, size, base, col in zip(hook, HOOK_SIZE, HOOK_BASE, HOOK_COLORS):
        sz = draw_line(dt, line, HOOK_FONT, size, W / 2, base, col + (255,), maxw=HOOK_MAXW,
                       stroke_width=HOOK_STROKE, stroke_fill=(0, 0, 0, 255))
        draw_line(ds, line, HOOK_FONT, sz, W / 2 + HOOK_SHADOW[0], base + HOOK_SHADOW[1], (0, 0, 0, 255),
                  stroke_width=HOOK_STROKE, stroke_fill=(0, 0, 0, 255))
    db = ImageDraw.Draw(tx)
    db.rectangle(BOX, fill=(255, 255, 255, 255))
    draw_line(db, title, BOX_FONT, BOX_SIZE, (BOX[0] + BOX[2]) / 2, (BOX[1] + BOX[3]) / 2 + 0.4 * BOX_SIZE,
              (0, 0, 0, 255), maxw=BOX_MAXW)
    over = Image.alpha_composite(Image.alpha_composite(canvas, sh), tx)
    a = np.array(over)
    return a[:, :, 2::-1].copy(), (a[:, :, 3:4].astype(np.float32) / 255.0)

def sub_layer(lines):
    """자막 줄(최대 2줄) 알파 — 자막 띠 높이만 그린다."""
    y0, y1 = SUB_BASE[0] - 70, SUB_BASE[1] + 25
    m = Image.new("L", (W, y1 - y0), 0); d = ImageDraw.Draw(m)
    for i, line in enumerate(lines[:2]):
        draw_line(d, clean(line), SUB_FONT, SUB_SIZE, W / 2, SUB_BASE[i] - y0, 255)
    return y0, (np.array(m).astype(np.float32) / 255.0)[:, :, None]

# ---------------- 미디어 ----------------
def load_image(path):
    im = Image.open(path).convert("RGB")
    return np.array(im)[:, :, ::-1].copy()

def cover(img, w, h, focus=(0.5, 0.5)):
    """칸을 꽉 채우게 자르고 맞춤. focus(가로·세로 비율)가 칸 가운데에 오게 자른다 —
    원본은 인물·행위가 영상 칸 가운데(가로 50%·세로 45~50%)에 오게 잡고, 확대는 칸 가운데 기준이다."""
    ih, iw = img.shape[:2]; a = w / h
    if iw / ih > a:
        nw = int(round(ih * a)); x0 = int(round(focus[0] * iw - nw / 2)); x0 = min(max(x0, 0), iw - nw); img = img[:, x0:x0 + nw]
    else:
        nh = int(round(iw / a)); y0 = int(round(focus[1] * ih - nh / 2)); y0 = min(max(y0, 0), ih - nh); img = img[y0:y0 + nh]
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

class Media:
    def __init__(self, path, start=0.0, crop=None):
        self.is_video = os.path.splitext(path)[1].lower() in (".mp4", ".webm", ".mov", ".mkv", ".m4v")
        self.crop = crop
        if self.is_video:
            self.reader = VideoReader(path, start, FPS)
            if self.reader.last is None:  # 시작 시각이 영상 길이를 넘음 — 빈 화면으로 넘어가지 않게 바로 멈춘다
                raise SystemExit(f"소재 시작 {start}초가 영상 길이 {self.reader.duration:.1f}초를 넘음: {path}")
        self.last = self._crop(self.reader.last if self.is_video else load_image(path))
    def _crop(self, fr):
        if self.crop is None or fr is None: return fr
        h, w = fr.shape[:2]; x0, y0, x1, y1 = self.crop
        return fr[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
    def frame(self, t):
        if self.is_video: self.last = self._crop(self.reader.frame(t))
        return self.last

class Renderer:
    def __init__(self, proj):
        self.proj = proj
        self.script = json.load(open(os.path.join(proj, "script.json"), encoding="utf-8"))
        tp = os.path.join(proj, "timing.json")
        self.timing = json.load(open(tp, encoding="utf-8")) if os.path.exists(tp) else self.fake_timing()
        s = self.script
        self.base = build_base(s["title"])
        self.intro_rgb, self.intro_a = build_intro_overlay(build_base(s["title"], with_title=False), s["title"], s["hook"])
        self.subs, self.media, self.blank = {}, {}, {}
        self.starts = [c["start"] for c in self.timing["cards"]]
        if self.starts != sorted(self.starts):
            raise SystemExit("timing.json 의 카드 시작 시각이 시각 순이 아닙니다 — `python preset.py tts <프로젝트> --reuse` 로 다시 만드세요")

    def reset_media(self):
        """소재 읽기(앞으로만 가는 파이프)와 빈 화면 셈을 처음으로 — 같은 편을 다시 그릴 때."""
        for m in self.media.values():
            if m.is_video:
                m.reader.close()
        self.media, self.blank = {}, {}

    def fake_timing(self):
        t, cards = 1.8, []
        for c in self.script["cards"]:
            cards.append({"start": t, "line_starts": [t + 0.8 * i for i in range(len(c["lines"]))]})
            t += 0.8 * len(c["lines"]) + 0.4
        return {"intro_end": 1.8, "cards": cards, "end": t}

    def get_media(self, key, spec):
        if key not in self.media:
            spec = {"path": spec} if isinstance(spec, str) else spec
            self.media[key] = Media(os.path.join(self.proj, spec["path"]), spec.get("start", 0.0), spec.get("crop"))
        return self.media[key]

    def frame_at(self, t):
        tm = self.timing
        if t < tm["intro_end"]:
            fr = self.base.copy()
            im = self.script.get("intro_media")
            if im:
                fr[INTRO_MEDIA_Y:] = cover(self.get_media("intro", im).frame(t), W, H - INTRO_MEDIA_Y,
                                           tuple(im.get("focus", (0.5, 0.5))) if isinstance(im, dict) else (0.5, 0.5))
            return (fr * (1 - self.intro_a) + self.intro_rgb * self.intro_a).astype(np.uint8)
        cards = tm["cards"]
        ci = max(0, bisect.bisect_right(self.starts, t) - 1)   # 시작 시각 순 — 프레임마다 카드 전체를 훑지 않는다
        c = cards[ci]; card = self.script["cards"][ci]
        n = max(1, sum(1 for ls in c["line_starts"] if t >= ls))
        fr = self.base.copy()
        if (ci, n) not in self.subs:
            self.subs[(ci, n)] = sub_layer(card["lines"][:n])
        y0, a = self.subs[(ci, n)]
        reg = fr[y0:y0 + a.shape[0]]
        fr[y0:y0 + a.shape[0]] = (reg * (1 - a)).astype(np.uint8)
        # media 는 한 개(카드 내내 한 컷) 또는 목록(k번째 줄부터 k번째 컷). 컷 안에서 줄이 바뀌면 «툭» 들어감
        media = card.get("media")
        if media:
            lst = media if isinstance(media, list) else [media]
            k = min(n, len(lst)) - 1
            spec = lst[k]
            t0 = c["line_starts"][k] if isinstance(media, list) else c["start"]
            m = self.get_media((ci, k), spec)
            img = m.frame(t - t0)
            f = int(round((t - t0) * FPS))
            z = ENTRY[f] if f < len(ENTRY) else 1.0
            for ls in c["line_starts"][k + 1:n]:   # 이 컷이 보이는 동안 새로 나온 자막 줄
                pf = int(round((t - ls) * FPS))
                z *= PUNCH[min(pf, len(PUNCH) - 1)]
            img = cover(img, W, MEDIA_H, tuple(spec.get("focus", (0.5, 0.5))) if isinstance(spec, dict) else (0.5, 0.5))
            if z != 1.0:   # 칸 가운데(= 피사체) 기준 확대
                ih, iw = img.shape[:2]; ch, cw = int(ih / z), int(iw / z)
                img = cv2.resize(img[(ih - ch) // 2:(ih - ch) // 2 + ch, (iw - cw) // 2:(iw - cw) // 2 + cw], (W, MEDIA_H), interpolation=cv2.INTER_LINEAR)
            if float(img[::8, ::8].std()) < 8:    # 거의 한 색(흰 전환·검은 화면) — 원본엔 없는 빈 화면
                self.blank[(ci, k)] = self.blank.get((ci, k), 0) + 1
            fr[MEDIA_Y:MEDIA_Y + MEDIA_H] = img
        return fr

    def mix_audio(self, narration, out):
        """내레이션 + 클립 자체 소리 + 효과음 + 배경음악을 한 번의 ffmpeg 로 섞는다.
        참고 채널 원본: 배경음악이 처음부터 끝까지 깔리고, 영상 클립 자체 소리와 편집 효과음(쿵·띠용 등)이 얹힌다.
        음량 기본값(clip_db·sfx_db·bgm_db)은 원본에서 잰 값이 아니다 — config.json 에서 귀로 맞춘다."""
        tm, cards = self.timing, self.script["cards"]
        total = tm["end"]
        ins, labels, chains = ["-i", narration], ["[0:a]"], []
        def add(path, filt, pre=()):
            k = len(labels)
            ins.extend([*pre, "-i", path]); labels.append(f"[a{k}]")
            chains.append(f"[{k}:a]{filt}[a{k}]")
        has_audio = {}
        def clip(m, t0, t1):  # 클립 자체 소리: 그 칸이 보이는 동안만
            if not (isinstance(m, dict) and m.get("audio")):
                return
            p = os.path.join(self.proj, m["path"])
            if p not in has_audio:
                has_audio[p] = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                                    "stream=index", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip())
            if has_audio[p]:
                st = m.get("start", 0.0)
                add(p, f"atrim={st}:{st + t1 - t0},asetpts=PTS-STARTPTS,volume={m.get('audio_db', CFG.get('clip_db', -10))}dB,"
                       f"adelay={int(t0 * 1000)}:all=1")
        clip(self.script.get("intro_media"), 0.0, tm["intro_end"])
        for ci, card in enumerate(cards):
            t0 = tm["cards"][ci]["start"]
            t1 = tm["cards"][ci + 1]["start"] if ci + 1 < len(cards) else total
            med = card.get("media")
            if isinstance(med, list):
                ls = tm["cards"][ci]["line_starts"]
                for k, mk in enumerate(med):
                    clip(mk, ls[min(k, len(ls) - 1)], ls[k + 1] if k + 1 < len(ls) and k + 1 < len(med) else t1)
            else:
                clip(med, t0, t1)
            for fx in card.get("sfx", []):
                fx = {"name": fx} if isinstance(fx, str) else fx
                ls = tm["cards"][ci]["line_starts"]
                at = ls[min(fx["line"], len(ls) - 1)] if "line" in fx else t0 + fx.get("at", 0.0)   # line: 그 자막 줄이 나올 때
                add(os.path.join(ROOT, "assets", "sfx", fx["name"] + ".mp3"),
                    f"volume={fx.get('db', CFG.get('sfx_db', 3))}dB,adelay={int(at * 1000)}:all=1")
        if CFG.get("bgm"):
            add(os.path.join(ROOT, CFG["bgm"]), f"atrim=0:{total},volume={CFG.get('bgm_db', -18)}dB", pre=("-stream_loop", "-1"))
        fc = ";".join(chains + [f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,apad=whole_dur={total}[out]"])
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[out]", "-ar", "48000", "-ac", "2", out], check=True)
        return out

    def render(self, out, narration=None, size=None, fps=FPS, quality=("medium", 18)):
        """size·fps·quality 는 굽기 전 미리보기(tools/review.py — 같은 그림을 작게)만 바꾼다. 완성본은 기본값 그대로."""
        n = int(round(self.timing["end"] * fps))
        ow, oh = size or (W, H)
        audio = self.mix_audio(narration, os.path.join(self.proj, "final_audio.wav")) if narration else None
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ow}x{oh}", "-r", str(fps), "-i", "-"]
        if audio: cmd += ["-i", audio]
        cmd += [*x264(quality[0], quality[1], ow, oh, fps), "-pix_fmt", "yuv420p", "-t", f"{n / fps:.3f}"]   # 인코더 자리(실행기 공통 판정)
        if audio: cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        for gpu, argv in enc_attempts(cmd + ["-movflags", "+faststart", out]):   # GPU 1번 · 굽다 실패하면 프레임을 처음부터 CPU 1번
            with gpu_slot(gpu):
                p = subprocess.Popen(argv, stdin=subprocess.PIPE)
                try:
                    for i in range(n):
                        fr = self.frame_at(i / fps)
                        p.stdin.write((fr if size is None else cv2.resize(fr, (ow, oh), interpolation=cv2.INTER_AREA)).tobytes())
                    p.stdin.close()
                except BaseException as e:
                    # 인코더가 먼저 죽었다 — 종료 코드로 가른다. 읽는 쪽이 끝난 파이프: POSIX 는 BrokenPipeError(EPIPE), 윈도우는 OSError(EINVAL 22) — 파이썬 subprocess._stdin_write 와 같은 자(bpo-19612·bpo-30418). 그 밖의 OSError(디스크 가득 등)는 그대로 올린다.
                    if not (isinstance(e, OSError) and (isinstance(e, BrokenPipeError) or e.errno in (errno.EPIPE, errno.EINVAL))):
                        p.kill(); p.wait()
                        if os.path.exists(out): os.remove(out)   # 반쪽 파일을 남기지 않는다
                        raise
                p.wait()
            if p.returncode == 0:
                break
            if gpu is None:
                raise SystemExit("ffmpeg 실패")
            enc_failed(gpu, f"종료 코드 {p.returncode}")
            self.reset_media()                      # 다시 그리는 판 — 소재 읽기·빈 화면 셈을 처음부터
        bad = {k: v for k, v in self.blank.items() if v * FPS > 6 * fps}   # 0.2초 넘게 빈 화면인 컷(30fps 6장 — 미리보기 fps 로 같은 시간)
        if bad:
            os.remove(out)
            raise SystemExit("빈 화면(한 색) 컷 — 소재 구간을 바꿔라: " + ", ".join(
                f"카드{ci + 1}-{k + 1}컷 {v / fps:.1f}초" for (ci, k), v in bad.items()))

def _sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_receipt(proj, out, review):
    """렌더 영수증 — 이 렌더가 만든 영상(sha256)과 그때의 대본·타이밍, 그리고 굽기 전 판정을 묶는다. `check` 가 지금 영상과 대조한다.
    대본·타이밍 지문은 굽기 전 판정 대조(review.require_pass)가 잰 값을 그대로 쓴다(같은 파일을 다시 재지 않는다)."""
    rec = {"video": os.path.basename(out), "video_sha256": _sha(out),
           "script_sha256": review["script_sha256"], "timing_sha256": review["timing_sha256"],
           "pre_render_review": {"verdict": review["verdict"], "file": review["file"], "model": review.get("model"),
                                 "script_sha256": review["script_sha256"], "timing_sha256": review["timing_sha256"]}}
    json.dump(rec, open(os.path.join(proj, "render_receipt.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    proj = os.path.abspath(sys.argv[1]); r = Renderer(proj)
    if "--still" in sys.argv:
        t = float(sys.argv[sys.argv.index("--still") + 1]); out = os.path.join(proj, f"still_{t:.2f}.png")
        imwrite(out, r.frame_at(t)); print(out)
    else:
        import review                               # 굽기 전 판정(agy 한 번 · 판정은 코드) — 없거나 낡았거나 실패면 굽지 않는다
        ok = review.require_pass(proj)
        narr = os.path.join(proj, "narration.wav")
        out = os.path.join(proj, "out.mp4"); r.render(out, narr if os.path.exists(narr) else None)
        write_receipt(proj, out, ok)
        print(out)
