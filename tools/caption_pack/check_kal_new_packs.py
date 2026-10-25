# -*- coding: utf-8 -*-
"""칼카피 새 판 자막팩 점검(관제 263 · 팩요청.md <판>#1) — 판마다 자막팩을 **실제 렌더**해 벤치 프레임과 대조한다.

    PYTHONUTF8=1 py tools/caption_pack/check_kal_new_packs.py [팩,...] [--out out/check_kal_new_packs]

벤치 프레임(같은 편·같은 시각) 의 자막 띠만 지운(inpaint) 바탕 위에 같은 글을 그 팩으로 그려(scene_style.render_layers — 렌더·캡컷·썸네일이
같이 쓰는 레이어 길) kal_analyze.frame_metrics 로 잉크 상자·높이·색을 잰다. 합격 = 좌표 ±4px · 높이 ±4px · 글자색 ΔE76 < 5(kal_analyze.FRAME_PASS).
여러 줄 덩어리는 줄 잉크 행(줄 간격)을 따로 잰다. pack_map 거리(1.0 = 같음 문턱)도 판마다 같이 낸다.
※ 벤치 자리는 편마다 다를 수 있다(안나픽 1110~1210 · 만템 나레 1223~1255) — 팩 자리는 한 값이라 그 편 차이는 표에 그대로 보인다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
BENCH = Path("C:/숏템_칼카피")
BOARD = {"썰템홈샷판": "banggu", "맛템썰템판": "yummyknow", "썰템쇼판": "humorshowshow", "숏템리폿판": "hottemreport", "신박판": "sinbak", "두유노판": "homedesignnote",
         "트롯파파판": "uljimatrot", "만템판": "mantem", "아이템홈판": "itemhome", "안나픽판": "annapick", "도파민썰템A판": "sseolpulda_a",
         "도파민썰템B판": "sseolpulda_b", "뜨거운사람들판": "hotpeople"}
# 쌓기 판(판 caption.stack) 벤치 줄 피치 px — 팩 place.y = 첫 줄 자리, 여러 줄은 stack_rows 가 덩어리 가운데를 옮긴다(판 stack.y·pitch 가 이 값이어야 한다)
STACK_PITCH = {"banggu": 78, "yummyknow": 89, "humorshowshow": 76}
# 팩 → 벤치 대조 칸 [편 영상(BENCH 아래), 초, 글(여러 줄 = \n), 벤치 잉크 y[위,아래](줄판독), 화자]
CASES = json.loads(r"""{
"banggu": [
[
"banggu/mp4/48PbLQ5az6k.mp4",
2.117,
"이 붓을 쓰는 모습을 보면",
[
504,
551
],
"narr"
],
[
"banggu/mp4/8iEhEniPpjE.mp4",
4.716,
"하지만 사람들이",
[
504,
551
],
"narr"
],
[
"banggu/mp4/E9hmVYVa7OY.mp4",
7.834,
"사실 오픈형 이어폰은",
[
503,
551
],
"narr"
],
[
"banggu/mp4/48PbLQ5az6k.mp4",
3.484,
"이 붓을 쓰는 모습을 보면\n사람들이 놀라는 부분이 있는데",
[
504,
630
],
"narr"
],
[
"banggu/mp4/8iEhEniPpjE.mp4",
3.8,
"코스트코에 가면 꼭 사야한다는\nEMMI 티라미수",
[
504,
630
],
"narr"
]
],
"yummyknow": [
[
"yummyknow/mp4/76uZKOpnlqQ.mp4",
3.284,
"콜라는 안 시켜도",
[
580,
631
],
"narr"
],
[
"yummyknow/mp4/8f9T8Jeo-gQ.720.mp4",
2.1,
"사실 명랑 핫도그는",
[
578,
631
],
"narr"
],
[
"yummyknow/mp4/PFvCfu1ECK4.mp4",
2.033,
"최근 코스트코는",
[
578,
631
],
"narr"
],
[
"yummyknow/mp4/76uZKOpnlqQ.mp4",
4.483,
"콜라는 안 시켜도\n치즈볼은 꼭 시킨다 할 정도로",
[
580,
721
],
"narr"
],
[
"yummyknow/mp4/8f9T8Jeo-gQ.720.mp4",
3.333,
"사실 명랑 핫도그는\n치명적인 단점이 존재하는데",
[
578,
721
],
"narr"
]
],
"humorshowshow": [
[
"humorshowshow/mp4/BlA9f8rBPuc.mp4",
5.833,
"부시맨빵은 이제",
[
500,
552
],
"narr"
],
[
"humorshowshow/mp4/NBdmq90aJus.mp4",
5.234,
"한국 진출을 조사하다",
[
498,
550
],
"narr"
],
[
"humorshowshow/mp4/bfKkNmVTGPs.mp4",
2.4,
"미국인들이 숨쉬듯",
[
500,
550
],
"narr"
],
[
"humorshowshow/mp4/BlA9f8rBPuc.mp4",
4.5,
"아웃백에 이거 먹으러 갈 정도로\n사람들이 환장하는 부시맨빵과 버터",
[
500,
628
],
"narr"
],
[
"humorshowshow/mp4/NBdmq90aJus.mp4",
4.1,
"디저트 하나로 북미 코스트코를\n씹어먹은 한 프랑스 회사",
[
500,
628
],
"narr"
]
],
"hottemreport": [
[
"hottemreport/mp4/IRFN5B_2LMo.mp4",
2.75,
"요즘 미국에서",
[
1365,
1443
],
"narr"
],
[
"hottemreport/mp4/IRFN5B_2LMo.mp4",
8.584,
"원래는 두바이 금수저",
[
1366,
1444
],
"narr"
]
],
"homedesignnote": [
["homedesignnote/src/DCXQjaWcZ-g.mp4", 1.75, "와이프한테 혼났어요", [587, 646], "narr"],
["homedesignnote/src/SU9YofB1IoI.mp4", 0.9, "이렇게 쓸 거라고는", [532, 597], "narr"],
["homedesignnote/src/EINoAh8C9rQ.mp4", 1.3, "결혼선물로 이거", [765, 827], "narr"]
],
"sinbak": [
[
"sinbak/src/CnRWZ3scVfk.mp4",
1.216,
"물로 죄를 씻어주고 있는데",
[
1299,
1364
],
"narr"
],
[
"sinbak/src/bpjoacs2S6Q.mp4",
3.55,
"알아두면 좋을 것 같음",
[
1299,
1364
],
"narr"
],
[
"sinbak/src/edTkyQKrqMk.mp4",
3.633,
"얼룩마다 치트키가 다름",
[
1300,
1363
],
"narr"
]
],
"uljimatrot": [
[
"uljimatrot/src/7b1j3LptlCo.mp4",
6.966,
"네이비 색상 착장에 매치한",
[
1165,
1249
],
"narr"
],
[
"uljimatrot/src/JlgdcIk9Gd0.mp4",
5.284,
"이번에 장윤정 가족은",
[
1168,
1246
],
"narr"
],
[
"uljimatrot/src/NXBepjjp6BY.mp4",
4.7,
"장윤정이 없는 틈을 타",
[
1165,
1250
],
"narr"
]
],
"mantem": [
[
"mantem/원본/9FcPMZtJVB0.mp4",
4.3,
"최근에 가장",
[
1323,
1391
],
"orig"
],
[
"mantem/원본/9FcPMZtJVB0.mp4",
6.483,
"원래 저는 좀 이렇게",
[
1321,
1390
],
"orig"
],
[
"mantem/원본/9FcPMZtJVB0.mp4",
9.183,
"아님 아주 작은",
[
1321,
1389
],
"orig"
],
[
"mantem/원본/3Xb8hDoRiU4.mp4",
2.984,
"대성이 10년째 정착중인",
[
1195,
1262
],
"narr"
],
[
"mantem/원본/9FcPMZtJVB0.mp4",
2.15,
"김혜수가 엄청 아끼는",
[
1226,
1284
],
"narr"
],
[
"mantem/원본/BDAjUIBTjfY.mp4",
2.667,
"장윤정이 비싸도",
[
1226,
1290
],
"narr"
]
],
"itemhome": [
[
"itemhome/원본/2uPIHITVEX8.mp4",
1.383,
"커플로 만난 서강준이",
[
1228,
1303
],
"narr"
],
[
"itemhome/원본/MfptnwqlGKs.mp4",
1.067,
"안유진이 약 사던",
[
1228,
1303
],
"narr"
],
[
"itemhome/원본/agEwVlDn25U.mp4",
0.65,
"녹차밭에 선 박진영이",
[
1229,
1297
],
"narr"
]
],
"annapick": [
[
"annapick/원본/Ww0IZLSL7mY.mp4",
3.35,
"몇개가 있는데",
[
1078,
1149
],
"narr"
],
[
"annapick/원본/rF_-X8jLkdU.mp4",
3.167,
"PPL(광고) 안받고",
[
1074,
1146
],
"narr"
],
[
"annapick/원본/iS0la2aQyl8.mp4",
10.716,
"파스타 할 때 넣으면",
[
1171,
1245
],
"narr"
],
[
"annapick/원본/wweUXE86oMM.mp4",
8.267,
"모든 사람한테",
[
1174,
1246
],
"narr"
],
[
"annapick/원본/wweUXE86oMM.mp4",
9.216,
"맞을수 있을지 모르겠어요",
[
1174,
1244
],
"narr"
]
],
"sseolpulda_a": [
[
"sseolpulda/mp4/ZdeZRtCeAC4.mp4",
9.117,
"진짜 아무 데나 대면",
[
1468,
1528
],
"narr"
],
[
"sseolpulda/mp4/ZdeZRtCeAC4.mp4",
16.517,
"소리 커지는 거 소름 돋네",
[
1468,
1528
],
"narr"
]
],
"sseolpulda_b": [
[
"sseolpulda/mp4/mYxuF1A74j4.mp4",
1.367,
"선수가 퍽을",
[
1229,
1317
],
"narr"
],
[
"sseolpulda/mp4/mYxuF1A74j4.mp4",
2.55,
"관중석으로 던졌어요",
[
1229,
1315
],
"narr"
],
[
"sseolpulda/mp4/mYxuF1A74j4.mp4",
4.45,
"퍽을 잡았지만",
[
1230,
1317
],
"narr"
]
],
"evenshopping": [
["evenshopping/src/ABjQ0YCZoes.mp4", 3.1, "이 여러겹의 네모난", [458, 513], "narr"],
["evenshopping/src/LHembw8EUU0.mp4", 6.9, "근데 한국에 한 천재가", [455, 513], "narr"],
["evenshopping/src/Y2YXuAE4J00.mp4", 10.5, "근데 한국의 한 천재가", [455, 513], "narr"]
],
"hotpeople": [
[
"hotpeople/src/N4VoQUIwb-I.mp4",
37.683,
"틈을 완벽하게 간파해버림",
[
1318,
1376
],
"narr"
],
[
"hotpeople/src/X4GIghUr_B4.mp4",
38.1,
"독학해서 아이들을 가르침",
[
1310,
1370
],
"narr"
],
[
"hotpeople/src/dvJg0By8Luw.mp4",
21.334,
"이름은 '방탄소년단'",
[
1322,
1382
],
"narr"
],
[
"hotpeople/src/BzMWncGDhnY.mp4",
1.35,
"한국 자전거 대회 역사상\n가장 충격적인 사건이 터짐.",
[
1288,
1426
],
"narr"
]
]
}""")
BOARD["이븐쇼핑판"] = "evenshopping"   # 재미썸홈 1차 판(관제 097 10-26)


def _bench_png(video: str, t: float, out: Path) -> Path:
    if not out.exists():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(BENCH / video), "-frames:v", "1", "-vf", "scale=1080:1920", str(out)], check=True)
    return out


def _clean_band(png: Path, band: tuple, out: Path) -> Path:
    """벤치 자막 띠의 글자만 지운다(중앙값 바탕과 다른 픽셀 → inpaint). 흐리기만 하면 흰 바탕에 회색 얼룩이 남아 잉크 측정이 엇나간다."""
    import cv2
    import numpy as np
    A = cv2.imdecode(np.fromfile(str(png), np.uint8), cv2.IMREAD_COLOR)
    c = A[band[0]:band[1]]
    m = (np.abs(c.astype(int) - cv2.medianBlur(c, 51).astype(int)).sum(2) > 60).astype(np.uint8)
    A[band[0]:band[1]] = cv2.inpaint(c, cv2.dilate(m, np.ones((9, 9), np.uint8)), 7, cv2.INPAINT_TELEA)
    out.write_bytes(cv2.imencode(".png", A)[1].tobytes())
    return out


def line_rows(png: Path, band: tuple, dark: bool) -> list[list[int]]:
    """띠 안 글자 줄 잉크 행 [위, 아래] — 줄 간격(피치) 재기."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert("L")).astype(int)[band[0]:band[1]]
    rows = ((a < 90) if dark else (a > 215)).sum(1) > 4
    out, s = [], None
    for i, v in enumerate(list(rows) + [False]):
        if v and s is None:
            s = i
        if not v and s is not None:
            if i - s > 12:
                out.append([s + band[0], i - 1 + band[0]])
            s = None
    return out


