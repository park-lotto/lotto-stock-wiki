# -*- coding: utf-8 -*-
"""꾸미기 미리보기 자막이 불규칙하게 깜빡이던 것 (2026-09-01 고객 녹화 제보).

녹화(KakaoTalk_20260901_161409136.mp4, 7초) 실측 — 12fps로 자막 띠를 프레임 대조:
    0.17s 장면·자막 전환 / 1.42s 자막 전환 / 2.67s 자막 전환 / 3.33s 자막 전환
    → 3.33~4.00초 구간은 **자막이 아예 없었다**(페이드 아웃 바닥)
    → 4.00s에 **같은 문구가 다시** 흐리게 떠올랐다(같은 구절을 두 번 깜빡임)

★원인: 효과가 `animation:... infinite`(fade/slide/pop 2.2초, sparkle 2.6초)로 **자기 주기로
  무한 반복**인데, 구절 표시시간은 서버 durs 기준 1.0~1.5초다(칸0 = 1.5/1.0/1.43/1.08).
  두 주기가 서로 미끄러져 "어떤 구절은 뜨자마자 사라지고, 어떤 구절은 두 번 깜빡인다".
  실제 렌더는 구절이 새로 뜰 때 효과가 **한 번** 난다 — 미리보기가 렌더와 달랐다.

계약: 효과는 구절마다 1회(both로 끝 상태 유지). 재시작은 **문구가 바뀔 때만** 건다
      (글씨 크기·색을 손보는 중에 깜빡이면 자리를 못 잡는다).
"""
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_자막효과는_무한반복이_아니다():
    rules = re.findall(r"\.eff-(?:fade|slide|pop|sparkle)\{animation:[^}]*\}", HTML)
    assert len(rules) == 4, f"효과 규칙이 4개가 아니다: {rules}"
    for r in rules:
        assert "infinite" not in r, f"효과가 아직 무한반복이다 — 구절 주기와 미끄러진다: {r}"
        assert " both}" in r or "both}" in r, f"1회 재생 뒤 끝 상태를 유지해야 한다: {r}"


def test_문구가_바뀔_때만_효과를_다시_튼다():
    # 재시작 열쇠는 리플로우(offsetWidth) — 클래스만 뗐다 붙이면 브라우저가 재시작하지 않는다.
    i = HTML.index("el.classList.remove('eff-fade'")
    j = HTML.index("if(cs.effect==='fade')", i)
    block = HTML[i:j]
    assert "_CAP_FX_TEXT !== el.textContent" in block, "문구 변경 판정이 없다 — 매번 재시작하면 손볼 때 깜빡인다"
    assert "void el.offsetWidth" in block, "리플로우가 없으면 효과가 재시작되지 않는다"
    assert "let _CAP_FX_TEXT=" in HTML, "마지막 문구를 기억하는 전역이 없다"
