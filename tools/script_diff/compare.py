# -*- coding: utf-8 -*-
"""이야기 작가 대본이 씨앗과 얼마나 다른가 — 같은 입력으로 **진짜 모델**을 불러, 그 작업에 실제로 나왔던 라이브 대본과 비교한다.
  ../../.venv/Scripts/python.exe tools/script_diff/compare.py <sd_dump.json> [--out 결과.json] [--limit N]
  (입력은 tools/script_diff/dump_works.py 가 서버에서 읽기 전용으로 떠 온 것)

2026-09-26 사장님: "대본이 씨앗이랑 거의 똑같다 — 차별 포인트는 기능·특징·장점" / "「OO의 정체」를 골랐는데 결과가 안 나온다".
재는 것(안마다, 라이브 대본과 새 대본을 **같은 잣대**로):
  · 반전·고조2가 씨앗이 이미 말한 내용을 쓰나 — 새 실행이 뽑은 씨앗 셀링포인트 목록의 특징 낱말이 2개 이상 나오면 '씨앗 내용'
    (story_writer._seed_word_hits — 생성기의 검사와 같은 함수)
  · 고른 스타일 안: 첫 줄이 스타일 제목 틀을 따르나(style_hook_line으로 채운 문장과 같은가 / 틀 고정 낱말 절반 이상)
  · 새 대본만: 특징 줄(고조·반전) 컷이 그 특징의 근거 컷 안인가 · 새 특징 수 · 재작성·고정 기록
모델 호출은 실제로 나간다(작업당 5회 안팎). 작업 사이 순서대로 돈다(동시에 돌리면 API 오류가 섞였다, 09-26).
"""
import sys, os, json, re, pathlib, argparse
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser(); ap.add_argument("dump"); ap.add_argument("--out", default=""); ap.add_argument("--limit", type=int, default=0)
args = ap.parse_args()
os.chdir(ROOT)
from shopping_shorts import story_writer as sw


def text_of(d, roles):
    return " ".join(b.get("text", "") for b in d.get("beats") or [] if b.get("role") in roles)


def title_ok(d, sp):
    """첫 줄이 스타일 제목 틀을 따르나 — 틀 고정 낱말(빈칸 뺀 2글자↑)이 절반 이상 들어갔나."""
    tpl = (sp or {}).get("templates") if isinstance((sp or {}).get("templates"), dict) else {}
    hook = re.sub(r"\s+", "", ((d.get("beats") or [{}])[0].get("text") or ""))
    for t in tpl.get("title") or []:
        ws = [re.sub(r"\s+", "", w) for w in re.split(r"\{[^}]*\}", t) if len(re.sub(r"[^가-힣A-Za-z0-9]", "", w)) >= 2]
        ws = [w for part in ws for w in part.split() or [part]]
        if ws and sum(1 for w in ws if w in hook) * 2 >= len(ws):
            return True
    return False


D = json.load(open(args.dump, encoding="utf-8"))
works = D["works"][:args.limit] if args.limit else D["works"]
res = []
for w in works:
    spines = [D["spines"][str(i)] for i in w["style_ids"] if D["spines"].get(str(i))]
    sp_by = {str(s.get("id")): s for s in spines}
    try:
        drafts, why = sw.make_drafts(spines, w["job"], 25, job_id=w["job_id"], preset="short",
                                     seed_text=w["seed_text"], seed_product=w["product"])
    except Exception as e:      # noqa: BLE001 — 한 작업 실패가 비교 전체를 막지 않게
        drafts, why = [], "예외 %r" % e
    pts = next((d.get("seed_points") for d in drafts if d.get("seed_points")), []) or []
    print("\n" + "=" * 70 + "\n작업 %s (%s) — why=%r\n씨앗 셀링포인트: %s" % (w["work_id"], w["product"], why, pts))
    for kind, ds in (("라이브", w.get("old_drafts") or []), ("수정본", drafts)):
        for d in ds:
            sp = sp_by.get(str(d.get("style_id"))) if d.get("style_id") is not None else None
            tw_hits = sw._seed_word_hits(text_of(d, ("반전",)), pts, w["product"])
            e2_hits = sw._seed_word_hits(text_of(d, ("고조2",)), pts, w["product"])
            fm, lg = d.get("feats_meta") or [], d.get("line_groups") or []
            ev = None
            if fm:
                chk = [set(b.get("src_segs") or []) <= set(fm[g]["cuts"]) for i, b in enumerate(d.get("beats") or [])
                       for g in [lg[i] if i < len(lg) else -1] if 0 <= g < len(fm) and fm[g]["cuts"]]
                ev = [sum(chk), len(chk)]
            row = {"work": w["work_id"], "kind": kind, "style": d.get("style_name"), "has_style": sp is not None,
                   "twist_seed_hits": tw_hits, "esc2_seed_hits": e2_hits,
                   "title_ok": title_ok(d, sp) if sp else None, "evidence": ev,
                   "n_new": sum(1 for f in fm if f.get("new")) if fm else None,
                   "note": d.get("writer_note"), "hook": ((d.get("beats") or [{}])[0].get("text")),
                   "twist": text_of(d, ("반전",)), "esc2": text_of(d, ("고조2",))}
            res.append(row)
            print("  [%s] %-28s 반전씨앗낱말 %-18s 고조2씨앗낱말 %-18s 스타일첫줄 %s 근거컷 %s 새특징 %s"
                  % (kind, (row["style"] or "")[:28], tw_hits, e2_hits, row["title_ok"], ev, row["n_new"]))
            print("        첫줄: %s\n        반전: %s" % (row["hook"], row["twist"][:90]))

def agg(kind):
    rs = [r for r in res if r["kind"] == kind]
    n = len(rs)
    tw = sum(1 for r in rs if len(r["twist_seed_hits"]) >= 2)
    e2 = sum(1 for r in rs if len(r["esc2_seed_hits"]) >= 2)
    st = [r for r in rs if r["has_style"]]
    so = sum(1 for r in st if r["title_ok"])
    ev = [r["evidence"] for r in rs if r["evidence"]]
    evs = "%d/%d" % (sum(a for a, b in ev), sum(b for a, b in ev)) if ev else "-"
    return "%s: %d안 · 반전이 씨앗 내용 %d · 고조2가 씨앗 내용 %d · 스타일 첫줄 준수 %d/%d · 특징줄 근거컷 %s" % (kind, n, tw, e2, so, len(st), evs)

print("\n" + "#" * 70)
print(agg("라이브")); print(agg("수정본"))
if args.out:
    json.dump(res, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
