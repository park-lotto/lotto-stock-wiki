# -*- coding: utf-8 -*-
"""꾸밈(장식) 한 곳 — 관제 263 10-25 사장님 "키치잇은 연예인 본인 사진·큰 손글씨 강조·글자마다 다른 색·소리 글자·원+화살표를 쓰는데
우리 편엔 거의 없다 / 같은 걸 반복하지 말고 틀 안에서 응용·발전 / 규칙 = 종류·횟수·자리·모양 범위, Claude = 영상마다 정해진 질문으로 내용 선택".

판단의 주인(이 파일 하나):
  measure(st)            벤치 줄판독(+추가판독) → 꾸밈 종류별 횟수·초당 빈도·놓인 줄 역할·모양      (실측)
  board_deco(meas, L)    실측 → 판 칸 deco(종류·횟수 범위·역할·모양·why)                                (규칙)
  questions(S, st)       영상마다 Claude 가 답하는 질문 묶음(대본 줄·덩어리 목록이 들어간다)          (회원 지시서도 이것)
  apply(rows, ans, st)   답(deco_answers.json) → 자막 줄(caption_rows 꼴)에 색·변형·스티커를 얹는다     (렌더러가 부름)
  count_rows(rows, T)    결과물(자막표 rows·계획 컷) 꾸밈 종류별 횟수                                    (검사의 재기)
  check(doc, st)         판 deco 값만큼 들어갔나 — quality_gate·preset_card 가 부른다                    (결과물 검사)
  repeat_check(ans, ...) 작업기록 최근 N편과 같은 소리 글자·손글씨 문구 금지                              (반복 방지)
  collect(doc, ans, ok)  통과한 꾸밈 → channel/<벤치>/_kal/꾸밈모음.json                                (발전 재료)

모든 판 필수 칸 = deco. 칸이 없거나 비면 check 가 '미달(판에 deco 없음)' — 판을 채워야 통과한다.
"""
from __future__ import annotations

import json
import re
import statistics as stt
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# 꾸밈 종류 — 렌더러가 그리는 길(how)과 같이 둔다. how 가 None 이면 아직 못 그림(보고만).
KINDS = {
    "word_color":   {"ko": "핵심 낱말 한 색",        "how": "emph(낱말 1개, 팩 5색 돌림)"},
    "multi_color":  {"ko": "한 덩어리 여러 색",      "how": "emph(낱말 2개+ 각자 색 — 어절 단위)"},
    "chunk_color":  {"ko": "덩어리 전체 색",         "how": "emph(덩어리 전체 낱말, 색 하나)"},
    "big":          {"ko": "크게 튀어나옴",          "how": None},   # 자막팩 변형 추가 = 다음(사장님 10-26 간소화)
    "hand_big":     {"ko": "큰 손글씨 강조 자막",    "how": None},   # 자막팩 변형 hand(NanumBrushScript) 시험 렌더만 함 — 추가는 다음
    "tilt":         {"ko": "기울임",                 "how": None},
    "letter_pop":   {"ko": "글자마다 튀어나옴",      "how": None},
    "sound_word":   {"ko": "소리 글자 스티커",       "how": "스티커 sound_word(편집기 renderStickers — 빨강 BMJUA 고정)"},
    "circle_arrow": {"ko": "원+화살표",              "how": "스티커 circle_arrow(fx_target.aim 좌표 — 빨강 고정)"},
    "spark_lines":  {"ko": "강조선",                 "how": "스티커 spark_lines"},
    "gem":          {"ko": "💎",                     "how": "스티커 gem"},
    "heart":        {"ko": "♥",                      "how": "스티커 heart(타이핑 덩어리)"},
    "comment_card": {"ko": "댓글 카드",              "how": "스티커 comment_card"},
    "photo":        {"ko": "연예인 본인 사진 컷",    "how": "재료.json 그림 컷(본인 출처 — 02 원본찾기)"},
}
CAPTION_KINDS = ("word_color", "multi_color", "chunk_color", "big", "hand_big", "tilt", "letter_pop")
STICKER_KINDS = ("sound_word", "circle_arrow", "spark_lines", "gem", "heart", "comment_card")

_STICKER_WHAT = (("ㅋㅋ", "sound_word"), ("두둥", "sound_word"), ("소리", "sound_word"), ("원+화살표", "circle_arrow"), ("빨간원", "circle_arrow"),
                 ("강조선", "spark_lines"), ("💎", "gem"), ("♥", "heart"), ("댓글", "comment_card"))


