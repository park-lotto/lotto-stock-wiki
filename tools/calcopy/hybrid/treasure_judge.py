"""보물 판정 — 채널 엔진(채널자산.json)이 고른 상위 채널의 터진 영상마다 '우리 숏템프리셋 판 중 어디에 쓸 수 있나'를 판정한다
(사장님 10-27 "정말 우리 칼카피 채널들에서 쓸 만한 영상들이 있는지 그것까지" / "소넷이 판정을 못 하면 오푸스가 해").

    py tools/calcopy/hybrid/treasure_judge.py [--pool C:/숏템_칼카피/of_pool] [--min-score 8] [--min-views 1000000]

대상 = 점수 --min-score 이상·해외 채널의 영상 중 조회 --min-views 이상. 판정 = 소넷(BATCH 편씩, 글만 — 제목·조회·채널 판정) → 답이 없거나
깨지면 오푸스로 한 번 더. 인스타는 제목이 없어(화면에서 못 읽음) 채널 판정·조회만으로 본다(그렇다고 답에 적게 한다).
한국에 이미 있나 = 원본 찾기 장부(장부.json korean_same·origins)에 그 영상이 있으면 '한국 재편집 있음'. 없으면 '모름'(못 찾은 것 ≠ 없음).
결과 = <pool>/보물후보.json {영상 주소: {...판정, channel, views, korea}} — 판정한 영상은 다시 안 본다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
CLAUDE = shutil.which("claude") or "claude"
BATCH = 25

PRESETS = """우리 숏템프리셋 판(해외 원본으로 한국어 쇼츠를 만드는 채널들):
- ititemlog(잇템로그): 외국인이 **한국 화장품·K제품**을 처음 써 보고 놀라거나 반응하는 영상 → 한국어 나레 + 원음. 제품이 한국 것일수록 좋다
- hottemreport(숏템리폿, 벤치 핫템리포트): 해외에서 터진 **신기한 생활용품·핫템**을 써 보는 영상 → 한국어 나레 + 원음
- sseolpulda(도파민썰템, 벤치 썰풀다): 해외에서 크게 터진 현장 영상 + 그 안에 **팔 수 있는 제품**이 있음 → 썰 나레(현장썰)
- foreignshowshow(샥탬스토리): 발명품·창업 제품을 소개·시연하는 영상(샤크탱크 쇼핑 편 꼴)
- byeolsong(릴리릴리, 벤치 별헤는쏭)·sinbak·shortvitc: 나레 없이 **자막+배경음**만 얹는 판 — 말 없이 화면만으로 이해되는 시연·반응
판정 기준: 제품이 화면에 또렷하고 한국에서 살 수 있을 법한가(쿠팡) · 이야기(놀람·반전·전후 비교)가 있나 · 한국 시청자 정서에 맞나(문화 농담·정치·위험 행동·의약품은 X)."""

ASK = PRESETS + """

