"""10-31 회원 눈·경험. 같은 자료를 새 Claude 는 잡는데 회원 편은 통과 — 봤다는 증거 없는 답·시트 없는 통과를 막는다."""
import json
from pathlib import Path

import pytest

from tools.calcopy.hybrid import flow as F

ROOT = Path(__file__).resolve().parents[2]
SV = {"title": "영업 기밀을 빼앗겨버린 아웃백", "lines": ["첫 줄", "둘째 줄", "셋째 줄", "넷째 줄"]}
SCENES = [{"at": "0~3", "line": "첫", "seen": "빵"}, {"at": "3~6", "line": "둘째", "seen": "오븐"}]


def test_lazy_ok_is_not_an_answer():
    assert F.sheet_proof_problems({"ok": True}, SV)


def test_cut_title_is_caught_from_what_was_read():
    got = F.sheet_proof_problems({"title_seen": "영업 기밀을", "scenes": SCENES}, SV)
    assert len(got) == 1 and got[0].startswith("제목")


def test_full_answer_passes_even_with_spacing_difference():
    assert F.sheet_proof_problems({"title_seen": "영업 기밀을 빼앗겨 버린 아웃백", "scenes": SCENES}, SV) == []


def test_flow_rejects_ok_with_cut_title():
    """회원 Claude 가 ok 라고 해도 읽은 제목이 대본과 다르면 합격이 아니다 — 흐름에서 잰다."""
    st = {"version": "x", "log": [], "tries": {}, "script": {"S": {"title_lines": [["영업 기밀을"], ["빼앗겨버린 아웃백"]], "lines": [{"id": "a", "kind": "tts", "tts": "첫 줄"}]}}}
    F.ph_final_sheet(st, {}, {"sheet_x": {"ok": True, "problems": [], "title_seen": "영업 기밀을", "scenes": [{"seen": "빵"}]}}, {})
    assert st["look"]["ok"] is False and st["look"]["problems"][0].startswith("제목")


def test_no_sheet_does_not_pass_silently():
    st = {"version": "x", "log": [], "tries": {}}
    with pytest.raises(F._Stop):
        F.ph_check_got(st, {"check": {"auto": {"ok": True, "rows": []}, "eye_files": []}}, {}, {})
    assert "look" not in st


def test_sheet_ask_requires_proof_and_carries_lessons():
    st = {"version": "x", "log": [], "tries": {}, "script": {"S": {"title_lines": [["제목"]], "lines": []}}}
    r = F.ph_check_got(st, {"check": {"auto": {"ok": True, "rows": []}, "eye_files": ["x/eye/시트_1초.jpg"]}}, {}, {})
    rv = r["review"][0]
    assert tuple(rv["need"]) == F.SHEET_NEED and "지난 제작 경험" in rv["ask"] and "(#" not in rv["ask"]


def test_every_stage_guide_file_ships_with_the_server():
    """가이드 파일이 저장소에 없으면 제작자 과제의 가이드가 빈 글로 나간다(10-31 라이브 실측: 폴더 자체가 없었다)."""
    assert not [n for n in set(F.STAGE_GUIDE.values()) if not (F.GUIDE_DIR / n).exists()]


def test_lessons_file_stays_small_and_every_stage_exists():
    d = json.loads(F.LESSONS_FILE.read_text(encoding="utf-8"))
    assert set(d) == {"script", "material", "plan", "final"}
    assert all(0 < len(v) <= 15 for v in d.values())
    assert all(F._lessons(k) for k in d)