def _norm(s: str) -> str:
    return re.sub(r"[\s~!?.,·…'\"]", "", str(s or ""))


def line_kinds(L: dict) -> list[str]:
    """줄판독 한 줄(덩어리) → 꾸밈 종류 목록(겹칠 수 있다). 줄판독 칸 이름 그대로(emph·variant·sticker·scene_desc)."""
    out = []
    var = str(L.get("variant") or "")
    emph = [e for e in (L.get("emph") or []) if isinstance(e, dict) and e.get("word")]
    hexes = {str(e.get("hex") or "").upper() for e in emph}
    whole = any(_norm(e["word"]) == _norm(L.get("text")) for e in emph) or bool(re.search(r"전체 ?(분홍|연보라|라일락|하늘|초록|노랑|연하늘)|분홍보라", var))
    if "손글씨" in var:
        out.append("hand_big")
    elif whole:
        out.append("chunk_color")
    elif len(hexes) >= 2 or "여러 색" in var:
        out.append("multi_color")
    elif emph:
        out.append("word_color")
    if re.search(r"크게|출렁|1\.3배", var):
        out.append("big")
    if "기울" in var:
        out.append("tilt")
    if re.search(r"글자마다|음절마다|글자 단위", var):
        out.append("letter_pop")
    for s in L.get("sticker") or []:
        what = str(s.get("what") or "")
        k = next((k for key, k in _STICKER_WHAT if key in what), None)
        if k:
            out.append(k)
    return out


def is_photo(L: dict) -> bool:
    d = str(L.get("scene_desc") or "")
    return ("화보" in d or "사진" in d) and "쿠팡" not in d


def _videos(st: dict) -> list[dict]:
    B = st.get("bench") or {}
    vids = []
    lr = ROOT / B.get("line_reads", "")
    for f in sorted(lr.glob("*.json")) if B.get("line_reads") else []:
        d = json.loads(f.read_text(encoding="utf-8"))
        vids.append({"id": d["id"], "dur": float(d["dur"]), "lines": d["lines"], "from": f"줄판독/{f.name}"})
    extra = ROOT / "channel" / B.get("channel", "_") / "_kal" / "꾸밈_추가판독.json"
    if extra.exists():
        for v in json.loads(extra.read_text(encoding="utf-8"))["videos"]:
            if not any(x["id"] == v["id"] for x in vids):
                vids.append({"id": v["id"], "dur": float(v["dur"]), "lines": v["lines"], "from": "_kal/꾸밈_추가판독.json"})
    return vids


