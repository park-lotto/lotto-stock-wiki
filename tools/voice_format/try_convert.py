"""확정 대본 하나를 대화 틀 5종(또는 지정 틀)으로 변환해 보고 검사 결과와 함께 출력·저장.
사용: py tools/voice_format/try_convert.py <대본.txt> [틀 ...] > 결과 / 저장: <대본>_대화변환.json"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shopping_shorts import dialogue_script as ds
path = sys.argv[1]
src = [l for l in open(path, encoding="utf-8").read().split("\n") if l.strip()]
forms = sys.argv[2:] or list(ds.FORMS)
res = {}
for form in forms:
    try:
        out = ds.convert(src, form); res[form] = out
        print(f"\n== {form} ({ds.FORMS[form]['label']}) {len(out)}줄")
        for o in out: print(f"  {o['speaker']:4s} [{o['tag']}] {o['text']}  src{o['src']}")
    except ValueError as e:
        res[form] = {"error": str(e)}; print(f"\n== {form} 실패: {e}")
json.dump(res, open(os.path.splitext(path)[0] + "_대화변환.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