아래 영상마다 판정해라(제목·조회수·채널 설명만 보고 — 인스타는 제목이 없으니 채널 설명으로 짐작하고 note 에 '제목 없음'):
- fit: 맞는 판 slug 목록(없으면 [])
- product: 영상 속 제품 한 줄 짐작(모르면 '')
- story: 이야기 있나 "strong"|"some"|"none"
- korea_ok: 한국 정서·판매에 맞나 true/false
- score: 0~10(우리가 바로 만들 가치)
- note: 한 줄
JSON 하나: {"videos": [{"key": "<키 그대로>", "fit": [...], "product": "...", "story": "...", "korea_ok": true, "score": 7, "note": "..."}]}"""


def _ask(prompt: str, model: str) -> dict:
    r = subprocess.run([CLAUDE, "-p", "--model", model, "--output-format", "json", "--settings", '{"disableAllHooks": true}', "--max-turns", "2",
                        "--system-prompt", "너는 JSON 으로만 답하는 판정기다.", "--strict-mcp-config",
                        "--disallowedTools", "Bash,Edit,Write,Read,Glob,Grep,WebSearch,WebFetch,Agent,Skill"],
                       input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tempfile.gettempdir(), timeout=900)
    try:
        txt = json.loads(r.stdout).get("result") or ""
        s, e = txt.find("{"), txt.rfind("}")
        return json.loads(txt[s:e + 1])
    except (ValueError, AttributeError):
        return {}


def judge(batch: list[tuple[str, dict]]) -> dict[str, dict]:
    rows = "\n".join(f"- 키 {k} · {v['platform']} @{v['channel']} · {v['views']:,}회 · 제목: {v.get('title') or '(제목 없음)'} · 채널: {v.get('ch_note')}"
                     for k, v in batch)
    want = {k for k, _ in batch}
    out: dict[str, dict] = {}
    for model in ("sonnet", "opus"):         # 소넷이 못 하면 오푸스(사장님 10-27)
        left = [(k, v) for k, v in batch if k not in out]
        if not left:
            break
        a = _ask(ASK + "\n\n" + "\n".join(r for r in rows.split("\n") if any(f"키 {k} " in r for k, _ in left)) + "\n\n답은 JSON 하나만.", model)
        for x in a.get("videos") or []:
            k = str(x.get("key") or "")
            if k in want and isinstance(x.get("fit"), list):
                out[k] = {**x, "model": model}
    return out


HOOK_ASK = """너는 쇼츠 시선 끌기 판정 담당이다. 그림 = 영상 표지 여러 장(칸마다 파란 번호). 스크롤하던 사람이 **멈춰서 보게 되는가**를 칸마다 0~10으로 매겨라.
높게: 기괴하거나 충격적인 장면(눈·입에 뭔가·얼굴이 확 변함)·웃긴 표정·전후가 확 다른 비교·이상한 제품 모양·과장된 반응. 낮게: 평범한 셀카·제품만 덩그러니·글자뿐.
JSON 하나: {"cells": [{"n": 번호, "hook": 0~10, "why": "한 줄(무엇이 눈을 끄나)"}]}"""
NL2 = chr(10) * 2
HOOK_GRID = (5, 4)          # 한 장에 20칸 — 그림 수를 줄여 토큰을 아낀다


def _cover(v: dict) -> Path | None:
    from tools.calcopy.hybrid import channel_worker as C
    vid = v["url"].rstrip("/").split("/")[-1].split("?")[0]
    f = C.COVERS / f"{vid}.jpg"
    if f.exists():
        return f
    if v.get("platform") == "yt":                 # 유튜브 표지는 주소가 정해져 있다
        import requests
        try:
            r = requests.get(f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", timeout=15)
            if r.ok and len(r.content) > 2000:
                C.COVERS.mkdir(parents=True, exist_ok=True)
                f.write_bytes(r.content)
                return f
        except Exception:  # noqa: BLE001
            return None
    return None


def hook_judge(book: dict, outp: Path) -> int:
    """(판단 = 소넷, 못 하면 오푸스) 표지 그림으로 '시선 끌기' 점수 — 사장님 10-27 '이런 시선 끌 만한 영상들이 조회수 잘 나온다'(눈 닦기 캡처).
    제목만 보던 판정이 화면을 못 봤다. 표지 20장을 번호 붙인 한 장으로 묶어 한 번에 묻는다."""
    import cv2
    import numpy as np
    todo = [(u, v) for u, v in book.items() if v.get("judge") and "hook" not in v["judge"]]
    todo = [(u, v, c) for u, v in todo for c in [_cover(v)] if c]
    print(f"[시선] 표지 있는 영상 {len(todo)}편", flush=True)
    c, r = HOOK_GRID
    sheet_dir = outp.parent / "_hook_sheets"
    sheet_dir.mkdir(exist_ok=True)
    done = 0
    for i in range(0, len(todo), c * r):
        part = todo[i:i + c * r]
        tiles = []
        for k, (u, v, f) in enumerate(part):
            im = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_COLOR)
            im = cv2.resize(im if im is not None else np.zeros((10, 10, 3), np.uint8), (216, 384))
            cv2.rectangle(im, (0, 0), (52, 34), (200, 90, 20), -1)
            cv2.putText(im, str(k + 1), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            tiles.append(im)
        while len(tiles) % c:
            tiles.append(np.zeros((384, 216, 3), np.uint8))
        grid = np.vstack([np.hstack(tiles[j:j + c]) for j in range(0, len(tiles), c)])
        sp = sheet_dir / f"hook_{i // (c * r) + 1}.jpg"
        cv2.imencode(".jpg", grid, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tofile(str(sp))
        got = {}
        for model in ("sonnet", "opus"):
            rr = subprocess.run([CLAUDE, "-p", "--model", model, "--output-format", "json", "--settings", '{"disableAllHooks": true}', "--max-turns", "4",
                                 "--allowedTools", "Read", "--add-dir", str(sheet_dir), "--strict-mcp-config"],
                                input=HOOK_ASK + NL2 + f"그림 파일(Read 로 열어 본다): {sp}" + chr(10) + f"칸 수 {len(part)}" + NL2 + "답은 JSON 하나만.",
                                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tempfile.gettempdir(), timeout=900)
            try:
                txt = json.loads(rr.stdout).get("result") or ""
                a = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
                got = {int(x["n"]): x for x in a.get("cells") or [] if isinstance(x, dict) and str(x.get("n", "")).isdigit()}
            except (ValueError, AttributeError, KeyError):
                got = {}
            if len(got) >= len(part) // 2:
                break
        for k, (u, v, f) in enumerate(part):
            x = got.get(k + 1)
            if x:
                book[u]["judge"]["hook"] = x.get("hook")
                book[u]["judge"]["hook_why"] = str(x.get("why") or "")[:120]
                done += 1
        outp.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[시선] {min(i + c * r, len(todo))}/{len(todo)} · 판정 {len(got)}", flush=True)
    return done


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="C:/숏템_칼카피/of_pool")
    ap.add_argument("--min-score", type=float, default=8)
    ap.add_argument("--min-views", type=int, default=1_000_000)
    ap.add_argument("--hook", action="store_true", help="표지 그림으로 시선 끌기 점수만(판정 끝난 영상)")
    a = ap.parse_args(argv)
    pool = Path(a.pool)
    chans = json.loads((pool / "채널자산.json").read_text(encoding="utf-8"))
    led = json.loads((pool / "장부.json").read_text(encoding="utf-8")) if (pool / "장부.json").exists() else {}
    kr_urls = {x.get("url") for v in led.values() for x in v.get("korean_same") or []}
    have_orig = {o for v in led.values() if v.get("status") == "found" for o in v.get("origins") or []}
    outp = pool / "보물후보.json"
    book = json.loads(outp.read_text(encoding="utf-8")) if outp.exists() else {}
    if a.hook:
        n = hook_judge(book, outp)
        print(f"[시선] 점수 매긴 영상 {n}편")
        return 0
    todo = []
    for ck, c in chans.items():
        j = c.get("judge") or {}
        if c.get("korean") or float(j.get("score") or 0) < a.min_score:
            continue
        for v in c.get("top") or []:
            if int(v.get("views") or 0) < a.min_views or not v.get("url") or v["url"] in book:
                continue
            vid = v["url"].rstrip("/").split("/")[-1]
            todo.append((str(len(todo) + 1), {"url": v["url"], "platform": c["platform"], "channel": c.get("handle"), "ch_key": ck, "views": int(v["views"]),
                                              "title": v.get("title") or "", "ch_note": f"{j.get('kind')}·{j.get('product')}·{j.get('why')}"[:160],
                                              "korea": "우리 원본" if vid in have_orig else ("한국 재편집 있음" if v["url"] in kr_urls else "모름")}))
    print(f"[보물] 판정할 영상 {len(todo)}편(채널 점수 {a.min_score}+ · 조회 {a.min_views:,}+)", flush=True)
    t0 = time.time()
    for i in range(0, len(todo), BATCH):
        bt = todo[i:i + BATCH]
        js = judge(bt)
        for k, v in bt:
            book[v["url"]] = {**v, "judge": js.get(k), "t": time.strftime("%Y-%m-%d %H:%M")}
        outp.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[보물] {min(i + BATCH, len(todo))}/{len(todo)} · 판정 {len(js)}/{len(bt)}(오푸스 {sum(1 for x in js.values() if x.get('model') == 'opus')}) · {time.time() - t0:.0f}초", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
