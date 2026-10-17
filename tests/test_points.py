"""잇썸홈(두유노홈디노 결) 잉?·와우 포인트(channel/homedesignnote/대본설명서/points.json) — 사장님 2026-10-18.
빨강: 10-18 엔진이 낸 4줄 대본(포인트 없음) · 어제 손 대본(②줄에 귀에 들어오는 연결어 없음) 반려. 초록: 포인트 넣은 6줄 통과."""
from pathlib import Path

from tools.calcopy.engine import script_frame as SF

ROOT = Path(__file__).resolve().parents[1]
FRAME = ROOT / "channel" / "homedesignnote" / "대본설명서" / "script_frame.json"
PC = SF.load_points(FRAME)
IDS = {f"f{i}" for i in range(1, 10)}


def _L(*rows):
    return [{"text": t, "facts": f, **({"point": p} if p else {}), **({"answer_at": a} if a is not None else {})} for t, f, p, a in rows]


def test_signal_words_from_shortem_owner():
    w = SF.signal_words()
    assert len(w) >= 30 and "근데 진짜 충격적인 포인트는" in w and "이게 미친 포인트인게" in w


def test_flat_four_lines_rejected():
    r = SF.points_check(_L(("매일 캡슐 쓰레기 버리는 게 귀찮아서 짜증 났던 커피 마니아가 콘센트 없이 쓰는 추출기를 뚝딱 만들어버렸대요.", ["f1"], None, None),
                           ("보통 위에서 떨어지는데 이건 아래에서부터 크레마가 싹 차오르더라고요.", ["f5"], None, None),
                           ("캡슐커피가 물 탄 맛인데 이건 진짜 원액 같아서 커피 맛 몰라도 바로 느껴져요.", ["f8"], None, None),
                           ("캡슐 쓰레기 쌓일 일도 없으니까 요즘은 동네 카페들 다 망할까 봐 제가 걱정되더라고요.", ["f7"], None, None)), PC, IDS)
    assert not r["ok"] and any("와우 포인트 0/3" in w for w in r["why"]) and any("잉?" in w for w in r["why"])


def test_quiet_connector_not_wow():
    # 어제 손 대본 ②줄 — 내용은 있지만 머리에 강한 연결어가 없어 귀에 안 꽂힌다
    assert SF.wow_head("근데 이건 중국에서만 누적 판매 수백만 대를 찍었다는데,", PC) is None
    assert SF.wow_head("진짜 핵심은 이건데, 싱크볼에 그릇 툭툭 넣고 뚜껑만 닫으면 돼요.", PC)


def test_points_script_passes():
    r = SF.points_check(_L(("매일 캡슐 쓰레기 치우는 게 귀찮았던 친구가 아예 전기선 없는 커피 추출기를 들여버렸대요.", [], None, None),
                           ("코드 꽂을 곳도 없는데 대체 진한 에스프레소가 어떻게 나오나 싶잖아요.", [], "잉", 3),
                           ("이게 진짜 대박인 게, 캡슐커피랑 비교하면 맹물과 원액 수준이라 커피 맛 몰라도 차이가 확 느껴져요.", ["f8"], "와우", None),
                           ("근데 진짜 충격적인 포인트는 위에서 떨어지는 게 아니라 밑에서부터 솟구치며 진한 크레마가 차올라요.", ["f5"], "와우", None),
                           ("심지어 더 미친 포인트가 콘센트 없이 전기 안 쓰는데 캡슐 쓰레기 쌓일 일도 전혀 없더라고요.", ["f1", "f7"], "와우", None),
                           ("이거 들인 뒤로는 집 앞 카페는 쳐다도 안 보고 하루 종일 에스프레소만 마시면서 살아요.", [], None, None)), PC, IDS)
    assert r["ok"], r


def test_wow_needs_fact_and_ing_needs_answer():
    r = SF.points_check(_L(("처음 줄이에요.", [], "잉", None), ("이게 진짜 대박인 게, 그냥 진짜 좋아요 완전 최고예요.", [], "와우", None),
                           ("근데 진짜 충격적인 포인트는 이거예요.", ["f1"], "와우", None), ("심지어 더 미친 포인트가 있어요 정말로요.", ["f2"], "와우", None)), PC, IDS)
    assert not r["ok"] and 1 in r["bad"] and any("answer_at" in w for w in r["why"])


def test_cta_switch_off_by_default():
    assert PC["cta"]["required"] is False         # 사장님: 유튜브 스타일 — 인스타형 판에서만 켠다
    on = {**PC, "cta": {**PC["cta"], "required": True}}
    r = SF.points_check(_L(("a", [], None, None), ("b 끝 줄.", [], None, None)), on, IDS)
    assert any("끝 CTA" in w for w in r["why"])
