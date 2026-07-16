"""track.py 테스트.

핵심(설계 §11이 '이 설계의 심장'이라 부른 것): **게이트가 실패하면 커밋이
생기지 않는가.** 커밋되는 순간 post-commit이 무조건 push하므로, 커밋이 생기면
게이트는 존재 이유가 없다. 그래서 아래 테스트들은 진짜 git 저장소를 만들어
`git log`와 훅 발동 여부를 직접 확인한다 (가짜 mock으로는 이걸 증명 못 한다).
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import track


# ── 순수 로직 ────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["a/b", "a\\b", "..", "../x", ".hidden", "a b", "", "  "])
def test_validate_name_rejects_path_escapes(bad):
    with pytest.raises(track.TrackError):
        track.validate_name(bad)


def test_validate_name_accepts_korean():
    assert track.validate_name("보이스") == "보이스"


def test_is_ignorable_covers_bot_outputs():
    assert track.is_ignorable("raw/yt/foo.md")
    assert track.is_ignorable("shopping_shorts/data/app.db")
    assert track.is_ignorable("out/card.html")
    assert track.is_ignorable("x/__pycache__/y.pyc")


def test_is_ignorable_does_not_swallow_code():
    assert not track.is_ignorable("shopping_shorts/app.py")
    assert not track.is_ignorable("tools/track.py")
    # 'data'가 파일명 일부인 코드까지 무시하면 안 된다
    assert not track.is_ignorable("shopping_shorts/data_utils.py")


def test_parse_status_extracts_paths_and_renames():
    porcelain = ' M shopping_shorts/app.py\n?? new.py\nR  old.py -> new2.py\n'
    assert track.parse_status(porcelain) == ["shopping_shorts/app.py", "new.py", "new2.py"]


# ── 진짜 git 저장소 ───────────────────────────────────────────────

def _git(cwd, *args):
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert p.returncode == 0, f"git {' '.join(args)} 실패:\n{p.stdout}{p.stderr}"
    return p.stdout


@pytest.fixture
def repo(tmp_path):
    """origin(bare) + main 워킹트리. post-commit 훅은 발동을 파일로 기록한다."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))

    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@t.t")
    _git(r, "config", "user.name", "t")
    _git(r, "remote", "add", "origin", str(origin))
    (r / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-m", "init")
    _git(r, "push", "-u", "origin", "main")

    # 실제 저장소처럼 post-commit이 무조건 뭔가 한다 — 발동하면 흔적이 남는다
    hooks = Path(_git(r, "rev-parse", "--git-path", "hooks").strip())
    if not hooks.is_absolute():
        hooks = r / hooks
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "post-commit").write_text(
        "#!/bin/sh\necho fired >> \"$(git rev-parse --show-toplevel)/../push_log\"\n",
        encoding="utf-8",
    )
    (hooks / "post-commit").chmod(0o755)
    return r


class _Gate:
    """게이트 스텁 — snapshot은 상수, compare는 미리 정한 문제를 낸다."""

    def __init__(self, problems=()):
        self.problems = list(problems)
        self.snapshots = 0

    def snapshot(self, cwd=None, **kw):
        self.snapshots += 1
        return {"compile_ok": True, "import_ok": True, "pytest_rc": 0,
                "failed": [], "import_out": "", "pytest_out": ""}

    def baseline_warnings(self, before):
        return []

    def compare(self, before, after):
        return self.problems


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").strip()


def _make_track_commit(repo, name, body="VALUE = 2\n"):
    track.start(name, repo=repo)
    wt = track.worktree_path(name, repo)
    _git(wt, "config", "user.email", "t@t.t")
    _git(wt, "config", "user.name", "t")
    (wt / "app.py").write_text(body, encoding="utf-8")
    _git(wt, "add", "app.py")
    _git(wt, "commit", "-m", f"{name} 작업")
    return wt


