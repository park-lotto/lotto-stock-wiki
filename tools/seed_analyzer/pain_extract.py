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

# 불편을 말하는 세그의 표식 — 태깅이 이미 갖고 있는 것들
PROBLEM_ROLES = {"문제", "before"}
PROBLEM_WORDS = re.compile(r"불편|어려움|번거|귀찮|지저분|엉키|엉망|힘들|고생|낭비|"
                           r"문제|손상|망가|샌다|흘러|끈적|답답|공감")

SCHEMA = {
    "type": "object",
    "properties": {"feats": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"},        # 특징 이름
        "claim": {"type": "string"},       # 이 제품이 하는 일
        "pain": {"type": "string"},        # ★이게 없을 때 뭐가 괴로운가(장면으로)
        "from_cuts": {"type": "array", "items": {"type": "string"}},  # 근거 컷 번호
    }, "required": ["name", "claim", "pain", "from_cuts"]}}},
    "required": ["feats"],
}

BRIEF = """아래는 같은 제품을 찍은 영상들의 장면 태깅이다.
이 제품의 특징을 **3~4개**만 뽑아라. 제일 센 것만 남기고 약한 건 버려라.

특징마다 세 가지를 적는다:
  name   짧은 이름
  claim  이 제품이 실제로 하는 일 (화면에 보이는 것만)
  pain   ★**이게 없을 때 뭐가 괴로운가** — 기능을 뒤집어 쓰지 말고, 그 사람이 겪던 장면으로 적어라
         X 고정이 안 된다                     (기능을 뒤집은 말 — 쓸모없다)
         O 조금만 건드려도 쓰러지고 굴러다녀서 매번 다시 세워야 했다
  from_cuts  근거로 삼은 컷 번호들

pain을 적는 법:
- 태깅에 **[문제]·[before] 컷**이 있으면 먼저 거기서 가져와라. 제작자가 찍어 둔 불편이다.
- `용처` 설명에 "~의 어려움", "~하는 불편함"처럼 적혀 있으면 그대로 쓴다.
- ★화면에 그 장면이 없어도 된다(2026-09-22 사장님). 카메라는 제품이 **잘 되는 모습**을 찍지
  불편한 장면은 거의 안 찍는다(실측: 문제 컷이 3,880개 중 132개=3.4%).
  그러니 **그 제품을 쓰는 사람이라면 누구나 겪을 법한 불편**을 구체적인 장면으로 적어라.
    O 조금만 건드려도 쓰러지고 굴러다녀서 매번 다시 세워야 했다
    O 테이프로 붙이면 나중에 누렇게 떠서 떼어낼 때 자국이 남는다
- 기능을 뒤집어 쓰지 마라. 그건 쓸모없다.
    X 고정이 안 된다  /  X 도포가 균일하지 않다

★claim(이 제품이 하는 일)은 화면에 보이는 것만 쓴다. pain은 화면 밖에서 와도 된다."""


def source_block(extract):
    """태깅을 모델이 읽을 형태로. 문제/before 컷을 앞에 모아 눈에 띄게 한다."""
    prob, normal = [], []
    for vid, v in sorted((extract or {}).items()):
        for x in (v.get("segments") or []) if isinstance(v, dict) else []:
            role = x.get("shot_role") or ""
            up = (x.get("use_point") or "")
            line = "  [%s] %s | 화면:%s%s%s%s" % (
                x.get("seg_id"), role, (x.get("scene_desc") or "")[:70],
                (" | 변화:%s" % (x.get("change") or "")[:40]) if x.get("change") else "",
                (" | 용처:%s" % up[:70]) if up else "",
                (" | 특징:%s" % " / ".join(str(b) for b in (x.get("product_benefits") or [])[:2]))
                if x.get("product_benefits") else "")
            if role in PROBLEM_ROLES or PROBLEM_WORDS.search(up):
                prob.append(line)
            else:
                normal.append(line)
    out = []
    if prob:
        out.append("[불편을 보여주는 컷 — pain은 여기서 가져와라]")
        out += prob[:20]
        out.append("")
    out.append("[나머지 컷]")
    out += normal[:60]
    return "\n".join(out)


def extract_pain(extract, product="", note=None):
    from shopping_shorts import script_generate as _sg
    prompt = "%s\n\n[제품] %s\n\n%s" % (BRIEF, product or "(미상)", source_block(extract))
    return (_sg._call_json(prompt, SCHEMA, note=note) or {}).get("feats") or []


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
