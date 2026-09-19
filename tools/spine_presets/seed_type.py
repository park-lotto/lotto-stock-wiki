# 씨앗 영상 유형 판정 — "이 영상에 딱 맞는 스타일" 자동 선택의 근거 (2026-09-19 사장님).
# 히트작 분류(classify_hits)와 **같은 프롬프트·같은 유형표**로 씨앗 대본을 판정한다(0순위-B: 판정 기준 한 곳).
# 사용(서버):  python3 seed_type.py out.json job_id [job_id ...]
import json, re, sys
sys.path.insert(0, "/tmp/ab")
from classify_hits import prompt, SCHEMA, TYPES
from shopping_shorts import script_generate as sg

BIG = {"썰형": ["오용형", "발명품형", "제품정체형", "정체의문형"],
       "체험후기형": ["지인증언형", "내자랑형", "목격담형", "무지후회형"],
       "추천지시형": ["다이소지목형", "금지경고형", "권유지시형", "가성비형", "만능템형", "사회증거형", "물건발견형"]}
TYPE_BIG = {t: b for b, L in BIG.items() for t in L}


def seed_of(job):
    from shopping_shorts import backbone_assemble as ba
    ext = (job or {}).get("extract") or {}
    srcs = ba.sources_from_extract(ext)
    bm = (job or {}).get("backbone_main")
    if bm is not None and isinstance(ext.get("s%d" % int(bm)), dict):
        return ba.sources_from_extract({"s%d" % int(bm): ext["s%d" % int(bm)]})[0]
    ko = lambda t: sum(1 for c in t if "가" <= c <= "힣") / max(1, sum(1 for c in t if c.isalpha()))
    kor = [s for s in srcs if ko(s.get("full_text") or "") > 0.7]
    return max(kor or srcs, key=lambda s: len(s.get("full_text") or "")) if srcs else None


def judge(texts):
    """[{id,text}] → {id: {type, hook, strength}} (12편씩 한 번에)."""
    out = {}
    for i in range(0, len(texts), 12):
        r = sg._call_json(prompt(texts[i:i + 12]), SCHEMA) or {}
        for x in r.get("items") or []:
            out[str(x.get("id"))] = x
    return out


def main():
    from shopping_shorts.store import Store
    dst, jobs = sys.argv[1], sys.argv[2:]
    st = Store("/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    rows = []
    for j in jobs:
        s = seed_of(st.get_mix_job(j))
        if s and len((s.get("full_text_ko") or s.get("full_text") or "")) >= 60:
            rows.append({"id": j, "text": (s.get("full_text_ko") or s.get("full_text")).strip(), "product": s.get("product") or ""})
    J = judge(rows)
    for r in rows:
        x = J.get(r["id"]) or {}
        r["type"] = x.get("type") or "판정 실패"
        # 레시피는 여는 방식이 아니라 소재로 가른다(히트작 대분류와 같은 규칙)
        rec = re.search(r"레시피|만들|굽|끓|볶|반죽", r["text"]) and len(re.findall(r"레시피|만들어 (먹|드)|굽|반죽|끓여|볶아|재료|한 입|맛있|드세요|먹이", r["text"])) >= 2
        r["big"] = "레시피형" if rec else TYPE_BIG.get(r["type"], "기타")
        r["why"] = x.get("strength") or ""
        print(r["id"], r["big"], r["type"], "|", r["text"][:50], flush=True)
    json.dump(rows, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
