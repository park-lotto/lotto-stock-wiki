"""조용한 실패 총량 상한 — **늘어나는 것만** 막는다(2026-08-19).

## 왜

`except ...: pass`는 오류를 통째로 삼킨다. 이 저장소는 그 패턴에서 실사고를 두 번 냈다:

  · SQL 오류를 삼켜 히트작이 **라이브에서 0건**인데 아무 데도 안 남았다
    (memory `reference_테스트_시한폭탄_침묵except`)
  · 2026-08-03 EDL 실패가 조용히 DB에만 쌓여 **다음날까지 아무도 몰랐다**
    (mix_pipeline.py 주석 — 그래서 ops_alert가 생겼다)

증상이 지연·변형돼 나타나므로 "왜 매일 버그가 나는지 모르겠다"의 큰 축이다.

## 왜 일괄 수정이 아니라 상한인가

현재 **117개**다. 한 번에 고치면 그 자체가 대형 회귀다 — 부가기능의 조용한 실패는
**설계 의도인 곳도 많다**(썸네일 보강 실패가 담기를 막으면 안 되는 것처럼).
그래서 지금 개수를 천장으로 박고 **더 늘지 못하게만** 한다. 줄이는 건 사고 경로부터
선별해서 따로 한다. 기준선 방식은 finish 게이트가 이미 쓰는 개념이라 낯설지 않다.

## 새로 추가하고 싶다면

정말 삼켜야 하는 자리인지 먼저 의심하고, 맞다면 **사유를 남겨라**:

    except Exception as e:      # noqa: BLE001 — 왜 무해한지 한 줄
        import sys as _sys
        print(f"[어디] 실패(무해) {맥락}: {e!r}", file=_sys.stderr)

최근 사고들이 빨리 풀린 건 전부 이 로그 덕이었다(`who=채이홈 reels=0` 실례).
그래도 늘려야 한다면 아래 천장을 **의식적으로** 올리고, 왜 올리는지 커밋에 적어라.
"""
import io
import pathlib
import re

PKG = pathlib.Path(__file__).resolve().parents[1]

#: 2026-08-19 실측 기준선. **올릴 때는 커밋 메시지에 이유를 남긴다.**
#: 내리는 건 언제나 환영 — 줄었으면 이 숫자도 같이 내려라(그래야 되돌아가지 않는다).
BUDGET = {
    "app.py": 35,
    "store.py": 30,   # +2(2026-08-24): welcome_due·성별연령 컬럼 마이그레이션 — 위 컬럼들과 같은 "이미 존재" 패턴
    "instagram_playwright.py": 9,
    "media_download.py": 4,
    "mix_pipeline.py": 4,
    "product_facts.py": 3,
}
#: 위에 없는 파일의 개별 상한(작은 파일이 갑자기 늘어나는 것도 막는다).
DEFAULT_BUDGET = 2

_EXCEPT = re.compile(r"^(\s*)except\b.*:\s*(#.*)?$")


def _count_silent(path):
    """`except ...:` 다음 줄이 `pass`뿐인 자리의 개수."""
    lines = io.open(path, encoding="utf-8").read().split("\n")
    n = 0
    for i, line in enumerate(lines):
        if _EXCEPT.match(line) and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt == "pass" or nxt.startswith("pass "):
                n += 1
    return n


def test_조용한_실패가_늘지_않는다():
    """파일별 상한 초과를 잡는다 — 어느 파일이 몇 개 늘었는지 함께 알려준다."""
    over = []
    for f in sorted(PKG.glob("*.py")):
        n = _count_silent(f)
        cap = BUDGET.get(f.name, DEFAULT_BUDGET)
        if n > cap:
            over.append(f"{f.name}: {n}개 (상한 {cap})")
    assert not over, (
        "`except ...: pass`(조용한 실패)가 늘었습니다.\n"
        "정말 삼켜야 하면 사유 로그를 남기세요:\n"
        "    except Exception as e:  # noqa: BLE001 — 왜 무해한지\n"
        "        print(f'[어디] 실패(무해): {e!r}', file=sys.stderr)\n"
        "의도한 증가라면 test_silent_except_budget.py의 BUDGET을 올리고 커밋에 이유를 적으세요.\n"
        "초과: " + " / ".join(over))


def test_기준선이_현실보다_느슨하지_않다():
    """★상한이 실제보다 크게 잡혀 있으면 가드가 무력해진다.

    누가 고쳐서 개수가 줄면 상한도 같이 내려야 '되돌아감'을 막을 수 있다.
    여유 2개까지는 봐준다(리팩터링 중 오르내림).
    """
    slack = []
    for name, cap in BUDGET.items():
        p = PKG / name
        if not p.exists():
            continue
        n = _count_silent(p)
        if cap - n > 2:
            slack.append(f"{name}: 실제 {n} < 상한 {cap}")
    assert not slack, (
        "조용한 실패가 줄었습니다 — BUDGET도 함께 내려 되돌아가지 않게 하세요.\n"
        + " / ".join(slack))
