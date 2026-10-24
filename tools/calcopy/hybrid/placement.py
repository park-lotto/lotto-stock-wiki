# -*- coding: utf-8 -*-
"""자막·효과 **배치 규칙** — 벤치 줄판독에서 세고(count), 편마다 계산한다(place). 관제 097, 2026-10-19.

사장님 10-19(강한 규칙): 자막팩을 모든 줄에 똑같이 바르지 않는다. 벤치는 영상마다·장면마다 다르게 들어간다
(어느 덩어리에 팝/타이핑/강조색/스티커/효과음이 붙나). 꾸밈이 없는 덩어리·구간은 꾸미지 않는다(없는 것도 스타일).

판단 주인:
  · 규칙 세기   = count(판 설정)  → 판 설정 placement.counted (벤치 8편 줄판독 + 효과음 신호 표 sfx_events_rules)
  · 편마다 배치 = place(rows, 판 설정, 씨앗) — **이 함수 하나**. 렌더러(render_bench)·자막표·검사(check_place)가 이걸 부른다.
자막팩(caption-motions.js)은 효과의 '모양'만, 어디에 붙나는 여기서만 정한다.

어떻게 편마다 다르게(10-19 줄판독 실측: 키치잇 Nv99 = 꾸밈 거의 없음·BRa = 타이핑 10·💎3, 편마다 결이 크게 다르다 →
벤치 8편을 한 평균으로 뭉개면 '어느 편도 아닌' 영상이 된다):
  ① 씨앗(편 slug)으로 **본보기 벤치 편 하나**를 고른다(8편 고르게) — 같은 편은 늘 같은 본보기, 편이 여럿이면 벤치 편들이 골고루.
  ② 칸(slot = 화자 narr/orig × 말 차례의 첫 덩어리 first/rest)마다 본보기 편의 등장 비율(팝·컷·반투명·타이핑…)을 우리 덩어리 수에 나눠 준다.
     본보기 편에 그 칸이 없으면 8편 합계 비율.
  ③ 강조 낱말 비율·스티커 종류와 개수·효과음 수도 본보기 편 그대로(우리 덩어리에 조건 맞는 자리가 있을 때만).
  ④ 어느 덩어리에 붙나 = 조건(lex: 감탄·고급·값·물음, 대본 key 낱말)이 맞는 덩어리 먼저, 나머지는 고르게 펼침.

10-24 표준 §3-3 A1·A2·A3(관제 263, 지시서 03) — 이 함수가 전환·효과음·짤·스티커 자리까지 한 곳에서 정한다:
  ⑤ 효과음 = 본보기 편 줄판독 sfx{kind,t}·role 이 있으면 역할(훅·공개·반전·끝·본문) 비율 × 종류 비율(rules.sfx.kinds) × 시각 편차(벤치 중앙),
     없으면 옛 길(효과음 신호표 sfx_events 의 고립 후보 자리). 신호표 = channel/<slug>/_kal/sfx_events.json(engine/sound/sfx_events.py <slug>).
  ⑥ 전환 = transitions[{t,kind,ms}] — 본보기 편 줄판독 transition 비율을 **컷 경계**에 나눈다(짧은 컷 < cond.min_cut_s 엔 안 붙임,
     화자 바뀜·공개 줄 앞 먼저). 옛 흰 번쩍(rules.flash)은 transitions kind=flash 로 들어가고 flashes 는 거기서 뽑은 뷰다(한 자리에서만 정한다).
  ④ 스티커·짤 자리 = rules.stickers.<kind>.target(face|object|caption_side|fixed{x,y}+why) → locate(검출, hybrid/fx_target.locator)로 받는다.
     검출이 없으면(locate=None) 자리는 '받을 것'(target)으로 남기고 check_place 가 미해결로 센다 — 눈대중 좌표로 메우지 않는다.

    PYTHONUTF8=1 py tools/calcopy/hybrid/placement.py count <판> [--top] [--dry]  # 벤치 줄판독 → 판 설정 placement.counted 갱신(--dry = 쓰지 않고 출력만)
                                                                          # --top = 상위 편 묶음 counted.top + channel/<slug>/_kal/상위편_목표.json density·hook(지시서 15)
    PYTHONUTF8=1 py tools/calcopy/hybrid/placement.py show <판>           # 센 규칙 표
    PYTHONUTF8=1 py tools/calcopy/hybrid/placement.py plan <doc> <work> --version <판>   # 배치만(렌더 없이) → <work>/plan/자막표.json
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SLOTS = ("narr.first", "narr.rest", "orig.first", "orig.rest")
LEX = {
    "excl": r"!|대박|너무|진짜|완전|와우|와~|우와|헐|미쳤|최고|짱|맛있|예쁘|좋아|감동|난리",
    "lux": r"고급|명품|부내|부자|럭셔리|프리미엄|귀티|비싼|비싸|사악|억|백만|천만|수천",
    "price": r"\d+\s*(원|만|천)|가격|값|가성비|만원|원대|세일|할인",
    "ask": r"\?",
}


def lex_of(text: str) -> list[str]:
    return [k for k, p in LEX.items() if re.search(p, text or "")]


def norm_enter(s: str) -> str:
    """줄판독 enter 칸(자유 글) → pop|cut|fade|typing|append|other. '타이핑 아님'·'전체 한 번에' 같은 부정이 먼저."""
    s = (s or "").lower()
    if re.search(r"타이핑\s*아님|타이핑 없음|전체 한 번에|instant|^cut|컷인", s):
        return "pop" if re.search(r"작게 시작|튀|pop|확대", s) else "cut"
    if re.search(r"typing|타이핑|한 자씩|글자씩|1자씩", s):
        return "typing"
    if re.search(r"pop|작게 시작|튀어|확대|넘쳤", s):
        return "pop"
    if re.search(r"fade|반투명|서서히|flash", s):
        return "fade"
    if re.search(r"append|이어 붙", s):
        return "append"
    return "other"


def sticker_kind(what: str) -> str:
    w = what or ""
    # question·yellow_label·cursor·hand_x = 지시서 03→15 넘김(10-25 줄판독 '기타' 실측: 노랑 물음표+동심원 2·노랑 글자 라벨 6·마우스 손가락 포인터 1·주황 손그림 X 6) —
    # '노랑 물음표' 가 '노랑 글자 라벨' 보다 먼저(같은 노랑). 세기 어휘일 뿐 — 그리기는 렌더러(02), 배치는 rules.stickers 에 그 kind 가 있을 때만.
    for k, p in (("gem", r"💎|다이아"), ("heart", r"♥|하트"), ("question", r"물음표"), ("hand_x", r"손그림\s*X|손그림\s*엑스"),
                 ("cursor", r"마우스|커서|손가락\s*포인터"), ("yellow_label", r"노랑\s*글자\s*라벨|노란\s*글자\s*라벨"),
                 ("spark_lines", r"강조선|\\\s*\||반짝|✦|별"), ("circle_arrow", r"빨간\s*원|화살표|동그라미"),
                 ("kk_doodle", r"ㅋㅋ"), ("comment_card", r"댓글"), ("object_pop", r"누끼|3D|입체|사진 스티커")):
        if re.search(p, w):
            return k
    return "other"


def slot_of(speaker: str, first: bool) -> str:
    return f"{speaker}.{'first' if first else 'rest'}"


# 줄판독 칸 접기(지침서 §6 어휘 + 자유 글) — 세기(count)·배치(place)·검사(check_place)가 같은 접기를 쓴다
ROLES = ("hook", "reveal", "twist", "end", "body")
TRANS_DRAWABLE = ("zoomblur", "flash", "black")      # 렌더러가 그릴 전환(표준 §3-3 A1) — cut 은 전환 없음, other(회오리 등)는 못 그림
TWIST_LEX = r"근데|하지만|그런데|반전|알고 보니|사실은|의외로"


def role_key(s) -> str:
    """줄 역할 자유 글 → hook|reveal|twist|end|body. '사회 반응 끝'·'끝' = end, '공개'·'정체' = reveal."""
    s = str(s or "").lower()
    for k, p in (("hook", r"훅|hook"), ("reveal", r"공개|정체|reveal"), ("twist", r"반전|twist"), ("end", r"끝|마무리|ending|^end")):
        if re.search(p, s):
            return k
    return "body"


def trans_key(s) -> str:
    """줄판독 transition 칸 → cut|zoomblur|flash|black|other. none·빈칸·'같은 컷 안' = cut(전환 없음)."""
    s = str(s if s is not None else "").lower()
    if re.search(r"zoom|줌", s):
        return "zoomblur"
    if re.search(r"flash|번쩍|흰", s):
        return "flash"
    if re.search(r"black|검은|암전", s):
        return "black"
    if not s or re.search(r"^cut|^none|컷|하드", s):
        return "cut"
    return "other"


def sfx_key(s) -> str | None:
    """줄판독 sfx.kind → ding|whoosh|pop|laugh|wow|other. '원본 동작음·타격음' 처럼 원본에 든 소리(벤치가 얹은 게 아님)는 None."""
    s = str(s or "")
    if re.search(r"원본|원음|^\d", s):
        return None
    for k, p in (("ding", r"띵|띠링|딩|ding|tonal"), ("whoosh", r"휙|슉|whoosh|swish"), ("pop", r"뽁|팝|톡|뿅|pop"),
                 ("laugh", r"웃음|laugh"), ("wow", r"탄성|wow")):
        if re.search(p, s, re.I):
            return k
    return "other"


def row_roles(out: list[dict]) -> list[str]:
    """우리 덩어리 역할 — 대본 줄 role 이 있으면 그것(접기), 없으면 박자 어림: 첫 줄 = 훅, 끝 줄 = 끝,
    제품 이름(key)이 훅 밖에서 처음 나온 덩어리 = 공개, 반전 낱말 = 반전, 나머지 = 본문."""
    if not out:
        return []
    first, last = out[0]["line"], out[-1]["line"]
    roles, seen_key = [], False
    for r in out:
        if r.get("role"):
            roles.append(role_key(r["role"])); continue
        if r["line"] == first:
            roles.append("hook")
        elif r["line"] == last:
            roles.append("end")
        elif r.get("key") and not seen_key:
            roles.append("reveal"); seen_key = True
        elif re.search(TWIST_LEX, r.get("text") or ""):
            roles.append("twist")
        else:
            roles.append("body")
        if r.get("key") and r["line"] != first:
            seen_key = True
    return roles


# ── 세기 ──────────────────────────────────────────────────────────────
def _bench_rows(path: Path) -> tuple[list[dict], dict]:
    d = json.loads(path.read_text(encoding="utf-8"))
    rows = [l for l in d.get("lines") or [] if not str(l.get("layer", "")).startswith("원본")]   # 원본에 박힌 층은 벤치 채널이 얹은 게 아니다
    prev = None
    for l in rows:
        sp = "narr" if str(l.get("speaker", "")).startswith("나레") else "orig"
        l["_sp"], l["_first"], prev = sp, sp != prev, sp
        l["_enter"] = norm_enter(str(l.get("enter", "")))
        l["_lex"] = lex_of(l.get("text", ""))
    return rows, d


def sfx_events_path(style: dict) -> tuple[Path | None, str | None]:
    """(판단 주인: 벤치 효과음 신호표 자리) 표준 §3-3 A2 — 채널마다 자기 파일 `channel/<slug>/_kal/sfx_events.json`(키 = 편 id).
    그 파일이 있으면 그것. 없고 판 칸 bench.sfx_events 가 옛 공유 파일(키 `<sfx_key>/<id>`)을 가리키면 그 파일 + 접두(경보 출력 —
    `py tools/calcopy/engine/sound/sfx_events.py <slug>` 로 1회 변환하라). 반환 (경로, 접두 | None)."""
    B = style["bench"]
    slug = B.get("channel") or B.get("sfx_key") or (Path(B["line_reads"]).parts[1] if B.get("line_reads") else None)
    own = ROOT / "channel" / slug / "_kal" / "sfx_events.json" if slug else None
    if own and own.exists():
        return own, None
    if B.get("sfx_events"):
        p = ROOT / B["sfx_events"]
        if p == own:
            return None, None
        print(f"[placement] 경보: {slug} 효과음 신호표가 옛 공유 파일({B['sfx_events']}) — "
              f"`py tools/calcopy/engine/sound/sfx_events.py {slug}` 로 channel/{slug}/_kal/sfx_events.json 을 만들어라", file=sys.stderr)
        return p, B.get("sfx_key") or slug
    return None, None


def _sfx_table(style: dict) -> dict:
    p, prefix = sfx_events_path(style)
    if not p or not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for k, v in d.items():
        if k == "_meta" or not isinstance(v, dict):       # 편 id 가 _ 로 시작할 수 있다(_Wa4IehA6yE) — 표식 칸은 _meta 하나뿐
            continue
        if prefix:
            if not k.startswith(prefix + "/"):
                continue
            k = k.split("/", 1)[1]
        where = []
        for e in (v["cand_kept"] if isinstance(v.get("cand_kept"), list) else v.get("cand")) or []:     # 받아쓰기 거름이 있으면 남은 후보만(sfx_events.filter_channel)
            near = e.get("near") or {}
            w = min(near, key=near.get) if near else "none"
            where.append(w if near.get(w, 9) <= 0.3 else "none")
        out[k] = where
    return out


def count(style: dict) -> dict:
    """벤치 줄판독(덩어리) + 효과음 신호 표 → 편마다·칸마다 빈도. 반환 꼴 = 판 설정 placement.counted."""
    B = style["bench"]
    files = sorted((ROOT / B["line_reads"]).glob("*.json"))
    if not files:
        raise SystemExit(f"줄판독이 없다: {B['line_reads']}")
    sfx = _sfx_table(style)
    allslot = defaultdict(lambda: {"n": 0, "enter": Counter(), "emph": 0})
    videos = []
    for f in files:
        rows, d = _bench_rows(f)
        vid = d.get("id", f.stem)
        sl = defaultdict(lambda: {"n": 0, "enter": Counter(), "emph": 0})
        stick, variants = Counter(), Counter()
        stick_lex = defaultdict(Counter)
        trans, n_trans, roles, sfx_lines = Counter(), 0, Counter(), []
        for k_, l in enumerate(rows):
            roles[role_key(l.get("role"))] += 1
            if k_ and l.get("transition") not in (None, ""):      # 잰 줄만 분모(null·빈 칸 = 안 잰 것, '전환 없음(cut·none)'과 다르다)
                n_trans += 1; trans[trans_key(l.get("transition"))] += 1
            s = l.get("sfx")
            if isinstance(s, dict) and s.get("kind"):
                kk = sfx_key(s["kind"])
                if kk:
                    t = s.get("t")
                    off = round(float(t) - float(l.get("t0", 0)), 3) if isinstance(t, (int, float)) and isinstance(l.get("t0"), (int, float)) else None
                    sfx_lines.append({"kind": kk, "role": role_key(l.get("role")), "t": t, "off": off, "basis": s.get("basis")})
        for l in rows:
            key = slot_of(l["_sp"], l["_first"])
            for s in (sl[key], allslot[key]):
                s["n"] += 1; s["enter"][l["_enter"]] += 1; s["emph"] += bool(l.get("emph"))
            v = str(l.get("variant") or "")
            if v and v != "기본":
                variants[v] += 1
            for st in l.get("sticker") or []:
                k = sticker_kind(st.get("what", "") if isinstance(st, dict) else str(st))
                stick[k] += 1
                for x in l["_lex"] or ["none"]:
                    stick_lex[k][x] += 1
        videos.append({"id": vid, "n": len(rows),
                       "slots": {k: {"n": s["n"], "enter": dict(s["enter"].most_common()), "emph": s["emph"]} for k, s in sl.items()},
                       "stickers": dict(stick), "sticker_lex": {k: dict(c) for k, c in stick_lex.items()}, "variants": dict(variants),
                       "sfx": sfx.get(vid, []), "no_caption": len(d.get("no_caption") or []),
                       "transitions": dict(trans), "n_trans": n_trans, "roles": dict(roles), "sfx_lines": sfx_lines})
    nv = len(videos)
    tr_all = Counter(); n_tr_all = sum(v["n_trans"] for v in videos)
    for v in videos:
        tr_all.update(v["transitions"])
    sk_all = Counter(e["kind"] for v in videos for e in v["sfx_lines"])
    out = {"made_by": "tools/calcopy/hybrid/placement.py count", "source": B["line_reads"], "n_videos": nv,
           "slots": {k: {"n": s["n"], "enter": {e: round(c / s["n"], 3) for e, c in s["enter"].most_common()}, "emph": round(s["emph"] / s["n"], 3)}
                     for k, s in sorted(allslot.items())},
           "share": {"emph": round(sum(1 for v in videos if any(s["emph"] for s in v["slots"].values())) / nv, 3),
                     "typing": round(sum(1 for v in videos if any(s["enter"].get("typing") for s in v["slots"].values())) / nv, 3),
                     "sfx": round(sum(1 for v in videos if v["sfx"]) / nv, 3)},
           "stickers": {k: round(sum(1 for v in videos if v["stickers"].get(k)) / nv, 3) for k in sorted({k for v in videos for k in v["stickers"]})},
           "transition": {k: round(c / n_tr_all, 3) for k, c in tr_all.most_common()} if n_tr_all else {},     # 줄 경계당 전환 종류 비율(잰 줄만)
           "sfx_kinds": {k: round(c / sum(sk_all.values()), 3) for k, c in sk_all.most_common()} if sk_all else {},
           "videos": videos}
    return out


# ── 상위 편 묶음(표준 §12-2·§12-4, 지시서 15) ─────────────────────────────────
DENSITY = {"fx_rate_narr": "fx.rate.나레", "fx_rate_orig": "fx.rate.원음", "sfx_rate": "sfx.rate", "sticker_rate": "sticker.rate"}
TOP_FILE = "상위편_목표.json"        # channel/<slug>/_kal/ — 14 가 만든 파일(scene_fit 칸) · 여기선 density·hook 칸만 더한다


def top_of(style: dict, counted: dict) -> dict:
    """(판단 주인: 업그레이드 판 효과 밀도 목표값) 상위 편(조회 상위 50%) 묶음 집계 — 선정 = upgrade_table.Ctx.top(같은 함수 import),
    밀도 = kal_analyze._stats(upgrade_table.m_density 가 벤치를 재는 **같은 자**) 의 편마다 값 → p75·max(사분위 = upgrade_table._q).
    반환 {ids, slots(상위 편 칸 합), stickers(합), sfx(상위 편 줄판독 sfx_lines 모음), per_video{id:{밀도}}, p75{밀도}, max{밀도}, hook{…}}."""
    from tools.calcopy.engine import upgrade_table as UT
    C = UT.Ctx(style, ROOT, ROOT)
    docs = C.top()
    ids = [d["id"] for d in docs]
    K = C.K
    per = {}
    for d in docs:
        s = K._stats(d.get("lines") or [], float(d.get("dur") or 0))
        per[d["id"]] = {k: s.get(v) for k, v in DENSITY.items()}
    p75 = {k: UT._q([v[k] for v in per.values()], 75) for k in DENSITY}
    mx = {k: (max(x for x in (v[k] for v in per.values()) if isinstance(x, (int, float))) if any(isinstance(v[k], (int, float)) for v in per.values()) else None)
          for k in DENSITY}
    vids = [v for v in counted.get("videos") or [] if v["id"] in ids]
    slots = defaultdict(lambda: {"n": 0, "enter": Counter(), "emph": 0})
    stick = Counter()
    for v in vids:
        for k, s in v["slots"].items():
            slots[k]["n"] += s["n"]; slots[k]["emph"] += s["emph"]; slots[k]["enter"].update(s["enter"])
        stick.update(v.get("stickers") or {})
    return {"made_by": "placement.top_of(upgrade_table.Ctx.top · kal_analyze._stats)", "group": "조회 상위 50%", "ids": ids,
            "views": {i: C.views().get(i) for i in ids},
            "slots": {k: {"n": s["n"], "enter": dict(s["enter"]), "emph": s["emph"]} for k, s in slots.items()},
            "stickers": dict(stick), "sfx": [e for v in vids for e in v.get("sfx_lines") or []],
            "per_video": per, "p75": p75, "max": mx, "hook": hook_of(C, docs)}


def hook_of(C, docs: list[dict]) -> dict:
    """상위 편 훅 3초(표준 §12-4): 첫 컷 길이(upgrade_table._first_cut = scene_cuts, 벤치 원본 — 우리 완성본과 같은 함수) 중앙 ·
    0초 얼굴 비율(줄판독 frame0.face_frac 숫자) 중앙 · 첫 꾸밈 줄 시각(kal_analyze._decorated) 중앙. 못 잰 칸은 None + why."""
    import statistics
    from tools.calcopy.engine import upgrade_table as UT
    K = C.K
    fc, ff, fx, miss = {}, {}, {}, []
    for d in docs:
        i = d["id"]
        mp4 = C.src / f"{i}.mp4" if C.src else None
        if mp4 and mp4.exists() and C.bench_win():
            try:
                fc[i] = UT._first_cut(K, mp4, C.bench_win())
            except Exception as e:          # noqa: BLE001 — 못 잰 편은 why 에 남긴다(조용히 0 금지)
                miss.append(f"{i} 첫 컷 못 잼 {type(e).__name__}")
        else:
            miss.append(f"{i} 원본 영상 없음(src_dir)")
        f0 = d.get("frame0") if isinstance(d.get("frame0"), dict) else {}
        m = re.search(r"\d+(?:\.\d+)?", str(f0.get("face_frac", "")))
        if m:
            ff[i] = float(m.group())
        first = next((l for l in d.get("lines") or [] if (l.get("layer") or "채널") != "원본박힘" and any(K._decorated(l).values())), None)
        if first is not None and isinstance(first.get("t0"), (int, float)):
            fx[i] = round(float(first["t0"]), 3)
    med = lambda xs: round(statistics.median([x for x in xs if isinstance(x, (int, float))]), 3) if any(isinstance(x, (int, float)) for x in xs) else None  # noqa: E731
    return {"first_cut_sec_p50": med(fc.values()), "face_or_object_frac": med(ff.values()), "first_fx_t": med(fx.values()),
            "per_video": {"first_cut": fc, "face_frac": ff, "first_fx_t": fx},
            "why": "첫 컷 = upgrade_table._first_cut(벤치 원본) · 0초 얼굴 = 줄판독 frame0.face_frac(눈 어림 숫자) · 첫 꾸밈 = kal_analyze._decorated 첫 줄 t0"
                   + (f" · 못 잼: {miss}" if miss else "")}


def write_top(style: dict, top: dict) -> Path | None:
    """상위편_목표.json 에 density·hook 칸만 더한다(scene_fit 칸 = 14 주인, 손대지 않음)."""
    slug = (style.get("bench") or {}).get("channel")
    if not slug:
        return None
    p = ROOT / "channel" / slug / "_kal" / TOP_FILE
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    d["density"] = {"made_by": "tools/calcopy/hybrid/placement.py count <판> --top (top_of)", "group": top["group"], "top_ids": top["ids"],
                    "rule": "업그레이드 판 목표 = 상위 편 p75 · 상한 = 상위 편 max(표준 §12-2·§12-4) — upgrade_table.m_density 와 같은 자(kal_analyze._stats)",
                    **{k: {"p75": top["p75"][k], "max": top["max"][k], "per_video": {i: v[k] for i, v in top["per_video"].items()}} for k in DENSITY}}
    d["hook"] = {"made_by": "placement.hook_of", "top_ids": top["ids"], **top["hook"]}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def top_ids_saved(style: dict) -> list[str]:
    """상위 편 id — 상위편_목표.json density.top_ids(count --top 이 적은 것). 판 counted.top 이 없을 때 효과음 역할 근거를 모으는 데 쓴다."""
    slug = (style.get("bench") or {}).get("channel")
    p = ROOT / "channel" / slug / "_kal" / TOP_FILE if slug else None
    return list(((json.loads(p.read_text(encoding="utf-8")).get("density") or {}).get("top_ids") or []) if p and p.exists() else [])


def density_targets(style: dict) -> dict | None:
    """(판단 주인: 이 판이 targets 모드인가·목표 밀도 얼마인가) 판에 `targets` 칸이 있으면(업그레이드 판, 07 주인) 목표 = 상위편_목표.json density
    (같은 자 재측정 — §12-5 'targets 의 출처') p75, 상한 = max. 그 파일에 density 가 없으면 판 counted.top, 그것도 없으면 판 targets.sfx.per_s
    (꾸밈 비율 targets.fx.deco_rate 는 다른 자 — 줄판독 전체 줄 꾸밈 — 라 쓰지 않는다, 로그에 남김). 반환 {밀도: {goal, cap, src}} | None(1차 판 = 옛 동작)."""
    T = style.get("targets")
    if not T:
        return None
    slug = (style.get("bench") or {}).get("channel")
    p = ROOT / "channel" / slug / "_kal" / TOP_FILE if slug else None
    D = (json.loads(p.read_text(encoding="utf-8")).get("density") if p and p.exists() else None) or {}
    src = f"channel/{slug}/_kal/{TOP_FILE} density"
    if not D:
        top = ((style.get("placement") or {}).get("counted") or {}).get("top") or {}
        D = {k: {"p75": (top.get("p75") or {}).get(k), "max": (top.get("max") or {}).get(k)} for k in DENSITY} if top else {}
        src = "판 placement.counted.top"
    out = {k: {"goal": v["p75"], "cap": v.get("max"), "src": src} for k, v in D.items() if k in DENSITY and isinstance(v, dict) and isinstance(v.get("p75"), (int, float))}
    if not out:
        ps = ((T.get("sfx") or {}).get("per_s") or {})
        if isinstance(ps.get("ours_goal"), (int, float)):
            out["sfx_rate"] = {"goal": ps["ours_goal"], "cap": ps.get("cap"), "src": "판 targets.sfx.per_s"}
    return out or {"_none": {"goal": None, "cap": None, "src": f"targets 칸은 있는데 목표 밀도 없음({src} · counted.top · targets.sfx.per_s 다 없음) — count <판> --top"}}


def _want(goal: float | None, cap: float | None, n: float) -> tuple[int, int | None]:
    """목표 비율 × 분모 → 개수(반올림), 상한 비율 × 분모 → 개수(내림 — 상위 편 최대를 넘지 않는다, B14)."""
    if goal is None or n <= 0:
        return 0, None
    c = int(math.floor(cap * n + 1e-9)) if isinstance(cap, (int, float)) else None
    w = int(round(goal * n))
    return (min(w, c) if c is not None else w), c


def _is_deco(r: dict) -> bool:
    """우리 덩어리의 꾸밈 유무 — kal_analyze._decorated 와 같은 칸(등장 효과·강조·스티커)으로 센다(효과음은 match 가 덩어리에 안 붙여 뺀다)."""
    return r.get("enter") not in ("cut", "instant", "append", None) or bool(r.get("emph")) or bool(r.get("stickers"))


def density_step(out: list[dict], style: dict, tg: dict, log: list) -> dict:
    """targets 모드 꾸밈 채우기: 화자마다(나레·원음) 꾸밈 덩어리 수를 목표(p75 × 덩어리 수)까지 — 종류는 1차 그대로 '강조 낱말'(대본 key 가 있는
    덩어리만, 1차 ② 와 같은 조건), 자리 = 역할 순서(훅 → 공개 → 반전 → 본문 → 끝, 같은 역할 안에선 고르게). 조건 맞는 덩어리가 모자라면 그 수까지 + 로그.
    상한(max × 덩어리 수)을 1차 배치가 이미 넘었으면 빼지 않고 로그(1차 규칙은 그대로)."""
    rep = {}
    order = {"hook": 0, "reveal": 1, "twist": 2, "body": 3, "end": 4}
    for key, sp in (("fx_rate_narr", "narr"), ("fx_rate_orig", "orig")):
        t = tg.get(key)
        idx = [i for i, r in enumerate(out) if r["speaker"] == sp]
        if not t or not idx:
            continue
        want, cap = _want(t["goal"], t["cap"], len(idx))
        have = sum(_is_deco(out[i]) for i in idx)
        added = []
        if have < want:
            cand = [i for i in idx if out[i].get("key") and not _is_deco(out[i])]
            by_role = defaultdict(list)
            for i in cand:
                by_role[order.get(out[i]["role_key"], 3)].append(i)
            need = want - have
            for o in sorted(by_role):
                if need <= 0:
                    break
                for i in _spread(by_role[o], min(need, len(by_role[o]))):
                    out[i]["emph"] = [{"word": out[i]["key"], **({"color": out[i]["key_color"]} if out[i].get("key_color") else {})}]
                    out[i]["emph_by"] = "targets"
                    added.append(i)
                need = want - have - len(added)
            if need > 0:
                log.append(f"꾸밈({sp}) 목표 {want} 중 {have + len(added)}개만 — 대본 key 있는 덩어리 모자람")
        elif cap is not None and have > cap:
            log.append(f"꾸밈({sp}) {have}개 > 상한 {cap}(상위 편 최대) — 1차 배치 그대로 둠")
        got = have + len(added)
        rep[key] = {"goal": t["goal"], "cap": t["cap"], "want": want, "cap_n": cap, "n": len(idx), "ours": round(got / len(idx), 3), "src": t["src"]}
        log.append(f"꾸밈({sp}) targets: 목표 {t['goal']}×{len(idx)}={want} · 상한 {cap} · 1차 {have} → {got}"
                   + (f" (+강조 {[out[i]['line'] + '「' + out[i]['text'] + '」' for i in added]})" if added else ""))
    if tg.get("sticker_rate") and not [k for k in ((style["placement"].get("rules") or {}).get("stickers") or {}) if k != "comment_card"]:
        log.append(f"스티커 targets {tg['sticker_rate']['goal']} — 판 rules.stickers 에 그릴 종류가 없어 못 채움(종류는 1차 규칙 그대로, 판 주인 07)")
    return rep


# ── 편마다 배치(판단 주인) ──────────────────────────────────────────────
def _h(seed: str, what: str) -> int:
    return int(hashlib.md5(f"{seed}|{what}".encode()).hexdigest()[:8], 16)


def _chance(seed: str, what: str) -> float:
    return _h(seed, what) / 0xFFFFFFFF


def reference(style: dict, seed: str) -> dict | None:
    """씨앗 → 본보기 벤치 편(counted.videos 중 하나). 판 설정 placement.reference 로 고정할 수도 있다."""
    vs = (style["placement"].get("counted") or {}).get("videos") or []
    if not vs:
        return None
    fix = style["placement"].get("reference")
    if fix:
        return next((v for v in vs if v["id"] == fix), vs[0])
    return vs[_h(seed, "reference") % len(vs)]


def _alloc(n: int, dist: dict) -> list[str]:
    """비율 → n 개 이름(가장 큰 나머지) — 순서는 부드러운 가중 돌림(같은 것이 몰리지 않게)."""
    tot = sum(dist.values()) or 1
    want = {k: v / tot * n for k, v in dist.items()}
    cnt = {k: int(w) for k, w in want.items()}
    for k in sorted(want, key=lambda k: want[k] - cnt[k], reverse=True)[:n - sum(cnt.values())]:
        cnt[k] += 1
    cur = {k: 0.0 for k in cnt}
    seq = []
    for _ in range(n):
        for k in cur:
            cur[k] += cnt[k]
        k = max(cur, key=cur.get)
        seq.append(k); cur[k] -= n
    return seq


def _spread(idx: list[int], k: int) -> list[int]:
    if k <= 0 or not idx:
        return []
    if k >= len(idx):
        return list(idx)
    step = len(idx) / k
    return [idx[int(step * i + step / 2)] for i in range(k)]


def place(rows: list[dict], style: dict, seed: str, cuts: list[dict] | None = None, locate=None, targets=None) -> dict:
    """rows = 자막 덩어리 [{line, j, speaker:'narr'|'orig', text, key?, key_color?, object_src?, role?, t0, t1}] (시간 순).
    cuts = 화면 컷 [{t0, t1|dur}](render_bench.timeline cuts) — 전환은 컷 경계에만. 없으면 줄 경계로 어림(로그에 남긴다).
    locate(target, row, sticker) -> {x,y,w,h,conf,…} | None — 스티커·짤 자리 검출(hybrid/fx_target.locator). 없으면 자리는 target 으로 남는다.
    반환 {reference, rows:[…+first, lex, role_key, enter, variant, emph, stickers], sfx:[{t, kind, why, role?}],
          transitions:[{t, kind, ms, why}], flashes:[t](= transitions kind=flash 뷰), log:[왜], warn:[⚠], targets:{…}}.
    targets = None → 판에 `targets` 칸이 있으면(업그레이드 판) density_targets(판) 로 목표 밀도 모드, 없으면 옛 동작(1차 판 — 결과 그대로) ·
              dict → 그 목표({밀도: {goal, cap, src}}) · False → 끔. 목표 모드는 종류·조건·자리 규칙은 1차 그대로, 개수만 상위 편 p75 쪽으로(상한 max)."""
    P = style["placement"]; R = P.get("rules") or {}; C = P.get("counted") or {}
    ref = reference(style, seed)
    out = [dict(r) for r in rows]
    log = [f"본보기 벤치 편 = {ref['id'] if ref else '없음(합계 비율)'}"]
    warn = []
    tg = density_targets(style) if targets is None else (targets or None)
    if tg and "_none" in tg:
        warn.append(f"⚠ {tg['_none']['src']}")
        tg = None
    if tg:
        log.append("목표 밀도 모드(업그레이드 판 targets): " + ", ".join(f"{k} {v['goal']}(상한 {v['cap']})" for k, v in tg.items()) + f" · 출처 {next(iter(tg.values()))['src']}")
    for k, r in enumerate(out):
        r["first"] = k == 0 or r["speaker"] != out[k - 1]["speaker"] or r["line"] != out[k - 1]["line"]
        r["lex"] = lex_of(r["text"])
        r["stickers"] = list(r.get("stickers") or [])
        r["slot"] = slot_of(r["speaker"], r["first"])
    for r, rk in zip(out, row_roles(out)):
        r["role_key"] = rk
    fixed = R.get("enter") or {}
    # ① 등장: 칸마다 본보기 편 비율을 우리 덩어리에 나눠 준다(타이핑은 감탄 덩어리 먼저)
    for key in SLOTS:
        idx = [i for i, r in enumerate(out) if r["slot"] == key]
        if not idx:
            continue
        if key in fixed:
            for i in idx:
                out[i]["enter"] = fixed[key]
            continue
        src = ((ref or {}).get("slots", {}).get(key) or {}).get("enter") or (C.get("slots", {}).get(key) or {}).get("enter")
        if not src:     # 판 rules.enter 도 본보기·합계 비율도 없다 → 전부 컷(꾸밈 0)을 조용히 내지 않는다(⑮ 꼴)
            if not C.get("slots") and not (ref or {}).get("slots"):      # 벤치 등장 측정이 통째로 없다 = ×(판 rules.enter 를 적거나 count 를 돌려라)
                warn.append(f"⚠ 등장 {key} {len(idx)}덩어리 — 판 rules.enter 에 이 칸 없음·벤치 등장 집계(counted.slots) 없음 → 전부 컷(꾸밈 0)")
            else:           # 벤치에 그 칸(예: 원음 자막)이 아예 없었다 — 컷이 벤치 그대로일 수 있어 기록만
                log.append(f"등장 {key} {len(idx)}덩어리 — 벤치 집계에 그 칸 없음 → 컷")
            src = {"cut": 1}
        dist = {}
        for e, v in src.items():      # 이어 붙이기·기타는 우리 렌더에서 컷과 같다
            e = "cut" if e in ("other", "append") else e
            dist[e] = dist.get(e, 0) + v
        seq = _alloc(len(idx), dist)
        nty = seq.count("typing")
        rest = [e for e in seq if e != "typing"]
        ty_at = set(sorted(idx, key=lambda i: (0 if set(out[i]["lex"]) & {"excl"} else 1, i))[:nty]) if nty else set()
        it = iter(rest)
        for i in idx:
            out[i]["enter"] = "typing" if i in ty_at else next(it)
    # ② 강조 낱말: 칸마다 본보기 편 강조 비율 × 우리 덩어리 수 (대본 key 가 있는 덩어리 중 고르게) — 0 이면 칠하지 않는다
    for key in SLOTS:
        rs = ((ref or {}).get("slots", {}).get(key) or (C.get("slots", {}).get(key)) or {})
        rate = rs.get("emph", 0) / max(1, rs.get("n", 1)) if ref and key in ref.get("slots", {}) else (C.get("slots", {}).get(key) or {}).get("emph", 0.0)
        idx_all = [i for i, r in enumerate(out) if r["slot"] == key]
        idx = [i for i in idx_all if out[i].get("key")]
        for i in _spread(idx, round(rate * len(idx_all))):
            out[i]["emph"] = [{"word": out[i]["key"], **({"color": out[i]["key_color"]} if out[i].get("key_color") else {})}]
    # ③ 줄 변형(꿀템노트 빨강 펀치 등): 본보기 편에 그 변형이 있으면 조건 맞는 덩어리 하나
    for name, rule in (R.get("variants") or {}).items():
        have = sum(c for v, c in ((ref or {}).get("variants") or {}).items() if rule.get("match", name) in v)
        cand = [i for i, r in enumerate(out) if r["speaker"] == rule.get("speaker", r["speaker"]) and (not rule.get("lex") or set(rule["lex"]) & set(r["lex"]))]
        for i in _spread(cand, have):
            out[i]["variant_force"] = name
            log.append(f"변형 {name} → {out[i]['line']}「{out[i]['text']}」")
    # ③' 훅 줄 변형(잇템로그 빨강 훅): 편 첫 그 화자 줄의 덩어리 전부 = variant, 그 줄 마지막 덩어리 = pop_variant(팝+글리치)
    HK = R.get("hook")
    if HK:
        first = next((r["line"] for r in out if r["speaker"] == HK.get("speaker", "narr")), None)
        idx = [i for i, r in enumerate(out) if r["line"] == first]
        for i in idx:
            out[i].setdefault("variant_force", HK["variant"])
        if idx and HK.get("pop_variant"):
            out[idx[-1]]["variant_force"] = HK["pop_variant"]
        log.append(f"훅 {first} 덩어리 {len(idx)}개 → {HK['variant']}" + (f" (끝 {HK['pop_variant']})" if HK.get("pop_variant") else ""))
    # ④ 스티커: 본보기 편의 종류·개수(규칙에 있는 종류만 — 그릴 수 있는 것), 조건 맞는 덩어리
    for kind, rule in (R.get("stickers") or {}).items():
        if kind == "comment_card":
            continue        # 댓글 카드는 렌더러 틀 층(대본 comment 가 있을 때) — plan_rows 가 본보기 편 수로 정한다
        need = int(((ref or {}).get("stickers") or {}).get(kind, 0)) if ref else 0
        if not need:
            continue
        cand = [i for i, r in enumerate(out) if (not rule.get("lex") or set(rule["lex"]) & set(r["lex"])) and (not rule.get("speaker") or r["speaker"] == rule["speaker"])
                and (not rule.get("needs_key") or r.get("key")) and (kind != "object_pop" or r.get("object_src"))]
        for i in _spread(cand, need):
            st = {"kind": kind, "word": out[i].get("key") or ""}
            if kind == "object_pop":
                st.update({"src": out[i]["object_src"], "hold": "beat"})
            st = _site(st, rule, out[i], locate, log)
            if st is None:
                continue
            out[i]["stickers"].append(st)
            log.append(f"스티커 {kind} → {out[i]['line']}「{out[i]['text']}」")
        if len(cand) < need:
            log.append(f"스티커 {kind} 본보기 {need}개 중 {len(cand)}개만(조건 맞는 덩어리 모자람)")
    # 타이핑 덩어리에 따라붙는 스티커(키치잇 원음 타이핑 + ♥): 본보기 편에 그 스티커가 있을 때만
    ty = R.get("typing_sticker")
    if ty and ((ref or {}).get("stickers") or {}).get(ty["kind"]):
        for r in out:
            if r["enter"] == "typing" and r["speaker"] == ty.get("speaker", r["speaker"]):
                r["stickers"].append({"kind": ty["kind"], "follow": True})
    tg_rep = density_step(out, style, tg, log) if tg else {}
    # ⑥ 전환(표준 §3-3 A1): 본보기 편 줄판독 transition 비율 → 컷 경계(짧은 컷 제외, 화자 바뀜·공개 앞 먼저). 옛 흰 번쩍(rules.flash)도 여기서.
    transitions = transitions_step(out, style, seed, ref, cuts, log)
    flashes = [x["t"] for x in transitions if x["kind"] == "flash"]       # 렌더러가 읽는 뷰 — 정하는 곳은 transitions_step 하나
    # ⑤ 효과음(A2): 본보기 편 줄판독 sfx·role 이 있으면 역할×종류 비율, 없으면 옛 길(신호표 고립 후보 자리)
    sfx = sfx_step(out, style, ref, transitions, cuts, log, tg=tg, warn=warn)
    if tg and "sfx_rate" in tg:
        dur = max((float(r.get("t1") or 0) for r in out), default=0.0)
        tg_rep["sfx_rate"] = {**{k: tg["sfx_rate"][k] for k in ("goal", "cap", "src")}, "dur": round(dur, 3), "n": len(sfx),
                              "ours": round(len(sfx) / dur, 3) if dur else None}
    # ⑦ 짤(meme): rules.meme{rate, cond{role,lex}, tone, len_s, pack, target} — rate 0(벤치에 짤 없음)이면 0개(없는 것도 스타일)
    meme_step(out, style, seed, locate, log)
    effects_step(out, style, seed, log)
    for r in out:
        r["variant"] = r.pop("variant_force", None) or variant_of(r, style)
    tally = Counter(r["enter"] for r in out)
    log.append(f"등장 {dict(tally)} · 강조 {sum(1 for r in out if r.get('emph'))}/{len(out)}")
    log += warn
    res = {"reference": ref["id"] if ref else None, "rows": out, "sfx": sfx, "transitions": transitions, "flashes": flashes,
           "cut_bounds": len(cut_bounds(out, cuts, [])), "log": log}
    if warn:
        res["warn"] = warn
    if tg_rep:
        res["targets"] = tg_rep
    return res


# ── 자리(표준 §3-3 A3): 스티커·짤·pointer 는 검출로 자리를 받는다 ─────────────────
def _site(st: dict, rule: dict, row: dict, locate, log: list) -> dict | None:
    """rule.target = face|object|caption_side|{fixed:{x,y}, why} → 스티커 자리. 반환 st(자리 붙음/받을 것 표시) | None(못 둠 → 안 붙인다).
    target 없는 옛 규칙(rule.x·y 고정 %)은 그대로 둔다(옛 판 동작 유지 — check_place 가 'legacy_fixed' 로 센다)."""
    tg = rule.get("target")
    if tg is None:
        st.update({k: rule[k] for k in ("x", "y") if isinstance(rule.get(k), (int, float))})   # 판 설정 스티커 자리(화면 %) — 없으면 그림 쪽 기본 자리
        if any(k in st for k in ("x", "y")):
            st["site"] = "legacy_fixed"
        return st
    if isinstance(tg, dict) and "fixed" in tg:
        why = tg.get("why") or rule.get("why")
        fx = tg["fixed"] or {}
        if not why or not all(isinstance(fx.get(k), (int, float)) for k in ("x", "y")):
            log.append(f"스티커 {st['kind']} 고정 좌표 거절(벤치 실측 근거 why 없음·좌표 빠짐) → {row['line']} 안 붙임")
            return None
        st.update({"x": fx["x"], "y": fx["y"], "site": "fixed", "site_why": why})
        return st
    st["target"] = {"kind": tg, "avoid": list(rule.get("avoid") or ["face"])}
    if locate is None:
        st["site"] = "pending"          # 검출 전 — 렌더 전에 fx_target.locator 로 받아야 한다(check_place 미해결)
        return st
    got = locate(st["target"], row, st)
    if not got:
        log.append(f"스티커 {st['kind']} 자리 검출 실패({tg}) → {row['line']}「{row['text']}」 안 붙임(억지로 안 둔다)")
        return None
    st.update({k: got[k] for k in ("x", "y", "w", "h", "conf", "face_clear", "how") if k in got})
    st["site"] = "detected"
    return st


# ── 전환(A1) ─────────────────────────────────────────────────────────────
def cut_bounds(out: list[dict], cuts: list[dict] | None, log: list) -> list[dict]:
    """컷 경계 [{t, prev, next, switch, reveal}] — prev/next = 앞·뒤 컷 길이. cuts 가 없으면 줄 경계로 어림(로그)."""
    if cuts:
        cs = sorted(cuts, key=lambda c: float(c["t0"]))

        def dur(i):
            c = cs[i]
            if c.get("dur") is not None:
                return float(c["dur"])
            if c.get("t1") is not None:
                return float(c["t1"]) - float(c["t0"])
            return float(cs[i + 1]["t0"]) - float(c["t0"]) if i + 1 < len(cs) else 9.0
        b = [{"t": round(float(cs[i]["t0"]), 3), "prev": dur(i - 1), "next": dur(i)} for i in range(1, len(cs))]
    else:
        st = [r["t0"] for k, r in enumerate(out) if k and r["line"] != out[k - 1]["line"]]
        st = ([out[0]["t0"]] + st) if out else []
        end = out[-1]["t1"] if out else 0
        b = [{"t": round(st[i], 3), "prev": st[i] - st[i - 1], "next": (st[i + 1] if i + 1 < len(st) else end) - st[i]} for i in range(1, len(st))]
        if b:
            log.append("전환: 컷 목록 없음 → 줄 경계를 컷 경계로 어림(렌더러는 cuts= 를 넘겨라)")
    for x in b:
        nxt = next((k for k, r in enumerate(out) if r["t0"] >= x["t"] - 1e-3), None)
        prv = max((k for k, r in enumerate(out) if r["t0"] < x["t"] - 1e-3), default=None)
        x["switch"] = nxt is not None and prv is not None and out[nxt]["speaker"] != out[prv]["speaker"]
        x["reveal"] = nxt is not None and out[nxt].get("role_key") == "reveal"
    return b


def transitions_step(out: list[dict], style: dict, seed: str, ref: dict | None, cuts, log: list) -> list[dict]:
    """(판단 주인: 전환 종류·자리) 판 칸 placement.rules.transition{kinds, cond{min_cut_s, prefer}, max_per_video} · cuts.transition.ms(02 와 같은 이름).
    비율 = 본보기 편 줄판독 transition(잰 줄 기준 k/n) → 없으면 counted.transition(벤치 합계) → 없으면 옛 rules.flash(편 비율 share, 마지막 화자 바뀜)."""
    R = style["placement"].get("rules") or {}
    C = style["placement"].get("counted") or {}
    TR = R.get("transition") or {}
    cond = TR.get("cond") or {}
    min_cut = float(cond.get("min_cut_s", 1.2))
    prefer = cond.get("prefer", ["switch", "reveal"])
    CT = (style.get("cuts") or {}).get("transition") or {}          # 02 렌더러와 같은 칸(cuts.transition{kinds 비율, ms}) — 그리기는 render_bench, 자리는 여기
    F = style.get("frame") or {}

    def ms(kind):
        v = CT.get("ms")
        v = v.get(kind) if isinstance(v, dict) else v
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
        return int(round(1000 * float(F.get("flash_sec", 0.1)))) if kind == "flash" else None    # None = 렌더러 종류별 기본 길이
    allowed = [k for k in (TR.get("kinds") or TRANS_DRAWABLE) if k in TRANS_DRAWABLE]
    share, src = {}, None
    pan = {k: float(v) for k, v in (CT.get("kinds") or {}).items() if k in TRANS_DRAWABLE and float(v) > 0} if isinstance(CT.get("kinds"), dict) else {}
    if ref and ref.get("n_trans"):
        share = {k: c / ref["n_trans"] for k, c in (ref.get("transitions") or {}).items()}
        src = f"본보기 {ref['id']} 줄판독 {ref['n_trans']}줄"
    elif C.get("transition"):
        share = dict(C["transition"])
        src = "벤치 합계"
    if not {k: v for k, v in share.items() if k in TRANS_DRAWABLE and v > 0} and pan:
        share = pan
        src = "판 cuts.transition.kinds"
    share = {k: v for k, v in share.items() if k in allowed and v > 0}
    if src and share:
        bounds = cut_bounds(out, cuts, log)
        nb = len(bounds)
        want = {k: v * nb for k, v in share.items()}
        total = int(round(sum(want.values())))
        if TR.get("max_per_video") is not None:
            total = min(total, int(TR["max_per_video"]))
        elig = [b for b in bounds if b["prev"] >= min_cut and b["next"] >= min_cut]
        pref = [b for b in elig if any(b.get(p) for p in prefer)]
        rest = [b for b in elig if b not in pref]
        pick = pref[:total] if len(pref) >= total else pref + _spread(rest, total - len(pref))
        pick.sort(key=lambda b: b["t"])
        kinds = _alloc(len(pick), want) if pick else []
        res = [{"t": b["t"], "kind": k, "ms": ms(k), "why": "화자 바뀜" if b["switch"] else "공개 앞" if b["reveal"] else "컷 경계"}
               for b, k in zip(pick, kinds)]
        log.append(f"전환 {[(x['t'], x['kind']) for x in res]} ({src} 비율 {({k: round(v, 2) for k, v in share.items()})}, "
                   f"컷 경계 {nb}·붙일 수 있는 {len(elig)}(≥{min_cut}초))" + (f" — 모자람 {total - len(pick)}" if len(pick) < total else ""))
        return res
    Fl = R.get("flash")
    if Fl and _chance(seed, "flash") < float(Fl.get("share", 0)):
        cand = [r["t0"] for k, r in enumerate(out) if k and r["speaker"] != out[k - 1]["speaker"]]
        res = [{"t": cand[-1], "kind": "flash", "ms": ms("flash"), "why": "마지막 화자 바뀜(rules.flash)"}] if cand else []
        log.append(f"번쩍 {[x['t'] for x in res]}")
        return res
    return []


# ── 효과음(A2) ───────────────────────────────────────────────────────────
def _sfx_allowed(style: dict) -> list[str]:
    S = (style["placement"].get("rules") or {}).get("sfx") or {}
    if isinstance(S.get("kinds"), dict):
        return list(S["kinds"])
    files = [k for k in (style.get("sfx_files") or {}) if k != "gain_db"]
    return files or [S.get("kind", "ding")]


def sfx_step(out: list[dict], style: dict, ref: dict | None, transitions: list[dict], cuts, log: list, tg: dict | None = None,
             warn: list | None = None) -> list[dict]:
    """(판단 주인: 효과음 수·자리·종류) 판 칸 placement.rules.sfx{max, kinds{이름:비율}, offset, kind(옛 한 종류)}.
    새 길 = 본보기 편 줄판독 sfx_lines(종류·역할·덩어리 시작 대비 시각) — 역할(훅·공개·반전·끝·본문) 비율 그대로, 역할 안에선 강조 덩어리 먼저,
    종류 = rules.sfx.kinds 비율(없으면 본보기 편 종류 중 렌더러에 파일 있는 것) — whoosh 는 전환 자리로, 시각 편차 = 벤치 중앙(±0.3초 안).
    옛 길(sfx_lines 없음) = 신호표 고립 후보 자리(본보기 편 수, max 까지) — 옛 판 그대로 동작.
    rules.sfx.roles = 붙어도 되는 역할 목록(지시서 03→15, 예 잇템로그 ⑦ⓒ 훅만) — 있으면 그 밖 역할 몫은 허용 역할로 옮긴다.
    tg(목표 밀도 모드, 업그레이드 판) = 발 수 = 목표 sfx_rate(상위 편 p75) × 길이(반올림, 상한 max × 길이 내림) — 역할 비율은 본보기 편 줄판독,
    본보기 편에 sfx 가 없으면 상위 편 묶음(counted.top.sfx 또는 상위 편 videos 의 sfx_lines), 그것도 없으면 허용 역할(없으면 훅)."""
    S = (style["placement"].get("rules") or {}).get("sfx") or {}
    if not S:
        msg = "⚠ 효과음 0발 — 판 규칙 placement.rules.sfx 없음(벤치에 효과음이 정말 없으면 rules.sfx = {max:0, why} 로 적는다 · 조용한 0발 금지 ⑮)"
        (warn if warn is not None else log).append(msg)       # warn 은 place 가 로그 끝에 붙인다(두 번 안 적게)
        return []
    allowed = _sfx_allowed(style)
    default = S.get("kind", allowed[0] if allowed else "ding")
    lines = list((ref or {}).get("sfx_lines") or [])
    roles_ok = [role_key(x) for x in S.get("roles") or []]
    n_tg = None
    if tg and tg.get("sfx_rate"):
        dur = max((float(r.get("t1") or 0) for r in out), default=0.0)
        n_tg, cap_n = _want(tg["sfx_rate"]["goal"], tg["sfx_rate"]["cap"], dur)
        if not lines:
            C = style["placement"].get("counted") or {}
            top = C.get("top") or {}
            ids = set(top.get("ids") or top_ids_saved(style))
            lines = list(top.get("sfx") or [e for v in C.get("videos") or [] if v["id"] in ids for e in v.get("sfx_lines") or []])
            src = "상위 편 묶음" if lines else None
            if not lines:
                lines = [{"kind": default, "role": (roles_ok or ["hook"])[0], "off": None}]
                src = f"역할 근거 없음 → {(roles_ok or ['hook'])[0]}"
            log.append(f"효과음 targets: 본보기 편 sfx 없음 → 역할·편차 = {src}")
        log.append(f"효과음 targets: 목표 {tg['sfx_rate']['goal']}발/초 × {dur:.2f}초 = {n_tg}발 · 상한 {cap_n}(상위 편 최대 {tg['sfx_rate']['cap']})")
    sfx = []
    if lines:
        n = n_tg if n_tg is not None else min(len(lines), int(S.get("max", len(lines))))
        offs = sorted(e["off"] for e in lines if isinstance(e.get("off"), (int, float)))
        off = float(S["offset"]) if isinstance(S.get("offset"), (int, float)) else (max(-0.3, min(0.3, offs[len(offs) // 2])) if offs else 0.0)
        rc = Counter(e["role"] for e in lines)
        if roles_ok:
            rc = Counter({k: v for k, v in rc.items() if k in roles_ok}) or Counter({roles_ok[0]: 1})
        per_role = Counter(_alloc(n, rc)) if n else Counter()
        taken = []

        def free(t):
            return all(abs(t - s) > 0.4 for s in taken)
        short = 0
        for role in ROLES:
            k = per_role.get(role, 0)
            if not k:
                continue
            idx = [i for i, r in enumerate(out) if r["role_key"] == role]
            idx.sort(key=lambda i: (0 if out[i].get("emph") else 1 if out[i]["first"] else 2, i))      # 강조 낱말 덩어리 → 줄 첫 덩어리 → 나머지
            got = 0
            for i in idx:
                if got >= k:
                    break
                t = round(max(0.0, out[i]["t0"] + off), 3)
                if free(t):
                    sfx.append({"t": t, "role": role, "why": role + (" 강조" if out[i].get("emph") else "")})
                    taken.append(t)
                    got += 1
            short += k - got
        if short:      # 그 역할 덩어리가 모자라면 전환·컷 경계 자리로(벤치에서 소리가 붙는 둘째 자리)
            spots = [(x["t"], "전환") for x in transitions] + [(b["t"], "컷 경계") for b in cut_bounds(out, cuts, [])]
            for t, why in spots:
                if not short:
                    break
                if free(t):
                    sfx.append({"t": round(t, 3), "role": None, "why": why})
                    taken.append(t)
                    short -= 1
            if short:
                log.append(f"효과음 {short}발 자리 모자람(0.4초 간격)")
        sfx.sort(key=lambda e: e["t"])
        src_kinds = dict(S["kinds"]) if isinstance(S.get("kinds"), dict) else dict(Counter(e["kind"] for e in lines if e["kind"] in allowed))
        if not src_kinds:
            src_kinds = {default: 1}
        for e, k in zip(sfx, _alloc(len(sfx), src_kinds) if sfx else []):
            e["kind"] = k
        # whoosh 는 전환 자리로: 전환 자리에 whoosh 아닌 것, 전환 아닌 자리에 whoosh 가 있으면 맞바꾼다(개수 비율은 그대로)
        at_tr = [e for e in sfx if any(abs(e["t"] - x["t"]) <= 0.05 for x in transitions)]
        for e in at_tr:
            if e["kind"] != "whoosh":
                o = next((x for x in sfx if x["kind"] == "whoosh" and x not in at_tr), None)
                if o:
                    e["kind"], o["kind"] = o["kind"], e["kind"]
        log.append(f"효과음 {len(sfx)}발(본보기 줄판독 {len(lines)}발 · 역할 {dict(per_role)} · 편차 {off:+.2f}초) {[(s['t'], s['kind'], s['role']) for s in sfx]}")
        return sfx
    want = (ref or {}).get("sfx") or []
    n = min(len(want), int(S.get("max", 3)))
    if n:
        spots = []
        for w in [w for w, _ in Counter(want).most_common() if w != "none"] + ["cap"]:
            if w == "switch":
                spots += [(r["t0"], "switch") for k, r in enumerate(out) if k and r["speaker"] != out[k - 1]["speaker"]]
            elif w == "sticker":
                spots += [(r["t0"], "sticker") for r in out if r["stickers"]]
            else:
                spots += [(r["t0"], "cap") for r in out[1:]]
        seen = set()
        for t, why in spots:      # 벤치 고립 후보는 앞쪽(첫 원음 훅·첫 전환)에 몰린다 → 앞에서부터
            if len(sfx) >= n:
                break
            if all(abs(t - s) > 0.4 for s in seen):
                sfx.append({"t": round(t, 3), "kind": default, "why": why})
                seen.add(t)
        sfx.sort(key=lambda e: e["t"])
        if isinstance(S.get("kinds"), dict) and sfx:
            for e, k in zip(sfx, _alloc(len(sfx), S["kinds"])):
                e["kind"] = k
    log.append(f"효과음 {len(sfx)}발(본보기 {len(want)}) {[(s['t'], s['why']) for s in sfx]}")
    return sfx


# ── 짤(meme) ─────────────────────────────────────────────────────────────
def meme_files(tone: str | None = None, pack: str | None = None) -> list[str]:
    """짤 후보 파일(로고·남의 글자 짤 meme_exclude 제외 — 주인 material_auto.MEME_*). pack = 폴더, tone = 감정 낱말(팩 목록 emotion)."""
    from tools.calcopy.engine import material_auto as MA
    ex = set((json.loads(MA.MEME_EXCLUDE.read_text(encoding="utf-8")).get("exclude") or {}) if MA.MEME_EXCLUDE.exists() else ())
    if pack:
        d = Path(pack)
        return sorted(str(p) for p in d.glob("*.mp4") if p.stem not in ex) if d.exists() else []
    if not MA.MEME_INDEX.exists():
        return []
    idx = json.loads(MA.MEME_INDEX.read_text(encoding="utf-8"))
    return [str(MA.MEME_DIR / f"{m['id']}.mp4") for m in idx
            if m["id"] not in ex and (not tone or tone in str(m.get("emotion", ""))) and (MA.MEME_DIR / f"{m['id']}.mp4").exists()]


def meme_step(out: list[dict], style: dict, seed: str, locate, log: list, files=None):
    """(판단 주인: 짤 수·자리·파일) 판 칸 placement.rules.meme{rate(줄당 짤 k/n), cond{role[], lex[]}, tone, len_s, pack, target(기본 caption_side)}."""
    M = (style["placement"].get("rules") or {}).get("meme")
    if not M:
        return
    lines = []
    for r in out:
        if r["line"] not in lines:
            lines.append(r["line"])
    n = int(round(float(M.get("rate", 0)) * len(lines)))
    if n <= 0:
        log.append(f"짤 0개(rate {M.get('rate', 0)} — 벤치에 짤 없음도 스타일)")
        return
    cond = M.get("cond") or {}
    cand = [i for i, r in enumerate(out) if r["first"] and (not cond.get("role") or r["role_key"] in cond["role"])
            and (not cond.get("lex") or set(cond["lex"]) & set(r["lex"]))]
    fs = files if files is not None else meme_files(M.get("tone"), M.get("pack"))
    if not fs:
        log.append(f"짤 {n}개 중 0개 — 짤 팩 없음(tone {M.get('tone')}·pack {M.get('pack')})")
        return
    used = set()
    for k, i in enumerate(_spread(cand, n)):
        j = _h(seed, f"meme:{k}") % len(fs)
        while fs[j] in used and len(used) < len(fs):
            j = (j + 1) % len(fs)
        used.add(fs[j])
        st = {"kind": "meme", "src": fs[j], "len_s": float(M.get("len_s", 1.0))}
        st = _site(st, {"target": M.get("target", "caption_side"), "avoid": M.get("avoid"), "why": M.get("why")}, out[i], locate, log)
        if st is None:
            continue
        out[i]["stickers"].append(st)
        log.append(f"짤 {Path(fs[j]).name} → {out[i]['line']}「{out[i]['text']}」")
    if len(cand) < n:
        log.append(f"짤 {n}개 중 조건 맞는 덩어리 {len(cand)}개뿐")


# ── 효과별 붙는 조건(주인 = 자막팩 계약 caption-motions.js CAPTION_EFFECT_RULES, 관제 235) ─────────────
# 조건 글(채널·편당 횟수·글자 수)은 계약 파일 한 곳에서 읽는다 — 여기는 '그 조건이 우리 덩어리 중 어디냐'를 고르는 법(박자 자리)만.
# 효과 이름 → (자막팩에서 어떻게 거나: 줄 변형 이름 | 스티커 kind, 박자 자리 고르기)
EFFECT_HOW = {
    "rgbGlitch": ("variant", "glitch"), "wipeRTL": ("variant", "wipe"), "rainbowCycle": ("variant", "rainbow"),
    "hearts": ("sticker", "hearts"), "comic_burst": ("sticker", "comic_burst"), "aside_line": ("sticker", "aside_line"),
    "append_text": ("sticker", "append_text"), "sound_word": ("sticker", "sound_word"), "small_text": ("sticker", "small_text"),
}
TEXT_NEEDS = {"aside_line": "aside", "append_text": "append", "sound_word": "sound", "small_text": "small"}   # 대본 caps 에 그 글이 있을 때만


def effect_rules() -> dict:
    s = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
    return json.loads(s.split("/*RULES*/")[1]) if "/*RULES*/" in s else {}


def _per_video(cond: str) -> tuple[int, int]:
    m = re.search(r"편당\s*(\d+)\s*(?:~\s*(\d+))?\s*회", cond or "")
    return (int(m.group(1)), int(m.group(2) or m.group(1))) if m else (0, 1)


def _effect_where(name: str, out: list[dict], cond: str) -> list[int]:
    nc = lambda r: len(re.sub(r"\s", "", r["text"]))
    m = re.search(r"(\d+)\s*~\s*(\d+)\s*자", cond or ""); lo, hi = (int(m.group(1)), int(m.group(2))) if m else (0, 99)
    m = re.search(r"(\d+)\s*자 이상", cond or ""); lo = int(m.group(1)) if m else lo
    hook_end = next((r["t0"] for k, r in enumerate(out) if k and r["speaker"] != out[0]["speaker"]), 8.0)
    if name == "rgbGlitch":       # 훅(앞 원음 구간) 원음 줄, 제품 이름(key)이 처음 나오는 줄
        return [i for i, r in enumerate(out) if r["speaker"] == "orig" and r["t0"] < max(hook_end, 3.5) and r.get("key")][:1]
    if name == "wipeRTL":         # 화면 바뀐 직후 첫 줄, 8자 이상 원음, 둘로 나눈 둘째 조각 제외
        return [i for i, r in enumerate(out) if r["speaker"] == "orig" and r["first"] and nc(r) >= lo]
    if name == "rainbowCycle":    # 편 첫 나레 줄, 8~10자
        i = next((i for i, r in enumerate(out) if r["speaker"] == "narr"), None)
        return [i] if i is not None and lo <= nc(out[i]) <= hi + 2 else []
    if name == "hearts":          # 편 첫 장면 감탄 한마디
        return [0] if out and set(out[0]["lex"]) & {"excl"} else []
    if name == "comic_burst":     # 2초 넘게 머무는 나레 줄
        return [i for i, r in enumerate(out) if r["speaker"] == "narr" and r["t1"] - r["t0"] > 2.0]
    if name == "aside_line":      # 1.5초+ 머무는 원음 줄
        return [i for i, r in enumerate(out) if r["speaker"] == "orig" and r["t1"] - r["t0"] >= 1.5]
    return [i for i, r in enumerate(out)]


def effects_step(out: list[dict], style: dict, seed: str, log: list):
    """CAPTION_EFFECT_RULES 중 이 판 벤치 채널 효과만: 편당 횟수(씨앗으로 범위 안에서 고름) → 박자 자리 → 줄 변형·스티커."""
    ko = style["bench"].get("ko")
    ref = reference(style, seed)
    for name, R in effect_rules().items():
        if name.startswith("_") or name not in EFFECT_HOW or not ko or ko not in R.get("채널", ""):
            continue
        # 영상마다 다르게: 그 효과가 '본 곳'(벤치 편 id 앞부분)에 본보기 편이 있을 때만 — 없는 편을 본보기로 삼았으면 안 붙인다
        seen_ids = re.findall(r"[A-Za-z0-9_-]{3,}", R.get("본 곳", ""))
        if not ref or not any(ref["id"].startswith(x) for x in seen_ids):
            continue
        lo, hi = _per_video(R.get("조건", ""))
        n = lo + _h(seed, f"effect:{name}") % (hi - lo + 1)
        if not n:
            log.append(f"효과 {name} 0회(편당 {lo}~{hi})"); continue
        need = TEXT_NEEDS.get(name)
        cand = [i for i in _effect_where(name, out, R.get("조건", "")) if not need or out[i].get(need)]
        how, key = EFFECT_HOW[name]
        for i in _spread(cand, n):
            if how == "variant":
                if not out[i].get("variant_force"):
                    out[i]["variant_force"] = key
            else:
                st = {"kind": key}
                if need:
                    st["text"] = out[i][need]
                if name == "comic_burst":
                    st["variant"] = "a"
                if name == "hearts":
                    st.update({"x": 50, "y": 41, "hold": 1.0})
                out[i]["stickers"].append(st)
            log.append(f"효과 {name} → {out[i]['line']}「{out[i]['text']}」(계약 조건: {R.get('조건', '')[:40]})")


def variant_of(r: dict, style: dict) -> str:
    """정한 등장 → 자막팩 줄 변형 이름. 팩 기본(caption.pack_default: 칸마다 팩이 원래 내는 등장)과 같으면 변형 없음(''),
    다르면 caption.variant_for[등장] — 팩에 그 변형이 있어야 한다(caption-motions.js PACKS)."""
    cap = style["caption"]
    if r["enter"] == "typing" and cap.get("typing_variant") and r["speaker"] == "orig":
        return cap["typing_variant"]
    if r["enter"] == (cap.get("pack_default") or {}).get(r["slot"], r["enter"]):
        return ""
    return (cap.get("variant_for") or {}).get(r["enter"], "")


def check_place(placed: dict, style: dict) -> dict:
    """배치 결과 ↔ 본보기 벤치 편 대조(검사): 칸마다 등장 비율 차이(최대 절댓값)·강조 비율·스티커·효과음 수."""
    ref = next((v for v in (style["placement"].get("counted") or {}).get("videos") or [] if v["id"] == placed.get("reference")), None)
    rows = placed["rows"]
    rep, worst = {}, 0.0
    for key in SLOTS:
        mine = [r for r in rows if r["slot"] == key]
        rs = (ref or {}).get("slots", {}).get(key)
        if not mine or not rs:
            continue
        ours = Counter(r["enter"] for r in mine)
        bd = {("cut" if e in ("other", "append") else e): 0.0 for e in rs["enter"]}
        for e, c in rs["enter"].items():
            bd["cut" if e in ("other", "append") else e] += c / rs["n"]
        diff = max(abs(ours.get(e, 0) / len(mine) - bd.get(e, 0)) for e in set(bd) | set(ours))
        worst = max(worst, diff)
        rep[key] = {"bench": {e: round(v, 2) for e, v in bd.items()}, "ours": {e: round(c / len(mine), 2) for e, c in ours.items()},
                    "bench_emph": round(rs["emph"] / rs["n"], 2), "ours_emph": round(sum(1 for r in mine if r.get("emph")) / len(mine), 2), "n": len(mine)}
    rep["stickers"] = {"bench": (ref or {}).get("stickers"), "ours": dict(Counter(s["kind"] for r in rows for s in r["stickers"]))}
    rep["sfx"] = {"bench": len((ref or {}).get("sfx") or []), "ours": len(placed["sfx"])}
    # 덩어리 수가 적으면 비율이 굵게 갈린다(우리 3덩어리 칸에서 1개 = 33%) → 칸 크기에 맞춘 허용 오차
    tol = {k: 0.5 / max(1, v["n"]) + 0.15 for k, v in rep.items() if isinstance(v, dict) and "n" in v}
    ok = all(max(abs(v["ours"].get(e, 0) - v["bench"].get(e, 0)) for e in set(v["bench"]) | set(v["ours"])) <= tol[k]
             for k, v in rep.items() if k in tol)
    bad = []
    # 전환(A1): 본보기 편 줄판독에 전환 칸이 있으면 종류마다 (벤치 비율 × 우리 컷 경계 수) ±1
    tr = placed.get("transitions") or []
    ours_tr = Counter(x["kind"] for x in tr)
    if ref and ref.get("n_trans"):
        nb = placed.get("cut_bounds") or 0
        exp = {k: round(c / ref["n_trans"] * nb, 2) for k, c in (ref.get("transitions") or {}).items() if k in TRANS_DRAWABLE}
        rep["transitions"] = {"bench_expect": exp, "ours": dict(ours_tr), "cut_bounds": nb}
        bad += [f"전환 {k} 우리 {ours_tr.get(k, 0)} ≠ 벤치 기대 {v}(±1)" for k, v in exp.items() if abs(ours_tr.get(k, 0) - v) > 1]
    else:
        rep["transitions"] = {"ours": dict(ours_tr)}
    # 효과음 종류·역할(A2): 본보기 편 줄판독 sfx 가 있으면 역할 수 ±1 · 종류 수 ±1(판 kinds 가 있으면 그 비율)
    lines = (ref or {}).get("sfx_lines") or []
    sx = placed.get("sfx") or []
    rep["sfx"]["kinds"] = dict(Counter(e.get("kind") for e in sx))
    if lines and sx:
        n = len(sx)
        rr = Counter(e["role"] for e in lines)
        exp_r = {k: round(v / len(lines) * n, 2) for k, v in rr.items()}
        ours_r = Counter(e.get("role") for e in sx if e.get("role"))
        rep["sfx"]["roles"] = {"bench_expect": exp_r, "ours": dict(ours_r)}
        bad += [f"효과음 역할 {k} 우리 {ours_r.get(k, 0)} ≠ 기대 {v}(±1)" for k, v in exp_r.items() if abs(ours_r.get(k, 0) - v) > 1]
        too_close = [(a["t"], b["t"]) for a, b in zip(sx, sx[1:]) if b["t"] - a["t"] < 0.3]
        if too_close:
            bad.append(f"효과음 0.3초 안 겹침 {too_close}")
    # 자리(A3): 받을 것(pending)·검출 확신 < 0.6·얼굴 겹침 = ×
    sites = Counter()
    for r in rows:
        for s in r["stickers"]:
            site = s.get("site")
            if not site:
                continue
            sites[site] += 1
            if site == "pending":
                bad.append(f"{s['kind']} 자리 미해결({(s.get('target') or {}).get('kind')}) {r['line']}")
            elif site == "detected" and (float(s.get("conf", 0)) < 0.6 or s.get("face_clear") is False):
                bad.append(f"{s['kind']} 자리 검출 확신 {s.get('conf')}·얼굴 안 겹침 {s.get('face_clear')} {r['line']}")
    rep["sites"] = dict(sites)
    rep["meme"] = {"ours": sum(1 for r in rows for s in r["stickers"] if s["kind"] == "meme")}
    # 조용한 0(⑮): 판 규칙이 없어 0발·전부 컷이 된 것 = ×
    bad += list(placed.get("warn") or [])
    # 목표 밀도(업그레이드 판 targets, 표준 §12-4): 우리 = 목표(상위 편 p75) ±20%p 안 · 상한(상위 편 max) 이하
    T = placed.get("targets") or {}
    if T:
        rep["targets"] = T
        for k, v in T.items():
            o, g, c = v.get("ours"), v.get("goal"), v.get("cap")
            if o is None or g is None:
                continue
            if abs(o - g) > 0.20 + 1e-9:
                bad.append(f"목표 밀도 {k} 우리 {o} — 목표 {g} ±20%p 밖")
            if isinstance(c, (int, float)) and o > c + 1e-9:
                bad.append(f"목표 밀도 {k} 우리 {o} > 상한 {c}(상위 편 최대)")
    return {"ok": ok and not bad, "reference": placed.get("reference"), "worst_slot_diff": round(worst, 3), "slots": rep, "bad": bad}


def plan(doc: Path, work: Path, version: str, locate=None) -> dict:
    """배치만(렌더 없이): 계획 시간표(doc/plan/계획_시간표.json 의 timeline — 없으면 render_bench.timeline 어림) → place(cuts=컷) →
    <work>/plan/자막표.json(render_bench 자막표와 같은 꼴 + transitions). 대본 줄 role 을 덩어리에 붙인다(효과음 역할·공개 전환)."""
    from tools.calcopy.hybrid import render_bench as RB, styles as ST
    st = ST.load(version)
    doc, work = Path(doc), Path(work)
    S = json.loads((doc / "대본.json").read_text(encoding="utf-8"))
    saved = doc / "plan" / "계획_시간표.json"
    if saved.exists():
        T = json.loads(saved.read_text(encoding="utf-8"))["timeline"]
        src = str(saved.relative_to(ROOT) if saved.is_relative_to(ROOT) else saved)
    else:
        M = json.loads((doc / "재료.json").read_text(encoding="utf-8"))
        S.setdefault("cps_target", st.get("cps_target", 7.0))
        T = RB.timeline(S, M, st, None, None)
        src = "render_bench.timeline(글자÷cps 어림)"
    role = {l["id"]: l.get("role") for l in S.get("lines") or [] if l.get("id")}
    rows = [{**{k: v for k, v in r.items() if k != "show"}, **({"role": role[r["line"]]} if role.get(r["line"]) else {})} for r in T["rows"]]
    placed = place(rows, st, S.get("slug") or doc.name, cuts=T.get("cuts"), locate=locate)
    for r, t in zip(placed["rows"], T["rows"]):
        r["show"] = t.get("show") or [t["t0"], t["t1"]]
    chk = check_place(placed, st)
    tab = {"_note": f"배치만(placement.py plan, 판 설정 {version}) · 시간표 = {src} · 렌더 안 함", "pack": st["caption"]["pack"],
           "rows": RB.caption_rows(placed, st), "sfx": placed["sfx"], "transitions": placed["transitions"], "flashes": placed["flashes"],
           "log": placed["log"], "check": chk}
    (work / "plan").mkdir(parents=True, exist_ok=True)
    (work / "plan" / "자막표.json").write_text(json.dumps(tab, ensure_ascii=False, indent=1), encoding="utf-8")
    return tab


def main():
    from tools.calcopy.hybrid import styles as ST
    if len(sys.argv) < 3:
        print(__doc__); return 2
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "plan":
        import argparse
        ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("doc"); ap.add_argument("work"); ap.add_argument("--version", required=True)
        a = ap.parse_args()
        tab = plan(Path(a.doc), Path(a.work), a.version)
        print(json.dumps({"rows": len(tab["rows"]), "sfx": tab["sfx"], "transitions": tab["transitions"], "flashes": tab["flashes"],
                          "check_ok": tab["check"]["ok"], "bad": tab["check"]["bad"], "out": str(Path(a.work) / "plan" / "자막표.json")}, ensure_ascii=False, indent=1))
        return 0
    st = ST.load(name)
    if cmd == "count":
        c = count(st)
        if "--top" in sys.argv:          # 상위 편 묶음(지시서 15) — counted.top + channel/<slug>/_kal/상위편_목표.json density·hook
            c["top"] = top_of(st, c)
            if "--dry" not in sys.argv:
                print(f"상위편_목표.json ← {write_top(st, c['top'])}")
        elif (st["placement"].get("counted") or {}).get("top"):
            c["top"] = st["placement"]["counted"]["top"]       # --top 없이 다시 세도 앞서 잰 상위 편 묶음은 남긴다
        if "--dry" not in sys.argv:
            ST.save_counted(name, c)
        print(json.dumps({k: v for k, v in c.items() if k != "videos"}, ensure_ascii=False, indent=1))
        for v in c["videos"]:
            print(v["id"], v["n"], {k: s["enter"] for k, s in v["slots"].items()}, "stk", v["stickers"], "var", v["variants"], "sfx", len(v["sfx"]),
                  "trans", v["transitions"], "sfx_lines", [(e["kind"], e["role"]) for e in v["sfx_lines"]])
    elif cmd == "show":
        print(json.dumps({k: v for k, v in st["placement"].items() if k != "counted"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
