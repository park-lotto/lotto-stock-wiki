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


def main(argv=None):
    ap = argparse.ArgumentParser(description="칼카피 한 편 한 명령")
    ap.add_argument("tteutgi"); ap.add_argument("frame"); ap.add_argument("--out", required=True)
    ap.add_argument("--materials"); ap.add_argument("--script")
    ap.add_argument("--queries", default="", help="재료 후보 검색어 '|' 구분(재료.json 없을 때)")
    ap.add_argument("--topic", default=""); ap.add_argument("--roles", default=""); ap.add_argument("--scenes", default="")
    ap.add_argument("--points", default=""); ap.add_argument("--rules", default=str(ROOT / "channel/sseolpulda/제품_이야기썰형.rules.json"))
    ap.add_argument("--bgm", default="qiuqiu"); ap.add_argument("--bgm-ratio", type=float, default=0.15)
    ap.add_argument("--lufs", type=float, default=None, help="목표 통합 LUFS(기본 = 뜯기 audio.I)")
    a = ap.parse_args(argv)
    from shopping_shorts.calcopy_frame import schema
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    J = json.loads(Path(a.tteutgi).read_text(encoding="utf-8"))
    frame = json.loads(Path(a.frame).read_text(encoding="utf-8"))
    spec = schema.validate(frame)
    log = {"steps": {}}
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
    else:
        from tools.calcopy import style_writer
        res = style_writer.write_captions(a.rules, a.tteutgi, a.topic, a.roles.split(","), a.scenes.split("|") if a.scenes else None,
                                          55.0, a.frame, a.points)
        S_p = out / "대본.json"
        S_p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        log["steps"]["script"] = {"written": str(S_p), "check": res["final"].get("check")}
    # 3) 만들기
    from tools.calcopy import remake_video
    target = a.lufs if a.lufs is not None else float((((J.get("audio") or {}).get("bench") or {}).get("I")) or -14.0)   # 뜯기 audio.bench.I
    final = remake_video.make(a.frame, a.tteutgi, a.materials, str(S_p), out, a.bgm, a.bgm_ratio, target)
    # 4) 대조 + 1초 시트
    from tools.calcopy.engine import compare
    res = compare.compare(J["source"], str(final), str(out / "대조"), "single")
    sheet_1s(final, out / "final_sheet_1s.jpg")
    v = res["verdict"]
    log["steps"]["compare"] = {"verdict": v["verdict"], "n_in": v["n_in"], "n_criteria": v["n_criteria"], "out": v["out"], "failed": v["failed"]}
    (out / "remake_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"판정(① 픽셀): {v['verdict']} (기준 {v['n_criteria']} 중 안 {v['n_in']}) · 밖 {v['out'] or '없음'}")
    print("final:", final)
    return 0 if v["verdict"] == "통과" else 1


if __name__ == "__main__":
    sys.exit(main())
