# -*- coding: utf-8 -*-
"""한 번 호출 작가(story_writer.write_styled) 결과물 검사 — 진짜 모델로 최근 작업들을 다시 써 보고 잰다.
  (서버, repo 폴더에서, env 적재 후) python3 tools/script_diff/check_styled.py <sd_dump.json> [--limit N] [--quiet]
  입력 = tools/script_diff/dump_works.py 가 읽기 전용으로 떠 온 작업들. DB에는 아무것도 안 쓴다.

2026-09-27 사장님: "스타일이 많을 이유가 없잖아 다 똑같이 나오면" / "노바 작가처럼 틀 유지 + 기능·특징·장점" /
  "지어내고 어그로 있어도 상관없어". 재는 것(안마다):
  · 칸 순서 = 고른 스타일 칸 순서인가(연속 같은 칸은 하나로)
  · 컷: 없는 번호를 적은 줄 수 / 끝내 컷 없는 줄 수
  · 씨앗 되풀이: 앞 두 칸(씨앗 결은 첫 줄) 뒤 줄에 씨앗 셀링포인트 낱말 2개↑ (생성기 검사와 같은 함수)
  · A·B 겹침: 두 안의 4글자 조각 겹침(_gram_share, 상한 AB_MAX_SHARE)
  · 틀 예시 베낌: 줄이 고른 스타일의 예시 문장을 거의 그대로 옮겼나(TEMPLATE_COPY_SHARE 이상) — 작업이 달라도 같은 말이 되는 뿌리
  · 작업 사이 같은 줄: 다른 제품인데 글자가 같은 줄(회원 100명이 돌려쓰면 똑같아지는가)
  · 인증(Vertex인가)·다시쓰기 여부·남은 문제
끝에 합계 줄: 전 작업에서 하나라도 어긋나면 FAIL.
"""
import sys, os, json, pathlib, argparse
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser(); ap.add_argument("dump"); ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--quiet", action="store_true")
# 2026-09-27 사장님 "무료 제미나이랑 버텍스 차이가 있는 것 같은데 객관적으로" — 같은 작업·같은 지시로 무료 키풀만 태운다
ap.add_argument("--free", action="store_true", help="Vertex를 끄고 무료 키풀(대본생성 모델)로만")
# 2026-09-27: 앱처럼 제품 사실(쿠팡 수집분·제미니 지식·웹검색 wow)을 같이 준다 — app의 같은 함수를 부른다(캐시 공유)
ap.add_argument("--facts", action="store_true")
args = ap.parse_args()
os.chdir(ROOT)
from shopping_shorts import story_writer as sw
if args.free:
    from shopping_shorts import vertex_route as _vr
    _vr.try_call = lambda *a, **k: (False, None)


def collapse(xs):
    out = []
    for x in xs:
        if not out or out[-1] != x:
            out.append(x)
    return out


