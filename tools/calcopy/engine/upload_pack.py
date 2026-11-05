# -*- coding: utf-8 -*-
"""업로드 글(제목·설명·해시태그) 검사 한 곳 — apply-09(관제 319, 11-06 · Jev 해결 0.73·위험 0.44·신뢰 0.99).
판단 주인: 미끼 낱말 금지 목록 BAIT 한 곳 + 판 값 해시태그 개수(판 칸 upload.hashtags {min,max}, 없으면 기본 HASHTAGS).
kal.py step_apply 가 _kal/업로드글.txt 가 있으면 부르고, 걸리면 waiting_human.
"""
from __future__ import annotations

import re

BAIT = ("충격", "경악", "100%", "무조건", "역대급 공개", "클릭", "꼭 보세요", "안 보면 손해", "실화냐", "소름 돋는 진실")   # 회원 값(J 미끼 제목·과장 단정) — 낱말 단위
HASHTAGS = {"min": 1, "max": 5}                                                                                   # 쇼츠 해시태그 기본 범위(판 칸이 있으면 그 값)


def check(txt: str, rule: dict | None = None) -> list[str]:
    """업로드 글 → 걸린 것 목록(빈 목록 = 통과)."""
    rule = rule or {}
    bad = [f"미끼 낱말 '{w}'" for w in (rule.get("bait") or BAIT) if w in (txt or "")]
    tags = re.findall(r"#[^\s#]+", txt or "")
    lim = {**HASHTAGS, **(rule.get("hashtags") or {})}
    if not lim["min"] <= len(tags) <= lim["max"]:
        bad.append(f"해시태그 {len(tags)}개 — 판 범위 {lim['min']}~{lim['max']}")
    dup = sorted({t for t in tags if tags.count(t) > 1})
    if dup:
        bad.append(f"해시태그 겹침 {dup}")
    return bad
