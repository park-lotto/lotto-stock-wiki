# -*- coding: utf-8 -*-
"""상위 10편 대조 — 대본 점수·장면 매칭을 벤치 조회 상위 편과 **같은 자**로 잰다 (관제 097, 2026-10-26 사장님
"두유노홈디노의 가장 잘된 편들과 대본 점수·장면 매칭 등 만들어진 퀄리티를 꼭 비교해야 한다. 대본과 장면 매칭이 핵심이다").

    PYTHONUTF8=1 py tools/calcopy/bench_compare_script_scene.py prep  <slug> <작품 판 폴더(doc)> <work> [--top 10]
    (Claude 가 <doc>/대조/judge.json 을 눈으로 채운다 — 시트 = <doc>/대조/sheets/Vxx.jpg, 누가 우리 편인지 모르게 V 번호를 섞었다)
    PYTHONUTF8=1 py tools/calcopy/bench_compare_script_scene.py table <slug> <doc>       → <doc>/대조표.md

판단 주인(이 파일 한 곳 — 두 채널(잇썸홈·재미썸홈) 같은 도구):
  bench_ids   벤치 상위 편 = C:/숏템_칼카피/<slug>/top.json 조회순 중 mp4·asr 가 있는 앞 N편
  sentences   받아쓰기 → 줄(문장): 스피치매틱스 낱말+문장부호 / 제미나이 구절(evenshopping) — 문장부호 또는 0.6초 넘는 쉼에서 끊는다
  machine     기계 칸: 줄 수·글자 수·줄당 글자·연결어 줄 비율·끝맺음 종류·지어냄 후보 수 / 길이·컷 중앙(kal_analyze.media_of — 관문과 같은 자)·
              줄 시작↔컷 시작 어긋남(초, 중앙)·정지 비율(0.1초 간격 창 회색 차 < STILL_DIFF)·먼 재등장(사이 컷 ≥1, 그림 상관 ≥ SAME_CORR)
  눈 칸(judge.json, 오푸스 — 칼카피_시작 13): 대본 = 첫 줄 틀·훅 세기(0~2)·블록 순서(0~2)·이야기 기술 수·어색함 수·지어냄 수 /
              장면 = 줄마다 ○△×+이유 · 제품 보이는 비율
  table       칸마다 상위 N편 중앙·최저(또는 최고 — 낮을수록 좋은 칸)·우리 → 중앙보다 나쁜 칸 표시(원인·고칠 규칙은 사람이 표 아래에 적는다)
"""
from __future__ import annotations

import json
import random
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA = Path("C:/숏템_칼카피")
FPS = 30
STILL_DIFF = 1.5      # 0.1초 간격 회색(90px 폭) 평균 절대차가 이보다 작으면 정지 칸 — quality_gate.freezes 와 같은 뜻(창 안 같은 그림)
SAME_CORR = 0.95      # 먼 재등장 = 사이에 컷 ≥1 끼고 그림 상관 ≥ 이 값(같은 프레임을 다시 보임 — channel/homedesignnote/preset/repeat_measure.py 같은 자)
GAP_BREAK = 0.6       # 받아쓰기 낱말 사이 쉼이 이보다 길면 줄 끊기(문장부호 없는 받아쓰기)
CONNECTORS = ("심지어", "근데", "특히", "얼마 전에", "그런데", "진짜 핵심", "더 말도 안", "말도 안 되는", "충격적인", "미친", "대박", "알고 보니", "그래서", "게다가", "무엇보다")
END_KINDS = (("CTA", r"댓글|남겨|링크|프로필|구매처"), ("사회반응", r"난리|품절|사이에서|필수템|대란|열풍|인기|유명"), ("질문", r"\?|까요$|나요$"),
             ("반전·정체성", r"아니라|소리까지"), ("만족·변화", r"."))
MADE_RE = re.compile(r"\d+\s*(?:분|초|시간|일|년|개월|배|%|만|천|억|명|개)|(?:일본|미국|독일|중국|한국|프랑스|영국|스웨덴|이탈리아|대만)|(?:특허|인증|연구|박사|의사|약사)")
LOWER_BETTER = {"줄↔컷 어긋남(초)", "정지 비율", "먼 재등장(개)", "어색함(개)", "지어냄 후보(개, 기계)", "지어냄(개, 눈)", "장면 × 비율"}


