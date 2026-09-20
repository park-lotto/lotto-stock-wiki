# -*- coding: utf-8 -*-
"""같은 제품 하나로 여러 판을 뽑아 훅·스토리라인이 얼마나 갈리는지 본다."""
import os, sys, shutil, copy, importlib, json
os.chdir("/home/ubuntu/lotto-stock-wiki"); sys.path.insert(0,"."); sys.path.insert(0,"/tmp")
FS=("product_facts.py","bank_assemble.py","store.py","script_generate.py","script_gate.py")
baks={}
for f in FS:
    o="shopping_shorts/"+f; b="/tmp/bak_"+f; shutil.copy(o,b); baks[o]=b
    shutil.copy("/tmp/new_"+f,o)
try:
    import genius_spine; importlib.reload(genius_spine)
    from genius_spine import GENIUS_SPINE, BEAT_DESCS
    from shopping_shorts.store import Store
    from shopping_shorts import config, product_facts as PF, script_generate as SG, bank_assemble as BA
    _o=BA.beat_descs
    BA.beat_descs=lambda st: BEAT_DESCS if (st or {}).get("name")=="천재의 발명품형" else _o(st)
    st=Store(config.DB_PATH); job=st.get_mix_job("e823c5fef9d7")
    srcs=copy.deepcopy(list((job.get("extract") or {}).values()))
    for s2 in srcs:
        s2["full_text"]=""
        x=s2.get("structure") or {}
        for k in ("hook","development","tone"): x[k]=""
        s2["structure"]=x
    f=PF.expand_by_llm("선풍기 틈새 청소 솔","생활용품","",log=lambda *a:None)
    fb=PF.prompt_block(f)
    out=[]
    for i,seed in enumerate(["v1","v2","v3","v4","v5","v6"]):
        d=SG.generate_one_style(srcs, GENIUS_SPINE, target_seconds=32,
                                facts_block=fb, seed=seed, grounded=False)
        out.append({"seed":seed,"passed":(d or {}).get("passed"),
                    "beats":[{"role":b.get("role",""),"text":b.get("text") or ""}
                             for b in ((d or {}).get("beats") or [])]})
        print("  %s -> %s" % (seed, "PASS" if (d or {}).get("passed") else "FAIL"),
              file=sys.stderr, flush=True)
    print("JSON_START"); print(json.dumps({"peak":f.get("peak"),"runs":out}, ensure_ascii=False))
finally:
    for o,b in baks.items(): shutil.copy(b,o)
