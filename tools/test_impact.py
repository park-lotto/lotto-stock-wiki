# -*- coding: utf-8 -*-
"""영향 지도(impact.py) + finish 연결.

핵심: ① 주인 함수를 고쳤는데 소비처가 diff 에도 카드에도 없으면 finish 가 막는다 ② 카드에 '영향 없음: <파일> — 이유' 를 적으면 통과
③ 소비처를 같이 고치면 통과 ④ 주인 함수가 안 바뀐 병합은 검사하지 않는다 ⑤ 새 소비처가 생기면 알린다."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import control
import impact
import track
from test_control import _install, _publish_file, _make_track_commit_with_card, _origin_head  # noqa: F401
from test_track import repo, _Gate, _git  # noqa: F401 (fixture)


def _finish(repo_, name):
    import video_gate
    return track.finish(name, repo=repo_, gate=_Gate(), video_gate=lambda s, b: video_gate.GateResult(True, False, "", []))


# ── 순수 함수 ────────────────────────────────────────────────────

def test_py_names_finds_defs_calls_imports_and_attribute_refs():
    defs, uses = impact.py_names("from a import owner\nimport m\ndef f():\n    owner(1)\n    m.other(2)\n    g = m.third\n")
    assert defs == {"f"} and {"owner", "other", "third"} <= uses


def test_js_names_finds_functions_and_calls():
    defs, uses = impact.js_names("function planClips(a){ return guard(a); }\nconst armSfx = (x) => x;\nplanClips(1);")
    assert {"planClips", "armSfx"} <= defs and {"guard", "planClips"} <= uses


def test_consumers_excludes_owner_and_redefiners():
    idx = {"shopping_shorts/owner.py": ({"render"}, {"x"}),
           "shopping_shorts/user.py": (set(), {"render"}),
           "shopping_shorts/copy.py": ({"render"}, {"render"}),      # 두 벌 — ownership_check 의 몫
           "shopping_shorts/none.py": (set(), {"other"})}
    assert impact.consumers(idx, "render", "shopping_shorts/owner.py") == ["shopping_shorts/user.py"]


def test_no_impact_claims_parses_card_lines():
    cards = [{"body": "## 요청\n영향 없음: shopping_shorts/capcut_draft.py — 반환 형식 그대로\n", "이력": ["10:00 영향 없음: export_bundle.py — 예비 경로만"]}]
    c = impact.no_impact_claims(cards)
    assert "shopping_shorts/capcut_draft.py" in c and "export_bundle.py" in c


def test_spec_marks_customer_ui_consumers_as_approval():
    own = {"판단": [{"이름": "컷", "주인": ["shopping_shorts/static/scene_play.js:planClips"], "소비처": ["화면"], "검사도구": "evf", "과금": False}]}
    idx = {"shopping_shorts/static/scene_play.js": ({"planClips"}, set()),
           "shopping_shorts/static/produce.html": (set(), {"planClips"}),
           "shopping_shorts/screen_clips.py": (set(), {"planClips"})}
    s = impact.spec(idx, own, "planClips")
    assert s["소비처 파일"] == ["shopping_shorts/screen_clips.py", "shopping_shorts/static/produce.html"]
    assert s["승인"].startswith("예") and s["고객 화면 소비처"] == ["shopping_shorts/static/produce.html"]
    assert "영향 없음: shopping_shorts/screen_clips.py" in impact.template(s)


# ── 진짜 저장소: finish 대조 ──────────────────────────────────────────

OWN = {"판단": [{"이름": "컷 계획", "주인": ["shopping_shorts/owner.py:render_cut_plan"], "시그니처": [r"def render_cut_plan\b"],
                "소비처": ["완성본", "캡컷"], "검사도구": "tools/evf.py", "과금": False, "예외": {}}]}


def _seed(repo_):
    _install(repo_)
    _publish_file(repo_, "관제/ownership.json", json.dumps(OWN, ensure_ascii=False))
    _publish_file(repo_, "shopping_shorts/owner.py", "def render_cut_plan(x):\n    return x\n", "주인")
    _publish_file(repo_, "shopping_shorts/user.py", "from owner import render_cut_plan\n\ndef go():\n    return render_cut_plan(1)\n", "소비처")
    _publish_file(repo_, "shopping_shorts/other.py", "def unrelated():\n    return 0\n", "무관")


def test_owner_change_without_consumer_or_note_is_rejected(repo):
    _seed(repo)
    n = control.new_card(repo, "컷 고침", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "컷", n, files={"shopping_shorts/owner.py": "def render_cut_plan(x):\n    return x + 1\n"})
    before = _origin_head(repo)
    with pytest.raises(track.TrackError) as e:
        _finish(repo, "컷")
    msg = str(e.value)
    assert "소비처 1곳이 diff 에도 카드에도 없다" in msg and "shopping_shorts/user.py" in msg and "수리 명세서" in msg
    assert _origin_head(repo) == before

    control.note(repo, n, "영향 없음: shopping_shorts/user.py — 반환 형식 그대로, 값만 +1", printer=lambda *a: None)
    assert _finish(repo, "컷") == 0


def test_owner_change_with_consumer_changed_passes(repo):
    _seed(repo)
    n = control.new_card(repo, "함께 고침", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "함께", n, files={
        "shopping_shorts/owner.py": "def render_cut_plan(x, y=0):\n    return x + y\n",
        "shopping_shorts/user.py": "from owner import render_cut_plan\n\ndef go():\n    return render_cut_plan(1, 2)\n"})
    assert _finish(repo, "함께") == 0


def test_non_owner_change_is_not_checked(repo, capsys):
    _seed(repo)
    n = control.new_card(repo, "무관", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "무관", n, files={"shopping_shorts/other.py": "def unrelated():\n    return 1\n"})
    assert _finish(repo, "무관") == 0
    assert "주인 함수 변경 없음" in capsys.readouterr().out


def test_new_consumer_is_reported(repo, capsys):
    _seed(repo)
    n = control.new_card(repo, "새 소비처", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "새소비", n, files={
        "shopping_shorts/owner.py": "def render_cut_plan(x):\n    return x * 2\n",
        "shopping_shorts/newuser.py": "from owner import render_cut_plan\nprint(render_cut_plan(3))\n"})
    control.note(repo, n, "영향 없음: shopping_shorts/user.py — 값 배율만", printer=lambda *a: None)
    assert _finish(repo, "새소비") == 0
    out = capsys.readouterr().out
    assert "새 소비처" in out and "shopping_shorts/newuser.py" in out
