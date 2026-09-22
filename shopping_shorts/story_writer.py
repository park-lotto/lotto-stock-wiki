# -*- coding: utf-8 -*-
"""이야기 작가 — 씨앗 결로 쓰고 화면은 나중에 붙인다 (2026-09-22 사장님 승인).

★왜 새 모듈인가: 기존 `backbone_assemble.write_lines*`는 **화면 묶음(groups_out)을 먼저 받아**
  그 화면에 맞춰 대본을 쓴다. 그래서 화면이 대본을 끌고 갔다(핸드오프: "두 달간 14번 전부
  문장↔장면 매칭을 더 잘하는 법이었다. 전부 두더지").
  여기서는 **대본이 먼저**다 — 씨앗 결 + 제품 특징으로 쓰고, 컷은 `assign_cuts`가 뒤에 붙인다.
  노바 작가(썰쇼핑 1위)가 쓰는 순서와 같다(2026-09-22 영상 정독).

★플랫폼으로 갈린다(실측):
  유튜브 썰  — 반말 · CTA 없음 · 고조 = 순간→벌어지는일→없애버림 · 신호어 17가지
  인스타     — 존댓말 · CTA · 고조 = before→after 체험담 · `~더라고요` 95~98% · 신호어 5가지
  섞으면 둘 다 망가진다.

★표현은 자유다(2026-09-22 사장님 "어짜피 이건 후킹싸움이야"):
  불편·상황·인물·수치·효능을 화면 밖에서 가져와도 된다. 사용자가 고칠 수 있다.
  단 **claim(제품이 하는 일)은 화면에 보이는 것만** — 그래야 컷을 붙일 수 있다.

시험대 원본: tools/seed_analyzer/{insta_writer,try_forced,pain_extract}.py
"""
import re

from shopping_shorts import script_generate as _sg

# ── 신호어 세트 — 코드가 칸 순서대로 박는다 ────────────────────────────────
# ★모델에게 고르게 하면 가장 흔한 하나로 쏠린다(실측 2026-09-22: 2편 모두
#   "이게 진짜 말도 안 되는 게"). 세트마다 한 자리는 비워 기계 티를 없앤다.
YT_SETS = {
    "A": ["심지어", "이게 말도 안 되는게", "", "근데 진짜 미친 포인트는"],
    "B": ["", "게다가", "이게 미친 포인트인게", "진짜 충격적인 포인트는"],
    "C": ["이게 말도 안 되는게", "", "대박인 건", "근데 진짜 충격적인 포인트는"],
    "D": ["심지어", "거기다", "진짜 말도 안 되는게", ""],
    "E": ["", "충격적인 건", "이게 미친 포인트인게", "진짜 미친 포인트는 따로 있는데"],
    "F": ["게다가", "이게 말도 안 되는게", "", "진짜 대박인 건"],
    "G": ["", "이게 말도 안 되는게", "거기다", "진짜 미친 포인트는"],
    "H": ["심지어", "", "충격적인 건", "근데 진짜 미친 포인트는"],
}
# 인스타는 낱말이 다르다(실측: 심지어 73·게다가 39·대박인 건 21·거기다 7·무엇보다 6).
# 썰의 "진짜 미친 포인트는"·"이게 말도 안 되는게"는 인스타에 거의 없다.
IG_SETS = {
    "A": ["", "심지어", "무엇보다"],
    "B": ["게다가", "", "대박인 건"],
    "C": ["", "거기다", "심지어"],
    "D": ["심지어", "", "게다가"],
    "E": ["", "대박인 건", "거기다"],
}

_EXPR = """■ 표현은 자유롭게 — 후킹이 전부다
불편·상황·인물·수치·효능·가격은 **화면에 없어도 쓸 수 있다.** 그 제품을 쓰는 사람이
겪을 법한 일이면 된다. 사용자가 나중에 고치니 세게, 구체적으로 써라.
★다만 장면을 아주 못 만들 정도로 화면과 동떨어진 말은 피해라 — 이 재료로 화면을 붙인다."""

