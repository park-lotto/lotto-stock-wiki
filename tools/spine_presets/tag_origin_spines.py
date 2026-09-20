# 원문형 스파인에 **미리 세팅**: 전제·필요 장면·훅 범용성·맞는 소재 (2026-09-20 사장님
# "가능한 걸로 미리 세팅을 하면 안 되나"). 대본을 다 만들어 본 뒤 버리지 말고, 돌리기 전에 후보를 거른다.
#
# 사용(서버):  python3 tag_origin_spines.py [--apply] [--only <spine_id,...>]
# 저장 위치: spine.templates_json 의 _origin 안(premise·needs·hook_generic·material)
import json, re, sqlite3, sys
sys.path.insert(0, "/tmp/ab")
from shopping_shorts import script_generate as sg
from shopping_shorts import backbone_assemble as ba

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
TAG_SCHEMA = {"type": "object", "properties": {
    "needs": {"type": "array", "items": {"type": "string"}},          # 화면에 꼭 있어야 하는 것
    "material": {"type": "string", "enum": ["레시피", "물건", "아무거나"]},
    "hook_generic": {"type": "boolean"},                               # 훅이 다른 제품에도 얹히나
    "hook_locked_words": {"type": "array", "items": {"type": "string"}}},
    "required": ["needs", "material", "hook_generic", "hook_locked_words"]}


def tag_of(origin):
    cells = origin.get("cells") or []
    text = "\n".join("[%s] %s" % (c.get("role"), c.get("text")) for c in cells)
    p = ("아래는 쇼핑 숏폼 히트작 대본이다. 이 대본을 **다른 제품에 틀로 쓸 수 있는지** 미리 판단할 표를 만들어라.\n"
         "needs = 이 이야기가 되려면 새 제품 영상에 꼭 있어야 하는 장면 1~3개(짧게, 제품 이름 없이. "
         "예: '쓰는 모습', '원래 용도와 다르게 쓰는 모습', '남이 보고 반응하는 장면', '설치·조립 과정').\n"
         "material = 이 틀이 얹히는 소재. 요리·음식 전용이면 '레시피', 물건 소개 전용이면 '물건', 둘 다 되면 '아무거나'.\n"
         "hook_generic = 첫 줄(훅)이 제품 고유 이야기 없이 다른 제품에도 그대로 얹히나(true/false).\n"
         "hook_locked_words = 훅에 박혀 다른 제품엔 못 쓰는 낱말들(없으면 빈 배열).\n\n" + text)
    return sg._call_json(p, TAG_SCHEMA) or {}


def main():
    apply = "--apply" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = {int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("select * from spine where name like '히트작%' order by id")]
    for sp in rows:
        if only and sp["id"] not in only:
            continue
        tpl = json.loads(sp["templates_json"] or "{}")
        o = tpl.get("_origin") or {}
        if not o:
            continue
        tag = tag_of(o)
        prem = o.get("premise") or ba.read_premise(o)
        o["premise"], o["tag"] = prem, tag
        tpl["_origin"] = o
        print("%-4d %-40s 소재=%s 훅범용=%s 필요장면=%s %s"
              % (sp["id"], sp["name"][:40], tag.get("material"), tag.get("hook_generic"),
                 ",".join(tag.get("needs") or [])[:40], ("막힌말:" + ",".join(tag.get("hook_locked_words") or [])) if tag.get("hook_locked_words") else ""),
              flush=True)
        if apply:
            con.execute("update spine set templates_json=?, updated_at=datetime('now') where id=?",
                        (json.dumps(tpl, ensure_ascii=False), sp["id"]))
            con.commit()


if __name__ == "__main__":
    main()
