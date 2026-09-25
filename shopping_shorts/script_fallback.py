# -*- coding: utf-8 -*-
"""AI 생성·검사 실패 시 원본 관측만으로 만드는 마지막 대본 출구.

★2026-09-25 사장님 제보(work 4bd606509402)로 좁혔다: Gemini 503 때 이 출구가 **번역 안 된 중국어
  전사와 단어 중간에서 잘린 333자 문장**을 대본 칸에 그대로 올렸다. "0안 금지"(09-16)는 유지하되
  0안보다 나쁜 안은 내보내지 않는다 — 쓸 수 있는 한국어 관측이 없으면 None을 돌려주고 호출부가
  이유(과부하·한도)를 말한다.
"""
import re


_ALLOWED_KINDS = {"visual", "transcript", "product_fact"}
_MAX_CHARS = 120           # 한 칸 상한 — 넘으면 **어절 경계**에서 자른다(글자 중간 금지)
_MIN_KO_RATIO = 0.5        # 알파벳 글자 중 한글 비율 — 못 넘으면 번역 안 된 외국어 전사로 본다
_HANGUL = re.compile(r"[가-힣]")


def _src_seg(evidence_id):
    parts = str(evidence_id or "").split(":")
    return parts[-2] if len(parts) >= 4 and parts[0] == "scene" else ""


def is_korean(text):
    """한글이 있고, 알파벳 글자 중 한글이 절반 이상인가(외국어 원문 전사를 걸러낸다)."""
    alpha = [ch for ch in str(text or "") if ch.isalpha()]
    if not alpha:
        return False
    ko = sum(1 for ch in alpha if _HANGUL.match(ch))
    return ko / len(alpha) >= _MIN_KO_RATIO


def canonical_observations(evidence, limit=8):
    """검증 근거의 원문 발화·관측만 짧은 중복 없는 **한국어** 문장으로 돌려준다.

    ★_MAX_CHARS를 넘는 문장은 **버린다**(자르지 않는다). 구두점 없는 333자 전사를 160자에서 잘라
      '…완벽하게 집'을 만든 게 실사고고, 어절 경계에서 잘라도 '…개발된 이 제품이'처럼 말이 안 끝난다
      (라이브 재료로 실측). 대사로 못 쓰는 줄은 없는 게 낫다 — 장면 관측(visual)이 남는다.
    ★줄바꿈으로 먼저 가른다 — 장면 관측은 '동작\\n변화' 두 줄이라 공백으로 뭉치면 한 줄이 된다.
    """
    out, seen = [], set()
    for item in (evidence or {}).get("items") or []:
        if not isinstance(item, dict) or item.get("kind") not in _ALLOWED_KINDS:
            continue
        pieces = []
        for line in re.split(r"\n+", str(item.get("text") or "")):
            line = re.sub(r"\s+", " ", line).strip()
            pieces.extend(re.split(r"(?<=[.!?。！？])\s+", line))
        for sentence in pieces:
            text = sentence.strip(" -\t")
            if not is_korean(text) or len(text) > _MAX_CHARS:
                continue
            key = re.sub(r"\s+", "", text)
            if not text or key in seen:
                continue
            seen.add(key)
            out.append({"text": text, "src_seg": _src_seg(item.get("evidence_id"))})
            if len(out) >= limit:
                return out
    return out


def humanize_reason(detail):
    """모델 오류 원문(ServerError: 503 …)을 사용자가 읽을 문장으로. 모르는 건 그대로 둔다.

    ★여기 한 곳에서만 옮긴다(0순위-B) — app._gen_fail_message(0안일 때)와 장면근거 안의
      fallback_reason(1안일 때)이 같은 말을 해야 한다.
    """
    d = str(detail or "")
    if "spending cap" in d or "spend cap" in d:
        return "AI 키가 월 지출 한도에 걸렸습니다 — 관리페이지에서 키를 확인해 주세요"
    if "503" in d or "UNAVAILABLE" in d or "high demand" in d:
        return "AI 서버가 잠시 과부하입니다(503) — 1~2분 뒤 '다시 만들기'를 눌러 주세요"
    if "429" in d or "RESOURCE_EXHAUSTED" in d:
        return "AI 호출이 한도에 걸렸습니다(429) — 잠시 후 다시 시도해 주세요"
    return d


def _keyword(product):
    words = re.findall(r"[0-9A-Za-z가-힣]+", str(product or ""))
    return (words[-1] if words else "제품")[:6]


def _assign_roles(rows, roles):
    roles = [str(role) for role in (roles or []) if str(role).strip()]
    beats = []
    for i, row in enumerate(rows):
        if i == 0:
            role = roles[0] if roles else "hook"
        elif i == len(rows) - 1:
            role = roles[-1] if len(roles) > 1 else "cta"
        elif i < len(roles) - 1:
            role = roles[i]
        else:
            role = "body"
        seg = row.get("src_seg") or ""
        beats.append({"role": role, "text": row["text"], "src_seg": seg,
                      "src_segs": [seg] if seg else []})
    return beats


def build_grounded_fallback(product, evidence, style=None, reason=""):
    """스타일 결과가 0개일 때 반환 가능한 장면 근거 대본 한 안.

    ★쓸 수 있는 한국어 관측이 하나도 없으면 **None** — 제품명·CTA만 남은 두 줄이나 외국어
      전사를 대본이라고 내보내지 않는다. 호출부는 None을 빈 결과로 다루고 이유를 말한다.
    """
    product = str(product or "").strip() or "영상 속 제품"
    roles = list((style or {}).get("beat_roles") or [])
    max_observations = max(1, len(roles) - 2) if roles else 4
    observations = canonical_observations(evidence, limit=max_observations)
    if not observations:
        return None
    reason = humanize_reason(reason)
    rows = [{"text": f"이 영상에서 확인한 제품은 {product}입니다.", "src_seg": ""}]
    rows.extend({"text": "영상에서는 " + row["text"], "src_seg": row["src_seg"]}
                for row in observations)
    rows.append({"text": f"제품 정보가 더 궁금하다면 댓글에 '{_keyword(product)}' 남겨주세요.",
                 "src_seg": ""})
    beats = _assign_roles(rows, roles)
    script = "\n".join(row["text"] for row in beats)
    return {
        "style_id": (style or {}).get("id"), "style_name": (style or {}).get("name"),
        "beats": beats, "script": script, "hook": beats[0]["text"],
        "checks": [{"name": "자동 복구", "ok": False,
                    "detail": reason or "장면 근거 대본으로 복구했습니다"}],
        "passed": False, "needs_review": True,
        "fallback_reason": reason or "생성 결과를 장면 근거 대본으로 복구했습니다",
        "made_by": "장면근거", "tries": [],
    }