def test_start_creates_folder_and_branch(repo):
    track.start("보이스", repo=repo)
    assert track.worktree_path("보이스", repo).exists()
    assert track.branch_exists(repo, "track/보이스")


def test_track_folder_lives_inside_the_project(repo):
    """프로젝트 밖(형제 폴더)이 아니라 안에 둔다 — 사장님이 찾기 쉬운 곳."""
    track.start("보이스", repo=repo)
    wt = track.worktree_path("보이스", repo)
    assert wt.parent == repo.resolve() / ".tracks"
    assert repo.resolve() in wt.parents, "프로젝트 밖으로 나가면 안 된다"


def test_track_folder_does_not_pollute_main_status(repo):
    """★프로젝트 안에 두면 main 워킹트리가 트랙 폴더(883MB·1만여 파일)를 untracked로 본다.
    .gitignore에 의존하지 않고 도구 자체가 무시해야 한다 — .gitignore가 없는
    클론·테스트 저장소에서도 안전해야 하니까."""
    track.start("보이스", repo=repo)
    assert track.dirty_code_files(repo) == [], \
        "★트랙 폴더가 main의 '커밋 안 된 코드'로 잡힌다 = finish가 남의 작업으로 오인"


def test_stage_also_lives_inside_tracks_dir(repo):
    _make_track_commit(repo, "보이스")
    seen = []

    class Watcher(_Gate):
        def snapshot(self, cwd=None, **kw):
            seen.append(Path(cwd).resolve())
            return super().snapshot(cwd, **kw)

    track.finish("보이스", repo=repo, gate=Watcher())
    for cwd in seen:
        assert cwd.parent == repo.resolve() / ".tracks", f"stage가 엉뚱한 데 있다: {cwd}"


def test_start_never_points_upstream_at_main(repo):
    """★`worktree add -b <br> origin/main`은 upstream을 origin/main으로 박는다 →
    post-commit의 인자 없는 push가 '트랙 브랜치를 main으로'가 된다(게이트 우회)."""
    track.start("보이스", repo=repo)
    up = track.upstream_of(track.worktree_path("보이스", repo))
    assert up != "origin/main", "★트랙 커밋이 post-commit으로 main에 직행하는 경로가 열렸다"
    assert up in (None, "origin/track/보이스"), f"예상 밖 upstream: {up}"


def test_track_commit_cannot_reach_main_even_without_push_default_simple(repo):
    """지금 안전한 건 push.default가 unset(=simple)이라 git이 거절해주기 때문일 뿐이다.
    누가 push.default=upstream으로 바꿔도 main은 안전해야 한다 — 우연에 기대지 않는다."""
    track.start("보이스", repo=repo)
    wt = track.worktree_path("보이스", repo)
    _git(wt, "config", "user.email", "t@t.t")
    _git(wt, "config", "user.name", "t")
    _git(wt, "config", "push.default", "upstream")  # simple의 보호를 벗긴다
    origin_before = _origin_head(repo)

    (wt / "app.py").write_text("트랙의 미완성 코드\n", encoding="utf-8")
    _git(wt, "add", "app.py")
    _git(wt, "commit", "-m", "트랙 작업")
    subprocess.run(["git", "push"], cwd=str(wt), capture_output=True)  # post-commit이 하는 짓

    assert _origin_head(repo) == origin_before, \
        "★트랙 커밋이 게이트를 건너뛰고 main으로 직행했다"


def test_start_leaves_no_main_upstream_when_push_fails(repo):
    """오프라인·원격장애로 `push -u`가 실패하는 경로. 그때 upstream이 origin/main으로
    남으면 post-commit이 트랙 커밋을 곧장 main으로 민다 — push 성공 경로만 보면 안 보인다."""
    _git(repo, "remote", "set-url", "origin", str(repo.parent / "없는저장소.git"))
    track.start("보이스", repo=repo)
    up = track.upstream_of(track.worktree_path("보이스", repo))
    assert up != "origin/main", "★원격이 죽으면 트랙 커밋이 main으로 직행한다"
    assert up is None, f"원격에 못 올렸으면 upstream은 없어야 한다: {up}"