# ── 유튜브 썰 ────────────────────────────────────────────────────────────
YT_SCHEMA = {
    "type": "object",
    "properties": {
        "hook": {"type": "string"},
        "bait": {"type": "string"},
        "reveal": {"type": "string"},
        "contrast": {"type": "string"},
        "escalations": {"type": "array", "items": {"type": "object", "properties": {
            "moment": {"type": "string"},
            "what_happens": {"type": "string"},
            "erased": {"type": "string"},
            "from_pain": {"type": "string"},
            "feat": {"type": "integer"},
        }, "required": ["moment", "what_happens", "erased", "from_pain", "feat"]}},
        "twist": {"type": "string"},
        "closing": {"type": "string"},
    },
    "required": ["hook", "bait", "reveal", "contrast", "escalations", "twist", "closing"],
}

YT_BRIEF = """너는 한국 쇼핑 숏폼 나레이션 작가다. 반말체 유튜브 썰쇼핑 대본을 써라.

■ 설명문을 쓰지 마라
"A는 B 기능이 있어 편리합니다" 같은 문장은 한 줄도 쓰지 마라.
제품 설명서가 아니라 그 장면을 보고 있는 사람의 말이다.
  X 원래 두피 영양제는 손에 묻어서 바르기 불편하지만
  O 겨우 짜서 바르려는데 손가락 사이로 다 흘러내리고 머리만 떡져서

■ reveal — 짧게 끊어라
"이건 바로 {제품명}." 로 끝낸다. 뒤에 설명을 이어 붙이지 마라.
실측(썰채널 30편): 공개 줄은 거의 전부 제품명만 말하고 바로 다음 칸으로 넘어간다.

■ contrast — 기존 것의 한계를 걸어 대비를 만든다
"온도를 유지만 시켜 주던 기존 컵홀더와는 달리" · "007 가방 크기 급의 거추장스러운 버너와 달리"
댈 게 없으면 빈칸으로 둬라.

■ escalations — 재료의 불편이 **진짜 괴로운 것만** 넣어라
칸 수를 채우려 하지 마라. 1개여도 2개여도 된다.
from_pain에는 근거로 삼은 특징을 적어라. 댈 게 없으면 그 칸을 만들지 마라.
칸을 여는 신호어는 **우리가 붙인다. 네가 쓰지 마라.** moment는 신호어 다음에 이어질 말로 시작해라.

칸 하나는 이렇게 채운다 (없는 걸 지어내지 말고 **있는 불편을 깊게 파라**):
  moment        그 불편이 벌어지는 순간을 현재형으로   "겨우 재워놓고 바닥에 내려놓는 순간"
  what_happens  그때 벌어지는 일 + 반복되는 괴로움    "등이 닿자마자 눈을 번쩍 떠서 다시 재우던 그 지옥을"
  erased        그걸 통째로 없앤 방식, 강한 동사로 끊기 "자리를 아예 하나로 합쳐서 없애 버렸다는 거"
  ★what_happens가 "~을/를"로 끝나면 erased는 그 목적어를 받는 서술어로 이어져야 한다.

■ twist는 앞 고조와 **다른 축**이어야 한다 (위생·보관·휴대 같은 다른 걱정거리)
■ closing은 권유가 아니다 — "~해 보세요" 금지. 남의 말로 닫아라("…난리라는데").

■ 표현 재료 (골라 쓰는 것이다. 안 맞으면 쓰지 마라)
  의태어  싹·착·탁·쓱·확·쏙·슥·쭉·뚝딱·똑·푹·사르르·살살·번쩍
  고통    지옥·진절머리·빡쳤던·노이로제·스트레스·귀찮·답답·짜증
  없애기  없애 버렸다는 거 · 사라져 버리는데 · 줄여 버렸다고 · 날려 버려서
  증언    난리라는데 · 품절 대란 · 입소문이 터지며 · 쓰는 사람이 많다는데
  폭넓히기 거실이든 안방이든 차 안이든

""" + _EXPR + """

■ 지키는 것
- 문장을 마침표로 딱 끊지 말고 연결어미로 이어라.
- 씨앗의 말투는 가져오되 문장은 베끼지 말고 새로 써라."""

