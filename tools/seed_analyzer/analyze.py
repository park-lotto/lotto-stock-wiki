# -*- coding: utf-8 -*-
"""씨앗 영상 1편 → 구조 분석 (2026-09-22 사장님 "씨앗 분석기를 해봐").

★왜 필요한가: 지금은 씨앗 **전사 원문을 통째로** 프롬프트에 던진다
  (`simple_writer/harness.py`: "[씨앗]\n%s" % seed_text). 그래서 모델이 매번 스스로
  흐름·말버릇·화자·고조 자리를 추론해야 하고, 전사에 섞인 오탈자·잘림까지 같이 읽는다.
  노바 작가(현시점 썰쇼핑 1위)는 **1단계가 씨앗 분석**이다 — 대본 추출 + "사람들이 홀린 요인"을
  먼저 뽑고, 그 결과를 작가 프롬프트에 넣는다(2026-09-22 영상 정독).

★씨앗은 작업당 1편이라 **분석은 1회**다. 캐시해 두면 대본을 몇 편 뽑든 추가 비용이 없다.

쓰기(서버에서, env 필요):
  python3 tools/seed_analyzer/analyze.py --works <작업ID,…>          # 라이브 씨앗으로
  python3 tools/seed_analyzer/analyze.py --text "<대본 원문>"        # 손으로 넣어 시험
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

SCHEMA = {
    "type": "object",
    "properties": {
        "speaker": {"type": "string"},                    # 화자
        "tone": {"type": "string", "enum": ["존댓말", "반말"]},
        "endings": {"type": "array", "items": {"type": "string"}},   # 실제 쓰인 어미
        "beats": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},                   # 칸 이름(이 대본에 맞는 말로)
            "does": {"type": "string"},                   # 그 칸이 하는 일
            "text": {"type": "string"},                   # 그 칸의 원문(뜻이 통하게 고쳐 적은 것)
        }, "required": ["name", "does", "text"]}},
        "openers": {"type": "array", "items": {"type": "string"}},   # 칸 여는 말버릇(없으면 빈 목록)
        "hooked_why": {"type": "string"},                 # 홀린 요인
        "product": {"type": "string"},
        "benefits": {"type": "array", "items": {"type": "string"}},  # 대본이 실제로 말한 장점만
        "escalation": {"type": "array", "items": {"type": "object", "properties": {
            "at": {"type": "string"}, "by": {"type": "string"},
        }, "required": ["at", "by"]}},
    },
    "required": ["speaker", "tone", "endings", "beats", "openers",
                 "hooked_why", "product", "benefits", "escalation"],
}


def analyze(seed_text, note=None):
    """씨앗 전사 → 구조. 실패하면 None(호출부가 옛 경로로 간다)."""
    from shopping_shorts import script_generate as _sg
    brief = open(os.path.join(HERE, "seed_brief.txt"), encoding="utf-8").read().strip()
    prompt = "%s\n\n[전사]\n%s" % (brief, (seed_text or "").strip())
    out = _sg._call_json(prompt, SCHEMA, note=note)
    return out or None


def _live_seeds(work_ids, cid=0):
    """라이브 작업에서 씨앗 전사를 읽어온다(읽기 전용)."""
    from shopping_shorts.store import Store
    from shopping_shorts import backbone_assemble as ba
    from shopping_shorts import app as A
    store = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    out = []
    for wid in work_ids:
        work = store.get_produce_work(wid, cid) or {}
        jid = str(work.get("job_id") or "").strip()
        job = A._enrich_job_extract(store.get_mix_job(jid), store) if jid else None
        if not (job or {}).get("extract"):
            job = dict(job or {}, extract=A._extract_from_work(wid, cid, store))
        srcs = ba.sources_from_extract((job or {}).get("extract") or {})
        seed = ba.seed_source(srcs, (job or {}).get("backbone_main"))
        out.append({"work_id": wid,
                    "seed_vid": (seed or {}).get("video_id"),
                    "text": ((seed or {}).get("full_text") or "").strip()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--cid", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    seeds = []
    if a.text:
        seeds = [{"work_id": "(직접입력)", "seed_vid": "", "text": a.text}]
    elif a.works:
        seeds = _live_seeds([x.strip() for x in a.works.split(",") if x.strip()], a.cid)
    else:
        raise SystemExit("--works 또는 --text 중 하나는 있어야 한다")

    rows = []
    for s in seeds:
        if len(s["text"]) < 60:
            rows.append(dict(s, error="전사가 너무 짧다(%d자)" % len(s["text"])))
            print("  %s 건너뜀 — 전사 %d자" % (s["work_id"], len(s["text"])), flush=True)
            continue
        note = {}
        res = analyze(s["text"], note=note)
        rows.append(dict(s, result=res, note=note))
        if res:
            print("  %s  %s/%s · 칸 %d · 말버릇 %d · 장점 %d · 고조 %d"
                  % (s["work_id"], res.get("speaker", "")[:10], res.get("tone", ""),
                     len(res.get("beats") or []), len(res.get("openers") or []),
                     len(res.get("benefits") or []), len(res.get("escalation") or [])), flush=True)
        else:
            print("  %s  분석 실패" % s["work_id"], flush=True)
    if a.out:
        json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("저장: %s" % a.out)
    else:
        sys.stdout.write("@@JSON@@" + json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
