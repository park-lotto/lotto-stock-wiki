# -*- coding: utf-8 -*-
"""완성본 자막 줄 시각 ↔ 실제 나레 소리 대조 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/engine/check_line_sync.py <make 폴더(final.mp4·sfx_events.json)> [...]

왜: 썰템쇼 작품3 에서 B 표가 통과(B15 만 미달)했는데 실제로는 가운데 줄 자막이 소리보다 1~2초 늦게 떴다(줄 시각 = sfx_events.timeline,
소리 = 받아쓰기). 자막 시각은 렌더 쪽 계산이라 렌더 결과물(소리)로 대조해야 잡힌다.
재는 법: final.mp4 소리를 받아쓰기(asr_segments, 구절 단위) → 줄마다 '그 줄 첫 낱말이 처음 들리는 구절 시작'과
자막 줄 시작의 차. 구절이 여러 줄을 묶으면 그 구절 안 글자 비율로 줄 시작을 나눠 추정한다.
판정: |차| > 0.6초 줄 또는 받아쓰기에서 못 찾은 줄이 하나라도 있으면 미달(못 잰 걸 통과로 치지 않는다 — 10-18 첫 판이 전부 '?'로 ○를 냈다). 결과 = <make>/line_sync.json + 표 출력.
"""
import json
import re


import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIMIT = 0.6


def _norm(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s or "")


def _sec(v) -> float:
    v = str(v)
    if ":" in v:                    # 'MM:SS(.s)' 로 오는 답도 있다
        m, x = v.rsplit(":", 1)
        return int(m) * 60 + float(x)
    return float(v)


def asr_segments(final: Path) -> list[tuple[float, float, str]]:
    """받아쓰기 = 엔진 제미나이 창구(gemini_free.ask — 로컬 키 → 막히면 서버 공용 풀) + 지시문 transcribe_free.P 한 벌.
    소리만(mp3) + gemini-2.5-flash — 영상째·기본 모델은 2초 단위 시각만 돌려줘 0.6초 판정에 못 쓴다(10-18 실측)."""
    import subprocess
    sys.path.insert(0, str(ROOT))
    from tools.calcopy.engine import gemini_free as G
    from tools.calcopy.transcribe_free import P
    mp3 = subprocess.run(["ffmpeg", "-v", "error", "-i", str(final), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", "-f", "mp3", "-"],
                         capture_output=True).stdout
    import time
    for k in range(4):              # 503(모델 바쁨)은 잠깐 쉬고 다시
        d, err = G.ask([(mp3, "audio/mp3")], P, tag="line_sync", models=("gemini-2.5-flash",))
        if d is not None or "503" not in str(err):
            break
        time.sleep(20 * (k + 1))
    if d is None:
        raise RuntimeError(f"받아쓰기 실패: {err}")
    seg = (d.get("segments") or d.get("items") or [])
    out = [(_sec(x["start"]), _sec(x["end"]), x["text"]) for x in seg if str(x.get("text", "")).strip()]
    if not out:
        raise RuntimeError("받아쓰기 빈 답")
    if all(float(a).is_integer() and float(b).is_integer() for a, b, _ in out):
        raise RuntimeError("받아쓰기 시각이 1초 단위뿐 — 0.6초 판정에 못 쓴다")
    return out


def line_starts_from_asr(lines: list[str], segs) -> list[float | None]:
    """줄 글(정규화)을 받아쓰기 구절 글 이어붙인 것에 차례로 맞춰, 줄 첫 글자가 놓인 구절 안 위치를 시각으로 옮긴다.
    lines = 줄마다 실제로 말하는 전문. 찾은 뒤(또는 못 찾아도) 그 줄 몫만큼 앞으로 넘긴다 — 10-18 작품1: 「성분표」를 「공분표」로
    들어 5줄을 놓치자 6줄 「다크 초콜릿」이 5줄 안의 같은 낱말에 붙어 1.29초 어긋남으로 거짓 미달이 났다.
    오탈자는 창(남은 줄 몫 안) 안에서 첫 6글자 비슷함(≥ 0.6)으로 찾는다 — 숫자 표기(1만 2천 ↔ 12,000) 차이 때문에 몫은 절반만 넘긴다."""
    from difflib import SequenceMatcher
    chars = []                      # (글자, 시각)
    for a, b, t in segs:
        n = _norm(t)
        for k, ch in enumerate(n):
            chars.append((ch, a + (b - a) * k / max(1, len(n))))
    stream = "".join(c for c, _ in chars)
    out, pos = [], 0
    for ln in lines:
        n = _norm(ln)
        if not n:
            out.append(None); continue
        key = n[:6]
        hi = min(len(stream), pos + len(n) + 12)
        j = stream.find(key[:4], pos, hi + 4)
        if j < 0:                   # 받아쓰기 오탈자 — 창 안에서 가장 비슷한 자리
            best = max(((SequenceMatcher(None, key, stream[i:i + len(key)]).ratio(), i) for i in range(pos, max(pos + 1, hi))),
                       default=(0, -1))
            j = best[1] if best[0] >= 0.6 else -1
        if j < 0:
            out.append(None); pos = min(len(stream), pos + len(n) // 2); continue
        out.append(round(chars[j][1], 2)); pos = j + max(1, len(n) // 2)
    return out


def check(make: Path) -> dict:
    tl = json.loads((make / "sfx_events.json").read_text(encoding="utf-8"))["timeline"]
    # 말하는 전문 = caption_lines 마지막(쌓이는 자막이면 앞은 그 일부) — 화자 표시('제조사 : ')는 소리에 없으니 뗀다
    lines = [re.sub(r"^[^:]{1,12}\s:\s", "", (b.get("caption_lines") or [b["narration"]])[-1].replace("\n", " ")) for b in tl]
    segs = asr_segments(make / "final.mp4")
    heard = line_starts_from_asr(lines, segs)
    rows = []
    for b, ln, h in zip(tl, lines, heard):
        d = None if h is None else round(float(b["t0"]) - h, 2)
        rows.append({"line": ln[:24], "caption_t0": b["t0"], "heard_t0": h, "diff": d, "ok": d is not None and abs(d) <= LIMIT})
    bad = [r for r in rows if not r["ok"]]
    res = {"make": str(make), "limit_sec": LIMIT, "ok": not bad, "bad": len(bad), "rows": rows, "asr": segs}
    (make / "line_sync.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    for m in sys.argv[1:]:
        r = check(Path(m))
        print(f"== {m} → {'○' if r['ok'] else '× 미달'} (어긋난 줄 {r['bad']})")
        for x in r["rows"]:
            print(f"  자막 {x['caption_t0']:6.2f}  소리 {x['heard_t0'] if x['heard_t0'] is not None else '  ?  ':>6}  차 {x['diff'] if x['diff'] is not None else '-':>6} {'' if x['ok'] else '×'} {x['line']}")