def test_start_makes_output_safe(repo, monkeypatch):
    """main()에서만 안전화하면 코드가 start()를 직접 부를 때 cp949에서 터진다.
    실측: 트랙 이전 스크립트가 worktree를 만든 직후 '✅' print에서 크래시 —
    폴더는 생기고 예외는 나는 어정쩡한 상태가 됐다."""
    called = []
    monkeypatch.setattr(track.merge_gate, "make_output_safe", lambda: called.append("start"))
    track.start("보이스", repo=repo)
    assert called == ["start"], "start()가 출력 안전화를 안 했다"


def test_finish_makes_output_safe(repo, monkeypatch):
    _make_track_commit(repo, "보이스")
    called = []
    monkeypatch.setattr(track.merge_gate, "make_output_safe", lambda: called.append("finish"))
    track.finish("보이스", repo=repo, gate=_Gate())
    assert "finish" in called, "finish()가 출력 안전화를 안 했다"


def test_list_makes_output_safe(repo, monkeypatch):
    called = []
    monkeypatch.setattr(track.merge_gate, "make_output_safe", lambda: called.append("list"))
    track.list_tracks(repo=repo)
    assert called == ["list"], "list_tracks()가 출력 안전화를 안 했다"


def test_main_worktree_found_from_inside_a_track_folder(repo):
    """★finish는 main 워크트리를 알아야 한다. __file__ 기준으로 잡으면 트랙 폴더 안에서
    부를 때 그 폴더의 복사본을 가리켜 깨진다(2026-07-16 실측: worktree_path가 존재하지도
    않는 .tracks/lotto-<이름>을 가리켰다). git에게 물어야 한다."""
    track.start("보이스", repo=repo)
    wt = track.worktree_path("보이스", repo)
    assert track.main_worktree(wt) == repo.resolve(), "트랙 폴더 안에서 main을 못 찾는다"
    assert track.main_worktree(repo) == repo.resolve()
    sub = wt / "sub" / "deep"
    sub.mkdir(parents=True)
    assert track.main_worktree(sub) == repo.resolve(), "하위폴더에서도"


def test_finish_keeps_the_track_folder(repo):
    """★설계는 '태스크 단위로 자주 병합'을 요구한다. 병합할 때마다 883MB 체크아웃을
    지웠다 다시 만들면 그 요구와 정면으로 안 맞는다. 폴더는 남기고 재사용한다."""
    _make_track_commit(repo, "보이스")
    track.finish("보이스", repo=repo, gate=_Gate())
    assert track.worktree_path("보이스", repo).exists(), "★폴더를 또 지웠다"
    assert track.branch_exists(repo, "track/보이스"), "★브랜치를 또 지웠다"


def test_finish_levels_track_branch_with_new_main(repo):
    """병합 후 트랙 브랜치는 새 main과 같은 자리에 서야 다음 작업을 바로 얹는다."""
    _make_track_commit(repo, "보이스")
    track.finish("보이스", repo=repo, gate=_Gate())
    assert track.ahead_count(repo, "track/보이스") == 0, "★병합했는데 아직 앞서 있다"
    wt = track.worktree_path("보이스", repo)
    assert _git(wt, "rev-parse", "HEAD").strip() == _origin_head(repo)


