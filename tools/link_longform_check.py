"""구매링크용 롱폼 결과물 검사 — 만든 가로 영상을 원본 쇼츠와 **영상으로** 대조한다(관제 132).

  py tools/link_longform_check.py <원본 쇼츠.mp4> <롱폼.mp4> [link_longform_layout.json]

꾸민 안내(세 번째 인자, 관제 133)가 있으면 ④⑤⑦을 이렇게 잰다 — 같은 그리기 코드로 '그 시각의 안내 그림'을 다시 뽑아
원본 쇼츠 위에 얹은 예상 화면과 롱폼의 실제 화면을 대조한다(자리·문구·줄어드는 시계 숫자까지 한 번에 걸린다):
  ④ 가운데 = 원본 쇼츠 + 안내 그림   ⑤ 문구 띠가 가운데를 실제로 덮는다   ⑦ 양옆 화살표가 안내 그림 색 그대로 보인다

재는 것(전부 파일에서 직접):
  ① 크기 1920x1080            ② 길이가 원본과 같다(±0.15초)      ③ 소리가 없다(무음 — 쇼츠 전용 곡이 실리면 안 된다)
  ④ 가운데가 원본 쇼츠와 같다(문구 띠 밖, 3시점)   ⑤ 문구가 보인다(띠 안 노란 글자)
  ⑥ 양옆이 검정이 아니다(흐린 배경)               ⑦ 화살표가 보인다(양옆 빨강)
실패가 하나라도 있으면 종료코드 1.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shopping_shorts import link_longform as LL  # noqa: E402


def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,width,height,duration", "-show_entries", "format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    return {"w": int(v["width"]), "h": int(v["height"]), "dur": float(j["format"]["duration"]),
            "a_dur": float(a["duration"]) if a and a.get("duration") else None}


def _frame(path, t, vf, out_png):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t, "-i", str(path), "-frames:v", "1",
                    "-vf", vf, str(out_png)], check=True, stdin=subprocess.DEVNULL)
    from PIL import Image
    return Image.open(out_png).convert("RGB")


def _mean_abs_diff(a, b):
    from PIL import ImageChops, ImageStat
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3.0


def _count(img, pred):
    return sum(n for n, px in img.getcolors(maxcolors=img.size[0] * img.size[1]) if pred(px))


def check_layout(src, out, items):
    """꾸민 안내로 구운 롱폼: 예상 화면(원본 + 다시 뽑은 안내 그림)과 실제 화면을 3시점에서 대조한다."""
    from PIL import Image, ImageChops, ImageStat
    res = []
    ps, po = _probe(src), _probe(out)
    res.append(("크기 1920x1080", (po["w"], po["h"]) == (LL.OUT_W, LL.OUT_H), "%dx%d" % (po["w"], po["h"])))
    res.append(("길이 = 원본(±0.15초)", abs(ps["dur"] - po["dur"]) <= 0.15, "원본 %.3f / 롱폼 %.3f" % (ps["dur"], po["dur"])))
    if LL.tts_text(items):
        ok = po["a_dur"] is not None and abs(po["a_dur"] - po["dur"]) <= 0.3
        res.append(("소리 = 읽어 줄 말(영상 길이만큼)", ok, "롱폼 소리 줄기 %s / 영상 %.3f" % (po["a_dur"], po["dur"])))
    else:
        res.append(("소리 없음(무음)", po["a_dur"] is None, "롱폼 소리 줄기 %s" % ("없음" if po["a_dur"] is None else "%.3f초" % po["a_dur"])))
    fg_w = LL.fg_width(ps["w"], ps["h"]); x0 = (LL.OUT_W - fg_w) // 2
    n = LL.frame_count(items, ps["dur"]); clock = any(m.get("clock") for m in items)
    frames = [int(ps["dur"] * LL.FPS * k) for k in (0.2, 0.5, 0.8)]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        want = [f if clock else f % n for f in frames]          # 시계가 없으면 한 바퀴(n장)를 되풀이해 얹었다
        LL.overlay_frames(items, td / "ov", sorted(set(want)))
        worst, cover, side_px, side_bad, side_lum = 0.0, 0, 0, 0, 0.0
        for i, (f, w) in enumerate(zip(frames, want)):
            t = f / LL.FPS + 0.002
            fo = _frame(out, t, "null", td / ("o%d.png" % i))
            fs = _frame(src, t, "scale=%d:%d" % (fg_w, LL.OUT_H), td / ("s%d.png" % i))
            ov = Image.open(td / "ov" / ("%05d.png" % w)).convert("RGBA")
            # ④ 가운데: 원본 + 안내 그림 = 실제
            exp = fs.convert("RGBA"); exp.alpha_composite(ov.crop((x0, 0, x0 + fg_w, LL.OUT_H)))
            worst = max(worst, _mean_abs_diff(fo.crop((x0, 0, x0 + fg_w, LL.OUT_H)), exp.convert("RGB")))
            # ⑤ 띠가 가운데를 덮는 넓이(불투명한 점)
            a = ov.split()[3].point(lambda v: 255 if v > 250 else 0)
            cover = max(cover, ImageStat.Stat(a.crop((x0, 0, x0 + fg_w, LL.OUT_H))).sum[0] / 255)
            # ⑦ 양옆: 안내 그림이 불투명한 점에서 실제 색 = 안내 그림 색(움직임 한 프레임 어긋남은 봐준다 → 점의 85% 이상)
            for xa, xb in ((0, x0), (x0 + fg_w, LL.OUT_W)):
                m = a.crop((xa, 0, xb, LL.OUT_H)); k = ImageStat.Stat(m).sum[0] / 255
                d = ImageChops.difference(fo.crop((xa, 0, xb, LL.OUT_H)), ov.convert("RGB").crop((xa, 0, xb, LL.OUT_H))).convert("L").point(lambda v: 255 if v > 40 else 0)
                side_px += k; side_bad += ImageStat.Stat(ImageChops.multiply(d, m)).sum[0] / 255
            if x0 >= 40:
                side_lum = max(side_lum, ImageStat.Stat(fo.crop((0, 0, x0, LL.OUT_H)).convert("L")).mean[0])
    res.append(("가운데 = 원본 쇼츠 + 안내 그림(평균차 ≤ 8)", worst <= 8.0, "가장 큰 평균차 %.2f" % worst))
    res.append(("문구 띠가 가운데를 덮는다(≥ 5000px)", cover >= 5000, "%d px" % cover))
    if x0 >= 40:
        res.append(("양옆 흐린 배경(밝기 > 12)", side_lum > 12, "밝기 %.1f" % side_lum))
        ok = side_px >= 3000 and side_bad <= side_px * 0.15
        res.append(("양옆 화살표가 안내 그림 색 그대로(≥ 3000px, 어긋난 점 ≤ 15%)", ok, "%d px 중 어긋남 %d" % (side_px, side_bad)))
    return res


def check(src, out):
    res = []
    ps, po = _probe(src), _probe(out)
    res.append(("크기 1920x1080", (po["w"], po["h"]) == (LL.OUT_W, LL.OUT_H), "%dx%d" % (po["w"], po["h"])))
    res.append(("길이 = 원본(±0.15초)", abs(ps["dur"] - po["dur"]) <= 0.15,
                "원본 %.3f / 롱폼 %.3f" % (ps["dur"], po["dur"])))
    res.append(("소리 없음(무음)", po["a_dur"] is None, "롱폼 소리 줄기 %s" % ("없음" if po["a_dur"] is None else "%.3f초" % po["a_dur"])))
    fg_w = LL.fg_width(ps["w"], ps["h"])
    x0 = (LL.OUT_W - fg_w) // 2
    y0, y1 = LL.band_box()
    side = x0
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        worst, band_yellow, side_dark, side_red = 0.0, 0, 0.0, 0
        times = [ps["dur"] * k for k in (0.2, 0.5, 0.8)]
        for i, t in enumerate(times):
            fo = _frame(out, t, "null", td / ("o%d.png" % i))
            fs = _frame(src, t, "scale=%d:%d" % (fg_w, LL.OUT_H), td / ("s%d.png" % i))
            # ④ 가운데(띠 위·아래)가 원본과 같은가
            for (ya, yb) in ((0, y0), (y1, LL.OUT_H)):
                d = _mean_abs_diff(fo.crop((x0, ya, x0 + fg_w, yb)), fs.crop((0, ya, fg_w, yb)))
                worst = max(worst, d)
            # ⑤ 띠 안 노란 글자 — 원본 화면이 원래 노란 경우를 빼고 센다(2026-10-05: 노란 시험 화면에서
            #    문구 없는 가짜가 통과했다). 가운데는 원본의 같은 자리, 양옆은 띠 바로 아래 같은 높이를 기준으로 뺀다.
            yel = lambda p: p[0] > 200 and p[1] > 180 and p[2] < 90
            red = lambda p: p[0] > 190 and p[1] < 80 and p[2] < 90
            bh = y1 - y0
            base = _count(fs.crop((0, y0, fg_w, y1)), yel)
            if side >= 40:
                for xa, xb in ((0, side), (LL.OUT_W - side, LL.OUT_W)):
                    base += _count(fo.crop((xa, y1, xb, y1 + bh)), yel)
            band_yellow = max(band_yellow, _count(fo.crop((0, y0, LL.OUT_W, y1)), yel) - base)
            # ⑥ 양옆 밝기(검정 띠가 아니어야) — 원본이 어두운 장면일 수 있어 3시점 중 가장 밝은 값으로 본다
            from PIL import ImageStat
            if side >= 40:
                lum = ImageStat.Stat(fo.crop((0, 0, side, LL.OUT_H)).convert("L")).mean[0]
                side_dark = max(side_dark, lum)
                # ⑦ 화살표(250~440줄)의 빨강 — 띠 아래 같은 높이의 빨강을 기준으로 뺀다
                #    양옆 중 잘 보이는 쪽으로 판정한다(배경이 원래 빨간 쪽에서는 화살표가 색으로 안 갈린다).
                for xa, xb in ((0, side), (LL.OUT_W - side, LL.OUT_W)):
                    side_red = max(side_red, _count(fo.crop((xa, 240, xb, 450)), red)
                                   - _count(fo.crop((xa, y1, xb, y1 + 210)), red))
    res.append(("가운데 = 원본 쇼츠(띠 밖 평균차 ≤ 6)", worst <= 6.0, "가장 큰 평균차 %.2f" % worst))
    res.append(("문구 보임(노란 글자 ≥ 5000px)", band_yellow >= 5000, "%d px" % band_yellow))
    if side >= 40:
        res.append(("양옆 흐린 배경(밝기 > 12)", side_dark > 12, "밝기 %.1f" % side_dark))
        res.append(("화살표 보임(빨강 ≥ 3000px)", side_red >= 3000, "%d px" % side_red))
    return res


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    items = LL.normalize_layout(json.loads(Path(argv[3]).read_text(encoding="utf-8")).get("items")) if len(argv) == 4 else []
    res = check_layout(argv[1], argv[2], items) if items else check(argv[1], argv[2])
    bad = 0
    for name, ok, detail in res:
        print(("✅" if ok else "❌"), name, "—", detail)
        bad += 0 if ok else 1
    print("결과: %d개 중 %d개 통과" % (len(res), len(res) - bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
