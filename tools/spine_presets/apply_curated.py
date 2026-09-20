# -*- coding: utf-8 -*-
"""사람이 고른 문장틀만 스파인에 넣는다 (2026-09-18, 인스타 스파인 보강).

harvest_templates.py 는 모델이 뽑은 후보를 보여줄 뿐이다. 다시 돌리면 후보가 바뀐다 — 그래서 읽고 고른 것을
JSON {"스파인id": {"칸": ["문장", ...]}} 로 적고 이 도구로 넣는다. 넣기 전에 다시 거른다:
  ① 원문 그대로(슬롯 뺀 6자 이상 조각이 인스타 원문에 있음)  ② audit_spines 결함 기준(결합·외국어·박힌수치·브랜드·슬롯오타)
  ③ 기존 틀과 중복 제외. 하나라도 걸리면 그 문장은 빼고 이유를 찍는다.
  서버: cd /tmp/ab && python3 tools/spine_presets/apply_curated.py curated.json [--apply]
"""
import io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from tools.spine_presets.harvest_templates import _load_texts, _verbatim_ok, DB
from tools.spine_presets.audit_spines import BAD_JOIN, FAKE_FACT, BRAND, SLOT, KNOWN_SLOTS, _ko_ratio


# 자동 자막(유튜브) 오타 — 원문 대조 전에만 바로잡는다(틀에 오타를 넣지 않으려고). 2026-09-18 실측 빈도순
ASR_FIX = [("때돈", "떼돈"), ("돈방 앉은", "돈방석에 앉은"), ("돈방에 앉", "돈방석에 앉"), ("이키아", "이케아"), ("바이러럴", "바이럴")]


def _corpus_texts(argv):
    """원문 대조 대상. 기본 = 인스타(예전 그대로).
    --corpus=insta,wiki,texts  wiki = script_wiki 전 출처(유튜브·틱톡·인스타 대본)
    --texts=<json>             유튜브 자막 원문 파일(문자열 리스트) — PC에서 모은 썰쇼핑 자막(서버엔 없다)"""
    want = next((a.split("=", 1)[1] for a in argv if a.startswith("--corpus=")), "insta").split(",")
    out = []
    if "insta" in want:
        out += [t for _, _, t in _load_texts("*", "insta", 100000)]
    if "wiki" in want:
        import sqlite3
        c = sqlite3.connect(DB)
        out += [r[0] or "" for r in c.execute("select full_text from script_wiki")]
    tf = next((a.split("=", 1)[1] for a in argv if a.startswith("--texts=")), None)
    if tf:
        out += list(json.load(io.open(tf, encoding="utf-8")))
    fixed = []
    for t in out:
        for a, b in ASR_FIX:
            t = t.replace(a, b)
        fixed.append(t)
    return fixed


def main():
    cur_file = sys.argv[1]; apply = "--apply" in sys.argv
    want = json.load(io.open(cur_file, encoding="utf-8"))
    texts = _corpus_texts(sys.argv)
    from shopping_shorts.store import Store
    st = Store(DB)
    sp_all = {s["id"]: s for s in st.list_spines(status="approved")}
    for sid, roles in want.items():
        sp = sp_all[int(sid)]; tpl = dict(sp.get("templates") or {}); added = 0
        for r, arr in roles.items():
            if r not in (sp.get("beat_roles") or []):
                print(f"[{sid}] 칸 없음 {r} — 건너뜀"); continue
            cur = list(tpl.get(r) or [])
            for t in arr:
                why = ("원문아님" if not _verbatim_ok(t, texts) else "결합깨짐" if BAD_JOIN.search(t) else
                       "박힌수치" if FAKE_FACT.search(t) else "브랜드" if BRAND.search(t) else
                       "외국어" if _ko_ratio(t) < 0.6 else
                       "슬롯오타" if any(x not in KNOWN_SLOTS for x in SLOT.findall(t)) else
                       "중복" if t in cur else "")
                if why:
                    print(f"[{sid}] {r} x({why}) {t}"); continue
                cur.append(t); added += 1; print(f"[{sid}] {r} + {t}")
            tpl[r] = cur
        if apply and added:
            st.set_spine_style(int(sid), templates=tpl)
        print(f"[{sid}] {'APPLIED' if apply else '(미적용)'} {added}개 → " + str({k: len(v) for k, v in tpl.items()}))


if __name__ == "__main__":
    main()