def test_finish_does_not_destroy_ignorable_edits_in_track_folder(repo):
    """★ff 병합이어야 하는 이유 — `reset --hard`로 맞추면 안 되는 근거.

    함정: **미추적 파일로는 이걸 증명 못 한다.** reset --hard는 미추적 파일을 안 지우므로
    그런 테스트는 reset 뮤턴트가 그대로 살아남는다(실측으로 확인함 — 내 첫 테스트가 딱 그
    죽은 테스트였다). 진짜 차이는 **추적되면서 무시대상인 파일의 수정분**이다:
    _preflight가 통과시키고 → reset --hard는 조용히 날리고 → ff는 보존한다.
    """
    wt = _make_track_commit(repo, "보이스")
    raw = wt / "raw"
    raw.mkdir()
    (raw / "크롤.md").write_text("커밋된 크롤 데이터\n", encoding="utf-8")
    _git(wt, "add", "raw/크롤.md")
    _git(wt, "commit", "-m", "크롤 데이터 추가")
    # 이제 추적되는 파일을 고친다 → " M raw/크롤.md" = _preflight가 무시대상으로 통과시킴
    (raw / "크롤.md").write_text("작업 중인 수정분\n", encoding="utf-8")

    track.finish("보이스", repo=repo, gate=_Gate())

    assert (raw / "크롤.md").read_text(encoding="utf-8") == "작업 중인 수정분\n", \
        "★무시대상 수정분이 날아갔다 — reset --hard로 되돌아갔나?"


def test_close_removes_folder_and_branch(repo):
    _make_track_commit(repo, "보이스")
    track.finish("보이스", repo=repo, gate=_Gate())
    track.close("보이스", repo=repo)
    assert not track.worktree_path("보이스", repo).exists()
    assert not track.branch_exists(repo, "track/보이스")


def test_close_refuses_to_throw_away_unmerged_work(repo):
    """★close는 파괴적이다. 아직 main에 안 들어간 커밋이 있으면 막아야 한다."""
    _make_track_commit(repo, "보이스")          # 커밋만 하고 finish 안 함
    with pytest.raises(track.TrackError, match="병합 안 된"):
        track.close("보이스", repo=repo)
    assert track.worktree_path("보이스", repo).exists(), "막았으면 폴더도 그대로여야"


def test_start_refuses_duplicate(repo):
    track.start("보이스", repo=repo)
    with pytest.raises(track.TrackError, match="이미 있는"):
        track.start("보이스", repo=repo)


def _origin_head(repo):
    return _git(repo, "rev-parse", "origin/main").strip()


def test_finish_commits_when_gate_passes(repo):
    _make_track_commit(repo, "보이스")
    before = _head(repo)
    rc = track.finish("보이스", repo=repo, gate=_Gate())
    assert rc == 0
    assert _origin_head(repo) != before, "게이트 통과했으면 origin/main에 병합이 올라가야 한다"
    assert (repo / "app.py").read_text(encoding="utf-8") == "VALUE = 2\n", "원본 폴더도 당겨졌어야"
    assert track.worktree_path("보이스", repo).exists(), "폴더는 남아야 한다(close가 지운다)"


# ★★ 이 설계의 심장 ★★
def test_finish_pushes_nothing_when_gate_fails(repo):
    _make_track_commit(repo, "보이스")
    before_main = _head(repo)
    before_origin = _origin_head(repo)
    push_log = repo.parent / "push_log"
    push_log.unlink(missing_ok=True)  # 트랙 폴더의 셋업 커밋이 이미 훅을 때렸다

    with pytest.raises(track.TrackError, match="게이트 실패"):
        track.finish("보이스", repo=repo, gate=_Gate(problems=["새로 깨진 테스트 1건"]))

    assert _origin_head(repo) == before_origin, "★게이트 실패인데 라이브(origin/main)로 나갔다 = 설계가 죽었다"
    assert _head(repo) == before_main, "★게이트 실패인데 main 폴더가 움직였다"
    assert not push_log.exists(), "★커밋이 없어야 하는데 post-commit이 발동했다"


