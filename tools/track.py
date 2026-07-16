"""트랙별 작업 폴더 — 시작 / 끝 / 목록.

설계: docs/superpowers/specs/2026-07-15-트랙폴더-병합게이트-design.md

한 PC에서 6개 세션이 같은 폴더·같은 인덱스로 일하면 먼저 커밋하는 세션이
남의 미완성 코드를 **물리적으로** 자기 커밋에 담는다(흡수). 락으로는 못 막는다
— 락은 '언제 커밋하나'만 조율하고 '파일 안에 뭐가 들었나'는 못 바꾼다.
그래서 트랙마다 자기 폴더(worktree)+자기 브랜치를 준다.

폴더를 나누면 흡수는 사라지지만 **의미적 충돌**이 커진다(A가 함수명을 바꾸고
B가 옛 버전을 보고 그 함수를 부르면, 텍스트가 안 겹쳐 깨끗이 병합되고 main이
ImportError). 그래서 병합에 게이트가 붙는다 — merge_gate.py.

★ post-commit이 무조건 `git push`다. 그래서 병합은 반드시
  `merge --no-ff --no-commit`(커밋 없음 → 훅 안 돎) → 게이트 → 통과해야 commit.
  순진하게 merge하면 게이트가 돌기 전에 이미 라이브다.

사용:
    py tools/track.py start 보이스
    py tools/track.py finish 보이스
    py tools/track.py list
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_gate

BRANCH_PREFIX = "track/"
MAIN_BRANCH = "main"


def _sh(cmd, cwd):
    """cwd가 없어도 크래시하지 않는다 — 지워진 트랙 폴더를 가리킬 수 있다(finish 직후 등).
    subprocess는 없는 cwd에 NotADirectoryError를 던지는데, 그건 호출자가 다룰 수 없다."""
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except (NotADirectoryError, FileNotFoundError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main_worktree(cwd=None):
    """이 저장소의 **main 워크트리**를 찾는다 — git에게 물어서.

    ★`__file__` 기준으로 잡으면 안 된다. 트랙 폴더에는 tools/track.py의 복사본이 있어서,
    거기서 부르면 BASE가 그 트랙 폴더가 되고 `worktree_path`가 존재하지도 않는
    `.tracks/<이름>/.tracks/<이름>`을 가리킨다 → finish가 "트랙 폴더가 없다"로 깨진다
    (2026-07-16 실측). CLAUDE.md에 "finish는 main 폴더에서"라는 우회를 적어둬야 했던 이유.

    `git rev-parse --git-common-dir`는 링크된 워크트리에서도 **공유 .git**을 가리킨다
    → 그 부모가 main 워크트리다.
    """
    start = Path(cwd) if cwd else Path(__file__).resolve().parent
    rc, out = _sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], start)
    if rc == 0 and out.strip():
        return Path(out.strip()).resolve().parent
    return Path(__file__).resolve().parent.parent      # git이 없거나 구버전이면 옛 방식


BASE = main_worktree()

# 트랙 폴더는 프로젝트 **안**에 둔다 — 사장님이 찾기 쉬운 곳.
# 점(.)으로 시작하는 이유 2가지:
#   ① 이 폴더는 옵시디언 볼트고 .md가 11,120개다. 점 폴더는 옵시디언이 인덱싱에서
#      자동 제외하므로, 트랙마다 볼트에 중복 노트 1만여 개가 생기는 걸 막는다.
#   ② .gitignore(/.tracks/)와 짝 — main 워킹트리가 트랙 폴더를 untracked로 보지 않는다.
TRACKS_DIR = ".tracks"
STAGE_PREFIX = "_merge-"

# 봇 산출물·런타임 파일 — main 폴더에 이게 더러워도 병합을 막지 않는다.
# (크롤봇이 raw/에 계속 쓴다. 이걸로 막으면 게이트가 영원히 안 돈다.)
_IGNORABLE = ("raw/", "out/", "wiki/log.d/", ".fablize/", ".superpowers/", ".tracks/")
_IGNORABLE_PARTS = ("/data/", "__pycache__/")
_IGNORABLE_SUFFIX = (".db", ".db-journal", ".db-wal", ".pyc", ".log")


class TrackError(Exception):
    """사람에게 그대로 보여줄 중단 사유."""


def run(cmd, cwd, check=False):
    p = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    if check and p.returncode != 0:
        raise TrackError(f"명령 실패: {' '.join(cmd)}\n{out}")
    return p.returncode, out


def validate_name(name):
    """폴더·브랜치 이름이 될 것이므로 경로를 벗어나는 이름을 막는다."""
    if not name or not name.strip():
        raise TrackError("트랙 이름이 비었다")
    bad = set('/\\:*?"<>| \t')
    if any(c in bad for c in name) or ".." in name or name.startswith("."):
        raise TrackError(
            f"트랙 이름에 쓸 수 없는 문자: {name!r}\n"
            "경로 구분자·공백·'..'는 폴더와 브랜치를 깨뜨린다."
        )
    return name


def branch_name(name):
    return f"{BRANCH_PREFIX}{name}"


def tracks_dir(repo=BASE):
    return Path(repo).resolve() / TRACKS_DIR


def worktree_path(name, repo=BASE):
    """`<프로젝트>/.tracks/<이름>` — 프로젝트 안. gitignore + 옵시디언 자동제외로 안전."""
    return tracks_dir(repo) / name


def is_ignorable(path):
    p = path.replace("\\", "/")
    return (
        p.startswith(_IGNORABLE)
        or any(part in p for part in _IGNORABLE_PARTS)
        or p.endswith(_IGNORABLE_SUFFIX)
    )


def parse_status(porcelain):
    """git status --porcelain → 경로 목록."""
    paths = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:  # rename
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip('"'))
    return paths


def dirty_code_files(repo):
    """봇 산출물을 뺀 '진짜' 더러운 파일."""
    _, out = run(["git", "status", "--porcelain"], repo)
    return [p for p in parse_status(out) if not is_ignorable(p)]


def current_branch(repo):
    _, out = run(["git", "branch", "--show-current"], repo)
    return out.strip()


def worktree_exists(name, repo=BASE):
    return worktree_path(name, repo).exists()


def branch_exists(repo, branch):
    rc, _ = run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], repo)
    return rc == 0


# ── start ────────────────────────────────────────────────────────

def _detach_upstream_from_main(wt, br):
    """★ `worktree add -b <br> origin/main`은 upstream을 **origin/main으로 박는다.**

    그러면 트랙 폴더의 커밋마다 post-commit의 인자 없는 `git push`가
    '트랙 브랜치를 main으로 밀어라'가 된다 — 게이트를 통째로 우회하는 경로다.
    지금 사고가 안 나는 건 순전히 `push.default`가 unset(=git 기본 `simple`)이라
    git이 거절해주기 때문이다(실측 2026-07-16). **누가 `push.default=upstream`으로
    바꾸는 순간 트랙 커밋이 곧장 main으로 나간다.** 우연에 기대지 않는다.

    → upstream을 끊고, 자기 이름의 원격 브랜치로 다시 건다(백업 겸용).
      원격에 못 올리면 upstream 없는 채로 둔다 — 그러면 post-commit이
      무해하게 실패할 뿐 main은 안전하다.
    """
    run(["git", "branch", "--unset-upstream"], wt)
    rc, out = run(["git", "push", "-u", "origin", f"HEAD:{br}"], wt)
    if rc != 0:
        print(f"ℹ️ 트랙 브랜치를 origin에 못 올렸다 — 로컬에만 둔다(병합엔 지장 없다).\n   {out.strip()[:200]}")


def _copy_local_secrets(repo, wt):
    """`.env`를 트랙 폴더에 복사한다 — **이게 없으면 트랙에서 AI 작업이 통째로 막힌다.**

    `.env`는 gitignore(비밀키)라 worktree로 안 따라온다. 그런데 `key_vault._ENV_PATH`는
    **모듈 위치 기준**이라 트랙 폴더에선 `.tracks/<이름>/.env`를 찾고, 없으니 키가 0개가 된다
    (2026-07-16 실측: main 45개 / 트랙 0개 → Gemini 영상분석이 "키풀이 비었다"로 죽었다).

    복사가 안전한 이유: 같은 PC·같은 사용자이고, 트랙 폴더에서도 `.env`는 gitignore라
    커밋될 수 없다. 없으면(서버·CI) 조용히 넘어간다.
    """
    src = Path(repo).resolve() / ".env"
    if not src.exists():
        return
    try:
        shutil.copy2(src, wt / ".env")
        print("   .env 복사됨 (트랙에서도 AI 키 사용 가능)")
    except OSError as e:
        print(f"⚠️ .env를 못 복사했다 — 이 트랙에선 AI 작업이 막힌다: {e}")


def upstream_of(wt):
    rc, out = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], wt)
    return out.strip() if rc == 0 else None


def start(name, repo=BASE):
    merge_gate.make_output_safe()
    validate_name(name)
    wt = worktree_path(name, repo)
    if wt.exists():
        raise TrackError(
            f"이미 있는 트랙 폴더: {wt}\n"
            "덮어쓰지 않는다. 이어서 쓰려면 그 폴더에서 Claude Code를 열어라."
        )
    if branch_exists(repo, branch_name(name)):
        raise TrackError(
            f"이미 있는 브랜치: {branch_name(name)}\n"
            f"폴더만 없다면 되살릴 수 있다: git worktree add \"{wt}\" {branch_name(name)}"
        )

    run(["git", "fetch", "origin"], repo)
    wt.parent.mkdir(parents=True, exist_ok=True)
    rc, out = run(
        ["git", "worktree", "add", str(wt), "-b", branch_name(name), "origin/main"],
        repo,
    )
    if rc != 0:
        raise TrackError(f"worktree 생성 실패:\n{out}")

    _detach_upstream_from_main(wt, branch_name(name))
    _copy_local_secrets(repo, wt)

    print(f"✅ 트랙 '{name}' 시작")
    print(f"   폴더:    {wt}")
    print(f"   브랜치:  {branch_name(name)} (origin/main 기준)")
    print()
    print("   이제 그 폴더에서 Claude Code를 열어라. 여기(main 폴더)에서 일하지 마라 —")
    print("   그러면 흡수가 그대로 재발한다.")
    print()
    print("   ⚠️ shopping_shorts/data/ 는 gitignore라 새 폴더는 빈 DB로 시작한다.")
    print("      로컬 데이터가 필요하면 복사해 오거나 서버에서 확인해라.")
    print(f"   끝나면: py tools/track.py finish {name}")
    return 0


# ── finish ───────────────────────────────────────────────────────

def _preflight(name, repo):
    """트랙 폴더만 본다. **main 폴더는 검사하지도, 건드리지도 않는다** —
    거기선 다른 세션 5개가 계속 일하고 있고, 우리는 그 폴더를 쓰지 않는다."""
    wt = worktree_path(name, repo)
    if not wt.exists():
        raise TrackError(f"트랙 폴더가 없다: {wt}\n먼저: py tools/track.py start {name}")

    _, st = run(["git", "status", "--porcelain"], wt)
    if [p for p in parse_status(st) if not is_ignorable(p)]:
        raise TrackError(
            f"트랙 폴더가 dirty다 — 커밋 먼저 해라.\n\n{st}\n"
            f"(폴더: {wt})"
        )
    return wt


def _open_stage(repo, name):
    """병합·게이트 전용 임시 폴더 (origin/main에 detached).

    ★ 왜 main 폴더에서 안 하나: `merge --no-commit` 후 게이트(pytest)가 도는
    수 분 동안 main 폴더는 '반쯤 병합된' 상태가 된다. 그 창에 다른 세션이
    커밋하면 그 반쪽 병합을 통째로 담아 push한다 — 없애려던 흡수가 바로
    그 자리에서 되살아난다. 게다가 옆 세션의 편집이 게이트 결과를 오염시켜
    없는 실패가 잡힌다(오탐). 전용 폴더는 둘 다 원천 차단한다.
    """
    stage = tracks_dir(repo) / f"{STAGE_PREFIX}{name}"
    stage.parent.mkdir(parents=True, exist_ok=True)
    if stage.exists():
        run(["git", "worktree", "remove", "--force", str(stage)], repo)
    rc, out = run(["git", "worktree", "add", "--detach", str(stage), "origin/main"], repo)
    if rc != 0:
        raise TrackError(f"병합용 임시 폴더를 못 만들었다:\n{out}")
    return stage


def _close_stage(repo, stage):
    run(["git", "worktree", "remove", "--force", str(stage)], repo)


def finish(name, repo=BASE, gate=merge_gate, attempts=3):
    merge_gate.make_output_safe()
    validate_name(name)
    wt = _preflight(name, repo)
    br = branch_name(name)

    for attempt in range(1, attempts + 1):
        run(["git", "fetch", "origin"], repo)
        stage = _open_stage(repo, name)
        try:
            result = _merge_and_gate(name, repo, stage, br, gate, wt)
        finally:
            _close_stage(repo, stage)

        if result == "nothing":
            print(f"\n병합할 것이 없다 (트랙 '{name}'에 새 커밋 없음).")
            return 0
        if result == "pushed":
            _sync_main_folder(repo)
            _level_track_with_main(name, repo, wt, br)
            return 0
        # result == "raced": 다른 트랙이 먼저 병합했다 → 그 위에서 다시
        print(f"⚠️ 다른 트랙이 먼저 main에 들어왔다. 최신 main 위에서 다시 시도 "
              f"({attempt}/{attempts})...")

    raise TrackError(
        f"{attempts}번 시도했는데 매번 다른 트랙이 먼저 들어왔다.\n"
        "지금 병합이 몰리는 중이다. 잠시 뒤 다시: py tools/track.py finish " + name
    )


def _merge_and_gate(name, repo, stage, br, gate, wt):
    print("기준선 수집 중 (병합 전 origin/main)...")
    before = gate.snapshot(stage)
    for w in gate.baseline_warnings(before):
        print(f"  {w}")

    # ★ 커밋 없이 병합만 — 커밋하면 post-commit(git push)이 게이트 전에 라이브로 보낸다
    rc, out = run(["git", "merge", "--no-ff", "--no-commit", br], stage)

    if "Already up to date" in out:
        return "nothing"

    if rc != 0:
        # abort하지 않는다 — stage 자체가 finally에서 통째로 삭제되므로 중복이다.
        # (실측: abort를 지워도 부분 병합이 남지 않는다 — worktree remove --force가 처리)
        raise TrackError(
            f"병합 충돌 — 자동 해결하지 않는다(사람 판단).\n\n{out}\n"
            f"트랙 폴더에서 main을 먼저 받아 충돌을 풀어라:\n"
            f"  cd \"{wt}\"\n"
            f"  git fetch origin && git merge origin/main\n"
            f"  (충돌 해결·커밋 후) py tools/track.py finish {name}"
        )

    print("게이트 실행 중 (병합된 상태, 아직 커밋 없음)...")
    after = gate.snapshot(stage)
    problems = gate.compare(before, after)

    if problems:
        msg = ["❌ 게이트 실패 — 병합을 버렸다. 라이브는 무사하다.\n"]
        msg += [f"  • {p}" for p in problems]
        if not after["import_ok"]:
            msg.append(f"\n--- import 출력 ---\n{after['import_out']}")
        if after["pytest_rc"] not in merge_gate._PYTEST_SANE_RC:
            msg.append(f"\n--- pytest 출력 ---\n{after['pytest_out']}")
        msg.append(f"\n트랙 폴더는 그대로 있다: {wt}\n고친 뒤 다시: py tools/track.py finish {name}")
        raise TrackError("\n".join(msg))

    print(f"✅ 게이트 통과 (기존 실패 {len(before['failed'])}건은 그대로)")

    # stage는 detached HEAD라 post-commit의 인자 없는 `git push`는 조용히 실패한다.
    # 그래서 push는 아래에서 우리가 명시적으로 한다 — 즉 **게이트 통과 후에만** 나간다.
    rc, out = run(["git", "commit", "--no-edit"], stage)
    if rc != 0:
        raise TrackError(f"커밋 실패 — 병합을 버렸다(라이브 무사):\n{out}")

    rc, out = run(["git", "push", "origin", "HEAD:main"], stage)
    if rc != 0:
        if _is_race(out):
            return "raced"
        raise TrackError(
            f"push 실패 — main은 안 바뀌었다(라이브 무사):\n{out}"
        )
    print("✅ main에 병합 완료 — push됨. 3분 뒤 서버 반영.")
    return "pushed"


def _is_race(push_output):
    """다른 트랙이 먼저 밀어넣어 거절당했나 (git이 주는 원자적 신호등)."""
    o = push_output.lower()
    return "non-fast-forward" in o or "fetch first" in o or "rejected" in o


def _sync_main_folder(repo):
    """원본 폴더를 새 main으로 당겨준다. 실패해도 병합은 이미 끝났다 — 알리기만."""
    rc, out = run(["git", "merge", "--ff-only", "origin/main"], repo)
    if rc != 0:
        print(f"ℹ️ 원본 폴더는 아직 옛 main이다 (거기서 직접 pull 해라):\n{out.strip()}")


def _level_track_with_main(name, repo, wt, br):
    """병합 후 트랙 브랜치를 새 main 자리로 당긴다. **폴더는 남긴다.**

    ★왜 안 지우나: 설계는 "태스크 단위로 자주 병합"을 요구한다. 병합할 때마다 883MB
    체크아웃을 지웠다 다시 만들면 그 요구와 정면으로 안 맞는다. 게다가 사용자의 터미널이
    그 폴더 안에 있으면 윈도우가 삭제를 거부해 어차피 실패한다(2026-07-16 실측 2회).
    트랙 폴더 = 그 트랙의 작업대다. 태스크가 끝난 거지 트랙이 끝난 게 아니다.
    트랙을 진짜 접을 땐 `close`.

    ★reset --hard가 아니라 ff 병합인 이유: reset은 트랙 폴더의 미추적 산출물·메모를
    날릴 수 있다. 우리 커밋은 방금 main에 병합됐으므로 origin/main은 트랙 브랜치의
    **자손**이다 → ff가 성립한다.
    """
    rc, out = run(["git", "merge", "--ff-only", "origin/main"], wt)
    if rc != 0:
        print(f"ℹ️ 트랙 '{name}' 폴더를 최신 main으로 못 당겼다 — 거기서 직접 pull 해라.\n   {out.strip()[:200]}")
        return
    # ff 결과를 백업 브랜치에도 올린다. 안 올리면 로컬이 자기 upstream보다 앞선 상태가 돼
    # `git branch -d`가 "upstream에 아직 병합 안 됨"이라며 거절한다(HEAD엔 병합됐는데도).
    # 실패해도(오프라인 등) 병합은 이미 끝났으므로 조용히 넘어간다 — close가 -D로 처리한다.
    run(["git", "push", "origin", f"HEAD:{br}"], wt)
    print(f"✅ 트랙 '{name}' 폴더는 그대로 두고 최신 main에 맞췄다 — 바로 다음 작업 가능.")
    print(f"   트랙을 아주 접으려면: py tools/track.py close {name}")


def close(name, repo=BASE):
    """트랙을 접는다 — 폴더·브랜치 삭제. finish와 달리 **파괴적**이라 확인이 붙는다."""
    merge_gate.make_output_safe()
    validate_name(name)
    wt = worktree_path(name, repo)
    br = branch_name(name)
    if not wt.exists() and not branch_exists(repo, br):
        raise TrackError(f"없는 트랙: {name}")

    run(["git", "fetch", "origin"], repo)
    ahead = ahead_count(repo, br) if branch_exists(repo, br) else 0
    if ahead:
        raise TrackError(
            f"트랙 '{name}'에 아직 **병합 안 된 커밋 {ahead}개**가 있다 — 접으면 사라진다.\n"
            f"먼저: py tools/track.py finish {name}\n"
            f"버릴 작정이면: git worktree remove --force \"{wt}\" && git branch -D {br}"
        )
    if wt.exists():
        rc, out = run(["git", "worktree", "remove", str(wt)], repo)
        if rc != 0:
            raise TrackError(
                f"트랙 폴더를 못 지웠다 — 그 폴더 안에 열린 터미널·창이 있나 확인해라"
                f"(윈도우는 사용 중인 폴더 삭제를 거부한다).\n{out.strip()[:200]}"
            )
    run(["git", "push", "origin", "--delete", br], repo)   # 원격 백업 먼저(없으면 조용히 실패)
    # -D인 이유: `-d`는 **upstream**(origin/track/X) 기준으로 판단해서, 로컬이 ff로 앞서 있으면
    # "HEAD엔 병합됐는데도" 거절한다(실측). 우리는 위에서 ahead_count==0으로 **main에 다 들어갔음**을
    # 이미 확인했다 — git의 upstream 휴리스틱보다 정확한 검사다. 그 확인 없이 -D를 쓰면 안 된다.
    rc, out = run(["git", "branch", "-D", br], repo)
    if rc != 0:
        raise TrackError(f"브랜치를 못 지웠다:\n{out.strip()[:200]}")
    print(f"🧹 트랙 '{name}' 접음 (폴더·브랜치 삭제)")
    return 0


# ── list ─────────────────────────────────────────────────────────

def track_branches(repo=BASE):
    _, out = run(["git", "branch", "--list", f"{BRANCH_PREFIX}*", "--format=%(refname:short)"], repo)
    return [b.strip() for b in out.splitlines() if b.strip()]


def ahead_count(repo, branch, base=MAIN_BRANCH):
    rc, out = run(["git", "rev-list", "--count", f"{base}..{branch}"], repo)
    if rc != 0:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def list_tracks(repo=BASE):
    merge_gate.make_output_safe()
    branches = track_branches(repo)
    if not branches:
        print("열린 트랙 없음.  시작: py tools/track.py start <이름>")
        return 0
    print("열린 트랙:\n")
    for br in branches:
        name = br[len(BRANCH_PREFIX):]
        wt = worktree_path(name, repo)
        n = ahead_count(repo, br)
        mark = ""
        if n is None:
            mark = "  (앞선 커밋 수 계산 실패)"
        elif n >= 10:
            mark = f"  ⚠️⚠️ main보다 {n}커밋 앞섬 — 너무 오래 끌었다. 지금 병합해라."
        elif n >= 5:
            mark = f"  ⚠️ main보다 {n}커밋 앞섬 — 슬슬 병합할 때."
        else:
            mark = f"  main보다 {n}커밋 앞섬"
        exists = "" if wt.exists() else "  ❗폴더 없음(브랜치만 남음)"
        print(f"  {name:<16} {br}{mark}{exists}")
        print(f"  {'':<16} {wt}")
    print("\n끝내기: py tools/track.py finish <이름>")
    return 0


# ── cli ──────────────────────────────────────────────────────────

def main(argv=None):
    merge_gate.make_output_safe()  # cp949 콘솔에서 ✅·⚠️ 찍다 터지는 것 방지(실측)
    parser = argparse.ArgumentParser(description="트랙별 작업 폴더")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start", help="트랙 폴더+브랜치 생성")
    p_start.add_argument("name")
    p_finish = sub.add_parser("finish", help="게이트 통과 시 main에 병합 (폴더는 남는다)")
    p_finish.add_argument("name")
    p_close = sub.add_parser("close", help="트랙을 접는다 — 폴더·브랜치 삭제")
    p_close.add_argument("name")
    sub.add_parser("list", help="열린 트랙과 밀린 정도")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "start":
            return start(args.name)
        if args.cmd == "finish":
            return finish(args.name)
        if args.cmd == "close":
            return close(args.name)
        return list_tracks()
    except TrackError as e:
        print(f"\n중단: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
