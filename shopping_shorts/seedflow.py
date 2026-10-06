# -*- coding: utf-8 -*-
"""씨앗 흐름 — 어떤 대본이든 같은 세 단계로 쓴다 (2026-10-06 사장님).

  "씨앗을 먼저 분석하고 / 제품에 대해 팔릴 만한 포인트·흥미로운 사실을 꺼내고 / 해외 영상들 분석 장면을 토대로 대본을 쓴다."

노바 작가 순서(docs/nova_writer_script_2026-09-22.md)와 같다: 씨앗은 **왜 홀렸나**와 **틀(흐름·말투)**을 뽑는 재료지
문장 재료가 아니다. 채널·스타일은 코드에 없다 — 틀은 그때그때 씨앗에서 나온다(이븐쇼핑 씨앗이면 이븐쇼핑 틀, 방구석이면 방구석 틀).

  ① analyze_seed   씨앗의 말 → 틀(칸 순서·말끝·말버릇) + 홀린 요인(무엇이 사람을 붙잡았나) + 씨앗이 이미 말한 포인트
  ② mine_points    제품 + 해외 영상 장면 태깅 → 팔릴 포인트·흥미로운 사실(어디서 왔는지 표시, 붙일 장면 번호)
  ③ write          틀은 씨앗 그대로, 내용은 ②의 포인트로, 줄마다 붙일 장면을 달아서
  ④ problems       씨앗 문장 베낌·없는 장면·말투 섞임·새 포인트 부족 → 1회 고쳐 쓰기

모델 호출기는 주입한다(call(prompt)->str). 표준 라이브러리만 쓴다 — 서버에서 /tmp 에 올려 시험할 수 있게.
"""
import json
import re

POINT_KINDS = ("팔릴 포인트", "흥미로운 사실", "뜻밖의 쓰임", "비교", "사람 이야기")
ORIGINS = ("씨앗", "영상", "일반지식")
MIN_NEW_POINTS = 2          # 씨앗에 없던 포인트를 적어도 이만큼 쓴다 — 노바 시안: 7줄 씨앗 → 18줄, 늘어난 건 씨앗에 없던 셀링포인트
COPY_SHARE = 0.5            # 한 줄의 6글자 조각 중 씨앗에 있는 비율이 이보다 크면 베낀 것

SEED_PROMPT = """아래는 조회수가 터진 쇼핑 쇼츠 한 편의 말(받아쓰기)이다. 이 영상을 **분석**해라. 새 대본을 쓰는 게 아니다.

찾을 것
1. 틀 — 이 대본이 어떤 **칸 순서**로 흘러가나. 칸마다 이름(이 대본에 맞는 말로) · 그 칸이 하는 일 · 그 칸의 원문.
2. 말투 — 반말/존댓말, 누가 누구에게 말하는 결인가(전해 듣는 썰 / 내 체험담 / 해설), 실제로 쓰인 말끝 5개 이내, 칸을 여는 말버릇.
3. ★홀린 요인 — 사람들이 이 영상을 끝까지 본 이유 1~3가지. "신기해서" 같은 말 말고, **대본의 어느 말이 무엇을 건드렸는지**
   (예: "'내려놓는 순간 리셋된다'로 육아인의 고충을 먼저 건드리고 '옮겨 심을 필요 없다'로 풀었다"). 근거가 된 원문을 같이 적는다.
4. 첫 줄 꼴 — 첫 줄의 문장 틀(구체 낱말을 OO로 바꿔서).
5. 씨앗이 이미 말한 포인트 — 이 대본이 자랑한 것 전부, 한 줄에 하나씩 짧게.

출력은 JSON 객체 하나:
{"product": "제품", "tone": "반말|존댓말", "voice": "말하는 결 한 줄", "endings": ["~는데", ...], "openers": ["이게 말도 안 되는 게", ...],
 "beats": [{"name": "칸 이름", "does": "하는 일", "text": "원문"}],
 "hooked": [{"why": "무엇을 건드렸나", "quote": "근거 원문"}],
 "title_shape": "첫 줄 꼴", "said_points": ["...", "..."]}

[씨앗의 말]
%s"""

