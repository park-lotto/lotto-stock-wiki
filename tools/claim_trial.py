"""주장 번호 태깅 시험(2026-10-01 사장님 "제미니로 해보고 버텍스로 해봐").

가설: 태그를 '대본에 쓸 수 있는 주장 목록(C1…)' + '장면마다 증명하는 주장 번호'로 뽑으면
대본 줄 ↔ 장면 매칭이 추측이 아니라 찾아보기가 되고, 꼬다리(장면이 줄보다 짧아 멈춤·느림·옆 장면)가 준다.

1단계 = 이미 있는 태그(scene_desc·label·product_benefits·change)를 글로 넣어 모양만 바꿔 본다(영상 안 봄).
  job 하나에 호출 2번: ①주장 목록 + 장면별 주장 번호 ②기존 대본 줄별 주장 번호.

서버에서(읽기 전용 — DB는 mode=ro, 결과는 /tmp 에만):
  set -a && . /etc/shopping-shorts.env && set +a
  cd /home/ubuntu/lotto-stock-wiki && python3 /tmp/claim_trial.py run gemini <job...>
  python3 /tmp/claim_trial.py run vertex <job...>
로컬에서 채점: py tools/claim_trial.py score claim_trial_gemini.json [claim_trial_vertex.json]
"""
import json
import sys
import time

DB = "file:/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db?mode=ro"
GEMINI_MODEL = "gemini-3.5-flash"      # frame_script.TAG_MODELS 의 상위 모델
SLOW_MAX = 1.2                         # 고르게 늦추기 허용 상한(경쟁사 실측 3.2→3.8초 = 1.19배)
CHAIN_GAP = 0.25                       # 같은 소스 '바로 다음 컷' 으로 보는 틈(초)

CLAIM_PROMPT = """너는 쇼핑 쇼츠 편집자다. 아래는 한 제품을 찍은 소스 영상들의 장면(컷) 목록이다.
각 장면은 AI가 화면을 보고 적은 태그다(화면·역할·특장점·변화).

할 일 두 가지:
1) 이 재료로 **대본에 쓸 수 있는 주장 목록**을 만든다 — 제품의 기능·특징·장점·효과 중
   **화면으로 실제 증명되는 것만**. 3~8개. 각 주장은 대본에 그대로 쓸 수 있는 짧은 한국어 구(8~20자).
   예: "레고처럼 맞물려 쌓인다", "뚜껑이 경첩식이라 안 잃어버린다", "작은 소품이 쏙 들어간다".
   같은 뜻은 하나로 합쳐라(장면마다 표현이 달라도 같은 주장이면 한 번호).
2) 장면마다 **그 장면이 화면으로 증명하는 주장 번호**를 단다. 여러 개 가능.
   도입·인물·포장·배경처럼 어떤 주장도 증명하지 않는 장면은 빈 배열.
   ★화면 태그에 근거가 없는 주장을 붙이지 마라.

출력 JSON만: {"claims":[{"id":"C1","text":"...","kind":"기능|특징|장점|효과"}],
            "seg_claims":{"<장면id>":["C1"], ...}}  — 장면을 빠짐없이.

[제품] %s

[장면 목록]
%s
"""

LINE_PROMPT = """아래는 한 쇼츠 대본의 줄들과, 이 제품 재료에서 뽑은 주장 목록이다.
줄마다 **그 줄이 말하는 주장 번호**를 단다(여러 개 가능).
훅·감정·연결·가격·CTA처럼 제품 주장을 말하지 않는 줄은 빈 배열 + needs_scene=false.
주장 목록에 없는 제품 주장을 말하는 줄은 빈 배열 + needs_scene=true + unlisted에 그 주장을 적어라.

출력 JSON만: {"lines":[{"i":0,"claims":["C2"],"needs_scene":true,"unlisted":""}, ...]} — 줄을 빠짐없이.

[주장 목록]
%s

[대본 줄]
%s
"""


