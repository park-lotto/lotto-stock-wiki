# -*- coding: utf-8 -*-
"""[서버용·읽기 전용] 장면 먼저 → 스토리보드 시험 (2026-10-04 사장님 "분석부터 매칭까지 이 화면 전체").

  ① 장면 목록: 1단계 태그(컷마다 설명·쓰임·소구점)를 "무엇을 보여 주나"로 묶고, 없는 장면을 적는다 + 재료 종류
  ② 스타일 묶음 추천: 승인 스타일(spine)을 칸 구조가 같은 것끼리 묶어, 재료 종류에 맞는 판 + 칸마다 맞는 장면이 있나로 점수
  ③ 스토리보드: 1위 묶음의 칸마다 장면 번호를 **먼저** 꽂고, 그 장면이 보여 주는 것만으로 스타일 말투 문장을 쓴다(빈 칸 없음, 약한 칸은 설명)
  ④ 매칭 검사(코드): 없는 컷 번호·칸끼리 겹친 컷·컷 길이×1.2 < 문장 예상 길이
  모델 호출: 작업당 4번(①·②·③·③-2 검수). script_generate._call_json(vertex=True) — 서버 설정 vertex_ops 의 script_generate = gemini-3.6-flash.
  DB 무변경. 출력: /tmp/sbtrial_<job>.json

    set -a && . /etc/shopping-shorts.env && set +a && cd /home/ubuntu/lotto-stock-wiki
    python3 tools/storyboard_trial.py f3d86941c30b 9fed785a6af4
"""
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.getcwd())
from shopping_shorts import script_generate as sg            # noqa: E402
from shopping_shorts.edit_plan import narr_secs                # noqa: E402

DB = "shopping_shorts/data/reference.db"

S1 = {"type": "object", "properties": {
    "kind": {"type": "string"},
    "groups": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "desc": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["name", "ids"]}},
    "missing": {"type": "array", "items": {"type": "string"}}},
    "required": ["kind", "groups", "missing"]}

S2 = {"type": "object", "properties": {
    "styles": {"type": "array", "items": {"type": "object", "properties": {
        "family": {"type": "integer"}, "pan": {"type": "string"}, "filled": {"type": "integer"}, "total": {"type": "integer"},
        "note": {"type": "string"}}, "required": ["family", "filled", "total"]}},
    "board": {"type": "object", "properties": {
        "family": {"type": "integer"}, "first_line_style": {"type": "string"},
        "slots": {"type": "array", "items": {"type": "object", "properties": {
            "slot": {"type": "string"}, "need": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}},
            "line": {"type": "string"}, "weak": {"type": "string"}}, "required": ["slot", "ids", "line"]}}},
        "required": ["family", "slots"]}},
    "required": ["styles", "board"]}

P1 = """너는 쇼핑 쇼츠 **영상 추출·분석 전문가**다. 아래는 담은 영상들의 컷 태그다(컷 번호 | 길이 | 화면 설명 | 쓰임 | 소구점).
대본을 쓰기 **전에**, 이 재료에 어떤 장면이 있는지 한눈에 보이게 정리하라.
1) kind: 재료 종류 하나 — 레시피 / 홈템 / 뷰티 / 가전 / 생활용품 / 장비템 / 기타
2) groups: "무엇을 보여 주나"가 같은 컷끼리 5~9묶음. name 은 이모지 하나 + 짧은 이름, desc 는 한 구절,
   ids 는 그 묶음 컷 번호(목록에 있는 것만, 대표 컷 순으로 최대 6개). 뒷컷(인사·채널·검은 화면)·다른 제품 컷은 넣지 마라.
3) missing: 쇼츠 대본에 흔히 쓰는데 이 재료에는 없는 장면 2~4개.
출력 JSON만.

[컷 목록]
%s
"""

