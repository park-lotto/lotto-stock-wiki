# -*- coding: utf-8 -*-
"""한 편 안 장면 반복·소스 배분 검사 (카드 033, 2026-09-29).

고객 제보: "같은 영상이 반복돼 재사용된다 / 소스 6개 넣었는데 롱폼 1개에서 대부분 가져온다".
3단계 편성(edit_plan)과 실제 완성본 컷 지도(clean_base.json)를 보고 재는 **독립 검사기**다.
주인 함수(shopping_shorts/backbone.py:finalize_scenes)의 코드를 빌려 쓰지 않는다 — 고친 코드로
자기 자신을 재면 아무것도 안 잰다(0순위-A1c). 판정 규칙은 여기서 따로 센다.

입력:
    job.json        = {edit_plan, extract{sN:{video_id, segments}}, ...}  (DB mix_jobs 행을 떠 온 것)
    clean_base.json = (선택) 완성본 컷 지도 {cuts:[{video_id, beat_idx, src, dur, ...}]}

판정(편성 기준):
    PASS = 같은 seg_id 재사용 0 · 같은 scene_desc 재사용 0 · 안 쓴 소스 0
    칸 재료는 렌더와 같은 우선순위로 본다: scene_override 가 있으면 그것, 없으면 primary+alternates.

--apply: edit_plan beats 에 finalize_scenes 를 적용한 뒤 같은 판정을 한 번 더 보여 준다(전/후 대조).
         scene_override(사람 편성 저장본)는 3단계 생성 시점엔 없던 것이라 지우고 적용한다(그 사실을 출력에 적는다).

--batch SRC: 여러 job 을 한 번에 — 생성기(generator)별로 반복 job 수·안 쓴 소스 job 수를 표로.
         SRC = 폴더(안의 *.json 전부) · .jsonl(한 줄 = job 하나) · job 목록 .json 배열 · '-'(표준입력 JSONL/배열).
         job 은 {edit_plan, extract} 또는 DB 행 모양 {edit_plan_json, extract_json(문자열)} 둘 다 받는다.
         --apply 를 같이 주면 [생성본 → finalize_scenes 후] 열이 붙는다(상속 job 은 mode="inherit").

사용:
    py tools/scene_repeat_audit.py <job.json> [--clean-base <clean_base.json>] [--apply]
    py tools/scene_repeat_audit.py --batch <폴더|jobs.jsonl|-> [--apply]
종료코드: 0 = PASS, 1 = FAIL (편성 기준; --apply 면 적용 후 기준 · 배치는 항상 0)
"""
import argparse
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:      # noqa: BLE001 — 콘솔 인코딩 못 바꾸면 기본대로
    pass


def _norm_desc(d):
    return " ".join(str(d or "").split())


def _sources(job):
    ex = job.get("extract") or {}
    vals = list(ex.values()) if isinstance(ex, dict) else list(ex)
    out = []
    for i, s in enumerate(vals):
        if not isinstance(s, dict):
            continue
        vid = s.get("video_id") or "s%d" % i
        segs = [g for g in (s.get("segments") or []) if isinstance(g, dict) and g.get("seg_id")]
        out.append({"video_id": vid, "segments": segs})
    return out


def _seg_index(sources):
    idx = {}
    for s in sources:
        for g in s["segments"]:
            idx[g["seg_id"]] = dict(g, video_id=s["video_id"])
    return idx


def beat_material(beat):
    """렌더가 재료로 쓰는 조각 목록 — scene_override 우선(video_assemble._beat_material 과 같은 우선순위)."""
    over = beat.get("scene_override")
    if over:
        return [c for c in over if isinstance(c, dict) and c.get("seg_id")], "scene_override"
    out = []
    p = beat.get("primary") or {}
    if p.get("seg_id"):
        out.append(p)
    out += [a for a in (beat.get("alternates") or []) if isinstance(a, dict) and a.get("seg_id")]
    return out, "primary+alternates"