def check_pack(pack: str, work: Path) -> list[dict]:
    from PIL import Image
    from shopping_shorts import scene_style
    from tools.calcopy.engine.kal_analyze import FRAME_PASS, frame_metrics
    from tools.calcopy.hybrid.pack_map import _hex_lab, caption_packs, delta_e
    from tools.caption_pack.check_bench_packs import rows_to_timeline, snapshot
    P = caption_packs()[pack]
    cases = CASES[pack]
    tts = work / "silence.wav"
    if not tts.exists():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1", str(tts)], check=True)
    rows = []
    for i, c in enumerate(cases):
        r = {"line": i, "t0": float(i), "t1": i + 1.0, "text": c[2], "speaker": c[4], "variant": "", "emph": [], "sticker": "", "stickers": [], "enter": "instant"}
        k = c[2].count("\n") + 1
        if k > 1 and pack in STACK_PITCH:      # 쌓기 판: render_bench.stack_rows 와 같은 식 — 첫 줄 제자리, 덩어리 가운데 = y + (k−1)·pitch/2
            r["place"] = {"x": 50, "y": round(P["place"]["y"] + (k - 1) * STACK_PITCH[pack] / 2 / 19.2, 3)}
        rows.append(r)
    lw = work / f"layers_{pack}"
    shutil.rmtree(lw, ignore_errors=True)
    L = scene_style.render_layers(rows_to_timeline(rows, tts, float(len(cases))), snapshot(pack), lw)
    out = []
    for i, (c, lay) in enumerate(zip(cases, L)):
        video, t, text, y, who = c
        band = (max(0, y[0] - 45), min(1919, y[1] + 45))
        bp = _bench_png(video, t, work / f"bench_{Path(video).stem}_{t}.png")
        bg = Image.open(_clean_band(bp, band, work / f"clean_{pack}_{i}.png")).convert("RGBA")
        f = lay.get("file") or sorted(lw.glob(lay["animation"]["pattern"].replace("%04d", "*")))[-1].name
        op = work / f"ours_{pack}_{i}.png"
        Image.alpha_composite(bg, Image.open(lw / f).convert("RGBA")).convert("RGB").save(op)
        B, O = frame_metrics(str(bp), band), frame_metrics(str(op), band)
        sp = ((P.get("speakers") or {}).get(who) or {})
        fill = ((sp.get("text") or {}).get("color")) or P["text"]["color"]
        dark = _hex_lab(fill)[0] < 50
        r = {"pack": pack, "i": i, "video": video, "t": t, "text": text, "who": who, "band": band, "bench_box": B.get("box"), "ours_box": O.get("box"),
             "bench_h": B.get("h"), "ours_h": O.get("h")}
        if B.get("box") and O.get("box"):
            r["d"] = [O["box"][k] - B["box"][k] for k in range(4)]
            r["dh"] = O["h"] - B["h"]
            kb, ko = ("outline_hex", "outline_hex") if dark else ("fill_hex", "fill_hex")
            r["color"] = [B.get(kb), O.get(ko)]
            r["dE"] = delta_e(B[kb], O[ko]) if B.get(kb) and O.get(ko) else None
            r["pass"] = (max(abs(v) for v in r["d"]) <= FRAME_PASS["xy_px"] and abs(r["dh"]) <= FRAME_PASS["h_px"]
                         and r["dE"] is not None and r["dE"] < FRAME_PASS["dE"])
        if "\n" in text:
            lb, lo = line_rows(bp, band, dark), line_rows(op, band, dark)
            r["lines"] = {"bench": lb, "ours": lo}
            if len(lb) >= 2 and len(lo) >= 2:
                r["pitch"] = [lb[-1][0] - lb[-2][0], lo[-1][0] - lo[-2][0]]
        out.append(r)
    return out


