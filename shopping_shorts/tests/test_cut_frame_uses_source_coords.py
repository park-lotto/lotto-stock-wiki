# -*- coding: utf-8 -*-
"""꾸미기 컷 그림이 3단계와 다른 장면으로 뜨던 것 (2026-09-01 사장님 캡처 대조).

사장님 실측: 3단계 hook 4컷 = 케이크 / 여자 / 야외케이크 / 아이
             꾸미기 4컷    = 케이크 / 케이크 / 여자 / 여자   ← 사실상 2장면

★뿌리(좌표계가 두 벌):
    3단계 재생 : 소스 mp4 + 원본 시각   (s3의 8.8초)
    꾸미기 프레임: 완성본 청소본의 몇 초  (clean_preview.mp4 × 비율)
  완성본 청소본은 **청소를 돌린 그 시점의 편성물**이다. 실측 job 84b5f66a8e1f는
  clean_preview.mp4가 8/27 20:58 생성인데 컷 계획은 9/1 — 그 초는 아무 뜻이 없다.
  _extract_beat_frame이 seg_spec(컷 좌표)을 받아놓고도 clean_final이 있으면
  **무조건 덮어썼다**(CLAUDE.md 0순위-B: if A: x=1 아래 x=2).

계약:
  · 컷 좌표(seg_spec)가 있으면 완성본 좌표계로 덮어쓰지 않는다 → 3단계와 같은 그림
  · 소스별 청소본(clean_sources)은 좌표계가 같으므로 그대로 우선한다
  · 칸 대표 프레임(seg_spec 없음)은 종전대로 완성본에서 뜬다
"""
import inspect

from shopping_shorts import app as A

_SRC = inspect.getsource(A._extract_beat_frame)


def test_컷좌표가_있으면_완성본으로_덮어쓰지_않는다():
    assert "if seg_spec is None and clean_final" in _SRC, \
        "컷 좌표가 있어도 완성본 시각으로 덮어쓴다 — 3단계와 다른 그림이 뜬다"


def test_소스별_청소본은_그대로_우선한다():
    """좌표계가 같으니(소스+원본시각) 자막 지운 화면을 계속 쓴다(2026-07-21 제보 유지)."""
    i = _SRC.index("if src is None and vid and clean_sources:")
    j = _SRC.index("if src is None and vid:", i)
    assert "clean_sources.get(vid)" in _SRC[i:j], "소스별 청소본 경로가 사라졌다"


def test_캐시이름이_실제로_뜬_곳을_반영한다():
    """이름이 _clean 그대로면 옛 완성본에서 뜬 틀린 그림이 재사용된다."""
    s = inspect.getsource(A._beatframe_file)
    assert '_ctag = "_src"' in s, "컷 프레임 캐시 태그가 안 갈린다 — 옛 그림이 그대로 나온다"
    assert "if _spec and not clean_map:" in s, "소스별 청소본일 때는 _clean 태그를 지켜야 한다"
