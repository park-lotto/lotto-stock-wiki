# -*- coding: utf-8 -*-
"""썸네일에 loading="lazy"를 쓰지 않는다 — 2026-08-28, **세 번째 재발**을 끝낸다.

## 왜 (라이브 실측 — 추측 아님)
같은 URL을 lazy로 두면 브라우저가 요청을 **아예 안 보낸다**. eager로 바꾸면 즉시 뜬다.

  화면            lazy 로드   eager 로드
  랭킹(/)          0 / 99      2 / 2
  발굴(/discover)  0 / 79      2 / 2
  즐겨찾기(/collection) 0 / 591  2 / 2

강제 재요청 실측: 실패한 lazy 이미지 5장의 **같은 src**를 새 Image()로 부르니
5/5 즉시 로드(540x960 · 720x1280 · 736x981 …). 서버·CDN·화이트리스트는 무죄다.

원인: 카드가 `display:grid` 안에서 `aspect-ratio`로 크기를 잡는 구조라
lazy 로더가 가시성 판정을 못 한다. 실측한 실패 이미지는 **화면 안에 있었다**
(rect.top -113, height 376, 뷰포트 1138) — 그런데도 요청이 없었다.

## 왜 테스트로 막나
같은 함정을 이미 **두 번** 주석으로만 막았고(2026-08-04 모달 · 2026-08-28 랭킹),
그때마다 다른 화면 6곳에는 그대로 남아 세 번째가 났다. 주석은 새 코드를 못 막는다.
"""
import pathlib
import re

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"

# 썸네일이 아닌 정적 삽화(도움말 그림 등)는 lazy가 정상 작동한다.
# 판정은 파일이 아니라 **그 img가 카드/그리드 썸네일인가**로 한다.
_THUMB_HINT = re.compile(
    r"(thumb|poster|card|cell|grid|segthumb|vcard)", re.I)


def _lazy_thumb_hits(path):
    """그 파일에서 '카드/썸네일 문맥의 lazy img' 줄 번호를 모은다."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    hits = []
    for i, line in enumerate(lines, 1):
        if 'loading="lazy"' not in line:
            continue
        if line.lstrip().startswith(("//", "<!--", "*", "#")):
            continue          # 금지 주석 자체는 건드리지 않는다
        # 앞뒤 4줄까지 훑어 카드/썸네일 문맥인지 본다
        ctx = " ".join(lines[max(0, i - 5):i + 2])
        if _THUMB_HINT.search(ctx):
            hits.append(i)
    return hits


def test_썸네일에_lazy가_없다():
    bad = {}
    for p in sorted(_STATIC.glob("*.html")):
        hits = _lazy_thumb_hits(p)
        if hits:
            bad[p.name] = hits
    assert not bad, (
        "썸네일에 loading=\"lazy\"가 남아 있다 — 라이브에서 요청조차 안 나가 "
        "카드가 통째로 빈다(실측 랭킹 0/99·발굴 0/79·즐겨찾기 0/591).\n"
        + "\n".join("  %s: %s행" % (k, v) for k, v in bad.items()))