# ── 인스타 ───────────────────────────────────────────────────────────────
IG_SCHEMA = {
    "type": "object",
    "properties": {
        "opening": {"type": "string"},
        "scene": {"type": "string"},
        "ask": {"type": "string"},
        "reveal": {"type": "string"},
        "beats": {"type": "array", "items": {"type": "object", "properties": {
            "before": {"type": "string"},
            "after": {"type": "string"},
            "from_pain": {"type": "string"},
            "feat": {"type": "integer"},
        }, "required": ["before", "after", "from_pain", "feat"]}},
        "feeling": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["opening", "scene", "ask", "reveal", "beats", "feeling", "cta"],
}

IG_BRIEF = """너는 인스타 릴스 쇼핑 대본 작가다. **겪은 일을 이야기하듯** 써라.

■ 이건 설명이 아니라 상황극이다
  X 이 제품은 콩알만큼 떼어 붙이면 고정되는 기능이 있습니다
  O 어느 날 언니네 갔더니 식탁 위 소품들이 하나도 안 굴러다니길래 뭐 했냐고 물어봤거든요

■ 말투 (인스타 641편 실측)
- 존댓말 1인칭. 문장 끝은 **~더라고요 / ~거든요 / ~어요 / ~습니다**.
- 유튜브 썰 어미(`~다는데` · `~버렸다는 거` · `~는 거임`)를 쓰면 인스타가 아니다.
- 감탄으로 여는 편이 많다(38%): "와…", "아니 이거".

■ 대사는 따옴표 없이 **간접화법**으로 (실측: 따옴표 대사 0%)
  "비결이 뭐냐니까 창문에 그냥 이 페인트를 바른 거래요"
  "놀라서 뭐 했냐고 물어봤더니 트레이너한테 추천 받았다는 거예요"
ask 칸이 이 자리다. 인물(친구·언니·엄마·지인)은 이야기를 사게 하는 장치이니 자연스럽게 등장시켜라.

■ beats — 겪은 일을 before/after로
  before  이걸 모를 때 내가 어떻게 하고 있었나. 그 장면과 짜증을 그대로.
  after   쓰고 나서 어떻게 달라졌나. **기능이 아니라 장면으로.**
  from_pain  이 칸이 어느 특징에서 나왔는지 적어라.
칸 수를 채우려 하지 마라. 억지로 늘리면 안 쓴 것만 못하다.

■ feeling — 결과를 숫자가 아니라 **생활의 장면**으로
  "이거 들고 간 날부터 물에서 나오지를 않아요" · "간만에 신혼 때로 돌아간 것 같아요"

""" + _EXPR + """

■ 지키는 것
- 시간 표지를 자연스럽게(37%): 얼마 전 · 어느 날 · 요즘 · 처음엔.
- 문장을 길게 이어 붙여라. 딱딱 끊으면 이야기가 아니라 목록이 된다."""


def _feats_block(feats):
    # ★번호를 매긴다 — 고조 칸이 **어느 재료에서 나왔는지 번호(feat)로** 답하게 한다.
    #   글로 적게 하면 풀어 쓴다(2026-09-22 실측: 특징 '원터치 타공 및 고정'을 "원터치 타공으로 수선 고민 해결"로
    #   적어 글자 대조가 실패 → 그 줄이 근거 컷을 못 받고 아무 컷이나 받았다).
    rows = ["(고조 칸마다 feat에 아래 **재료 번호**를 적어라. 그 번호의 화면이 그 칸에 붙는다.)"]
    for i, f in enumerate(feats or []):
        rows.append("%d. %s — %s" % (i + 1, f.get("name") or "", f.get("claim") or ""))
        if f.get("pain"):
            rows.append("    이게 없을 때: %s" % f["pain"])
    return "\n".join(rows)


def _pick(sets, key, nth=0):
    """세트를 정해진 규칙으로 고른다. nth는 **순번으로 더한다** —
    해시에 섞으면 한 작업의 1안과 3안이 우연히 같은 세트가 된다(2026-09-22 실측)."""
    import zlib
    names = sorted(sets)
    i = (zlib.crc32(str(key).encode("utf-8")) % len(names) + int(nth)) % len(names)
    return names[i], sets[names[i]]


def write(product, seed_text, feats, platform="yt", style=None, key="", nth=0, note=None, seconds=0):
    """대본 한 편 → [{beat, text}]. 실패하면 [](호출부가 옛 경로로 간다).

    platform: "yt"(유튜브 썰) | "ig"(인스타)
    style:    {"name","hook_angle","flow","extra"} — 고객이 고른 스타일(없으면 기본 흐름)
    """
    ig = (platform == "ig")
    brief = IG_BRIEF if ig else YT_BRIEF
    if style:
        brief += ("\n\n■ 이번 대본의 스타일: %s\n스토리라인: %s\n첫 줄 각도: %s\n%s"
                  % (style.get("name") or "", style.get("flow") or "",
                     style.get("hook_angle") or "", style.get("extra") or ""))
    if seconds:
        # ★분량은 **칸 수로** 맞춘다 — 칸을 얇게 쓰면 설명문이 된다(시험대 실측: 4칸을 만들다 칸마다 1줄로 쪼그라듦).
        #   안 넘기면 재료 컷이 동난다(2026-09-22 실측 job 13d4cab55fba: 쓸 컷 27개·48.8초에 대본 45.7초 → 4줄이 컷 없음).
        from shopping_shorts.script_gate import SPEECH_CHARS_PER_SEC as _CPS
        brief += ("\n\n■ 분량: 전체 **%d자 안팎**(읽으면 약 %d초). 넘치면 고조 **칸 수를 줄여라** — "
                  "칸 하나를 얇게 쓰지 마라. 남긴 칸은 깊게 파라." % (int(seconds * _CPS), int(seconds)))
    prompt = "%s\n\n[제품] %s\n\n[씨앗 — 이 제품으로 터진 영상의 말]\n%s\n\n[재료]\n%s" % (
        brief, product or "", (seed_text or "").strip(), _feats_block(feats))
    out = _sg._call_json(prompt, IG_SCHEMA if ig else YT_SCHEMA, note=note) or {}
    return _to_lines(out, ig, key, nth, feats)


def _group_of(from_pain, feats):
    """고조 칸이 댄 근거(from_pain) → 특징 번호. 못 찾으면 -1(구조 줄처럼 남는 컷을 받는다).
    모델은 특징 이름을 적기도 하고 불편 문장을 적기도 한다 — 둘 다 본다."""
    fp = re.sub(r"\s+", "", from_pain or "")
    if not fp:
        return -1
    for i, f in enumerate(feats or []):
        nm = re.sub(r"\s+", "", f.get("name") or "")
        pn = re.sub(r"\s+", "", f.get("pain") or "")
        if (nm and (nm in fp or fp in nm)) or (pn and (pn[:8] in fp or fp[:8] in pn)):
            return i
    return -1


_LEAD_CONJ = re.compile(r"^(근데|그런데|그리고|또|그래서|또한)\s+")


def _to_lines(o, ig, key, nth, feats=None):
    """모델 출력 → [{role, text, group}]. group = 그 줄이 말하는 특징 번호(-1 = 구조 줄).
    ★신호어는 칸의 **첫 줄 앞에 붙인다** — 따로 한 줄로 두면 3글자짜리 줄에 컷이 배정된다."""
    esc_keys = ("before", "after") if ig else ("moment", "what_happens", "erased")
    if ig:
        escs = o.get("beats") or []
        _, sigs = _pick(IG_SETS, key, nth)
        rows = [("훅", o.get("opening"), -1), ("장면", o.get("scene"), -1)]
        if (o.get("ask") or "").strip():
            rows.append(("물어봄", o["ask"], -1))
        rows.append(("공개", o.get("reveal"), -1))
        tail = [("소감", o.get("feeling"), -1), ("CTA", o.get("cta"), -1)]
    else:
        escs = o.get("escalations") or []
        _, sigs = _pick(YT_SETS, key, nth)
        rows = [("훅", o.get("hook"), -1), ("미끼", o.get("bait"), -1), ("공개", o.get("reveal"), -1)]
        if (o.get("contrast") or "").strip():
            rows.append(("대비", o["contrast"], -1))
        tail = [("반전", o.get("twist"), -1), ("마무리", o.get("closing"), -1)]
    for i, e in enumerate(escs):
        n = e.get("feat")
        gi = (n - 1) if isinstance(n, int) and 1 <= n <= len(feats or []) else _group_of(e.get("from_pain"), feats)
        sig = sigs[i] if i < len(sigs) else ""
        # ★인스타는 신호어를 **after 줄**에 붙인다(2026-09-22 실측: 히트작 641편의 신호어 146개 중 과거 불편
        #   "전에는~" 앞에 온 것 0개. before 줄에 붙이면 "게다가 전에는 …했거든요"가 돼 10편 중 4편이 어색했다).
        sig_key = "after" if ig else esc_keys[0]
        for k in esc_keys:
            t = (e.get(k) or "").strip()
            if not t:
                continue
            if sig and (k == sig_key or not (e.get(sig_key) or "").strip()):
                t = _LEAD_CONJ.sub("", t)      # "게다가 근데 이건…" — 신호어 뒤 접속사 겹침(실측 7줄 중 1)
                t, sig = sig + " " + t, ""
            rows.append(("고조%d" % (i + 1), t, gi))
    rows += tail
    return _drop_repeat_signal(
        [{"role": b, "text": re.sub(r"\s+", " ", t).strip(), "group": g}
         for b, t, g in rows if (t or "").strip()], sigs)


# ── 재료에서 특징 + 불편(pain) 뽑기 (모델 1회) ─────────────────────────────
# ★정의는 여기 한 곳(0순위-B). 시험대 tools/seed_analyzer/pain_extract.py는 이걸 가져다 쓴다.
#   근거(라이브 실측 2026-09-22, 최근 57 job·3,880 세그): shot_role '문제' 132·'before' 339,
#   57 job 중 43개(75%)에 문제/before 세그가 있다 — 뽑는 사람이 없었을 뿐이다.
PROBLEM_ROLES = {"문제", "before"}
PROBLEM_WORDS = re.compile(r"불편|어려움|번거|귀찮|지저분|엉키|엉망|힘들|고생|낭비|"
                           r"문제|손상|망가|샌다|흘러|끈적|답답|공감")

FEATS_SCHEMA = {
    "type": "object",
    "properties": {"feats": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"},
        "claim": {"type": "string"},
        "pain": {"type": "string"},
        "from_cuts": {"type": "array", "items": {"type": "string"}},
    }, "required": ["name", "claim", "pain", "from_cuts"]}}},
    "required": ["feats"],
}

