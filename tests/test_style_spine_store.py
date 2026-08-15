"""spine을 '스타일 저장소'로 쓰는 배관 — 컬럼 추가·조회·카테고리 잠금·프롬프트 블록."""
import json

from shopping_shorts import bank_assemble
from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


ROLES = ["hook", "before", "reveal", "after", "cta"]
TEMPLATES = {"hook": ["이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요"],
             "cta": ["댓글에 {단어} 남겨주세요"]}


def _seed(st, name="시월드형", cats=None, roles=ROLES, chars=300):
    sid = st.add_spine(name=name, situation_type="가족에게 혼남",
                       beat_chain=["훅", "문제", "반전", "결과", "CTA"],
                       fit_categories=cats, status="approved")
    st.update_spine_stats(sid, source_count=4, perf_score=0.0)
    if roles:
        st.set_spine_style(sid, beat_roles=roles, templates=TEMPLATES, chars_per_30s=chars)
    return sid


def test_스타일_정보를_저장하고_되읽는다(tmp_path):
    st = _store(tmp_path)
    sid = _seed(st)
    sp = [s for s in st.list_spines() if s["id"] == sid][0]
    assert sp["beat_roles"] == ROLES
    assert sp["templates"]["cta"] == TEMPLATES["cta"]
    assert sp["chars_per_30s"] == 300


def test_구조없는_스파인은_스타일_목록에서_빠진다(tmp_path):
    """기존 31행처럼 beat_roles가 없는 스파인은 검사가 불가능하므로 고를 수 없어야 한다."""
    st = _store(tmp_path)
    _seed(st, name="구조없음", roles=None)
    sid = _seed(st, name="구조있음")
    ids = [s["id"] for s in st.list_style_spines()]
    assert ids == [sid]


def test_카테고리가_안_맞으면_목록에서_빠진다(tmp_path):
    """★실측 근거: 이어폰 소재에 살림용 시월드형을 씌우면 구조는 통과하는데 어색했다.
    게이트로 못 잡는 실패라 목록에서 막는다."""
    st = _store(tmp_path)
    _seed(st, name="살림용", cats=["살림청소"])
    assert [s["name"] for s in st.list_style_spines(category="살림청소")] == ["살림용"]
    assert st.list_style_spines(category="전자기기") == []


def test_적합카테고리가_비면_범용으로_통과한다(tmp_path):
    st = _store(tmp_path)
    _seed(st, name="범용", cats=None)
    assert [s["name"] for s in st.list_style_spines(category="전자기기")] == ["범용"]


def test_미승인_스파인은_안_나온다(tmp_path):
    st = _store(tmp_path)
    sid = _seed(st, name="대기중")
    st.set_spine_status(sid, "pending")
    assert st.list_style_spines() == []


def test_스타일_블록에_칸순서와_문장틀과_밀도가_박힌다(tmp_path):
    st = _store(tmp_path)
    sid = _seed(st)
    sp = [s for s in st.list_spines() if s["id"] == sid][0]
    block = bank_assemble.style_block(sp, seconds=30)
    assert 'role="hook"' in block and 'role="cta"' in block
    assert "이 순서 그대로" in block
    assert "욕 바가지로" in block                      # 문장틀이 실제로 실린다
    assert "300자 안팎" in block                       # 밀도가 실린다
    assert block.index('role="hook"') < block.index('role="cta"')


def test_구조없는_스파인은_블록이_빈다(tmp_path):
    assert bank_assemble.style_block({"name": "x"}) == ""
    assert bank_assemble.style_block(None) == ""


def test_스타일_블록은_중괄호를_소독한다(tmp_path):
    """script_generate 프롬프트가 .format()을 돌리므로 살아있는 중괄호가 있으면 터진다."""
    st = _store(tmp_path)
    sid = _seed(st)
    sp = [s for s in st.list_spines() if s["id"] == sid][0]
    block = bank_assemble.style_block(sp)
    assert "{" not in block and "}" not in block


def test_사용기록에_스타일id가_남는다(tmp_path):
    st = _store(tmp_path)
    sid = _seed(st)
    st.record_script_usage(hook="이것 때문에", spine_id=sid)
    with st._conn() as c:
        row = c.execute("SELECT spine_id FROM script_usage ORDER BY id DESC LIMIT 1").fetchone()
    assert row[0] == sid
