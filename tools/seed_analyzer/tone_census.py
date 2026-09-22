# -*- coding: utf-8 -*-
"""말맛 센서스 — 씨앗(히트작 전사)과 이야기 작가 결과를 **같은 자로** 나란히 잰다 (2026-09-22 사장님
"1번부터 테스트 / 반말→존댓말로 바뀌거나 어색한 게 들어가지 않게").

재는 축(전부 코드, 모델 0회):
  어미     줄 끝이 존댓말 / 반말 / 연결어미(끊지 않고 이어짐) / 기타 중 무엇인가 → 분포
  뒤섞임   한 편 안에 존댓말 줄과 반말 줄이 **같이** 있나(줄 번호까지)
  의태어   의태어·강조 부사 밀도(어절 100개당) — 씨앗 vs 결과
  문장길이 줄당 어절 수
  어색     설명문 지문(_FLAT) · 권유("~해 보세요") · 신호어 두 번 · 따옴표 대사 · 영문/한자 섞임

서버에서(라이브 함수 그대로, 읽기 전용·저장 없음):
  python3 tools/seed_analyzer/tone_census.py --n 10 --out /tmp/tone_census.json
  python3 tools/seed_analyzer/tone_census.py --jobs 73387018ca85,524372dd1368 --out ...
이 PC에서 표만 다시:
  py tools/seed_analyzer/tone_census.py --report <json> [--html <경로>]
"""
import argparse
import collections
import json
import os
import re
import sys
import time

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

_POLITE = re.compile(r"(어요|아요|에요|예요|해요|세요|네요|죠|니다|니까요|거든요|더라고요|더라구요|는데요|잖아요)[.!?~…]*$")
_PLAIN = re.compile(r"(다|야|지|네|임|음|함|는데|거든|잖아|더라|더라고|었어|았어|해|래|대|는 거|던 거|버림)[.!?~…]*$")
_PLAIN_STRONG = re.compile(r"(거든|잖아|더라고|더라구|더라|는 거|던 거|는 거임|임|음|함|버림|래|대)[.!?~…]*$")
# 줄 끝이 이어지는 꼴(마침표로 안 끊고 다음 줄로 넘어감)
_CONNECT = re.compile(r"(는데|서|고|니까|면|다가|길래|더니|라서|라며|자마자|지만|는데도|든|거나|을|를|달리|순간|때문에)[,~…]*$")
_MIMETIC = ["싹", "착", "탁", "쓱", "확", "쏙", "슥", "쭉", "뚝딱", "똑", "푹", "사르르", "살살", "번쩍",
            "진짜", "완전", "너무", "엄청", "그냥", "딱", "바로", "확실히", "정말"]
_FLAT = re.compile(r"(있어|있어서|때문에|덕분에)\s*(편리|간편|좋|유용)|기능이 있|사용할 수 있습니다|해 줍니다$|됩니다$|입니다$")
_SUGGEST = re.compile(r"해 ?보세요|추천드려요|추천합니다|써 ?보세요|구매하세요")
_QUOTE = re.compile(r"[\"“”'‘’]")
_FOREIGN = re.compile(r"[A-Za-z]{3,}|[一-鿿]")
_SIGNALS = ["심지어", "게다가", "거기다", "무엇보다", "대박인 건", "이게 말도 안 되는게", "이게 말도 안 되는 게",
            "진짜 미친 포인트는", "근데 진짜 미친 포인트는", "이게 미친 포인트인게", "충격적인 건",
            "진짜 충격적인 포인트는", "근데 진짜 충격적인 포인트는", "진짜 말도 안 되는게", "진짜 대박인 건"]


def _ending(line):
    t = line.strip()
    if not t:
        return "빈줄"
    if _POLITE.search(t):
        return "존댓말"
    if _PLAIN_STRONG.search(t):      # 거든·더라고·는 거… 는 연결어미(든·고·거)보다 먼저 본다
        return "반말"
    if _CONNECT.search(t):
        return "연결"
    if _PLAIN.search(t):
        return "반말"
    return "기타"


