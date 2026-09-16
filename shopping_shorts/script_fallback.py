# -*- coding: utf-8 -*-
"""AI 생성·검사 실패 시 원본 관측만으로 만드는 마지막 대본 출구."""
import re


_ALLOWED_KINDS = {"visual", "transcript", "product_fact"}


def _src_seg(evidence_id):
    parts = str(evidence_id or "").split(":")
    return parts[-2] if len(parts) >= 4 and parts[0] == "scene" else ""


def canonical_observations(evidence, limit=8):
    """검증 근거의 원문 발화·관측만 짧은 중복 없는 문장으로 돌려준다."""
    out, seen = [], set()
    for item in (evidence or {}).get("items") or []:
        if not isinstance(item, dict) or item.get("kind") not in _ALLOWED_KINDS:
            continue
        raw = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        for sentence in re.split(r"(?<=[.!?。！？])\s+|\n+", raw):
            text = sentence.strip(" -\t")[:160]
            key = re.sub(r"\s+", "", text)
            if not text or key in seen:
                continue
            seen.add(key)
            out.append({"text": text, "src_seg": _src_seg(item.get("evidence_id"))})
            if len(out) >= limit:
                return out
    return out


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
    """스타일 결과가 0개일 때도 반환 가능한 장면 근거 대본 한 안."""
    product = str(product or "").strip() or "영상 속 제품"
    roles = list((style or {}).get("beat_roles") or [])
    max_observations = max(1, len(roles) - 2) if roles else 4
    observations = canonical_observations(evidence, limit=max_observations)
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
