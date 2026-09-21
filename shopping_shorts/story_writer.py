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
        }, "required": ["moment", "what_happens", "erased", "from_pain"]}},
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
        }, "required": ["before", "after", "from_pain"]}},
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
    rows = []
    for f in feats or []:
        rows.append("- %s — %s" % (f.get("name") or "", f.get("claim") or ""))
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


def write(product, seed_text, feats, platform="yt", style=None, key="", nth=0, note=None):
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
    prompt = "%s\n\n[제품] %s\n\n[씨앗 — 이 제품으로 터진 영상의 말]\n%s\n\n[재료]\n%s" % (
        brief, product or "", (seed_text or "").strip(), _feats_block(feats))
    out = _sg._call_json(prompt, IG_SCHEMA if ig else YT_SCHEMA, note=note) or {}
    return _to_lines(out, ig, key, nth)


def _to_lines(o, ig, key, nth):
    if ig:
        escs = o.get("beats") or []
        _, sigs = _pick(IG_SETS, key, nth)
        rows = [("훅", o.get("opening")), ("장면", o.get("scene"))]
        if (o.get("ask") or "").strip():
            rows.append(("물어봄", o["ask"]))
        rows.append(("공개", o.get("reveal")))
        for i, b in enumerate(escs):
            if i < len(sigs) and sigs[i]:
                rows.append(("고조%d" % (i + 1), sigs[i]))
            for k in ("before", "after"):
                if (b.get(k) or "").strip():
                    rows.append(("고조%d" % (i + 1), b[k]))
        rows += [("소감", o.get("feeling")), ("CTA", o.get("cta"))]
    else:
        escs = o.get("escalations") or []
        _, sigs = _pick(YT_SETS, key, nth)
        rows = [("훅", o.get("hook")), ("미끼", o.get("bait")), ("공개", o.get("reveal"))]
        if (o.get("contrast") or "").strip():
            rows.append(("대비", o["contrast"]))
        for i, e in enumerate(escs):
            if i < len(sigs) and sigs[i]:
                rows.append(("고조%d" % (i + 1), sigs[i]))
            for k in ("moment", "what_happens", "erased"):
                if (e.get(k) or "").strip():
                    rows.append(("고조%d" % (i + 1), e[k]))
        rows += [("반전", o.get("twist")), ("마무리", o.get("closing"))]
    return [{"role": b, "text": re.sub(r"\s+", " ", t).strip()}
            for b, t in rows if (t or "").strip()]
