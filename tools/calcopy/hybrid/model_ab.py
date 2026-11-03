"""같은 질문을 다른 모델에 다시 물어 답 대조(사장님 10-27 '소넷으로 돌리나 오푸스로 돌리나 같은지').

    py tools/calcopy/hybrid/model_ab.py --model sonnet <reviews 폴더 glob…>    예) C:/숏템_칼카피/ititemlog/of_only*/job/reviews/*of_judge*

flow_dev 가 남긴 reviews/<id>/ask.txt(그림 경로 포함)를 그대로 그 모델에 묻고 answer.json(원래 모델 답)과 'same' 칸 겹침·시간을 찍는다.
새 답은 같은 폴더 answer_<model>.json 에 남긴다(다시 돌리면 그 답을 쓴다)."""
from __future__ import annotations

import argparse
import glob
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CLAUDE = shutil.which("claude") or "claude"


def ask(d: Path, model: str) -> tuple[dict, float]:
    out = d / f"answer_{model}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8")), -1
    t0 = time.time()
    r = subprocess.run([CLAUDE, "-p", "--model", model, "--allowedTools", "Read,Glob,Grep", "--add-dir", str(d.parents[1]), "--output-format", "json",
                        "--max-turns", "30", "--settings", '{"disableAllHooks": true}'],
                       input=(d / "ask.txt").read_text(encoding="utf-8"), capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(d), timeout=1800)
    try:
        txt = json.loads(r.stdout).get("result") or ""
    except ValueError:
        txt = r.stdout
    s, e = txt.find("{"), txt.rfind("}")
    try:
        a = json.loads(txt[s:e + 1])
    except ValueError:
        a = {"_raw": txt[:500]}
    out.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return a, time.time() - t0


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--par", type=int, default=4)
    ap.add_argument("dirs", nargs="+")
    a = ap.parse_args(argv)
    ds = [Path(p) for g in a.dirs for p in sorted(glob.glob(g)) if (Path(p) / "ask.txt").exists() and (Path(p) / "answer.json").exists()]
    with ThreadPoolExecutor(a.par) as ex:
        res = list(ex.map(lambda d: ask(d, a.model), ds))
    agree = 0
    for d, (b, sec) in zip(ds, res):
        o = json.loads((d / "answer.json").read_text(encoding="utf-8"))
        so, sb = set(o.get("same") or []), set(b.get("same") or [])
        same_empty = (not so) == (not sb)
        agree += same_empty
        print(f"■ {d.parents[2].name}/{d.name}  {a.model} {sec:.0f}초")
        print(f"   오푸스 same {sorted(so)} / {a.model} same {sorted(sb)} · 겹침 {sorted(so & sb)} · 찾음/못찾음 일치 {same_empty}")
        print(f"   {a.model} 이유: {str(b.get('why') or b.get('_raw') or '')[:200]}")
    print(f"\n{len(ds)}개 중 찾음/못찾음 판단 일치 {agree}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