FEATS_BRIEF = """아래는 같은 제품을 찍은 영상들의 장면 태깅이다.
이 제품의 특징을 **3~4개**만 뽑아라. 제일 센 것만 남기고 약한 건 버려라.

특징마다 네 가지를 적는다:
  name   짧은 이름
  claim  이 제품이 실제로 하는 일 (화면에 보이는 것만)
  pain   ★**이게 없을 때 뭐가 괴로운가** — 기능을 뒤집어 쓰지 말고, 그 사람이 겪던 장면으로 적어라
         X 고정이 안 된다                     (기능을 뒤집은 말 — 쓸모없다)
         O 조금만 건드려도 쓰러지고 굴러다녀서 매번 다시 세워야 했다
  from_cuts  그 특징이 **화면에 실제로 보이는** 컷 번호들 (목록에 있는 번호만. 지어내지 마라)

pain을 적는 법:
- 태깅에 **[문제]·[before] 컷**이 있으면 먼저 거기서 가져와라. 제작자가 찍어 둔 불편이다.
- `용처` 설명에 "~의 어려움", "~하는 불편함"처럼 적혀 있으면 그대로 쓴다.
- ★화면에 그 장면이 없어도 된다(2026-09-22 사장님). 카메라는 제품이 **잘 되는 모습**을 찍지
  불편한 장면은 거의 안 찍는다(실측: 문제 컷이 3,880개 중 132개=3.4%).
  그러니 **그 제품을 쓰는 사람이라면 누구나 겪을 법한 불편**을 구체적인 장면으로 적어라.
    O 테이프로 붙이면 나중에 누렇게 떠서 떼어낼 때 자국이 남는다
- 기능을 뒤집어 쓰지 마라.  X 고정이 안 된다  /  X 도포가 균일하지 않다

★claim(이 제품이 하는 일)은 화면에 보이는 것만 쓴다. pain은 화면 밖에서 와도 된다."""


