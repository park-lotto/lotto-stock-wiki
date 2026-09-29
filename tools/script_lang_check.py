# -*- coding: utf-8 -*-
"""이야기 작가 대본 언어 점검 — 같은 씨앗으로 N회 돌려 "영어 섞인 대본 수 / 전체"를 잰다(관제 039, 2026-09-29).

제보(이정민님 09-28~29): "대본 뽑으면 영어가 나온다". 씨앗(s2.seed.text)이 영어인 작업에서 재현한다.

사용:
  py tools/script_lang_check.py <jobs.json> <job_id> --runs 10 [--out 결과.json] [--keypool]

  jobs.json = {job_id: {"job": mix_jobs 행(extract_json 문자열 등), "work_state": produce_works state_json}}
              (서버에서 읽기 전용으로 뽑아 온 사본)

호출 모양은 app.py `api_wiki_generate` 의 이야기 작가 호출 그대로다:
  story_writer.make_drafts(_picked, _job, target_seconds, job_id=_jid, preset=length_preset,
                           seed_text=it.full_text, seed_product=_sources_product(_src))
  - _picked : work 의 s2.drafts 에서 style_id 가 있는 것 → 스파인. ★로컬 DB에 스파인 행이 없어
              tools/spine_presets/yt_templates_2026-09-23.json 의 틀로 대신 만든다(이름은 draft 의 style_name,
              no_cta 는 draft platform=="yt"). 라이브 DB 의 틀이 그 뒤에 바뀌었으면 첫 줄·마무리 틀만 다를 수 있다.
  - _job    : extract 는 s2.materials.sources 의 제품명과 같은 재료만 남긴다(라이브 _materials_for_generate 가
              topic 으로 재료를 거르는 것을 흉내 — 정확한 source_id 필터는 아니다).
  - seed_product : s2.materials.topic_product
  - 모델   : 기본 Vertex(gemini-3.6-flash, 로컬 ADC) — 라이브 _call_json 첫 경로와 같다. --keypool 이면 키풀.
  - 컷 AI 매칭(ai_match)은 대본 글과 무관해 건너뛴다(코드 매칭만) — 호출 비용 절약.

잰다: 줄마다 글자 중 한글 비율. 판정은 story_writer.non_korean_lines 가 있으면 그것(정본), 없으면 같은 규칙
(글자 4개 이상인 줄에서 한글 < 50%)으로 센다.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


def _ko_share(text):
    letters = [c for c in str(text or "") if c.isalpha()]
    if not letters:
        return 1.0
    return sum(1 for c in letters if "가" <= c <= "힣") / len(letters)


def bad_lines(lines):
    from shopping_shorts import story_writer as sw
    f = getattr(sw, "non_korean_lines", None)
    if f:
        return f(lines)
    return [t for t in lines if len([c for c in t if c.isalpha()]) >= 4 and _ko_share(t) < 0.5]


def spine_for(style_id, style_name, platform):
    spec = json.load(open(HERE / "spine_presets" / "yt_templates_2026-09-23.json", encoding="utf-8"))
    d = spec["spines"].get(str(style_id)) or {}
    tp = dict(spec.get(d.get("_base") or "", {}) or {})
    tp.update({k: v for k, v in d.items() if not k.startswith("_")})
    return {"id": int(style_id), "name": style_name or "", "no_cta": platform == "yt",
            "beat_roles": list(tp.keys()), "templates": tp}


def build_inputs(rec):
    row = rec["job"]
    ws = rec["work_state"]
    ws = json.loads(ws) if isinstance(ws, str) else ws
    s2 = ws.get("s2") or {}
    mat = s2.get("materials") or {}
    ex = json.loads(row["extract_json"]) if isinstance(row.get("extract_json"), str) else row.get("extract_json")
    prods = {(s.get("product") or "").strip() for s in (mat.get("sources") or [])}
    if prods:
        ex = {k: v for k, v in ex.items()
              if ((v or {}).get("source_brief") or {}).get("product", "").strip() in prods} or ex
    job = {"job_id": row.get("job_id"), "extract": ex, "backbone_main": row.get("backbone_main"),
           "customer_id": row.get("customer_id")}
    picked = []
    preset = "short"
    for dr in s2.get("drafts") or []:
        preset = dr.get("length_preset") or preset
        if dr.get("style_id") and not picked:
            picked.append(spine_for(dr["style_id"], dr.get("style_name"), dr.get("platform")))
    seed = s2.get("seed") or {}
    return picked, job, row.get("target_seconds") or 25, preset, seed.get("text") or "", mat.get("topic_product") or ""


def patch_env(keypool):
    from shopping_shorts import ai_match, vertex_route
    ai_match.match = lambda *a, **k: None          # 컷 AI 매칭 생략(글과 무관)
    if keypool:
        vertex_route.on = lambda op, cid=None: False
    else:
        vertex_route.on = lambda op, cid=None: True
        vertex_route.model = lambda: vertex_route.DEFAULT_MODEL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("job_id")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--out", default="")
    ap.add_argument("--keypool", action="store_true")
    a = ap.parse_args()
    patch_env(a.keypool)
    from shopping_shorts import story_writer as sw
    rec = json.load(open(a.jobs, encoding="utf-8"))[a.job_id]
    picked, job, secs, preset, seed_text, seed_product = build_inputs(rec)
    print("씨앗 %d자 한글 %.0f%% · 스타일 %s · preset %s · 제품 %s · 재료 %s" % (
        len(seed_text), 100 * _ko_share(seed_text), [p["name"] for p in picked], preset, seed_product,
        list(job["extract"].keys())))
    results = []
    for i in range(a.runs):
        t0 = time.time()
        try:
            drafts, why = sw.make_drafts(picked, job, secs, job_id=a.job_id, preset=preset,
                                         seed_text=seed_text, seed_product=seed_product)
        except Exception as e:      # noqa: BLE001 — 측정 도구: 실패도 한 건으로 기록
            drafts, why = [], "예외 %r" % e
        for d in drafts:
            lines = [b.get("text") or "" for b in (d.get("beats") or []) if (b.get("text") or "").strip()]
            bad = bad_lines(lines)
            ko = _ko_share("".join(lines))
            results.append({"run": i, "style": (d.get("spine") or {}).get("name") or d.get("style_name")
                            or ("씨앗 결" if d.get("auto_pick") else "스타일"),
                            "auto": d.get("auto_pick"), "ko": round(ko, 3), "bad": bad, "lines": lines,
                            "note": d.get("writer_note")})
            print("run%d %-6s 한글 %3.0f%% 영어줄 %d  첫줄: %s" % (
                i, "씨앗결" if d.get("auto_pick") else "스타일", 100 * ko, len(bad), lines[0][:50] if lines else ""))
        if not drafts:
            results.append({"run": i, "fail": why})
            print("run%d 실패: %s" % (i, why))
        print("   (%.0fs)" % (time.time() - t0))
    ok = [r for r in results if "lines" in r]
    mixed = [r for r in ok if r["bad"]]
    print("\n== 영어 섞인 대본 %d / %d (실패 %d) ==" % (len(mixed), len(ok), len(results) - len(ok)))
    for r in mixed:
        print("  run%d %s: %s" % (r["run"], "씨앗결" if r["auto"] else "스타일", r["bad"][:3]))
    if a.out:
        Path(a.out).write_text(json.dumps({"job": a.job_id, "results": results}, ensure_ascii=False, indent=1),
                               encoding="utf-8")


if __name__ == "__main__":
    main()
