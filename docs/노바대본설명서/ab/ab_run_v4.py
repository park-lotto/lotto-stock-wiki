"""4차 판 B4 대본 뽑기 — ../cards_v4/*.json, 시안 5개(2026-10-20 사장님 '5개씩만').
ab_run_v2.run_B2 를 그대로 쓰고 설명서 폴더·시안 수·자가 검수 문구만 바꾼다. 버텍스는 스타일×소재 1회.
사용: py ab_run_v4.py [--ids even,jungche] [--src glasspaint,wrap] [--force]  → out/B4_<id>_<src>.json"""
import argparse, json, os, time

import ab_common as C
import ab_run as R
import ab_run_v2 as V2

V2.V2 = os.path.join(C.HERE, "..", "cards_v4")
i = [t for t, _ in V2.ORDER_V2].index("3단계 — 후킹 유형(시안마다 다른 유형)")
V2.ORDER_V2.insert(i + 1, ("3-1단계 — 미끼·연결어: 이븐쇼핑 78편 실측 틀(이 틀 안에서만 고른다)", ["even_bait", "even_signals", "bait_rule", "wow_rule"]))
V2.ORDER_V2.insert(1, ("★공통 — 잉?·와우 포인트(빠지면 다시 쓴다)", ["ing_wow"]))
_li = R.B_SCHEMA["properties"]["drafts"]["items"]["properties"]["lines"]["items"]["properties"]
_li["point"] = {"type": "string"}
_li["answer_at"] = {"type": "integer"}
_vj = C.vertex_json
REPL = [
    ("맨 앞 ★공통 두 절(첫 줄 공식 · 사실 지어냄 vs 분위기 과장)을 먼저 지키고",
     "맨 앞 ★공통 두 절(첫 줄 = 스타일 틀의 고정 낱말 유지 · 발명품·정체 계열은 맨 앞에 해소되는 불편 원인 / 사실 지어냄 vs 분위기 과장 · 효과는 들은 얘기로)을 먼저 지키고"),
    ("대본 **시안 2개**를 써라. 두 시안은 서로 다른 후킹 유형(몸통이 있으면 몸통도 다르게)을 쓰고 첫 줄이 확연히 달라야 한다.",
     "대본 **시안 5개**를 써라. 후킹 유형은 겹쳐도 되지만 첫 줄 · 미끼 조합 · 가장 센 셀링포인트(마지막 와우) · 마무리는 시안마다 달라야 한다."),
    ("출력: drafts 2개.", "출력: drafts 5개."),
    ("(첫 줄 두 덩어리·사실 지어냄 0·7자 겹침 0)", "(첫 줄 틀 고정 낱말·불편 원인 앞·효과는 전언·마무리 서로 다름·7자 겹침 0)"),
    ("compare 에 두 시안 비교와 추천 한 줄", "compare 에 다섯 시안 비교와 추천 한 줄"),
]


def _vertex_json(prompt, schema, tag=""):
    for a, b in REPL:
        assert a in prompt, "프롬프트 문구가 바뀌었다: " + a[:30]
        prompt = prompt.replace(a, b)
    return _vj(prompt, schema, tag=tag.replace("B2", "B4"))


V2.C.vertex_json = _vertex_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="even,jungche")
    ap.add_argument("--src", default="glasspaint,wrap")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for src in a.src.split(","):
        inp = R.load_input(src)
        for cid in a.ids.split(","):
            dst = os.path.join(R.OUT, "B4_%s_%s.json" % (cid, src))
            if os.path.exists(dst) and not a.force:
                print("건너뜀(있음)", dst); continue
            r = V2.run_B2(cid, inp)
            r.update(side="B4", id=cid, src=src)
            json.dump(r, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("B4 %s %s 시안 %d" % (cid, src, len(r["drafts"])), flush=True)
    json.dump(C.CALLS, open(os.path.join(R.OUT, "_calls_B4_%d.json" % int(time.time())), "w", encoding="utf-8"), ensure_ascii=False)
    print("버텍스 호출 %d (실패 %d)" % (len(C.CALLS), sum(not c["ok"] for c in C.CALLS)))


if __name__ == "__main__":
    main()