POINT_PROMPT = """한 제품으로 쇼핑 쇼츠 대본을 쓰려고 한다. 대본에 쓸 **포인트**를 꺼내라. 대본을 쓰는 게 아니다.

재료는 둘이다: ①씨앗 분석(터진 영상이 무엇으로 사람을 붙잡았나) ②같은 제품을 찍은 해외 영상들의 장면 태깅.

꺼낼 것 — 8~12개
- 팔릴 포인트 : 보는 사람이 "이건 사야겠다" 싶어지는 것. 기능 이름이 아니라 **그래서 뭐가 달라지나**로 적는다.
- 흥미로운 사실: 이 제품(종류)에 대해 "어 그래?" 싶은 것 — 왜 만들어졌나, 누가 쓰나, 어디서 화제인가, 원래 뭐였나.
- 뜻밖의 쓰임 : 원래 용도 말고 사람들이 쓰는 법.
- 비교        : 기존 방법·비싼 것과 견주면 무엇이 다른가.
- 사람 이야기 : 누가 왜 이걸 쓰게 됐나(장면에 사람이 보이면).

포인트마다
- text   포인트 한 줄
- hook   그 포인트를 **한마디 어그로**로(대본의 한 줄이 될 말, 20자 안팎)
- origin "씨앗"(씨앗 분석에 나옴) / "영상"(장면 태깅에 보임) / "일반지식"(둘 다에 없지만 이 제품 종류에 대해 널리 알려진 것)
         ★일반지식은 확실한 것만. 숫자·상표·나라·매출을 지어내지 마라. 애매하면 넣지 않는다.
- cuts   그 포인트를 **보여 줄 수 있는** 장면 번호들(아래 목록에 있는 번호만. 없으면 빈 배열)
- in_seed 씨앗이 이미 말한 포인트면 true

★씨앗에 없던 포인트(in_seed=false)를 5개 이상 찾아라 — 대본이 씨앗과 달라지는 곳이 여기다.

출력은 JSON 객체 하나: {"points": [{"kind": "...", "text": "...", "hook": "...", "origin": "...", "cuts": ["..."], "in_seed": false}]}

[제품] %s

[씨앗 분석]
홀린 요인: %s
씨앗이 이미 말한 포인트: %s

[해외 영상 장면 태깅 — 번호 | 역할 | 화면 | 용처 | 특징]
%s"""

WRITE_PROMPT = """너는 쇼핑 쇼츠 대본 작가다. 터진 영상(씨앗)의 **틀을 그대로 빌려**, 같은 제품의 **새 대본**을 쓴다.

원리
- 틀 = 씨앗의 칸 순서 · 말끝 · 말버릇 · 줄 길이. 이건 **그대로 따른다**(아래 [틀]).
- 내용 = [포인트]. 씨앗 문장을 옮기지 마라 — 같은 말을 또 하면 같은 영상이 된다.
- 씨앗이 사람을 붙잡은 방법([홀린 요인])을 **같은 자리에서 다시 일으켜라** — 같은 낱말이 아니라 같은 수법으로.
- 앞쪽 칸은 씨앗과 같은 포인트로 열어도 된다. **가운데부터 끝까지는 씨앗에 없던 포인트**(새)로 채운다 — 새 포인트를 %d개 이상 쓴다.
- 제품을 설명하지 말고 **쓰는 장면**을 말로 따라가라. 줄마다 그 줄에 붙일 장면(cuts)을 단다 — 화면에 없는 말은 길게 하지 마라.
- 훅(첫 줄)은 [첫 줄 꼴]의 OO 자리를 이 제품의 사람·물건으로 바꿔 새로 쓴다.
- 말투는 씨앗과 같게 하나로. 보는 사람에게 사라고 하지 마라(씨앗이 그렇게 끝나지 않는 한).
- 길이: 공백 빼고 %d~%d자.

출력은 JSON 객체 하나:
{"title": "첫 줄(훅)", "lines": [{"beat": "칸 이름(틀의 이름 그대로)", "text": "한 줄", "points": [포인트 번호], "cuts": ["장면 번호"]}]}
(title 은 lines 에 다시 넣지 않는다)

[제품] %s

[틀 — 씨앗의 칸 순서와 원문(원문은 모양만 보고 베끼지 마라)]
%s
말투: %s · %s
말끝: %s
말버릇: %s
[첫 줄 꼴] %s

[홀린 요인]
%s

[포인트 — 번호. (종류/어디서) 한 줄 — 어그로 한마디 | 붙일 장면]
%s
%s"""