def _seed_sentences(text):
    """전사엔 문장부호가 거의 없다 → 부호가 있으면 부호로, 없으면 어미 어절에서 끊는다."""
    t = (text or "").strip()
    if len(re.findall(r"[.!?…]", t)) >= 3:
        return [s for s in re.split(r"(?<=[.!?…])\s+", t) if s.strip()]
    out, cur = [], []
    for w in t.split():
        cur.append(w)
        if _POLITE.search(w) or re.search(r"(다|요|죠|임|음|거든|잖아|더라)$", w):
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def measure(lines):
    lines = [l for l in lines if l.strip()]
    words = sum(len(l.split()) for l in lines) or 1
    ends = collections.Counter(_ending(l) for l in lines)
    mim = sum(l.count(m) for l in lines for m in _MIMETIC)
    pol = [i for i, l in enumerate(lines) if _ending(l) == "존댓말"]
    pla = [i for i, l in enumerate(lines) if _ending(l) == "반말"]
    starts = [s for l in lines for s in _SIGNALS if l.strip().startswith(s)]
    dup_sig = [s for s, c in collections.Counter(starts).items() if c > 1]
    return {
        "lines": len(lines), "words": words, "words_per_line": round(words / max(1, len(lines)), 1),
        "ending": {k: round(v / max(1, len(lines)), 2) for k, v in ends.items()},
        "mimetic_per100": round(mim * 100 / words, 1),
        "polite_lines": pol, "plain_lines": pla,
        "mixed": bool(pol and pla),
        "flat": [l for l in lines if _FLAT.search(l)],
        "suggest": [l for l in lines if _SUGGEST.search(l)],
        "quote": [l for l in lines if _QUOTE.search(re.sub(r"댓글에\s*[\"“”'‘’][^\"“”'‘’]{1,8}[\"“”'‘’]", "", l))],   # CTA 낱말 따옴표는 대사가 아니다
        "foreign": [l for l in lines if _FOREIGN.search(l)],
        "dup_signal": dup_sig,
    }


def _tone(m):
    p, q = len(m["polite_lines"]), len(m["plain_lines"])
    return "존댓말" if p > q else "반말" if q > p else "불명"


def run_live(n, jobs, seconds):
    from shopping_shorts.store import Store
    from shopping_shorts import app as A
    from shopping_shorts import backbone_assemble as ba
    from shopping_shorts import story_writer as sw
    if os.environ.get("SW_PATH"):        # 고친 story_writer를 배포 전에 시험할 때(서버 코드는 안 건드린다)
        import importlib.util
        spec = importlib.util.spec_from_file_location("sw_new", os.environ["SW_PATH"])
        sw = importlib.util.module_from_spec(spec); spec.loader.exec_module(sw)
        print("story_writer =", os.environ["SW_PATH"])
    store = Store(A.DB_PATH)
    if jobs:
        jids = jobs
    else:
        jids = [w["job_id"] for w in store.list_produce_works(0, limit=80) if w.get("job_id")]
    rows, seen = [], set()
    for jid in jids:
        if jid in seen or len(rows) >= n:
            continue
        seen.add(jid)
        job = A._enrich_job_extract(store.get_mix_job(jid), store)
        if not (job or {}).get("extract"):
            continue
        srcs = ba.sources_from_extract(job["extract"])
        seed = ba.seed_source(srcs, job.get("backbone_main"))
        seed_text = ((seed or {}).get("full_text_ko") or (seed or {}).get("full_text") or "").strip()
        if len(seed_text) < 60 or _FOREIGN.search(seed_text[:200]) and not re.search(r"[가-힣]{4}", seed_text[:200]):
            continue
        t0 = time.time()
        drafts, why = sw.make_drafts([], job, seconds, job_id=jid)
        row = {"job_id": jid, "seed_vid": (seed or {}).get("video_id"),
               "seed_platform": sw.seed_platform(seed_text),
               "seed_text": seed_text[:1500], "seed": measure(_seed_sentences(seed_text)),
               "why": why, "secs": round(time.time() - t0, 1), "drafts": []}
        for d in drafts:
            ls = [b["text"] for b in d.get("beats") or []]
            row["drafts"].append({"platform": d.get("platform"), "lines": ls, "m": measure(ls),
                                  "no_cut": (d.get("meta") or {}).get("note", {}).get("no_cut_lines") if isinstance(d.get("meta"), dict) else None,
                                  "total_sec": round(sum(b.get("sec") or 0 for b in d.get("beats") or []), 1)})
        rows.append(row)
        print("  %s 씨앗=%s 대본 %d편 %.0f초 %s" % (jid, row["seed_platform"], len(drafts), row["secs"], why or ""), flush=True)
    return rows