P2 = """너는 수천 편을 쓴 쇼핑 쇼츠 **영상 대본 작가 겸 편집자**다. 아래 [장면 목록]이 이 재료에 있는 장면 전부다. 장면이 먼저고, 문장은 장면에서 나온다.

[재료 종류] %s
[장면 목록]
%s
[없는 장면] %s

[스타일 묶음] — 번호 | 이름들 | 맞는 재료 종류 | 칸 구조(칸 이름: 그 칸이 하는 일) | 감정 흐름
%s

styles: 이 재료 종류에 맞는 판으로 쓸 수 있는 묶음 4개를 고르고(재료 종류가 그 묶음의 기본 종류와 다르면 칸 뜻을 이 재료에 맞게 바꿔 읽어라 — pan 에 그 판 이름),
칸마다 맞는 장면이 있는지 세어 filled/total, note 는 무엇이 모자란지 한 구절. 점수 높은 순.
★칸이 요구하는 장면이 [없는 장면]에 있으면(예: 가격 칸인데 가격 장면 없음, 반응 칸인데 반응 장면 없음) 그 칸은 채운 칸으로 세지 마라.
board 는 {"family": 1위 번호, "slots": []} 로 둔다(다음 단계에서 짠다).
출력 JSON만.
"""

P3 = """너는 수천 편을 쓴 쇼핑 쇼츠 **영상 대본 작가 겸 편집자**다. 장면이 먼저고, 문장은 장면에서 나온다.
[재료 종류] %s
[장면 목록 — 컷 번호(길이)]
%s
[없는 장면] %s
[스타일] %s (%s) — 감정 흐름: %s
[칸 — 아래 %d칸을 이 순서대로 **전부** 채워라. 하나도 빼지 마라]
%s

칸마다:
- ids: 그 칸 컷 번호 1~3개(목록에 있는 것만, 한 컷은 한 칸에만). 컷 길이 합 × 1.2 ≥ 그 칸 문장 읽는 시간(글자 수 ÷ 7초).
- line: 그 칸 컷들이 실제로 보여 주는 것만 말하는 한 문장(12~40자), 그 스타일 말투. 과장·감탄은 허용.
  ★화면에 없는 가격·숫자·사람(가족·친구·전문가 등)·댓글 안내는 지어내지 마라 — 칸 이름이 그걸 요구해도 컷이 보여 주는 것으로 그 칸 역할을 해라.
  첫 줄 틀에 {대상} 같은 빈칸이 있으면 이 재료의 말로 채워라.
- need: 그 칸이 하는 일.
- weak: 딱 맞는 장면이 없어 가까운 장면으로 대신했으면 그 이유와 보충 방법 한 줄, 맞으면 빈 문자열.
first_line_style: 그 묶음 안에서 고른 첫 줄 틀 이름.
출력 JSON만.
"""

S4 = {"type": "object", "properties": {"fix": {"type": "array", "items": {"type": "object", "properties": {
    "i": {"type": "integer"}, "why": {"type": "string"}, "line": {"type": "string"}}, "required": ["i", "line"]}}}, "required": ["fix"]}

P4 = """너는 쇼핑 쇼츠 **장면 매칭 검수자**다. 아래는 스토리보드 칸마다 [문장]과 그 칸에 꽂힌 컷들의 [화면 설명]이다.
문장이 화면 설명에 **보이지 않는 것**(가격·숫자·사람·댓글 안내·화면에 없는 기능)을 말하는 칸을 찾아,
같은 스타일 말투로 **그 칸 화면에 보이는 것만** 말하는 문장(12~40자)으로 다시 써라. 과장·감탄은 허용. 맞는 칸은 넣지 마라.
코드가 이미 걸러 낸 칸: %s
출력 JSON만: {"fix":[{"i":칸번호(0부터),"why":"...","line":"..."}]}

%s
"""

import re as _re
_PEOPLE = ("남편", "아내", "아이", "아들", "딸", "엄마", "아빠", "친구", "가족", "전문가", "셰프", "직원", "사장님", "할머니", "시어머니")


