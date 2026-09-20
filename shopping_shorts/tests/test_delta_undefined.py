# -*- coding: utf-8 -*-
"""조회수 옆 '+undefined' — 수집이 delta를 안 채워서 난 것(2026-08-31 사장님 제보).

## 무엇이 보였나
카드의 조회수 옆에 증가분이 `+undefined`로 찍혔다. 화면 코드가
`${i.is_new?'신규':'+'+i.delta}`인데, delta가 없으면 문자열 결합이 그대로
"+undefined"가 된다(자바스크립트는 조용히 통과시킨다).

## 왜 어떤 플랫폼만 그런가 (서버 실측 2026-08-31)
| 플랫폼 | delta 키 없음 |
|---|---|
| youtube | 0 / 8,000 |
| tiktok | 0 / 8 |
| **naverclip** | **4,492 / 4,492** |
| **pinterest** | **2,259 / 2,259** |

유튜브·인스타·틱톡은 `ranking.py`를 거치며 `platform_snapshots`(직전 수집의
조회수)와 비교해 delta·is_new를 채운다. 네이버클립·핀터레스트는 **그 경로를
안 타고** 바로 저장해서 두 키가 통째로 없다.

## 처방 (두 겹)
1. 수집이 delta·is_new를 채운다 — snapshot 기반, 다른 플랫폼과 같은 규칙.
2. 화면은 그래도 방어한다 — 다음에 또 새 플랫폼이 붙어도 undefined가 안 뜨게.
   (수집만 고치면 옛 저장분 4,492건은 그대로 undefined다)
"""
import json
import re
from pathlib import Path

import pytest

from shopping_shorts import ranking


_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"


# ── ① 수집이 delta를 채우는가 ──────────────────────────────────────────
def test_attach_delta_marks_new_items():
    """처음 보는 영상은 is_new=True, delta=조회수 전부."""
    rows = ranking.attach_delta(
        [{"shortcode": "A", "views": 100}, {"shortcode": "B", "views": 5}],
        prev_base={})
    assert rows[0]["is_new"] is True and rows[0]["delta"] == 100
    assert rows[1]["is_new"] is True and rows[1]["delta"] == 5


def test_attach_delta_computes_increase():
    """두 번째 수집부터는 직전 대비 증가분."""
    rows = ranking.attach_delta(
        [{"shortcode": "A", "views": 150}, {"shortcode": "B", "views": 5}],
        prev_base={"A": 100, "B": 5})
    assert rows[0]["is_new"] is False and rows[0]["delta"] == 50
    assert rows[1]["is_new"] is False and rows[1]["delta"] == 0


def test_attach_delta_never_negative():
    """조회수가 줄어 보여도(집계 보정) 음수 증가분을 만들지 않는다."""
    rows = ranking.attach_delta([{"shortcode": "A", "views": 80}],
                                prev_base={"A": 100})
    assert rows[0]["delta"] == 0


def test_attach_delta_handles_missing_views():
    """조회수가 없는 소스(쓰레드 등)에서도 키는 채워져야 한다 — 없으면 undefined다."""
    rows = ranking.attach_delta([{"shortcode": "A"}], prev_base={})
    assert rows[0]["delta"] == 0 and rows[0]["is_new"] is True


def test_attach_delta_keeps_other_fields():
    rows = ranking.attach_delta([{"shortcode": "A", "views": 9, "name": "채널"}],
                                prev_base={})
    assert rows[0]["name"] == "채널" and rows[0]["views"] == 9


# ── ② 화면이 방어하는가 ────────────────────────────────────────────────
def _card_block():
    src = _HTML.read_text(encoding="utf-8")
    i = src.index('<div class="rank">')
    return src[i:i + 4000]


def test_screen_never_prints_plus_undefined():
    """★`'+'+i.delta`를 **그대로** 쓰면 안 된다 — delta가 없으면 '+undefined'다.

    새 플랫폼이 붙을 때마다 같은 사고가 난다(핀터레스트·네이버클립 둘 다 겪었다).
    화면에서 한 번 막아 두면 수집이 빠뜨려도 사용자에겐 안 보인다.
    """
    block = _card_block()
    assert "'+'+i.delta" not in block, "delta를 그대로 이어붙이고 있다(+undefined 위험)"
    assert "_delta(" in block, "delta 표시는 헬퍼(_delta)를 거쳐야 한다"


def test_delta_helper_exists_and_guards():
    """헬퍼가 없는 값·0을 어떻게 다루는지 소스로 확인한다."""
    src = _HTML.read_text(encoding="utf-8")
    m = re.search(r"function _delta\(([^)]*)\)\s*\{(.+?)\n\}", src, re.S)
    assert m, "_delta 헬퍼가 없다"
    body = m.group(2)
    # 값이 없을 때 빈 문자열로 빠지는 분기가 있어야 한다
    assert "undefined" in body or "== null" in body or "!=null" in body, \
        "없는 값을 거르는 분기가 없다"


def test_comments_render_is_guarded():
    """★`i.comments.toLocaleString()`은 comments가 없으면 **카드가 통째로 죽는다**.

    조회수처럼 조용히 이상해지는 게 아니라 render가 예외로 멈춰 화면이 빈다
    (메모리 reference_render죽으면_전화면공백).
    """
    block = _card_block()
    assert "i.comments.toLocaleString()" not in block, \
        "comments를 가드 없이 부르고 있다 — 값이 없으면 render가 죽는다"
