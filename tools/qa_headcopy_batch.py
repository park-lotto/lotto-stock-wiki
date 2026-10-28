# -*- coding: utf-8 -*-
"""실제 대본 여러 편으로 **자동 제목·소제목**을 뽑아 계약(길이·줄수)을 지키는지 전수로 잰다.

왜(2026-09-22 사장님): "실제 대본 뽑히는 걸로 테스트를 여러 번 해야 된다 / 제목과 자막 들어가는 거."
한 편만 보고 "된다"고 하면 길이 초과·줄 안 나눔 같은 결함이 다음 편에서 터진다.

재는 것(편마다):
  ① 후보가 4개 나왔나          ② text가 정확히 두 줄인가
  ③ 각 줄이 계약 길이 안인가    ④ subline이 있고 계약 길이 안인가
  ⑤ split_hook을 거친 뒤에도 두 줄이 유지되나(편집기가 실제로 쓰는 경로)

실행: py tools/qa_headcopy_batch.py <대본json>  [--family youtube_reveal] [--limit 6]
      대본json = ["대본 전문", ...] 또는 [{"job":…, "script":…}, …]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shopping_shorts import headcopy_gen                       # noqa: E402
from shopping_shorts.template_copy import EVEN_SHOPPING, split_hook   # noqa: E402


def check_one(script: str, family: str) -> dict:
    copies = headcopy_gen.suggest(script, family=family)
    result = {"후보수": len(copies), "실패": [], "첫후보": None}
    if not copies:
        result["실패"].append("후보를 못 뽑았다(AI 실패)")
        return result
    first = copies[0]
    text = (first.get("text") or "").strip()
    subline = (first.get("subline") or "").strip()
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    result["첫후보"] = {"text": text.replace("\n", " / "), "subline": subline}

    if len(lines) != 2:
        result["실패"].append(f"제목이 두 줄이 아니다({len(lines)}줄)")
    else:
        if len(lines[0]) > EVEN_SHOPPING.hook_line_max:
            result["실패"].append(f"첫 줄 {len(lines[0])}자 > 계약 {EVEN_SHOPPING.hook_line_max}")
        if len(lines[1]) > EVEN_SHOPPING.hook2_line_max:
            result["실패"].append(f"둘째 줄 {len(lines[1])}자 > 계약 {EVEN_SHOPPING.hook2_line_max}")
    if not subline:
        result["실패"].append("소제목(subline)이 비었다")
    elif len(subline) > EVEN_SHOPPING.support_max:
        result["실패"].append(f"소제목 {len(subline)}자 > 계약 {EVEN_SHOPPING.support_max}")

    # 편집기가 실제로 쓰는 경로 — 두 줄이 그대로 살아야 한다.
    h1, h2 = split_hook(text)
    result["편집기표시"] = f"{h1} / {h2}"
    if not h2:
        result["실패"].append("split_hook을 거치니 둘째 줄이 사라진다")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", help="대본 JSON 배열 파일")
    ap.add_argument("--family", default="youtube_reveal",
                    help="화법 계열(기본 youtube_reveal = 이븐쇼핑류 후킹 제목)")
    ap.add_argument("--limit", type=int, default=6)
    args = ap.parse_args()

    raw = json.loads(Path(args.scripts).read_text(encoding="utf-8"))
    items = []
    for row in raw[: args.limit]:
        if isinstance(row, str):
            items.append(("", row))
        else:
            items.append((row.get("job", ""), row.get("script", "")))

    bad_total = 0
    for job, script in items:
        if not script.strip():
            continue
        head = (script.strip().splitlines() or [""])[0][:26]
        print(f"── [{job or '?'}] {head}…")
        r = check_one(script, args.family)
        if r["첫후보"]:
            print(f"   제목  : {r['첫후보']['text']}")
            print(f"   소제목: {r['첫후보']['subline']}  ({len(r['첫후보']['subline'])}자)")
            print(f"   편집기: {r.get('편집기표시','')}")
        if r["실패"]:
            bad_total += 1
            for f in r["실패"]:
                print(f"   ✗ {f}")
        else:
            print("   ✓ 계약 통과")
        print()

    print(f"편수 {len(items)} / 결함 있는 편 {bad_total}")
    sys.exit(0 if bad_total == 0 else 1)


if __name__ == "__main__":
    main()