def source_block(sources):
    """태깅을 모델이 읽을 형태로. 문제/before 컷을 앞에 모아 눈에 띄게 한다."""
    prob, normal = [], []
    for v in sources or []:
        for x in (v.get("segments") or []) if isinstance(v, dict) else []:
            role = x.get("shot_role") or ""
            up = (x.get("use_point") or "")
            line = "  [%s] %s | 화면:%s%s%s%s" % (
                x.get("seg_id"), role, (x.get("scene_desc") or "")[:70],
                (" | 변화:%s" % (x.get("change") or "")[:40]) if x.get("change") else "",
                (" | 용처:%s" % up[:70]) if up else "",
                (" | 특징:%s" % " / ".join(str(b) for b in (x.get("product_benefits") or [])[:2]))
                if x.get("product_benefits") else "")
            (prob if (role in PROBLEM_ROLES or PROBLEM_WORDS.search(up)) else normal).append(line)
    out = []
    if prob:
        out += ["[불편을 보여주는 컷 — pain은 여기서 가져와라]"] + prob[:20] + [""]
    out.append("[나머지 컷]")
    out += normal[:60]
    return "\n".join(out)


def extract_feats(sources, product="", note=None):
    prompt = "%s\n\n[제품] %s\n\n%s" % (FEATS_BRIEF, product or "(미상)", source_block(sources))
    return (_sg._call_json(prompt, FEATS_SCHEMA, note=note) or {}).get("feats") or []


