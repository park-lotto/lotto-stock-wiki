"""3차 판 B3 대본 뽑기 — ../cards_v3/*.json. ab_run_v2 와 같고 설명서 폴더·자가 검수 문구만 다르다(2026-10-20).
버텍스 아끼기: 기본은 첫 줄을 바꾼 스타일만(--ids even,jungche). 읽어 보고 통과하면 나머지를 돌린다.
사용: py ab_run_v3.py [--ids even,jungche] [--src glasspaint,wrap] [--force]  → out/B3_<id>_<src>.json"""
import argparse, json, os, time

import ab_common as C
import ab_run as R
import ab_run_v2 as V2

V2.V2 = os.path.join(C.HERE, "..", "cards_v3")
_vj = C.vertex_json


def _vertex_json(prompt, schema, tag=""):
    prompt = prompt.replace("맨 앞 ★공통 두 절(첫 줄 공식 · 사실 지어냄 vs 분위기 과장)을 먼저 지키고",
                            "맨 앞 ★공통 두 절(첫 줄 = 스타일 틀의 고정 낱말 유지 · 발명품·정체 계열은 맨 앞에 해소되는 불편 원인 / 사실 지어냄 vs 분위기 과장)을 먼저 지키고")
    prompt = prompt.replace("(첫 줄 두 덩어리·사실 지어냄 0·7자 겹침 0)", "(첫 줄 틀 고정 낱말·불편 원인 앞·사실 지어냄 0·7자 겹침 0)")
    return _vj(prompt, schema, tag=tag.replace("B2", "B3"))


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
            dst = os.path.join(R.OUT, "B3_%s_%s.json" % (cid, src))
            if os.path.exists(dst) and not a.force:
                print("건너뜀(있음)", dst); continue
            r = V2.run_B2(cid, inp)
            r.update(side="B3", id=cid, src=src)
            json.dump(r, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print("B3 %s %s 시안 %d" % (cid, src, len(r["drafts"])), flush=True)
    json.dump(C.CALLS, open(os.path.join(R.OUT, "_calls_B3_%d.json" % int(time.time())), "w", encoding="utf-8"), ensure_ascii=False)
    print("버텍스 호출 %d (실패 %d)" % (len(C.CALLS), sum(not c["ok"] for c in C.CALLS)))


if __name__ == "__main__":
    main()
