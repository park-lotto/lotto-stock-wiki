# -*- coding: utf-8 -*-
"""LOO 시연(렌더·TTS 없음) — 원본 1편을 숨기고 상품 사실만 주고 설명서+가까운 예문 3편으로 대본 초안 생성, 원본과 나란히.
같은 상품을 핫템리포트 설명서(script_engine.ROLES['hottemreport'] 7칸)로도 생성해 고른 사실·사슬이 다른지 대조.

    PYTHONUTF8=1 py channel/homedesignnote/대본설명서/loo_demo.py --chan C:/숏템_칼카피/homedesignnote --db <발굴DB 덤프.json>

생성 문장 쓰기는 이 시연에서만 임시로 한다 — 정식 주인은 script_engine.draft(설명서 brief() 를 받아 쓰기, 엔진 요청).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import script_frame as SF  # noqa: E402

PROMPT = """너는 한국어 쇼핑 숏폼 나레이션 대본 작가다. 아래 [설명서]대로 [상품 사실]만 써서 대본 1편을 써라.
규칙
- 칸 순서 = {slots}. 칸별 글자 비율 참고 {ratio}.
- 첫 문장(훅) 유형은 {hooks} 중 하나.
- 사실은 [고른 사실]을 중심으로 쓴다. [뺄 사실 종류]({drop})는 쓰지 마라. 사실 목록에 없는 사실·숫자·브랜드를 지어내지 마라.
- 화자의 체험(누가 선물했다·직접 써봤다)은 사실 목록에 없다 — 지어내지 말고 전언(~대요/~다던데)이나 듣는 사람 상황으로 쓴다.
- 논리 사슬(노드 순서) 꼴: {chains} 중 하나.
- 문장 끝 어미는 {endings} 안에서만. 말버릇(결만 참고, 그대로 베끼기 금지): {sig}
- 길이: 전체 약 {chars}자, 문장 {nsent}개 안팎, 문장 평균 {slen}자.
- [예문]은 설명 방식만 참고하고, 예문과 공백 뺀 7자 이상 같은 구절을 쓰지 마라.
출력 JSON: {{"lines":[{{"text": 문장, "role": 칸 이름({slots} 중), "node": 상황|불편|속성|결과|증거|감상|권유, "facts": ["f1",…], "shot_kind": {shots} 중}}]}}