# ── 벤치 편 고르기 ─────────────────────────────────────────────────────────
def bench_ids(slug: str, n: int) -> list[str]:
    top = json.loads((DATA / slug / "top.json").read_text(encoding="utf-8"))
    out = []
    for r in top:
        vid = r["id"]
        if (DATA / slug / "mp4" / f"{vid}.mp4").exists() and (DATA / slug / "asr" / f"{vid}.json").exists():
            out.append(vid)
        if len(out) >= n:
            break
    return out


# ── 받아쓰기 → 줄 ───────────────────────────────────────────────────────────
def sentences(asr: dict) -> list[dict]:
    """[{t0,t1,text}] — 문장부호(. ? !) 또는 GAP_BREAK 넘는 쉼에서 끊는다. 스피치매틱스(낱말)·제미나이(구절) 둘 다 results 꼴."""
    out, cur, t0, last = [], [], None, None
    for r in asr.get("results") or []:
        txt = ((r.get("alternatives") or [{}])[0].get("content") or "").strip()
        if r.get("type") == "punctuation":
            if cur:
                cur[-1] += txt
                if txt in ".?!":
                    out.append({"t0": t0, "t1": last, "text": " ".join(cur)}); cur, t0 = [], None
            continue
        s, e = float(r.get("start_time") or 0), float(r.get("end_time") or 0)
        if cur and last is not None and s - last > GAP_BREAK:
            out.append({"t0": t0, "t1": last, "text": " ".join(cur)}); cur, t0 = [], None
        if t0 is None:
            t0 = s
        cur.append(txt); last = e
        if re.search(r"[.?!]$", txt):
            out.append({"t0": t0, "t1": last, "text": " ".join(cur)}); cur, t0 = [], None
    if cur:
        out.append({"t0": t0, "t1": last, "text": " ".join(cur)})
    return [x for x in out if re.sub(r"\W", "", x["text"])]


def asr_raw(mp4: Path, cache: Path) -> dict:
    """우리 완성본 받아쓰기 — 벤치 asr/<id>.json 과 **같은 설정**(스피치매틱스 batch · language ko · enhanced · json-v2 원본 그대로)이라야 줄 끊기가 같은 자다.
    키 = engine/asr_local.speechmatics_key(값은 어디에도 안 적는다). cache 가 있으면 다시 안 부른다(과금 1회)."""
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    import time
    import requests
    from tools.calcopy.engine.asr_local import speechmatics_key
    H = {"Authorization": f"Bearer {speechmatics_key()}"}
    cfg = {"type": "transcription", "transcription_config": {"language": "ko", "operating_point": "enhanced", "diarization": "none"}}
    with open(mp4, "rb") as f:
        r = requests.post("https://asr.api.speechmatics.com/v2/jobs", headers=H, files={"data_file": f}, data={"config": json.dumps(cfg)}, timeout=120)
    r.raise_for_status()
    jid = r.json()["id"]
    for _ in range(120):
        time.sleep(3)
        st = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}", headers=H, timeout=30).json()["job"]["status"]
        if st == "done":
            break
        if st in ("rejected", "deleted"):
            raise RuntimeError(f"speechmatics {st}")
    t = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}/transcript?format=json-v2", headers=H, timeout=60).json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
    return t


def ours_lines(doc: Path, work: Path) -> list[dict]:
    """우리 편 줄 = 완성본 받아쓰기 → sentences(벤치와 같은 끊기). 대본 줄로 끊으면 벤치(받아쓰기 문장)와 자가 달라진다(10-26 첫 판: 8줄 vs 4줄)."""
    import hashlib
    f = work / "render" / "final.mp4"
    h = hashlib.md5(f.read_bytes()).hexdigest()[:8]          # 완성본이 바뀌면 다시 받아쓴다(캐시 열쇠 = md5)
    return sentences(asr_raw(f, doc / "대조" / f"ours_asr_{h}.json"))


# ── 기계 칸 ─────────────────────────────────────────────────────────────────
def _gray(mp4: Path, fps: float, w: int = 90):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},scale={w}:-2,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    h = round(w * 1920 / 1080 / 2) * 2
    n = len(raw) // (w * h)
    return np.frombuffer(raw[:n * w * h], np.uint8).reshape(n, h, w).astype(np.float32)


