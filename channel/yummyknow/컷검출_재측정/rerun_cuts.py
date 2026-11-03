# -*- coding: utf-8 -*-
"""통과작·원본의 컷을 옛 방식(바탕 빼기 없음) vs 새 방식(bench.cuts 바탕 빼기)으로 다시 잰다 (관제 097, 2026-10-16).
창·배경은 각 편 대조/차이표.md 의 ① '영상 창'·'배경 RGB' 행(compare 가 layout1 로 잰 값)을 그대로 쓴다 — layout 재측정 안 함.
새로 생긴 컷마다 프레임 차 급등(그 프레임 차 / 앞뒤 4프레임 차 중앙값)을 같이 적어 진짜 하드 컷인지 본다.
    PYTHONUTF8=1 py channel/yummyknow/컷검출_재측정/rerun_cuts.py  → 같은 폴더 결과.json · 결과.md
    … --only "썰풀다 ZdeZ"  → 그 편만 다시 재서 결과.json·결과.md 갱신
"""
import json, re, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from shopping_shorts.channelkit.bench import cuts, probe  # noqa: E402

R = "C:/숏템_칼카피/"
# (이름, 영상, 창·배경을 읽을 차이표, 열: 0=원본 1=우리)
V = [("원본 yummyknow rGFX", R + "yummyknow/mp4/rGFXQlS9Cp4.mp4", "channel/yummyknow/칼카피_rGFX/대조/차이표.md", 0),
     ("원본 방구석 ILIi", R + "banggu/mp4/ILIiqCJAOSI.mp4", "channel/banggu/칼카피_ILIi/대조/차이표.md", 0),
     ("원본 핫템 OE11", R + "hottemreport/mp4/OE-11wb7vdY.mp4", "channel/hottemreport/칼카피_OE11/대조/차이표.md", 0),
     ("원본 썰풀다 ZdeZ", R + "sseolpulda/mp4/ZdeZRtCeAC4.mp4", "channel/sseolpulda/칼카피_ZdeZ/대조/차이표.md", 0),
     ("원본 썰풀다 mY", R + "sseolpulda/mp4/mYxuF1A74j4.mp4", "channel/sseolpulda/칼카피_mY/대조/차이표.md", 0),
     ("썰풀다 ZdeZ", R + "sseolpulda/칼카피_ZdeZ/render/final.mp4", "channel/sseolpulda/칼카피_ZdeZ/대조/차이표.md", 1),
     ("썰풀다 LED 수도꼭지", R + "sseolpulda/새소재_ledfaucet/render/final.mp4", "channel/sseolpulda/새소재_ledfaucet/render/차이표.md", 1),
     ("썰풀다 하키 퍽(mY)", R + "sseolpulda/칼카피_mY/make/final.mp4", "channel/sseolpulda/칼카피_mY/대조/차이표.md", 1),
     ("썰풀다 4호 포수", R + "sseolpulda/칼카피_4호/make/final_bed.mp4", "channel/sseolpulda/칼카피_4호/대조/차이표.md", 1),
     ("yummyknow rGFX 4판-b", R + "yummyknow/칼카피_rGFX/render/final.mp4", "channel/yummyknow/칼카피_rGFX/대조/차이표.md", 1),
     ("yummyknow 신라면", R + "yummyknow/새소재_shinramyun_gumi/render/final.mp4", "channel/yummyknow/새소재_shinramyun_gumi/대조/차이표.md", 1),
     ("yummyknow 리센느 빵", R + "yummyknow/새소재_rescene_bread/render/final.mp4", "channel/yummyknow/새소재_rescene_bread/대조/차이표.md", 1),
     ("방구석 아웃백(ILIi)", R + "banggu/칼카피_ILIi/render2/final.mp4", "channel/banggu/칼카피_ILIi/대조/차이표.md", 1),
     ("방구석 바나나우유", R + "banggu/칼카피_banana/render2/final.mp4", "channel/banggu/칼카피_banana/대조/차이표.md", 1),
     ("핫템 아이언맨(OE11)", R + "hottemreport/칼카피_OE11/make/final_src.mp4", "channel/hottemreport/칼카피_OE11/대조/차이표.md", 1)]