def audit_plan(beats, sources, seg_idx):
    rows = []
    seg_uses = defaultdict(list)
    desc_uses = defaultdict(list)
    src_count = Counter()
    for bi, b in enumerate(beats):
        mat, where = beat_material(b)
        for k, c in enumerate(mat):
            sid = c["seg_id"]
            info = seg_idx.get(sid, {})
            vid = c.get("video_id") or info.get("video_id") or "?"
            desc = _norm_desc(c.get("scene_desc") or info.get("scene_desc"))
            dur = float(c.get("end") or 0) - float(c.get("start") or 0)
            rows.append({"beat": b.get("beat_idx", bi), "k": k, "vid": vid, "sid": sid,
                         "dur": round(dur, 2), "desc": desc, "where": where,
                         "role": "P" if k == 0 else "A"})
            seg_uses[sid].append(b.get("beat_idx", bi))
            if desc:
                desc_uses[desc].append((b.get("beat_idx", bi), sid))
            src_count[vid] += 1
    seg_rep = {s: v for s, v in seg_uses.items() if len(v) > 1}
    desc_rep = {d: v for d, v in desc_uses.items() if len({x[1] for x in v}) > 1 or len(v) > 1}
    # 같은 seg 재사용은 seg_rep 에서 이미 센다 — desc 반복은 **다른 seg** 끼리만 따로 본다
    desc_rep = {d: v for d, v in desc_rep.items() if len({x[1] for x in v}) > 1}
    all_vids = [s["video_id"] for s in sources if s["segments"]]
    unused = [v for v in all_vids if src_count.get(v, 0) == 0]
    return {"rows": rows, "seg_rep": seg_rep, "desc_rep": desc_rep, "src_count": src_count,
            "all_vids": all_vids, "unused": unused,
            "ok": not seg_rep and not desc_rep and not unused}


def print_plan_report(title, rep):
    print("=" * 78)
    print(title)
    print("=" * 78)
    print("칸 | 자리 | 소스 | seg | 초 | 설명(앞 28자) | 재료출처")
    for r in rep["rows"]:
        mark = ""
        if r["sid"] in rep["seg_rep"]:
            mark = "  <== 같은 seg 재사용"
        elif r["desc"] in rep["desc_rep"]:
            mark = "  <== 같은 설명 재사용"
        print("%2s | %s | %s | %s | %5.2f | %s | %s%s" % (
            r["beat"], r["role"], r["vid"], r["sid"].rsplit("-", 1)[-1] if "-" in r["sid"] else r["sid"],
            r["dur"], r["desc"][:28], r["where"], mark))
    print("-" * 78)
    print("같은 seg 재사용: %d건" % len(rep["seg_rep"]))
    for s, v in rep["seg_rep"].items():
        print("   %s  칸 %s" % (s, v))
    print("같은 설명(다른 seg) 재사용: %d건" % len(rep["desc_rep"]))
    for d, v in rep["desc_rep"].items():
        print("   '%s'  %s" % (d[:40], v))
    total = sum(rep["src_count"].values()) or 1
    print("소스별 컷 수: " + ", ".join("%s=%d(%.0f%%)" % (v, rep["src_count"].get(v, 0),
                                                       100.0 * rep["src_count"].get(v, 0) / total)
                                    for v in rep["all_vids"]))
    print("안 쓴 소스: %s" % (rep["unused"] or "없음"))
    print("판정(편성): %s" % ("PASS" if rep["ok"] else "FAIL"))


def audit_clean_base(cb, sources, seg_idx):
    """완성본 컷 지도 — 컷의 원본 시각(src)이 어느 seg 안에 있나로 재사용을 센다."""
    by_vid = defaultdict(list)
    for s in sources:
        for g in s["segments"]:
            by_vid[s["video_id"]].append(g)
    cuts = cb.get("cuts") or []
    seg_beats = defaultdict(set)
    src_count = Counter()
    rows = []
    for c in cuts:
        vid, src = c.get("video_id"), float(c.get("src") or 0)
        hit = next((g["seg_id"] for g in by_vid.get(vid, [])
                    if float(g.get("start") or 0) - 1e-3 <= src < float(g.get("end") or 0) - 1e-3), None)
        rows.append((c.get("beat_idx"), vid, hit, round(src, 2), round(float(c.get("dur") or 0), 2)))
        src_count[vid] += 1
        if hit:
            seg_beats[hit].add(c.get("beat_idx"))
    rep = {s: sorted(v) for s, v in seg_beats.items() if len(v) > 1}
    all_vids = [s["video_id"] for s in sources if s["segments"]]
    unused = [v for v in all_vids if src_count.get(v, 0) == 0]
    print("=" * 78)
    print("완성본 컷 지도(clean_base) — 컷 %d개" % len(cuts))
    print("=" * 78)
    for r in rows:
        print("칸 %2s | %s | %s | src %7.2f | %4.2f초%s" % (
            r[0], r[1], r[2], r[3], r[4], "  <== 다른 칸과 같은 seg" if r[2] in rep else ""))
    print("-" * 78)
    total = sum(src_count.values()) or 1
    print("여러 칸에 쓰인 seg: %d건 %s" % (len(rep), rep))
    print("소스별 컷 수: " + ", ".join("%s=%d(%.0f%%)" % (v, src_count.get(v, 0),
                                                       100.0 * src_count.get(v, 0) / total) for v in all_vids))
    print("안 쓴 소스: %s" % (unused or "없음"))
    ok = not rep and not unused
    print("판정(완성본): %s" % ("PASS" if ok else "FAIL"))
    return ok


