# -*- coding: utf-8 -*-
"""D8(흰 바탕 위 그림만 바뀌는 컷 누락) 8편 전/후 — 옛(바탕 빼기 없음) vs 새(bench.cuts) (관제 097, 2026-10-16).
창·배경 = channel/<채널>/뜯기/<id>/뜯기.json layout(window·bg_rgb). 정답은 각 편 점검.md(사람 눈, 1초 시트)의 컷 줄.
    PYTHONUTF8=1 py channel/yummyknow/컷검출_재측정/d8_check.py → 같은 폴더 D8.json · D8.md
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from shopping_shorts.channelkit.bench import cuts, probe  # noqa: E402

V = [("banggu", i) for i in ("48PbLQ5az6k", "8iEhEniPpjE", "ayNy6CSSrIQ", "Kz8KlJoQ1Vc")] + \
    [("yummyknow", i) for i in ("76uZKOpnlqQ", "Mqhm5IH06NM", "p8IDs2HdfvY", "rGFXQlS9Cp4")]


def longest(c, dur):
    s = cuts.shot_lengths(c, dur)
    i = max(range(len(s)), key=lambda j: s[j])
    a = ([0.0] + c)[i]
    return f"{round(s[i], 2)}({round(a, 2)}~{round(a + s[i], 2)})"


def main():
    out, L = [], ["| 채널 | 영상 | 샷 옛→새 | 컷 중앙 옛→새 | 가장 긴 샷 옛 → 새 | 새로 잡힘 | 빠짐 | 이동으로 뺌 |", "|---|---|---|---|---|---|---|---|"]
    for ch, vid in V:
        lay = json.loads((ROOT / f"channel/{ch}/뜯기/{vid}/뜯기.json").read_text(encoding="utf-8"))["layout"]
        path = f"C:/숏템_칼카피/{ch}/mp4/{vid}.mp4"
        meta = probe.info(path)
        o = cuts.measure_video(path, {"window": lay["window"]}, meta, [], zoom=False)
        n = cuts.measure_video(path, {"window": lay["window"], "bg_rgb": lay["bg_rgb"]}, meta, [], zoom=False)
        add = [t for t in n["cuts"] if not any(abs(t - x) < 0.05 for x in o["cuts"])]
        rem = [t for t in o["cuts"] if not any(abs(t - x) < 0.05 for x in n["cuts"])]
        d = meta["duration"]
        r = {"ch": ch, "vid": vid, "window": lay["window"], "bg": lay["bg_rgb"], "old": o["cuts"], "new": n["cuts"],
             "old_shots": o["shots"], "new_shots": n["shots"], "old_med": o["shot_median"], "new_med": n["shot_median"],
             "old_long": longest(o["cuts"], d), "new_long": longest(n["cuts"], d), "added": add, "removed": rem, "moved": n["moved"]}
        out.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        L.append(f"| {ch} | {vid} | {r['old_shots']}→{r['new_shots']} | {r['old_med']}→{r['new_med']} | {r['old_long']} → {r['new_long']} | "
                 f"{len(add)} | {', '.join(map(str, rem)) or '-'} | {', '.join(str(m[0]) for m in r['moved']) or '-'} |")
    here = Path(__file__).parent
    (here / "D8.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (here / "D8.md").write_text("# D8 전/후 — 흰 바탕 위 그림만 바뀌는 컷\n\n" + "\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
