# -*- coding: utf-8 -*-
"""갈래 묶기 — 판독이 자유롭게 붙인 갈래 이름을 정해진 갈래 몇 개로 합친다(사람 확정 전 1차 묶음).

    PYTHONUTF8=1 py tools/calcopy/group_styles.py channel/sseolpulda

규칙(위에서부터 먼저 걸리는 것): 화자 2명↑ → 역할극형 / 나레 없음·'시연' → 시연형 /
'스토리' → 스토리텔링형 / 정보·꿀팁·직업·장소·랭킹 → 정보 전달형 / 그 밖 → 제품 이야기썰형.
출력: <폴더>/갈래.json — 갈래마다 편 id·조회 중앙·판독 원래 이름 목록(왜 거기 들어갔는지 보이게).
"""
import collections, json, statistics, sys
from pathlib import Path

ORDER = ["제품 이야기썰형", "정보 전달형", "스토리텔링형", "역할극형", "시연형"]


def group_of(r: dict) -> str:
    s = r.get("style") or ""
    roles = [x for x in (r.get("roles") or []) if x]
    if len(roles) > 1:
        return "역할극형"
    if r.get("voice") == "없음" or "시연" in s:
        return "시연형"
    if "스토리" in s:
        return "스토리텔링형"
    if any(k in s for k in ("정보", "꿀팁", "직업", "장소", "랭킹")):
        return "정보 전달형"
    return "제품 이야기썰형"


def main(folder: str):
    d = Path(folder)
    rows = json.loads((d / "1차분석_편별.json").read_text(encoding="utf-8"))
    g = collections.defaultdict(list)
    for r in rows:
        g[group_of(r)].append(r)
    out = []
    for name in ORDER:
        rs = g.get(name, [])
        if not rs:
            continue
        out.append({"name": name, "confirmed": False, "n": len(rs),
                    "views_median": int(statistics.median(r["views"] for r in rs)),
                    "views_max": max(r["views"] for r in rs),
                    "from_labels": collections.Counter(r.get("style") for r in rs).most_common(),
                    "ids": [r["id"] for r in sorted(rs, key=lambda r: -r["views"])]})
    (d / "갈래.json").write_text(json.dumps({"rule": __doc__.split("규칙")[1].split("출력")[0].strip(), "styles": out},
                                          ensure_ascii=False, indent=1), encoding="utf-8")
    for s in out:
        print(f"{s['n']:>2}편 중앙 {s['views_median']:>9,}  {s['name']}")


if __name__ == "__main__":
    main(sys.argv[1])