RESEARCH_PROMPT = """한 제품으로 쇼핑 쇼츠 '썰' 대본을 쓰려고 한다. 이 제품(또는 이 제품 종류·브랜드)에 대해 **숨겨진 이야기**를 찾아라.
찾을 것(5~8개): 탄생 비화(누가 왜 만들었나) · 알려지지 않은 사실 · 원래 용도와 다른 뜻밖의 쓰임 · 사람 이야기(누가 어떻게 쓰다 퍼졌나) · 원조·비싼 것과의 관계 · 흔한 오해.
★검색으로 **확인한 것만** 적고, 항목마다 근거 출처(URL 또는 매체·페이지 이름)를 적어라. 확인 못 한 것은 적지 마라. 숫자·상표·나라는 출처에 있는 그대로.
출력은 JSON 객체 하나: {"facts": [{"kind": "탄생 비화|숨은 사실|뜻밖의 쓰임|사람 이야기|원조 관계|오해", "text": "한 줄", "source": "출처"}]}

[제품] %s
[영상에서 이미 본 것 — 겹치는 건 빼라] %s"""

STORY_PROMPT = """쇼핑 쇼츠 '썰' 대본의 **줄거리**를 짜라. 대본을 쓰는 게 아니다 — 누가, 무슨 일이, 어떻게 됐나를 정하는 단계다.

썰은 제품 설명이 아니라 **사람들에게 벌어진 일**이다. 원본 채널 39편의 썰은 이 다섯 꼴 중 하나였다:
  대체 탐정  : 비싼 원조 → 못 구하거나 아쉬움 → 포기 못 한 무리가 시행착오 끝에 이걸 찾아냄 → 원조에 갈 이유가 없어짐
  숨은 이유  : 다들 OO 때문에 사는 줄 알았는데 → 살펴보니 → 정작 꽂힌 이유는 따로 있었음
  원리       : 겉보기엔 말이 안 되는데 → 사실 기존 것은 이런 방식이라 단점이 있었고 → 이건 이렇게 해서 됨 → 덤
  역전       : 원래는 망하거나 무시당하던 것 → 누군가의 아이디어·집착 → 뒤집힘 → 지금은
  소동       : 뜻밖의 일(루머·오용·사건)이 벌어짐 → 사람들 반응 → 제조사 반응 → 그래도 계속

재료는 [포인트](영상에서 본 것)와 [숨겨진 이야기](조사한 것)다. **숨겨진 이야기가 있으면 그걸 사건의 중심에 둔다.**
선: 제품 사실(기능·숫자·상표·가격·효능)과 숨겨진 이야기는 재료에 있는 것만 쓴다. 사람과 사건의 **서술**(어떤 무리가 실험을 거듭했다, 사람들이 놀랐다)은 썰로 꾸며도 된다 — 단 꾸민 자리는 dramatized 에 적어라.

출력은 JSON 객체 하나:
{"type": "다섯 꼴 중 하나", "cast": "주인공 무리(별명으로, 예: 빵돌이들·러너들·자취생들)",
 "beats": [{"step": "계기|막힘|발견|반전|결과 중", "text": "그 단계에서 벌어지는 일 한두 문장(대본체 아님, 줄거리)", "uses": ["p3", "f1"]}],
 "dramatized": ["꾸민 서술 한 줄", ...]}
(uses 는 포인트 p번호·숨겨진 이야기 f번호)

[제품] %s
[씨앗이 사람을 붙잡은 방법 — 같은 수법을 쓴다] %s
[포인트]
%s
[숨겨진 이야기]
%s"""


def parse(raw):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.S)
    i = s.find("{")
    if i < 0:
        raise ValueError("응답에 JSON 객체가 없다")
    return json.JSONDecoder().raw_decode(s[i:])[0]


def _norm(t):
    return re.sub(r"[^가-힣A-Za-z0-9]", "", t or "")


def chars(t):
    return len(re.sub(r"\s", "", t or ""))