def _loads(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


def _caller(provider):
    from google.genai import types
    cfg = types.GenerateContentConfig(response_mime_type="application/json")
    if provider == "vertex":
        from shopping_shorts import vertex_route
        cl, m = vertex_route.client(0), vertex_route.model()

        def call(prompt):
            return _loads(cl.models.generate_content(model=m, contents=prompt, config=cfg).text), m
        return call
    from shopping_shorts import comment_gen

    def call(prompt):
        last = None
        for n in range(6):                         # 일시 오류(503 수요 과다 등)면 다른 키로·간격 늘려
            key, _i = comment_gen._current_key_and_idx()
            if key is None:
                raise RuntimeError("키풀 비어 있음")
            try:
                r = comment_gen._client_for_key(key).models.generate_content(
                    model=GEMINI_MODEL, contents=prompt, config=cfg)
                return _loads(r.text), GEMINI_MODEL
            except Exception as e:                 # noqa: BLE001
                last = e
                time.sleep(8 * (n + 1))
        raise last
    return call


def job_material(db, jid):
    ej, ep = db.execute("select extract_json, edit_plan_json from mix_jobs where job_id=?", (jid,)).fetchone()
    ext, plan = json.loads(ej), json.loads(ep)
    segs, product = [], ""
    for sk, s in ext.items():
        if not isinstance(s, dict):
            continue
        product = product or (s.get("source_brief") or {}).get("product", "")
        for g in s.get("segments") or []:
            segs.append({"seg_id": g.get("seg_id"), "src": sk, "start": round(float(g.get("start") or 0), 2),
                         "end": round(float(g.get("end") or 0), 2), "scene_desc": g.get("scene_desc") or "",
                         "label": g.get("label") or "", "benefits": g.get("product_benefits") or [],
                         "change": g.get("change") or ""})
    beats = []
    for b in plan.get("beats") or []:
        p = b.get("primary") or {}
        need = sum(b.get("cap_durs") or []) or float(b.get("target_seconds") or 0)
        beats.append({"i": b.get("beat_idx"), "role": b.get("role"), "text": b.get("narration") or "",
                      "need": round(need, 2), "cur_seg": p.get("seg_id"),
                      "cur_len": round(float(p.get("end") or 0) - float(p.get("start") or 0), 2),
                      "fit_evidence": b.get("fit_evidence")})
    return product, segs, beats


def run(provider, jobs):
    import sqlite3
    db = sqlite3.connect(DB, uri=True)
    call = _caller(provider)
    out = {"provider": provider, "jobs": {}}
    for jid in jobs:
        product, segs, beats = job_material(db, jid)
        seg_txt = "\n".join(
            "[%s] %s %.1f~%.1f초 | 화면:%s | 역할:%s | 특장점:%s | 변화:%s" % (
                s["seg_id"], s["src"], s["start"], s["end"], s["scene_desc"][:90], s["label"],
                " / ".join(s["benefits"])[:120], s["change"][:60]) for s in segs)
        t0 = time.time()
        a, model = call(CLAIM_PROMPT % (product, seg_txt))
        claims_txt = "\n".join("%s %s" % (c.get("id"), c.get("text")) for c in a.get("claims") or [])
        lines_txt = "\n".join("%d: %s" % (k, b["text"]) for k, b in enumerate(beats))
        b2, _ = call(LINE_PROMPT % (claims_txt, lines_txt))
        out["jobs"][jid] = {"product": product, "model": model, "secs": round(time.time() - t0, 1),
                            "segs": segs, "beats": beats, "claims": a.get("claims") or [],
                            "seg_claims": a.get("seg_claims") or {}, "lines": b2.get("lines") or []}
        print(jid, provider, model, "주장", len(a.get("claims") or []), "장면태그", len(a.get("seg_claims") or {}),
              "/", len(segs), "줄", len(b2.get("lines") or []), "/", len(beats), "%.1fs" % (time.time() - t0),
              flush=True)
    path = "/tmp/claim_trial_%s.json" % provider
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("저장", path)


# ── 채점(순수 함수 — 로컬) ─────────────────────────────────────────────
def chains(segs, seg_claims, want):
    """같은 소스에서 '바로 다음 컷'이 계속 want 주장을 증명하는 동안 이어 붙인 길이들. [(길이, [id…])]"""
    by_src = {}
    for s in segs:
        by_src.setdefault(s["src"], []).append(s)
    out = []
    for lst in by_src.values():
        lst.sort(key=lambda s: s["start"])
        for k, s in enumerate(lst):
            if not set(seg_claims.get(s["seg_id"]) or []) & want:
                continue
            ids, total, j = [s["seg_id"]], s["end"] - s["start"], k
            while j + 1 < len(lst) and lst[j + 1]["start"] - lst[j]["end"] <= CHAIN_GAP \
                    and set(seg_claims.get(lst[j + 1]["seg_id"]) or []) & want:
                j += 1
                ids.append(lst[j]["seg_id"])
                total += lst[j]["end"] - lst[j]["start"]
            out.append((round(total, 2), ids))
    return out


def resolve(need, segs, seg_claims, want):
    """줄 하나가 꼬다리 없이 어디서 해결되나: 1한장면 · 2같은소스이어붙이기 · 3고르게늦추기 · 4다른소스합치기 · 5다시쓰기."""
    if not want:
        return "주장없음", 0
    lens = {s["seg_id"]: s["end"] - s["start"] for s in segs}
    cands = [sid for sid, cs in seg_claims.items() if set(cs or []) & want and sid in lens]
    if not cands:
        return "5다시쓰기(장면0)", 0
    if max(lens[c] for c in cands) >= need:
        return "1한장면", len(cands)
    best = max(t for t, _ in chains(segs, seg_claims, want))
    if best >= need:
        return "2같은소스이어붙이기", len(cands)
    if best * SLOW_MAX >= need or max(lens[c] for c in cands) * SLOW_MAX >= need:
        return "3고르게늦추기", len(cands)
    if sum(lens[c] for c in cands) >= need:
        return "4다른소스합치기", len(cands)
    return "5다시쓰기(길이부족)", len(cands)


def score(paths):
    import collections
    for path in paths:
        d = json.load(open(path, encoding="utf-8"))
        print("\n=====", d["provider"], path)
        tot = collections.Counter()
        cur = collections.Counter()
        for jid, j in d["jobs"].items():
            sc = {k: set(v or []) for k, v in j["seg_claims"].items()}
            tagged = sum(1 for s in j["segs"] if sc.get(s["seg_id"]))
            print("\n#", jid, j["product"], j["model"], "| 주장", len(j["claims"]),
                  "| 주장 붙은 장면 %d/%d" % (tagged, len(j["segs"])))
            for c in j["claims"]:
                n = sum(1 for v in sc.values() if c.get("id") in v)
                print("   %s %s (%s) — 장면 %d" % (c.get("id"), c.get("text"), c.get("kind"), n))
            lines = {int(x.get("i", -1)): x for x in j["lines"] if isinstance(x, dict)}
            for k, b in enumerate(j["beats"]):
                ln = lines.get(k, {})
                want = set(ln.get("claims") or [])
                how, n = resolve(b["need"], j["segs"], sc, want) if ln.get("needs_scene", True) else ("장면자유", 0)
                tot[how] += 1
                cur_ok = b["cur_seg"] in {sid for sid, cs in sc.items() if cs & want} if want else None
                short = b["cur_len"] < b["need"] - 0.05
                if want:
                    cur["주장줄"] += 1
                    cur["지금장면=같은주장"] += bool(cur_ok)
                    cur["지금장면이 줄보다 짧음(꼬다리)"] += short
                print("   %2d %-4s %.1fs %-18s 후보%2d | 지금 %s %.1fs%s | %s%s" % (
                    k, (b["role"] or "")[:4], b["need"], how, n, (b["cur_seg"] or "-")[-12:], b["cur_len"],
                    "" if cur_ok is None else (" ✓같은주장" if cur_ok else " ✗다른주장"),
                    b["text"][:40], (" | 목록밖:" + ln["unlisted"]) if ln.get("unlisted") else ""))
        print("\n합계 줄 해결:", dict(tot))
        print("지금 편성(주장 있는 줄 기준):", dict(cur))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], sys.argv[3:])
    else:
        score(sys.argv[2:])
