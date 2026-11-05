# -*- coding: utf-8 -*-
"""모션 자산 목록 (관제 331 2단계). 영상이 19GB 라 복사하지 않고 '어디에 무엇이 있나'만 적는다.

    py -X utf8 tools/asset_library/motion_index.py [--lib C:/숏템_자산]

판단 주인 = build() 하나.
- 레퍼런스(X·유튜브에서 받은 원본) / 칼카피 프리셋(presets/*/preset.json) / 작업 결과물 셋으로 나눈다
- 같은 파일은 (크기 + 앞 1MB 지문)으로 하나만 센다
- 레퍼런스마다 '프리셋에 적혀 있나'(칼카피 했나)를 표시 → 아직 안 한 레퍼런스 목록이 나온다
결과: <lib>/모션/목록.json
"""
from __future__ import annotations
import glob, hashlib, json, os, sys
from pathlib import Path

H = Path.home(); M = H / "숏템자료/모션그래픽엔진"
REFS = {"X": [M / "jasonzhu/motion", M / "jasonzhu/production"], "유튜브": [M / "ref_video"]}
V = (".mp4", ".webm", ".mov", ".gif")


def _fp(p: Path) -> str:
    with open(p, "rb") as f:
        return f"{p.stat().st_size}:{hashlib.sha1(f.read(1 << 20)).hexdigest()[:12]}"


def build(lib: Path) -> dict:
    presets = []
    pj_text = {}
    for pj in sorted(glob.glob(str(M / "presets/*/preset.json"))):
        d = json.loads(Path(pj).read_text(encoding="utf-8"))
        pid = Path(pj).parent.name
        pj_text[pid] = Path(pj).read_text(encoding="utf-8")
        presets.append({"id": pid, "name": d.get("name"), "use": d.get("용도"), "ratio": d.get("ratio"),
                        "preview": str(M / "presets" / pid / (d.get("preview") or "sample.mp4").split("/")[-1])})
    fams = json.loads((M / "presets/families.json").read_text(encoding="utf-8")) if (M / "presets/families.json").exists() else {}
    seen, refs = set(), []
    for src, dirs in REFS.items():
        for d in dirs:
            for p in sorted(d.glob("*")):
                if p.suffix.lower() not in V:
                    continue
                h = _fp(p)
                if h in seen:
                    continue
                seen.add(h)
                used = [pid for pid, t in pj_text.items() if p.stem in t]
                refs.append({"id": p.stem, "from": src, "file": str(p), "mb": round(p.stat().st_size / 1e6, 1), "presets": used})
    todo = [r for r in refs if not r["presets"]]
    res = {"presets": len(presets), "families": len(fams), "refs": len(refs), "refs_done": len(refs) - len(todo),
           "refs_todo": len(todo), "preset_list": presets, "family_list": fams, "ref_list": refs,
           "gallery": str(M / "presets/갤러리.html")}
    out = lib / "모션"; out.mkdir(parents=True, exist_ok=True)
    (out / "목록.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    a = sys.argv[1:]
    r = build(Path(a[a.index("--lib") + 1]) if "--lib" in a else Path("C:/숏템_자산"))
    print(f"칼카피 프리셋 {r['presets']}개(묶음 {r['families']}) · 받은 레퍼런스 {r['refs']}개 = 칼카피함 {r['refs_done']} / 아직 {r['refs_todo']}")
