# -*- coding: utf-8 -*-
"""관제(control.py) + track.py 연결 테스트.

핵심(0순위-A1c "검사가 무엇을 잡는지 먼저 시험한다"):
  ① 관제가 설치된 저장소에서 카드 없는 start/finish 는 **막힌다** — 그리고 막힐 때 main 에 아무것도 안 나간다
  ② 고객 화면·과금 변경은 카드 승인이 없으면 막힌다
  ③ 주인 함수 시그니처가 지도 밖 파일에 새로 생기면 막힌다(기존 두 벌은 안 막는다 — 새로 생긴 것만)
  ④ 미설치 저장소(옛 테스트 저장소)에선 전부 꺼져 기존 동작 그대로
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import control
import ownership_check as oc
import track
from test_track import repo, _Gate, _git, _make_track_commit, _origin_head  # noqa: F401 (fixture)


def _pass_video(stage, br):
    import video_gate
    return video_gate.GateResult(True, False, "", [])


def _finish(repo_, name):
    return track.finish(name, repo=repo_, gate=_Gate(), video_gate=_pass_video)


def _origin_cards(repo_):
    _git(repo_, "fetch", "origin")
    return control.cards_from_ref(repo_)


def _install(repo_):
    control.install(repo_, printer=lambda *a: None)
    assert control.installed(repo_)


def _publish_file(repo_, rel, text, msg="파일"):
    """관제/ 안 파일은 control._publish 로, 그 밖(코드)은 main 폴더에서 커밋·push 로 origin/main 에 올린다."""
    if rel.startswith(control.CTRL_DIR + "/"):
        def mutate(wt):
            p = wt / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        control._publish(repo_, mutate, msg)
        return
    _git(repo_, "fetch", "origin")
    _git(repo_, "merge", "--ff-only", "origin/main")
    p = repo_ / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    _git(repo_, "add", rel)
    _git(repo_, "commit", "-m", msg)
    _git(repo_, "push", "origin", "HEAD:main")


# ── 순수 로직 ────────────────────────────────────────────────────

def test_card_roundtrip_keeps_fields_and_history():
    c = {"번호": 7, "제목": "자막 먼저 뜸", "상태": "수리", "등록": "2026-09-28 10:00", "제보": "사장님",
         "판단 주인": "video_assemble.py:caption_schedule", "분배": "관제, 자막", "됐다의 기준": "시각차 0",
         "승인 필요": "예", "승인": "", "병합": "", "서버 반영": "", "라이브 실측": "", "재발": "4회",
         "요청": "자막이 목소리보다 먼저 뜬다", "이력": ["2026-09-28 10:00 등록"]}
    p = control.parse_card(control.render_card(c), "관제/cards/007-x.md")
    assert p["번호"] == 7 and p["제목"] == "자막 먼저 뜸" and p["상태"] == "수리"
    assert p["분배목록"] == ["관제", "자막"]
    assert p["이력"] == ["2026-09-28 10:00 등록"]
    assert control._body_section(p["body"]) == "자막이 목소리보다 먼저 뜬다"


def test_card_refs_from_commit_messages():
    assert control.card_refs("[관제 12] 고침\n관제#3 · (관제 007)") == {12, 3, 7}
    assert control.card_refs("관제 없음") == set()


@pytest.mark.parametrize("files,diff,expect", [
    (["shopping_shorts/static/produce.html"], "", True),
    (["shopping_shorts/static/scene_play.js"], "", True),
    (["shopping_shorts/video_assemble.py"], "+    x = clean_charge_plan(job)\n", True),
    (["shopping_shorts/store.py"], "-    update_mix_job(a)\n", True),
    (["shopping_shorts/video_assemble.py"], "+    y = 1\n", False),
    (["tools/track.py"], "+    z = 2\n", False),
])
def test_approval_reasons(files, diff, expect):
    assert bool(control.approval_reasons(files, diff, control.DEFAULT_RULES)) is expect


def test_approval_tokens_only_count_inside_shopping_shorts():
    d = ("diff --git a/tools/control.py b/tools/control.py\n--- a/tools/control.py\n+++ b/tools/control.py\n@@ -1 +1 @@\n"
         "+    tokens = ['clean_charge_plan', 'mix_jobs']\n"
         "diff --git a/shopping_shorts/x.py b/shopping_shorts/x.py\n--- a/shopping_shorts/x.py\n+++ b/shopping_shorts/x.py\n@@ -1 +1 @@\n"
         "+    y = 1\n")
    assert control.approval_reasons(["tools/control.py", "shopping_shorts/x.py"], d, control.DEFAULT_RULES) == []
    d2 = d.replace("+    y = 1", "+    y = clean_charge_plan(j)")
    r = control.approval_reasons(["tools/control.py", "shopping_shorts/x.py"], d2, control.DEFAULT_RULES)
    assert r and all("shopping_shorts/x.py" in x for x in r), r        # 토큰 둘(_charge_·clean_charge_plan)에 걸려도 전부 x.py 것


def test_approval_ignores_context_lines_in_diff():
    """바뀌지 않은 문맥 줄에 과금 토큰이 있어도 승인 사유가 아니다(-U0 라 문맥이 없지만 헤더 줄은 있다)."""
    d = "--- a/shopping_shorts/x.py\n+++ b/shopping_shorts/x.py\n@@ -1 +1 @@\n+a = 1\n"
    assert control.approval_reasons(["shopping_shorts/x.py"], d, control.DEFAULT_RULES) == []


def _own(exceptions=None):
    own = {"판단": [{"이름": "컷 계획", "주인": ["shopping_shorts/owner.py:render_cut_plan"],
                   "시그니처": [r"def render_cut_plan\b", r"beat_frames\s*="], "예외": exceptions or {}}]}
    for j in own["판단"]:
        j["_owner_files"] = ["shopping_shorts/owner.py"]
        import re
        j["_re"] = [re.compile(s) for s in j["시그니처"]]
    return own


def test_ownership_flags_only_new_foreign_signatures():
    own = _own()
    # 주인 파일 안은 아무것도 아니다
    assert oc.foreign_hits("shopping_shorts/owner.py", "def render_cut_plan(): pass", own) == []
    # 남의 파일에 새로 생김 → 빨강
    hits = oc.compare_texts("shopping_shorts/other.py", "x = 1\n", "def render_cut_plan(): pass\n", own)
    assert [h["sig"] for h in hits] == [r"def render_cut_plan\b"]
    # 이미 있던 두 벌은 새 것이 아니다(카드로 줄인다)
    assert oc.compare_texts("shopping_shorts/other.py", "def render_cut_plan(): pass\n", "def render_cut_plan(): return 1\n", own) == []
    # 예외에 사유가 있으면 통과
    own2 = _own({"shopping_shorts/other.py": "예비 계획 — 카드 002"})
    assert oc.compare_texts("shopping_shorts/other.py", "", "def render_cut_plan(): pass\n", own2) == []


def test_ownership_scope_skips_tests_and_foreign_dirs():
    assert oc.in_scope("shopping_shorts/app.py", None)
    assert oc.in_scope("tools/control.py", None)
    assert not oc.in_scope("shopping_shorts/tests/test_x.py", None)
    assert not oc.in_scope("tools/test_control.py", None)
    assert not oc.in_scope("dashboard/app.py", None)
    assert not oc.in_scope("shopping_shorts/data/x.json", None)


def test_claim_conflicts_detects_other_tracks_targets():
    claims = {"shopping_shorts/app.py": {"track": "A", "card": 3},
              "shopping_shorts/mix.py:clean_route": {"track": "B", "card": 4},
              "tools/x.py": {"track": "me", "card": 5}}
    got = control.claim_conflicts(claims, "me", ["shopping_shorts/app.py", "shopping_shorts/mix.py", "tools/x.py"])
    assert sorted(t for t, _ in got) == ["shopping_shorts/app.py", "shopping_shorts/mix.py:clean_route"]


def test_board_groups_by_state_and_links_cards():
    cards = [control.parse_card(control.render_card({"번호": 1, "제목": "가", "상태": "등록", "승인 필요": "예", "이력": []}), "관제/cards/001-가.md"),
             control.parse_card(control.render_card({"번호": 2, "제목": "나", "상태": "완료", "이력": ["x 병합"]}), "관제/cards/002-나.md")]
    b = control.render_board(cards, now="지금")
    assert "## 등록 (1)" in b and "## 완료 (1)" in b
    assert b.index("## 등록") < b.index("## 완료"), "완료는 맨 아래"
    assert "[001](cards/001-가.md)" in b and "**필요**" in b


# ── 진짜 git 저장소 ───────────────────────────────────────────────

def test_uninstalled_repo_keeps_old_behaviour(repo):
    """관제가 없는 저장소: 카드 없이 start·finish 다 된다(기존 테스트 60여 개가 이 길이다)."""
    assert not control.installed(repo)
    _make_track_commit(repo, "옛트랙")
    assert _finish(repo, "옛트랙") == 0
    assert _origin_head(repo) != ""


def test_install_puts_control_folder_on_main_without_touching_main_folder(repo):
    marker = repo / "app.py"
    marker.write_text("VALUE = 999  # 다른 세션이 편집 중\n", encoding="utf-8")
    _install(repo)
    assert marker.read_text(encoding="utf-8").startswith("VALUE = 999"), "main 폴더의 남의 편집을 건드리면 안 된다"
    files = control._tree_files(repo, "origin/main", "관제")
    assert "관제/cards/.keep" in files and "관제/rules.json" in files and "관제/BOARD.md" in files
    assert not list((repo / ".tracks").glob("_card-*")), "임시 폴더는 치워야 한다"


def test_start_requires_card_when_installed(repo):
    _install(repo)
    with pytest.raises(track.TrackError) as e:
        track.start("새트랙", repo=repo)
    assert "control.py new" in str(e.value)
    assert not track.worktree_path("새트랙", repo).exists()
    with pytest.raises(track.TrackError):
        track.start("새트랙", repo=repo, card=99)          # 없는 카드


def test_start_with_card_links_track_on_main(repo):
    _install(repo)
    n = control.new_card(repo, "정지 컷 채우기", reporter="사장님", owner="scene_play.js:planClips", done="정지 컷 0",
                         printer=lambda *a: None)
    assert n == 1
    track.start("정지컷", repo=repo, card=n)
    c = control.find_card(_origin_cards(repo), n)
    assert "정지컷" in c["분배목록"] and c["상태"] == "분배"
    assert any("분배 → 정지컷" in h for h in c["이력"])


def test_card_numbers_increase_and_files_are_named_by_number(repo):
    _install(repo)
    a = control.new_card(repo, "첫 카드", printer=lambda *a: None)
    b = control.new_card(repo, "둘째/카드: 특수문자", printer=lambda *a: None)
    assert (a, b) == (1, 2)
    paths = [c["path"] for c in _origin_cards(repo)]
    assert paths[0].startswith("관제/cards/001-") and paths[1].startswith("관제/cards/002-")
    assert "/" not in Path(paths[1]).name.replace(".md", "") and ":" not in paths[1]


def test_finish_without_card_fails_and_pushes_nothing(repo):
    """트랙을 먼저 열고(카드 없이 — 관제 전에 만든 옛 트랙 흉내) 관제를 설치하면 finish 가 막히고 main 은 그대로."""
    _make_track_commit(repo, "옛트랙")
    _install(repo)
    before = _origin_head(repo)
    with pytest.raises(track.TrackError) as e:
        _finish(repo, "옛트랙")
    assert "카드가 없다" in str(e.value)
    assert _origin_head(repo) == before
    assert track.worktree_path("옛트랙", repo).exists()


def test_finish_with_linked_card_records_merge(repo):
    _install(repo)
    n = control.new_card(repo, "값 바꾸기", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "값", n)
    assert _finish(repo, "값") == 0
    c = control.find_card(_origin_cards(repo), n)
    assert c["상태"] == "병합"
    assert c["병합"] and "(값)" in c["병합"]
    assert any("반영됨·미검증" in h for h in c["이력"]), "병합은 '됐다'가 아니다 — 라이브 실측 전"


def test_commit_message_reference_links_a_card(repo):
    """분배가 안 된 카드라도 커밋 메시지에 '관제 N' 이 있으면 그 카드로 병합한다."""
    _make_track_commit(repo, "옛트랙")             # 카드 없이 열린 트랙
    _install(repo)
    n = control.new_card(repo, "메시지로 연결", printer=lambda *a: None)
    wt = track.worktree_path("옛트랙", repo)
    (wt / "app.py").write_text("VALUE = 3\n", encoding="utf-8")
    _git(wt, "add", "app.py")
    _git(wt, "commit", "-m", "[관제 %d] 값 3" % n)
    assert _finish(repo, "옛트랙") == 0
    assert control.find_card(_origin_cards(repo), n)["상태"] == "병합"


def _make_track_commit_with_card(repo_, name, card, files=None, msg=None):
    track.start(name, repo=repo_, card=card)
    wt = track.worktree_path(name, repo_)
    _git(wt, "config", "user.email", "t@t.t")
    _git(wt, "config", "user.name", "t")
    for rel, body in (files or {"app.py": "VALUE = 2\n"}).items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        _git(wt, "add", rel)
    _git(wt, "commit", "-m", msg or f"{name} 작업")
    return wt


def test_customer_ui_change_needs_card_approval(repo):
    _install(repo)
    n = control.new_card(repo, "버튼 색", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "버튼", n, files={"shopping_shorts/static/produce.html": "<b>x</b>\n"})
    before = _origin_head(repo)
    with pytest.raises(track.TrackError) as e:
        _finish(repo, "버튼")
    assert "승인이 없다" in str(e.value) and "고객 화면 변경" in str(e.value)
    assert _origin_head(repo) == before, "승인 없는 고객 화면 변경이 main 에 나가면 안 된다"

    control.approve(repo, n, "사장님 구두", printer=lambda *a: None)
    assert _finish(repo, "버튼") == 0
    c = control.find_card(_origin_cards(repo), n)
    assert c["승인"].endswith("사장님 구두") and c["상태"] == "병합"


def test_billing_token_change_needs_approval(repo):
    _install(repo)
    n = control.new_card(repo, "과금", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "과금", n, files={"shopping_shorts/mix.py": "def f():\n    return clean_charge_plan(1)\n"})
    with pytest.raises(track.TrackError) as e:
        _finish(repo, "과금")
    assert "과금 관련 코드 변경" in str(e.value)


def test_new_duplicate_of_owner_signature_is_rejected_but_existing_is_not(repo):
    _install(repo)
    own = {"판단": [{"이름": "컷 계획", "주인": ["shopping_shorts/owner.py:render_cut_plan"],
                   "시그니처": [r"def render_cut_plan\b"], "소비처": ["렌더"], "예외": {}}]}
    _publish_file(repo, "관제/ownership.json", json.dumps(own, ensure_ascii=False))
    # 이미 있는 두 벌(legacy.py)은 main 에 먼저 둔다
    _publish_file(repo, "shopping_shorts/legacy.py", "def render_cut_plan():\n    return 0\n", "옛 두 벌")
    n = control.new_card(repo, "컷", printer=lambda *a: None)

    # 기존 두 벌을 고치는 것만은 통과(새로 생긴 게 아니다)
    _make_track_commit_with_card(repo, "고침", n, files={"shopping_shorts/legacy.py": "def render_cut_plan():\n    return 1\n"})
    assert _finish(repo, "고침") == 0

    # 새 파일에 같은 판단을 또 적으면 거절
    _make_track_commit_with_card(repo, "새벌", n, files={"shopping_shorts/copy.py": "def render_cut_plan():\n    return 2\n"})
    before = _origin_head(repo)
    with pytest.raises(track.TrackError) as e:
        _finish(repo, "새벌")
    assert "새로** 나타났다" in str(e.value) and "shopping_shorts/copy.py" in str(e.value)
    assert _origin_head(repo) == before

    # 예외에 사유를 적으면(main 의 지도에) 통과
    own["판단"][0]["예외"] = {"shopping_shorts/copy.py": "시험용 예외 — 카드 %d" % n}
    _publish_file(repo, "관제/ownership.json", json.dumps(own, ensure_ascii=False))
    assert _finish(repo, "새벌") == 0


def test_ownership_check_crash_fails_closed(repo, monkeypatch):
    _install(repo)
    _publish_file(repo, "관제/ownership.json", json.dumps({"판단": []}, ensure_ascii=False))
    n = control.new_card(repo, "x", printer=lambda *a: None)
    _make_track_commit_with_card(repo, "x", n)
    monkeypatch.setattr(oc, "compare_refs", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(track.TrackError) as e:
        _finish(repo, "x")
    assert "검사 도구가 죽었다" in str(e.value)


def test_claim_conflict_is_reported_not_blocking(repo, capsys):
    _install(repo)
    a = control.new_card(repo, "A", printer=lambda *a: None)
    b = control.new_card(repo, "B", printer=lambda *a: None)
    control.claim(repo, "다른트랙", a, ["app.py"], printer=lambda *a: None)
    _make_track_commit_with_card(repo, "나", b)
    assert _finish(repo, "나") == 0
    out = capsys.readouterr().out
    assert "선점 충돌" in out and "다른트랙" in out


def test_claim_does_not_steal_another_tracks_target(repo):
    _install(repo)
    a = control.new_card(repo, "A", printer=lambda *a: None)
    control.claim(repo, "갑", a, ["shopping_shorts/app.py:render"], printer=lambda *a: None)
    taken = control.claim(repo, "을", a, ["shopping_shorts/app.py:render"], printer=lambda *a: None)
    assert taken and taken[0][1]["track"] == "갑"
    assert control.load_claims(repo)["shopping_shorts/app.py:render"]["track"] == "갑"
    control.release(repo, "갑", printer=lambda *a: None)
    assert control.load_claims(repo) == {}


def test_list_shows_card_numbers_per_track(repo, capsys):
    _install(repo)
    n = control.new_card(repo, "목록", printer=lambda *a: None)
    track.start("목록트랙", repo=repo, card=n)
    track.list_tracks(repo)
    out = capsys.readouterr().out
    assert "목록트랙" in out and "카드 %03d" % n in out
