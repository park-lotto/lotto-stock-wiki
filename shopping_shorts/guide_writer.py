"""지침서 작가 — 채널 대본 지침서(정리표 형식)를 입혀 버텍스가 스토리보드 대본을 쓰고, 코드가 검수한 뒤 걸린 것만 1번 다시 쓰게 한다.

판단 주인: 이 모듈 하나(storyboard._board_guide 가 부른다).
  사장님 2026-10-20: "숏템 클로드형은 Claude 가 대본을 쓰고, 숏템메이커는 지침서를 입혀 버텍스가 써라."
  지침서·참고 대본: shopping_shorts/guides/<채널>.html · <채널>_refs.json — 대본 칼카피 엔진(tools/calcopy/script)이 채널 600편을 뜯어 만든 것.
시험에서 1등 결을 재현한 조합만 쓴다(같은 소재 비교 시험 · 2026-10-20):
  - B 정보형 = 지침서(0.공통+B) + 씨앗 1편 + 정보형 히트 전문 10편 / A 체험형 = 지침서(0.공통+A)만(참고 전문을 넣으면 사용 설명서처럼 무너졌다)
  - 정보형 소재 관문: 근거(화면 설명)에 만든 사람·계기·사건 사실이 2개 미만이면 체험형으로 쓴다
  - 버텍스 결과는 그대로 못 낸다(인스타판 시험: 4편 중 3편 길이 초과·예 낱말·사실 지어냄) → check() 로 걸러 1번 다시 쓰게 하고, 남은 문제는 보드에 남긴다
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDES = os.path.join(HERE, "guides")

STYLES = {
    "g:expA": {"channel": "guide_home", "style": "A", "name": "체험형(지침서)"},
    "g:infoB": {"channel": "guide_home", "style": "B", "name": "정보형(지침서)"},
}
LEN = {"A": (140, 190), "B": (180, 230)}
# 칸 이름 — storyboard.ROLE_KO 에 있는 것만(화면 칸 이름·끼워 넣기·신호어가 이 이름으로 돈다)
SLOTS = {
    "A": [("hook", "결과·오해로 여는 첫 줄"), ("situation", "사건 펼치기 — 언제·누가·어디서(정체는 아직)"), ("pain", "왜 고민이었나 — 돈·전셋집·집주인"),
          ("authority", "조언자 — 권위를 인물의 입으로"), ("reveal", "'바로 ~예요' 한 줄 단독"), ("mechanism", "왜 되는지 한 줄"),
          ("howto", "쓰는 동작 — 딱 1줄"), ("effect", "와우 — 비교·감각·주변 반응"), ("extra", "심지어 — 다른 축의 장점"),
          ("result", "공간·생활 변화"), ("end", "닫기 — 첫 줄 그 사람으로 돌아와 비틀기"), ("cta", "댓글 키워드(인스타판만)")],
    "B": [("hook", "역설 첫 줄(숫자 없이)"), ("spread", "화제·정체 숨김"), ("pain", "배경·불편 — 공감 딜레마"), ("authority", "권위·정체 — 근데로 꺾기"),
          ("reveal", "'바로 ~예요' 한 줄 단독"), ("mechanism", "어떻게 되나 — 비교로"), ("action", "동작·숫자"), ("react", "사회 반응"), ("effect", "와우 — 감각+비교"),
          ("extra", "심지어 — 가장 센 카드 직전"), ("end", "닫기 — 첫 줄 회수"), ("cta", "댓글 키워드(인스타판만)")],
}
# 지침서 예 문장에서 나온 낱말 — 시험에서 버텍스가 그대로 베꼈다(인스타판 시험 5개). 코드가 잡는다.
BAN_WORDS = ["버려진", "금덩이", "돌처럼", "박박", "살살", "안개 낀", "페인트 가게", "황금 덩어리", "단체로 소리 질렀다는", "정리업체 알바하는"]
STORY_KEYS = re.compile(r"개발|만든|만들|창업|회사|방송|출시|판매|팔렸|특허|투자|발명|계기|유래")
SCHEMA = {"type": "object", "properties": {
    "mold": {"type": "string"}, "analysis": {"type": "string"}, "first_line_style": {"type": "string"},
    "slots": {"type": "array", "items": {"type": "object", "properties": {
        "slot": {"type": "string"}, "line": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}},
        "weak": {"type": "string"}}, "required": ["slot", "line", "ids"]}},
    "check": {"type": "string"}}, "required": ["mold", "slots"]}

_CACHE = {}


def _guide_text(channel):
    if channel not in _CACHE:
        h = open(os.path.join(GUIDES, channel + ".html"), encoding="utf-8").read()
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"<(br|/tr|/li|/h[1-3]|/p|/div)>", "\n", h)
        h = re.sub(r"</t[dh]>", " | ", h)
        t = re.sub(r"<[^>]+>", "", h).replace("&gt;", ">").replace("&amp;", "&").replace("&lt;", "<")
        _CACHE[channel] = re.sub(r"\n\s*\n+", "\n", t)
    return _CACHE[channel]


def section(channel, style):
    """지침서에서 0.공통 + 그 스타일 + 검수만 — 다른 스타일 규칙을 섞지 않는다."""
    t = _guide_text(channel)
    common = t[t.index("0. 공통"):t.index("체험형 —")]
    a0, b0, c0 = t.index("체험형 —"), t.index("정보형 —"), t.index("검수 — 시안마다")
    return common + "\n" + (t[a0:b0] if style == "A" else t[b0:c0]) + "\n" + t[c0:]


def _no_molds(guide_sec):
    """겹침 검사에서 '첫 줄 틀 사전'은 뺀다 — 틀의 고정 낱말(보고 진짜 깜짝 놀랐어요 …)은 쓰라고 준 말이다(라이브 시험 10-20 오판)."""
    i = guide_sec.find("3. 첫 줄 틀 사전")       # 지침서 3장 제목 — '첫 줄 틀 사전'이란 말은 0.공통·검수에도 나온다
    j = guide_sec.find("4. 블록 배치", i + 1) if i >= 0 else -1
    return guide_sec[:i] + guide_sec[j:] if i >= 0 and j > i else guide_sec


def refs(channel):
    p = os.path.join(GUIDES, channel + "_refs.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def gate(facts_text):
    """정보형 소재 관문 — 근거에 만든 사람·계기·사건 사실이 2줄 이상인가."""
    return sum(1 for ln in facts_text.splitlines() if STORY_KEYS.search(ln)) >= 2


def ns(t):
    return re.sub(r"\s", "", t or "")


def build(key, kind, scenes_txt, missing, star, roles_pick, platform="ig", issues=None, prev=None):
    """버텍스 프롬프트. scenes_txt = storyboard 의 장면 목록(조각 번호·길이·화면 설명) — 사실 근거이자 깔 장면."""
    meta = STYLES[key]
    style = meta["style"]
    lo, hi = LEN[style]
    slots = SLOTS[style] if platform == "ig" else [s for s in SLOTS[style] if s[0] != "cta"]
    cta = ("- 인스타판: 마지막 칸 cta = 댓글 키워드 한 줄('{바라는 것} 하고 싶으시면 댓글에 {키워드} 남겨주세요', 키워드 2~3자). cta 줄은 길이에서 뺀다.\n"
           if platform == "ig" else "- 유튜브판: cta 칸 없음.\n")
    head = ("너는 쇼핑 쇼츠 채널의 대본 작가 겸 편집자다. 아래 [대본 지침서] 0.공통과 스타일 %s(%s)가 이번 일의 지침 전부다. "
            "지침서 순서(첫 줄 틀 → 블록 배치 → 이야기 기술 → 검수)대로 이 재료로 스토리보드 대본 **1편**을 써라.\n"
            "- 제품이 무엇이고 무엇을 하는지는 [장면 목록]의 화면 설명에서만 읽어라. 화면에 없는 효능·숫자·회사·인물 사실은 지어내지 마라. "
            "인물·사건·반응·감상(체험담)은 지어내도 된다. 근거 없는 효과는 들은 얘기(~대요)로.\n"
            "- 상표 금지 — '이거'·제품군 낱말로. 존댓말 1인칭 체험·전언. 본문(cta 빼고) 공백 빼고 %d~%d자, 7~9칸 — 넘으면 실격. 한 칸 = 한 줄 = 사실 하나.\n"
            "- 지침서의 '이야기 기술' 표를 전부 지킨다. 지침서·참고 대본 문장 10자 이상 그대로 베끼기 금지 — 예 문장은 구조만.\n"
            "- 칸마다 ids: 그 말이 화면에 보이는 조각 번호 1~3개(목록에 있는 것만, 한 조각은 한 칸에만). 조각 길이 합 × 1.2 ≥ 문장 읽는 시간(글자 수 ÷ 7초). "
            "화면 밖 이야기(조언자·반응) 칸은 그 이야기에 어울리는 결과 장면으로.\n"
            "- slot 은 아래 칸 이름 중에서(순서는 지침서 블록 배치대로, 안 쓰는 칸은 뺀다): %s\n%s"
            "- mold 에 고른 첫 줄 틀 번호, first_line_style 에 첫 줄, check 에 검수 체크리스트 결과 한 줄.\n") % (
        style, "체험형" if style == "A" else "정보형", lo, hi, " / ".join("%s=%s" % s for s in slots), cta)
    body = "[대본 지침서]\n%s\n\n[재료 종류] %s\n[장면 목록 — 묶음별 조각 번호(길이): 화면 설명]\n%s\n[없는 장면 — 효능·사실로 쓰지 마라] %s\n[⭐ 손님이 꼭 쓰라고 고른 조각 — 반드시 어느 칸엔가] %s\n[🎯 손님이 역할을 짐작해 담은 조각] %s\n" % (
        section(meta["channel"], style), kind or "", scenes_txt, " / ".join(missing or []) or "(없음)", ", ".join(star or []) or "(없음)", roles_pick or "(없음)")
    if style == "B":
        rf = refs(meta["channel"])
        if rf:
            body = ("[씨앗 대본](조회 %d만) — 먼저 이 대본이 사람들을 홀린 요인(궁금증·고충→해결→놀람 순서·믿게 만든 것)을 analysis 에 짧게 적고 그 흐름을 옮겨라\n%s\n\n"
                    "[참고 대본 — 같은 채널 정보형 히트작 전문, 흐름만 본뜬다]\n%s\n\n" % (
                        rf["seed"]["views"] // 10000, rf["seed"]["text"], "\n\n".join("(%d만) %s" % (r["views"] // 10000, r["text"]) for r in rf["refs"]))) + body
    if issues:
        body += ("\n★직전 답이 코드 검수에 걸렸다 — 아래를 고쳐 처음부터 다시 써라(같은 장면 목록):\n%s\n직전 답 첫 줄: %s\n" % (
            "\n".join("- " + x for x in issues), (prev or {}).get("first_line_style") or ""))
    return head + "\n" + body


def check(slots, style, scene_text, banned_src="", segs=None):
    """코드 검수 — 걸린 이유 목록(없으면 통과). 길이 · 칸 수 · 금지 예 낱말 · 지침서/참고 8자 겹침 · 화면에 없는 숫자 · 장면 번호."""
    lo, hi = LEN[style]
    why = []
    body = [s for s in slots if s.get("slot") != "cta" and "댓글" not in (s.get("line") or "")]
    n = len(ns("".join(s.get("line") or "" for s in body)))
    if not (lo <= n <= hi):
        why.append("본문 길이 %d자 — %d~%d자로" % (n, lo, hi))
    if not (6 <= len(body) <= 9):
        why.append("본문 칸 %d개 — 7~9칸으로" % len(body))
    hit = [w for w in BAN_WORDS if w in "".join(s.get("line") or "" for s in body)]
    if hit:
        why.append("지침서 예 문장의 낱말을 그대로 씀: %s — 새 말로" % ", ".join(hit))
    if banned_src:
        src, seen = ns(banned_src), ns(scene_text)
        for s in body:
            t = ns(s.get("line"))
            for i in range(0, max(0, len(t) - 9)):
                frag = t[i:i + 10]      # 10자 — 8자는 제품 사용법 말(테이프 두르고 롤러…)까지 잡았다(라이브 시험 10-20)
                if frag in src and frag not in seen:
                    why.append("지침서·참고 대본과 10자 이상 같음: '%s…'" % frag)
                    break
    for s in body:
        for num in re.findall(r"\d+", s.get("line") or ""):
            if num not in scene_text:
                why.append("화면 설명에 없는 숫자 %s — 빼라" % num)
    if any(not s.get("ids") for s in body):
        why.append("장면 번호(ids)가 빈 칸이 있다")
    if segs:      # 장면 초 — 판정 주인은 storyboard.slot_checks(화면 '짧음'과 같은 식·같은 말속도 함수). 여기서 따로 계산하지 않는다
        from shopping_shorts.storyboard import slot_checks
        for i, (s, c) in enumerate(zip(slots, slot_checks(slots, segs))):
            if c["short"]:
                why.append("%d번째 칸(%s) 장면이 모자람 — 문장 %.1f초인데 장면 %.1f초, 조각을 더 깔아라" % (i + 1, s.get("slot"), c["need"], c["have"]))
    return why


def write(call, key, kind, scenes_txt, missing, star, roles_pick, platform="ig", scene_text="", segs=None):
    """call(prompt, schema) → dict. 1번 쓰고 검수 → 걸리면 이유를 붙여 1번 다시. 반환: (결과, 남은 문제, 쓴 스타일, 관문 메모)."""
    meta = STYLES[key]
    style, note = meta["style"], ""
    if style == "B" and not gate(scene_text):
        style, note = "A", "정보형 소재 관문: 화면 설명에 만든 사람·계기·사건 사실이 2개 미만이라 체험형으로 썼어요"
        key = "g:expA"
    rf = refs(meta["channel"]) if style == "B" else {}
    banned_src = _no_molds(section(meta["channel"], style)) + " ".join([rf.get("seed", {}).get("text", "")] + [r["text"] for r in rf.get("refs", [])])
    r = call(build(key, kind, scenes_txt, missing, star, roles_pick, platform), SCHEMA) or {}
    left = check(r.get("slots") or [], style, scene_text, banned_src, segs)
    tries = 1
    if left:
        r2 = call(build(key, kind, scenes_txt, missing, star, roles_pick, platform, issues=left, prev=r), SCHEMA) or {}
        left2 = check(r2.get("slots") or [], style, scene_text, banned_src, segs)
        tries = 2
        if r2.get("slots") and len(left2) <= len(left):
            r, left = r2, left2
    r["guide_tries"] = tries
    return r, left, style, note
