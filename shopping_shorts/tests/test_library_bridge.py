"""도서관→제작소 다리(2026-07-15). 구조분석 dict를 mix job에 보관하는 경로.

⚠️ 기존 mix_jobs.structure는 template/free 모드 플래그(문자열)라 구조분석 dict를
넣으면 edit_plan의 분기가 깨진다. 그래서 별도 컬럼 script_structure_json을 쓴다.
"""
from shopping_shorts.store import Store


def test_create_mix_job_stores_script_structure(tmp_path):
    st = Store(str(tmp_path / "reference.db"))
    struct = {"hook_type": "질문형", "characters": ["요리 고수 언니"], "tone": "친근한 반말"}
    st.create_mix_job("J1", ["https://x/a.mp4"], 30, "template",
                      given_script="확정 대본", script_structure=struct)
    job = st.get_mix_job("J1")
    assert job["script_structure"] == struct
    # 기존 structure(=모드 플래그)는 오염되지 않는다 — 이름 충돌 회귀가드
    assert job["structure"] == "template"


def test_create_mix_job_without_script_structure_is_none(tmp_path):
    st = Store(str(tmp_path / "reference.db"))
    st.create_mix_job("J2", ["https://x/a.mp4"], 30, "template")
    job = st.get_mix_job("J2")
    assert job["script_structure"] is None
    assert job["structure"] == "template"
