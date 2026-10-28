# -*- coding: utf-8 -*-
"""대본 품질의 **기준자** — 고장 검사가 아니라 "터진 대본과 닮았나 / 고객이 그대로 쓰나"를 잰다 (2026-09-21).

왜: 대본 방식을 한 달에 다섯 번 갈았는데 매번 기준이 '사장님 눈' 하나였다. 검사는 전부 고장 여부
    (말투·칸 수·깨진 결합)만 봐서, 검사는 통과하는데 읽으면 별로인 일이 반복됐다.
    기준은 두 군데서만 나온다: ①히트작 원문 자체 ②고객의 실제 행동.

서버에서(읽기 전용 — DB를 mode=ro로 연다, 아무것도 안 쓴다, 모델 호출 0회):
    cd /home/ubuntu/lotto-stock-wiki && python3 /home/ubuntu/patchcheck/script_yardstick.py [--days 30]

출력은 **집계 숫자만**이다(고객 대본 원문은 찍지 않는다).
"""
import argparse
import datetime
import difflib
import json
import re
import sqlite3
import statistics as st

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
OPEN_END = re.compile(r"(는데|은데|인데|던데|다는데|라는데|다고|라고|다며|면서|해서|라서|고|며|지만|니까)[\s.~…]*$")
POLITE = re.compile(r"(요|니다|니까|세요|시오|죠)[\s.!?~…]*$")
CTA = re.compile(r"댓글|프로필|링크|팔로우|구독|저장해|눌러|써보세요|해보세요|확인하세요")


def _lines_of(text):
    return [l.strip() for l in re.split(r"[\n]+", text or "") if l.strip()]


def shape(lines):
    """대본 한 편의 모양. lines=줄 목록."""
    ls = [l for l in lines if l]
    n = len(ls)
    if not n:
        return None
    chars = sum(len(re.sub(r"\s", "", l)) for l in ls)
    return {"lines": n, "chars": chars, "per_line": chars / n,
            "open": sum(1 for l in ls if OPEN_END.search(l)) / n,      # 문장을 안 끝내고 잇는 줄 비율
            "polite": sum(1 for l in ls if POLITE.search(l)) / n,
            "cta": 1.0 if any(CTA.search(l) for l in ls[-2:]) else 0.0,
            "hook": len(re.sub(r"\s", "", ls[0])),
            "last_open": 1.0 if OPEN_END.search(ls[-1]) else 0.0}       # 끝을 끊어 반복재생으로 잇나


def summarize(name, shapes):
    shapes = [s for s in shapes if s]
    if not shapes:
        print("  %-22s (자료 없음)" % name)
        return
    med = lambda k: st.median(s[k] for s in shapes)      # noqa: E731
    avg = lambda k: sum(s[k] for s in shapes) / len(shapes)   # noqa: E731
    print("  %-22s n=%-4d 줄 %4.1f · 글자 %5.0f · 줄당 %4.1f · 훅 %4.1f자 | 잇는줄 %3.0f%% · 존댓말 %3.0f%% · CTA %3.0f%% · 끝 끊음 %3.0f%%"
          % (name, len(shapes), med("lines"), med("chars"), med("per_line"), med("hook"),
             100 * avg("open"), 100 * avg("polite"), 100 * avg("cta"), 100 * avg("last_open")))


def draft_text(d):
    if not isinstance(d, dict):
        return ""
    for k in ("script", "text", "given", "full_text"):
        if isinstance(d.get(k), str) and d[k].strip():
            return d[k]
    bs = d.get("beats")
    if isinstance(bs, list):
        return "\n".join(str((b or {}).get("text") or (b or {}).get("narration") or "") for b in bs if isinstance(b, dict))
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    con.row_factory = sqlite3.Row

    print("== ① 터진 대본은 어떻게 생겼나 (원문형 스파인의 히트작 원문)")
    hits = []
    for r in con.execute("SELECT id, name, templates_json FROM spine WHERE templates_json LIKE '%_origin%'"):
        try:
            o = (json.loads(r["templates_json"] or "{}") or {}).get("_origin") or {}
        except Exception:      # noqa: BLE001
            continue
        cells = [str(c.get("text") or "").strip() for c in (o.get("cells") or []) if isinstance(c, dict)]
        if len(cells) >= 3:
            hits.append((o.get("views") or 0, shape(cells)))
    summarize("히트작 전체", [s for _, s in hits])
    hits.sort(key=lambda x: -(x[0] or 0))
    k = max(1, len(hits) // 4)
    summarize("  조회수 상위 25%", [s for _, s in hits[:k]])
    summarize("  조회수 하위 25%", [s for _, s in hits[-k:]])

    since = (datetime.datetime.utcnow() - datetime.timedelta(days=a.days)).strftime("%Y-%m-%d")
    print("\n== ② 우리가 만든 대본은 어떻게 생겼나 (최근 %d일, 작업에 저장된 2단계 후보)" % a.days)
    works = []
    for r in con.execute("SELECT work_id, customer_id, state_json, step FROM produce_works WHERE updated_at >= ?", (since,)):
        try:
            s = json.loads(r["state_json"] or "{}")
        except Exception:      # noqa: BLE001
            continue
        s2 = s.get("s2") if isinstance(s.get("s2"), dict) else {}
        drafts = [draft_text(d) for d in (s2.get("drafts") or [])]
        drafts = [d for d in drafts if d.strip()]
        works.append({"cid": r["customer_id"], "step": r["step"] or 0, "script": (s.get("script") or "").strip(),
                      "drafts": drafts})
    cust = [w for w in works if w["cid"] != 0]
    adm = [w for w in works if w["cid"] == 0]
    summarize("고객 후보", [shape(_lines_of(d)) for w in cust for d in w["drafts"]])
    summarize("관리자 후보", [shape(_lines_of(d)) for w in adm for d in w["drafts"]])
    summarize("고객이 확정한 대본", [shape(_lines_of(w["script"])) for w in cust if w["script"]])

    print("\n== ③ 고객은 우리 대본을 그대로 쓰나 (확정 대본 ↔ 가장 가까운 후보의 닮음)")
    for name, grp in (("고객", cust), ("관리자", adm)):
        have = [w for w in grp if w["drafts"]]
        sims = []
        for w in have:
            if not w["script"]:
                continue
            nz = lambda t: re.sub(r"\s+", "", t)      # noqa: E731
            sims.append(max(difflib.SequenceMatcher(None, nz(w["script"]), nz(d)).ratio() for d in w["drafts"]))
        n = len(sims)
        as_is = sum(1 for x in sims if x >= 0.95)
        edited = sum(1 for x in sims if 0.6 <= x < 0.95)
        rewrote = sum(1 for x in sims if x < 0.6)
        no_script = sum(1 for w in have if not w["script"])
        print("  %-6s 작업 %d건 중 후보 받은 작업 %d건 → 확정 %d건(그대로 %d · 고쳐 씀 %d · 갈아엎음/직접 씀 %d) · 확정 안 함 %d건"
              % (name, len(grp), len(have), n, as_is, edited, rewrote, no_script))
        if sims:
            print("         닮음 중앙값 %.2f · 확정한 작업 중 다음 단계(3단계+)로 간 비율 %d%%"
                  % (st.median(sims), 100 * sum(1 for w in have if w["script"] and w["step"] >= 7) / max(1, n)))


if __name__ == "__main__":
    main()
