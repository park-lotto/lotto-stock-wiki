# -*- coding: utf-8 -*-
"""완성본 컷마다 그림 검수 — A3(줄↔장면)·A5(남의 글자/UI/잘린 글자)·B10(주피사체 가운데)·의미 없는 사람 (관제 097, 2026-10-24).

    PYTHONUTF8=1 py tools/calcopy/engine/cut_review.py <final.mp4> <대본/재료 폴더> [--out 폴더] [--timeline timeline.json] [--workers 6]

왜: preset_make 자동 검사는 길이·중복·소리만 잰다. 취객선비잔 1차본에서 잔이 오른쪽 끝에 잘린 컷(0:03)·제품 무관 일러스트+반토막 글자(0:24)·
'일시품절'→'시품절'(0:27)·줄과 무관한 손님 얼굴(0:02)이 전부 '통과'로 나갔다.
컷 시각 = timeline.json groups(t0·dur) — 폴더 안, 폴더/make, 재료.json cand_dir/make 순으로 찾는다.
1) 컷마다 앞·가운데·뒤 프레임(긴 변 768) 2) 숫자 힌트(가장자리 글자 잉크·선명도 무게중심) 3) claude_cli.ask(소넷)로 판정 → 코드가 묶어 ○/× 표.
x 하나라도 있으면 rc 1. 회원 결과물(preset_make)에는 연결하지 않는다 — 칼카피 우리 PC 렌더 뒤 수동으로 돌린다.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KEYS = ("A3", "A5", "B10", "meaningless_person")
LONG = 768

PROMPT = """너는 쇼핑 쇼츠 검수원이다. 그림 1장 = 한 컷에서 뽑은 프레임 3장을 가로로 붙인 것(왼쪽=컷 시작, 가운데=중간, 오른쪽=컷 끝).
이 컷 동안 나오는 자막(대사 조각): «{piece}» (비어 있으면 그림 속 우리 자막 띠의 글자를 직접 읽어 그것을 자막으로 삼는다)
그 줄 전체 문장(또는 대본 전체 — 문맥): {line}
영상 주제(제품): {topic}
재료 고를 때 적어 둔 장면 설명(참고만, 실제 그림이 우선): {seen}
우리가 얹은 틀(남의 글자가 아니다 — 판정에서 완전히 무시): 화면 위쪽의 채널 머리띠(채널명 «{channel}»·메뉴 아이콘·검색 돋보기·'광고' 배지), 제목 띠({titles}), 자막 띠(«{piece}» 같은 우리 자막).
판정 대상은 그 띠들 아래(또는 사이)의 '영상 창' 안 그림뿐이다. 영상 창 안에 원래 박혀 있던 글자만 남의 글자다.
숫자 힌트(코드가 잰 값, 참고만): {hint}

네 항목을 각각 판정한다. 통과 = true, 불량 = false. A5·B10 은 엄격하게(애매하면 불량). A3 는 줄이 말하는 대상(그 그림·인물·제품·동작)이 화면에 보이면 통과 — 멀리서 찍었다는 이유만으로 불량 아님. 우리 틀(머리띠·아이콘)은 어떤 항목의 근거로도 쓰지 않는다.
A3 줄↔장면: 그 자막 조각/문장의 뜻(말하는 대상·동작·상태)이 그림에 보이는가. 제품 주제 영상에서 제품·주제와 무관한 그림(엉뚱한 일러스트·톱니바퀴·직원 그림·다른 상품)이 화면 주인이면 false.
A5 남의 글자/UI: 우리 자막·제목 말고 화면에 남의 글자·로고·워터마크·방송 자막·쇼핑몰/앱 UI·안내문이 보이면 false. 특히 글자가 화면 가장자리에서 잘려 반토막이면(예: '일시품절'이 '시품절') 반드시 false. 화면 절반 이상이 다른 상품이면 A3·A5 둘 다 false.
B10 주피사체 가운데: 주피사체(제품·그림 속 인물 등)가 화면 가운데 근처에 온전히 보이면 true. 주피사체가 좌우 끝에 쏠리거나 잘리고 화면 대부분이 흐린 배경·빈 탁자면 false.
meaningless_person: 줄 뜻과 상관없는 실제 사람(손님·행인·직원 얼굴)이 크게 화면 주인이면 false(=불량). 줄이 그 사람 이야기거나, 제품을 쓰는 손만 보이거나, 그림 속 인물이면 true.