def row(md: str, label: str, col: int):
    for line in md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) > 4 and cells[1] == label:
            return json.loads(cells[2 + col])
    raise ValueError(f"차이표에 '{label}' 행 없음")


def p90(c, dur):
    return round(float(np.percentile(cuts.shot_lengths(c, dur), 90)), 2)


def one(name, path, table, col):
    md = (ROOT / table).read_text(encoding="utf-8")
    win, bg = row(md, "영상 창 [x,y,w,h]", col), row(md, "배경 RGB", col)
    meta = probe.info(path)
    old = cuts.measure_video(path, {"window": win}, meta, [], zoom=False)
    new = cuts.measure_video(path, {"window": win, "bg_rgb": bg}, meta, [], zoom=False)
    add = [t for t in new["cuts"] if not any(abs(t - o) < 0.05 for o in old["cuts"])]
    rem = [t for t in old["cuts"] if not any(abs(t - o) < 0.05 for o in new["cuts"])]
    spikes = {}
    if add:
        x, y, w, h = win
        fr = [g.astype(np.float32) for g in probe.frames(path, f"crop={w}:{h}:{x}:{y},scale=64:64", 64, 64, "gray")]
        d = [0.0] + [float(np.abs(fr[i] - fr[i - 1]).mean()) for i in range(1, len(fr))]
        for t in add:
            k = int(round(t * meta["fps"]))
            nb = [d[j] for j in range(max(1, k - 4), min(len(d), k + 5)) if j != k]
            spikes[str(t)] = [round(d[k], 1), round(float(np.median(nb)), 1)]
    dur = meta["duration"]
    return {"name": name, "path": path, "window": win, "bg": bg,
            "old": {"shots": old["shots"], "median": old["shot_median"], "p90": p90(old["cuts"], dur), "cuts": old["cuts"]},
            "new": {"shots": new["shots"], "median": new["shot_median"], "p90": p90(new["cuts"], dur), "cuts": new["cuts"]},
            "added": add, "removed": rem, "spike_added": spikes}


def main():
    out, here = [], Path(__file__).parent
    for v in V:
        try:
            r = one(*v)
        except Exception as e:  # noqa: BLE001 — 편 하나 실패는 표에 남기고 다음 편
            r = {"name": v[0], "path": v[1], "error": f"{type(e).__name__}: {e}"}
        out.append(r)
        print(json.dumps({k: r.get(k) for k in ("name", "old", "new", "added", "removed", "spike_added", "error") if k in r},
                         ensure_ascii=False), flush=True)
    (here / "결과.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    write_md(out, here)


def write_md(out, here):
    L = ["| 편 | 샷 옛→새 | 컷 중앙 옛→새(초) | p90 옛→새(초) | 새로 잡힘(프레임 차 / 이웃 중앙) | 빠짐 |", "|---|---|---|---|---|---|"]
    for r in out:
        if "error" in r:
            L.append(f"| {r['name']} | 오류 {r['error']} | | | | |"); continue
        o, n = r["old"], r["new"]
        L.append(f"| {r['name']} | {o['shots']}→{n['shots']} | {o['median']}→{n['median']} | {o['p90']}→{n['p90']} | "
                 + (", ".join(f"{t}({r['spike_added'][str(t)][0]}/{r['spike_added'][str(t)][1]})" for t in r["added"]) or "-")
                 + f" | {', '.join(map(str, r['removed'])) or '-'} |")
    (here / "결과.md").write_text("# 컷 검출 재측정 — 옛(바탕 빼기 없음) vs 새(bench.cuts 바탕 빼기)\n\n" + "\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--only":
        here = Path(__file__).parent
        out = json.loads((here / "결과.json").read_text(encoding="utf-8"))
        names = set(sys.argv[2:])
        out = [one(*[v for v in V if v[0] == r["name"]][0]) if r["name"] in names else r for r in out]
        (here / "결과.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        write_md(out, here)
    else:
        main()
