# -*- coding: utf-8 -*-
"""히트작 원문에서 스파인 문장틀(껍데기)을 **원문 그대로** 수확한다 (2026-09-18).

집 세션이 55번(이븐쇼핑)에 손으로 한 일을 도구로: 원문 N편 → 모델이 역할별로 "제품과 무관한 껍데기 문장"을
{슬롯}만 바꿔 뽑는다 → **원문에 실제로 있는 문장인지 코드가 검증**(슬롯 뺀 조각 6자 이상이 전부 원문에 있어야) →
out/에 JSON + 사람이 읽는 txt → `--apply`면 DB templates에 합친다(중복 제거).

서버에서: cd /tmp/ab && python3 tools/spine_presets/harvest_templates.py 56 --pattern "원래 이렇게|이렇게 쓰는 거 아닌|용도" [--apply]
재료: raw/analysis/썰쇼핑_히트작200_2026-08-20/hits_subs.json (없으면 --corpus script_wiki)
"""
import io
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

DB = os.environ.get("SS_DB", "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
HITS = os.environ.get("SS_HITS", "/home/ubuntu/lotto-stock-wiki/raw/analysis/썰쇼핑_히트작200_2026-08-20/hits_subs.json")
SLOT = re.compile(r"\{[^{}]+\}")


def _verified_channels():
    """SS_VERIFIED=verified_channels.json 이 있으면 S·A 등급 채널 이름 집합, 없으면 None(거르지 않음).
    등급 기준은 grade_yt_channels.py 한 곳(0순위-B)."""
    p = os.environ.get("SS_VERIFIED")
    if not p or not os.path.exists(p):
        return None
    g = json.load(io.open(p, encoding="utf-8"))
    return {ch for ch, v in g.items() if v.get("grade") in ("S", "A")}


def _load_texts(pattern, corpus, limit):
    if corpus == "hits":
        hits = json.load(io.open(HITS, encoding="utf-8"))
        _vc = _verified_channels()          # 검증(S·A) 채널 원문만 — 사장님 "S급 채널은 검증하고 받는거야?"
        if _vc is not None:
            hits = [h for h in hits if (h.get("channel") or "") in _vc]
        rows = [(h["video_id"], h.get("channel") or "", h.get("full_text") or "") for h in hits]
    elif corpus == "insta":
        c = sqlite3.connect(DB)
        def _ko(t):    # 한글 비율(실측: 긴 순으로 뽑으니 영어·힌디·포르투갈어가 먼저 왔다)
            L = [ch for ch in t if ch.isalpha()]
            return (sum(1 for ch in L if "가" <= ch <= "힣") / len(L)) if L else 0
        seen = set(); rows = []
        for r in c.execute("select rowid, full_text, source_url from script_wiki"):
            txt = r[1] or ""
            if "instagram" in str(r[2] or "") and len(txt) >= 150 and _ko(txt) >= 0.8 and txt[:80] not in seen:
                seen.add(txt[:80]); rows.append((str(r[0]), r[2] or "", txt))
    else:
        c = sqlite3.connect(DB)
        cols = [r[1] for r in c.execute("pragma table_info(script_wiki)")]
        tcol = next(x for x in cols if x in ("text", "script", "full_text", "body", "content"))
        # 유튜브 출처만(인스타는 존댓말이라 유튜브형 반말 스파인과 안 맞는다)
        rows = [(str(r[0]), r[2] or "", r[1] or "") for r in c.execute(f"select rowid, {tcol}, source_url from script_wiki")
                if "youtu" in str(r[2] or "")]
    if pattern == "*":                      # 훅 문구가 없는 스파인(인스타형): 긴 원문부터
        return sorted(rows, key=lambda r: -len(r[2]))[:limit]
    rx = re.compile(pattern)
    out = [r for r in rows if r[2] and rx.search(r[2][:200])]
    return out[:limit]


def _verbatim_ok(tpl, texts):
    """슬롯을 뺀 조각(6자 이상)이 전부 어느 원문엔가 있어야 '원문 그대로'로 친다."""
    parts = [p.strip() for p in SLOT.split(tpl) if len(p.strip()) >= 6]
    if not parts:
        return False
    blob = "\n".join(t.replace(" ", "") for t in texts)
    return all(p.replace(" ", "") in blob for p in parts)


def harvest(spine, texts, note=None):
    from shopping_shorts import script_generate as _sg
    roles = spine.get("beat_roles") or []
    tpl = spine.get("templates") or {}
    chain = spine.get("beat_chain") or []
    role_desc = "\n".join(f"  - {r}: 예) {' / '.join((tpl.get(r) or [])[:2])}" for r in roles)
    chain_desc = "\n".join(f"  {i + 1}. {c}" for i, c in enumerate(chain))
    body = "\n\n".join(f"[{vid}] {t[:900]}" for vid, _, t in texts)
    prompt = (
        f"스타일 「{spine.get('name')}」의 문장틀을 원문에서 수확한다. 역할 순서:\n{chain_desc}\n"
        f"역할별 기존 틀 예:\n{role_desc}\n\n"
        "규칙:\n"
        "- 아래 원문에서 **역할마다** 그 역할을 말하는 문장을 **원문 글자 그대로** 떼어라(어미·연결어 한 글자도 바꾸지 마라).\n"
        "- 제품·효능·숫자·나라처럼 제품마다 바뀌는 자리만 {제품}·{제품군}·{효능}·{효능2}·{효능3}·{나라}·{대상}·{성과}·{본래용도}·{가격} 으로 바꿔라.\n"
        "- 빈칸 바로 뒤에 어미가 붙는 꼴({효능}는데·{효능}다는 거)은 그대로 둔다 — 그게 이 채널 말투다.\n"
        "- 역할마다 서로 다른 문장 3~8개. 같은 뜻의 문장은 하나만. 원문에 없는 문장을 지어내지 마라.\n"
        "- 출력: {\"templates\": {\"역할\": [\"문장\", ...]}} 만.\n\n"
        f"원문 {len(texts)}편:\n{body}")
    # Gemini Developer API는 additionalProperties를 못 받는다 — 역할을 속성으로 하나씩 적는다
    schema = {"type": "object", "properties": {"templates": {"type": "object", "properties": {
        r: {"type": "array", "items": {"type": "string"}} for r in roles}}}, "required": ["templates"]}
    out = _sg._call_json(prompt, schema, note=note) or {}
    got = out.get("templates") or {}
    texts_only = [t for _, _, t in texts]
    kept, dropped = {}, {}
    for r in roles:
        for s in (got.get(r) or []):
            s = re.sub(r"\s+", " ", str(s)).strip().rstrip(".!?。")
            if not s:
                continue
            L = [ch for ch in s if ch.isalpha()]
            if L and sum(1 for ch in L if "가" <= ch <= "힣") / len(L) < 0.6:
                dropped.setdefault(r, []).append("(외국어) " + s); continue
            (kept if _verbatim_ok(s, texts_only) else dropped).setdefault(r, []).append(s)
    return kept, dropped


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    sid = int(sys.argv[1])
    pattern = sys.argv[sys.argv.index("--pattern") + 1] if "--pattern" in sys.argv else ""
    corpus = sys.argv[sys.argv.index("--corpus") + 1] if "--corpus" in sys.argv else "hits"
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 30
    apply = "--apply" in sys.argv
    exclude = sys.argv[sys.argv.index("--exclude") + 1] if "--exclude" in sys.argv else ""   # 상표·특정 제품어가 든 틀 제외
    from shopping_shorts.store import Store
    st = Store(DB)
    spine = next((s for s in st.list_spines(status="approved") if s.get("id") == sid), None)
    if not spine:
        print("스파인 없음", sid); return 1
    texts = _load_texts(pattern or spine.get("name", ""), corpus, limit)
    print(f"[{sid}] {spine.get('name')} 재료 {len(texts)}편 (corpus={corpus}, pattern={pattern!r})")
    if len(texts) < 3:
        print("재료 3편 미만 — 중단"); return 1
    note = {}
    kept, dropped = harvest(spine, texts, note=note)
    # ★슬롯 없는 문장은 제품이 박힌 문장일 가능성이 크다(실측 56번: "엉뚱한 용도로 초대방난 테이프"·"다이서도 놀란 이유").
    #   bait·fame·land·notice·react 처럼 원래 제품과 무관한 칸만 슬롯 없이 허용한다.
    NO_SLOT_OK = {"bait", "fame", "land", "notice", "react"}
    # 슬롯 없이 받는 칸도 **일반어**가 있어야 한다(실측 70~73: "이게 원래는 … 초음파 세정기였습니다" 같은 제품 문장이 bait로 들어옴)
    GENERIC = re.compile(r"아이템|제품|이거|이게|이걸|사람들|SNS|난리|논란|화제|천재|직원|개발자|제조사|판매자|업체|떼돈|바이럴|미쳤|충격")
    ORIGIN_WORDS = re.compile(r"원래")     # '원래는 …'은 origin 칸 문장 — bait·fame에 들어오면 칸이 틀린 것
    def _ok(r, x):
        if SLOT.search(x):
            return not (r in ("bait", "fame", "title") and ORIGIN_WORDS.search(x))
        return r in NO_SLOT_OK and bool(GENERIC.search(x)) and not ORIGIN_WORDS.search(x)
    for r in list(kept):
        bad = [x for x in kept[r] if not _ok(r, x)]
        kept[r] = [x for x in kept[r] if _ok(r, x)]
        if bad:
            dropped.setdefault(r, []).extend("(슬롯없음) " + x for x in bad)
    if exclude:
        rx = re.compile(exclude)
        for r in list(kept):
            bad = [x for x in kept[r] if rx.search(x)]
            kept[r] = [x for x in kept[r] if not rx.search(x)]
            if bad:
                dropped.setdefault(r, []).extend("(제외어) " + x for x in bad)
    if not kept:
        print("수확 0 — note:", note); return 1
    cur = spine.get("templates") or {}
    merged = {r: list(cur.get(r) or []) for r in spine.get("beat_roles") or []}
    added = 0
    for r, arr in kept.items():
        for s in arr:
            if s not in merged.setdefault(r, []):
                merged[r].append(s); added += 1
    os.makedirs(os.path.join(ROOT, "out", "spine_presets"), exist_ok=True)
    base = os.path.join(ROOT, "out", "spine_presets", f"spine{sid}")
    json.dump({"spine": sid, "name": spine.get("name"), "kept": kept, "dropped": dropped, "merged": merged,
               "sources": [v for v, _, _ in texts]}, io.open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with io.open(base + ".txt", "w", encoding="utf-8") as f:
        f.write(f"# {sid} {spine.get('name')} — 재료 {len(texts)}편, 수확 {sum(len(v) for v in kept.values())} / 탈락(원문 아님) {sum(len(v) for v in dropped.values())}\n")
        for r in spine.get("beat_roles") or []:
            f.write(f"\n[{r}] 기존 {len(cur.get(r) or [])} + 새 {len(kept.get(r) or [])}\n")
            for s in kept.get(r) or []: f.write(f"  + {s}\n")
            for s in dropped.get(r) or []: f.write(f"  x {s}\n")
    print(io.open(base + ".txt", encoding="utf-8").read())
    if apply:
        st.set_spine_style(sid, templates=merged)
        print(f"APPLIED: {added}개 추가 → 칸별 {{k: len(v) for k, v in merged.items()}}")
    else:
        print(f"(미적용) --apply 주면 {added}개 추가")
    return 0


if __name__ == "__main__":
    sys.exit(main())
