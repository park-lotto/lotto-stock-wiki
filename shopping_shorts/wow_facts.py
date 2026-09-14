# -*- coding: utf-8 -*-
"""제품 카테고리 → **영상 밖의 신기한 정보**(wow_facts) 웹 보강 (2026-09-09).

## 왜 이 모듈이 필요한가 — 사장님이 짚은 빈 자리

사장님이 보여준 방식(유튜브 H3UG7cY-fTQ 21~26분)은 노가다 3단계였다:

    ① 영상 → 제품명·특징·타임코드 대본        ← 우리도 오늘 붙였다(insta_facts 프레임 입력)
    ② "이 아이템 관련 **신기한 정보**를 더 찾아줘"  ← ★이 모듈. 우리에겐 아예 없었다
    ③ 그걸로 대본                              ← 우리도 있다(스파인·script_gate)

②가 만든 문장이 그 대본의 알맹이였다:
    "소리를 빛처럼 귓구멍에만 쏘아주는 지향성 기술이라 옆 사람도 거의 못 듣는다는 거"
    "예전 골전도는 뼈를 직접 때려서 오래 끼면 멀미나 두통이 왔는데"

②가 없으면 대본은 **화면에 이미 보이는 것만 다시 말한다**. 시청자가 눈으로 본 걸
귀로 또 듣는다 — 사장님 말로 "사람들이 보게 해야 할 이유가 없어"가 그 상태다.
실측(2026-09-09): 대본 경로 전체에 웹검색 grounding이 **한 줄도 없었다**.

## 어디서 갈리나 (0순위-B — 다른 재료 모듈과 겹치지 않는다)

    product_facts : 쿠팡 상세·리뷰      — 이 **상품**이 왜 좋은가
    insta_facts   : 영상 전사 + 화면    — 이 **영상**이 보여준 것
    sul_facts     : 유튜브 썰 자막      — 원래 용도 / 엉뚱한 사용처
    wow_facts     : 웹                  — 이 **카테고리**에 대해 영상 밖에 있는 지식  ← 여기

앞의 셋은 전부 "영상·상품 안"을 본다. 이 모듈만 밖을 본다. 그래서 따로다.

## 지켜야 할 것

★**fail-open** — 못 찾으면 []. 대본은 종전대로 나온다(회귀 0).
★**캐시 필수** — 실측에서 키 4개가 연속 429였다. 카테고리 단위로 캐시하면
  같은 종류 제품이 다시 와도 안 때린다(제품명이 아니라 **카테고리**로 캐시하는 이유).
★**지어낸 사실은 대본에 박히면 거짓말이 된다** — 웹 grounding을 켜서 묻고,
  응답 metadata가 그 훅 구간과 실제 웹 URL을 연결한 항목만 쓴다. 모델이 적은 `why`는
  설명일 뿐 검증 근거가 아니다.
"""
import json
import re
from urllib.parse import urlparse

_MODEL = "gemini-3.1-flash-lite"
CACHE_VERSION = 2

# 몇 개를 받나. 3개면 대본 한 편에서 1~2개를 쓰고도 고를 여지가 남는다.
WOW_N = 3

# 키를 최대 몇 번까지 돌려볼지. 살아있는 키 수만큼 돌되 이 값을 넘지 않는다 —
# 키가 25개여도 이 한 단계가 대본을 그만큼 붙잡으면 안 된다.
_MAX_TRIES = 20

# ★블록의 머리말. 게이트가 "이 대본이 이 재료를 실제로 썼나"를 판정할 때 이 표식으로
#   블록을 찾는다 — 문자열을 두 곳에 적으면 한쪽만 고쳐져 검사가 조용히 죽는다(0순위-B).
WOW_MARK = "[검증된 영상 밖 정보"
WOW_END = "[/검증된 영상 밖 정보]"