def machine(mp4: Path, lines: list[dict]) -> dict:
    import numpy as np
    from tools.calcopy.engine.kal_analyze import media_of
    m = media_of(str(mp4))
    cuts = [0.0] + list(m["cut_at"])
    txt = [re.sub(r"\s", "", l["text"]) for l in lines]
    off = [min(abs(l["t0"] - c) for c in cuts) for l in lines if l["t0"] is not None]
    G = _gray(mp4, 10)
    d = np.abs(np.diff(G, axis=0)).mean(axis=(1, 2)) if len(G) > 1 else np.array([])
    # 먼 재등장: 컷 조각마다 가운데 프레임 — 사이 컷 ≥1 인 짝 상관 ≥ SAME_CORR
    b = cuts + [m["duration"]]
    mids = [int((b[i] + b[i + 1]) / 2 * 10) for i in range(len(b) - 1)]
    F = [G[min(k, len(G) - 1)].ravel() for k in mids] if len(G) else []
    F = [(f - f.mean()) / (f.std() + 1e-6) for f in F]
    rep = sum(1 for i in range(len(F)) for j in range(i + 2, len(F)) if float(np.mean(F[i] * F[j])) >= SAME_CORR)
    last = lines[-1]["text"] if lines else ""
    end = next(k for k, rx in END_KINDS if re.search(rx, last.strip()))
    return {"길이(초)": m["duration"], "컷 중앙(초)": m["cut_median"], "컷 수": m["n_cuts"],
            "줄 수": len(lines), "글자 수": sum(len(t) for t in txt), "줄당 글자(중앙)": statistics.median([len(t) for t in txt]) if txt else None,
            "연결어 줄 비율": round(sum(any(l["text"].strip().startswith(c) for c in CONNECTORS) for l in lines) / len(lines), 3) if lines else None,
            "끝맺음": end, "지어냄 후보(개, 기계)": sum(len(MADE_RE.findall(l["text"])) for l in lines),
            "줄↔컷 어긋남(초)": round(statistics.median(off), 3) if off else None,
            "정지 비율": round(float((d < STILL_DIFF).mean()), 3) if len(d) else None, "먼 재등장(개)": rep}


