# -*- coding: utf-8 -*-
"""태깅에서 **불편(pain)**을 뽑는다 — 고조의 재료 (2026-09-22).

★왜 필요한가: 지금 특징 분석(`build_groups`)은 기능(claim)만 뽑는다. 기능만 나열하면
  "빗 뒷면에 앰플을 채운다"처럼 심심해진다. 불편이 짝으로 있어야
  "손에 다 묻고 머리만 떡지던 걸 없앴다"가 된다 — 고조의 재료는 기능이 아니라 **불편-해결 짝**이다.
  시험대에서는 내가 손으로 pain을 써 넣어 좋은 대본이 나왔다. 그건 **내가 정답을 흘려준 것**이라
  라이브에서 같은 품질이 난다는 보장이 없었다(메모리: 지어낸소재_지어낸결론).

★재료는 이미 태깅 안에 있다(라이브 실측 2026-09-22, 최근 57 job·3,880 세그):
  - `shot_role="문제"` 132개 · `"before"` 339개
  - **57 job 중 43개(75%)**에 문제/before 세그가 있다
  - `use_point`가 불편을 말로 적어 둔다:
      "화분 관리의 어려움을 언급하며 공감을 이끌어내는 영상 도입부"
      "충전 케이블이 엉키는 불편함을 시각적으로 보여주어 제품 필요성을 강조할 때"
  즉 **뽑는 사람이 없었을 뿐**이다.

쓰기(서버, env 필요):
  python3 tools/seed_analyzer/pain_extract.py --job 13d4cab55fba
  python3 tools/seed_analyzer/pain_extract.py --job <id> --raw   # 모델 없이 태깅만 모아 보기
"""
import argparse
import json
import re
import sys

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

# ★정의는 shopping_shorts/story_writer.py 한 곳(0순위-B) — 여기서는 가져다 쓴다.
from shopping_shorts.story_writer import (PROBLEM_ROLES, source_block as _source_block,  # noqa: E402
                                          extract_feats)


def _sources(extract):
    from shopping_shorts import backbone_assemble as ba
    return ba.sources_from_extract(extract or {})


def source_block(extract):
    return _source_block(_sources(extract))


def extract_pain(extract, product="", note=None):
    return extract_feats(_sources(extract), product, note=note)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--raw", action="store_true", help="모델 없이 태깅만 모아 본다")
    a = ap.parse_args()
    from shopping_shorts.store import Store
    from shopping_shorts import app as A
    store = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    job = A._enrich_job_extract(store.get_mix_job(a.job), store) or {}
    ext = job.get("extract") or {}
    n = sum(len(v.get("segments") or []) for v in ext.values() if isinstance(v, dict))
    nprob = sum(1 for v in ext.values() if isinstance(v, dict)
                for x in (v.get("segments") or [])
                if (x.get("shot_role") or "") in PROBLEM_ROLES)
    print("job %s · 소스 %d · 세그 %d (문제/before %d)" % (a.job, len(ext), n, nprob))
    if a.raw:
        print(source_block(ext)[:3000])
        return
    feats = extract_pain(ext, (job.get("product") or ""))
    print("뽑은 특징 %d개\n" % len(feats))
    for f in feats:
        print("  ■ %s — %s" % (f.get("name"), f.get("claim")))
        print("     pain: %s" % (f.get("pain") or "(빈칸)"))
        print("     근거: %s" % ", ".join(f.get("from_cuts") or [])[:80])
        print()


if __name__ == "__main__":
    main()