WOW_PROMPT = """'{subject}' 제품으로 한국어 쇼핑 숏폼을 만든다.

이 **카테고리**에 대해 시청자가 모르는 신기한 사실 {n}개를 웹에서 찾아라.

★스펙 나열은 쓸모없다 — 그건 화면에 이미 보인다. 시청자가 듣는 순간
  "어? 그래?" 하는 것만 골라라: 작동 **원리**, 옛날 방식과의 **비교**,
  의외의 **역사**, 흔한 **오해를 깨는 사실**.
★영상에 안 나온 지식이어야 한다. 화면에 보이는 걸 다시 말하면 실패다.
★한국어로. 대본 문장에 그대로 끼울 수 있게 **입말**로 써라.
★확인 안 되는 건 넣지 마라. {n}개를 못 채우면 적게 줘도 된다.
★검색 결과가 직접 뒷받침하는 범위만 써라. 카테고리의 일반 원리를 이 특정 제품의
  효능으로 바꾸거나, 출처에 없는 원인·효과·수치·절대 표현을 덧붙이지 마라.

JSON 배열만 출력하라. 다른 말 붙이지 마라:
[{{"hook": "듣는 순간 어? 하는 한 줄", "why": "왜 그런지 한두 줄"}}]"""


def _say(log, msg):
    try:
        log(msg)
    except Exception:      # noqa: BLE001 — 로그가 재료 추출을 막지 않는다
        pass


def _parse(text):
    """모델 텍스트를 파싱만 한다. 이 결과는 아직 사실로 인정하면 안 된다."""
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for x in data if isinstance(data, list) else []:
        if not isinstance(x, dict):
            continue
        hook = str(x.get("hook") or "").strip()
        why = str(x.get("why") or "").strip()
        if hook:
            out.append({"hook": hook, "why": why})
    return out[:WOW_N]


