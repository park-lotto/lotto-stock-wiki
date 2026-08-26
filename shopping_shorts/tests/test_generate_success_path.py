"""대본 생성 **성공경로**를 끝까지 달린다 — 2026-08-19.

## 왜 이 파일이 필요한가

08-15~17 사흘간 같은 영역에서 긴급수리가 **4건** 났다:

    08-15 aec0af237  장면 편집 통째로 안 뜸 — 칸 길이 함수가 병합 중 지워짐
    08-16 354105612  재료 보강이 대본 생성을 통째로 막음("내가 낸 사고")
    08-16 5c49ce8f6  source_brief가 dict인데 .strip() 호출 → 500 (사장님이 6번 클릭)
    08-17 429fcce1f  _scene_block NameError → 500

넷 다 **성공경로 마지막 줄**에서 터졌다. 기존 테스트는 거절 경로(422/404)만 검사해서
게이트를 그냥 통과했다(memory `reference_바꾸기_한칸재생성`에 이미 진단돼 있던 것).

그래서 여기서는 **200이 나올 때까지 실제로 달린다**. AI 호출만 응답 모양 그대로
가로채고, 재료 조립·장면 블록·프롬프트 조립은 **진짜 코드가 돌게** 둔다 —
거기가 매번 터진 자리이기 때문이다.

## fixture 설계 원칙

라이브에서 실제로 터진 모양을 쓴다. 특히:

  · `source_brief`는 **dict**다(product/role/core/summary) — 문자열이 아니다.
    손으로 지은 미니 fixture는 이 함정을 재현 못 해 5c49ce8f6이 그대로 새 나갔다.
  · `job_id`/`work_id`로 **dict가 올 수 있다**(클라이언트 값) — 타입을 믿지 마라.
  · 추출 본문은 실제처럼 길다(라이브 실패 job의 extract_json은 9,091자였다).
"""
import json

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    return TestClient(appmod.app)


def _extract_blob():
    """라이브 job의 extract 모양 — ★source_brief가 dict인 것이 핵심."""
    return {
        "vidA": {
            # 실제 실패 job의 extract_json은 9KB대였다. 길이도 재현한다.
            "full_text": "이 제품은 정말 편리합니다. " * 200,
            "source_brief": {                     # ← dict! (문자열 아님)
                "product": "분리형 미니 세탁기",
                "role": "제품 소개",
                "core": "물기만 하면 건조까지",
                "summary": "작은 세탁기로 속옷·수건을 따로 빤다",
            },
            "segments": [
                {"start": 0.0, "end": 3.2, "label": "제품 클로즈업",
                 "use_point": "훅에서 정체를 감출 때", "text": "이게 뭐냐면요"},
                {"start": 3.2, "end": 7.9, "label": "물 붓는 장면",
                 "use_point": "작동 원리 보여줄 때", "text": "물을 넣고"},
                {"start": 7.9, "end": 12.0, "label": "건조 완료",
                 "use_point": "결과 제시", "text": "바로 건조까지"},
            ],
        }
    }


def _seed_job(db_path, job_id="JOB1"):
    store = Store(db_path)
    store.create_mix_job(job_id, ["https://www.instagram.com/reel/AAA111/"],
                         target_seconds=30, structure="template")
    store.update_mix_job(job_id, extract_json=json.dumps(_extract_blob(), ensure_ascii=False))
    return store


def _fake_styles(*a, **kw):
    """generate_by_styles 응답 모양(**리스트**)을 그대로 흉내낸다 — AI 호출만 차단.

    ★계약을 코드에서 확인했다(app.py: `for dr in _styled: dr.get("hook"/"script")`).
      dict를 돌려주면 502로 빠져 성공경로를 못 달린다 — 그러면 이 테스트가
      존재 이유를 잃는다(가짜 green의 반대편 함정).
    """
    return [{"hook": "훅입니다.", "script": "훅입니다.\n본론입니다.\nCTA입니다.",
             "style_id": "s1", "name": "기본"}]


