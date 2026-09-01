"""한 화면 자리를 덮어쓰는 함수가 **더 늘어나지 않게** 막는다 (2026-08-19).

사장님: "매번 이러는데 이건 못막는거야?"

못 막는 게 아니라 **안 막은 자리가 남아 있었다**. 실측하니 produce.html 한 파일에만
같은 DOM 자리를 여러 함수가 각자 innerHTML로 덮어쓰는 곳이 24군데였다.

실제로 터진 것들(전부 같은 모양이다):
  2026-08-19 ① 1단계 분석이 안 보임 — #srcAnalysis를 renderSourceAnalysis ·
                renderAutoloadingState · renderQueuedState 셋이 각자 덮어써서,
                8초 폴링과 자동적재가 서로를 지웠다. 새로고침해야만 보였다.
  2026-08-19 ② 3단계 미리보기가 "끊김" — #mixPreview를 4개 함수가 만진다.
                미리보기는 성공(ready)했는데 화면이 초기 안내로 되돌아갔다.

왜 이 모양이 위험한가: **누가 마지막에 이기는지 아무도 모른다.** 폴러·타이머·사용자
클릭이 겹치면 순서가 매번 달라진다. 그래서 "고쳤는데 또 난다"가 반복된다.
CLAUDE.md 0순위-B("같은 결정이 두 군데 적히면 언젠가 어긋난다")가 말하는 바로 그것.

이 테스트가 하는 일 — **지금 있는 24곳을 고치라는 게 아니다**(한꺼번에 뜯으면 더 큰
사고가 난다). 현재치를 천장으로 삼아 **새로 늘어나는 것만** 막는다. 그래서 오탐이 0이고
(지금은 전부 통과), 오늘 이후로는 새 지뢰가 안 깔린다. 줄어들면 천장도 같이 내린다
(안 내리면 되돌아가는 것을 못 잡는다 — test_silent_except_budget과 같은 방식).

고칠 때는 자리 하나에 그리는 함수 하나로 모아라(2026-08-19 #srcAnalysis가 그 예).
"""
import collections
import re
from pathlib import Path

_HTML = Path(__file__).resolve().parents[1] / "static" / "produce.html"

# 자리(DOM id) → 그 자리를 innerHTML로 덮어쓰는 함수 수. 2026-08-19 실측 기준선.
# ⚠️ 새 항목을 여기 추가하지 마라 — 그건 지뢰를 하나 더 깔았다는 뜻이다.
#    자리 하나에 그리는 함수 하나로 모으고, 줄어든 값으로 고쳐라.
BASELINE = {
    # ⚠️mixPreview 6 / pmResults 4 는 **늘어난 게 아니라** 원래 그랬는데 못 세던 값이다
    #   (2026-08-24 스캐너 수정 — 한 줄 다중선언의 둘째 변수를 놓치고 있었다).
    #   실측으로 확인: 손대지 않은 main에서도 똑같이 6·4다. 천장을 올린 게 아니라
    #   눈이 멀어 낮게 적혀 있던 것을 **사실에 맞춘** 것이다. 여전히 "더 늘면 실패"다.
    "mixPreview": 6, "mixReview": 4, "aiPick": 4, "cleanPreview": 4,
    "finalVideo": 4, "mixCandidates": 4, "coupangSlot": 3, "pmResults": 4,
    "btnFinalRender": 2, "candStatus": 2, "finalStatus": 2, "frPresets": 2,
    "fxResult": 2, "handoffBanner": 2, "matOverlay": 2, "matchProgress": 2,
    "presetCards": 2, "s2StyleRow": 2, "seoBody": 2, "thumbFramesHint": 2,
    "thumbGallery": 2, "thumbTitleSuggest": 2, "tplCards": 2, "voicePreview": 2,
    "wsList": 2,
}


def _scan_owners(text):
    """DOM id → {그 자리에 innerHTML을 대입하는 함수 이름}.

    두 가지 쓰기 형태를 본다:
      ① getElementById('x').innerHTML = ...      (직접)
      ② const box = getElementById('x'); box.innerHTML = ...   (변수 경유)
    읽기(innerHTML을 꺼내 보는 것)는 세지 않는다 — 덮어쓰는 것만이 서로를 지운다.
    """
    owners = collections.defaultdict(set)
    fn = None
    var_of = {}          # 지역변수 이름 → DOM id (같은 함수 안에서만 유효)
    for line in text.split("\n"):
        m = re.match(r"\s*(?:async\s+)?function\s+(\w+)", line)
        if m:
            fn, var_of = m.group(1), {}
        # ★한 줄에 여러 개를 선언하면 **첫 개만** 잡던 것을 고쳤다(2026-08-24).
        #   `const a=getElementById('x'), b=getElementById('y');` 에서 b를 놓쳐,
        #   b.innerHTML= 로 덮어쓰는 함수가 소유자 집계에서 통째로 빠졌다.
        #   실측: _renderMixReviewBody가 #mixPreview를 쓰는데도(5259행) 안 세어졌다
        #   — 자리 하나에 6명인데 5명으로 보였다. 세는 눈이 멀면 천장은 무의미하다.
        for v in re.finditer(r"(\w+)\s*=\s*document\.getElementById\('([\w-]+)'\)", line):
            var_of[v.group(1)] = v.group(2)
        d = re.search(r"getElementById\('([\w-]+)'\)\.innerHTML\s*=", line)
        if d and fn:
            owners[d.group(1)].add(fn)
        if fn:
            for var, gid in var_of.items():
                if re.search(r"\b%s\.innerHTML\s*=" % re.escape(var), line):
                    owners[gid].add(fn)
    return owners


def test_한_자리를_덮어쓰는_함수가_늘지_않는다():
    owners = _scan_owners(_HTML.read_text(encoding="utf-8"))
    grown, appeared = [], []
    for gid, fns in owners.items():
        if len(fns) < 2:
            continue
        cap = BASELINE.get(gid)
        if cap is None:
            appeared.append(f"  ⚠️ 새 자리 #{gid} — {len(fns)}개 함수가 덮어쓴다: {sorted(fns)}")
        elif len(fns) > cap:
            grown.append(f"  ⚠️ #{gid} {cap} → {len(fns)}개로 늘었다: {sorted(fns)}")
    msg = "\n".join(appeared + grown)
    assert not msg, (
        "\n한 화면 자리를 덮어쓰는 함수가 늘었다 — 이 모양이 '고쳤는데 또 나는' 버그의 뿌리다.\n"
        + msg
        + "\n\n고치는 법: 그리는 함수는 하나만 두고, 나머지는 상태 값만 바꾼 뒤 그 함수를 부른다.\n"
          "  (2026-08-19 #srcAnalysis가 그렇게 정리됐다 — renderSourceAnalysis 하나가 그린다)\n"
    )


def test_기준선이_현실보다_느슨하면_알려준다():
    """줄었는데 천장이 그대로면 실패시킨다 — 안 그러면 되돌아가는 것을 못 잡는다."""
    owners = _scan_owners(_HTML.read_text(encoding="utf-8"))
    stale = []
    for gid, cap in BASELINE.items():
        now = len(owners.get(gid, ()))
        if now < cap:
            stale.append(f"  ✅ #{gid} {cap} → {now}개로 줄었다. BASELINE을 {now}(또는 삭제)로 고쳐라")
    assert not stale, "\n기준선이 현실보다 느슨하다(좋은 소식이니 반영하라):\n" + "\n".join(stale)
