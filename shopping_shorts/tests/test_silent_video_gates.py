# -*- coding: utf-8 -*-
"""키 없는 회원이 **무음 영상**을 받지 않게 막는 관문들.

★왜(2026-09-01 감사 → 2026-09-02 수리): 자막제거·TTS를 '내 키 필수'로 바꾸면서
  진입 게이트를 8곳에 걸었는데 **렌더·미리보기·후보선택 3곳이 빠져 있었다.**
  그 경로로 들어오면 tts.py가 무음 mp3로 폴백해 소리 없는 영상이 끝까지 만들어지고
  화면은 "✅ 완료"라고 말한다 — 사장님 지시("실패했을 때 안내문구를 띄우면 된다")의
  정반대다. 조용한 실패가 실패보다 나쁘다.

★그리고 게이트를 통과한 회원의 **재합성**이 사장님 키로 나가던 구멍(cid 미전달)도
  같이 막았다 — 막으려던 누수가 그 경로로 되살아나 있었다.
"""
import io
import os
import re

_DIR = os.path.join(os.path.dirname(__file__), "..")


def _src(name):
    return io.open(os.path.join(_DIR, name), encoding="utf-8").read()


def _body(src, fn, span=40):
    """함수 정의부터 span줄까지 — 게이트는 함수 초입에 있어야 한다."""
    i = src.index("def %s(" % fn)
    return "\n".join(src[i:].splitlines()[:span])


def test_렌더_미리보기_후보선택에_키게이트가_있다():
    app = _src("app.py")
    for fn in ("api_mix_render", "api_produce_mix_preview", "api_mix_candidate"):
        b = _body(app, fn)
        assert "_need_own_key_or_402" in b, (
            f"{fn}: 키 게이트가 없다 — 키 없는 회원이 무음 영상을 받고 '완료'를 본다")
        assert "request" in app[app.index("def %s(" % fn):
                                app.index("def %s(" % fn) + 200], \
            f"{fn}: request를 안 받으면 누구인지 몰라 게이트를 걸 수 없다"


def test_콘폼과_재합성이_고객키로_나간다():
    """cid를 안 넘기면 0(사장님 키)으로 떨어진다 — 누수가 이 경로로 되살아난다."""
    mp = _src("mix_pipeline.py")

    sig = re.search(r"def _conform_beats\(([^)]*)\)", mp, re.S)
    assert sig and "customer_id" in sig.group(1), "_conform_beats가 cid를 안 받는다"

    # 본 파이프라인 호출부
    call = re.search(r"_conform_beats\(plan\[\"beats\"\][^)]*\)", mp, re.S)
    assert call and "customer_id" in call.group(0), "본 렌더 경로가 cid를 안 넘긴다"

    # 한 비트 재합성 경로
    r = _body(mp, "resynth_one_beat", span=80)
    assert "customer_id=_cid_of_job" in r, "재합성이 cid를 안 넘긴다(사장님 키로 나간다)"
    assert 'job.get("customer_id")' in r, "job 주인을 안 꺼내면 넘길 값이 없다"


def test_게이트는_판단을_스스로_하지_않는다():
    """판단은 keyroute 한 곳(0순위-B). 엔드포인트가 키 유무를 또 검사하면 어긋난다."""
    app = _src("app.py")
    for fn in ("api_mix_render", "api_produce_mix_preview", "api_mix_candidate"):
        b = _body(app, fn)
        assert "customer_keys" not in b, f"{fn}: 키를 직접 조회한다 — keyroute와 갈라진다"


def test_막을때_하루횟수를_돌려준다():
    """게이트가 막으면 check_and_count로 깎은 횟수를 되돌려야 한다.

    ★안 돌려주면 아무것도 못 만들고 오늘 한 번을 잃는다 — 막힌 사람을 두 번 벌한다.
      원본(api_mix_start)엔 있었는데 복제 경로(api_mix_candidate_clone)에만 빠져 있었다.
    """
    app = _src("app.py")
    # check_and_count 뒤에 오는 _need_own_key_or_402 블록마다 uncount가 붙어야 한다
    for m in re.finditer(r"check_and_count\(cid, \"render\"\)", app):
        tail = app[m.end():m.end() + 1800]
        gate = tail.find("_need_own_key_or_402")
        if gate < 0:
            continue
        block = tail[gate:gate + 260]
        assert "uncount" in block, (
            "게이트가 하루 횟수를 안 돌려준다 — 막힌 사람이 오늘 1회를 잃는다:\n" + block[:200])


def test_전체음성_생성이_응답을_읽는다():
    """POST 결과를 안 읽으면 402로 막혀도 2.5초 뒤 '완료'를 띄운다(거짓 보고)."""
    pr = _src("static/produce.html")
    i = pr.index("async function applyVoice(")
    body = pr[i:i + 2600]
    assert "await fetch('/api/mix/voice'" in body
    assert "r.ok" in body or "d.ok" in body, "응답을 안 읽는다 — 거짓 '완료'가 뜬다"
    assert "needKeyHtml" in body, "막힌 이유(키 없음)를 안내하지 않는다"


def test_settings_keys_해시가_키탭을_연다():
    """안내가 /settings#keys로 보내는데 그 해시를 안 읽으면 엉뚱한 탭이 열린다."""
    st = _src("static/settings.html")
    assert '"#keys"' in st and 'showTab("keys")' in st, "#keys 해시를 아무도 안 읽는다"
