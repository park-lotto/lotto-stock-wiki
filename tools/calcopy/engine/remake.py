# -*- coding: utf-8 -*-
"""칼카피 한 편 한 명령 — 뜯기 + 틀 → (재료 후보 시트) → 대본 → 우리 영상 → 대조 (관제 097, 2026-10-16).

    PYTHONUTF8=1 py tools/calcopy/engine/remake.py <뜯기.json> <frame.json> --out <폴더> [--materials 재료.json] [--script 대본.json]
          [--queries "검색어1|검색어2"] [--topic 주제 --roles "역할1,역할2,…" --scenes "화면1|…" --points "포인트"] [--bgm qiuqiu]

흐름(손으로 이었던 ZdeZ 1편을 그대로 한 줄로):
  1) 재료  : --materials 가 없으면 **후보까지만 자동** — 검색어로 유튜브 쇼츠(4분 미만) 받기 → 원본 컷 그리드 + 후보 접촉 시트
             (out/재료후보/) + 재료.json 뼈대(out/재료_뼈대.json)를 쓰고 멈춘다. 어느 후보 몇 초를 어느 컷에 쓸지는
             사람(또는 오푸스)의 판단 자리 — 뼈대를 채워 --materials 로 다시 부른다.
  2) 대본  : --script 가 있으면 그대로(같은 결과 재현), 없으면 style_writer.write_captions(역할·말끝·폭·겹침 검사, 무료 제미나이).
  3) 만들기: remake_video.make(재료 창·꼬리·원음+BGM·효과음, 라이브 렌더 경로 scene_style.compose) → out/final.mp4
  4) 대조  : compare.compare(원본, final, --layout single) → out/대조/차이표.md · side_by_side.jpg, 1초 시트 out/final_sheet_1s.jpg
판단 주인은 각 단계 도구(재료=사람, 대본=style_writer, 조립=remake_video, 대조=compare) — 이 파일은 잇기만 한다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse as up
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


# ── 1) 재료 후보 ──────────────────────────────────────────────────────────
def _probe(p) -> tuple[int, int, float]:
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.split()
    try:
        w, h = map(int, o[0].split(",")[:2]); return w, h, float(o[1])
    except (ValueError, IndexError):
        return 0, 0, 0.0


def search_shorts(q: str, n: int = 12) -> list[str]:
    """유튜브 '4분 미만' 검색(sp=EgIYAQ) 목록에서 60초 이하 id — scene_pack.videos 와 같은 검색 문(10-15 실측: ytsearch 는 긴 영상만)."""
    url = "https://www.youtube.com/results?search_query=" + up.quote(q) + "&sp=EgIYAQ%253D%253D"
    lst = subprocess.run(["yt-dlp", "--encoding", "utf-8", "--flat-playlist", "-I", f"1:{n}", "--print", "%(id)s %(duration)s", url],
                         capture_output=True, encoding="utf-8", stdin=subprocess.DEVNULL).stdout.splitlines()
    return [l.split()[0] for l in lst if l.strip() and l.split()[-1] not in ("NA", "None") and float(l.split()[-1]) <= 60]


def download(vid: str, out: Path) -> Path | None:
    f = out / f"v_{vid}.mp4"
    if not f.exists():
        try:   # ★윈도우에서 "timeout" 명령은 GNU 가 아니라 System32	imeout.exe(대기)라 받기가 통째로 0개였다(10-16) → subprocess timeout
            subprocess.run(["yt-dlp", "--encoding", "utf-8", "-q", "--no-warnings", "-f",
                            "bv*[height<=1920][ext=mp4]+ba/b[ext=mp4]/b", "--merge-output-format", "mp4", "-o", str(f),
                            f"https://www.youtube.com/shorts/{vid}"], capture_output=True, stdin=subprocess.DEVNULL, timeout=150)
        except subprocess.TimeoutExpired:
            print(f"[재료] 받기 시간 초과 {vid}", file=sys.stderr)
    return f if f.exists() else None


def contact_sheet(videos: list[Path], dst: Path, per: int = 6, rows: int = 9):
    """후보마다 한 줄(고르게 per 장 + 시각) — 원본 컷과 눈으로 대조할 시트."""
    from PIL import Image, ImageDraw
    lines = []
    for v in videos:
        w, h, dur = _probe(v)
        if not dur:
            continue
        row = Image.new("RGB", (per * 120 + 150, 213), "white"); dr = ImageDraw.Draw(row)
        dr.text((2, 100), v.stem[2:], fill=(200, 0, 0)); dr.text((2, 115), f"{w}x{h} {dur:.0f}s", fill=(90, 90, 90))
        for k in range(per):
            t = dur * (k + 0.5) / per
            b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(v), "-frames:v", "1", "-vf",
                                "scale=120:213:force_original_aspect_ratio=decrease", "-f", "image2pipe", "-vcodec", "png", "-"],
                               capture_output=True, stdin=subprocess.DEVNULL).stdout
            if b:
                import io
                row.paste(Image.open(io.BytesIO(b)), (150 + k * 120, 0))
            dr.text((152 + k * 120, 2), f"{t:.1f}", fill=(255, 255, 0))
        lines.append(row)
    for p in range(0, len(lines), rows):
        S = Image.new("RGB", (per * 120 + 150, 213 * len(lines[p:p + rows])), "white")
        for i, r in enumerate(lines[p:p + rows]):
            S.paste(r, (0, i * 213))
        S.save(dst / f"후보시트_{p // rows + 1}.jpg", quality=85)


def orig_grid(J: dict, spec: dict, dst: Path):
    """원본 컷마다 가운데 프레임의 영상 창(설명서 video 층) — 후보와 나란히 볼 기준."""
    from PIL import Image, ImageDraw
    import io
    v = next(l for l in spec["layers"] if l["kind"] == "video")
    cuts = [0.0] + list((J.get("cuts") or {}).get("times") or []) + [float(J["probe"]["duration"])]
    tiles = []
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        t = (a + b) / 2
        png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", J["source"], "-frames:v", "1", "-vf",
                              f"crop={v['w']}:{v['h']}:{v['x']}:{v['y']},scale=270:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL).stdout
        im = Image.open(io.BytesIO(png)).convert("RGB"); ImageDraw.Draw(im).text((4, 4), f"#{i} {a:.2f}-{b:.2f}", fill=(255, 0, 0))
        tiles.append(im)
    S = Image.new("RGB", (sum(t.width for t in tiles), max(t.height for t in tiles)), "white")
    x = 0
    for t in tiles:
        S.paste(t, (x, 0)); x += t.width
    S.save(dst / "원본컷.jpg", quality=88)
    return [(round(a, 3), round(b, 3)) for a, b in zip(cuts, cuts[1:])]


def gather_candidates(J: dict, spec: dict, queries: list[str], out: Path) -> Path:
    cand = out / "재료후보"; cand.mkdir(parents=True, exist_ok=True)
    shots = orig_grid(J, spec, cand)
    ids, seen = [], set()
    for q in queries:
        for vid in search_shorts(q):
            if vid not in seen:
                seen.add(vid); ids.append(vid)
    got = [f for f in (download(v, cand) for v in ids) if f]
    contact_sheet(sorted(got), cand)
    skel = {"_note": "remake.py 가 만든 뼈대 — 후보시트_*.jpg 를 원본컷.jpg 와 대조해 shots[*].src/ss/crop_y/status 를 채운다(판단 자리)",
            "cand_dir": str(cand), "queries": queries, "downloaded": len(got),
            "shots": [{"i": i, "t0": a, "t1": b, "src": None, "url": None, "ss": None, "crop_y": 0.5, "status": None} for i, (a, b) in enumerate(shots)],
            "sfx": []}
    p = out / "재료_뼈대.json"
    p.write_text(json.dumps(skel, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def draft_materials(skel: dict, defaults: dict, assets: dict, asset_file) -> dict:
    """(판단 주인, 10-16 calcopy_make 에서 이관) 뼈대 → 재료 자동 초안(선검수용): 컷마다 후보 영상 순서대로 + 팩 기본값
    (효과음 시작·끝, 짤 후보, BGM·목소리·자막 꼴). 사람이 계획을 보고 고친다. asset_file(자산, 폴더, 갈래) → 파일 경로는 팩 창구(calcopy_make)가 준다."""
    import copy
    M = copy.deepcopy(skel)
    cand = sorted(Path(M.get("cand_dir") or ".").glob("v_*.mp4")) if M.get("cand_dir") else []
    for k, s in enumerate(M.get("shots") or []):
        if not s.get("src") and cand:
            s.update(src=cand[k % len(cand)].name, ss=round(float(s.get("t0") or 0) % 20, 2), status="draft",
                     why="자동 초안(만들기 입구) — 후보 순서대로, 선검수에서 사람이 고침")
    pools = defaults.get("sfx_pool") or {}

    def sfx(aid, t, why):
        a = assets.get(aid) or {}
        f = asset_file(a, pools.get("dir"), "sfx")
        return {"file": f.as_posix() if f else None, "asset_id": aid, "title": a.get("title"), "t": t, "db": 0, "why": why}
    M["sfx"] = ([sfx(pools["start"][0], 0.0, "팩 효과음(시작)")] if pools.get("start") else []) + \
               ([sfx(pools["end"][0], "end-0.2", "팩 효과음(끝)")] if pools.get("end") else [])
    M["sfx_pool"], M["meme_pool"] = pools, defaults.get("meme_pool") or {}
    M["bgm"], M["tts"], M["caption_style"] = defaults.get("bgm") or {}, defaults.get("tts") or {}, defaults.get("caption") or {}
    M["_note"] = "만들기 입구 자동 초안 — 팩 기본값(효과음·짤 후보·BGM·목소리) 주입, 컷 선택은 선검수에서 확정"
    return M


# ── 4) 1초 시트 ────────────────────────────────────────────────────────────
def sheet_1s(video: Path, dst: Path, cols: int = 8):
    from PIL import Image, ImageDraw
    import io
    _, _, dur = _probe(video)
    tiles = []
    for k in range(int(dur)):
        b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{k + 0.5:.1f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=180:-2",
                            "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
        if b:
            im = Image.open(io.BytesIO(b)).convert("RGB"); ImageDraw.Draw(im).text((3, 3), f"{k + 0.5:.1f}s", fill=(255, 0, 0)); tiles.append(im)
    w, h = tiles[0].size
    S = Image.new("RGB", (w * cols, h * ((len(tiles) + cols - 1) // cols)), "white")
    for i, im in enumerate(tiles):
        S.paste(im, ((i % cols) * w, (i // cols) * h))
    S.save(dst, quality=88)


def narration_kind(J: dict) -> str:
    """뜯기 audio.composition.narration — 'none'(원음만+자막 → remake_video) / 'tts'·'human'(나레 → narr_video). 판단은 뜯기 값 하나."""
    n = ((J.get("audio") or {}).get("composition") or {}).get("narration")
    return (n.get("kind") if isinstance(n, dict) else n) or "none"


SHEET_EVERY = 2.0   # 계획 시트: 컷 길이 이 초마다 1장(10-16 썰풀다 담당: 0.2·1.0·1.8 세 장 고정이라 6초 넘는 컷 뒷부분이 안 보였다)
SHEET_MIN, SHEET_MAX = 3, 6


def shot_len(s: dict) -> float | None:
    """재료 컷 길이(초) — dur · est_dur · t1−t0 · cuts 합 순. 모르면 None."""
    for k in ("dur", "est_dur"):
        if s.get(k):
            return float(s[k])
    if s.get("t0") is not None and s.get("t1") is not None:
        return float(s["t1"]) - float(s["t0"])
    if s.get("cuts"):
        return sum(float(c["dur"]) for c in s["cuts"])
    return None


def sheet_samples(s: dict) -> list[tuple[str, float, list | None]]:
    """(판단 주인) 계획 시트에 찍을 프레임 [(소스, 소스 초, src_crop)]. 길이 모르면 0.2·1.0·1.8(종전), 알면 0.2~끝−0.2 를
    고르게 clamp(ceil(길이/SHEET_EVERY), 3, 6) 장. 페이지 안 다중 컷(cuts)은 narr_video.shot_pieces 로 그 시각의 토막 소스를."""
    import math
    L = shot_len(s)
    if not L:
        ts = [0.2, 1.0, 1.8]
    else:
        n = min(SHEET_MAX, max(SHEET_MIN, math.ceil(L / SHEET_EVERY)))
        a, b = min(0.2, L / 4), max(L - 0.2, L * 3 / 4)
        ts = [round(a + (b - a) * j / (n - 1), 3) for j in range(n)]
    if not s.get("cuts"):
        return [(s["src"], float(s.get("ss", 0)) + t, s.get("src_crop")) for t in ts]
    from tools.calcopy.narr_video import shot_pieces
    pcs = shot_pieces(s, 0.0, L or 2.0)
    out = []
    for t in ts:
        pc = next((x for x in reversed(pcs) if x["t"] <= t), pcs[0])
        out.append((pc["sh"]["src"], pc["ss"] + (t - pc["t"]), pc["sh"].get("src_crop")))
    return out


def plan_sheet(M: dict, J: dict, dst: Path):
    """컷마다 소스 프레임(sheet_samples — 길이 비례 3~6장, 칸 비율로 자름, src_crop 반영) + 대사 why — 렌더 전 선검수용 접촉 시트."""
    import io
    from PIL import Image, ImageDraw, ImageFont
    base = Path(M["cand_dir"])
    pb = [x["box"] for x in (((J.get("cuts") or {}).get("picture_boxes") or {}).get("per_shot") or []) if x.get("box")]
    f = ImageFont.truetype(str(ROOT / "shopping_shorts/static/fonts/SpoqaHanSansNeo-Bold.otf"), 18)
    rows = []
    for k, s in enumerate(M["shots"]):
        box = s.get("box") or (pb[k % len(pb)] if pb else None)
        bw, bh = (box[2], box[3]) if (box and not s.get("full")) else (1080, 1008)
        th = 200
        tw = int(th * bw / bh)
        samples = sheet_samples(s)
        row = Image.new("RGB", (560 + len(samples) * (tw + 6), th + 10), "white")
        d = ImageDraw.Draw(row)
        d.text((6, 6), f"#{s['i']} {s.get('kind', '')} · {Path(s['src']).name[:30]} @{s.get('ss', 0)}", font=f, fill=(200, 0, 0))
        texts = [s.get("ours", "")[:30], s.get("ours", "")[30:60], "왜: " + s.get("why", "")[:28], s.get("why", "")[28:58]]
        for n, txt in enumerate(texts):
            d.text((6, 34 + n * 26), txt, font=f, fill=(0, 0, 0) if n < 2 else (0, 90, 0))
        for j, (sname, at, scrop) in enumerate(samples):
            crop = "crop={2}:{3}:{0}:{1},".format(*scrop) if scrop else ""
            src = base / sname
            still = src.suffix.lower() in (".png", ".jpg", ".jpeg")
            seek = [] if still else ["-ss", f"{at:.2f}"]
            b = subprocess.run(["ffmpeg", "-v", "error", *seek, "-i", str(src), "-frames:v", "1",
                                "-vf", f"{crop}scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}",
                                "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
            if b:
                row.paste(Image.open(io.BytesIO(b)).convert("RGB"), (560 + j * (tw + 6), 5))
        rows.append(row)
    W = max(r.width for r in rows)
    S = Image.new("RGB", (W, sum(r.height for r in rows)), "white")
    y = 0
    for r in rows:
        S.paste(r, (0, y))
        y += r.height
    S.save(dst, quality=82)


def plan_extra(J: dict, S: dict, M: dict, voice: dict | None = None) -> list[str]:
    """완성작 기준(사장님 10-16: "소재와 대본이 좋고 나레이션과 자막 효과도") 세 절 — 소재 5기준·썰 각도 / 나레 설계 / 자막 효과.
    점수·각도는 대본.json gate(사람·오푸스 판정), 나레·자막 효과 규칙은 뜯기 실측에서 읽는다."""
    from collections import Counter
    md, g = [], S.get("gate") or {}
    md += ["", "## 소재 5기준 + 썰 각도", ""]
    sc = g.get("scores") or {}
    if sc:
        keys = ["아는 대상", "몰랐던", "재미", "이야기", "얻는 것", "보여줄 수 있나"]
        md += ["| | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
        for who, row in sc.items():
            md.append(f"| {who} | " + " | ".join(str(row.get(k, "-")) for k in keys) + " |")
        if g.get("score_note"):
            md += ["", g["score_note"]]
    else:
        md.append("- (대본.json gate.scores 없음 — 5기준 판정 전)")
    for k, lab in (("angle", "썰 각도"), ("twist", "반전 자리"), ("twist_orig", "원본 반전 자리")):
        if g.get(k):
            md.append(f"- {lab}: {g[k]}")
    vr = J.get("voice_rules") or {}
    md += ["", "## 나레 설계(뜯기 voice_rules → 우리)", "",
           f"- 원본: 성별 {vr.get('genders')} · 말속도 {vr.get('cps')}자/초 · 어조 {vr.get('tone')} · 존댓말 비율 {(J.get('script_tone') or {}).get('polite_ratio')}"]
    voice = voice or M.get("narration")
    if voice:
        md.append(f"- 우리: {voice}")
    cm = J.get("caption_motion") or {}
    anims = Counter(x.get("anim") for x in cm.get("starts") or [])
    fx = J.get("text_fx") or {}
    glyph = fx.get("glyph") or []
    md += ["", "## 자막 효과(뜯기 caption_motion·text_fx → 우리)", "",
           f"- 등장(원본 실측 {sum(anims.values())}개): {dict(anims)}",
           f"- 글자: 채움 {[x.get('fill_rgb') for x in (fx.get('per_crop') or [])[:1]]} · 외곽선 {[g_.get('outline_px') for g_ in glyph]}px · 강조 상자 {[x.get('box') for x in fx.get('per_crop') or []][:1]}"]
    eff = M.get("caption_effects") or {}
    for k in ("now", "planned"):
        if eff.get(k):
            md.append(f"- {'지금 렌더' if k == 'now' else '적용 예정'}: {eff[k]}")
    return md


def write_plan(out: Path, J: dict, frames: list, S: dict, M: dict, kind: str) -> Path:
    """선검수 계획.md — 대본(+근거)·컷별 소스·why·접촉 시트·규칙 예상. 렌더·TTS 전에 사람(조율자)이 본다(10-16 rGFX 3차 반려 교훈)."""
    from collections import Counter
    sheet = out / "계획_시트.jpg"
    plan_sheet(M, J, sheet)
    lines = (S.get("final") or {}).get("lines") or []
    facts = S.get("facts") or {}
    form = "원음만+자막(remake_video)" if kind == "none" else f"나레 {kind}(narr_video)"
    md = [f"# 계획 — {Path(str(J.get('source', ''))).stem}", "",
          f"- 꼴: {form} · 틀 {', '.join(Path(x).name for x in frames)}",
          f"- 접촉 시트: `{sheet}`", "", "## 대본", ""]
    for n, l in enumerate(lines, 1):
        fx = l.get("facts") or []
        md.append(f"{n}. ({l.get('fn', '')}) {l.get('text', '')}" + (f" — 근거 {', '.join(fx)}" if fx else ""))
    if facts:
        md += ["", "| 근거 | 내용 | 출처 |", "|---|---|---|"]
        md += [f"| {k} | {v.get('text', '')} | {v.get('url', '')} |" for k, v in facts.items()]
    md += ["", "## 재료(컷별)", "", "| # | 종류 | 소스 | 시작 | 칸 | src_crop | 왜 |", "|---|---|---|---|---|---|---|"]
    for s in M["shots"]:
        box = s.get("box") or ("전폭" if s.get("full") else "원본 순번")
        md.append(f"| {s['i']} | {s.get('kind', '')} | [{Path(s['src']).name}]({s.get('url', '')}) | {s.get('ss', 0)} | {box} | {s.get('src_crop') or '-'} | {s.get('why', '')} |")
    cnt = Counter(s.get("kind", "?") for s in M["shots"])
    tot = sum(cnt.values()) or 1
    mats = J.get("materials") or {}
    sfx0 = (((J.get("audio") or {}).get("composition") or {}).get("sfx") or {}).get("times")
    md += ["", "## 규칙 예상(렌더 전 — 컷 수 기준, 실제 시간 비율은 렌더 뒤 규칙표)", "",
           f"- 컷 {tot}개 · 종류 비율(컷 수) {dict((k, round(v / tot, 2)) for k, v in cnt.items())}",
           f"- 원본 제작법 비율: {mats.get('time_ratio') or mats.get('ratio') or '뜯기 materials 참고'}",
           f"- 효과음: {[x.get('t') for x in M.get('sfx') or []]} · 원본 {sfx0}"]
    md += plan_extra(J, S, M)
    p = out / "계획.md"
    p.write_text("\n".join(md) + "\n", encoding="utf-8")
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description="칼카피 한 편 한 명령")
    ap.add_argument("tteutgi")
    ap.add_argument("frame", help="본문 틀(frame.json)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hook-frame", help="훅 카드 틀(있으면 첫 문장 동안 이 틀) — 나레 꼴")
    ap.add_argument("--materials")
    ap.add_argument("--script")
    ap.add_argument("--plan-only", action="store_true", help="계획.md·접촉 시트만 쓰고 멈춤(렌더·TTS 전 선검수)")
    ap.add_argument("--tts", help="나레 소리 파일(나레 꼴). 없으면 --make-tts 로 타입캐스트 1회")
    ap.add_argument("--make-tts", action="store_true")
    ap.add_argument("--voice", default=None, help="타입캐스트 목소리 tc_…(기본 필재 copy_render.NARR). 원본이 여성 나레면 문정 tc_68f9c6a72f0f04a417bb136f(10-16 3호)")
    ap.add_argument("--tempo", type=float, default=1.36)
    ap.add_argument("--chunk", type=int, default=10, help="나레 꼴 자막 한 줄 글자 수")
    ap.add_argument("--caption-mode", default="accumulate", choices=["accumulate", "replace"], help="누적형(1줄→2줄) / 교체형(1줄씩)")
    ap.add_argument("--queries", default="", help="재료 후보 검색어 '|' 구분(재료.json 없을 때)")
    ap.add_argument("--topic", default="")
    ap.add_argument("--roles", default="")
    ap.add_argument("--scenes", default="")
    ap.add_argument("--points", default="")
    ap.add_argument("--rules", default=str(ROOT / "channel/sseolpulda/제품_이야기썰형.rules.json"))
    ap.add_argument("--bgm", default="qiuqiu")
    ap.add_argument("--bgm-ratio", type=float, default=0.15)
    ap.add_argument("--lufs", type=float, default=None, help="목표 통합 LUFS(기본 = 뜯기 audio.bench.I)")
    a = ap.parse_args(argv)
    from shopping_shorts.calcopy_frame import schema
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    J = json.loads(Path(a.tteutgi).read_text(encoding="utf-8"))
    frame = json.loads(Path(a.frame).read_text(encoding="utf-8"))
    spec = schema.validate(frame)
    kind = narration_kind(J)
    log = {"steps": {}, "kind": kind}
    # 1) 재료
    if not a.materials:
        qs = [q.strip() for q in a.queries.split("|") if q.strip()]
        if not qs:
            ap.error("--materials 가 없으면 --queries 로 재료 후보를 모아야 한다")
        skel = gather_candidates(J, spec, qs, out)
        print(f"[재료] 후보 시트 → {out / '재료후보'} · 뼈대 → {skel}\n  채운 뒤 --materials {skel} 로 다시 부르세요(판단 자리).")
        return 2
    # 2) 대본
    if a.script:
        S_p = Path(a.script)
        log["steps"]["script"] = {"from": str(S_p)}
    elif kind == "none":
        from tools.calcopy import style_writer
        res = style_writer.write_captions(a.rules, a.tteutgi, a.topic, a.roles.split(","), a.scenes.split("|") if a.scenes else None,
                                          55.0, a.frame, a.points)
        S_p = out / "대본.json"
        S_p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        log["steps"]["script"] = {"written": str(S_p), "check": res["final"].get("check")}
    else:
        ap.error("나레 꼴은 --script(style_writer narration 결과 + 근거) 가 필요하다")
    S = json.loads(S_p.read_text(encoding="utf-8"))
    M = json.loads(Path(a.materials).read_text(encoding="utf-8"))
    frames = ([a.hook_frame] if a.hook_frame else []) + [a.frame]
    # 3) 선검수 계획
    plan_md = write_plan(out, J, frames, S, M, kind)
    print("계획:", plan_md)
    if a.plan_only:
        return 3
    # 4) 만들기 — 뜯기 audio.composition 으로 꼴 분기
    target = a.lufs if a.lufs is not None else float((((J.get("audio") or {}).get("bench") or {}).get("I")) or -14.0)
    if kind == "none":
        from tools.calcopy import remake_video
        final = remake_video.make(a.frame, a.tteutgi, a.materials, str(S_p), out, a.bgm, a.bgm_ratio, target)
    else:
        from tools.calcopy import narr_video
        tts = a.tts
        if not tts:
            if not a.make_tts:
                ap.error("나레 꼴: --tts 파일이 없으면 --make-tts(타입캐스트 1회 — 비용)")
            from shopping_shorts.channelkit import providers
            from tools.calcopy.copy_render import NARR
            tts = str(out / "narr_full.mp3")
            providers.typecast_synth(a.voice or NARR, tempo=a.tempo)(" ".join(l["text"] for l in S["final"]["lines"]), tts)
            log["steps"]["tts"] = {"made": tts, "voice": a.voice or NARR, "tempo": a.tempo, "chars": sum(len(l["text"].replace(" ", "")) for l in S["final"]["lines"])}
        plan = {"tteutgi": a.tteutgi, "frames": [{"frame": f, "t_end": None} for f in frames], "script": str(S_p), "tts": tts,
                "materials": a.materials, "out": str(out), "bgm": a.bgm, "bgm_ratio": a.bgm_ratio, "lufs": target, "chunk": a.chunk, "caption_mode": a.caption_mode}
        final = narr_video.build(plan)
    # 5) 대조 + 1초 시트
    from tools.calcopy.engine import compare
    res = compare.compare(J["source"], str(final), str(out / "대조"), "single")
    sheet_1s(final, out / "final_sheet_1s.jpg")
    v = res["verdict"]
    log["steps"]["compare"] = {"verdict": v["verdict"], "n_in": v["n_in"], "n_criteria": v["n_criteria"], "out": v["out"], "failed": v["failed"]}
    # 6) 이음매(되감김·점프 줌) — 검수 B16. 10-17 아이템홈 1판 17.77초 0.37초 되감김을 B표·compare 가 못 잡았다
    from tools.calcopy.engine import check_seams
    sw, sm = check_seams.from_frame(a.frame)   # 훅 카드 틀 말고 본편 틀
    seam = check_seams.check(str(final), sw, sm)
    log["steps"]["seams"] = {"ok": seam["ok"], "rewinds": seam["되감김"]}
    (out / "remake_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"판정(① 픽셀): {v['verdict']} (기준 {v['n_criteria']} 중 안 {v['n_in']}) · 밖 {v['out'] or '없음'}")
    print(f"이음매(B16 되감김·점프줌): {'통과' if seam['ok'] else '걸림 ' + str(seam['되감김'])}")
    print("final:", final)
    return 0 if v["verdict"] == "통과" and seam["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
