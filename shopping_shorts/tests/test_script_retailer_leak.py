"""★재료에 없는 판매처가 대본에 들어가면 그 안은 버린다 (2026-09-11 사장님 "고질적으로 다른 내용이 두 개씩").

실측(work 79e2c2b40481, cid 57):
  재료 6편 전부 '반려동물 털 제거 젤 패드(세탁기)' — 다이소는 어디에도 없다.
  그런데 스타일 57('다이소 내부인형')로 만든 초안이
    "여러분 다이소 가면 이거 무조건 데려오세요… 제 지인이 다이소 매니저로 있거든요."
  30일간 그 스타일을 고른 109건 중 50건이 같은 모양이었다.

뿌리(아스트라와 함께 규명, 2026-09-11):
  ① spine 57의 문장틀에 '다이소 점장/매니저'가 문자 그대로 박혀 있다(reveal 6틀 전부).
  ② bank_assemble.style_block이 "틀 자체를 새로 짓지 마라"고 강제 → 모델은 지시를 따랐다.
  ③ 기존 게이트 '소재 일치'는 우리 제품 단어가 **하나라도** 있으면 통과라 이걸 못 잡았다.
  ④ 조립(assemble_off=1)이 꺼져 있어 조립 전용 템플릿이 늘 일반 생성기로 떨어졌다.
  ⑤ 공통 은폐 안내의 정답 예시 자체가 "여러분 다이소 가면…"이었다.
"""
from shopping_shorts import script_gate

# 실제로 나갔던 초안(그대로) — 소재(털 패드)는 맞는데 판매처·인맥이 지어낸 것이다.
_다이소_대본 = [
    {"role": "hook", "text": "여러분 다이소 가면 이거 무조건 데려오세요."},
    {"role": "pain", "text": "반려동물 키우면서 옷에 박힌 털 때문에 매번 고생했거든요."},
    {"role": "reveal", "text": "제 지인이 다이소 매니저로 있거든요."},
    {"role": "proof", "text": "진열하자마자 품절되는 반려동물 용품이라 보이면 바로 사라고 하더라고요."},
    {"role": "demo", "text": "방법도 진짜 간단해요, 세탁기에 그냥 넣기만 하면 끝이에요."},
    {"role": "cta", "text": "댓글에 정보 남겨주시면 제품 정보 바로 보내드릴게요."},
]
_재료_원문 = ("반려동물 키우면서 검은 옷 포기하셨다면 이거 세탁기에 한번 넣어보세요. "
          "Pet hair remover for laundry. 젤 패드 두 개만 넣으면 털이 싹 붙어 나옵니다.")
_제품 = "반려동물 털 제거 젤 패드"


def test_gate_catches_retailer_leak():
    """재료에 없는 '다이소'가 대본에 나오면 잡는다 — 소재 일치는 통과해도."""
    checks, _ = script_gate.check({}, _다이소_대본, product=_제품, seconds=25,
                                  materials_text=_재료_원문)
    names = {c["name"]: c["ok"] for c in checks}
    assert names.get("소재 일치") is True, "소재 자체는 맞는 대본이다(이게 사각지대의 이유)"
    assert names.get("재료 밖 판매처") is False, names


def test_retailer_leak_is_fatal():
    """고쳐서 내보낼 것이 아니다 — 그 스타일을 빼야 한다."""
    checks, _ = script_gate.check({}, _다이소_대본, product=_제품, seconds=25,
                                  materials_text=_재료_원문)
    assert script_gate.fatal_fail(checks) == "재료 밖 판매처"


def test_retailer_in_materials_passes():
    """재료에 진짜 다이소가 있으면 통과 — 다이소 제품 영상은 다이소를 말해도 된다."""
    checks, _ = script_gate.check({}, _다이소_대본, product=_제품, seconds=25,
                                  materials_text=_재료_원문 + " 다이소에서 3천원에 샀어요.")
    names = {c["name"]: c["ok"] for c in checks}
    assert names.get("재료 밖 판매처") is True, names


def test_no_materials_text_means_no_check():
    """materials_text를 안 주면 검사 자체가 없다(회귀 0) — 옛 호출부가 그대로 돈다."""
    checks, _ = script_gate.check({}, _다이소_대본, product=_제품, seconds=25)
    assert "재료 밖 판매처" not in {c["name"] for c in checks}


def test_generate_one_style_drops_retailer_leak(monkeypatch):
    """모델이 끝까지 다이소를 내면 generate_one_style은 버리고, 처방은 '다른 스타일'이다."""
    from shopping_shorts import script_generate as sg
    from shopping_shorts import bank_assemble
    monkeypatch.setattr(bank_assemble, "style_block", lambda *a, **k: "[스타일 예시] 테스트용 블록")
    monkeypatch.setattr(sg, "_call_json",
                        lambda *a, **k: {"beats": [dict(b) for b in _다이소_대본]})
    note = {}
    out = sg.generate_one_style([{"full_text": _재료_원문, "product": _제품}],
                                {"id": 57, "name": "다이소 내부인형"}, 25, note=note)
    assert out is None, "재료 밖 판매처가 든 안이 그대로 나갔다"
    assert note.get("reason") == "판매처이탈", note
    # ★"재료를 더 담으라"는 틀린 처방을 내지 않는다 — 문제는 재료가 아니라 스타일이다.
    assert "재료 대본이 부족" not in (note.get("detail") or ""), note
    assert "다른 스타일" in (note.get("detail") or ""), note


def test_common_prompts_do_not_teach_retailer():
    """공통 안내(은폐 예시·트렌드 예시)에 판매처 이름이 없어야 한다 — 57만 고쳐도 여기서 또 샌다."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "bank_assemble.py").read_text(encoding="utf-8")
    body = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    assert "여러분 다이소 가면" not in body
    assert "'다이소 가면 이건" not in body


def test_seed_script_respects_pending():
    """seed_daiso_spine.py는 사람이 내린(pending) 스파인을 되살리지 않는다."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "scripts" / "seed_daiso_spine.py").read_text(encoding="utf-8")
    assert '== "pending"' in src and "return 0" in src.split('== "pending"', 1)[1][:400]