# 팩 → 벤치 편 분포를 잴 줄판독 칸: (채널, 화자 앞글자들, 채움색 앞 3자 | None, 줄 고르기)
SPREAD = {"banggu": ("banggu", ("나레",), None, "first"), "yummyknow": ("yummyknow", ("나레",), None, "first"),
          "humorshowshow": ("humorshowshow", ("나레",), None, "first"), "hottemreport": ("hottemreport", ("나레",), "#FF", "one"),
          "sinbak": ("sinbak", ("나레",), "#00", "one"), "uljimatrot": ("uljimatrot", ("나레",), None, "one"),
          "mantem:orig": ("mantem", ("원음",), None, "one"), "mantem:narr": ("mantem", ("나레",), None, "one"),
          "itemhome": ("itemhome", ("나레", "원음"), None, "one"), "annapick": ("annapick", ("나레", "원음"), "#FF", "one"),
          "sseolpulda_a": ("sseolpulda", ("불명",), "#00", "one"), "sseolpulda_b": ("sseolpulda", ("나레",), None, "one"),
          "hotpeople": ("hotpeople", ("나레",), None, "one")}


def episode_spread(frames: list[dict], tol: int = 4) -> list[dict]:
    """(b) 벤치가 편마다 자리를 바꾸는 판 — 우리 한 줄 잉크 가운데(x·y)가 '벤치 편별 중앙값 범위 ±tol' 안에 드나.
    팩 자리는 한 값이라 편마다 다른 자리는 엄격 대조(같은 편 ±4)로 못 맞춘다 — 판 쪽 편별 자리 칸(07)이 없으면 이 표가 기준."""
    import statistics as S
    out = []
    for key, (slug, whos, fill, pick) in SPREAD.items():
        pack, _, who = key.partition(":")
        per = {}
        for f in sorted((ROOT / f"channel/{slug}/줄판독").glob("*.json")):
            L = [x for x in json.loads(f.read_text(encoding="utf-8")).get("lines") or [] if isinstance(x, dict)
                 and str(x.get("speaker", "")).startswith(whos) and isinstance(x.get("y"), list) and len(x["y"]) == 2
                 and all(isinstance(v, (int, float)) for v in x["y"]) and 30 < x["y"][1] - x["y"][0] < 110
                 and (fill is None or str(x.get("fill_hex", "")).upper().startswith(fill))]
            if pick == "first" and L:
                y0 = min(x["y"][0] for x in L)
                L = [x for x in L if x["y"][0] < y0 + 20]
            if len(L) >= 2:
                xs = [(x["ink_x"][0] + x["ink_x"][1]) / 2 if isinstance(x.get("ink_x"), list) and len(x["ink_x"]) == 2 else x.get("x")
                      for x in L]
                xs = [v for v in xs if isinstance(v, (int, float))]
                per[f.stem] = (S.median((x["y"][0] + x["y"][1]) / 2 for x in L), S.median(xs) if xs else None)
        ours = [((r["ours_box"][1] + r["ours_box"][3]) / 2, (r["ours_box"][0] + r["ours_box"][2]) / 2) for r in frames
                if r["pack"] == pack and r.get("ours_box") and "\n" not in r["text"] and (not who or r.get("who") == who)]
        if not per or not ours:
            continue
        ys = [v[0] for v in per.values()]; xs = [v[1] for v in per.values() if v[1] is not None]
        oy, ox = S.median(o[0] for o in ours), S.median(o[1] for o in ours)
        r = {"pack": key, "docs": len(per), "bench_y": [min(ys), max(ys)], "bench_x": [min(xs), max(xs)] if xs else None, "ours_y": oy, "ours_x": ox}
        r["y_in"] = min(ys) - tol <= oy <= max(ys) + tol
        r["x_in"] = (min(xs) - tol <= ox <= max(xs) + tol) if xs else None
        out.append(r)
    return out