def test_finish_gate_failure_leaves_no_merge_anywhere(repo):
    _make_track_commit(repo, "보이스")
    with pytest.raises(track.TrackError):
        track.finish("보이스", repo=repo, gate=_Gate(problems=["x"]))
    # 부분 병합이 어디에도 남으면 안 된다 — 남으면 다른 세션이 그걸 커밋한다
    assert not (track.tracks_dir(repo) / "_merge-보이스").exists()
    rc, _ = track.run(["git", "rev-parse", "--verify", "--quiet", "MERGE_HEAD"], repo)
    assert rc != 0
    assert (repo / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n", "main 폴더가 오염됐다"


def test_finish_never_touches_main_folder_during_gate(repo):
    """★main 폴더에서 병합하면 게이트가 도는 수 분 동안 '반쯤 병합된' 상태가 되고,
    그때 옆 세션이 커밋하면 그 반쪽을 담아 push한다 — 흡수 재발. 그래서 stage에서 한다."""
    _make_track_commit(repo, "보이스")
    seen = []

    class Watcher(_Gate):
        def snapshot(self, cwd=None, **kw):
            # 게이트가 도는 순간의 main 폴더 상태를 엿본다
            seen.append((Path(cwd).resolve(), (repo / "app.py").read_text(encoding="utf-8")))
            return super().snapshot(cwd, **kw)

    track.finish("보이스", repo=repo, gate=Watcher())
    for cwd, main_content in seen:
        assert cwd != repo.resolve(), "게이트가 main 폴더에서 돌았다"
        assert main_content == "VALUE = 1\n", "게이트 도는 동안 main 폴더가 병합 상태였다"


def test_stage_folder_is_removed_after_success(repo):
    _make_track_commit(repo, "보이스")
    track.finish("보이스", repo=repo, gate=_Gate())
    assert not (track.tracks_dir(repo) / "_merge-보이스").exists()


def test_stage_folder_is_removed_after_gate_failure(repo):
    _make_track_commit(repo, "보이스")
    with pytest.raises(track.TrackError):
        track.finish("보이스", repo=repo, gate=_Gate(problems=["x"]))
    assert not (track.tracks_dir(repo) / "_merge-보이스").exists(), "임시 폴더가 쌓이면 디스크가 샌다"


def test_finish_gate_failure_keeps_track_folder(repo):
    _make_track_commit(repo, "보이스")
    with pytest.raises(track.TrackError):
        track.finish("보이스", repo=repo, gate=_Gate(problems=["x"]))
    assert track.worktree_path("보이스", repo).exists(), "작업을 날리면 안 된다"


def test_finish_runs_gate_before_and_after_merge(repo):
    _make_track_commit(repo, "보이스")
    g = _Gate()
    track.finish("보이스", repo=repo, gate=g)
    assert g.snapshots == 2, "기준선(병합 전)과 병합 후 두 번 찍어야 비교가 된다"


def test_finish_refuses_dirty_track_folder(repo):
    wt = _make_track_commit(repo, "보이스")
    (wt / "app.py").write_text("미완성\n", encoding="utf-8")
    with pytest.raises(track.TrackError, match="dirty"):
        track.finish("보이스", repo=repo, gate=_Gate())


def test_finish_works_while_other_sessions_have_dirty_main(repo):
    """★전환기의 핵심: 다른 세션 5개가 main 폴더에서 계속 일하는 중에도 병합돼야 한다.
    main을 건드리지 않으니 남의 미커밋 코드는 병합에 딸려가지도, 병합을 막지도 않는다."""
    _make_track_commit(repo, "보이스")
    (repo / "other.py").write_text("옆 세션의 미완성 코드\n", encoding="utf-8")

    rc = track.finish("보이스", repo=repo, gate=_Gate())

    assert rc == 0
    merged = _git(repo, "show", "origin/main:app.py")
    assert merged == "VALUE = 2\n"
    rc2, _ = track.run(["git", "cat-file", "-e", "origin/main:other.py"], repo)
    assert rc2 != 0, "★옆 세션의 미커밋 코드가 병합에 딸려갔다 = 흡수 재발"
    assert (repo / "other.py").exists(), "남의 작업을 지우면 안 된다"


def test_finish_tolerates_bot_output_dirty_in_main(repo):
    _make_track_commit(repo, "보이스")
    (repo / "raw").mkdir()
    (repo / "raw" / "crawl.md").write_text("크롤봇이 방금 쓴 것\n", encoding="utf-8")
    rc = track.finish("보이스", repo=repo, gate=_Gate())
    assert rc == 0, "크롤봇 산출물 때문에 병합이 막히면 게이트가 영원히 안 돈다"


def test_finish_retries_when_another_track_wins_the_race(repo):
    """두 트랙이 동시에 끝내면 git이 두 번째 push를 거절한다(원자적 신호등).
    사람이 '기다려'라고 말할 필요 없이 최신 main 위에서 다시 시도한다."""
    _make_track_commit(repo, "보이스")
    calls = {"n": 0}
    real_run = track.run

    def flaky_run(cmd, cwd, check=False):
        if cmd[:2] == ["git", "push"] and calls["n"] == 0:
            calls["n"] += 1
            return 1, "! [rejected]  HEAD -> main (non-fast-forward)\nfatal: failed to push"
        return real_run(cmd, cwd, check)

    track.run = flaky_run
    try:
        rc = track.finish("보이스", repo=repo, gate=_Gate())
    finally:
        track.run = real_run

    assert rc == 0, "거절당했으면 최신 main 위에서 다시 시도했어야 한다"
    assert calls["n"] == 1
    assert _git(repo, "show", "origin/main:app.py") == "VALUE = 2\n"


def test_is_race_detects_push_rejection():
    assert track._is_race("! [rejected] main -> main (non-fast-forward)")
    assert track._is_race("hint: Updates were rejected... fetch first")
    assert not track._is_race("fatal: could not read from remote repository")


def test_finish_aborts_and_reports_on_conflict(repo):
    _make_track_commit(repo, "보이스", body="보이스 버전\n")
    # main에서 같은 줄을 다르게 커밋 → 충돌
    (repo / "app.py").write_text("main 버전\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "main 쪽 변경")
    _git(repo, "push", "origin", "main")  # 실제로는 post-commit이 무조건 push한다
    origin_before = _origin_head(repo)

    with pytest.raises(track.TrackError, match="충돌"):
        track.finish("보이스", repo=repo, gate=_Gate())

    # ⚠️ repo의 MERGE_HEAD를 확인하는 건 죽은 검사다 — 병합은 stage에서 하므로
    #    repo엔 애초에 생길 수 없다. 진짜로 지켜야 할 것만 검사한다.
    assert _origin_head(repo) == origin_before, "충돌인데 라이브로 나갔다"
    assert not (track.tracks_dir(repo) / "_merge-보이스").exists(), \
        "충돌 상태의 stage가 남으면 디스크가 새고, 다음 finish가 그걸 주워 쓴다"
    assert track.worktree_path("보이스", repo).exists(), "충돌 났다고 작업을 날리면 안 된다"


def test_finish_conflict_does_not_run_gate(repo):
    _make_track_commit(repo, "보이스", body="보이스 버전\n")
    (repo / "app.py").write_text("main 버전\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "main 쪽 변경")
    _git(repo, "push", "origin", "main")  # 실제로는 post-commit이 무조건 push한다
    g = _Gate()
    with pytest.raises(track.TrackError):
        track.finish("보이스", repo=repo, gate=g)
    assert g.snapshots == 1, "충돌 상태에서 게이트를 돌리면 시간만 버린다(기준선만 찍힘)"


def test_finish_handles_nothing_to_merge(repo):
    track.start("보이스", repo=repo)  # 커밋 없이 바로 끝
    head = _head(repo)
    rc = track.finish("보이스", repo=repo, gate=_Gate())
    assert rc == 0
    assert _head(repo) == head, "병합할 게 없으면 빈 커밋을 만들면 안 된다"


def test_finish_rejects_unknown_track(repo):
    with pytest.raises(track.TrackError, match="폴더가 없다"):
        track.finish("없는트랙", repo=repo, gate=_Gate())


def test_ahead_count_tracks_divergence(repo):
    _make_track_commit(repo, "보이스")
    assert track.ahead_count(repo, "track/보이스") == 1
