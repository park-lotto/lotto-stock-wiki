# -*- coding: utf-8 -*-
"""뜯기 전/후 점검 표 — 워커 점검.md(1판 결과·정답)와 새 뜯기.json 을 항목별로 대조해 맞음/틀림/수동을 자동으로 낸다.

    PYTHONUTF8=1 py tools/calcopy/engine/recheck.py <slug> [id …] [--new-root DIR] [--analyze] [--cpu-only]

  <slug>        channel/<slug>/뜯기/<id>/점검.md 가 있는 채널(id 생략 = 점검.md 있는 편 전부)
  --new-root    새 결과 폴더(편마다 <DIR>/<id>/뜯기.json). 기본 C:/숏템_칼카피/<slug>/engine_뜯기3
  --analyze     대조 전에 analyze.py 로 다시 뜯는다(영상 C:/숏템_칼카피/<slug>/mp4/<id>.mp4)
  --cpu-only    다시 뜯을 때 제미나이를 부르지 않는다(글자 읽기·제작법·받아쓰기 등은 failed:cpu-only)

출력: channel/<slug>/뜯기/<id>/재점검.md(항목별 1판 판정 · 새 값 · 자동 판정) + channel/<slug>/뜯기/재점검_요약.md(편별 개수).
★자동 판정은 점검.md 의 '정답' 글에서 숫자·낱말을 뽑아 비교한다(규칙은 아래 JUDGES 한 곳). 뽑을 수 없는 항목은 '수동'으로 남긴다 —
 맞음으로 세지 않는다. 1판 판정은 점검.md 의 '판정' 칸 글(없으면 '—')을 그대로 옮긴다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIDEO_ROOT = Path("C:/숏템_칼카피")
TOL_Y = 40          # 좌표 허용(px) — 정답이 540px 눈대중 ×2(±30) 이라 조금 넉넉히
TOL_T = 0.3         # 시각 허용(초)


# ── 점검.md 읽기 ───────────────────────────────────────────────────────────
def parse_check(md: str) -> list[dict]:
    """점검.md 안의 표마다 행 → {item, cols:{머리글: 값}, text: 행 전체}. 머리글 이름이 워커마다 달라 칸 이름으로 찾는다."""
    rows, head = [], None
    for line in md.splitlines():
        if not line.startswith("|"):
            head = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        if head is None:
            head = cells
            continue
        cols = dict(zip(head, cells))
        item = next((v for k, v in cols.items() if k not in ("#", "") and not re.fullmatch(r"\d+[a-z]?", v)), cells[0])
        rows.append({"item": re.sub(r"\*", "", item), "cols": cols, "text": " ".join(cells)})
    return rows


def _col(row: dict, *names: str) -> str:
    for k, v in row["cols"].items():
        if any(n in k for n in names):
            return v
    return ""


# ── 정답 글에서 뽑기 ───────────────────────────────────────────────────────
def _yrange(t: str):
    m = re.search(r"y\s*≈?\s*(\d{2,4})\s*[~\-–]\s*(\d{2,4})", t)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _secs(t: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*[~\-–]\s*(\d+(?:\.\d+)?|끝)\s*초", t)
    if not m:
        return None
    return float(m.group(1)), (None if m.group(2) == "끝" else float(m.group(2)))


def _count(t: str):
    m = re.search(r"(\d+)\s*개", t)
    return int(m.group(1)) if m else None


def _rgb(t: str):
    m = re.search(r"\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", t)
    if m:
        return [int(m.group(i)) for i in (1, 2, 3)]
    m = re.search(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", t)
    if m:
        h = m.group(1)
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    if re.search(r"흰", t):
        return [250, 250, 250]
    if re.search(r"검정|까만|검은", t):
        return [10, 10, 10]
    return None


def _ok(b) -> str:
    return "맞음" if b else "틀림"


# ── 항목 종류별 판정(한 곳) ────────────────────────────────────────────────
def j_duration(R, truth):
    m = re.search(r"(\d+\.\d+)\s*초", truth)
    if not m:
        return None
    return _ok(abs(R["probe"]["duration"] - float(m.group(1))) <= 0.15), f"{R['probe']['duration']}초"


def j_bg(R, truth):
    want = _rgb(truth)
    got = (R.get("layout") or {}).get("bg_rgb")
    if not want or not got:
        return None
    return _ok(max(abs(a - b) for a, b in zip(want, got)) <= 25), str(got)


def j_window(R, truth):
    w = (R.get("layout") or {}).get("window")
    m_top = re.search(r"위\s*(\d{2,4})\s*[~\-–]\s*(\d{2,4})", truth)
    m_bot = re.search(r"아래\s*(\d{2,4})\s*[~\-–]\s*(\d{2,4})", truth)
    if w is None:
        return ("틀림" if (m_top or _yrange(truth)) else None), "None"
    top, bot = w[1], w[1] + w[3]
    if m_top and m_bot:
        a, b = int(m_top.group(1)), int(m_top.group(2))
        c, d = int(m_bot.group(1)), int(m_bot.group(2))
        return _ok(a - TOL_Y <= top <= b + TOL_Y and c - TOL_Y <= bot <= d + TOL_Y), f"{top}~{bot}"
    yr = _yrange(truth)
    if not yr:
        return None
    return _ok(abs(top - yr[0]) <= TOL_Y and abs(bot - yr[1]) <= TOL_Y), f"{top}~{bot}"


def j_frames(R, truth):
    other = (R.get("layout") or {}).get("other_frame_segments") or []
    dur = R["probe"]["duration"]
    if re.search(r"없음|해당 없음", truth) and not _secs(truth):
        return _ok(not other), str(other)
    sc = _secs(truth)
    if not sc:
        return None
    a, b = sc
    b = dur if b is None else b
    hit = any(abs(s - a) <= TOL_T + 0.2 and abs(e - b) <= TOL_T + 0.2 for s, e in other)
    return _ok(hit), str(other)


def j_outro(R, truth):
    """아웃트로 = 영상 끝에 닿는 틀 다른 구간만. 처음 훅 카드(0~1.5초)를 아웃트로로 세면 '없음'이 틀림이 됐다(2026-10-16 rGFX)."""
    other = (R.get("layout") or {}).get("other_frame_segments") or []
    dur = R["probe"]["duration"]
    tail = [seg for seg in other if seg[1] >= dur - TOL_T - 0.2 and seg[0] > 0.5]
    if re.search(r"없음|해당 없음", truth) and not _secs(truth):
        return _ok(not tail), str(tail)
    sc = _secs(truth)
    if not sc:
        return None
    a = sc[0]
    return _ok(any(abs(s0 - a) <= TOL_T + 0.2 for s0, _ in tail)), str(tail)


def j_cap_count(R, truth):
    n = _count(truth)
    got = (R.get("captions") or {}).get("n_spans")
    if n is None or got is None:
        return None if n is None else ("틀림", "자막 없음")
    return _ok(abs(got - n) <= max(1, round(0.15 * n))), f"{got}개"


def j_cap_pos(R, truth):
    yr = _yrange(truth)
    band = (R.get("layout") or {}).get("caption_band")
    if not yr:
        return None
    if not band:
        return "틀림", "자막 띠 없음"
    return _ok(abs(band[0] - yr[0]) <= TOL_Y and abs(band[1] - yr[1]) <= TOL_Y), str(band)


def j_cap_color(R, truth):
    s = ((R.get("text_fx") or {}).get("summary") or {})
    fill = s.get("fill_rgb")
    if not fill:
        return None
    lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
    if re.search(r"검정|까만|검은", truth.split("외곽")[0]):
        return _ok(lum < 90), str(fill)
    if re.search(r"흰|하양|white", truth.split("외곽")[0]):
        return _ok(lum > 170), str(fill)
    return None


def j_outline(R, truth):
    s = ((R.get("text_fx") or {}).get("summary") or {})
    px = s.get("outline_px")
    if px is None:
        return None
    if re.search(r"외곽선\s*(·\s*그림자\s*)?없|외곽선 0|외곽선·그림자 없", truth):
        return _ok(px == 0), f"{px}px"
    m = re.search(r"(\d+)\s*[~\-]?\s*(\d+)?\s*px", truth)
    if "외곽" in truth and m:
        lo = int(m.group(1)); hi = int(m.group(2) or m.group(1))
        return _ok(lo - 2 <= px <= hi + 2), f"{px}px"
    if "외곽선" in truth:
        return _ok(px > 0), f"{px}px"
    return None


def j_shadow(R, truth):
    s = ((R.get("text_fx") or {}).get("summary") or {})
    if "shadow" not in s:
        return None
    if re.search(r"그림자\s*없|그림자 없음|외곽선·그림자 없|없는 그림자", truth):
        return _ok(not s["shadow"]), str(s["shadow"])
    return None


def j_tone(R, truth):
    st = R.get("script_tone") or {}
    if not st.get("ok"):
        return None
    # '반말' 먼저 — "반말 나레 + 인용 존댓말"은 반말이다(2026-10-16 7DY 거짓 틀림)
    if "반말" in truth:
        return _ok(st["polite_ratio"] < 0.5), f"존댓말 {st['polite_ratio']}"
    if "존댓말" in truth:
        return _ok(st["polite_ratio"] >= 0.5), f"존댓말 {st['polite_ratio']}"
    return None


def j_material(R, truth):
    sh = (R.get("materials") or {}).get("share_by_time") or {}
    if not sh:
        return None
    top = max(sh, key=sh.get)
    if "재편집" in truth or "남의 영상" in truth:
        return _ok(top == "남의영상재편집"), f"{top} {sh[top]}"
    return None


JUDGES = [   # (항목 이름에 들어 있으면, 판정 함수) — 위에서부터 첫 일치
    (r"길이|크기", j_duration),
    (r"아웃트로", j_outro),
    (r"^(?!.*글자).*(훅|인트로|틀이 다른|틀 사라|전환)", j_frames),
    (r"배경", j_bg),
    (r"영상 창|^창$|그림 칸", j_window),
    (r"자막 (개수|수)|교체 6개|자막 수", j_cap_count),
    (r"자막 (위치|띠|자리)", j_cap_pos),
    (r"외곽선", j_outline),
    (r"그림자", j_shadow),
    (r"자막 (색|글자색)|글자 효과|글자색", j_cap_color),
    (r"말투", j_tone),
    (r"제작법|재료", j_material),
]


def judge_row(R: dict | None, row: dict) -> tuple[str, str]:
    if R is None:
        return "새 결과 없음", ""
    # 정답 칸 이름이 워커마다 다르다('정답'·'시트로 본 것'). 못 찾으면 행 전체 글인데, 그러면 분석기 값 칸('존댓말 0.0')까지 정답으로 읽혀
    # 말투 3건이 거짓 틀림이 됐다(2026-10-16 썰풀다 1_Vt·7DY·ho5G)
    truth = _col(row, "정답", "시트로 본", "눈으로 본") or row["text"]
    for pat, fn in JUDGES:
        if re.search(pat, row["item"]):
            try:
                r = fn(R, truth)
            except Exception as e:  # noqa: BLE001 — 판정 함수 하나가 깨져도 표는 만든다
                return "수동", f"판정 오류 {type(e).__name__}"
            if r and r[0]:
                return r[0], r[1]
            return "수동", (r[1] if r else "정답 글에서 숫자·낱말을 못 뽑음")
    return "수동", "자동 판정 규칙 없음"


def old_verdict(row: dict) -> str:
    v = _col(row, "판정")
    return re.sub(r"\*", "", v) if v else "—"


def _norm(v: str) -> str:
    if re.search(r"틀림", v):
        return "틀림"
    if re.search(r"맞음", v):
        return "맞음"
    return "기타"


# ── 실행 ──────────────────────────────────────────────────────────────────
def analyze_one(slug: str, vid: str, out: Path, cpu_only: bool) -> str:
    mp4 = VIDEO_ROOT / slug / "mp4" / f"{vid}.mp4"
    if not mp4.exists():
        return f"영상 없음 {mp4}"
    from tools.calcopy.engine import analyze
    llm = (lambda parts, prompt, tag: (None, "cpu-only")) if cpu_only else None
    t = time.time()
    analyze.analyze(str(mp4), str(out / vid), llm=llm)
    return f"{time.time() - t:.0f}초"


def recheck(slug: str, ids: list[str], new_root: Path) -> dict:
    base = ROOT / "channel" / slug / "뜯기"
    summary = {}
    for vid in ids:
        ck = base / vid / "점검.md"
        if not ck.exists():
            summary[vid] = {"failed": "점검.md 없음"}
            continue
        rows = parse_check(ck.read_text(encoding="utf-8"))
        jf = new_root / vid / "뜯기.json"
        R = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else None
        lines = [f"# 재점검 — {vid}", "",
                 f"- 1판 점검: `{ck.relative_to(ROOT).as_posix()}` · 새 결과: `{jf.as_posix()}`" + ("" if R else " (없음)"),
                 f"- 새 결과 엔진: {(R or {}).get('engine', '—')} · 잰 시각 {(R or {}).get('measured_at', '—')}", "",
                 "| 항목 | 1판 판정 | 새 값 | 자동 판정 |", "|---|---|---|---|"]
        cnt = {"맞음": 0, "틀림": 0, "수동": 0, "1판_맞음": 0, "1판_틀림": 0}
        for row in rows:
            ov = old_verdict(row)
            nv, val = judge_row(R, row)
            cnt[nv if nv in cnt else "수동"] += 1
            if _norm(ov) == "맞음":
                cnt["1판_맞음"] += 1
            elif _norm(ov) == "틀림":
                cnt["1판_틀림"] += 1
            lines.append(f"| {row['item'][:40]} | {ov[:40]} | {val[:60]} | **{nv}** |")
        lines += ["", f"자동 판정: 맞음 {cnt['맞음']} · 틀림 {cnt['틀림']} · 수동 {cnt['수동']} "
                      f"(1판 점검 판정 칸: 맞음 {cnt['1판_맞음']} · 틀림 {cnt['1판_틀림']})", ""]
        (base / vid / "재점검.md").write_text("\n".join(lines), encoding="utf-8")
        summary[vid] = cnt
    sm = [f"# 재점검 요약 — {slug}", "", f"새 결과: `{new_root.as_posix()}` · {time.strftime('%Y-%m-%d %H:%M')}", "",
          "| 편 | 자동 맞음 | 자동 틀림 | 수동 | 1판 맞음 | 1판 틀림 |", "|---|---|---|---|---|---|"]
    tot = {"맞음": 0, "틀림": 0, "수동": 0, "1판_맞음": 0, "1판_틀림": 0}
    for vid, c in summary.items():
        if c.get("failed"):
            sm.append(f"| {vid} | {c['failed']} | | | | |")
            continue
        sm.append(f"| {vid} | {c['맞음']} | {c['틀림']} | {c['수동']} | {c['1판_맞음']} | {c['1판_틀림']} |")
        for k in tot:
            tot[k] += c[k]
    sm.append(f"| **합** | {tot['맞음']} | {tot['틀림']} | {tot['수동']} | {tot['1판_맞음']} | {tot['1판_틀림']} |")
    sm += ["", "★1판 판정은 워커가 손으로 적은 글이라 '맞음/틀림' 낱말이 없는 칸(미측정·일부 등)은 세지 않았다.",
           "★자동 판정은 정답 글에서 뽑을 수 있는 항목만 — '수동'은 맞다고 세지 않는다."]
    (base / "재점검_요약.md").write_text("\n".join(sm), encoding="utf-8")
    return {"summary": summary, "total": tot}


def main() -> None:
    ap = argparse.ArgumentParser(description="뜯기 전/후 점검 표")
    ap.add_argument("slug")
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--new-root")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--cpu-only", action="store_true")
    a = ap.parse_args()
    base = ROOT / "channel" / a.slug / "뜯기"
    ids = a.ids or sorted(p.parent.name for p in base.glob("*/점검.md"))
    new_root = Path(a.new_root) if a.new_root else VIDEO_ROOT / a.slug / "engine_뜯기3"
    if a.analyze:
        for vid in ids:
            print(vid, "뜯기", analyze_one(a.slug, vid, new_root, a.cpu_only), flush=True)
    r = recheck(a.slug, ids, new_root)
    print(json.dumps(r["total"], ensure_ascii=False))
    print("요약:", (base / "재점검_요약.md").as_posix())


if __name__ == "__main__":
    main()
