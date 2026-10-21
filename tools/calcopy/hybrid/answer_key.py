# -*- coding: utf-8 -*-
"""정답지 검증(볼케이노형 회원 라인, 관제 234·097 2026-10-21) — 집 PC 가 만든 편을 기준으로 회원 경로 결과를 단계마다 대조한다.

    py tools/calcopy/hybrid/answer_key.py cache  <편> --to <캐시 폴더>      # 받아 둔 원본·벤치·재료로 소스 캐시(유튜브 0회 시험용) — 원본 폴더는 복사만
    py tools/calcopy/hybrid/answer_key.py compare <편> --job <회원 작업 폴더> # 합격 표(answer_key_report.md) + 종료코드(0 합격)

정답지 = KEYS[편] (조사.md §1 원본·근거.md 원음 구간·재료·쿠팡 번호). 합격 기준 = 설계 2026-10-21-숏템MCP-볼케이노형-design §8.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import jload  # noqa: E402

KEYS = {
    # 성시경 신라면(10-18 키치잇판) — 받아 둔 원본·재료가 남은 유일한 편(10-21 실측). 쿠팡 번호 없음('쿠팡·마트 어디서나') → 제품은 이름 대조
    "성시경": {
        "src_dir": r"C:\숏템_칼카피\yanshottem\하이브리드_성시경",
        "bench": "sMx9RWuifCA", "origin": "Wy9--jw0ZsM", "product_name": ["신라면"], "coupang": None,
        "orig_spans": [[11.80, 14.82], [15.85, 19.35], [257.2, 259.1]], "materials": ["-o8gedIaYmA", "FaIQ3NIgVbU"],
        "doc": "channel/kitchit/하이브리드_성시경",
    },
}


def cache(name: str, to: Path):
    K = KEYS[name]
    s = Path(K["src_dir"])
    (to / "yt").mkdir(parents=True, exist_ok=True)
    (to / "material").mkdir(parents=True, exist_ok=True)
    (to / "search").mkdir(parents=True, exist_ok=True)
    (to / "channel").mkdir(parents=True, exist_ok=True)
    for f in (s / "bench").glob(f"{K['bench']}*"):
        if f.suffix in (".json", ".vtt", ".mp4"):
            shutil.copyfile(f, to / "yt" / f.name)
    for ext in (".mp4", ".info.json"):
        f = s / "src" / f"{K['origin']}{ext}"
        if f.exists() and not (to / "yt" / f.name).exists():
            shutil.copyfile(f, to / "yt" / f.name)
    found, titles = [], []
    for mid in K["materials"]:
        for f in (s / "src").rglob(f"{mid}*"):
            if f.suffix in (".mp4", ".json") and ".part" not in f.name:
                dst = to / "material" / f.name
                if not dst.exists():
                    shutil.copyfile(f, dst)
    oi = jload(s / "src" / f"{K['origin']}.info.json")
    # 검색·채널 목록 = 원본 1건 + 다른 영상(재료 후보) — 후보가 하나뿐이면 원본 판정이 시험되지 않는다
    found.append({"id": oi["id"], "title": oi.get("title"), "channel": oi.get("channel"), "channel_id": oi.get("channel_id"), "dur": oi.get("duration")})
    titles.append({"id": oi["id"], "title": oi.get("title"), "dur": oi.get("duration")})
    for f in sorted((to / "material").glob("*.info.json")):
        i = jload(f)
        found.append({"id": i["id"], "title": i.get("title"), "channel": i.get("channel"), "channel_id": i.get("channel_id"), "dur": i.get("duration")})
    (to / "search" / "_default.json").write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    (to / "channel" / "_default.json").write_text(json.dumps(titles, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"cache": str(to), "files": sorted(p.relative_to(to).as_posix() for p in to.rglob("*") if p.is_file())}, ensure_ascii=False, indent=1))


def _overlap(a: list, b: list) -> float:
    """원음 구간 겹침 비율(정답 구간 길이 기준)."""
    tot = sum(y - x for x, y in b) or 1
    got = 0.0
    for x, y in a:
        for p, q in b:
            got += max(0.0, min(y, q) - max(x, p))
    return got / tot


def compare(name: str, job: Path) -> int:
    K = KEYS[name]
    st = jload(job / "flow_state.json")
    rows = []

    def row(stage, what, ok, got, want):
        rows.append((stage, what, "○" if ok else "×", str(got)[:120], str(want)[:120]))
    O = st.get("origin") or {}
    row("2 원본", "원본 id", O.get("id") == K["origin"], O.get("id"), K["origin"])
    row("2 원본", "지문 맞은 줄", len(O.get("matched") or []) >= 2, len(O.get("matched") or []), "≥2")
    P = st.get("product") or {}
    if K["coupang"]:
        row("3 제품", "쿠팡 번호", str(P.get("product_id")) == str(K["coupang"]), P.get("product_id"), K["coupang"])
    row("3 제품", "제품 이름", any(w in str(P.get("name") or "") for w in K["product_name"]), P.get("name"), K["product_name"])
    t0 = float(O.get("offset") or 0)
    spans = [[float(s["a"]) + t0, float(s["b"]) + t0] for s in (st.get("research") or {}).get("spans") or []]
    ov = _overlap(spans, K["orig_spans"])
    row("4·6 원음", "원음 구간 겹침(정답 대비)", ov >= 0.5, f"{ov:.0%} {spans}", K["orig_spans"])
    S = (st.get("script") or {}).get("S") or {}
    row("7 대본", "대본 줄 수", bool(S.get("lines")), len(S.get("lines") or []), "있음")
    A = st.get("auto") or {}
    row("11 검사", "자동 검사 6항목", bool(A.get("ok")), json.dumps(A.get("report"), ensure_ascii=False)[:120], "전부 ○")
    L = st.get("look") or {}
    row("11 검사", "눈 검수(회원 Claude)", bool(L.get("ok")), L.get("problems"), "ok")
    row("전체", "완성", st.get("phase") == "done", st.get("phase"), "done")
    ok = all(r[2] == "○" for r in rows)
    md = [f"# 정답지 대조 — {name} ({'합격' if ok else '불합격'})", "", "| 단계 | 항목 | | 회원 경로 | 정답지 |", "|---|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows]
    md += ["", f"반려·재시도: {json.dumps(st.get('tries'), ensure_ascii=False)}", f"기록: {json.dumps(st.get('log'), ensure_ascii=False)[:600]}",
           "", "⚠ 눈 검수 ○ 는 회원 Claude 판정 — 집 PC 세션이 완성본 0초 프레임·1초 시트를 직접 보고 확인해야 '됐다'(0순위-A1)."]
    (job / "answer_key_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cache", "compare"])
    ap.add_argument("name")
    ap.add_argument("--to")
    ap.add_argument("--job")
    a = ap.parse_args()
    if a.cmd == "cache":
        cache(a.name, Path(a.to))
    else:
        sys.exit(compare(a.name, Path(a.job)))


if __name__ == "__main__":
    main()
