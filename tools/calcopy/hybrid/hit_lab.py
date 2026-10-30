"""터진 편 vs 안 터진 편 비교 — 우리 채널(잇템로그) 쇼츠에서 조회 상위·하위를 골라 장면·대사를 오푸스가 나란히 보고, 터진 쪽에만 있는 공통점을 뽑는다
(사장님 10-27 '그냥 신기해 보이는 것만 보는 거지?' — 기준을 내가 정하지 않고 우리 데이터에서 뽑는다).

    py tools/calcopy/hybrid/hit_lab.py [--channel UCwHATELzDDqCWrlTleMtyrQ] [--k 10] [--out C:/숏템_칼카피/of_pool/_hitlab]

올린 지 30일 넘은 편만(새 편은 조회가 덜 쌓였다). 편마다 = 장면 12장(4×3 시트) + 자동 자막(ko) 대사. 결과 = <out>/결과.json · 기준.md"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
CLAUDE = shutil.which("claude") or "claude"
ASK = """너는 쇼츠 흥행 분석가다. 아래는 우리 채널(잇템로그: 외국인이 한국 화장품·K제품을 써 보는 해외 영상에 한국어 나레를 얹은 쇼츠)의 실제 영상들이다.
A 묶음 = 조회가 가장 높은 편들, B 묶음 = 조회가 가장 낮은 편들(둘 다 올린 지 30일 넘음). 편마다 장면 시트(12장, 시간 순)와 제목·대사가 있다.
그림 파일을 모두 Read 로 열어 보고, **A 에는 있고 B 에는 없는 것**을 찾아라. 짐작이 아니라 편 번호를 대며 말한다.
볼 것: 첫 1~2초 장면 · 제품이 무엇이고 얼마나 또렷한가 · 반응의 크기와 종류 · 이야기 흐름(기대→반전 등) · 출연자 · 제목 말투 · 나레 첫 문장.
그리고 해외 원본 영상 하나를 보고 '잇템로그로 만들면 터질까'를 판정할 수 있는 기준 5~8개를 만들어라(각 기준마다 A·B 에서 몇 편이 해당하는지 센다).
JSON 하나: {"a_only": ["…(편 번호 근거)"], "b_only": ["…"], "both": ["…"], "rubric": [{"name": "…", "how_to_check": "원본 영상에서 무엇을 보면 되나", "a_count": n, "b_count": n}], "summary": "세 줄"}"""


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="UCwHATELzDDqCWrlTleMtyrQ")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", default="C:/숏템_칼카피/of_pool/_hitlab")
    a = ap.parse_args(argv)
    from tools.calcopy.origin_find import yt_auth
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    allf = out / "all.json"
    if not allf.exists():
        allf.write_text(run(["yt-dlp", "--flat-playlist", "-J", f"https://www.youtube.com/channel/{a.channel}/shorts"], timeout=600).stdout, encoding="utf-8")
    es = [e for e in json.loads(allf.read_text(encoding="utf-8")).get("entries") or [] if e.get("id")]
    es.sort(key=lambda e: -(e.get("view_count") or 0))
    cut = (dt.date.today() - dt.timedelta(days=30)).strftime("%Y%m%d")
    auth = yt_auth("https://www.youtube.com/")

    def meta(e):
        f = out / f"{e['id']}.info.json"
        if not f.exists():
            run(["yt-dlp", *auth, "--skip-download", "--write-info-json", "--write-auto-subs", "--sub-langs", "ko", "--sub-format", "vtt",
                 "-o", str(out / "%(id)s.%(ext)s"), f"https://www.youtube.com/shorts/{e['id']}"], timeout=180)
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def pick(cands):
        got = []
        for e in cands:
            m = meta(e)
            if m.get("upload_date") and m["upload_date"] <= cut:
                got.append({**e, "date": m["upload_date"], "dur": m.get("duration")})
            if len(got) >= a.k:
                break
        return got
    top, low = pick(es[:a.k * 2]), pick(list(reversed(es))[:a.k * 4])
    print(f"[분석] 상위 {len(top)}편({top[-1]['view_count']:,}~{top[0]['view_count']:,}) · 하위 {len(low)}편({low[0]['view_count']:,}~{low[-1]['view_count']:,})", flush=True)
    rows, imgs = [], []
    for grp, items in (("A", top), ("B", low)):
        for n, e in enumerate(items, 1):
            mp4 = out / f"{e['id']}.mp4"
            if not mp4.exists():
                run(["yt-dlp", *auth, "-f", "bv*[height<=480]+ba/b[height<=480]/b", "--merge-output-format", "mp4", "-o", str(mp4), f"https://www.youtube.com/shorts/{e['id']}"], timeout=300)
            sh = out / f"{grp}{n}_{e['id']}.jpg"
            if mp4.exists() and not sh.exists():
                fps = 12 / max(float(e.get("dur") or 20), 1)
                run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", f"fps={fps:.4f},scale=200:-2,tile=4x3", "-frames:v", "1", str(sh)], timeout=120)
            vtt = out / f"{e['id']}.ko.vtt"
            words = []
            if vtt.exists():
                for ln in vtt.read_text(encoding="utf-8", errors="replace").splitlines():
                    if ln and "-->" not in ln and not ln.startswith(("WEBVTT", "Kind", "Language")) and ln not in words:
                        words.append(ln.strip())
            if sh.exists():
                imgs.append(str(sh))
            rows.append(f"{grp}{n}. 조회 {e.get('view_count'):,} · {e.get('date')} · {e.get('title')}\n   대사: {' / '.join(words)[:500] or '(자막 없음)'}\n   시트: {sh.name}")
    (out / "묶음.txt").write_text("\n".join(rows), encoding="utf-8")
    ask = ASK + "\n\n" + "\n".join(rows) + "\n\n그림 파일(Read 로 열어 본다):\n" + "\n".join(imgs) + "\n\n답은 JSON 하나만."
    r = run([CLAUDE, "-p", "--model", "opus", "--output-format", "json", "--settings", '{"disableAllHooks": true}', "--allowedTools", "Read",
             "--add-dir", str(out), "--max-turns", "40"], input=ask, cwd=tempfile.gettempdir(), timeout=1800)
    try:
        txt = json.loads(r.stdout).get("result") or ""
        res = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
    except (ValueError, AttributeError):
        res = {"_raw": (r.stdout or r.stderr)[:3000]}
    (out / "결과.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
