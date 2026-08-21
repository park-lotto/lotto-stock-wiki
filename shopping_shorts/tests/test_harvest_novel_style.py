"""신기템 축(2026-08-20) — 사장님 "신박템이 안 올라온다 / 레시피가 너무 많다".

실측 표본은 '꿀템 보물찾기' 채널 제목(전부 [기능 관형어]+[제품] 틀).

★import 대상을 바꿨다 (2026-08-21) — 종전엔 `scripts/harvest_styles_forever.py`를
**통째로 실행**해서 가져왔다. 그 파일은 최상단에 실행부가 그대로 놓인 수확 스크립트라
import만으로 API 키 검사(`assert KEYS`)·서버 전용 경로(`BASE=/home/ubuntu/...`)까지
닿아 로컬에선 반드시 죽었다 → **pytest 수집 오류(rc=2)** → finish 게이트가
"실패 목록이 비어도 통과가 아니다"로 **모든 트랙의 병합을 막았다**(실사고).

판정 로직은 원래 `shopping_shorts/yt_style.py`에 있고 그 스크립트는 `ys.score_novel`로
**가져다 쓸 뿐**이다(harvest_styles_forever.py:182). 그러니 여기서도 원본을 직접 본다
— 같은 코드를 검사하면서 수확기를 돌리지 않는다(0순위-B: 판정이 사는 곳은 한 군데다).
"""
import pathlib
import re

from shopping_shorts import yt_style as H

NOVEL = [
    "알아서 섞어주는 자동 회전 텀블러 믹서컵 #인생템 #꿀템",
    "늘어나고 분리되는 공간활용 화장대 #집꾸미기 #꿀템",
    "붙여주면 깨끗해지는 자석 레인지 가드 #주방꿀템",
    "버려졌던 공간 살려주는 곡선 코너 선반 #인테리어 #가구추천",
]


def test_기능관형어_제품이면_신기템이다():
    assert H.score_novel(NOVEL) >= 3


def test_연예인_제목은_신기템이_아니다():
    """연예인결합 축으로 가야 한다 — 두 축이 섞이면 대본 스파인이 오염된다."""
    celeb = ["기안84가 애정하는 선세럼 #꿀템",
             "르세라핌 채원 강추 바디로션 #추천",
             "강주은이 고민 끝에 선택한 여름 가방 #구매"]
    assert H.score_novel(celeb) == 0


def test_요리_제목은_신기템이_아니다():
    food = ["3분이면 되는 자취요리 레시피 #꿀템",
            "볶음 만들기 초간단 #추천",
            "에어프라이어 반찬 만들어주는 법 #제품"]
    assert H.score_novel(food) == 0


def test_제품신호_없으면_안_센다():
    """기능 관형어만으로는 안 된다 — 일상 문장이 전부 걸린다."""
    assert H.score_novel(["기분이 좋아지는 아침 산책", "잠이 잘 오는 밤"]) == 0


def test_검색어를_실제_제목에서_뽑는다():
    q = H.harvest_novel(NOVEL)
    assert q, "통과 제목에서 검색어를 하나도 못 뽑았다"
    assert all(4 <= len(k) <= 25 for k in q), q


def test_수확기_STYLES에_등록됐다():
    """수확 루프가 이 축을 실제로 돌리는지 — 등록이 빠지면 채널이 영영 안 쌓인다.

    ★소스를 **읽어서** 확인한다(실행하지 않는다). 저 스크립트는 import만으로
      API 키·서버 경로를 요구해서, 돌리는 순간 수집이 깨진다(위 모듈 주석 참고).
    """
    p = (pathlib.Path(__file__).resolve().parents[2]
         / "scripts" / "harvest_styles_forever.py")
    src = p.read_text(encoding="utf-8")
    m = re.search(r'"신기템":\s*\{[^}]*?"min":\s*(\d+)', src, re.S)
    assert m, "harvest_styles_forever.STYLES에 '신기템'이 없다"
    assert m.group(1) == "5", m.group(0)
    assert "ys.score_novel" in src, "판정을 yt_style에서 가져다 쓰는 배선이 끊겼다"


def test_신기템만_구독하한을_갖는다():
    """이 축은 판정이 쉬워 문턱이 둘이다(2026-08-21 실측).

    min 3 · 하한 없음으로 하룻밤 549채널이 들어왔는데 두 종류로 오염돼 있었다:
      ① 잡채널   구독 중앙값 264(다른 축 1,410~8,030) · 100명 미만 38%
      ② 대형 오탐 25편 중 3편(12%)만 우연히 맞은 큰 채널
                 (시스레터 1/12=이케아 브이로그 · 알쓸피식 2/12=피부과)
                 진짜(오늘의건짐 3/12)와 갈리는 선이 25편 중 5편이었다.
    연예인·오용형은 공식 자체가 어려워 그게 곧 필터다 — 하한을 걸면 멀쩡한 채널이 잘린다.
    실측 잔존: 549 → 68채널(구독 중앙값 10,450).
    """
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "scripts" / "harvest_styles_forever.py").read_text(encoding="utf-8")
    def cfg(style):
        m = re.search(r'"%s":\s*\{(.*?)\}' % style, src, re.S)
        assert m, "%s 축이 STYLES에 없다" % style
        return m.group(1)
    assert '"min_subs": 1000' in cfg("신기템")
    for style in ("썰쇼핑", "연예인결합", "레시피쇼핑"):
        assert "min_subs" not in cfg(style), style
    assert 'sc >= cfg["min"] and subs >= cfg.get("min_subs", 0)' in src,         "등록부가 두 문턱을 함께 보지 않는다"