D = json.load(open(args.dump, encoding="utf-8"))
works = D["works"][:args.limit] if args.limit else D["works"]
all_lines = {}          # 정규화 글 → 나온 작업들
tot = {"tpl_copy": 0, "cross_same": 0, "drafts": 0, "order_bad": 0, "seed_rep": 0, "no_cut": 0, "ab_over": 0, "fail_work": 0, "not_vertex": 0}
for w in works:
    spines = [D["spines"][str(i)] for i in w["style_ids"] if D["spines"].get(str(i))]
    facts = ""
    if args.facts:
        from shopping_shorts import app as A
        from shopping_shorts.store import Store as _S
        _st = _S(A.DB_PATH)
        facts = "\n\n".join(x for x in (A._facts_block_for_job(w["job_id"], _st, w["product"]),
                                         A._wow_block_for([{"product": w["product"]}], _st)) if x)
        print("   제품 사실 %d자" % len(facts))
    try:
        drafts, why = sw.make_drafts(spines[:1], w["job"], 25, job_id=w["job_id"], preset="short",
                                     seed_text=w["seed_text"], seed_product=w["product"], facts=facts)
    except Exception as e:      # noqa: BLE001
        drafts, why = [], "예외 %r" % e
    print("\n" + "=" * 72 + "\n작업 %s (%s) 스타일 %s — why=%r" % (
        w["work_id"], w["product"], [s.get("name") for s in spines[:1]], why))
    if len(drafts) < 1 + (1 if spines else 0):
        tot["fail_work"] += 1
    texts = []
    for d, sp in zip(drafts, [None] + spines[:1]):
        tot["drafts"] += 1
        frame = sw.frame_of(sp)
        beats = d.get("beats") or []
        got = collapse([b.get("role") for b in beats])
        order_ok = (not frame["roles"]) or got == frame["roles"]
        tot["order_bad"] += 0 if order_ok else 1
        pts = d.get("seed_points") or []
        open_n = set(frame["roles"][:2]) if frame["roles"] else None
        rep = [i + 1 for i, b in enumerate(beats)
               if (b.get("role") not in open_n if open_n else i >= 1)
               and len(sw._seed_word_hits(b.get("text"), pts, w["product"])) >= 2]
        tot["seed_rep"] += len(rep)
        nocut = sum(1 for b in beats if not b.get("src_segs"))
        exs = {} if frame.get("keep_idioms") else (frame.get("examples") or {})   # 유튜브 관용구는 베낌 아님(생성기와 같은 잣대)
        pins = frame_pins = (d.get("writer_note") or {}).get("pinned") or {}
        copy = [i + 1 for i, b in enumerate(beats) if b.get("role") not in pins and
                any(sw._gram_share(b.get("text"), x) >= sw.TEMPLATE_COPY_SHARE for x in exs.get(b.get("role"), []))]
        tot["tpl_copy"] += len(copy)
        for b in beats:
            all_lines.setdefault(sw._norm_text(b.get("text")).strip(".!?~"), set()).add(w["work_id"])
        tot["no_cut"] += nocut
        wn = d.get("writer_note") or {}
        if wn.get("auth") != "vertex" and not args.free:
            tot["not_vertex"] += 1
        texts.append(d.get("script") or "")
        print("── %s  %d자·%.1f초  인증=%s  칸순서=%s  틀베낌줄=%s  씨앗되풀이줄=%s  컷없는줄=%d  다시쓰기=%s  남은문제=%s" % (
            d.get("style_name"), d.get("chars") or 0, d.get("sec") or 0, wn.get("auth"),
            "OK" if order_ok else "틀림(%s)" % " → ".join(got), copy or "-", rep or "-", nocut,
            "예" if wn.get("retry") else "아니오", wn.get("problems") or "-"))
        if not args.quiet:
            for b in beats:
                print("   %-8s | %s   %s" % (b.get("role"), b.get("text"), b.get("src_segs")))
    if len(texts) == 2:
        share = sw._gram_share(texts[1], texts[0])
        over = share > sw.AB_MAX_SHARE
        tot["ab_over"] += 1 if over else 0
        print("   A·B 겹침 %.2f (상한 %.2f) %s" % (share, sw.AB_MAX_SHARE, "넘음" if over else "OK"))
    print("   씨앗(앞 120자): %s" % w["seed_text"][:120].replace("\n", " "))

same = {t: ws for t, ws in all_lines.items() if len(ws) > 1}
tot["cross_same"] = len(same)
for t, ws in sorted(same.items(), key=lambda x: -len(x[1]))[:10]:
    print("   작업 %d개에 같은 줄: %s" % (len(ws), t))
bad = tot["tpl_copy"] + tot["cross_same"] + tot["order_bad"] + tot["seed_rep"] + tot["ab_over"] + tot["fail_work"] + tot["not_vertex"]
print("\n합계 %s → %s" % (tot, "PASS" if bad == 0 else "FAIL"))
