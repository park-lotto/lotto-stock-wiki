# -*- coding: utf-8 -*-
"""고객이 실제로 타는 대본 경로를 **그대로** 돌리고, 모델에 들어간 글자·모델이 돌려준 글자·최종 대본을 전부 남긴다.

왜(2026-09-21 사장님): "시험에선 차이가 크지 않은데 실제 프로그램에서 돌리면 이상한 대본이 나온다."
    시험실(깨끗한 지시문+재료)과 프로그램(틀 조립 → 스타일 생성기 + 은행 + 게이트 재작성 + 후처리) 사이
    어디에서 망가지는지 보려면 프로그램이 **실제로 보내는 프롬프트**를 봐야 한다.

서버에서(별도 프로세스 — 라이브 서비스 프로세스를 안 건드린다. DB는 읽기만, draft 저장 안 함):
    cd /home/ubuntu/lotto-stock-wiki && python3 /home/ubuntu/patchcheck/live_path_capture.py \
        --work 7f7d2393eb0b --styles 70,72 --out /home/ubuntu/patchcheck/cap_7f7d
app.py `/api/wiki/generate`의 스타일 경로(3540~3638줄)를 같은 순서·같은 인자로 부른다:
    _materials_for_generate → (은행 조립) → _assembled_drafts(틀 조립) → generate_by_styles(남은 스타일)
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [os.getcwd()] + [p for p in sys.path if os.path.abspath(p or ".") != _HERE]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--cid", type=int, default=0)
    ap.add_argument("--styles", default="70,72")
    ap.add_argument("--seconds", type=int, default=25)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    from shopping_shorts import app as A, bank_assemble, script_generate as SG
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    store = Store(DB_PATH)

    calls = []
    real = SG._call_json

    def spy(prompt, schema, note=None):
        out = real(prompt, schema, note=note)
        calls.append({"n": len(calls) + 1, "prompt_chars": len(prompt), "prompt": prompt, "response": out})
        return out
    SG._call_json = spy

    work = store.get_produce_work(a.work, customer_id=a.cid)
    if not work:
        sys.exit("work 없음")
    body = {"work_id": a.work, "job_id": str(work.get("job_id") or ""), "target_seconds": a.seconds}
    it = {"structure": {}, "full_text": "", "category": ""}
    ids = [int(x) for x in a.styles.split(",") if x.strip().isdigit()]
    by_id = {s["id"]: s for s in store.list_style_spines()} if hasattr(store, "list_style_spines") else {}
    picked = [by_id[i] for i in ids if i in by_id]
    print("== 고른 스타일:", [(s.get("id"), s.get("name")) for s in picked], "| 못 찾음:", [i for i in ids if i not in by_id])

    src, facts_block, job, jid, scene_block = A._materials_for_generate(it, body, store, a.cid, spines=picked)
    print("== 재료 %d편 · 전사 글자 %s · 사실블록 %d자 · 장면블록 %d자"
          % (len(src or []), [len((s.get("full_text") or "")) for s in (src or [])], len(facts_block or ""), len(scene_block or "")))
    use_bank = (store.get_setting("ping_pong_enabled", "") == "1")
    bank_ctx = ""
    if use_bank:
        sc = sum(len((s.get("full_text") or "")) for s in (src or [])[:A._FACTS_MAX_SOURCES])
        bank_ctx = bank_assemble.assemble_bank_context(store, it.get("category") or "", source_chars=sc) or ""
    grounded = A._script_grounded(store, a.cid)
    print("== 은행 %d자(use_bank=%s) · grounded=%s · assemble_off=%s"
          % (len(bank_ctx), use_bank, grounded, store.get_setting("assemble_off")))

    assembled, left, why = A._assembled_drafts(
        picked, src, store, a.seconds, job_id=jid, topic_product=SG._sources_product(src), facts_block=facts_block,
        topic_semantic_required=any(s.get("topic_product") and s.get("topic_semantic_required", True) for s in (src or [])))
    print("== ①틀 조립: %d편 완성 · 생성기로 넘어간 스타일 %d개 · 사유: %s" % (len(assembled), len(left), str(why)[:120]))
    reasons, styled = [], []
    if left:
        styled = SG.generate_by_styles(src, left, target_seconds=a.seconds, bank_context=bank_ctx,
                                       facts_block=facts_block, reasons=reasons, seed=jid, grounded=grounded)
    print("== ②생성기: %d편 · 반려 사유 %s" % (len(styled), json.dumps(reasons, ensure_ascii=False)[:300]))

    for kind, ds in (("틀조립", assembled), ("생성기", styled)):
        for d in ds:
            print("\n----- 최종 대본 [%s] 스타일=%s passed=%s tries=%s" % (
                kind, d.get("style_name") or d.get("style_id"), d.get("passed"), json.dumps(d.get("tries"), ensure_ascii=False)[:160]))
            print(d.get("script") or "")
            fails = [c.get("name") for c in (d.get("checks") or []) if not c.get("ok")]
            if fails:
                print("   ⚠ 게이트 실패:", fails)
    print("\n== 모델 호출 %d회" % len(calls))
    for c in calls:
        path = os.path.join(a.out, "call_%02d.txt" % c["n"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(c["prompt"] + "\n\n######## 모델 원본 응답 ########\n" + json.dumps(c["response"], ensure_ascii=False, indent=1))
        print("  call %d: 프롬프트 %d자 → %s" % (c["n"], c["prompt_chars"], path))


if __name__ == "__main__":
    main()