# ── 라이브 연결: 대본 먼저 → 컷은 뒤에 (관리자 스위치 story_writer_enabled) ──────
MIN_LINES = 5      # 훅·공개·고조 1칸(2줄+)·마무리 — 이보다 짧으면 모델이 칸을 비운 것이다


def _style_of(sp):
    """고객이 고른 스타일(스파인) → write()의 style. 빈칸 틀은 안 넘긴다 — 이름·흐름만."""
    return {"name": sp.get("name") or "",
            "flow": " → ".join(str(r) for r in (sp.get("beat_roles") or [])),
            "hook_angle": "스타일 이름 「%s」이 말하는 각도로 첫 줄을 연다" % (sp.get("name") or ""),
            "extra": ""}


def _fit_length(lines, limit_secs):
    """대본이 한도를 넘으면 **고조 칸을 뒤에서부터 통째로** 뺀다(최소 1칸은 남긴다). 돌려준 값 = (줄, 뺀 칸 수).
    ★모델은 분량 지시를 안 지킨다(2026-09-22 실측, 목표 25초: 인스타 42·31·54초 / 썰 32·40·35초).
      칸을 얇게 다듬으면 설명문이 되므로 문장은 안 건드리고 칸 단위로만 뺀다 — 칸 하나는 그 자체로 완결이다."""
    from shopping_shorts import backbone_assemble as ba
    lines, dropped = list(lines), 0
    while sum(ba._secs(L["text"]) for L in lines) > limit_secs:
        escs = sorted({L["role"] for L in lines if L["role"].startswith("고조")}, key=lambda r: int(r[2:]))
        if len(escs) <= 1:
            break
        lines = [L for L in lines if L["role"] != escs[-1]]
        dropped += 1
    return lines, dropped