# ── 눈 시트 ─────────────────────────────────────────────────────────────────
def sheet(mp4: Path, lines: list[dict], out: Path):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 18)
    W, H = 150, 266
    im = Image.new("RGB", (3 * W + 420, max(1, len(lines)) * (H + 6)), "white")
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        y = i * (H + 6)
        for k, t in enumerate((l["t0"] + 0.15, (l["t0"] + l["t1"]) / 2, max(l["t0"] + 0.2, l["t1"] - 0.15))):
            b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={W}:{H}", "-f", "image2pipe", "-vcodec", "png", "-"],
                               capture_output=True, stdin=subprocess.DEVNULL).stdout
            if b:
                import io
                im.paste(Image.open(io.BytesIO(b)).convert("RGB"), (k * W, y))
        txt = f"{i + 1}. {l['text']}"
        for r in range(0, min(len(txt), 120), 20):
            d.text((3 * W + 8, y + 8 + (r // 20) * 26), txt[r:r + 20], font=f, fill="black")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=85)


def prep(slug: str, doc: Path, work: Path, top: int = 10, seed: int = 26) -> Path:
    D = doc / "대조"
    ids = bench_ids(slug, top)
    items = [{"name": vid, "mp4": str(DATA / slug / "mp4" / f"{vid}.mp4"), "lines": sentences(json.loads((DATA / slug / "asr" / f"{vid}.json").read_text(encoding="utf-8")))} for vid in ids]
    items.append({"name": "우리", "mp4": str(work / "render" / "final.mp4"), "lines": ours_lines(doc, work)})
    order = list(range(len(items)))
    random.Random(seed).shuffle(order)
    key, judge, mach = {}, {}, {}
    for v, k in enumerate(order, 1):
        it = items[k]
        V = f"V{v:02d}"
        key[V] = it["name"]
        mach[V] = machine(Path(it["mp4"]), it["lines"]) if it["lines"] else {"줄 수": 0}
        sheet(Path(it["mp4"]), it["lines"], D / "sheets" / f"{V}.jpg")
        judge[V] = {"script": {"첫 줄 틀": "", "훅 세기(0~2)": None, "블록 순서(0~2)": None, "이야기 기술(개)": None, "어색함(개)": None, "지어냄(개, 눈)": None, "메모": ""},
                    "scene": {"lines": [{"i": i + 1, "v": "", "why": ""} for i in range(len(it["lines"]))], "제품 보임 비율": None}}
    (D / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "machine.json").write_text(json.dumps({"slug": slug, "ids": ids, "machine": mach, "lines": {V: items[order[int(V[1:]) - 1]]["lines"] for V in key}},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    jp = D / "judge.json"
    if not jp.exists():
        jp.write_text(json.dumps(judge, ensure_ascii=False, indent=1), encoding="utf-8")
    return D


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def table(slug: str, doc: Path) -> Path:
    D = doc / "대조"
    key = json.loads((D / "key.json").read_text(encoding="utf-8"))
    M = json.loads((D / "machine.json").read_text(encoding="utf-8"))["machine"]
    J = json.loads((D / "judge.json").read_text(encoding="utf-8"))
    rows: dict = {}
    for V, name in key.items():
        r = dict(M.get(V) or {})
        js, jc = (J.get(V) or {}).get("script") or {}, (J.get(V) or {}).get("scene") or {}
        for k in ("훅 세기(0~2)", "블록 순서(0~2)", "이야기 기술(개)", "어색함(개)", "지어냄(개, 눈)"):
            r[k] = js.get(k)
        r["첫 줄 틀"] = js.get("첫 줄 틀")
        L = [x for x in jc.get("lines") or [] if x.get("v") in ("○", "△", "×")]
        if L:
            r["장면 ○ 비율"] = round(sum(x["v"] == "○" for x in L) / len(L), 3)
            r["장면 × 비율"] = round(sum(x["v"] == "×" for x in L) / len(L), 3)
        r["제품 보임 비율"] = jc.get("제품 보임 비율")
        rows[name] = r
    ours = rows.pop("우리", {})
    cols = [k for k in ours if _num(ours[k]) is not None or any(_num(v.get(k)) is not None for v in rows.values())]
    out = [f"# 상위 {len(rows)}편 대조 — {slug} (도구 tools/calcopy/bench_compare_script_scene.py · 눈 칸 = 오푸스, 섞은 V 번호로 매김)", "",
           f"벤치 편: {', '.join(rows)}", "", "| 칸 | 상위 중앙 | 상위 최저(나쁜 쪽) | 우리 | 판정 |", "|---|---|---|---|---|"]
    for k in cols:
        vals = [_num(v.get(k)) for v in rows.values() if _num(v.get(k)) is not None]
        o = _num(ours.get(k))
        if not vals:
            continue
        med = round(statistics.median(vals), 3)
        worst = max(vals) if k in LOWER_BETTER else min(vals)
        if o is None:
            j = "미측정"
        elif k in ("길이(초)", "컷 중앙(초)", "컷 수", "줄 수", "글자 수", "줄당 글자(중앙)", "연결어 줄 비율"):
            lo, hi = min(vals), max(vals)
            j = "○ 범위 안" if lo <= o <= hi else "× 범위 밖"
        else:
            bad = o > med if k in LOWER_BETTER else o < med
            j = "× 중앙보다 나쁨" if bad else "○"
        out.append(f"| {k} | {med} | {round(worst, 3)} | {o} | {j} |")
    out += ["", "## 편마다 끝맺음·첫 줄 틀", "", "| 편 | 첫 줄 틀 | 끝맺음 |", "|---|---|---|"]
    for name, r in list(rows.items()) + [("우리", ours)]:
        out.append(f"| {name} | {r.get('첫 줄 틀') or ''} | {r.get('끝맺음') or ''} |")
    p = doc / "대조표.md"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def main() -> int:
    a = sys.argv[1:]
    if len(a) >= 4 and a[0] == "prep":
        top = int(a[a.index("--top") + 1]) if "--top" in a else 10
        print(prep(a[1], Path(a[2]), Path(a[3]), top))
    elif len(a) >= 3 and a[0] == "table":
        print(table(a[1], Path(a[2])))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