def _norm_job(job):
    """DB 행 모양(edit_plan_json·extract_json 문자열)도 받는다."""
    job = dict(job or {})
    for k in ("edit_plan", "extract"):
        if not job.get(k) and isinstance(job.get(k + "_json"), str):
            try:
                job[k] = json.loads(job[k + "_json"])
            except ValueError:
                job[k] = None
    return job


def _mode_of(plan):
    return "inherit" if (plan or {}).get("generator") == "inherit" else "default"


def repeat_adjacency(beats, rep):
    """반복 seg 를 칸 위치로 가른다 — 붙은 칸(모든 연속 등장이 바로 옆 칸)/떨어진 칸(하나라도 떨어짐).
    같은 칸 안 두 번은 떨어진 칸으로 센다(렌더는 칸이 달라지면 처음부터 다시 튼다 — 칸 안도 재생 구간이 겹친다)."""
    pos = {b.get("beat_idx", i): i for i, b in enumerate(beats)}
    adj = apart = 0
    for sid, bis in rep["seg_rep"].items():
        ps = [pos.get(x, -99) for x in bis]
        pairs = list(zip(ps, ps[1:]))
        if pairs and all(q - p == 1 for p, q in pairs):
            adj += 1
        else:
            apart += 1
    return adj, apart


def _iter_jobs(src):
    """배치 입력 → (이름, job) 들."""
    def _from_text(name, text):
        text = text.strip()
        if not text:
            return
        if text[0] == "[":
            for i, j in enumerate(json.loads(text)):
                yield "%s#%d" % (name, i), j
            return
        if text[0] == "{" and "\n" not in text.strip():
            yield name, json.loads(text)
            return
        try:
            yield name, json.loads(text)          # 파일 하나 = job 하나(여러 줄 JSON)
            return
        except ValueError:
            pass
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if line:
                yield "%s#%d" % (name, i), json.loads(line)
    if src == "-":
        yield from _from_text("stdin", sys.stdin.read())
        return
    p = Path(src)
    if p.is_dir():
        for f in sorted(p.glob("*.json")) + sorted(p.glob("*.jsonl")):
            yield from _from_text(f.name, f.read_text(encoding="utf-8"))
    else:
        yield from _from_text(p.name, p.read_text(encoding="utf-8"))


