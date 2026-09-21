# -*- coding: utf-8 -*-
"""씨앗 뼈대(A안) 격리 점검 — 라이브를 안 건드리고 **고친 backbone_assemble.py**를 실제 재료로 돌린다.

쓰는 법(서버에서):
    # 1) 트랙에서 고친 파일을 격리 폴더에 올린다(라이브 폴더 아님)
    scp shopping_shorts/backbone_assemble.py ubuntu@<서버>:/home/ubuntu/patchcheck/shopping_shorts/
    scp tools/seed_origin_patchcheck.py      ubuntu@<서버>:/home/ubuntu/patchcheck/
    # 2) 라이브 저장소에서 읽기 전용으로 돌린다(DB는 읽기만, job·work를 새로 만들지 않는다)
    cd /home/ubuntu/lotto-stock-wiki && .venv/bin/python /home/ubuntu/patchcheck/seed_origin_patchcheck.py \
        --work 7f7d2393eb0b [--cid 0] [--live]      # --live = 고치기 전(라이브 파일)으로 돌려 전/후 대조

재는 것(사장님이 09-21 12:40 화면에서 짚은 것 그대로):
    ①말투: 씨앗 존댓말 비율 vs 대본 존댓말 비율      ②칸 수: 씨앗 칸 vs 대본 줄
    ③칸 첫머리(관용구) 몇 칸이 제자리에 살았나        ④6어절 겹침(통째로 베꼈나)   ⑤이름표
"""
import argparse
import importlib.util
import json
import os
import re
import sys

# ★이 스크립트가 놓인 폴더(/home/ubuntu/patchcheck)에도 `shopping_shorts/`가 있어, 그대로 두면
#   라이브 패키지를 가린다(실측: ImportError cannot import name 'app'). 현재 폴더(라이브 저장소)를 맨 앞에.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [os.getcwd()] + [p for p in sys.path if os.path.abspath(p or ".") != _HERE]

PATCH = "/home/ubuntu/patchcheck/shopping_shorts/backbone_assemble.py"


def _load(path):
    spec = importlib.util.spec_from_file_location("ba_patch", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _grams(t, n=6):
    ws = re.sub(r"[^\w가-힣\s]", " ", t or "").split()
    return {" ".join(ws[i:i + n]) for i in range(max(0, len(ws) - n + 1))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--cid", type=int, default=0)
    ap.add_argument("--live", action="store_true", help="고치기 전(라이브) 파일로 돌린다")
    ap.add_argument("--dump-prompt", default="", help="대본 쓰기 호출에 실제로 들어간 프롬프트를 이 파일에 적는다")
    a = ap.parse_args()

    from shopping_shorts import app as live_app
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    store = Store(DB_PATH)
    work = store.get_produce_work(a.work, customer_id=a.cid)
    if not work:
        sys.exit("work 없음: %s (cid=%s)" % (a.work, a.cid))
    jid = str(work.get("job_id") or "").strip()
    job = live_app._enrich_job_extract(store.get_mix_job(jid), store) if jid else None
    if not (job or {}).get("extract"):
        job = dict(job or {}, extract=live_app._extract_from_work(a.work, a.cid, store))
    if not (job or {}).get("extract"):
        sys.exit("재료(extract) 없음")

    if a.live:
        from shopping_shorts import backbone_assemble as ba
    else:
        ba = _load(PATCH)
    srcs = ba.sources_from_extract(job["extract"])
    seed_src = ba.seed_source(srcs, job.get("backbone_main"))
    if not seed_src:
        sys.exit("씨앗 없음")
    if a.dump_prompt:
        # 모델이 **실제로 받는 글자**를 그대로 남긴다 — 같은 입력으로 다른 필자와 대조하려고(2026-09-21).
        _real = ba._sg._call_json

        def _spy(prompt, schema, note=None):
            if "[칸 구조]" in prompt:
                with open(a.dump_prompt, "w", encoding="utf-8") as f:
                    f.write(prompt)
            return _real(prompt, schema, note=note)
        ba._sg._call_json = _spy
    note = {}
    got = ba.assemble_clean(srcs, seed_src.get("video_id"), store,
                            [{"id": None, "name": "씨앗 그대로", "_use_seed_origin": True}],
                            target_seconds=25, seed="patchcheck", want=1, note=note, seed_src=seed_src)
    print("== 파일: %s" % ("라이브(고치기 전)" if a.live else PATCH))
    if not got:
        print("== 통과본 없음 — 반려 사유:", json.dumps(note.get("skipped"), ensure_ascii=False),
              "| 칸나누기:", note.get("seed_origin_failed"), "| detail:", str(note.get("detail"))[:160])
        return
    g = got[0]
    # ★대본을 만든 **그 호출의 칸**과 대조한다 — 따로 나누면 칸 수가 달라 비교가 무효다(09-21 실측 7 vs 6).
    cells = ((g["meta"] or {}).get("note") or {}).get("seed_cells") or []
    print("== 씨앗 %s · 칸 %d" % (seed_src.get("video_id"), len(cells)))
    for i, c in enumerate(cells, 1):
        print("  씨앗%d [%s] %s%s" % (i, c.get("role"), c.get("text"),
                                     ("  ⟵고정: " + " / ".join(c["fixed"])) if c.get("fixed") else ""))
    lines = [t for t in (g["given"] or "").split("\n") if t.strip()]
    print("== 대본 %d줄 · 이름표: %s" % (len(lines), ((g["meta"] or {}).get("spine") or {}).get("name")))
    for i, t in enumerate(lines, 1):
        print("  대본%d %s" % (i, t))
    pol = re.compile(r"(요|니다|니까|세요|시오|죠)[\s.!?~…]*$")
    pr = lambda ts: sum(1 for t in ts if pol.search(t.strip())) / max(1, len(ts))   # noqa: E731
    op = lambda t: re.sub(r"[^\w가-힣]", "", (t.strip().split() or [""])[0])          # noqa: E731
    kept = sum(1 for c, t in zip(cells, lines) if op(c["text"]) and op(c["text"]) == op(t))
    sg, lg = _grams(seed_src.get("full_text")), _grams("\n".join(lines))
    print("== 측정")
    print("  ①존댓말 비율  씨앗 %.2f → 대본 %.2f" % (pr([c["text"] for c in cells]), pr(lines)))
    print("  ②칸 수        씨앗 %d → 대본 %d" % (len(cells), len(lines)))
    print("  ③칸 첫머리    %d/%d 칸이 씨앗 그대로" % (kept, len(cells)))
    # ★관용구는 대본을 만든 그 호출의 칸(note)이 아니라 여기서 따로 나눈 칸 기준이다 — 두 호출이 칸을
    #   다르게 나눌 수 있으므로 **칸 위치는 안 보고 대본 전체에 그 말이 있나**만 센다.
    nsp = lambda s: re.sub(r"\s+", "", s or "")                                       # noqa: E731
    fx = [f for c in cells for f in (c.get("fixed") or [])]
    alive = [f for f in fx if nsp(f) in nsp("".join(lines))]
    print("  ③'관용구      %d/%d 살아 있음  빠진 것: %s" % (len(alive), len(fx), [f for f in fx if f not in alive] or "없음"))
    print("  ④6어절 겹침   %.1f%%" % (100.0 * len(sg & lg) / max(1, len(lg))))
    print("  ⑤1인칭 사연   %s" % ([t for t in lines if re.search(r"(^|\s)(저도|저는|제가|아내|남편)\b", t)] or "없음"))


if __name__ == "__main__":
    main()