def report(rows, html=None):
    print("\n%-13s %-4s | %-22s %-5s | %-4s %-22s %-5s %-4s | 뒤섞임 설명문 권유 신호중복 따옴표" % (
        "job", "씨앗", "씨앗 어미(존/반/연/기)", "의태", "결과", "결과 어미(존/반/연/기)", "의태", "어절/줄"))
    tot = collections.Counter()
    for r in rows:
        s = r["seed"]
        def e(m):
            d = m["ending"]
            return "%.2f/%.2f/%.2f/%.2f" % (d.get("존댓말", 0), d.get("반말", 0), d.get("연결", 0), d.get("기타", 0))
        if not r["drafts"]:
            print("%-13s %-4s | %-22s %-5s | 실패: %s" % (r["job_id"], r["seed_platform"], e(s), s["mimetic_per100"], r["why"]))
            tot["fail"] += 1
            continue
        for d in r["drafts"]:
            m = d["m"]
            tone_flip = _tone(s) != "불명" and _tone(m) != "불명" and _tone(s) != _tone(m)
            flags = "%s %s %s %s %s" % (
                ("★줄%s" % (m["polite_lines"] if _tone(m) == "반말" else m["plain_lines"])) if m["mixed"] else "-",
                len(m["flat"]) or "-", len(m["suggest"]) or "-", ",".join(m["dup_signal"]) or "-", len(m["quote"]) or "-")
            print("%-13s %-4s | %-22s %-5s | %-4s %-22s %-5s %-4s | %s%s" % (
                r["job_id"], r["seed_platform"], e(s), s["mimetic_per100"], d["platform"], e(m), m["mimetic_per100"],
                m["words_per_line"], flags, "  ★씨앗과 말투 다름(%s→%s)" % (_tone(s), _tone(m)) if tone_flip else ""))
            tot["drafts"] += 1
            tot["mixed"] += m["mixed"]; tot["flip"] += tone_flip; tot["flat"] += bool(m["flat"])
            tot["suggest"] += bool(m["suggest"]); tot["dup"] += bool(m["dup_signal"]); tot["quote"] += bool(m["quote"])
    print("\n합계: 대본 %d편 (실패 %d) · 말투 뒤섞임 %d · 씨앗과 말투 다름 %d · 설명문 %d · 권유 %d · 신호어 중복 %d · 따옴표 %d" % (
        tot["drafts"], tot["fail"], tot["mixed"], tot["flip"], tot["flat"], tot["suggest"], tot["dup"], tot["quote"]))
    if html:
        _html(rows, html)
        print("HTML:", html)


def _html(rows, path):
    import html as H
    out = ["<meta charset='utf-8'><style>body{font-family:sans-serif;max-width:1100px;margin:20px auto}"
           "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:4px 6px;vertical-align:top;font-size:13px}"
           ".존댓말{background:#e8f0ff}.반말{background:#fff3e0}.연결{background:#eeffee}.기타{background:#f5f5f5}"
           ".bad{color:#c00;font-weight:bold}.seed{white-space:pre-wrap;font-size:12px;color:#444}</style>"
           "<h2>말맛 센서스 — 씨앗 vs 이야기 작가 (색 = 줄 끝 어미: 파랑 존댓말 / 주황 반말 / 초록 연결 / 회색 기타)</h2>"]
    for r in rows:
        out.append("<h3>%s · 씨앗 %s · %s</h3><div class=seed>%s</div>" % (
            r["job_id"], r["seed_platform"], H.escape(r["why"] or ""), H.escape(r["seed_text"][:700])))
        for d in r["drafts"]:
            m = d["m"]
            out.append("<p><b>결과(%s) %s초</b> 뒤섞임=%s 설명문=%d 권유=%d 신호중복=%s</p><table>" % (
                d["platform"], d["total_sec"], "<span class=bad>있음</span>" if m["mixed"] else "없음",
                len(m["flat"]), len(m["suggest"]), ",".join(m["dup_signal"]) or "없음"))
            for i, l in enumerate(d["lines"]):
                k = _ending(l)
                bad = " class=bad" if (_FLAT.search(l) or _SUGGEST.search(l)) else ""
                out.append("<tr class=%s><td>%d</td><td%s>%s</td><td>%s</td></tr>" % (k, i + 1, bad, H.escape(l), k))
            out.append("</table>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--jobs", default="")
    ap.add_argument("--seconds", type=int, default=25)
    ap.add_argument("--out", default="")
    ap.add_argument("--report", default="")
    ap.add_argument("--html", default="")
    a = ap.parse_args()
    if a.report:
        rows = json.load(open(a.report, encoding="utf-8"))
    else:
        rows = run_live(a.n, [x.strip() for x in a.jobs.split(",") if x.strip()], a.seconds)
        if a.out:
            json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    report(rows, a.html or None)


if __name__ == "__main__":
    main()