def _code_flags(slots, desc_of):
    """화면 설명에 없는 숫자·사람·댓글 안내·빈칸 틀 — 코드로 거른다(모델 검수 전에)."""
    out = {}
    for i, sl in enumerate(slots):
        line = sl.get("line") or ""
        seen = " ".join(desc_of(c) for c in sl.get("ids") or [])
        why = []
        for num in _re.findall(r"\d+", line):
            if num not in seen:
                why.append("화면에 없는 숫자 %s" % num)
        for p in _PEOPLE:
            if p in line and p not in seen:
                why.append("화면에 없는 사람 '%s'" % p)
        if "댓글" in line and "댓글" not in seen:
            why.append("댓글 안내")
        if "{" in line or "}" in line:
            why.append("빈칸 틀")
        if why:
            out[i] = why
    return out


def _families(db):
    rows = db.execute("select id, name, situation_type, fit_categories_json, beat_roles_json, beat_chain_json, emotion_arc "
                      "from spine where status='approved' order by id").fetchall()
    fam, order = {}, []
    for sid, name, sit, fit, roles, chain, arc in rows:
        roles_l = json.loads(roles or "[]")
        key = tuple(roles_l) if roles_l else ("solo", sid)
        if key not in fam:
            fam[key] = {"names": [], "fit": set(), "roles": roles_l, "chain": json.loads(chain or "[]"), "arc": arc or "", "sit": sit or ""}
            order.append(key)
        fam[key]["names"].append(name)
        fam[key]["fit"].update(json.loads(fit or "[]"))
    out = []
    for n, k in enumerate(order, 1):
        f = fam[k]
        slots = " / ".join("%s: %s" % (r, (f["chain"][i] if i < len(f["chain"]) else ""))[:70] for i, r in enumerate(f["roles"])) \
            or ("(칸 구조 없음 — %s)" % f["sit"])
        out.append((n, f, "%d | %s | %s | %s | %s" % (n, ", ".join(f["names"]), ", ".join(sorted(f["fit"])), slots, f["arc"])))
    return out


