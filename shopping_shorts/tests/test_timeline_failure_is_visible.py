"""칸 타임라인의 **실패**는 보이는 자리에 뜬다 (2026-09-13 근본 수리).

왜 이 테스트가 있나 — "경계 클릭이 안 먹는다"는 원인이 매번 달랐는데도 증상은 늘 같았다:
  08-26 대조 기준 두 벌 / 09-07 _wrap_long이 사람 결정 덮음 / 09-09 자동저장 레이스·한 칸만 반영
  / 09-13 대사 속 NBSP가 대조 키를 깨뜨림([[reference_NBSP가_경계클릭_막음]])
네 번 다 서버는 422로 **이유를 정확히 말하고 있었다**. 그런데 타임라인은 `nsay`로만 알렸고,
`nsay`가 쓰는 `#tbhint`는 제작소 iframe 안에서 **0x0**이라 글자가 아예 안 보인다(09-07 실측 —
그래서 saylo/toastlo가 생겼다). 그 결과 고객에겐 언제나 "눌러도 아무 일이 없다"로만 보였고,
매번 잡 로그를 뒤져야 원인을 알 수 있었다.

원인은 앞으로도 새로 생길 수 있다(공백 종류는 막았지만 다른 이유로 422가 날 수 있다).
**막을 수 있는 건 침묵이다** — 실패가 화면에 뜨면 5번째 원인은 제보 한 줄로 끝난다.
"""
import re
from pathlib import Path

_JS = (Path(__file__).resolve().parents[1] / "static" / "scene_timeline.js").read_text(
    encoding="utf-8"
)


def _body(name):
    """헬퍼 함수 본문만 떼어낸다(문자열 검색이 아니라 구조로 본다)."""
    m = re.search(r"function %s\([^)]*\) \{(.*?)\n  \}" % name, _JS, re.S)
    assert m, f"{name}()가 없다 — 실패 알림 경로가 통째로 사라졌는지 확인하라"
    return m.group(1)


def test_실패는_보이는자리_saylo로_간다():
    """saylo는 푸터+토스트에 쓴다 — nsay만 쓰면 iframe 안에서 안 보인다."""
    body = _body("_tlSay")
    assert "saylo" in body, "실패 알림이 다시 nsay 전용으로 돌아갔다(=화면에서 안 보인다)"
    # saylo가 없는 화면(실험실 단독)에서도 죽지 않아야 한다.
    assert "typeof saylo === 'function'" in body


def test_서버가_준_이유를_그대로_보여준다():
    """422 본문('글자가 달라졌습니다 — 줄만 나누고 붙이세요')이 곧 해결법이다."""
    body = _body("_tlFail")
    assert "serverMsg" in body, "서버 사유를 버리고 뭉뚱그리면 원인을 또 못 찾는다"


def test_경계저장_실패_세_갈래가_모두_알린다():
    """응답 실패·네트워크 예외·장면 교체 — 조용히 return 하는 갈래가 없어야 한다."""
    gap = re.search(r"g\.tlGapClick = async function[\s\S]*?\n  \};", _JS)
    assert gap, "tlGapClick이 없다"
    src = gap.group(0)
    # 서버가 거절한 경우
    assert "_tlFail(d && d.error" in src, "422 거절이 조용히 return 된다"
    # 네트워크 예외
    assert re.search(r"catch \(e\) \{ _tlFail\(", src), "네트워크 실패가 조용히 삼켜진다"
    # 알림 없이 그냥 빠져나가는 return이 없는지(= 침묵 복귀)
    assert "nsay(" not in src, "타임라인 실패 경로에 nsay가 남아 있다(안 보이는 자리)"


def test_장면교체_실패도_보인다():
    """같은 침묵이 다른 버튼에서 재발하지 않도록 — 교체 실패도 같은 경로로."""
    assert "_tlFail(e && e.message, '장면을 교체하지 못했어요')" in _JS
