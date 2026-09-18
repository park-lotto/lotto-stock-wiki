# -*- coding: utf-8 -*-
"""스파인 훅(title) 틀을 원문 **첫 문장**에서 채운다 (2026-09-18 사장님 "100명이 돌려써도 안 똑같게").
실측: 훅 틀이 2~4개인 스타일은 회원 100명 중 27~54명이 같은 첫 문장. 첫 문장 = 채널이 제목을 읽는 자리.
원문 첫 문장 → 모델이 제품·사람·나라 자리만 {슬롯}으로 → 슬롯 뺀 조각이 원문에 그대로 있는지 코드가 검증 → 추가.
서버: cd /tmp/ab && SS_HITS=... python3 tools/spine_presets/harvest_titles.py 71 "의 실수" [--apply]"""
import io, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
DB = os.environ.get("SS_DB", "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
HITS = os.environ.get("SS_HITS", "/tmp/ab/raw/analysis/썰쇼핑_자막확장_2026-09-18/hits_subs.json")
SLOT = re.compile(r"\{[^{}]+\}")
BRANDS = re.compile(r"다이소|이케아|코스트코|쿠팡|구글|아이소|애플|삼성")


def first_sentence(t):
    t = re.sub(r"\[[^\]]*\]|&gt;", " ", t or "")
    m = re.split(r"(?<=[.!?])\s|(?<=[다요음임죠함])\s", t.strip(), maxsplit=1)
    return re.sub(r"\s+", " ", m[0]).strip(" .")[:45]


def main():
    sid = int(sys.argv[1]); pat = sys.argv[2]; apply = "--apply" in sys.argv
    hits = json.load(io.open(HITS, encoding="utf-8"))
    firsts = []
    for h in sorted(hits, key=lambda h: -h.get("views", 0)):
        f = first_sentence(h.get("full_text"))
        if 8 <= len(f) <= 45 and re.search(pat, f) and f not in firsts:
            firsts.append(f)
    firsts = firsts[:20]
    print(f"[{sid}] 원문 첫 문장 {len(firsts)}개")
    if len(firsts) < 2:
        return 1
    from shopping_shorts import script_generate as _sg
    prompt = ("아래는 쇼츠 영상의 **첫 문장(제목 읽기)** 원문이다. 각 문장에서 **제품·사람·장소·나라 자리만** "
              "{제품군}·{대상}·{권위자}·{나라}·{장소}·{성과} 중 알맞은 빈칸으로 바꿔라. 나머지 글자는 한 글자도 바꾸지 마라. "
              "브랜드(다이소·이케아 등)도 {권위자}로. 문장마다 하나씩.\n\n" + "\n".join("- " + f for f in firsts))
    schema = {"type": "object", "properties": {"titles": {"type": "array", "items": {"type": "string"}}}, "required": ["titles"]}
    got = (_sg._call_json(prompt, schema) or {}).get("titles") or []
    from shopping_shorts.store import Store as _St
    banmal = bool(next(x for x in _St(DB).list_spines(status="approved") if x["id"] == sid).get("hook_3s"))
    blob = "\n".join(f.replace(" ", "") for f in firsts)
    keep = []
    for t in got:
        t = re.sub(r"\s+", " ", str(t)).strip(" .")
        parts = [p.replace(" ", "") for p in SLOT.split(t) if len(p.strip()) >= 3]
        # ★점검기(audit_spines)와 같은 기준으로 거른다 — 실측 74: {미국}·{공학자}·{복도} 같은 멋대로 빈칸, '때돈' 오타,
        #   두 문장 이어붙이기, 존댓말이 들어왔다. 거르는 기준을 한 곳(audit_spines)에서 빌려 쓴다(0순위-B).
        from tools.spine_presets.audit_spines import KNOWN_SLOTS, HONORIFIC
        slots_ok = all(x.strip("{}") in KNOWN_SLOTS for x in SLOT.findall(t))
        if (SLOT.search(t) and parts and all(p in blob for p in parts) and not BRANDS.search(t) and t not in keep
                and slots_ok and len(t) <= 30 and not re.search(r"때돈|이\{|[.!?] ", t)
                and not (banmal and HONORIFIC.search(t))):
            keep.append(t)
    from shopping_shorts.store import Store
    st = Store(DB)
    sp = next(s for s in st.list_spines(status="approved") if s["id"] == sid)
    tpl = sp.get("templates") or {}
    # ★훅 칸 이름은 스파인마다 다르다(67=react·68=price·69=deal) — 'title' 고정이면 안 쓰이는 칸에 들어간다(실측)
    hook_role = (sp.get("beat_roles") or ["title"])[0]
    cur = list(tpl.get(hook_role) or [])
    new = [t for t in keep if t not in cur]
    print("  기존", len(cur), "+ 새", len(new))
    for t in new:
        print("   +", t)
    if apply and new:
        tpl[hook_role] = cur + new
        st.set_spine_style(sid, templates=tpl)
        print("  APPLIED", hook_role, len(tpl[hook_role]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