def main(jobs):
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    fams = _families(db)
    for jid in jobs:
        t0 = time.time()
        ex = json.loads(db.execute("select extract_json from mix_jobs where job_id=?", (jid,)).fetchone()[0])
        segs, rows, descs = {}, [], {}
        for vid, e in ex.items():
            for s in (e or {}).get("segments") or []:
                a, b = float(s.get("start") or 0), float(s.get("end") or 0)
                if b - a < 0.6 or (s.get("is_outro") and not s.get("product_benefits")):
                    continue
                segs[s["seg_id"]] = round(b - a, 1)
                descs[s["seg_id"]] = "%s %s" % (s.get("scene_desc") or "", s.get("use_point") or "")
                rows.append("  %s | %.1f초 | %s | 쓰임:%s | 소구점:%s" % (s["seg_id"], b - a, (s.get("scene_desc") or "")[:70],
                                                                 s.get("label") or "-", (s.get("use_point") or "")[:40] or "-"))
        n1, n2 = {}, {}
        r1 = sg._call_json(P1 % "\n".join(rows), S1, note=n1, vertex=True) or {}
        inv = "\n".join("  %s (%s): %s" % (g.get("name"), g.get("desc") or "", ", ".join(g.get("ids") or [])) for g in r1.get("groups") or [])
        r2 = sg._call_json(P2 % (r1.get("kind") or "", inv, " / ".join(r1.get("missing") or []), "\n".join(f[2] for f in fams)),
                           S2, note=n2, vertex=True) or {}
        # ③ 1위 묶음의 칸 목록을 못 박고 스토리보드(1차 시험: 칸을 절반만 짰다)
        top = (r2.get("styles") or [{}])[0]
        fam = next((f for n, f, _ in fams if n == top.get("family")), fams[0][1])
        roles = fam["roles"] or ["hook", "problem", "method", "result", "land"]
        slot_txt = "\n".join("  %d. %s — %s" % (i + 1, r, (fam["chain"][i] if i < len(fam["chain"]) else "")) for i, r in enumerate(roles))
        inv2 = "\n".join("  %s: %s" % (g.get("name"), ", ".join("%s(%.1f초)" % (c, segs.get(c, 0)) for c in (g.get("ids") or [])))
                         for g in r1.get("groups") or [])
        n3 = {}
        r3 = sg._call_json(P3 % (r1.get("kind") or "", inv2, " / ".join(r1.get("missing") or []), ", ".join(fam["names"]),
                                 top.get("pan") or "", fam["arc"], len(roles), slot_txt), S2["properties"]["board"], note=n3, vertex=True) or {}
        r2["board"] = dict(r3, family=top.get("family"))
        # ③-2 검수: 코드로 걸러 낸 칸 + 모델 검수(호출 1번) → 걸린 칸만 문장 다시
        slots = r2["board"].get("slots") or []
        flags = _code_flags(slots, lambda c: descs.get(c, ""))
        block = "\n".join("칸 %d [%s] 문장: %s\n   화면: %s" % (i, sl.get("slot"), sl.get("line"), " / ".join(descs.get(c, "?") for c in sl.get("ids") or []))
                          for i, sl in enumerate(slots))
        n4 = {}
        r4 = sg._call_json(P4 % (json.dumps({str(k): v for k, v in flags.items()}, ensure_ascii=False), block), S4, note=n4, vertex=True) or {}
        fixed = []
        for fx in r4.get("fix") or []:
            i = fx.get("i")
            if isinstance(i, int) and 0 <= i < len(slots) and (fx.get("line") or "").strip():
                slots[i]["line_before"] = slots[i].get("line")
                slots[i]["line"] = fx["line"].strip()
                slots[i]["fixed_why"] = fx.get("why") or ""
                fixed.append(i)
        if "{" in (r2["board"].get("first_line_style") or ""):
            r2["board"]["first_line_style"] = ", ".join(fam["names"])
        left = _code_flags(slots, lambda c: descs.get(c, ""))
        r2["review"] = {"code_flags": {str(k): v for k, v in flags.items()}, "fixed": fixed, "left_after": {str(k): v for k, v in left.items()}}
        # ④ 매칭 검사(코드)
        used, check = {}, []
        for i, sl in enumerate((r2.get("board") or {}).get("slots") or []):
            ids = sl.get("ids") or []
            bad = [c for c in ids if c not in segs]
            dup = [c for c in ids if c in used]
            for c in ids:
                used.setdefault(c, i)
            have = sum(segs.get(c, 0) for c in ids)
            need = narr_secs(sl.get("line") or "")
            check.append({"slot": i, "bad_ids": bad, "dup_ids": dup, "have": round(have, 1), "need": round(need, 1), "short": have * 1.2 < need - 0.2})
        fam_names = {n: f["names"] for n, f, _ in fams}
        out = {"job": jid, "secs": round(time.time() - t0, 1), "auth": [n1.get("auth"), n2.get("auth"), n3.get("auth"), n4.get("auth")], "inventory": r1, "plan": r2,
               "family_names": {str(k): v for k, v in fam_names.items()}, "check": check}
        json.dump(out, open("/tmp/sbtrial_%s.json" % jid, "w"), ensure_ascii=False, indent=1)
        print(jid, "%.0f초" % out["secs"], "호출 4 · 경로", out["auth"], "· 묶음", len(r1.get("groups") or []),
              "· 칸", len(check), "· 없는 번호", sum(len(c["bad_ids"]) for c in check), "· 겹침", sum(len(c["dup_ids"]) for c in check),
              "· 길이 모자람", sum(1 for c in check if c["short"]), "· 코드 걸림", len(r2["review"]["code_flags"]), "· 고친 칸", len(r2["review"]["fixed"]),
              "· 남은 걸림", len(r2["review"]["left_after"]), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
