# -*- coding: utf-8 -*-
"""LOO 시연 2판 — 서사 노드·창작 허용선·S1 원리/체감 상한을 넣은 brief 로 다시 생성(렌더·TTS 없음).
원본 1편을 숨기고(build exclude) 제품 사실만 준다. 생성 뒤 같은 제미나이 표시기(label_narr_llm)로 원본·생성 노드열을 나란히 잰다.

    PYTHONUTF8=1 py channel/homedesignnote/대본설명서/loo_demo2.py --chan C:/숏템_칼카피/homedesignnote --db <DB tune.json> --facts LOO_상품사실.json LOO2_상품사실.json

생성 문장 쓰기는 시연에서만 — 정식 주인은 script_engine.draft(brief 를 받아 쓰기, 엔진 요청).
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

PROMPT = """너는 한국어 쇼핑 숏폼 나레이션 대본 작가다. 아래 [설명서]의 결대로 대본 1편을 써라.
[창작 허용선] 화자 설정·지인·가족·계기·감상·비유·결과 과장은 지어내도 된다(이 채널의 결이다).
제품 속성·수치·사회적 반응(인기·품절·유행)·가격은 [상품 사실]에 있는 것만 쓴다. 없는 제품 사실을 지어내지 마라.
[서사] 이 채널은 둘 중 하나로 말한다 — 체험담형(구체 인물 계기: 와이프·친구·엄마가 보여줌/선물/집에서 봄 + 극단 행동 '바로 버렸다·절대 안 산다' + 자기 위치 '초보·커알못·전셋집' + 쓴 뒤 결과 과장) 또는 전언해설형('~대요/~다는데'로 개발 배경·반응 전달).
노드 출현율(원본 49편): {nodes}. 계기·극단행동은 맨 앞, 체감비유는 가운데, 결과과장은 끝에 온다.
속성 다음에는 '나에게 생긴 변화(체감·결과)'로 넘긴다. 체감 비유(A 같다, A vs B) 1개 이상.
[고른 사실] 아래 사실을 중심으로(원리·스펙 사실은 {cap}개 이하): {picked}
[칸] {slots}  · 첫 문장 유형 {hooks}
[화법] 어미 {endings} 안에서만({foreign} 금지). 연결어미({conn})로 이어 쓴다 — 문장당 약 {cps}개. 전체 약 {chars}자, 문장 {nsent}개 안팎.
[예문] 설명 방식만 참고, 예문과 공백 뺀 7자 이상 같은 구절 금지.
{examples}
[상품 사실 전체]
{facts}
출력 JSON: {{"lines":[{{"text": 문장, "node": 계기|극단행동|자기위치|불편공감|원리스펙|체감비유|체감사실|결과과장|사회반응|가격|감상|권유, "facts": ["f1",…](제품 사실을 쓴 문장만), "creative": true|false(지어낸 화자·지인·감상·비유면 true)}}]}}
"""


def make_prompt(b: dict, facts: list[dict], slots: list[str]) -> str:
    cap = sum(1 for x in b["facts_picked"] if x["kind"] == "원리스펙")
    return PROMPT.format(nodes=", ".join(f"{k} {v:.0%}" for k, v in b["narr_nodes"].items()), cap=max(1, cap),
                         picked="; ".join(f"{facts[x['i']]['id']} {x['text']}" for x in b["facts_picked"]), slots=" > ".join(slots),
                         hooks="·".join(b["hook_types"]), endings="·".join(b["endings"]), foreign="·".join(b.get("foreign_endings") or []) or "없음",
                         conn="·".join(b.get("connectives") or []), cps=b.get("connect_per_sent", 1), chars=int(b["length"]["chars_median"]),
                         nsent=int(b["length"]["n_sent_median"]),
                         examples="\n\n".join(f"({i + 1}) {e['text']}" for i, e in enumerate(b["examples"])),
                         facts="\n".join(f"{f['id']}: {f['text']}" for f in facts))


def run(chan: Path, db: Path, fact_files: list[Path], ask=None) -> dict:
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as _ask
        ask = _ask
    contrast = [chan.parent / c / "engine_뜯기3" for c in ("hottemreport", "sseolpulda", "yummyknow", "banggu")] + [db]
    out = {}
    for ff in fact_files:
        L = json.loads(Path(ff).read_text(encoding="utf-8"))
        hid, product, facts = L["hidden"], L["product"], L["facts"]
        fr = SF.build(chan / "asr", chan / "top50.json", chan / "bench_main" / "bench.json", contrast, chan / "script_labels",
                      exclude=(hid,), channel="homedesignnote", narr_dir=chan / "narr_labels")
        b = SF.brief(product, fr, [f["text"] for f in facts], exclude=(hid,))
        f1 = fr["1_skeleton"]["formulas"][0]
        p = make_prompt(b, facts, f1["slots"])
        d, err = ask([], p, tag=f"loo2:{hid}", models=("gemini-3.5-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"))
        d = d or {}
        lines = d.get("lines") or d.get("items") or next((v for v in d.values() if isinstance(v, list)), [])
        text = " ".join(x.get("text", "") for x in lines)
        orig = json.loads((chan / "narr_labels" / f"{hid}.json").read_text(encoding="utf-8"))
        audit = SF.grounding_audit([x.get("text", "") for x in lines])
        out[hid] = {"facts_file": str(ff), "picked": [(facts[x["i"]]["id"], x["kind"]) for x in b["facts_picked"]], "examples": [e["id"] for e in b["examples"]],
                    "err": err, "draft_lines": lines, "draft_text": text, "orig_text": " ".join(orig["sentences"]), "orig_tags": orig["tags"],
                    "orig_chain": SF.narr_chain(orig["tags"], 6), "draft_chain_gen": SF.narr_chain([[x.get("node")] for x in lines], 6),
                    "copy7": SF.copy_spans(text, [e["text"] for e in b["examples"]]),
                    "ungrounded": [a["text"] for a, x in zip(audit, lines) if a["needs_ground"] and not x.get("facts")],
                    "judge_draft": SF.judge_like(text, fr), "judge_orig": SF.judge_like(" ".join(orig["sentences"]), fr), "frame_threshold": fr["judge"]["threshold"],
                    "prompt": p}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--chan", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--facts", nargs="+", required=True)
    a = ap.parse_args(argv)
    rep = run(Path(a.chan), Path(a.db), [HERE / f if not Path(f).is_absolute() else Path(f) for f in a.facts])
    (HERE / "LOO2_시연.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for hid, r in rep.items():
        print(hid, r["picked"], r["err"])
        print("  원본:", r["orig_chain"], "|", r["orig_text"][:160])
        print("  생성:", r["draft_chain_gen"], "|", r["draft_text"])
        print("  judge 생성", r["judge_draft"]["score"], r["judge_draft"]["pass"], "원본", r["judge_orig"]["score"], r["judge_orig"]["pass"],
              "copy7", r["copy7"], "근거없는 제품문장", r["ungrounded"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