def gram_share(a, b, n=6):
    """a 의 n글자 조각 중 b 에도 있는 비율."""
    qa, qb = _norm(a), _norm(b)
    g = [qa[i:i + n] for i in range(max(0, len(qa) - n + 1))]
    return (sum(1 for x in g if x in qb) / len(g)) if g else 0.0


def _sentences(t):
    """받아쓰기엔 문장부호가 거의 없다 — 말끝(~음/~거/~다고/~는데/~요/~다) 뒤에서도 끊는다."""
    parts = re.split(r"[.!?\n]+|(?<=[음임됨함거요다])\s+(?=[가-힣])", t or "")
    return [p.strip() for p in parts if p and p.strip()]


def _ask(call, prompt, tries=2):
    err = ""
    for _ in range(tries):
        try:
            out = parse(call(prompt))
            if isinstance(out, dict):
                return out
            err = "JSON 객체가 아니다"
        except ValueError as e:
            err = str(e)
    raise ValueError(err)


def analyze_seed(seed_text, call):
    """① 씨앗의 말 → 틀 + 홀린 요인. 홀린 요인의 근거 인용이 씨앗에 없으면 그 요인은 버린다(지어낸 분석 방지)."""
    out = _ask(call, SEED_PROMPT % (seed_text or "").strip()[:2500])
    out["hooked"] = [h for h in (out.get("hooked") or []) if isinstance(h, dict) and (h.get("why") or "").strip()
                     and gram_share(h.get("quote") or "", seed_text, 4) >= 0.5]
    out["beats"] = [b for b in (out.get("beats") or []) if isinstance(b, dict) and (b.get("name") or "").strip()]
    return out


def scene_block(scenes):
    """scenes = [{"id": 장면 번호, "role": 역할, "desc": 화면, "use": 용처, "feats": [특징]}]"""
    return "\n".join("[%s] %s | %s | %s | %s" % (s.get("id"), s.get("role") or "", (s.get("desc") or "")[:80], (s.get("use") or "")[:70],
                                                " / ".join(str(x) for x in (s.get("feats") or [])[:2])) for s in scenes or [])


def mine_points(product, seed_an, scenes, call):
    """② 포인트 꺼내기. 코드가 손보는 것: 없는 장면 번호 제거 · '씨앗에 이미 있음'을 낱말로 한 번 더 확인 · 번호 매기기."""
    said = seed_an.get("said_points") or []
    out = _ask(call, POINT_PROMPT % (product, " / ".join(h["why"] for h in seed_an.get("hooked") or []) or "(없음)",
                                     " · ".join(said) or "(없음)", scene_block(scenes)))
    ids = {str(s.get("id")) for s in scenes or []}
    blob = " ".join(said + [b.get("text") or "" for b in seed_an.get("beats") or []])
    pts = []
    for p in out.get("points") or []:
        if not isinstance(p, dict) or not (p.get("text") or "").strip():
            continue
        p["cuts"] = [str(c) for c in (p.get("cuts") or []) if str(c) in ids]
        p["origin"] = p.get("origin") if p.get("origin") in ORIGINS else "영상"
        p["in_seed"] = bool(p.get("in_seed")) or gram_share(p["text"], blob, 3) > 0.5
        p["id"] = len(pts) + 1
        pts.append(p)
    return pts



def research(product, seen_points, call):
    """②-2 숨겨진 이야기 조사. call 은 **검색이 붙은** 호출기여야 한다(그냥 모델 지식이면 지어낸다). 출처 없는 항목은 버린다."""
    try:
        out = _ask(call, RESEARCH_PROMPT % (product, " · ".join(seen_points or [])[:600] or "(없음)"))
    except ValueError:
        return []
    facts = []
    for f in out.get("facts") or []:
        if isinstance(f, dict) and (f.get("text") or "").strip() and len((f.get("source") or "").strip()) >= 4:
            f["id"] = "f%d" % (len(facts) + 1)
            facts.append(f)
    return facts


def _facts_block(facts):
    return "\n".join("%s. (%s) %s — 출처: %s" % (f["id"], f.get("kind") or "", f["text"], f.get("source") or "") for f in facts) or "(없음)"