def _share_cuts(lines, bs, seg_index):
    """컷이 하나도 없는 줄에 **남는 컷을 나눠 준다**. 돌려준 값 = 끝내 빈 줄 번호들.
    ★assign_cuts는 앞 줄부터 '길이+여유+최소 2컷'을 채워 재료가 빠듯하면 뒤 줄이 빈손이 된다
      (2026-09-22 실측 job 13d4cab55fba: 쓸 컷 27개를 9줄 중 8줄이 다 쓰고 마무리 줄 0컷).
      빈 줄은 3단계 채우기가 대본을 안 보고 메우므로, 넉넉한 줄에서 **빼도 대사 길이를 덮는 컷만** 옮긴다."""
    from shopping_shorts import backbone_assemble as ba

    def secs(s):
        return (seg_index.get(s) or {}).get("secs") or 0.0
    empty = []
    for i, b in enumerate(bs):
        if b and b.get("segs"):
            continue
        need, got = ba._secs(lines[i]["text"]), []
        while sum(secs(s) for s in got) < need:
            donors = [(len(d["segs"]), j) for j, d in enumerate(bs) if j != i and d and len(d.get("segs") or []) > 1
                      and sum(secs(s) for s in d["segs"][:-1]) >= ba._secs(lines[j]["text"])]
            if not donors:
                break
            j = max(donors)[1]
            got.append(bs[j]["segs"].pop())
        bs[i] = {"role": lines[i]["role"], "seg": got[0] if got else "", "segs": got}
        if not got:
            empty.append(i)
    return empty


def _drop_repeat_signal(lines, sigs):
    """모델이 직접 쓴 줄(반전·소감 등)이 **코드가 박은 신호어로 또 시작하면** 떼어 낸다 — 한 편에 "심지어"가 두 번 난다."""
    used = [s for s in sigs if s]
    for L in lines:
        if L.get("group", -1) != -1 or L["role"].startswith("고조"):
            continue
        for s in used:
            if L["text"].startswith(s + " "):
                L["text"] = L["text"][len(s):].strip()
    return lines


# ★"~더라고요/~거든요/~는데요/~잖아요"가 빠져 있었다(2026-09-22 말맛 센서스 실측): 인스타 대표 어미(docstring에도
#   95~98%라 적어 놓고!)를 안 세어, 차량용 홀더 씨앗("더라고요"×3)이 존댓말 어절 2개로 잡혀 **썰(반말)로 써졌다**.
_POLITE_ENDS = r"(어요|아요|에요|예요|해요|세요|네요|죠|니다|니까|더라고요|더라구요|거든요|는데요|잖아요|고요|나요|까요|래요|대요|돼요|져요|봐요|줘요|워요|와요)"
_POLITE_WORD = re.compile(_POLITE_ENDS + r"[.!?~…]*$")
_POLITE_SPLIT = re.compile(_POLITE_ENDS + r"(?=[가-힣])")     # 어미 목록은 위 한 곳(0순위-B)


def seed_platform(seed_text):
    """씨앗의 결 → "ig"(존댓말 체험담) | "yt"(반말 썰). **어절 단위**로 센다.
    ★전사엔 문장부호가 거의 없다(실측 524자에 2개) — 문장으로 나눠 끝말을 보면 한 덩어리가 돼 판정이 무의미하다."""
    # ★자막을 이어 붙인 전사는 문장 사이 띄어쓰기가 없다("안 돼요저도 매번사실") → 어미 뒤에서 한 번 끊어 준다.
    #   히트작 1,116편 대조(2026-09-22): 인스타 존댓말 놓침 38→26, 썰 소개체 362편 오판 0.
    #   문턱(3개·3%)은 그대로 — 2개로 낮추면 놓침 16이 되지만 썰 소개체 12편이 인스타로 넘어간다.
    t = _POLITE_SPLIT.sub(r"\1 ", seed_text or "")
    ws = t.split()
    pol = sum(1 for w in ws if _POLITE_WORD.search(w))
    return "ig" if pol >= 3 and pol / max(1, len(ws)) >= 0.03 else "yt"


