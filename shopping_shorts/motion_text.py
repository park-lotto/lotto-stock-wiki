"""텍스트 종속 모션 오버레이(키네틱 타이포·콜아웃)의 per-video 렌더 인터페이스.

Phase 1 뼈대에서는 스텁 — 서버 Node/헤드리스 크롬 가용성이 확인되면 Phase 2(팩)에서
Remotion `render:overlay`를 실제로 호출하도록 이 함수 본문을 채운다. 시그니처는 고정.
"""


class TextRenderUnavailable(RuntimeError):
    """텍스트 종속 오버레이 렌더가 아직 구성되지 않음(Node 미확인/미구현)."""


def render_text_overlay(template, props, out_dir):
    """template(예: 'KineticHook')과 props(예: {'text': ...})로 투명 오버레이 파일을
    렌더해 그 경로를 반환한다. Phase 1에서는 미구성이라 예외를 던진다.

    Phase 2 구현 방향:
      motion/ 프로젝트에서
      `npm run render:overlay -- --template=<template> --props=<json> --out=<out_dir>/x.webm`
      를 subprocess로 호출하고 out 경로를 반환.
    """
    raise TextRenderUnavailable(
        f"텍스트 종속 렌더 미구성(template={template!r}) — Phase 2에서 Remotion render:overlay 연결"
    )