[고른 사실]
{picked}
[상품 사실 전체]
{facts}
[예문]
{examples}
"""


def make_prompt(b: dict, facts: list[dict], slots: list[str], ratio: dict | None) -> str:
    return PROMPT.format(slots=" > ".join(slots), ratio=json.dumps(ratio or {}, ensure_ascii=False), hooks="·".join(b["hook_types"]),
                         drop="·".join(b["axes_drop"]) or "없음", chains=" / ".join(b["chains"]), endings="·".join(b["endings"]),
                         sig=" / ".join(b["signature_phrases"][:8]) or "없음", chars=int(b["length"]["chars_median"]),
                         nsent=int(b["length"]["n_sent_median"]), slen=int(b["length"]["sent_len_median"]), shots="|".join(SF.SHOT_KINDS),
                         picked="\n".join(f"{facts[x['i']]['id']}: {x['text']} (축 {','.join(x['axes']) or '-'})" for x in b["facts_picked"]),
                         facts="\n".join(f"{f['id']}: {f['text']}" for f in facts),
                         examples="\n\n".join(f"({i + 1}) {e['text']}" for i, e in enumerate(b["examples"])))


def run(chan: Path, db: Path, out: Path, ask=None):
    L = json.loads((HERE / "LOO_상품사실.json").read_text(encoding="utf-8"))
    hid, product, facts = L["hidden"], L["product"], L["facts"]
    contrast = [chan.parent / c / "engine_뜯기3" for c in ("hottemreport", "sseolpulda", "yummyknow", "banggu")] + [db]
    fr = SF.build(chan / "asr", chan / "top50.json", chan / "bench_main" / "bench.json", contrast, chan / "script_labels",
                  exclude=(hid,), channel="homedesignnote")
    hot = json.loads((HERE / "대조_hottemreport_frame.json").read_text(encoding="utf-8"))
    from tools.calcopy.engine.script_engine import ROLES          # 읽기만 — 핫템 7칸
    bh = SF.brief(product, fr, [f["text"] for f in facts], exclude=(hid,))
    bt = SF.brief(product, hot, [f["text"] for f in facts])
    f1 = fr["1_skeleton"]["formulas"][0]
    jobs = {"homedesignnote": make_prompt(bh, facts, f1["slots"], f1["len_ratio"]),
            "hottemreport": make_prompt(bt, facts, ROLES["hottemreport"], None)}
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as _ask
        ask = _ask
    res = {}
    for k, p in jobs.items():
        d, err = ask([], p, tag=f"loo_demo:{k}", models=("gemini-3.5-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"))
        res[k] = {"draft": d, "err": err, "brief_facts": [facts[x["i"]]["id"] for x in (bh if k == "homedesignnote" else bt)["facts_picked"]],
                  "examples": [e["id"] for e in (bh if k == "homedesignnote" else bt)["examples"]]}
    orig = json.loads((chan / "script_labels" / f"{hid}.json").read_text(encoding="utf-8"))
    rows = {}
    for k, r in res.items():
        lines = (r["draft"] or {}).get("lines") or []
        text = " ".join(x.get("text", "") for x in lines)
        ex_texts = [x["text"] for x in (bh if k == "homedesignnote" else bt)["examples"]]
        rows[k] = {"text": text, "lines": lines,
                   "macro": SF._collapse([SF.MACRO.get(x.get("role"), x.get("role")) for x in lines]),
                   "facts_used": sorted({f for x in lines for f in (x.get("facts") or [])}, key=lambda s: int(s[1:]) if s[1:].isdigit() else 99),
                   "nodes_llm": SF._collapse([x.get("node") for x in lines]),
                   "chain3_rules": SF.chain_shape(SF.features(text)["nodes"], 3),
                   "endings": SF.features(text)["endings"],
                   "judge_hdn": SF.judge_like(text, fr), "judge_hot": SF.judge_like(text, hot),
                   "copy7": SF.copy_spans(text, ex_texts), "brief_facts": r["brief_facts"], "examples": r["examples"], "err": r["err"]}
    o_text = orig["_text"]
    o_macro = SF._collapse([SF.MACRO[b["role"]] for b in orig["beats"] if b.get("role") in SF.MACRO])
    original = {"text": o_text, "macro": o_macro, "nodes_llm": SF._collapse([b.get("node") for b in orig["beats"]]),
                "chain3_rules": SF.chain_shape(SF.features(o_text)["nodes"], 3), "endings": SF.features(o_text)["endings"],
                "judge_hdn": SF.judge_like(o_text, fr), "judge_hot": SF.judge_like(o_text, hot), "facts_used": ["f8", "f9"]}
    for k, r in rows.items():
        a, b = r["macro"], o_macro
        r["order_match"] = round(1 - SF._lev(a, b) / max(1, max(len(a), len(b))), 3)
    out.mkdir(parents=True, exist_ok=True)
    rep = {"hidden": hid, "frame_excluded": fr["inputs"]["excluded"], "original": original, "drafts": rows,
           "facts": {f["id"]: f["text"] for f in facts}}
    (out / "LOO_시연.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chan", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args(argv)
    rep = run(Path(a.chan), Path(a.db), Path(a.out))
    for k, r in [("원본", rep["original"])] + list(rep["drafts"].items()):
        print(k, r.get("macro"), r.get("facts_used"), r.get("chain3_rules"), r["judge_hdn"]["score"], r["judge_hdn"]["pass"],
              r["judge_hot"]["pass"], r.get("order_match"), r.get("copy7"))
        print("   ", r["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
