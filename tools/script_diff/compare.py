# -*- coding: utf-8 -*-
"""이야기 작가 대본이 씨앗과 얼마나 다른가 — 같은 입력으로 **진짜 모델**을 불러 비교한다.
  PC_ROOT=<다른 체크아웃> ../../.venv/Scripts/python.exe tools/script_diff/compare.py <sd_dump.json> [--out 결과.json]

2026-09-26 사장님: "대본이 씨앗이랑 거의 똑같다 — 차별 포인트는 기능·특징·장점" / "「OO의 정체」를 골랐는데 결과가 안 나온다".
입력(sd_dump.json): 작업별 씨앗 원문·제품·고른 스타일·매칭 job(추출) — 서버에서 읽기 전용으로 떠 온 것.
재는 것(대본마다):
  · 고조2·반전 줄이 **새 특징(씨앗에 없음)**을 쓰나 — line_groups × feats_meta.new (트랙 코드만 표시가 있다)
  · 반전 줄이 씨앗 마지막 포인트와 겹치는 비율(4글자 조각)
  · 대본 전체가 씨앗과 겹치는 비율(4글자 조각)
  · 고른 스타일 안의 첫 줄·마무리가 스타일 틀을 따르나
  · 특징 줄(고조·반전)의 컷이 그 특징의 근거 컷 안인가(트랙 코드만 feats_meta에 근거 컷이 있다)
모델 호출은 실제로 나간다(작업당 5회 안팎).
"""
import sys, os, json, re, pathlib, argparse
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser(); ap.add_argument("dump"); ap.add_argument("--out", default="")
args = ap.parse_args()
os.chdir(ROOT)                                   # .env·key_vault가 이 체크아웃 기준으로 키를 찾는다
from shopping_shorts import story_writer as sw

def grams(t, n=4):
    t = re.sub(r"[^가-힣A-Za-z0-9]", "", t or "")
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}

def share(a, b):
    ga = grams(a); return round(len(ga & grams(b)) / len(ga), 2) if ga else 0.0

def seed_last(s):
    parts = [p.strip() for p in re.split(r"[.!?\n]", s or "") if len(p.strip()) >= 8]
    return parts[-1] if parts else ""

D = json.load(open(args.dump, encoding="utf-8"))
res = []
for w in D["works"]:
    spines = [D["spines"][str(i)] for i in w["style_ids"] if D["spines"].get(str(i))]
    drafts, why = sw.make_drafts(spines, w["job"], 25, job_id=w["job_id"], preset="short",
                                 seed_text=w["seed_text"], seed_product=w["product"])
    print("\n" + "=" * 70 + "\n작업 %s (%s) — 씨앗 %d자 · why=%r" % (w["work_id"], w["product"], len(w["seed_text"]), why))
    for d in drafts:
        beats = d.get("beats") or []
        text = " ".join(b.get("text", "") for b in beats)
        fm = d.get("feats_meta") or []
        lg = d.get("line_groups") or []
        esc2 = [(b, lg[i] if i < len(lg) else -1) for i, b in enumerate(beats) if b.get("role") in ("고조2", "반전")]
        new_used = [bool(fm and 0 <= g < len(fm) and fm[g].get("new")) for _, g in esc2] if fm else None
        tw = " ".join(b.get("text", "") for b in beats if b.get("role") == "반전")
        lock_ok = None
        if fm:
            chk = [(set(b.get("src_segs") or []) <= set(fm[g]["cuts"])) for i, b in enumerate(beats)
                   for g in [lg[i] if i < len(lg) else -1] if 0 <= g < len(fm) and fm[g]["cuts"]]
            lock_ok = "%d/%d" % (sum(chk), len(chk))
        row = {"work": w["work_id"], "style": d.get("style_name"), "chars": len(text),
               "seed_share": share(text, w["seed_text"]), "twist_vs_seed_last": share(tw, seed_last(w["seed_text"])),
               "esc2_twist_new": new_used, "feats": [(f.get("name"), f.get("new"), f.get("videos")) for f in fm] or d.get("feat_names"),
               "cuts_in_evidence": lock_ok, "note": d.get("writer_note"),
               "lines": [(b.get("role"), b.get("text")) for b in beats]}
        res.append(row)
        print("\n── [%s] %d자 · 씨앗겹침 %.0f%% · 반전↔씨앗끝 %.0f%% · 고조2/반전 새특징 %s · 근거컷 %s"
              % (row["style"], row["chars"], row["seed_share"] * 100, row["twist_vs_seed_last"] * 100, new_used, lock_ok))
        print("   특징:", row["feats"])
        print("   note:", row["note"])
        for r, t in row["lines"]:
            print("   %-4s | %s" % (r, t))
if args.out:
    json.dump(res, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