def build_story(product, seed_an, points, facts, call):
    """③-1 썰 짓기 — 포인트·숨겨진 이야기 → 줄거리(누가·무슨 일·어떻게). 재료 밖 사실을 쓴 단계는 uses 가 비어 걸러진다."""
    out = _ask(call, STORY_PROMPT % (product, " / ".join(h["why"] for h in seed_an.get("hooked") or []) or "(없음)",
                                     "\n".join("p%d. (%s) %s" % (p["id"], p.get("kind") or "", p["text"]) for p in points) or "(없음)", _facts_block(facts)))
    ids = {"p%d" % p["id"] for p in points} | {f["id"] for f in facts}
    beats = []
    for b in out.get("beats") or []:
        if isinstance(b, dict) and (b.get("text") or "").strip():
            b["uses"] = [u for u in (b.get("uses") or []) if u in ids]
            beats.append(b)
    return {"type": out.get("type") or "", "cast": out.get("cast") or "", "beats": beats, "dramatized": out.get("dramatized") or [],
            "uses_fact": any(u.startswith("f") for b in beats for u in b["uses"])}


def _story_block(story):
    if not story or not story.get("beats"):
        return ""
    rows = ["[줄거리 — 이 순서대로 쓴다. 주인공 무리: %s · 썰 꼴: %s]" % (story.get("cast") or "사람들", story.get("type") or "")]
    rows += ["%d. (%s) %s" % (i + 1, b.get("step") or "", b["text"]) for i, b in enumerate(story["beats"])]
    return "\n".join(rows) + "\n"


def _frame(seed_an):
    return "\n".join("%d. %s — %s\n     원문: %s" % (i + 1, b["name"], b.get("does") or "", (b.get("text") or "")[:120])
                     for i, b in enumerate(seed_an.get("beats") or []))


def _points_block(points):
    return "\n".join("%d. (%s/%s%s) %s — %s | 장면 %s" % (
        p["id"], p.get("kind") or "", p["origin"], "·씨앗이 이미 말함" if p["in_seed"] else "·새", p["text"], p.get("hook") or "",
        ",".join(p["cuts"]) or "없음") for p in points)


def problems(script, seed_text, seed_an, points, scenes):
    """④ 결과물 검사 → 다시 쓰라는 말 목록(없으면 [])."""
    bad = []
    lines = [L for L in (script.get("lines") or []) if (L.get("text") or "").strip()]
    if len(lines) < max(4, len(seed_an.get("beats") or []) - 2):
        bad.append("줄이 %d개뿐이다 — 틀의 칸을 빠뜨렸다" % len(lines))
    # ★문장 단위로 본다 — 한 줄에 두세 문장을 담으면 줄 전체 비율로는 베낀 문장이 묻힌다(1차 시험: 스티커 편 "하지만 일본의 집착은 여기서부터 시작됨"이 그대로 통과)
    for L in lines:
        for sent in _sentences(L["text"]):
            if len(_norm(sent)) >= 12 and gram_share(sent, seed_text) > COPY_SHARE:
                bad.append("«%s» — 씨앗 문장을 옮겼다. 내용을 새 포인트로 바꿔 새로 써라" % sent[:18])
    # ★첫 줄은 씨앗 첫 줄에서 낱말만 갈아 끼우면 안 된다(1차 시험 3/8건: "한국 주부"→"혼밥족", "일본 천재"→"시골 청년" — 베낀 데다 없는 사람을 지어냈다)
    first = (script.get("title") or (lines[0]["text"] if lines else "")).strip()
    seed_first = _sentences(seed_text)[0] if _sentences(seed_text) else ""
    if first and seed_first and gram_share(first, seed_first, 3) > COPY_SHARE:
        bad.append("첫 줄 «%s» — 씨앗 첫 줄에서 낱말만 바꿨다. [첫 줄 꼴]의 OO 자리는 [포인트]에 나온 사람·물건으로만 채우고 문장은 새로 써라" % first[:18])
    # ★숫자는 씨앗·장면·포인트에 나온 것만(1차 시험: "0.1초 만에"·"3초 만에"가 어디에도 없었다)
    known = set(re.findall(r"\d+(?:[.,]\d+)*", seed_text + " " + " ".join((sc.get("desc") or "") + " " + (sc.get("use") or "") + " " + " ".join(str(x) for x in sc.get("feats") or []) for sc in scenes or [])
                           + " " + " ".join(p["text"] for p in points if p["origin"] != "일반지식")))
    ghost_n = sorted({n for L in lines for n in re.findall(r"\d+(?:[.,]\d+)*", L["text"]) if n not in known})
    if ghost_n:
        bad.append("씨앗·장면에 없는 숫자를 썼다: %s — 빼거나 재료에 있는 숫자로" % ", ".join(ghost_n[:6]))
    ids = {str(s.get("id")) for s in scenes or []}
    ghost = sorted({str(c) for L in lines for c in (L.get("cuts") or []) if str(c) not in ids})
    if ghost:
        bad.append("없는 장면 번호를 달았다: %s" % ", ".join(ghost[:6]))
    by = {p["id"]: p for p in points}
    used_new = {i for L in lines for i in (L.get("points") or []) if i in by and not by[i]["in_seed"]}
    if len(used_new) < min(MIN_NEW_POINTS, sum(1 for p in points if not p["in_seed"])):
        bad.append("씨앗에 없던 포인트를 %d개밖에 안 썼다 — 가운데부터는 새 포인트로" % len(used_new))
    pol = sum(1 for L in lines if re.search(r"(요|니다|죠)[.!?~]*$", L["text"].strip()))
    if seed_an.get("tone") == "반말" and pol:
        bad.append("씨앗은 반말인데 존댓말 줄이 %d개 섞였다" % pol)
    if seed_an.get("tone") == "존댓말" and pol < len(lines) / 3:
        bad.append("씨앗은 존댓말인데 존댓말 줄이 %d개뿐이다" % pol)
    return bad


