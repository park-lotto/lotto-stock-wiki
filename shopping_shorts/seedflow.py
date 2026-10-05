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


def write(product, seed_text, seed_an, points, scenes, call, *, max_rewrites=1, log=print):
    """③ 쓰기 → (script, 남은 문제, 시도 수). 길이는 씨앗 길이를 따른다(0.9~1.4배, 최소 150자)."""
    n = max(150, chars(seed_text))
    lo, hi = int(n * 0.9), int(n * 1.4)
    need_new = min(MIN_NEW_POINTS + 1, sum(1 for p in points if not p["in_seed"]))
    base = WRITE_PROMPT % (need_new, lo, hi, product, _frame(seed_an), seed_an.get("tone") or "", seed_an.get("voice") or "",
                           " · ".join(seed_an.get("endings") or []), " · ".join(seed_an.get("openers") or []) or "(없음)",
                           seed_an.get("title_shape") or "", "\n".join("- %s" % h["why"] for h in seed_an.get("hooked") or []) or "(없음)",
                           _points_block(points), "")
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


def run(product, seed_text, scenes, call, *, log=print):
    """세 단계를 차례로. → {"seed": 분석, "points": 포인트, "script": 대본, "problems": 남은 문제, "attempts": n}"""
    seed_an = analyze_seed(seed_text, call)
    points = mine_points(product or seed_an.get("product") or "", seed_an, scenes, call)
    script, bad, n = write(product or seed_an.get("product") or "", seed_text, seed_an, points, scenes, call, log=log)
    return {"seed": seed_an, "points": points, "script": script, "problems": bad, "attempts": n}