def _get(obj, name, default=None):
    """SDK 객체와 테스트용 dict를 같은 방식으로 읽는다."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _valid_web_source(chunk):
    web = _get(chunk, "web")
    uri = str(_get(web, "uri", "") or "").strip() if web else ""
    try:
        parsed = urlparse(uri)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return {"title": str(_get(web, "title", "") or "").strip(), "url": uri}


def _value_byte_spans(text, value):
    """JSON 원문 안의 값 위치. 따옴표 등이 escape된 출력도 찾는다."""
    forms = [value, json.dumps(value, ensure_ascii=False)[1:-1]]
    spans = []
    for form in dict.fromkeys(forms):
        at = 0
        while text and form:
            pos = text.find(form, at)
            if pos < 0:
                break
            start = len(text[:pos].encode("utf-8"))
            end = start + len(form.encode("utf-8"))
            found = (start, end, form)
            if found not in spans:
                spans.append(found)
            at = pos + len(form)
    return spans


def _fully_covered(start, end, intervals):
    cursor = start
    for left, right in sorted(intervals):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return cursor >= end


def _grounded_claim(response, value):
    """첫 후보에서 value 전체를 URL support들이 빈틈없이 덮으면 provenance를 반환한다."""
    candidates = list(_get(response, "candidates", []) or [])
    if not candidates:
        return None
    # resp.text는 SDK의 첫 후보 텍스트다. 다른 후보의 support로 첫 후보 주장을
    # 검증하면 서로 관계없는 결과를 섞게 되므로 첫 후보만 본다.
    candidate = candidates[0]
    metadata = _get(candidate, "grounding_metadata")
    chunks = list(_get(metadata, "grounding_chunks", []) or []) if metadata else []
    supports = list(_get(metadata, "grounding_supports", []) or []) if metadata else []
    parts = list(_get(_get(candidate, "content"), "parts", []) or [])
    for part_index, part in enumerate(parts):
        part_text = str(_get(part, "text", "") or "")
        raw = part_text.encode("utf-8")
        for claim_start, claim_end, grounded_text in _value_byte_spans(part_text, value):
            evidence = []
            for support in supports:
                segment = _get(support, "segment")
                if not segment:
                    continue
                try:
                    seg_part = int(_get(segment, "part_index", 0) or 0)
                    seg_start = int(_get(segment, "start_index"))
                    seg_end = int(_get(segment, "end_index"))
                except (TypeError, ValueError):
                    continue
                if (seg_part != part_index or seg_start < 0 or seg_end <= seg_start
                        or seg_end > len(raw)):
                    continue
                sources = []
                for index in (_get(support, "grounding_chunk_indices", []) or []):
                    try:
                        index = int(index)
                        source = _valid_web_source(chunks[index]) if index >= 0 else None
                    except (IndexError, TypeError, ValueError):
                        source = None
                    if source and source not in sources:
                        sources.append(source)
                left, right = max(seg_start, claim_start), min(seg_end, claim_end)
                if not sources or right <= left:
                    continue
                clipped = raw[left:right].decode("utf-8")
                evidence.append({
                    "start": left - claim_start,
                    "end": right - claim_start,
                    "text": clipped,
                    "segment_text": str(_get(segment, "text", "") or ""),
                    "sources": sources,
                })
            if _fully_covered(0, claim_end - claim_start,
                              [(e["start"], e["end"]) for e in evidence]):
                sources = []
                for entry in evidence:
                    for source in entry["sources"]:
                        if source not in sources:
                            sources.append(source)
                return {"grounded_text": grounded_text, "supports": evidence,
                        "sources": sources}
    return None


def _verified_from_response(response):
    """모델 JSON 중 Google metadata가 해당 hook에 직접 연결한 항목만 승격한다."""
    text = str(_get(response, "text", "") or "")
    out = []
    for item in _parse(text):
        grounding = _grounded_claim(response, item["hook"])
        if grounding:
            why_grounding = _grounded_claim(response, item["why"]) if item["why"] else None
            out.append({"hook": item["hook"],
                        "why": item["why"] if why_grounding else "",
                        "sources": grounding["sources"],
                        "grounding": grounding,
                        **({"why_grounding": why_grounding} if why_grounding else {})})
    return out[:WOW_N]


def _validated_grounding(value, grounding):
    """캐시에 보존된 support 범위·텍스트·URL이 여전히 서로 맞는지 검사한다."""
    if not isinstance(grounding, dict):
        return None
    grounded_text = str(grounding.get("grounded_text") or "")
    allowed = {value, json.dumps(value, ensure_ascii=False)[1:-1]}
    if not value or grounded_text not in allowed:
        return None
    raw = grounded_text.encode("utf-8")
    evidence, sources = [], []
    for entry in (grounding.get("supports") or []):
        if not isinstance(entry, dict):
            continue
        try:
            start, end = int(entry.get("start")), int(entry.get("end"))
        except (TypeError, ValueError):
            continue
        if start < 0 or end <= start or end > len(raw):
            continue
        try:
            expected = raw[start:end].decode("utf-8")
        except UnicodeDecodeError:
            continue
        if str(entry.get("text") or "") != expected:
            continue
        clean_sources = []
        for source in (entry.get("sources") or []):
            if not isinstance(source, dict):
                continue
            clean = _valid_web_source({"web": {
                "uri": source.get("url", ""), "title": source.get("title", "")
            }})
            if clean and clean not in clean_sources:
                clean_sources.append(clean)
            if clean and clean not in sources:
                sources.append(clean)
        if clean_sources:
            evidence.append({**entry, "start": start, "end": end,
                             "text": expected, "sources": clean_sources})
    if not _fully_covered(0, len(raw), [(e["start"], e["end"]) for e in evidence]):
        return None
    return {"grounded_text": grounded_text, "supports": evidence, "sources": sources}


def verified_items(wows, max_items=WOW_N):
    """캐시·호출 결과 공용 검증기. 유효한 URL provenance가 있는 항목만 반환한다."""
    out = []
    for item in (wows or []):
        if not isinstance(item, dict):
            continue
        hook = str(item.get("hook") or "").strip()
        grounding = _validated_grounding(hook, item.get("grounding"))
        if not grounding:
            continue
        why = str(item.get("why") or "").strip()
        why_grounding = _validated_grounding(why, item.get("why_grounding")) if why else None
        clean = {"hook": hook,
                 "why": why if why_grounding else "",
                 "sources": grounding["sources"], "grounding": grounding}
        if why_grounding:
            clean["why_grounding"] = why_grounding
        out.append(clean)
        if len(out) >= max_items:
            break
    return out


def find(subject, *, n=WOW_N, log=print, _call=None):
    """제품·카테고리 이름 → [{hook, why, sources}]. 못 찾으면 [](예외 없음).

    _call은 테스트 주입용 — (prompt) -> SDK 응답과 같은 객체. 텍스트만 주면
    grounding 연결을 확인할 수 없으므로 빈 결과다.
    """
    subject = (subject or "").strip()
    if not subject:
        return []
    prompt = WOW_PROMPT.format(subject=subject, n=n)
    if _call is not None:
        try:
            return _verified_from_response(_call(prompt))
        except Exception as e:      # noqa: BLE001 — 주입 호출이 죽어도 대본은 나온다
            _say(log, "[wow_facts] 주입 호출 실패: %s" % str(e)[:100])
            return []

    try:
        from shopping_shorts import video_analysis, comment_gen
        from google.genai import types
    except Exception as e:          # noqa: BLE001
        _say(log, "[wow_facts] 모듈 import 실패 — %s" % str(e)[:100])
        return []

    # ★키를 **넉넉히** 돌린다(2026-09-09 사장님: "키배치를 여유있게 하는 걸로 해").
    #   실측에서 4개 연속 429였고 5번째에 성공했다 — 6회로 묶으면 키가 붐비는 시간엔
    #   그대로 빈손이 된다. 그래서 **살아있는 키 수만큼** 돈다(한 바퀴 = 모두에게 한 번씩).
    #   상한을 두는 이유: 키가 아주 많아도 이 한 단계가 대본 생성을 오래 붙잡으면
    #   그 기다림이 그대로 사장님 몫이 된다.
    try:
        _n_keys = len(comment_gen._live_key_indices() or [])
    except Exception:      # noqa: BLE001 — 키 수를 못 세도 최소한은 돈다
        _n_keys = 0
    tries = max(6, min(_n_keys or 6, _MAX_TRIES))
    last = ""
    for i in range(tries):
        try:
            key, _idx = comment_gen._next_live_key_and_idx()
            if key is None:
                _say(log, "[wow_facts] 살아있는 키 없음")
                return []
            resp = video_analysis._client_for_key(key).models.generate_content(
                model=_MODEL, contents=[prompt],
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]))
            got = _verified_from_response(resp)
            if got:
                _say(log, "[wow_facts] '%s' → %d개 (키 %d번째 시도)" % (subject, len(got), i + 1))
                return got
            # API는 성공했지만 검색 metadata가 이 주장 전체를 입증하지 않았다. 다른 키로
            # 같은 질문을 20번 반복해도 쿼터와 대기시간만 든다. 키 순회는 호출 실패 때만 한다.
            _say(log, "[wow_facts] '%s' → 검증 가능한 웹 근거 없음" % subject)
            return []
        except Exception as e:      # noqa: BLE001 — 웹 보강 실패가 대본을 막으면 안 된다
            last = "%s: %s" % (type(e).__name__, str(e)[:70])
    _say(log, "[wow_facts] '%s' 못 찾음 — 키 %d회 시도, 마지막: %s"
              % (subject, tries, last))
    return []


def wow_prompt_block(wows, max_items=WOW_N):
    """재료 → 대본 프롬프트에 붙일 블록. 비면 ''(호출부는 빈 문자열이면 회귀 0).

    ★product_facts.prompt_block·insta_facts.insta_prompt_block과 같은 규약이다.
    """
    wows = verified_items(wows, max_items=max_items)
    if not wows:
        return ""
    lines = [WOW_MARK + " — 시청자가 모르는 것]",
             "★이 중 **하나만** 골라 대본 가운데에 넣어라. 나열하지 마라.",
             "★화면에 안 보이는 얘기다 — 그래서 시청자가 끝까지 보는 이유가 된다."]
    for w in wows:
        sources = w.get("sources") or []
        source_text = " / ".join("%s %s" %
                                 (" ".join(str(s.get("title", "")).split()), s.get("url", ""))
                                 for s in sources[:2])
        hook = " ".join(str(w.get("hook", "")).split())
        why = " ".join(str(w.get("why", "")).split())
        extra = (" / 설명: %s" % why) if why else ""
        lines.append("- %s (근거: %s%s)" %
                     (hook, source_text.strip(), extra))
    lines.append(WOW_END)
    return "\n".join(lines) + "\n"