def run_batch(src, apply=False):
    backbone = None
    if apply:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from shopping_shorts import backbone
    rows = defaultdict(lambda: Counter())
    bad = []
    for name, raw in _iter_jobs(src):
        job = _norm_job(raw)
        plan = job.get("edit_plan") or {}
        beats = plan.get("beats") or []
        if not beats or not job.get("extract"):
            bad.append(name)
            continue
        sources = _sources(job)
        seg_idx = _seg_index(sources)
        g = plan.get("generator") or "?"
        r = rows[g]
        r["jobs"] += 1
        saved = audit_plan(beats, sources, seg_idx)
        gen = copy.deepcopy(beats)
        for b in gen:
            b.pop("scene_override", None)
        base = audit_plan(gen, sources, seg_idx)
        for tag, rep, bs in (("저장", saved, beats), ("생성", base, gen)):
            r[tag + "_반복job"] += bool(rep["seg_rep"])
            r[tag + "_설명반복job"] += bool(rep["desc_rep"])
            r[tag + "_미사용job"] += bool(rep["unused"])
            a_, p_ = repeat_adjacency(bs, rep)
            r[tag + "_반복seg"] += len(rep["seg_rep"])
            r[tag + "_붙은"] += a_
            r[tag + "_떨어진"] += p_
        if apply:
            frep = {}
            after_beats = backbone.finalize_scenes(gen, sources, report=frep, mode=_mode_of(plan))
            aft = audit_plan(after_beats, sources, seg_idx)
            a_, p_ = repeat_adjacency(after_beats, aft)
            r["후_반복job"] += bool(aft["seg_rep"])
            r["후_설명반복job"] += bool(aft["desc_rep"])
            r["후_미사용job"] += bool(aft["unused"])
            r["후_반복seg"] += len(aft["seg_rep"])
            r["후_붙은"] += a_
            r["후_떨어진"] += p_
            r["후_primary못바꿈job"] += bool(frep.get("primary_kept"))
            same = (len(after_beats) == len(gen)
                    and [b.get("narration") for b in after_beats] == [b.get("narration") for b in gen])
            r["후_불변식깨짐job"] += (not same)
    tags = [("저장", "저장본 재료(scene_override 우선)"), ("생성", "생성본 primary+alternates")]
    if apply:
        tags.append(("후", "finalize_scenes 후"))
    print("생성기 | 기준 | job | 반복 job | 반복 seg(붙은/떨어진) | 같은 설명 반복 job | 안 쓴 소스 job")
    for g in sorted(rows):
        r = rows[g]
        for tag, label in tags:
            print("%s | %s | %d | %d | %d(%d/%d) | %d | %d" % (
                g, label, r["jobs"], r[tag + "_반복job"], r[tag + "_반복seg"], r[tag + "_붙은"],
                r[tag + "_떨어진"], r[tag + "_설명반복job"], r[tag + "_미사용job"]))
        if apply:
            print("%s | 마감 뒤 경보 | primary 못 바꾼 job %d · 불변식(칸 수·대사) 깨진 job %d" % (
                g, r["후_primary못바꿈job"], r["후_불변식깨짐job"]))
    if bad:
        print("건너뜀(edit_plan·extract 없음) %d건: %s" % (len(bad), ", ".join(bad[:10])))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("job", nargs="?")
    ap.add_argument("--clean-base", default=None)
    ap.add_argument("--apply", action="store_true", help="finalize_scenes 적용 전/후 대조")
    ap.add_argument("--batch", default=None, help="폴더 · .jsonl · job 배열 .json · '-'(표준입력)")
    a = ap.parse_args(argv)
    if a.batch:
        run_batch(a.batch, apply=a.apply)
        return 0
    if not a.job:
        ap.error("job.json 경로 또는 --batch 가 필요하다")
    job = _norm_job(json.loads(Path(a.job).read_text(encoding="utf-8")))
    plan = job.get("edit_plan") or {}
    beats = plan.get("beats") or []
    sources = _sources(job)
    seg_idx = _seg_index(sources)
    print("job: %s · generator=%s · 칸 %d개 · 소스 %d개" % (
        a.job, plan.get("generator"), len(beats), len(sources)))
    before = audit_plan(beats, sources, seg_idx)
    print_plan_report("[전] 저장된 편성", before)
    if a.clean_base:
        audit_clean_base(json.loads(Path(a.clean_base).read_text(encoding="utf-8")), sources, seg_idx)
    if not a.apply:
        return 0 if before["ok"] else 1
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shopping_shorts import backbone
    gen = copy.deepcopy(beats)
    had_override = sum(1 for b in gen if b.get("scene_override"))
    for b in gen:
        b.pop("scene_override", None)
    base = audit_plan(gen, sources, seg_idx)
    print_plan_report("[전-생성본] scene_override %d칸을 지운 primary+alternates(=3단계가 만든 그대로)"
                      % had_override, base)
    report = {}
    after_beats = backbone.finalize_scenes(gen, sources, report=report, mode=_mode_of(plan))
    after = audit_plan(after_beats, sources, seg_idx)
    print_plan_report("[후] finalize_scenes 적용 (mode=%s)" % _mode_of(plan), after)
    # 불변식: 칸 수·칸 순서·narration·(반복 아닌) primary
    same_n = len(after_beats) == len(gen)
    same_order = [b.get("beat_idx") for b in after_beats] == [b.get("beat_idx") for b in gen]
    same_narr = [b.get("narration") for b in after_beats] == [b.get("narration") for b in gen]
    p_changed = [(b.get("beat_idx"), (g.get("primary") or {}).get("seg_id"), (b.get("primary") or {}).get("seg_id"))
                 for g, b in zip(gen, after_beats)
                 if (g.get("primary") or {}).get("seg_id") != (b.get("primary") or {}).get("seg_id")]
    print("-" * 78)
    print("불변식: 칸 수 %s · 칸 순서 %s · 대사 %s · primary 바뀐 칸 %s" % (
        "유지" if same_n else "★바뀜", "유지" if same_order else "★바뀜",
        "유지" if same_narr else "★바뀜", p_changed or "없음"))
    print("finalize 보고: " + json.dumps({k: v for k, v in report.items()}, ensure_ascii=False)[:1500])
    print("칸별 전→후:")
    for g, b in zip(gen, after_beats):
        bm = [c["seg_id"].rsplit("-", 1)[-1] + "(" + str(c.get("video_id")) + ")" for c in beat_material(g)[0]]
        am = [c["seg_id"].rsplit("-", 1)[-1] + "(" + str(c.get("video_id")) + ")" for c in beat_material(b)[0]]
        print("  칸 %2s: %s  ->  %s%s" % (b.get("beat_idx"), " ".join(bm), " ".join(am), "" if bm == am else "   *"))
    return 0 if (after["ok"] and same_n and same_order and same_narr) else 1


if __name__ == "__main__":
    sys.exit(main())