def _fake_variations(*a, **kw):
    """generate_variations(다른 분기) 응답 — 이쪽도 리스트다."""
    return [{"hook": "훅", "script": "본문", "elements": {}}]


def test_대본생성_성공경로가_200으로_끝난다(client, tmp_path, monkeypatch):
    """★이 테스트의 존재 이유 — 08-15~17 긴급 4건이 전부 이 구간에서 500이었다.

    재료 조립(_materials_for_generate)·장면 블록(_scene_points_block)은 **진짜로 돌린다**.
    """
    db = str(tmp_path / "t.db")
    _seed_job(db)
    monkeypatch.setattr(appmod.script_generate, "generate_by_styles", _fake_styles)
    monkeypatch.setattr(appmod.script_generate, "generate_variations", _fake_variations)

    r = client.post("/api/wiki/generate?shortcode=SC_SMOKE", json={
        "mode": "remake", "subject": "분리형 미니 세탁기", "n": 1,
        "job_id": "JOB1",
        "structure": {"beats": [{"role": "hook"}, {"role": "body"}, {"role": "CTA"}]},
        "base_script": "원본 대본입니다.",
    })
    assert r.status_code == 200, f"성공경로가 {r.status_code}로 죽었다: {r.text[:400]}"
    assert (r.json() or {}).get("ok") is not False, r.text[:300]


def test_source_brief가_dict여도_안_죽는다(tmp_path):
    """5c49ce8f6 재발 방지 — 영상 요약은 dict다. .strip()을 바로 부르면 500."""
    job = {"extract": _extract_blob()}
    out = appmod._scene_points_block(job)
    assert isinstance(out, str)
    # dict의 어느 필드든 실려야 '재료가 실제로 붙었다'는 뜻
    assert "분리형 미니 세탁기" in out or "물기만" in out or "제품 클로즈업" in out


def test_job_id가_dict로_와도_500이_아니다(client, tmp_path, monkeypatch):
    """★타입을 믿지 마라(work_id 사고와 같은 유형) — 클라이언트 값은 뭐든 올 수 있다.

    500(서버 잘못)이 아니라 정상 처리되거나 4xx로 거절돼야 한다.
    """
    db = str(tmp_path / "t.db")
    _seed_job(db)
    monkeypatch.setattr(appmod.script_generate, "generate_by_styles", _fake_styles)
    monkeypatch.setattr(appmod.script_generate, "generate_variations", _fake_variations)

    r = client.post("/api/wiki/generate?shortcode=SC_SMOKE", json={
        "mode": "remake", "subject": "x", "n": 1,
        "job_id": {"nope": 1}, "work_id": ["also", "wrong"],
        "structure": {"beats": [{"role": "hook"}]},
        "base_script": "원본",
    })
    assert r.status_code != 500, f"타입 방어 실패: {r.text[:300]}"


def test_장면블록이_깨진_세그먼트에도_안_죽는다():
    """세그가 문자열·None으로 섞여 와도 통째로 죽으면 안 된다(부분 손상 내성)."""
    job = {"extract": {"v1": {"segments": ["망가짐", None, {"label": "정상", "use_point": "쓸모"}],
                              "source_brief": "옛 형식(문자열)"}}}
    out = appmod._scene_points_block(job)
    assert isinstance(out, str) and "정상" in out


def test_재료가_비어도_500이_아니라_사유를_준다(client, monkeypatch):
    """재료가 없으면 422로 '왜 안 되는지' 말해야 한다 — 조용한 500 금지."""
    monkeypatch.setattr(appmod.script_generate, "generate_by_styles", _fake_styles)
    monkeypatch.setattr(appmod.script_generate, "generate_variations", _fake_variations)
    r = client.post("/api/wiki/generate?shortcode=SC_NONE", json={
        "mode": "remake", "subject": "x", "n": 1})
    assert r.status_code != 500, f"재료 없음이 500으로 샜다: {r.text[:300]}"