def distances() -> dict:
    from tools.calcopy.hybrid import styles
    from tools.calcopy.hybrid.pack_map import bench_caption, cap_distance, slug_of
    out = {}
    for board, pack in BOARD.items():
        st = styles.load(board, _skip_packs=True)
        B = bench_caption(slug_of(st), st)
        out[board] = {"pack": pack, **cap_distance(B, pack), "bench": B.get("basis")}
    return out


def main():
    argv = sys.argv[1:]
    od = ROOT / "out/check_kal_new_packs"
    if "--out" in argv:
        k = argv.index("--out")
        od = Path(argv[k + 1])
        del argv[k:k + 2]
    packs = argv[0].split(",") if argv else list(CASES)
    od.mkdir(parents=True, exist_ok=True)
    rep = {"frames": [], "distance": distances()}
    for p in packs:
        rep["frames"] += check_pack(p, od)
    rep["spread"] = episode_spread(rep["frames"])
    (od / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    for b, d in rep["distance"].items():
        print(f"{b:10s} {d['pack']:14s} 거리 {d['d']:.3f} {d['terms']}")
    for r in rep["frames"]:
        print(f"{r['pack']:14s} {Path(r['video']).stem:12s} {r['t']:7} d{r.get('d')} dh{r.get('dh')} ΔE{r.get('dE')} {'✓' if r.get('pass') else '✗'}"
              + (f" 피치 벤치/우리 {r['pitch']}" if r.get("pitch") else ""))
    for r in rep["spread"]:
        print(f"편 분포 {r['pack']:14s} 편 {r['docs']} 벤치 y {r['bench_y']} 우리 {r['ours_y']:.0f} {'✓' if r['y_in'] else '✗'} · "
              f"x {r['bench_x']} 우리 {r['ours_x']:.0f} {'✓' if r['x_in'] else '✗' if r['x_in'] is False else '-'}")
    n = sum(bool(r.get("pass")) for r in rep["frames"])
    print(f"합격 {n}/{len(rep['frames'])} → {od / 'report.json'}")


if __name__ == "__main__":
    main()