JSON: {{"A3": true/false, "A5": true/false, "B10": true/false, "meaningless_person": true/false, "why": "불량 항목마다 보이는 것 한 줄(한국어)"}}"""


def _find_timeline(folder: Path, given: str | None) -> Path:
    cands = [Path(given)] if given else []
    cands += [folder / "timeline.json", folder / "make" / "timeline.json"]
    mj = folder / "재료.json"
    if mj.exists():
        cd = json.loads(mj.read_text(encoding="utf-8")).get("cand_dir")
        if cd:
            cands.append(Path(cd) / "make" / "timeline.json")
    for c in cands:
        if c.exists():
            return c
    return None      # 없으면 장면 전환 검출 모드(scene_cuts)


def load_cuts(folder: Path, tl_path: Path) -> tuple[list[dict], dict]:
    T = json.loads(tl_path.read_text(encoding="utf-8"))
    D = json.loads((folder / "대본.json").read_text(encoding="utf-8")) if (folder / "대본.json").exists() else {}
    M = json.loads((folder / "재료.json").read_text(encoding="utf-8")) if (folder / "재료.json").exists() else {}
    lines = [l.get("text", "") for l in D.get("lines") or []]
    P = T["pieces"]
    seen_of = {}
    for s in M.get("shots") or []:
        if s.get("src") is not None:
            seen_of[(Path(s["src"]).name, round(float(s.get("ss", -1)), 2))] = s.get("seen") or ""
    cuts = []
    for k, g in enumerate(T["groups"]):
        idx = [i - 1 for i in g.get("pieces") or [] if 0 < i <= len(P)]      # groups.pieces = 1부터(실측: 작품6 첫 컷 [1] = pieces[0])
        ps = [P[i] for i in idx]
        li = ps[0]["line"] if ps else None
        cuts.append({"n": k, "t0": float(g["t0"]), "dur": float(g["dur"]),
                     "piece": " / ".join(p["text"] for p in ps),
                     "line": lines[li] if li is not None and li < len(lines) else "",
                     "seen": seen_of.get((Path(str(g.get("src", ""))).name, round(float(g.get("ss", -1)), 2)), ""),
                     "kind": g.get("kind", "")})
    meta = {"topic": D.get("topic") or D.get("제품명") or "", "titles": list(dict.fromkeys((D.get("title_lines") or []) + [v for v in (D.get("title_slots") or {}).values() if isinstance(v, str)])),
            "channel": D.get("채널") or D.get("channel") or ""}
    return cuts, meta


def _scene_times(video: Path, th: float = 0.3) -> list[float]:
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", f"crop=iw:ih*0.57:0:ih*0.43,select='gt(scene,{th})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def _duration(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def scene_cuts(video: Path, folder: Path) -> tuple[list[dict], dict]:
    """timeline 이 없거나 이 렌더 것이 아닐 때 — 영상 창 장면 전환으로 컷을 나눈다(0.3초 안 연속 감지는 한 경계).
    자막 조각은 Claude 가 화면 자막을 직접 읽는다(piece 비움), 줄 문장은 대본 전체를 문맥으로 준다."""
    D = json.loads((folder / "대본.json").read_text(encoding="utf-8")) if (folder / "대본.json").exists() else {}
    dur = _duration(video)
    b = [0.0]
    for t in _scene_times(video):
        if t - b[-1] >= 0.3 and dur - t >= 0.3:
            b.append(t)
    b.append(dur)
    whole = " / ".join(l.get("text", "") for l in D.get("lines") or [])
    cuts = [{"n": k, "t0": round(b[k], 3), "dur": round(b[k + 1] - b[k], 3), "piece": "", "line": whole, "seen": "", "kind": ""}
            for k in range(len(b) - 1)]
    meta = {"topic": D.get("topic") or "", "channel": D.get("채널") or D.get("channel") or "",
            "titles": list(dict.fromkeys((D.get("title_lines") or []) + [v for v in (D.get("title_slots") or {}).values() if isinstance(v, str)]))}
    return cuts, meta


def timeline_matches(video: Path, cuts: list[dict]) -> float:
    """timeline.json 이 이 영상의 것인가 — 영상 창(위 43% 뺀 아래) 장면 전환과 컷 시작(0초 제외)이 0.1초 안에 맞는 비율.
    취객선비잔: make/ 는 다시 렌더되면 덮인다(10-24 17:22) — 옛 완성본에 새 timeline 을 대면 컷이 어긋난다."""
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "crop=iw:ih*0.57:0:ih*0.43,select='gt(scene,0.3)',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    sc = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    ts = [c["t0"] for c in cuts if c["t0"] > 0.05]
    return round(sum(any(abs(t - x) <= 0.1 for x in sc) for t in ts) / max(len(ts), 1), 2)


def grab(video: Path, t: float, out: Path):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                    "-vf", f"scale=-2:{LONG}", "-q:v", "3", str(out)], check=True)


def hints(imgs: list[Path]) -> dict:
    """숫자 1차 거르기: 가장자리 띠(좌우 4%) 글자 잉크 = 고대비 엣지 밀도 / 선명도(라플라시안) 무게중심 x(0~1)."""
    import cv2
    import numpy as np
    edge_ink, cxs = [], []
    for p in imgs:
        g = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        h, w = g.shape
        e = cv2.Canny(g, 100, 200) > 0
        b = max(4, int(w * 0.04))
        edge_ink.append(round(float(max(e[:, :b].mean(), e[:, -b:].mean())), 3))
        lap = np.abs(cv2.Laplacian(cv2.GaussianBlur(g, (3, 3), 0), cv2.CV_32F))
        lap[int(h * 0.55):int(h * 0.8), :] = 0          # 우리 자막 띠(대략) 빼고
        lap[: int(h * 0.18), :] = 0                      # 위 제목 띠 빼고
        cols = lap.sum(0)
        cxs.append(round(float((cols * np.arange(w)).sum() / max(cols.sum(), 1e-6) / w), 2))
    cx = sorted(cxs)[1] if len(cxs) == 3 else cxs[0]
    return {"edge_ink": max(edge_ink), "sharp_cx": cx,
            "flag_edge_text": max(edge_ink) >= 0.12, "flag_off_center": not (0.35 <= cx <= 0.65)}


def review(video: Path, folder: Path, out: Path, tl: str | None = None, workers: int = 6) -> dict:
    from PIL import Image
    from tools.calcopy.engine import claude_cli
    tp = _find_timeline(folder, tl)
    match, mode = None, "scene"
    if tp:
        cuts, meta = load_cuts(folder, tp)
        match = timeline_matches(video, cuts)
        mode = "timeline"
    if not tp or match < 0.6:        # 없음/다른 렌더 것(make/ 는 재렌더 때 덮인다) → 장면 전환 모드
        print(f"[컷 시각] timeline {'없음' if not tp else f'불일치({match})'} → 장면 전환 검출 모드")
        cuts, meta = scene_cuts(video, folder)
        mode = "scene"
    fdir = out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    calls = [0]

    def one(c):
        a, b = c["t0"], c["t0"] + c["dur"]
        ts = [a + min(0.15, c["dur"] * 0.2), (a + b) / 2, b - min(0.15, c["dur"] * 0.2)]
        fs = []
        for j, t in enumerate(ts):
            f = fdir / f"cut{c['n']:02d}_{j}.jpg"
            grab(video, t, f)
            fs.append(f)
        c["hint"] = hints(fs)
        ims = [Image.open(f).convert("RGB") for f in fs]
        strip = Image.new("RGB", (sum(i.width for i in ims) + 8 * 2, max(i.height for i in ims)), "black")
        x = 0
        for i in ims:
            strip.paste(i, (x, 0))
            x += i.width + 8
        strip.thumbnail((1300, LONG))
        sp = fdir / f"cut{c['n']:02d}_strip.jpg"
        strip.save(sp, quality=85)
        c["strip"] = str(sp)
        pr = PROMPT.format(piece=c["piece"], line=c["line"], topic=meta["topic"], seen=c["seen"] or "없음",
                           titles=" / ".join(meta["titles"]) or "없음", channel=meta["channel"],
                           hint=f"가장자리 글자 잉크 {c['hint']['edge_ink']}(0.12↑ 잘린 글자 의심), 선명한 부분 무게중심 x={c['hint']['sharp_cx']}(0.35~0.65 밖 쏠림 의심)")
        t0 = time.time()
        r, err = None, None
        for _ in range(2):
            calls[0] += 1
            r, err = claude_cli.ask([sp.read_bytes()], pr, tag="ma_fit:cut_review", model="sonnet")
            if r and all(k in r for k in KEYS):
                break
        c["sec"] = round(time.time() - t0, 1)
        if not r or not all(k in r for k in KEYS):
            c["verdict"] = {k: None for k in KEYS}
            c["why"] = f"판정 실패: {err}"
        else:
            c["verdict"] = {k: bool(r[k]) for k in KEYS}
            c["why"] = str(r.get("why") or "")
        c["ok"] = all(v is True for v in c["verdict"].values())      # 판정 실패(None)도 ×
        return c

    t_all = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, cuts))
    rep = {"video": str(video), "timeline_match": match, "cut_mode": mode, "cuts": res, "n_bad": sum(not c["ok"] for c in res), "calls": calls[0],
           "wall_sec": round(time.time() - t_all, 1)}
    (out / "cut_review.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    mk = lambda v: "○" if v is True else ("×" if v is False else "?")
    rows = ["| 컷 | 시각 | 자막 | A3 | A5 | B10 | 사람 | 힌트(잉크/중심) | 이유 |", "|---|---|---|---|---|---|---|---|---|"]
    for c in res:
        v = c["verdict"]
        tm = f"{int(c['t0'] // 60)}:{c['t0'] % 60:05.2f}"
        rows.append(f"| {c['n']} | {tm} | {c['piece']} | {mk(v['A3'])} | {mk(v['A5'])} | {mk(v['B10'])} | {mk(v['meaningless_person'])} | "
                    f"{c['hint']['edge_ink']}/{c['hint']['sharp_cx']} | {'' if c['ok'] else c['why'].replace('|', '/')} |")
    (out / "cut_review.md").write_text(f"# 컷 검수 {video.name}\n\n× {rep['n_bad']}컷 / {len(res)}컷 · 호출 {rep['calls']} · {rep['wall_sec']}초\n\n"
                                        + "\n".join(rows) + "\n", encoding="utf-8")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("folder")
    ap.add_argument("--out")
    ap.add_argument("--timeline")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    v, f = Path(a.video), Path(a.folder)
    out = Path(a.out) if a.out else f / "cut_review"
    rep = review(v, f, out, a.timeline, a.workers)
    for c in rep["cuts"]:
        if not c["ok"]:
            bad = [k for k, x in c["verdict"].items() if x is not True]
            print(f"× 컷{c['n']} {c['t0']:.2f}s «{c['piece']}» {bad} — {c['why']}")
    print(f"× {rep['n_bad']}/{len(rep['cuts'])} · 호출 {rep['calls']} · {rep['wall_sec']}s → {out / 'cut_review.md'}")
    sys.exit(1 if rep["n_bad"] else 0)


if __name__ == "__main__":
    main()
