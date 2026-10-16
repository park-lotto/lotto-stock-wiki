# -*- coding: utf-8 -*-
"""대본 쓰기 엔진 — 프리셋 규칙 + 역할 칸 + 소재·벤치·사실로 대본을 쓰고, 같은 자로 재고, 틀린 줄만 다시 쓴다 (관제 097, 2026-10-16).

    PYTHONUTF8=1 py tools/calcopy/engine/script_engine.py --preset channel/sseolpulda/preset/A_흰바탕창/창아래_검정 \
        --topic <out>/후보.json#c2 --bench <out>/벤치/c2.md --facts facts.json --mode captions --out <폴더>
    PYTHONUTF8=1 py tools/calcopy/engine/script_engine.py --preset yummyknow --topic 소재.json --bench 벤치.md --facts facts.json \
        --mode narration --out <폴더>

1) 규칙: 프리셋 뜯기(captions 줄·폭 / 받아쓰기 문장·cps / 존댓말 비율) + 갈래 rules.json(예문·말투) + **역할 칸**
   (--roles > manifest.roles > ROLES[slug] — 썰풀다 6칸·yummyknow 5칸·방구석 6박자). 쓴 역할 칸은 <out>/roles.json 에 남긴다.
2) 초안(LLM 1회, 무료 제미나이) — 줄마다 근거 번호(facts f* · 벤치 포인트 b*) 필수, 화면 묘사 금지, 지어낸 사실·숫자 금지, 과장 OK.
3) 검사 = style_writer.check_captions / check_narration(베낌·존댓말·숫자·말끝·묘사·톤 밖·길이) + 이 엔진의 역할 칸 채움·근거·말투 섞임·
   전체 길이(나레 초) → 틀린 줄만 다시 쓰기(최대 2회, 줄 단위).
4) 산출: 대본.json(remake.py --script 그대로: final.lines[fn,text,facts,sources] · facts{id:{text,url}} · gate.scores) ·
   대본_검사.md · 대본_계획.md(선검수: 소재 5기준·썰 각도·근거표).
판단 주인: 검사 판정 = check_script() 한 곳(아래 style_writer 검사를 부르고 합친다) · 다시 쓸 줄 고르기 = bad_lines().
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.calcopy import style_writer as SW          # noqa: E402  검사·폭 추정·말끝·묘사 말끝은 style_writer 한 곳
from tools.calcopy.engine import topic_find as TF      # noqa: E402  프리셋 읽기·LLM 창구·5기준 이름 공용

# 채널별 역할 칸(뜯기·규칙 파일에 역할 칸이 없을 때 기본) — 근거:
#  sseolpulda = channel/sseolpulda/칼카피_ZdeZ/대본.json fns(원본 1위 6줄 역할·말끝, 10-16 통과편)
#  yummyknow  = 설계 지시(상황→반응→진짜 이유→반전→댓글 반응) · channel/yummyknow/칼카피_rGFX/대본.json final fn 5줄
#  banggu     = tools/calcopy/try_banggu_styles.py STYLES['숨은이유'] labels(제목 뺀 6칸)
ROLES = {
    "sseolpulda": ["발견 맥락(어디서 보고 알게 됐나) · 말끝 ~길래", "의심(처음엔 안 믿음) · 말끝 ~는데", "반전 시연(그냥 대기만 하면) · 말끝 ~면",
                   "결과 과장(평범한 물건이 뭐로 변함) · 말끝 ~함;;", "감탄 · 말끝 ~네", "인정·댓글유도 · 말끝 ~인정?"],
    "yummyknow": ["상황(훅 질문+무슨 일)", "반응(사람들 반응)", "진짜 이유(전언 ~다는데)", "반전", "댓글 반응(마무리)"],
    "banggu": ["소개(남들이 좋아한다는 수식+제품, 명사로 끝)", "의문(사는 이유는 단순히 OO 때문이 아니라는데)", "살펴봄(특징 1~2개)",
               "꺾음(정작 꽂힌 포인트는 따로 있다는데)", "진짜 이유(그건 바로 ~)", "혼잣말(말투 바꾼 한 줄)"],
}
MAX_REWRITES = 2
# 소재 일치 검사용 브랜드·대표 제품명(10-16 실측 결함: 신라면 소재 대본이 벤치 영상 하나를 따라 '진라면 공장' 이야기가 됐는데 검사는 통과)
BRANDS = ("신라면", "진라면", "너구리", "안성탕면", "짜파게티", "불닭", "삼양라면", "열라면", "육개장", "오뚜기", "농심", "삼양", "팔도", "빙그레",
          "롯데", "해태", "오리온", "크라운", "비비고", "풀무원", "동원", "맥도날드", "버거킹", "롯데리아", "맘스터치", "스타벅스", "이디야",
          "메가커피", "컴포즈", "투썸", "다이소", "코스트코", "이케아", "이마트", "홈플러스", "트레이더스", "쿠팡", "올리브영", "무인양품",
          "세븐일레븐", "노브랜드", "교촌", "굽네", "피자헛", "도미노", "삼성", "애플", "샤오미", "아마존", "테무", "알리",
          "CU", "GS25", "KFC", "BBQ", "bhc", "CJ")
NARR_TOTAL_TOL = 0.15        # 나레 전체 글자 수 = 원본 받아쓰기 합 ±15%
BANMAL_END = r"(음|임|함|됨|짐|거|는데|다고|라고|던데|네|냐|지|야|다)[.!?~;]*$"
POLITE_END = r"(습니다|니다|어요|아요|해요|세요|에요|예요|죠|네요)[.!?~;]*$"


# ── 입력 읽기 ─────────────────────────────────────────────────────────────
def load_topic(arg: str, pick: str | None = None) -> dict:
    """'후보.json#c2' · 후보.json(--pick 또는 recommend[0]) · 소재.json({topic,…}) · 그냥 글."""
    path, _, cid = arg.partition("#")
    p = Path(path)
    if p.suffix == ".json" and p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "candidates" in d:
            cid = cid or pick or (d.get("recommend") or [None])[0]
            c = next((c for c in d["candidates"] if c["id"] == cid), None)
            if not c:
                raise SystemExit(f"후보 {cid!r} 없음 — {[c['id'] for c in d['candidates']]}")
            return c
        if isinstance(d, dict) and d.get("topic"):
            return d
        raise SystemExit(f"소재 파일 꼴 모름: {arg}")
    return {"topic": arg}


def load_facts(path: str | None) -> dict:
    """facts.json → {id: {text, url}}. 받는 꼴: {id:{text,url}} · {id:"글"} · [{id?,text,source|url}] · {"facts":[…]}(seedflow)."""
    if not path:
        return {}
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict) and isinstance(d.get("facts"), (list, dict)):
        d = d["facts"]
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out[k] = {"text": v, "url": ""} if isinstance(v, str) else {"text": v.get("text", ""), "url": v.get("url") or v.get("source") or ""}
    else:
        for i, v in enumerate(d, 1):
            out[v.get("id") or f"f{i}"] = {"text": v.get("text", ""), "url": v.get("url") or v.get("source") or ""}
    return {k: v for k, v in out.items() if (v["text"] or "").strip()}


def load_bench(path: str | None) -> dict:
    """벤치 md(topic_find 가 쓴 '- [b1] (kind) 글 — from') 또는 같은 이름 .json → {b1: {text,url,kind}} + 베낌 검사용 원문."""
    if not path:
        return {"points": {}, "texts": []}
    p = Path(path)
    j = p.with_suffix(".json")
    if j.exists():
        d = json.loads(j.read_text(encoding="utf-8"))
        vids = {v["id"]: v for v in d.get("videos") or []}
        pts = {}
        for x in d.get("points") or []:
            vid = re.sub(r"^v_", "", str(x.get("from") or ""))
            pts[x["id"]] = {"text": f"({x.get('kind')}) {x['text']}", "url": (vids.get(vid) or {}).get("url", ""), "kind": x.get("kind")}
        texts = [v.get("title") or "" for v in vids.values()] + [c["text"] for v in vids.values() for c in v.get("comments", [])[:20]]
        return {"points": pts, "texts": texts}
    pts = {}
    for m in re.finditer(r"^- \[(b\d+)\]\s*(.+)$", p.read_text(encoding="utf-8"), re.M):
        pts[m.group(1)] = {"text": m.group(2).strip(), "url": "", "kind": None}
    return {"points": pts, "texts": []}


def skeleton(P: dict, mode: str | None, roles: list[str] | None) -> dict:
    """프리셋 → 칸 목록과 길이 규칙. 판단 주인: 줄 길이 범위는 style_writer.line_ranges/_cap_range, 나레 전체는 원본 받아쓰기 합 ±15%."""
    J = json.loads(Path(P["tteutgi"]).read_text(encoding="utf-8")) if P.get("tteutgi") else {}
    R = json.loads(Path(P["rules"]).read_text(encoding="utf-8")) if P.get("rules") else {}
    vr = J.get("voice_rules") or {}
    mode = mode or ("captions" if vr.get("narration") == "none" else "narration")
    roles = roles or P["manifest"].get("roles") or ROLES.get(P["slug"])
    if not roles:
        raise SystemExit(f"역할 칸 없음 — --roles '칸1,칸2,…' 로 주세요(채널 {P['slug']})")
    n = len(roles)
    polite_ratio = (J.get("script_tone") or {}).get("polite_ratio")
    honor = "존댓말" if (polite_ratio or 0) > 0.5 else "반말"
    sk = {"mode": mode, "roles": roles, "ends": SW.ends_of(roles), "honorific": honor, "rules": R, "tteutgi": P.get("tteutgi"),
          "width": None, "total": None, "cps": vr.get("cps") or (SW.CPS if mode == "narration" else None)}
    if mode == "captions":
        items = {i["i"]: i for i in (J.get("captions") or {}).get("items") or []}
        orig = [" ".join(items[k].get("text") or []) for k in sorted(items)]
        if len(orig) == n:
            widths = [(items[k].get("widths") or [None])[0] for k in sorted(items)]
            sk["ranges"] = SW.line_ranges(orig)
            if P.get("frame") and all(widths):
                try:
                    sk["width"] = {"est": SW.width_estimator(P["frame"]), "orig": widths}
                except Exception as e:  # noqa: BLE001 — 폭 추정 못 하면 글자 수 기준으로(이유는 남긴다)
                    sk["width_failed"] = f"{type(e).__name__}: {str(e)[:100]}"
        else:   # 원본 줄 수와 역할 칸 수가 다르면 원본 줄 길이 중앙 ±30%
            m = st.median([len(t.replace(" ", "")) for t in orig]) if orig else 12
            sk["ranges"] = [(max(4, int(m * 0.7)), int(m * 1.3) + 1)] * n
        sk["orig"] = orig
    else:
        tr = (J.get("audio") or {}).get("transcript") or []
        tr = tr.get("segments") or [] if isinstance(tr, dict) else tr
        orig = [t["text"].strip() for t in tr if isinstance(t, dict) and t.get("lang", "ko") == "ko"]
        T = sum(len(t.replace(" ", "")) for t in orig) or (R.get("length_chars") or {}).get("median") or 200
        sk["total"] = (int(T * (1 - NARR_TOTAL_TOL)), int(T * (1 + NARR_TOTAL_TOL)) + 1)
        per = T / n
        sk["ranges"] = [(max(6, int(per * 0.4)), int(per * 2.0) + 1)] * n   # 줄은 느슨하게 — 판정은 전체 길이
        sk["orig"] = orig
    return sk


# ── 프롬프트 ──────────────────────────────────────────────────────────────
# 규칙 문장의 주인 = style_writer(0순위-B, 10-16 커밋 71bd08ac2) — 여기선 가져다 쓰기만(test_calcopy_prompt_owner 가 동일성을 지킨다).
# 소재 이탈 금지 문장은 아직 SW 에 없다(요청) — 지금은 check_script 의 topic_match 가 잡고 FIX 단계에서 '빼야 할 이름'을 준다.
DRAFT_PROMPT = SW.DRAFT_PROMPT
FIX_PROMPT = SW.FIX_PROMPT


def _grounds(facts: dict, bench: dict) -> str:
    rows = [f"[{k}] (사실) {v['text']}" + (f" — {v['url']}" if v.get("url") else "") for k, v in facts.items()]
    rows += [f"[{k}] (벤치 포인트) {v['text']}" for k, v in bench["points"].items()]
    return "\n".join(rows) or "(없음)"


def _slots(sk: dict) -> str:
    out = []
    for k, r in enumerate(sk["roles"]):
        lo, hi = sk["ranges"][k]
        out.append(f"{k + 1}. 역할={r} · {lo}~{hi}자" + (f" · 화면 폭 약 {sk['width']['orig'][k]}px" if sk.get("width") else ""))
    if sk.get("total"):
        out.append(f"(전체 {sk['total'][0]}~{sk['total'][1]}자 ≈ {round(sum(sk['total']) / 2 / (sk['cps'] or SW.CPS), 1)}초)")
    return "\n".join(out)


# ── 검사(판단 주인) ────────────────────────────────────────────────────────
def _role_name(r: str) -> str:
    return re.split(r"[(·]", r)[0].strip()


def _brands_in(text: str) -> set:
    t = text or ""
    return {b for b in BRANDS if (re.search(rf"(?<![A-Za-z]){re.escape(b)}(?![A-Za-z])", t, re.I) if b.isascii() else b in t)}


def product_terms(topic: dict) -> list[str]:
    """소재 제품명 낱말 — topic.product 가 있으면 그것, 없으면 소재 글 머리(' — '·'('·' vs ' 앞)의 핵심 낱말."""
    head = topic.get("product") or re.split(r"\s+—\s+|\(|\s+vs\s+|\s+-\s+", topic.get("topic") or "")[0]
    return TF.core_terms(head)


def topic_match(texts: list[str], topic: dict, facts: dict, mode: str) -> dict:
    """소재 일치(판단 주인): ① 소재·사실(f*)에 없는 브랜드명이 줄에 나오면 그 줄 실패 ② 나레 꼴(또는 topic.product 지정)이면
    소재 제품명 낱말이 대본 어딘가에 1회 이상. 자막 꼴은 화면이 제품을 보여 줘 이름을 안 부르는 게 채널 꼴(ZdeZ·LED 수도꼭지) — ②는 경고만."""
    allowed = _brands_in(topic.get("topic") or "") | _brands_in(topic.get("product") or "") | _brands_in(" ".join(v["text"] for v in facts.values()))
    other = {k: sorted(_brands_in(t) - allowed) for k, t in enumerate(texts)}
    other = {k: v for k, v in other.items() if v}
    terms = product_terms(topic)
    flat = re.sub(r"\s+", "", " ".join(texts)).lower()
    named = [w for w in terms if w in flat]
    required = mode == "narration" or bool(topic.get("product"))
    return {"other_brand": other, "product_terms": terms, "product_named": named,
            "product_missing": bool(terms) and not named and required, "product_warn": bool(terms) and not named and not required}


def check_script(lines: list[dict], sk: dict, facts: dict, bench: dict, free_roles: tuple = (), topic: dict | None = None) -> dict:
    """한 곳에서 판정 — style_writer 검사 + 역할 칸·근거·말투 섞임·전체 길이·소재 일치. 줄 번호는 0부터."""
    n = len(sk["roles"])
    R = sk["rules"] or {"examples": []}
    R.setdefault("examples", [])
    ids = set(facts) | set(bench["points"])
    facts_text = " ".join(v["text"] for v in facts.values())
    texts = [l.get("text") or "" for l in lines]
    # 역할 칸: 줄 수 + 줄마다 그 칸 역할 이름으로 시작하는 fn
    role_missing = [k for k in range(n) if k >= len(lines) or _role_name(sk["roles"][k]) not in (lines[k].get("fn") or "")]
    extra_lines = list(range(n, len(lines)))
    base_lines = (lines + [{"fn": "", "text": ""}] * n)[:n]
    if sk["mode"] == "captions":
        base = SW.check_captions(base_lines, sk["orig"] if len(sk["orig"]) == n else [""] * n, R, sk["ranges"], sk.get("width"), sk["ends"])
        len_off = base["len_off_lines"]
        copied = base["copied_lines"] if len(sk["orig"]) == n else []
        describe, ending_off = base["describe_lines"], base["ending_off"]
    else:
        fstr = " ".join(f"[{k}] {v['text']}" for k, v in {**facts, **bench["points"]}.items())
        base = SW.check_narration(base_lines, sk["orig"] if len(sk["orig"]) == n else [""] * n, sk["ranges"], fstr)
        len_off, copied = base["len_off_lines"], base["copied_lines"]
        describe = [k for k, t in enumerate(texts[:n]) if t.rstrip("?!.;~ ").endswith(SW.DESCRIBE_ENDS)]
        ending_off = [k for k, (t, e) in enumerate(zip(texts[:n], sk["ends"])) if e and not SW._core(t).endswith(SW._core(e))]
        if len(sk["orig"]) != n:   # 원본 문장 수가 칸 수와 다르면 베낌은 원본 전체와 8글자 겹침으로
            o8 = set().union(*(SW._ngrams(t) for t in sk["orig"])) if sk["orig"] else set()
            copied = [k for k, t in enumerate(texts[:n]) if SW._ngrams(t) & o8]
    # 벤치 영상 제목·댓글과 8글자 겹침(포인트는 가져오되 문장은 베끼지 않는다)
    b8 = set().union(*(SW._ngrams(t) for t in bench.get("texts") or [])) if bench.get("texts") else set()
    copied_bench = [k for k, t in enumerate(texts[:n]) if SW._ngrams(t) & b8]
    # 근거: 줄마다 알려진 번호 1개 이상(free_roles 칸만 예외)
    no_ground = [k for k, l in enumerate(lines[:n]) if not (set(l.get("facts") or []) & ids)
                 and not any(fr and fr in (sk["roles"][k] if k < n else "") for fr in free_roles)]
    unknown_ids = sorted({i for l in lines for i in (l.get("facts") or []) if i not in ids})
    # 숫자: [f…] 사실 글에 있는 숫자만(벤치 포인트 숫자는 남의 영상 주장 — 사실 조사 전엔 못 쓴다)
    num_lines = [k for k, t in enumerate(texts[:n]) if any(x not in facts_text for x in re.findall(r"\d[\d,.]*", t))]
    # 말투: 채널이 반말이면 존댓말 줄, 존댓말이면 반말 줄
    if sk["honorific"] == "반말":
        tone_off = [k for k, t in enumerate(texts[:n]) if re.search(POLITE_END, t.strip()) or re.search(r"(습니다|어요|아요|해요|세요)\s", t)]
    else:
        tone_off = [k for k, t in enumerate(texts[:n]) if re.search(BANMAL_END, t.strip()) and not re.search(POLITE_END, t.strip())]
    off_tone_words = [k for k, t in enumerate(texts[:n]) if any(w in t for w in SW.OFF_TONE)]
    total_off = None
    chars = [len(t.replace(" ", "")) for t in texts[:n]]
    if sk.get("total"):
        tot = sum(chars)
        if not (sk["total"][0] <= tot <= sk["total"][1]):
            total_off = {"chars": tot, "range": list(sk["total"]), "fix_line": (max if tot > sk["total"][1] else min)(range(len(chars)), key=lambda k: chars[k]) if chars else None}
    tm = topic_match(texts[:n], topic or {}, facts, sk["mode"]) if topic else {"other_brand": {}, "product_missing": False}
    per_line = {"off_topic_brand": sorted(tm["other_brand"]), "product_missing": [0] if tm["product_missing"] else [], "role_missing": role_missing, "no_ground": no_ground, "len_off": len_off, "copied_orig": copied, "copied_bench": copied_bench,
                "describe": describe, "ending_off": ending_off, "numbers_unsourced": num_lines, "tone_off": tone_off, "off_tone_words": off_tone_words}
    chk = {**per_line, "n_lines": len(lines), "n_roles": n, "extra_lines": extra_lines, "unknown_ids": unknown_ids, "total_off": total_off,
           "chars": chars, "ranges": [list(r) for r in sk["ranges"]], "sec_est": round(sum(chars) / sk["cps"], 1) if sk.get("cps") else None,
           "est_px": base.get("est_px"), "orig_px": base.get("orig_px"), "width_median_pct": base.get("width_median_pct"),
           "copied_8grams_vs_examples": base.get("copied_8grams_vs_examples"), "topic_match": tm}
    chk["bad"] = bad_lines(chk)
    chk["ok"] = not chk["bad"] and not extra_lines and not unknown_ids and not total_off and len(lines) == n
    return chk


def bad_lines(chk: dict) -> dict:
    """다시 쓸 줄 → 이유 목록(판단 주인). 전체 길이 어긋남은 가장 긴/짧은 줄에 붙인다."""
    why = {}
    names = {"off_topic_brand": "소재 밖 브랜드명(소재 이탈)", "product_missing": "소재 제품명이 대본에 없음", "role_missing": "칸 역할 빠짐/어긋남", "no_ground": "근거 번호 없음", "len_off": "글자 수·폭 범위 밖", "copied_orig": "원본과 겹침",
             "copied_bench": "벤치 영상 문장과 겹침", "describe": "화면 묘사", "ending_off": "정해진 말끝으로 안 끝남",
             "numbers_unsourced": "사실에 없는 숫자", "tone_off": "말투 섞임(채널 말투 밖)", "off_tone_words": "톤 밖 낱말"}
    for key, label in names.items():
        for k in chk.get(key) or []:
            why.setdefault(k, []).append(label)
    t = chk.get("total_off")
    if t and t.get("fix_line") is not None:
        why.setdefault(t["fix_line"], []).append(f"전체 {t['chars']}자 → {t['range'][0]}~{t['range'][1]}자")
    return dict(sorted(why.items()))


# ── 쓰기 ─────────────────────────────────────────────────────────────────
def _merge(lines: list[dict], fixed: list[dict], n: int) -> list[dict]:
    out = [dict(l) for l in (lines + [{"fn": "", "text": "", "facts": []}] * n)[:n]]
    for f in fixed:
        try:
            i = int(f.get("i")) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < n and (f.get("text") or "").strip():
            out[i] = {"fn": f.get("fn") or out[i].get("fn"), "text": f["text"].strip(), "facts": f.get("facts") or []}
    return out


def write(P: dict, topic: dict, facts: dict, bench: dict, sk: dict, llm, free_roles: tuple = (), log=print) -> dict:
    honor_rule = ("존댓말(습니다·어요·해요·세요) 0 — 반말 음슴체·전언체(~임/~함/~는데/~다고 함)." if sk["honorific"] == "반말"
                  else "반말 섞지 마라 — 끝까지 존댓말.")
    prompt = DRAFT_PROMPT.format(slug=P["slug"], kind="자막" if sk["mode"] == "captions" else "나레이션", topic=topic.get("topic"),
                                 angle=topic.get("angle") or "-", grounds=_grounds(facts, bench), n=len(sk["roles"]), slots=_slots(sk),
                                 honor=sk["honorific"], honor_rule=honor_rule, orig="\n".join(f"- {t}" for t in sk["orig"][:12]) or "(없음)")
    tries = []
    d, err = llm(prompt, "draft")
    if not d:
        return {"error": f"초안 LLM 실패: {err}", "tries": [{"error": err}], "prompt": prompt}
    lines = [l for l in d.get("lines") or d.get("items") or [] if isinstance(l, dict)]
    chk = check_script(lines, sk, facts, bench, free_roles, topic)
    tries.append({"lines": lines, "check": chk, "model": d.get("_model")})
    meta = {k: d.get(k) for k in ("angle", "twist", "title")}
    log(f"[초안] {len(lines)}줄 · 다시 쓸 줄 {list(chk['bad'])}")
    for r in range(MAX_REWRITES):
        if chk["ok"]:
            break
        bad = chk["bad"] or {k: ["칸 수 맞추기"] for k in range(len(sk["roles"])) if k >= len(lines)}
        fixes = []
        for k, why in bad.items():
            lo, hi = sk["ranges"][k] if k < len(sk["ranges"]) else (0, 0)
            ob = (chk.get("topic_match") or {}).get("other_brand", {}).get(k)
            fixes.append(f"{k + 1}번 칸(역할 {sk['roles'][k] if k < len(sk['roles']) else '-'}) — {', '.join(why)}" + (f"(빼야 할 이름: {ob})" if ob else "")
                         + (f"(소재 제품명 {chk['topic_match']['product_terms']} 를 넣어라)" if "소재 제품명이 대본에 없음" in why else "") + f" · 목표 {lo}~{hi}자")
        if chk["unknown_ids"]:
            fixes.append(f"없는 근거 번호 {chk['unknown_ids']} → 위 목록 번호만")
        cur = _merge(lines, [], len(sk["roles"]))
        d2, err = llm(prompt + "\n\n" + FIX_PROMPT.format(lines=json.dumps([{"i": i + 1, **l} for i, l in enumerate(cur)], ensure_ascii=False),
                                                         fixes="\n".join(fixes), honor=sk["honorific"]), f"rewrite{r + 1}")
        if not d2:
            tries.append({"error": err, "round": r + 1})
            log(f"[다시 쓰기 {r + 1}] LLM 실패 {err} — 멈춤")
            break
        lines = _merge(cur, d2.get("lines") or d2.get("items") or [], len(sk["roles"]))
        chk = check_script(lines, sk, facts, bench, free_roles, topic)
        tries.append({"lines": lines, "check": chk, "model": d2.get("_model"), "round": r + 1, "asked": list(bad)})
        log(f"[다시 쓰기 {r + 1}] 남은 줄 {list(chk['bad'])}")
    return {"lines": lines, "check": chk, "tries": tries, "meta": meta}


# ── 산출 ─────────────────────────────────────────────────────────────────
def build_outputs(out: Path, P: dict, topic: dict, facts: dict, bench: dict, sk: dict, res: dict, bench_path: str | None, llm_calls: list) -> dict:
    allf = {**facts, **{k: {"text": v["text"], "url": v.get("url", "")} for k, v in bench["points"].items()}}
    lines = [{"fn": l.get("fn"), "text": l.get("text"), "facts": l.get("facts") or [],
              "sources": sorted({allf[i]["url"] for i in (l.get("facts") or []) if i in allf and allf[i].get("url")})} for l in res.get("lines") or []]
    sc = topic.get("scores") or {}
    gate = {"scores": {"엔진(LLM)": {name: (sc.get(k) or {}).get("score", "-") for k, name in TF.CRITERIA}} if sc else {},
            "score_note": "topic_find 점수(근거 문장 필수) — 사람/오푸스 판정 전" if sc else "",
            "angle": (res.get("meta") or {}).get("angle") or topic.get("angle"), "twist": (res.get("meta") or {}).get("twist")}
    S = {"engine": "script_engine v1", "topic": topic.get("topic"), "mode": sk["mode"], "preset": str(P.get("preset_dir") or P["slug"]),
         "tteutgi": sk.get("tteutgi"), "roles": sk["roles"], "ranges": [list(r) for r in sk["ranges"]], "orig": sk["orig"], "facts": allf,
         "title": (res.get("meta") or {}).get("title"), "bench": bench_path, "gate": gate,
         "final": {"lines": lines, "check": res.get("check")}, "tries": res.get("tries"), "llm_calls": llm_calls}
    if res.get("error"):
        S["error"] = res["error"]
    (out / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "roles.json").write_text(json.dumps({"slug": P["slug"], "roles": sk["roles"], "mode": sk["mode"],
                                                "note": "프리셋 manifest.roles 로 옮길 값(manifest 주인 preset_save 가 저장)"}, ensure_ascii=False, indent=1), encoding="utf-8")
    c = res.get("check") or {}
    md = [f"# 대본 검사 — {topic.get('topic')}", "", f"- 꼴 {sk['mode']} · 말투 {sk['honorific']} · 칸 {len(sk['roles'])} · 판정 **{'통과' if c.get('ok') else '미통과'}**"
          + (f" · 다시 쓰기 {len([t for t in res.get('tries') or [] if t.get('round')])}회" if res.get("tries") else ""), ""]
    if res.get("error"):
        md += [f"- ⚠ {res['error']}", ""]
    if c.get("total_off"):
        md.append(f"- ⚠ 전체 길이 {c['total_off']['chars']}자 → {c['total_off']['range']}")
    if c.get("sec_est"):
        md.append(f"- 예상 길이 {c['sec_est']}초(cps {sk['cps']})")
    if c.get("unknown_ids"):
        md.append(f"- ⚠ 없는 근거 번호 {c['unknown_ids']}")
    md += ["", "| # | 칸 | 줄 | 근거 | 글자(범위) | 문제 |", "|---|---|---|---|---|---|"]
    for k, l in enumerate(lines):
        rg = sk["ranges"][k] if k < len(sk["ranges"]) else ["-", "-"]
        md.append(f"| {k + 1} | {l['fn']} | {(l['text'] or '').replace('|', '¦')} | {', '.join(l['facts']) or '-'} | {len((l['text'] or '').replace(' ', ''))}({rg[0]}~{rg[1]}) | "
                  f"{', '.join((c.get('bad') or {}).get(k, [])) or 'OK'} |")
    (out / "대본_검사.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    pm = [f"# 대본 계획(선검수) — {topic.get('topic')}", "", "## 소재 5기준", ""]
    if sc:
        pm += ["| 기준 | 점수 | 근거 |", "|---|---|---|"] + [f"| {name} | {(sc.get(k) or {}).get('score', '-')} | {(sc.get(k) or {}).get('why', '')} |" for k, name in TF.CRITERIA]
        ov = topic.get("overlap") or {}
        pm.append(f"\n- 이미 만든 소재 겹침 {ov.get('score')} ({ov.get('with') or '-'}) · 합계 {topic.get('total')}")
    else:
        pm.append("- (소재 점수 없음 — topic_find 후보가 아닌 소재)")
    pm += ["", "## 썰 각도", "", f"- 각도: {gate['angle'] or '-'}", f"- 반전 자리: {gate['twist'] or '-'}", f"- 제목: {S['title'] or '-'}",
           "", "## 대본", ""] + [f"{k + 1}. ({l['fn']}) {l['text']} — 근거 {', '.join(l['facts']) or '없음'}" for k, l in enumerate(lines)]
    used = sorted({i for l in lines for i in l["facts"]})
    pm += ["", "## 근거표", "", "| 번호 | 내용 | 출처 |", "|---|---|---|"] + [f"| {i} | {allf[i]['text'] if i in allf else '(없는 번호)'} | {allf.get(i, {}).get('url', '')} |" for i in used]
    pm += ["", f"- 벤치: {bench_path or '-'}", "- 판정 자리: 이 계획을 사람/조율자가 보고 OK 면 remake.py --script 대본.json --plan-only 로 재료 계획을 잇는다"]
    (out / "대본_계획.md").write_text("\n".join(pm) + "\n", encoding="utf-8")
    return S


def run(preset: str, topic_arg: str, out: Path, bench_path: str | None = None, facts_path: str | None = None, mode: str | None = None,
        roles: list[str] | None = None, tteutgi: str | None = None, pick: str | None = None, free_roles: tuple = (), llm=None, log=print) -> dict:
    llm = llm or TF.LLM()
    P = TF.load_preset(preset, tteutgi)
    topic = load_topic(topic_arg, pick)
    facts = load_facts(facts_path)
    bench = load_bench(bench_path)
    sk = skeleton(P, mode, roles)
    out.mkdir(parents=True, exist_ok=True)
    log(f"[규칙] {P['slug']} · {sk['mode']} · 칸 {len(sk['roles'])} · 말투 {sk['honorific']} · 사실 {len(facts)} · 벤치 포인트 {len(bench['points'])}")
    res = write(P, topic, facts, bench, sk, llm, free_roles, log)
    S = build_outputs(out, P, topic, facts, bench, sk, res, bench_path, llm.calls)
    log(f"[끝] 판정 {'통과' if (res.get('check') or {}).get('ok') else '미통과'} → {out / '대본.json'}")
    return S


def main(argv=None):
    ap = argparse.ArgumentParser(description="대본 쓰기 엔진")
    ap.add_argument("--preset", required=True)
    ap.add_argument("--topic", required=True, help="후보.json#c2 · 후보.json · 소재.json · 그냥 글")
    ap.add_argument("--pick", help="후보.json 에서 고를 id(없으면 recommend[0])")
    ap.add_argument("--bench")
    ap.add_argument("--facts")
    ap.add_argument("--mode", choices=["captions", "narration"])
    ap.add_argument("--roles", default="", help="쉼표 구분 역할 칸(없으면 manifest.roles → 채널 기본)")
    ap.add_argument("--free-roles", default="", help="근거 번호 없이 둘 수 있는 칸 이름(쉼표)")
    ap.add_argument("--tteutgi")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-llm", type=int, default=4, help="무료 제미나이 호출 상한(초안 1 + 다시 쓰기 2 + 여유)")
    a = ap.parse_args(argv)
    S = run(a.preset, a.topic, Path(a.out), a.bench, a.facts, a.mode, [r for r in a.roles.split(",") if r.strip()] or None, a.tteutgi, a.pick,
            tuple(x for x in a.free_roles.split(",") if x), TF.LLM(budget=a.max_llm))
    for l in S["final"]["lines"]:
        print(f"  ({l['fn']}) {l['text']}  {l['facts']}")
    return 0 if (S["final"].get("check") or {}).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
