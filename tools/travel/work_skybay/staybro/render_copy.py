"""스테이브로 1위 편(ee3U4FtLb10 '상위 1% 고급 온천', 13.9만 회) 틀 그대로 — 숙소만 스카이베이 경포로.

    py tools/travel/work_skybay/staybro/render_copy.py            → work/out.mp4 (+ 바탕화면 복사)

원본 실측(2026-10-23, 줄판독 0.2초 띠·컷 검출·움직임 측정)에서 옮긴 것:
  - 0~0.1초(3프레임) 썸네일 화면: 대표 사진 + 작은 줄(흰 66px) + 큰 줄(흰 ExtraBold 150px), 뒤에 번지는 검은 그림자
  - 본편 컷 1.1~1.8초, 문장 경계 = 컷 경계, 문장 안은 자막 조각 경계에서 자른다(원본 85% 일치)
  - 컷 안 움직임 = 카메라가 천천히 밀고 들어가는 입체 움직임(원본은 사진→AI 영상 변환으로 추정, 24fps 흔적).
    여기서는 사진 깊이(Depth Anything V2 small)로 가까운 것은 더, 먼 것은 덜 커지게 해 같은 입체감을 낸다(무료·로컬)
  - 자막: Pretendard SemiBold 흰 글자 한 줄, 가운데 y≈572, 1~2어절 조각, 등장 효과 없음, 번지는 검은 그림자(딱딱한 외곽선 아님)
  - 워터마크: 가운데 아래 y≈1426 반투명 작은 글자
  - 소리: 나레이션 쉼 없이 이어 말하기, 배경음악 깔림, 전체 -14.4 LUFS
기준값은 원본 영상이 정본이다(디자인 토큰을 새로 만들지 않는다 — 원본 숫자 그대로).
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
W = HERE / "work"
PH = HERE.parent / "photos"
FONT = Path.home() / ".shottem/packs/font"
DEPTH = Path.home() / "숏템자료/models/onnx/model.onnx"
FPS, WD, HT = 30, 1080, 1920
THUMB_S = 0.1
TAIL_S = 0.35
SPEED = 1.15            # 미나 1.35배 위에 한 번 더 — 원본 말 속도 8.2자/초(상위 10편 중앙)에 맞춘다
BRAND = "@skybay.shortem"
BGM = Path.home() / ".shottem/packs/bgm/blue.mp3"     # 임시 — 사용권 미확인(라이브러리 곡). 올리기 전에 바꿀 것

# 자막 조각 = 원본처럼 뜻 덩어리 1~2어절(직접 끊음). 줄마다 이어 붙이면 lines.json 문장과 같아야 한다
CHUNKS = [
    ["강릉에서", "손꼽히는", "오션뷰 호텔이", "있습니다."],
    ["탁 트인 로비를", "지나면", "통유리", "실내 수영장을", "즐길 수 있고요."],
    ["창밖으로", "바다가 보이는", "피트니스에", "사우나까지", "있습니다."],
    ["특히", "20층 꼭대기로", "올라가면", "동해를", "내려다보는", "인피니티풀이", "펼쳐져요."],
    ["바깥 수영장이지만", "한겨울에도", "온수라", "따뜻하게", "즐길 수 있고,"],
    ["누운 채", "일출까지", "보고 싶다면", "한 번쯤", "묵어 볼", "만하겠죠?"],
]
# 문장마다 컷 = [(사진, 가로 중심 0~1)]. 자르는 자리는 cut_points 가 자막 조각 경계 중 원본 컷 길이(1.3초)에 가장 가깝게 고른다.
# 원본 이야기 = 걸어 들어가는 순서(입구→안 시설→'특히' 밖의 하이라이트→'~지만' 반전→상황 권유). 사진도 그 순서로 놓는다.
# 마지막 컷 = 썸네일 사진(원본도 첫 0.1초 썸네일 건물이 끝 컷으로 다시 나온다)
SHOTS = [
    [("11", 0.38), ("14", 0.66)],
    [("09", 0.50), ("06", 0.55)],
    [("07", 0.70), ("08", 0.50)],
    [("00", 0.36), ("05", 0.45), ("04", 0.72)],
    [("04", 0.30), ("05", 0.80)],
    [("18", 0.62), ("10", 0.42)],
]
CUT_S = 1.3
THUMB = ("10", 0.42, "강릉 평점 9.1", "오션뷰호텔")


# ---------- 깊이 ----------
_sess = None


def depth(img):
    """0(멀다)~1(가깝다). Depth Anything V2 small(onnx-community) — 518 입력, 상대 역깊이."""
    global _sess
    if _sess is None:
        _sess = ort.InferenceSession(str(DEPTH), providers=["CPUExecutionProvider"])
    h, w = img.shape[:2]
    x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (518, 518), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
    d = _sess.run(None, {_sess.get_inputs()[0].name: x})[0][0]
    d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
    d = (d - np.percentile(d, 2)) / max(1e-6, np.percentile(d, 98) - np.percentile(d, 2))
    return cv2.GaussianBlur(np.clip(d, 0, 1).astype(np.float32), (0, 0), 6)    # 경계에서 찢어지지 않게 깊이를 부드럽게


def vertical(name, cx):
    """가로 사진 → 9:16 세로(높이 꽉, 가운데 cx). 원본처럼 색을 진하게(채도·대비) + 1.6배 확대 흐림을 선명화로 덮는다."""
    im = cv2.imdecode(np.fromfile(str(PH / (name + ".jpg")), np.uint8), cv2.IMREAD_COLOR)
    h, w = im.shape[:2]
    cw = int(round(h * 9 / 16))
    x0 = int(np.clip(cx * w - cw / 2, 0, w - cw))
    im = cv2.resize(im[:, x0:x0 + cw], (WD, HT), interpolation=cv2.INTER_LANCZOS4)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.22, 0, 255)
    im = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    im = np.clip((im - 128) * 1.08 + 128, 0, 255)
    bl = cv2.GaussianBlur(im, (0, 0), 1.6)
    return np.clip(im * 1.55 - bl * 0.55, 0, 255).astype(np.uint8)


def dolly(img, dep, n, z0=0.03, zp=0.10, cy=0.55, lat=0.0):
    """카메라가 앞으로 들어가는 입체 움직임. 화면 점 p 는 원본 q = c + (p-c)/s(q), s = 1 + u·(z0 + zp·깊이).
    가까운 것(깊이 1)은 z0+zp 만큼, 먼 것(0)은 z0 만큼 커진다 → 앞뒤가 따로 움직인다. s≥1 이라 바깥이 드러나지 않는다."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    c = np.array([w * 0.5, h * cy], np.float32)
    for k in range(n):
        u = k / max(1, n - 1)
        s = 1 + u * (z0 + zp * dep)
        qx, qy = c[0] + (xx - c[0]) / s - u * lat * w * dep, c[1] + (yy - c[1]) / s
        for _ in range(2):                                     # 깊이를 q 자리에서 다시 읽어 맞춘다
            dq = cv2.remap(dep, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            s = 1 + u * (z0 + zp * dq)
            qx, qy = c[0] + (xx - c[0]) / s - u * lat * w * dq, c[1] + (yy - c[1]) / s
        yield cv2.remap(img, qx, qy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


# ---------- 글자 ----------
def text_layer(lines, sizes, ys, fonts, glow=(14, 1.0), spacing=-0.04, squeeze=0.9, grow=13):
    """흰 글자 + 번지는 검은 그림자(원본 실측: 외곽선 없이 넓게 번진 어두운 후광). RGBA 한 장."""
    lay = Image.new("RGBA", (WD, HT), (0, 0, 0, 0))
    ink = Image.new("L", (WD, HT), 0)
    d = ImageDraw.Draw(ink)
    for t, sz, y, f in zip(lines, sizes, ys, fonts):
        # 원본 글자는 가로로 살짝 좁다(실측 글자 높이 75px·폭 68px) — 넓게 그린 뒤 가로만 squeeze 배로 줄인다
        ft = ImageFont.truetype(str(FONT / f), sz)
        adv = [ft.getlength(ch) + sz * spacing for ch in t]
        tw = int(sum(adv)) + sz
        one = Image.new("L", (tw, sz * 2), 0)
        od = ImageDraw.Draw(one)
        x = sz / 2
        for ch, a in zip(t, adv):
            od.text((x, sz), ch, font=ft, fill=255, anchor="lm")
            x += a
        one = one.resize((max(1, int(tw * squeeze)), sz * 2), Image.LANCZOS)
        ink.paste(one, (int((WD - one.width) / 2), int(y - sz)), one)
    sh = ink.filter(ImageFilter.MaxFilter(grow)).filter(ImageFilter.GaussianBlur(glow[0]))
    sh = sh.point(lambda v: int(min(255, v * glow[1] * 1.8)))
    lay.paste((0, 0, 0, 255), (0, 0), sh)
    lay = Image.alpha_composite(lay, Image.merge("RGBA", (ink.point(lambda v: 255),) * 3 + (ink,)))
    return np.array(lay)


def over(frame, rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255
    rgb = rgba[..., [2, 1, 0]].astype(np.float32)
    return (frame * (1 - a) + rgb * a).astype(np.uint8)


# ---------- 소리·시간표 ----------
def voice():
    """줄 음성을 쉼 없이 이어 붙이고 SPEED 배로. 어절 시각도 같은 배로."""
    v = json.load(open(W / "voice.json", encoding="utf-8"))
    lst = W / "concat.txt"
    lst.write_text("".join("file '%s'\n" % x["mp3"] for x in v), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-filter:a", "atempo=%.4f" % SPEED, "-ar", "44100", str(W / "narr.wav")], check=True, cwd=W)
    t, sent = 0.0, []
    for x in v:
        sent.append({"t0": t / SPEED, "dur": x["dur"] / SPEED, "words": [(w.get("w") or w.get("word"), (t + w.get("t", w.get("start", 0))) / SPEED) for w in x["words"]]})
        t += x["dur"]
    return sent, t / SPEED


def chunk_times(sent):
    """CHUNKS 조각마다 시작 시각 = 그 조각 첫 어절의 시작."""
    out = []
    for si, (s, chs) in enumerate(zip(sent, CHUNKS)):
        words = [w for w, _ in s["words"]]
        assert "".join(words).replace(" ", "") == "".join(chs).replace(" ", ""), (si, words, chs)
        k, row = 0, []
        for ch in chs:
            row.append(THUMB_S + s["words"][k][1])
            k += len(ch.split())
        out.append(row)
    return out


def cut_points(row, end, k):
    """문장 안 컷 시작 시각 k개 — 첫 조각에서 시작, 나머지는 조각 경계 중 컷 길이가 CUT_S 에 가장 가깝게."""
    import itertools
    best = None
    for comb in itertools.combinations(range(1, len(row)), k - 1):
        st = [row[0]] + [row[i] for i in comb]
        lens = [b - a for a, b in zip(st, st[1:] + [end])]
        cost = sum((x - CUT_S) ** 2 for x in lens)
        if best is None or cost < best[0]:
            best = (cost, st)
    return best[1]


def main():
    sent, vdur = voice()
    ct = chunk_times(sent)
    total = THUMB_S + vdur + TAIL_S
    nf = int(round(total * FPS))
    # 자막 조각 (시작, 끝, 글)
    caps = []
    flat = [(t, txt) for row, chs in zip(ct, CHUNKS) for t, txt in zip(row, chs)]
    for i, (t, txt) in enumerate(flat):
        caps.append((t, flat[i + 1][0] if i + 1 < len(flat) else total, txt))
    # 컷 (시작, 끝, 사진, 중심)
    cuts = []
    for si, shots in enumerate(SHOTS):
        end = ct[si + 1][0] if si + 1 < len(ct) else total
        starts = cut_points(ct[si], end, len(shots))
        if si == 0:
            starts[0] = THUMB_S
        for (ph, cx), t0 in zip(shots, starts):
            cuts.append([t0, None, ph, cx])
    for i in range(len(cuts)):
        cuts[i][1] = cuts[i + 1][0] if i + 1 < len(cuts) else total
    plan = {"total": round(total, 3), "cuts": [[round(a, 2), round(b, 2), p, c] for a, b, p, c in cuts],
            "caps": [[round(a, 2), round(b, 2), t] for a, b, t in caps]}
    (W / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("길이 %.2f초 · 컷 %d · 자막 %d · 컷 길이 %s" % (total, len(cuts), len(caps), [round(b - a, 2) for a, b, _, _ in cuts]))

    pre = "Pretendard-SemiBold.otf"
    cap_png = {txt: text_layer([txt.replace(" ", "")], [90], [572], [pre]) for _, _, txt in caps}   # 원본 자막은 띄어쓰기를 뺀다
    wm = text_layer([BRAND], [34], [1426], ["Pretendard-Regular.otf"], glow=(4, 0.5), spacing=0, squeeze=1, grow=3)
    wm[..., 3] = (wm[..., 3] * 0.55).astype(np.uint8)
    th = THUMB
    thumb_txt = text_layer([th[2], th[3]], [100, 172], [515, 690], ["Pretendard-Bold.otf", "Pretendard-ExtraBold.otf"], glow=(20, 1.0), grow=17)

    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (WD, HT),
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                           "-pix_fmt", "yuv420p", str(W / "video.mp4")], stdin=subprocess.PIPE)
    fi = 0
    plan_lat = []
    # 썸네일 화면 3프레임
    timg = vertical(th[0], th[1])
    for _ in range(int(round(THUMB_S * FPS))):
        ff.stdin.write(over(over(timg, thumb_txt), wm).tobytes())
        fi += 1
    for a, b, ph, cx in cuts:
        a = max(a, THUMB_S)
        n = int(round(b * FPS)) - fi
        img = vertical(ph, cx)
        dep = depth(img)
        lat = 0.012 * (1 if len(plan_lat) % 2 else -1)            # 컷마다 옆으로 번갈아 조금 — 앞뒤 어긋남(입체감)을 키운다
        plan_lat.append(lat)
        for fr in dolly(img, dep, n, lat=lat):
            t = fi / FPS
            cap = next((c for c in caps if c[0] <= t < c[1]), None)
            if cap:
                fr = over(fr, cap_png[cap[2]])
            ff.stdin.write(over(fr, wm).tobytes())
            fi += 1
        print("  컷 %s %.2f~%.2f %d프레임" % (ph, a, b, n), flush=True)
    ff.stdin.close()
    ff.wait()

    # 소리: 나레이션 + 배경음악(나레이션 아래 -18dB 가량), 전체 -14.4 LUFS
    af = ("[1:a]adelay=%d|%d,apad=whole_dur=%.3f[nv];[2:a]atrim=0:%.3f,volume=0.16,afade=t=out:st=%.3f:d=0.4[bg];"
          "[nv][bg]amix=inputs=2:normalize=0,loudnorm=I=-14.4:TP=-1.0:LRA=7[a]"
          % (THUMB_S * 1000, THUMB_S * 1000, total, total, total - 0.4))
    out = W / "out.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(W / "video.mp4"), "-i", str(W / "narr.wav"), "-i", str(BGM),
                    "-filter_complex", af, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "44100", "-t", "%.3f" % total, str(out)], check=True)
    print("완성", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
