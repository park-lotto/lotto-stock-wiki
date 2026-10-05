"""구매링크용 롱폼 결과물 검사 — 만든 가로 영상을 원본 쇼츠와 **영상으로** 대조한다(관제 132).

  py tools/link_longform_check.py <원본 쇼츠.mp4> <롱폼.mp4>

재는 것(전부 파일에서 직접):
  ① 크기 1920x1080            ② 길이가 원본과 같다(±0.15초)      ③ 소리 줄기가 원본과 같은 길이로 있다
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


def check(src, out):
    res = []
    ps, po = _probe(src), _probe(out)
    res.append(("크기 1920x1080", (po["w"], po["h"]) == (LL.OUT_W, LL.OUT_H), "%dx%d" % (po["w"], po["h"])))
    res.append(("길이 = 원본(±0.15초)", abs(ps["dur"] - po["dur"]) <= 0.15,
                "원본 %.3f / 롱폼 %.3f" % (ps["dur"], po["dur"])))
    if ps["a_dur"] is not None:
        ok = po["a_dur"] is not None and abs(ps["a_dur"] - po["a_dur"]) <= 0.15
        res.append(("소리 = 원본 길이", ok, "원본 %.3f / 롱폼 %s" % (ps["a_dur"], po["a_dur"])))
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
    if len(argv) != 3:
        print(__doc__)
        return 2
    res = check(argv[1], argv[2])
    bad = 0
    for name, ok, detail in res:
        print(("✅" if ok else "❌"), name, "—", detail)
        bad += 0 if ok else 1
    print("결과: %d개 중 %d개 통과" % (len(res), len(res) - bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