def write(product, seed_text, seed_an, points, scenes, call, *, story=None, facts=None, max_rewrites=1, log=print):
    """③ 쓰기 → (script, 남은 문제, 시도 수). 길이는 씨앗 길이를 따른다(0.9~1.4배, 최소 150자)."""
    n = max(150, chars(seed_text))
    lo, hi = int(n * 0.9), int(n * 1.4)
    need_new = min(MIN_NEW_POINTS + 1, sum(1 for p in points if not p["in_seed"]))
    base = WRITE_PROMPT % (need_new, lo, hi, product, _frame(seed_an), seed_an.get("tone") or "", seed_an.get("voice") or "",
                           " · ".join(seed_an.get("endings") or []), " · ".join(seed_an.get("openers") or []) or "(없음)",
                           seed_an.get("title_shape") or "", "\n".join("- %s" % h["why"] for h in seed_an.get("hooked") or []) or "(없음)",
                           _points_block(points) + ("\n[숨겨진 이야기 — 출처 있는 것만]\n" + _facts_block(facts) if facts else ""), "")
    if story:
        base = base.replace("[제품] %s" % product, _story_block(story) + "\n[제품] %s" % product, 1)
    fb, last = "", None
    for attempt in range(max_rewrites + 1):
        script = _ask(call, base + fb)
        bad = problems(script, seed_text, seed_an, points, scenes)
        log("[seedflow] 시도 %d: %d줄 %d자, 문제 %d" % (attempt + 1, len(script.get("lines") or []),
                                                 sum(chars(L.get("text")) for L in script.get("lines") or []), len(bad)))
        last = (script, bad, attempt + 1)
        if not bad:
            break
        fb = "\n[다시 써라 — 방금 쓴 것의 문제]\n" + "\n".join("- " + b for b in bad) + "\n방금 쓴 것:\n" + json.dumps(script, ensure_ascii=False)[:3000]
    return last


def run(product, seed_text, scenes, call, *, search_call=None, seed_an=None, log=print):
    """단계를 차례로: 씨앗 분석 → 포인트 → (검색 호출기가 있으면) 숨겨진 이야기 조사 → 썰 짓기 → 쓰기.
    → {"seed", "points", "facts", "story", "script", "problems", "attempts"}"""
    seed_an = seed_an or analyze_seed(seed_text, call)
    product = product or seed_an.get("product") or ""
    points = mine_points(product, seed_an, scenes, call)
    facts = research(product, [p["text"] for p in points], search_call) if search_call else []
    story = build_story(product, seed_an, points, facts, call)
    script, bad, n = write(product, seed_text, seed_an, points, scenes, call, story=story, facts=facts, log=log)
    return {"seed": seed_an, "points": points, "facts": facts, "story": story, "script": script, "problems": bad, "attempts": n}
