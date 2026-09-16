# -*- coding: utf-8 -*-
"""대본 옛/새 코드 배치 비교 하네스 (2026-09-16 사장님 "30개 먼저 해봐").

같은 재료(mix_jobs.extract_json)·같은 스타일·같은 키로 두 체크아웃을 각각 돌려 표로 비교한다.
라이브 DB는 **읽기만** 한다(generate_by_styles는 DB에 쓰지 않는다. 키 상태 파일은 원래 공유).

  select : 최근 실제 job N건 고르기 → jobs.json   (한 번만. 양쪽이 같은 목록을 쓴다)
  run    : --code old|new --jobs jobs.json --out out_old.json   (체크아웃마다 그 폴더에서 실행)
  report : out_old.json out_new.json → 표

새 코드 체크아웃은 DB_PATH·.env가 모듈 위치 기준이라(config.py·key_vault.py) data/·.env를 심볼릭 링크로 잇는다.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

#: AB_ROOT — 이 파일을 체크아웃 밖(/tmp)에 두고 돌릴 때 "어느 체크아웃의 코드·DB를 쓸지"를 정한다.
#:   라이브 워킹트리에 파일을 넣지 않기 위해서다(서버 워킹트리 오염 금지 규칙).
ROOT = Path(os.environ.get("AB_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

DB = ROOT / "shopping_shorts" / "data" / "reference.db"


def _shares_word(text, desc):
    """script_gate._shares_word 사본 — 옛 코드엔 없으므로 하네스가 양쪽에 같은 잣대를 댄다."""
    def _stems(s):
        out = set()
        for run in re.findall(r"[가-힣]{2,}", s or ""):
            for i in range(len(run) - 1):
                out.add(run[i:i + 2])
        out.update(re.findall(r"\d+", s or ""))
        return out
    return bool(_stems(text) & _stems(desc))


def _descs(sources):
    out = {}
    for s in sources:
        for x in (s.get("segments") or []):
            if isinstance(x, dict) and x.get("seg_id"):
                out[str(x["seg_id"])] = " ".join(
                    str(x.get(k) or "") for k in ("scene_desc", "change", "action", "use_point"))
    return out


def _sources(c, job_id):
    row = c.execute("select extract_json from mix_jobs where job_id=?", (job_id,)).fetchone()
    if not row or not row[0]:
        return []
    ex = json.loads(row[0])
    return [v for k, v in sorted(ex.items()) if isinstance(v, dict) and (v.get("segments") or [])]


def cmd_select(n, out):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute(
        "select m.job_id, m.created_at, m.product_json, p.work_id, p.state_json "
        "from mix_jobs m left join produce_works p on p.job_id = m.job_id "
        "where m.extract_json is not null and length(m.extract_json) > 2000 "
        "order by m.created_at desc limit ?", (n * 4,)).fetchall()
    from shopping_shorts.store import Store
    st = Store(DB)
    picked_jobs, seen_products = [], set()
    for job_id, created, product_json, work_id, state_json in rows:
        srcs = _sources(c, job_id)
        if len(srcs) < 1:
            continue
        # ★제품명은 재료 dict에 없다(앱이 _materials_for_generate로 따로 주입한다) — 2단계 화면이
        #   저장한 materials.topic_product가 정본. 없으면 그 job은 비교에서 뺀다(제품 모르면 판정 불가).
        product, s2 = "", {}
        try:
            s2 = (json.loads(state_json) if state_json else {}).get("s2") or {}
            product = ((s2.get("materials") or {}).get("topic_product") or "").strip()
        except Exception:
            pass
        if not product or product in seen_products:      # 같은 제품 중복 배제 → 재료 다양성
            continue
        style_ids = [int(x) for x in (s2.get("picked") or []) if str(x).isdigit()][:2]
        if len(style_ids) < 2:
            # 사장님이 안 고른 job은 화면과 같은 규칙(추천 상위 2)으로
            cat = (srcs[0].get("category") or "") if isinstance(srcs[0], dict) else ""
            auto = st.list_style_spines(category=cat or None) or st.list_style_spines(category=None)
            style_ids = [s["id"] for s in auto[:2]]
        if len(style_ids) < 2:
            continue
        seen_products.add(product)
        picked_jobs.append({"job_id": job_id, "work_id": work_id, "created": created,
                            "product": product, "style_ids": style_ids,
                            "sources": len(srcs), "scenes": sum(len(s["segments"]) for s in srcs)})
        if len(picked_jobs) >= n:
            break
    Path(out).write_text(json.dumps(picked_jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"선정 {len(picked_jobs)}건 → {out}")
    for j in picked_jobs:
        print(f"  {j['job_id']} {j['product'][:22]:22s} 스타일{j['style_ids']} 재료{j['sources']}편 장면{j['scenes']}")


def cmd_run(code, jobs_path, out, secs):
    from shopping_shorts import script_generate as SG
    from shopping_shorts.store import Store
    st = Store(DB)
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    jobs = json.loads(Path(jobs_path).read_text(encoding="utf-8"))
    results = []
    if Path(out).exists():                       # 이어 돌리기(중간에 끊겨도 앞 결과 보존)
        results = json.loads(Path(out).read_text(encoding="utf-8"))
    done = {r["job_id"] for r in results}
    for j in jobs:
        if j["job_id"] in done:
            continue
        srcs = _sources(c, j["job_id"])
        # 앱(_materials_for_generate)과 같게 재료마다 제품명을 실어 준다 — 주제 고정·소재 일치 판정이 이걸 본다.
        for s in srcs:
            s.setdefault("product", j["product"])
            s.setdefault("topic_product", j["product"])
        styles = [s for s in st.list_style_spines(category=None) if s["id"] in j["style_ids"]]
        descs = _descs(srcs)
        reasons = []
        t = time.time()
        try:
            outs = SG.generate_by_styles(srcs, styles, target_seconds=secs, reasons=reasons,
                                         grounded=True, product=j["product"])
            err = ""
        except Exception as e:      # noqa: BLE001 — 하네스는 죽지 않고 기록한다
            outs, err = [], f"{type(e).__name__}: {e}"
        el = time.time() - t
        drafts = []
        for o in outs or []:
            beats = o.get("beats") or []
            withs = [b for b in beats if b.get("src_seg")]
            rel = sum(1 for b in withs if _shares_word(
                b.get("text", ""), descs.get(str(b.get("src_seg")).split(",")[0].strip(), "")))
            drafts.append({"style": o.get("style_name"), "passed": o.get("passed"),
                           "tries": len(o.get("tries") or []), "beats": len(beats),
                           "with_scene": len(withs), "related": rel,
                           "lines": [{"role": b.get("role"), "needs_scene": b.get("needs_scene"),
                                      "src_seg": b.get("src_seg"), "text": b.get("text")} for b in beats]})
        results.append({"job_id": j["job_id"], "product": j["product"], "style_ids": j["style_ids"],
                        "code": code, "elapsed": round(el, 1), "n_out": len(outs or []),
                        "n_req": len(styles), "reasons": reasons, "error": err, "drafts": drafts})
        Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{code}] {len(results)}/{len(jobs)} {j['job_id']} {j['product'][:18]:18s} "
              f"{el:5.1f}s 안{len(outs or [])}/{len(styles)} "
              f"{'ERR ' + err[:40] if err else ''}{[r.get('kind') for r in reasons] if reasons else ''}",
              flush=True)
    print(f"[{code}] 완료 {len(results)}건 → {out}")


def cmd_report(old_path, new_path):
    old = {r["job_id"]: r for r in json.loads(Path(old_path).read_text(encoding="utf-8"))}
    new = {r["job_id"]: r for r in json.loads(Path(new_path).read_text(encoding="utf-8"))}
    ids = [k for k in old if k in new]

    def agg(rs):
        n = len(rs)
        full = sum(1 for r in rs if r["n_out"] == r["n_req"])
        zero = sum(1 for r in rs if r["n_out"] == 0)
        el = sum(r["elapsed"] for r in rs) / max(1, n)
        withs = sum(d["with_scene"] for r in rs for d in r["drafts"])
        rel = sum(d["related"] for r in rs for d in r["drafts"])
        beats = sum(d["beats"] for r in rs for d in r["drafts"])
        tries = sum(d["tries"] for r in rs for d in r["drafts"]) / max(1, sum(len(r["drafts"]) for r in rs))
        fatal = {}
        for r in rs:
            for x in r["reasons"]:
                fatal[x.get("kind") or x.get("reason") or "?"] = fatal.get(x.get("kind") or x.get("reason") or "?", 0) + 1
        return dict(n=n, full=full, zero=zero, el=el, withs=withs, rel=rel, beats=beats, tries=tries, fatal=fatal)
    a, b = agg([old[i] for i in ids]), agg([new[i] for i in ids])
    print(f"비교 대상 {len(ids)}건 (양쪽 다 돌아간 job)")
    print(f"{'지표':28s} {'옛(라이브)':>14s} {'새(트랙)':>14s}")
    print(f"{'요청한 안이 다 나온 job':28s} {a['full']:>10d}/{a['n']:<3d} {b['full']:>10d}/{b['n']:<3d}")
    print(f"{'0안 job':28s} {a['zero']:>14d} {b['zero']:>14d}")
    print(f"{'평균 걸린 시간(초)':28s} {a['el']:>14.1f} {b['el']:>14.1f}")
    print(f"{'안당 평균 재시도 기록':28s} {a['tries']:>14.2f} {b['tries']:>14.2f}")
    print(f"{'장면 붙은 줄 / 전체 줄':28s} {a['withs']:>7d}/{a['beats']:<6d} {b['withs']:>7d}/{b['beats']:<6d}")
    ra = a['rel'] / max(1, a['withs']); rb = b['rel'] / max(1, b['withs'])
    print(f"{'그중 장면 설명과 겹침(≈맞음)':28s} {a['rel']:>7d} {ra:5.0%}   {b['rel']:>7d} {rb:5.0%}")
    print(f"{'치명 반려 종류':28s} {str(a['fatal']):>14s} {str(b['fatal']):>14s}")
    print()
    print("job별  (안 old→new | 초 old→new | 겹침비율 old→new)")
    for i in ids:
        o, n = old[i], new[i]
        def rr(r):
            w = sum(d["with_scene"] for d in r["drafts"]); k = sum(d["related"] for d in r["drafts"])
            return f"{k}/{w}" if w else "-"
        print(f"  {i} {o['product'][:16]:16s} 안 {o['n_out']}/{o['n_req']}→{n['n_out']}/{n['n_req']} | "
              f"{o['elapsed']:5.1f}→{n['elapsed']:5.1f}s | 겹침 {rr(o)}→{rr(n)}"
              f"{'  ★새코드 반려:' + str([x.get('kind') for x in n['reasons']]) if n['reasons'] else ''}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select"); s.add_argument("--n", type=int, default=30); s.add_argument("--out", default="/tmp/ab_jobs.json")
    r = sub.add_parser("run"); r.add_argument("--code", required=True); r.add_argument("--jobs", required=True)
    r.add_argument("--out", required=True); r.add_argument("--secs", type=int, default=25)
    p = sub.add_parser("report"); p.add_argument("old"); p.add_argument("new")
    a = ap.parse_args()
    if a.cmd == "select":
        cmd_select(a.n, a.out)
    elif a.cmd == "run":
        cmd_run(a.code, a.jobs, a.out, a.secs)
    else:
        cmd_report(a.old, a.new)