def _q(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p
    a = int(k)
    b = min(a + 1, len(xs) - 1)
    return xs[a] + (xs[b] - xs[a]) * (k - a)


def measure(st: dict) -> dict:
    """벤치 편마다 꾸밈 종류별 횟수·초당 빈도·놓인 줄 역할·모양 + 본인 사진 비율."""
    vids = _videos(st)
    per = []
    roles = {k: Counter() for k in KINDS}
    shapes = {k: Counter() for k in KINDS}
    for v in vids:
        c = Counter()
        photo_s, photo_hook = 0.0, False
        for L in v["lines"]:
            ks = line_kinds(L)
            for k in ks:
                c[k] += 1
                roles[k][L.get("role") or "?"] += 1
                if k in CAPTION_KINDS:
                    shapes[k][str(L.get("variant") or "기본")[:40]] += 1
                    for e in L.get("emph") or []:
                        if isinstance(e, dict) and e.get("hex"):
                            shapes[k][str(e["hex"]).upper()] += 1
                for s in L.get("sticker") or []:
                    if k in STICKER_KINDS and k in (next((kk for key, kk in _STICKER_WHAT if key in str(s.get("what"))), None),):
                        shapes[k][str(s.get("anim") or "")[:50]] += 1
            if is_photo(L):
                photo_s += float(L["t1"]) - float(L["t0"])
                photo_hook = photo_hook or float(L["t0"]) < 1.0
                roles["photo"][L.get("role") or "?"] += 1
        if photo_s:
            c["photo"] = sum(1 for L in v["lines"] if is_photo(L))
        n_lines = len(v["lines"])
        per.append({"id": v["id"], "dur": v["dur"], "lines": n_lines, "from": v["from"], "counts": dict(c),
                    "photo_s": round(photo_s, 2), "photo_share": round(photo_s / v["dur"], 3), "photo_hook": photo_hook,
                    "accents": sorted(k for k in c if k not in ("word_color", "photo"))})
    kinds = {}
    for k in KINDS:
        users = [p for p in per if p["counts"].get(k)]
        rates = [p["counts"].get(k, 0) / p["dur"] for p in per]
        kinds[k] = {"videos": len(users), "share": round(len(users) / max(1, len(per)), 3),
                    "per_video": [p["counts"].get(k, 0) for p in per],
                    "users_median": stt.median([p["counts"][k] for p in users]) if users else 0,
                    "users_max": max([p["counts"][k] for p in users], default=0),
                    "rate_per_10s_median": round(10 * stt.median(rates), 3) if rates else 0.0,
                    "rate_per_10s_p75": round(10 * _q(rates, 0.75), 3),
                    "roles": dict(roles[k].most_common()), "shapes": dict(shapes[k].most_common(8))}
    acc = [len(p["accents"]) for p in per]
    return {"videos": per, "kinds": kinds, "n": len(per),
            "accent_kinds_per_video": {"values": acc, "median": stt.median(acc) if acc else 0},
            "photo": {"share_median": round(stt.median([p["photo_share"] for p in per]), 3) if per else 0,
                      "share_p75": round(_q([p["photo_share"] for p in per], 0.75), 3),
                      "videos": sum(1 for p in per if p["photo_s"]), "hook": sum(1 for p in per if p["photo_hook"])}}


# ── 판 칸 deco(규칙) ─────────────────────────────────────────────────────
CORE_SHARE = 0.5          # 벤치 편 절반 넘게 쓰는 종류 = 매 편 필요(core) · 나머지 = 포인트(accent, 편마다 돌려 고른다)
NOT_DRAWN = tuple(k for k, v in KINDS.items() if not v["how"])
OWN_PHOTO_PREFIX = "own_"  # 본인 사진(연예인 본인 SNS·방송 공식 — 02 원본찾기) 재료 파일 이름 앞머리. 쿠팡·상품 사진(cp_)과 가른다


class DecoError(RuntimeError):
    pass


def board_deco(M: dict, length: float) -> dict:
    """실측(measure) → 판 칸 deco. 횟수는 우리 길이(length 초)로 옮긴다: want = 벤치 10초당 중앙 × length/10, core 범위 = want×0.5~×1.5(반올림, 쓴 편 최대보다 작으면 최대).
    포인트(accent) = core 아닌 종류 — 편마다 accent_min 가지 이상(벤치 편당 포인트 종류 수 중앙), 그리지 못하는 종류(NOT_DRAWN)는 고를 수 없다."""
    K = M["kinds"]
    out = {"_why": (f"벤치 {M['n']}편 실측(tools/calcopy/hybrid/deco.py measure → _kal/꾸밈실측.json — 줄판독 8편 + 꾸밈_추가판독 2편). "
                    f"core = 벤치 편 {int(CORE_SHARE * 100)}% 넘게 쓰는 종류(매 편 횟수 범위 안), accent = 나머지(편마다 accent_min 가지 이상, 최근 편과 같은 소리 글자·문구·조합 금지). "
                    f"core 횟수 = 벤치 10초당 중앙 × 우리 길이 {length}초 / 10 의 ×0.5~×1.5"),
           "made_by": "tools/calcopy/hybrid/deco.py board <판> (measure → board_deco — 기계 산출, 숫자 근거 = _kal/꾸밈실측.json)",
           "length_s": length, "kinds": {}}
    accents = []
    for k, v in K.items():
        if v["videos"] == 0:
            continue
        core = v["share"] > CORE_SHARE
        want = v["rate_per_10s_median"] * length / 10
        if core:
            lo, hi = max(1, round(want * 0.5)), max(round(want * 1.5), int(v["users_max"]))
        else:
            lo, hi = 0, max(1, int(v["users_max"]))
        out["kinds"][k] = {"need": "core" if core else "accent", "min": lo, "max": hi, "drawn": k not in NOT_DRAWN,
                           "bench_videos": f"{v['videos']}/{M['n']}", "per_10s": v["rate_per_10s_median"],
                           "roles": list(v["roles"])[:4], "shape": list(v["shapes"])[:4], "how": KINDS[k]["how"]}
        if not core:
            accents.append(k)
    acc_vals = [sum(1 for k in p["counts"] if k in accents) for p in M["videos"]]
    out["accent_min"] = int(stt.median(acc_vals)) if acc_vals else 0
    out["accent_max"] = max(acc_vals) if acc_vals else 0
    out["_why_accent"] = (f"편마다 포인트 종류 수(벤치 편별 {acc_vals}) 중앙 {out['accent_min']} · 최대 {out['accent_max']} — "
                          f"그리지 못하는 {list(NOT_DRAWN)} 는 벤치에 있어도 고를 수 없다(편집기 주인 몫으로 보고)")
    P = M["photo"]
    mx = round(max(p["photo_share"] for p in M["videos"]), 3) if M["videos"] else 0.0
    out["photo"] = {"own_share_max": mx, "hook_share": round(P["hook"] / max(1, M["n"]), 2),
                    "why": f"벤치 본인 사진(화보·방송 사진) 줄 초 ÷ 길이 편별 최대 {mx} · 중앙 {P['share_median']} · {P['hook']}/{M['n']}편이 첫 1초 안에 사진(훅). "
                           f"쿠팡·상품 사진 상한은 따로 rhythm.photo_share_max(본인 사진 own_ 은 그 셈에서 뺀다)"}
    out["repeat_n"] = 5
    out["_why_repeat"] = "작업기록(channel/작업기록.jsonl deco 칸) 최근 5편과 같은 소리 글자·손글씨 글·여러 색 덩어리 글·같은 포인트 조합을 다시 쓰지 않는다(사장님 10-25 '같은 걸 반복하지 말고 응용·발전')"
    return out


def board(st: dict) -> dict:
    D = st.get("deco")
    if not isinstance(D, dict) or not D.get("kinds"):
        raise DecoError(f"판 {st.get('name')} 에 deco 칸이 없다 — py -m tools.calcopy.hybrid.deco board <판> 으로 벤치 실측에서 채운다")
    return D


# ── 정해진 질문(회원 지시서와 같은 함수) ───────────────────────────────────
DECO_COLORS = ["#FEDD00", "#00FD0B", "#65FEFB", "#FD6B7B", "#BDB4FC"]   # 키치잇 팩 mark.colors 와 같은 5색(벤치 실측 — 자막팩 kitchit)


def questions(S: dict, st: dict, chunks: list | None = None, photos: list | None = None, recent: dict | None = None) -> dict:
    """영상마다 Claude(우리 PC 오푸스·회원 PC 회원 Claude)가 답하는 질문 묶음 — 답은 편 doc 의 deco_answers.json(꼴 = ANSWER_FORM).
    chunks = 자막 덩어리 [{line,text,role}] (없으면 대본 caps·caps_rel 에서) · photos = 본인 사진 후보 파일 · recent = recent_deco()."""
    D = board(st)
    if chunks is None:
        chunks = []
        for L in S.get("lines") or []:
            for c in L.get("caps") or []:
                chunks.append({"line": L["id"], "text": c["text"], "role": L.get("role")})
            for c in L.get("caps_rel") or []:
                chunks.append({"line": L["id"], "text": c[0], "role": L.get("role")})
    rng = {k: (v["min"], v["max"]) for k, v in D["kinds"].items()}
    acc = [k for k, v in D["kinds"].items() if v["need"] == "accent" and v["drawn"]]
    rec = recent or {}
    Q = [
        {"id": "accents", "ask": f"이번 편 포인트 꾸밈 종류를 {D['accent_min']}~{D['accent_max']}가지 고른다(고를 수 있는 것 {acc}). "
                                 f"최근 편 조합 {rec.get('kinds_recent') or '없음'} 과 같으면 하나 이상 바꾼다. 대본에 그 종류가 설 자리가 없으면 고르지 않는다(억지 금지)."},
        {"id": "chunk_color", "ask": f"덩어리 전체 한 색: {rng.get('chunk_color')}개 — 짧고(≤8자) 그 줄의 핵심인 덩어리(벤치 역할 {D['kinds'].get('chunk_color', {}).get('roles')}). 색 = {DECO_COLORS} 중"},
        {"id": "multi_color", "ask": "여러 색: 한 덩어리 안 낱말 2~3개를 각자 다른 색으로(벤치 '이거 바르고 이거 발라!'). 같은 낱말 두 번은 피한다(편집기가 첫 낱말만 칠함)."},
        {"id": "hand_big", "ask": f"큰 손글씨: 감정이 센 짧은 덩어리(≤{HAND_MAX_CHARS}자, 가격·반전·놀람 — 벤치 '화나게 비싸' 가격 줄) 하나. 덩어리 글 그대로(새 문구 금지). "
                                  f"최근 편 손글씨 {rec.get('hand') or '없음'} 과 같은 글 금지"},
        {"id": "big", "ask": f"크게(1.3배): 강조 덩어리 {rng.get('big')}개 — 짧은 단언·반전('안 했잖아')"},
        {"id": "sound_word", "ask": "소리 글자: 화면 전환·공개 순간 덩어리 하나에 붙일 짧은 의성어(1~3자, '두둥'·'짠'·'뿅' 등 — 그 장면 소리·감정에 맞게). "
                                    f"최근 편 소리 글자 {rec.get('sound') or '없음'} 과 같은 말 금지. 자리 x·y(화면 %) = 얼굴·제품·자막을 덮지 않는 곳"},
        {"id": "circle_arrow", "ask": "원+화살표: 덩어리 하나 + 그 덩어리 동안 화면의 강조 대상(제품 글자·부위, 화면 10% 이하)과 상자 [x0,y0,x1,y1](1080×1920 px). "
                                      "계획 접촉 시트(plan/계획_접촉시트.jpg)·fx_target.aim 질문(aim_prompt)으로 잰다. 큰 대상은 특징 부위로"},
        {"id": "photo", "ask": f"본인 사진: 후보 {photos or '(cand_dir own_*.jpg 없음 — 02 원본찾기 본인 출처에서 먼저 찾는다)'} 중 번호와 놓을 줄(훅 첫 1초 권장 — 벤치 {D['photo']['hook_share']}). "
                               f"사진 줄 초 합 ÷ 길이 ≤ {D['photo']['own_share_max']}. 재료.json 그 줄 컷에 own_ 파일로 넣는다"},
    ]
    return {"_why": "deco.questions — 판 deco 칸이 종류·횟수·자리·모양 범위를 정하고, 이 질문의 답이 내용(덩어리·낱말·색·말·좌표·사진)을 고른다",
            "board": D, "chunks": chunks, "questions": Q, "answer_form": ANSWER_FORM}


ANSWER_FORM = {
    "accents": ["hand_big", "multi_color", "sound_word"],
    "items": [
        {"kind": "chunk_color", "line": "N4", "text": "안 밀리더라고요", "color": "#FD6B7B"},
        {"kind": "multi_color", "line": "O2", "text": "이게 유기농이고", "words": [{"word": "이게", "color": "#65FEFB"}, {"word": "유기농이고", "color": "#00FD0B"}]},
        {"kind": "hand_big", "line": "O1", "text": "안 씁니다"},
        {"kind": "big", "line": "N7", "text": "인기래요"},
        {"kind": "sound_word", "line": "N5", "text": "심지어 튜브에", "word": "두둥", "x": 24, "y": 61},
        {"kind": "circle_arrow", "line": "N5", "text": "눈물 안 나는 티어프리라고", "what": "튜브의 TEAR-FREE 글자", "box": [400, 900, 700, 980]},
        {"kind": "photo", "line": "N1", "file": "own_1.jpg", "from": "본인 유튜브 채널 썸네일"},
    ],
}


# ── 답 → 자막 줄 ────────────────────────────────────────────────────────
SOUND_SIZE = 170            # 소리 글자 크기(px, 1080 폭) — 편집기 기본 265(꿀템노트 '쿰')는 키치잇 자막(78)의 3.4배라 화면을 덮는다. 키치잇 ㅋㅋㅋ(_Wa 12.5) 폭 220
HAND_MAX_CHARS = 6


def load_answers(doc) -> dict | None:
    p = Path(doc) / "deco_answers.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _find_row(rows: list, it: dict) -> dict:
    hit = [r for r in rows if r.get("line") == it.get("line") and _norm(r.get("text")) == _norm(it.get("text"))]
    if len(hit) != 1:
        raise DecoError(f"꾸밈 답 {it.get('kind')} {it.get('line')}「{it.get('text')}」 — 자막 덩어리 {len(hit)}개(1개여야). 자막 덩어리 글 그대로 적는다")
    return hit[0]


def apply(rows: list, ans: dict | None, st: dict, log=print) -> list:
    """답(deco_answers.json) → 배치 rows(placement.place 꼴: line·text·show·variant·emph·stickers)에 얹는다. 덩어리를 못 찾으면 멈춘다(조용한 빠짐 금지).
    photo 는 재료(재료.json own_ 파일) 몫이라 여기서 안 다룬다."""
    if not ans:
        return rows
    from tools.calcopy.hybrid import fx_target as FX
    for it in ans.get("items") or []:
        k = it.get("kind")
        if k == "photo":
            continue
        if k not in KINDS or k in NOT_DRAWN:
            raise DecoError(f"꾸밈 답 종류 {k} — 그릴 수 있는 것 {[x for x in KINDS if x not in NOT_DRAWN]}")
        r = _find_row(rows, it)
        if k == "chunk_color":
            r["emph"] = [{"word": r["text"], "color": it["color"]}]
        elif k == "multi_color":
            ws = it.get("words") or []
            if len(ws) < 2 or len({str(w["color"]).upper() for w in ws}) < 2:
                raise DecoError(f"여러 색 {it['line']}「{it['text']}」 — 낱말 2개+ 서로 다른 색")
            if len({_norm(w["word"]) for w in ws}) < len(ws):
                raise DecoError(f"여러 색 {it['line']} 같은 낱말 두 번 — 편집기(scene_marks)는 첫 낱말만 칠한다")
            r["emph"] = [{"word": w["word"], "color": w["color"]} for w in ws]
        elif k == "hand_big":
            if len(_norm(r["text"])) > HAND_MAX_CHARS:
                raise DecoError(f"손글씨 {it['line']}「{r['text']}」 {len(_norm(r['text']))}자 > {HAND_MAX_CHARS}(벤치 '화나게 비싸' 5자)")
            r["variant"], r["emph"] = "hand", []
        elif k == "big":
            r["variant"] = "big"
        elif k == "sound_word":
            w = str(it.get("word") or "")
            if not 1 <= len(_norm(w)) <= 3:
                raise DecoError(f"소리 글자 '{w}' — 1~3자")
            r.setdefault("stickers", []).append({"kind": "sound_word", "text": w, "x": float(it.get("x", 24)), "y": float(it.get("y", 61)),
                                                 "size": int(it.get("size", SOUND_SIZE)), "r": float(it.get("rot", -8)), "site": "answered", "deco": True})
        elif k == "circle_arrow":
            b = [float(v) for v in it["box"]]
            frac = (b[2] - b[0]) * (b[3] - b[1]) / (FX.CANVAS[0] * FX.CANVAS[1])
            if frac > FX.AIM_CIRCLE_FRAC_MAX:
                raise DecoError(f"원 대상 '{it.get('what')}' 화면 {round(frac * 100, 1)}% > {int(FX.AIM_CIRCLE_FRAC_MAX * 100)}% — 특징 부위로(fx_target 규칙)")
            rad = min(FX.AIM_R_MAX, max(FX.AIM_R_MIN, FX.AIM_DIAM_OVER_TARGET * max(b[2] - b[0], b[3] - b[1]) / 2))
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            show = r.get("show") or [None, None]
            r.setdefault("stickers", []).append({"kind": "circle_arrow", "x": round(cx / FX.CANVAS[0] * 100, 2), "y": round(cy / FX.CANVAS[1] * 100, 2),
                                                 "r": round(rad / FX.CANVAS[0] * 100, 2), "site": "answered", "how": "deco_answer", "deco": True,
                                                 "aim": {"what": it.get("what"), "why": "deco_answers.json(정해진 질문 circle_arrow)", "box": [round(v) for v in b],
                                                         "frac": round(frac, 4), "frames": [{"t": show[0], "box": [round(v) for v in b]}]}})
        log(f"[꾸밈] {k} {it['line']}「{it['text']}」")
    return rows


# ── 결과물 세기·검사 ─────────────────────────────────────────────────────
def row_kinds(r: dict) -> list:
    """자막표 한 줄(결과물) → 꾸밈 종류. 줄판독 line_kinds 와 같은 자(낱말 색·덩어리 색·여러 색·변형·스티커)."""
    out = []
    v = str(r.get("variant") or "")
    em = [e for e in (r.get("emph") or []) if isinstance(e, dict) and e.get("word")]
    if v == "hand":
        out.append("hand_big")
    elif em and any(_norm(e["word"]) == _norm(r.get("text")) for e in em):
        out.append("chunk_color")
    elif len(em) >= 2 and len({str(e.get("color") or "").upper() for e in em if e.get("color")}) >= 2:
        out.append("multi_color")
    elif em:
        out.append("word_color")
    if v == "big":
        out.append("big")
    for s in r.get("stickers") or []:
        if s.get("kind") in STICKER_KINDS:
            out.append(s["kind"])
    if r.get("sticker") == "heart":
        out.append("heart")
    return out


def is_own_photo(src) -> bool:
    return Path(str(src or "")).name.startswith(OWN_PHOTO_PREFIX)


def count_result(rows: list, cuts: list, end: float, comment=None) -> dict:
    c = Counter()
    for r in rows:
        for k in row_kinds(r):
            c[k] += 1
    if comment:
        c["comment_card"] += 1
    own = [x for x in cuts if is_own_photo(x.get("src"))]
    if own:
        c["photo"] = len(own)
    share = round(sum(float(x.get("t1", end)) - float(x["t0"]) for x in own) / end, 3) if end else 0.0
    return {"counts": dict(c), "own_photo_share": share, "photo_hook": any(float(x["t0"]) < 1.0 for x in own)}


def check(doc, st: dict, rows: list | None = None, cuts: list | None = None, end: float | None = None) -> dict:
    """결과물 검사(판단 주인) — 꾸밈 종류·횟수가 판 deco 값만큼 들어갔나. quality_gate·preset_card 가 부른다.
    rows·cuts·end 를 안 주면 doc/자막표.json(렌더 결과)·doc/plan/계획_시간표.json(화면 컷)을 읽는다. 판에 deco 칸이 없으면 ok=False(미달)."""
    doc = Path(doc)
    try:
        D = board(st)
    except DecoError as e:
        return {"ok": False, "bad": [str(e)], "rows": [], "accents": []}
    comment = None
    if rows is None:
        tab = json.loads((doc / "자막표.json").read_text(encoding="utf-8")) if (doc / "자막표.json").exists() else {}
        rows, comment = tab.get("rows") or [], tab.get("comment")
    if cuts is None:
        pl = doc / "plan" / "계획_시간표.json"
        T = json.loads(pl.read_text(encoding="utf-8"))["timeline"] if pl.exists() else {}
        cuts, end = T.get("cuts") or [], float(end or T.get("end") or 0)
    R = count_result(rows, cuts, float(end or 0), comment)
    got = R["counts"]
    out, bad = [], []
    for k, v in D["kinds"].items():
        n = int(got.get(k, 0))
        ok = v["min"] <= n <= v["max"]
        out.append({"kind": k, "ko": KINDS[k]["ko"], "need": v["need"], "got": n, "range": [v["min"], v["max"]], "ok": ok})
        if not ok:
            bad.append(f"{KINDS[k]['ko']}({k}) {n}개 — 판 {v['need']} {v['min']}~{v['max']}")
    acc = sorted(k for k, v in D["kinds"].items() if v["need"] == "accent" and got.get(k))
    if len(acc) < D["accent_min"]:
        bad.append(f"포인트 꾸밈 {len(acc)}가지 {acc} < 판 accent_min {D['accent_min']}")
    if R["own_photo_share"] > D["photo"]["own_share_max"] + 1e-9:
        bad.append(f"본인 사진 비중 {R['own_photo_share']} > 판 {D['photo']['own_share_max']}")
    return {"ok": not bad, "bad": bad, "rows": out, "accents": acc, "own_photo_share": R["own_photo_share"], "photo_hook": R["photo_hook"]}


# ── 반복 금지·꾸밈모음 ────────────────────────────────────────────────────
def summary(ans: dict | None) -> dict | None:
    """작업기록 deco 칸 — 편마다 쓴 꾸밈 내용(소리 글자·손글씨·여러 색 덩어리·종류)."""
    if not ans:
        return None
    its = ans.get("items") or []
    return {"kinds": sorted({i["kind"] for i in its}), "sound": [i.get("word") for i in its if i["kind"] == "sound_word"],
            "hand": [i.get("text") for i in its if i["kind"] == "hand_big"], "multi": [i.get("text") for i in its if i["kind"] == "multi_color"],
            "circle": [i.get("what") for i in its if i["kind"] == "circle_arrow"]}


def recent_deco(bench: str, n: int = 5, skip_doc: str | None = None, log_path=None) -> dict:
    from tools.calcopy import work_log as WL
    rows = [r for r in WL.read(log_path or WL.LOG) if r.get("bench_channel") == bench and r.get("deco")]
    if skip_doc:
        rows = [r for r in rows if skip_doc not in str(r.get("note") or "") + str(r.get("final_path") or "")]
    rows = rows[-n:]
    return {"n": len(rows), "sound": sorted({w for r in rows for w in r["deco"].get("sound") or []}),
            "hand": sorted({w for r in rows for w in r["deco"].get("hand") or []}), "multi": sorted({w for r in rows for w in r["deco"].get("multi") or []}),
            "kinds_recent": [r["deco"].get("kinds") for r in rows]}


def repeat_check(ans: dict | None, st: dict, skip_doc: str | None = None, log_path=None) -> list:
    """최근 N편(판 deco.repeat_n)과 같은 소리 글자·손글씨 글·여러 색 덩어리 글·같은 포인트 조합이면 거절 목록."""
    if not ans:
        return []
    D = board(st)
    rec = recent_deco(st["bench"]["channel"], int(D.get("repeat_n", 5)), skip_doc, log_path)
    me = summary(ans)
    bad = [f"소리 글자 '{w}' — 최근 {rec['n']}편에 이미 씀" for w in me["sound"] if w in rec["sound"]]
    bad += [f"손글씨 '{w}' — 최근 편에 이미 씀" for w in me["hand"] if w in rec["hand"]]
    bad += [f"여러 색 '{w}' — 최근 편에 이미 씀" for w in me["multi"] if w in rec["multi"]]
    acc = sorted(k for k in me["kinds"] if D["kinds"].get(k, {}).get("need") == "accent")
    if acc and any(sorted(k for k in (ks or []) if D["kinds"].get(k, {}).get("need") == "accent") == acc for ks in rec["kinds_recent"]):
        bad.append(f"포인트 조합 {acc} — 최근 편과 같다(하나 이상 바꾼다)")
    return bad


def collect(doc, st: dict, ans: dict | None, verdict: dict):
    """통과한 꾸밈(check ok) → channel/<벤치>/_kal/꾸밈모음.json 에 쌓는다(다음 편이 '이미 쓴 것'과 '잘 된 꼴'을 본다)."""
    if not ans or not verdict.get("ok"):
        return None
    p = ROOT / "channel" / st["bench"]["channel"] / "_kal" / "꾸밈모음.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"_why": "통과한 편의 꾸밈 내용(deco.collect) — 반복 금지·응용 재료", "items": []}
    rel = Path(doc).resolve()
    try:
        rel = rel.relative_to(ROOT)
    except ValueError:
        pass
    key = str(rel).replace("\\", "/")
    data["items"] = [x for x in data["items"] if x.get("doc") != key]
    data["items"].append({"doc": key, "style": st.get("name"), "summary": summary(ans), "items": ans.get("items"), "check": verdict.get("rows")})
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    from tools.calcopy.hybrid import styles as SS
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    if cmd == "measure":
        st = SS.load(sys.argv[2])
        M = measure(st)
        out = ROOT / "channel" / st["bench"]["channel"] / "_kal" / "꾸밈실측.json"
        out.write_text(json.dumps({"_made_by": "tools/calcopy/hybrid/deco.py measure " + sys.argv[2], **M}, ensure_ascii=False, indent=1), encoding="utf-8")
        for p in M["videos"]:
            print(p["id"], p["dur"], p["counts"], "사진", p["photo_share"])
        for k, v in M["kinds"].items():
            print(f"{k:13s} 편 {v['videos']}/{M['n']}  편당(쓴 편 중앙) {v['users_median']}  최대 {v['users_max']}  10초당 {v['rate_per_10s_median']}  역할 {v['roles']}")
        print("포인트 종류/편", M["accent_kinds_per_video"], "사진", M["photo"])
        print("→", out)
    elif cmd == "board":       # 실측 → 판 칸 deco(styles/<판>.json 에 쓴다)
        name = sys.argv[2]
        st = SS.load(name)
        L = (float(st["length"]["min"]) + float(st["length"]["max"])) / 2
        D = board_deco(measure(st), L)
        p = SS.DIR / f"{name}.json"
        raw = json.loads(p.read_text(encoding="utf-8"))
        raw["deco"] = D
        p.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(D, ensure_ascii=False, indent=1))
    elif cmd == "ask":         # 질문 묶음 → <doc>/plan/deco_questions.json
        st, doc = SS.load(sys.argv[2]), Path(sys.argv[3])
        S = json.loads((doc / "대본.json").read_text(encoding="utf-8"))
        M = json.loads((doc / "재료.json").read_text(encoding="utf-8"))
        photos = sorted(p.name for p in Path(M["cand_dir"]).glob(OWN_PHOTO_PREFIX + "*"))
        Q = questions(S, st, photos=photos, recent=recent_deco(st["bench"]["channel"], 5, skip_doc=doc.name))
        (doc / "plan").mkdir(exist_ok=True)
        (doc / "plan" / "deco_questions.json").write_text(json.dumps(Q, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(Q["questions"], ensure_ascii=False, indent=1))
    elif cmd == "check":       # 결과물 검사 + 반복 금지
        st, doc = SS.load(sys.argv[2]), Path(sys.argv[3])
        v = check(doc, st)
        rep = repeat_check(load_answers(doc), st, skip_doc=doc.name)
        print(json.dumps({**v, "repeat": rep}, ensure_ascii=False, indent=1))
        sys.exit(0 if v["ok"] and not rep else 1)
