# -*- coding: utf-8 -*-
"""시계는 **타임라인 t 하나** — 음성이 타임라인을 끌고 가지 못하게 지킨다.

배경(2026-09-20 사장님 "근본적으로 발생하게된 우리 구조적 문제를 파악해서 그걸 뽑는건데"):
  seekTo 는 t 로 음성을 보낸 뒤 **음성이 앉은 자리를 되읽어 t 를 덮어썼고**, 못 갔으면
  `seekTo(a.currentTime)` 으로 타임라인을 다시 끌고 갔다. 타임라인→음성→타임라인 되먹임이다.

  ★뿌리: **mp3 는 요청한 자리에 정확히 못 앉는다**(프레임 단위로만 앉는다).
    실측 2026-09-20, 48kHz VBR TTS 9/9 컷에서 **일정하게 0.42초** 뒤에 안착했다.
    우리가 없앨 수 없는 오차인데, 그 오차를 **화면을 끌고 가는 근거**로 썼다.
    그래서 음성이 밀릴 때마다 화면이 엉뚱한 컷으로 튀었다.

  같은 고리에서 네 번 터졌다(전부 scene_play.js 주석에 남아 있다):
    08-17 "시간을 마우스로 이동시키는게 안된다"  → seeking 중엔 안 읽기로 땜
    08-20 음성이 죽으면 0초로 튕김               → audioUsable() 조건으로 땜
    09-18 되감으면 다음다음 컷이 낀다            → seeked 대기로 땜
    09-20 음성 시크 불가로 화면이 되돌아감        → Range 지원(그건 진짜 고침)
  매번 조건문을 하나씩 덧댔을 뿐 고리는 그대로였다. 그 고리를 끊은 것을 여기서 지킨다.
"""
from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "static" / "scene_play.js").read_text(encoding="utf-8")


def _strip_comments(js):
    """주석을 걷어낸다 — **왜 없앴는지 적은 글**이 금칙어에 걸리면 안 된다.

    실제로 걸렸다: 되먹임을 설명하는 주석에 그 코드 모양을 그대로 적었더니 검사가 그것을
    코드로 보고 실패했다. 검사 대상은 **도는 코드**다.
    """
    return "\n".join((ln.split("//")[0] if "//" in ln else ln) for ln in js.splitlines())


def _seek_to_body():
    js = _strip_comments(JS)
    i = js.index("function seekTo(t){")
    return js[i:js.index("\n}", i)]


def test_audio_never_overwrites_the_timeline():
    """음성이 앉은 자리로 t 를 덮어쓰면 안 된다 — 그게 되먹임의 입구다."""
    assert "t = a.currentTime" not in _seek_to_body(), "음성이 타임라인을 덮어쓴다(되먹임 부활)"


def test_audio_never_re_seeks_the_timeline():
    """음성 seeked 로 seekTo 를 다시 부르면 화면이 음성에 끌려간다."""
    assert "a.onseeked" not in _strip_comments(JS), "음성이 타임라인을 다시 끌고 간다(되먹임 부활)"


def test_audio_still_follows_the_timeline():
    """끊은 것은 **역방향**뿐이다 — 음성을 t 로 보내는 것은 그대로여야 한다."""
    assert "a.currentTime = t;" in _seek_to_body(), "음성이 타임라인을 안 따라간다"