def make_drafts(spines, job, seconds=25, job_id=""):
    """(drafts, why) — app._backbone_drafts와 같은 계약(비면 why에 이유, 조용한 폴백 금지).

    자동 1안(씨앗 결 그대로) + 고른 스타일 1안. 모델 호출 = 특징 1회 + 안마다 1회.
    ★화면은 씨앗 영상을 안 쓴다(backbone_assemble.assemble과 같은 규칙, 2026-09-21 사장님).
    """
    from shopping_shorts import backbone_assemble as ba
    srcs = ba.sources_from_extract((job or {}).get("extract") or {})
    if not srcs:
        return [], "재료 분석(extract)이 아직 없음"
    seed_src = ba.seed_source(srcs, (job or {}).get("backbone_main"))
    seed_text = ((seed_src or {}).get("full_text_ko") or (seed_src or {}).get("full_text") or "").strip()
    if len(seed_text) < 60:
        return [], "씨앗 영상의 말이 너무 짧음(%d자)" % len(seed_text)
    vis = ba._drop_seed(srcs, seed_src)
    seg_index = ba._seg_index(vis)
    product = ((seed_src.get("source_brief") or {}).get("product") or "").strip()
    note = {}
    feats = extract_feats(vis, product, note=note)
    if not feats:
        return [], "특징을 못 뽑음(%s)" % (note.get("reason") or "빈 응답")
    groups_out = {"product": product, "order": list(range(len(feats))), "alt_use": False,
                  "groups": [{"name": f.get("name") or "", "claim": f.get("claim") or "",
                              "cuts": [c for c in (f.get("from_cuts") or []) if c in seg_index]}
                             for f in feats]}
    plans = [(None, seed_platform(seed_text))]
    for sp in (spines or [])[:1]:
        plans.append((sp, "yt" if sp.get("no_cta") else "ig"))
    backbone_vid = seed_src.get("video_id")
    drafts, whys = [], []
    for nth, (sp, plat) in enumerate(plans):
        name = (sp or {}).get("name") or "씨앗 결 이야기"
        n = {}
        lines = write(product, seed_text[:1500], feats, platform=plat,
                      style=_style_of(sp) if sp else None, key=job_id or product, nth=nth, note=n,
                      seconds=seconds)
        if len(lines) < MIN_LINES:
            whys.append("%s: 대본이 %d줄뿐(%s)" % (name, len(lines), n.get("reason") or "칸 빔"))
            continue
        # 한도 = 목표의 1.5배와 '쓸 수 있는 재료 화면 길이의 65%' 중 짧은 쪽 — 화면이 없는 말은 길어 봐야 빈 줄이 된다.
        #   65%의 근거(★job 13d4cab55fba 1건·재료 48.8초뿐이다 — 재료를 넓혀 다시 재라): 대본 31.8초 이하 4편은
        #   빈 줄 0, 33.3초 이상 5편은 빈 줄 1~4. 컷이 덩어리라(2초 대사에 4.8초 컷) 길이 합만큼은 못 쓴다.
        footage = sum(v["secs"] for v in seg_index.values() if v["secs"] >= ba.MIN_CUT_SECS)
        lines, n["dropped_escalations"] = _fit_length(lines, min(float(seconds) * 1.5, footage * 0.65))
        bs, report = ba.assign_cuts(lines, groups_out, seg_index, backbone_vid)
        n["no_cut_lines"] = _share_cuts(lines, bs, seg_index)     # 끝내 빈 줄 = 재료가 대본보다 짧다
        meta = {"product": product, "spine": {"id": (sp or {}).get("id"), "name": name},
                "groups": groups_out, "report": report, "note": n}
        d = ba.to_draft("\n".join(L["text"] for L in lines), bs, meta)
        d["made_by"] = "이야기작가"
        d["auto_pick"] = sp is None
        d["platform"] = plat
        d["line_groups"] = [L.get("group", -1) for L in lines]     # 점검용: 줄이 어느 재료에 걸렸나
        d["feat_names"] = [f.get("name") or "" for f in feats]
        drafts.append(d)
    return drafts, "; ".join(whys)
