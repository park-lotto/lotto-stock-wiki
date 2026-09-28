# -*- coding: utf-8 -*-
"""관제(管制) — 모든 요청은 카드로 등록되고, 트랙은 카드 없이 열리지 않고, finish 는 카드·승인·소유권을 검사한다.

설계: docs/superpowers/specs/2026-09-27-관제시스템-design.md (2026-09-28 사장님 "매우 중요하니까 시작해")

무엇이 어디에 있나 (전부 git, main 브랜치 `관제/`):
    관제/cards/<번호>-<제목>.md   카드 하나 = 요청 하나. 머리 블록(`- 키: 값`)이 기계가 읽는 부분
    관제/BOARD.md                 카드에서 **생성**되는 보드(손으로 고치지 마라 — 다음 publish 가 덮는다)
    관제/claims.json              트랙 간 선점 신고 {대상: {track, card, at}}
    관제/ownership.json           판단 소유권 지도(주인 함수·시그니처·소비처) — ownership_check.py 가 읽는다
    관제/rules.json               승인 표식 규칙(고객 화면·과금·고객 데이터 경로/토큰)

★카드는 **origin/main 에만** 있다 — 트랙 폴더 사본을 고치지 마라. 이 모듈의 쓰기는 전부 `_publish`:
  가벼운 임시 워크트리(sparse: 관제/ 만)를 origin/main 에 열고 → 고치고 → 커밋 → `push HEAD:main`.
  main 폴더·트랙 폴더는 건드리지 않으므로 흡수·dirty 문제가 없다. 경쟁(push 거절)은 최신 위에서 다시.
  카드 파일은 코드가 아니라 게이트 없이 main 으로 간다(merge_gate 는 코드 병합용).

★관제가 "설치됐다" = origin/main 에 `관제/cards/` 가 있다. 없는 저장소(옛 테스트 저장소 등)에선 모든 검사가
  꺼진다 — 그래서 track.py 의 기존 테스트 60여 개가 그대로 돈다. 설치는 `py tools/control.py install`.

사용:
    py tools/control.py new "제목" [--from 제보자] [--owner 파일:함수] [--done "됐다의 기준"] [--track 트랙] [--body 원문]
    py tools/control.py list | board | show <번호>
    py tools/control.py approve <번호> "사장님 구두 2026-09-28"      # 승인 표식(고객 화면·과금·데이터 변경은 이게 있어야 finish)
    py tools/control.py status <번호> <상태> | note <번호> "메모" | link <번호> <트랙>
    py tools/control.py claim <트랙> <번호> <파일|파일:함수>...          # 선점 신고
    (track.py start <트랙> --card <번호> / finish 가 이 모듈을 부른다)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CTRL_DIR = "관제"
CARDS_REL = CTRL_DIR + "/cards"
BOARD_REL = CTRL_DIR + "/BOARD.md"
CLAIMS_REL = CTRL_DIR + "/claims.json"
RULES_REL = CTRL_DIR + "/rules.json"
OWNERSHIP_REL = CTRL_DIR + "/ownership.json"
MAIN_REF = "origin/main"

STATES = ("등록", "분배", "수리", "로컬검증", "병합", "서버반영", "라이브실측", "완료", "승인대기", "회귀")
# 상태 순서(보드 정렬). 완료는 맨 아래.
_STATE_ORDER = {s: i for i, s in enumerate(("회귀", "승인대기", "등록", "분배", "수리", "로컬검증", "병합", "서버반영", "라이브실측", "완료"))}

# 커밋 메시지·핸드오프에서 카드 번호를 찾는 모양: "관제 12" / "관제#12" / "[관제 12]" / "(관제 012)"
CARD_REF = re.compile(r"관제\s*#?\s*0*(\d{1,4})")

DEFAULT_RULES = {
    "_설명": "승인 표식 규칙. diff 가 여기 닿으면 카드에 '승인:' 한 줄이 있어야 finish 가 병합한다(0순위-A1c). 경로는 접두, 토큰은 정규식(추가·삭제된 줄에서 찾는다).",
    "approval": {
        "customer_ui_prefixes": ["shopping_shorts/static/", "shopping_shorts/templates/"],
        "customer_ui_suffixes": [".html", ".js", ".css"],
        "token_scope_prefixes": ["shopping_shorts/"],
        "billing_tokens": ["_charge_", "clean_charge_plan", "clean_credit", "_sig_tier", "signature", "_render_stamp"],
        "customer_data_tokens": ["update_mix_job", "mix_jobs", "clean_base.json"],
    },
    "card_gate": {"require_card": True, "require_approval": True, "ownership_check": True},
}


class ControlError(Exception):
    """사람에게 그대로 보여줄 중단 사유."""


# ── git 잔심부름 ────────────────────────────────────────────────────

def _git(cwd, *args):
    p = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main_worktree(cwd=None):
    """이 저장소의 main 워크트리(공유 .git 의 부모). track.main_worktree 와 같은 원리 — 여기 다시 적는 이유는 순환 import 를 피하려고."""
    start = Path(cwd) if cwd else Path(__file__).resolve().parent
    rc, out = _git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if rc == 0 and out.strip():
        return Path(out.strip()).resolve().parent
    return Path(__file__).resolve().parent.parent


def _tree_files(repo, ref, prefix):
    rc, out = _git(repo, "ls-tree", "-r", "--name-only", ref, "--", prefix)
    if rc != 0:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _show(repo, ref, rel):
    rc, out = _git(repo, "show", "%s:%s" % (ref, rel))
    return out if rc == 0 else None


def installed(repo, ref=MAIN_REF):
    """관제가 이 저장소에 설치됐나 = ref 에 관제/cards/ 가 있나(빈 폴더는 git 이 못 담으니 .keep 이 있다)."""
    return bool(_tree_files(repo, ref, CARDS_REL))


def load_rules(repo, ref=MAIN_REF):
    raw = _show(repo, ref, RULES_REL)
    if not raw:
        return DEFAULT_RULES
    try:
        return json.loads(raw)
    except ValueError:
        return DEFAULT_RULES


# ── 카드 ────────────────────────────────────────────────────────────

_HEAD_LINE = re.compile(r"^- ([^:]+):\s?(.*)$")
_TITLE = re.compile(r"^#\s*0*(\d+)\s*·\s*(.+?)\s*$")
_FILE = re.compile(r"^0*(\d+)-.*\.md$")

CARD_KEYS = ("상태", "등록", "제보", "판단 주인", "분배", "됐다의 기준", "승인 필요", "승인", "병합", "서버 반영", "라이브 실측", "재발")


def parse_card(text, path=""):
    """카드 md → dict. 머리 블록은 첫 `## ` 전의 `- 키: 값` 줄. 본문은 그대로 둔다(사람 글)."""
    c = {"번호": None, "제목": "", "path": path, "이력": [], "body": text}
    lines = text.splitlines()
    for ln in lines:
        m = _TITLE.match(ln)
        if m:
            c["번호"], c["제목"] = int(m.group(1)), m.group(2)
            break
    if c["번호"] is None:
        m = _FILE.match(Path(path).name) if path else None
        if m:
            c["번호"] = int(m.group(1))
    in_head, section = True, None
    for ln in lines:
        if ln.startswith("## "):
            in_head = False
            section = ln[3:].strip()
            continue
        if in_head:
            m = _HEAD_LINE.match(ln)
            if m:
                c[m.group(1).strip()] = m.group(2).strip()
        elif section == "이력" and ln.startswith("- "):
            c["이력"].append(ln[2:].strip())
    for k in CARD_KEYS:
        c.setdefault(k, "")
    c["분배목록"] = [t.strip() for t in re.split(r"[,\s]+", c["분배"]) if t.strip()]
    return c


def render_card(c):
    """dict → 카드 md. 머리 블록은 여기서만 만든다(형식의 주인 함수)."""
    head = ["# %03d · %s" % (c["번호"], c["제목"]), ""]
    for k in CARD_KEYS:
        head.append("- %s: %s" % (k, c.get(k, "")))
    body = c.get("요청", "").rstrip()
    out = head + ["", "## 요청", "", body or "(원문 없음)", "", "## 이력", ""]
    out += ["- " + h for h in c.get("이력", [])]
    return "\n".join(out).rstrip() + "\n"


def _now():
    return time.strftime("%Y-%m-%d %H:%M")


def _slug(title, limit=24):
    s = re.sub(r'[\\/:*?"<>|\s]+', "_", title.strip()).strip("_")
    return (s[:limit] or "카드")


def card_filename(number, title):
    return "%s/%03d-%s.md" % (CARDS_REL, number, _slug(title))


def cards_from_ref(repo, ref=MAIN_REF):
    """ref(기본 origin/main)의 카드 전부 → [dict]. finish 는 이걸 쓴다(트랙 폴더 사본은 낡을 수 있다)."""
    out = []
    for rel in _tree_files(repo, ref, CARDS_REL):
        if not rel.endswith(".md"):
            continue
        text = _show(repo, ref, rel)
        if text is None:
            continue
        out.append(parse_card(text, rel))
    return sorted(out, key=lambda c: c["번호"] or 0)


def cards_from_dir(root):
    d = Path(root) / CARDS_REL
    if not d.exists():
        return []
    out = [parse_card(p.read_text(encoding="utf-8"), str(p.relative_to(root)).replace("\\", "/"))
           for p in sorted(d.glob("*.md"))]
    return sorted(out, key=lambda c: c["번호"] or 0)


def next_number(cards):
    return max([c["번호"] or 0 for c in cards] + [0]) + 1


def find_card(cards, number):
    for c in cards:
        if c["번호"] == int(number):
            return c
    return None


def cards_for_track(cards, track_name):
    return [c for c in cards if track_name in c["분배목록"]]


def card_refs(text):
    """텍스트(커밋 메시지들)에서 카드 번호 집합."""
    return {int(m) for m in CARD_REF.findall(text or "")}


def refs_in_branch(repo, base, br):
    rc, out = _git(repo, "log", "--format=%s%n%b", "%s..%s" % (base, br))
    return card_refs(out) if rc == 0 else set()


# ── 승인 표식 (순수 함수) ─────────────────────────────────────────────

_DIFF_FILE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def split_diff_by_file(diff_text):
    """통합 diff → {파일: [추가·삭제된 줄 본문]} (문맥·헤더 줄은 뺀다)."""
    out, cur = {}, None
    for ln in (diff_text or "").splitlines():
        m = _DIFF_FILE.match(ln)
        if m:
            cur = m.group(2).strip().strip('"')
            out.setdefault(cur, [])
            continue
        if cur is None or ln.startswith(("+++", "---", "@@", "index ", "new file", "deleted file", "similarity", "rename ")):
            continue
        if ln.startswith("+") or ln.startswith("-"):
            out[cur].append(ln[1:])
    return out


def approval_reasons(changed_files, diff_u0, rules):
    """변경 파일·diff → 승인이 필요한 이유 목록(비면 승인 불필요).
    토큰 검사는 token_scope_prefixes(기본 shopping_shorts/) 안 파일의 **바뀐 줄**에서만 — tools/ 의 규칙 파일·검사 도구가
    토큰 이름을 적는 것은 과금 코드 변경이 아니다."""
    a = (rules or DEFAULT_RULES).get("approval", DEFAULT_RULES["approval"])
    reasons = []
    for f in changed_files:
        f = f.replace("\\", "/")
        if any(f.startswith(p) for p in a.get("customer_ui_prefixes", [])) and \
                any(f.endswith(s) for s in a.get("customer_ui_suffixes", [])):
            reasons.append("고객 화면 변경: %s" % f)
    scope = tuple(a.get("token_scope_prefixes", ["shopping_shorts/"]))
    per_file = split_diff_by_file(diff_u0)
    if not per_file and diff_u0:                       # 파일 헤더 없는 조각(단일 파일 diff) — 첫 변경 파일의 것으로 본다
        per_file = {(changed_files[0] if changed_files else ""): [ln[1:] for ln in diff_u0.splitlines()
                    if (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---"))]}
    for f, lines in per_file.items():
        if not f.replace("\\", "/").startswith(scope):
            continue
        blob = "\n".join(lines)
        for tok in a.get("billing_tokens", []):
            if re.search(tok, blob):
                reasons.append("과금 관련 코드 변경(%s, 토큰 %r)" % (f, tok))
        for tok in a.get("customer_data_tokens", []):
            if re.search(tok, blob):
                reasons.append("고객 데이터 쓰기 관련 변경(%s, 토큰 %r)" % (f, tok))
    # 같은 이유 중복 제거(순서 유지)
    seen, out = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


# ── 보드 ────────────────────────────────────────────────────────────

def render_board(cards, now=None):
    now = now or _now()
    lines = ["# 관제 보드 (자동 생성 — 손으로 고치지 마라. `py tools/control.py board`)", "",
             "갱신: %s · 카드 %d장" % (now, len(cards)), "",
             "상태 흐름: 등록 → 분배 → 수리 → 로컬검증 → 병합 → 서버반영 → 라이브실측 → 완료  (예외: 승인대기 · 회귀)", ""]
    groups = {}
    for c in cards:
        groups.setdefault(c["상태"] or "등록", []).append(c)
    for st in sorted(groups, key=lambda s: _STATE_ORDER.get(s, 50)):
        lines += ["## %s (%d)" % (st, len(groups[st])), "",
                  "| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |", "|---|---|---|---|---|---|---|"]
        for c in groups[st]:
            last = c["이력"][-1] if c["이력"] else ""
            appr = c["승인"] or ("**필요**" if c["승인 필요"].startswith("예") else "-")
            lines.append("| [%03d](%s) | %s | %s | %s | %s | %s | %s |" % (
                c["번호"], c["path"].replace(CTRL_DIR + "/", ""), c["제목"], c["분배"] or "-", appr,
                c["판단 주인"] or "-", (c["됐다의 기준"] or "-").replace("|", "/"), last.replace("|", "/")[:60]))
        lines.append("")
    return "\n".join(lines)


# ── publish: origin/main 의 관제/ 만 고쳐 곧장 main 으로 ───────────────────

def _publish(repo, mutate, msg, attempts=4, keep_stage=False):
    """가벼운 임시 워크트리(관제/ 만 체크아웃)에서 mutate(wt) → 보드 재생성 → 커밋 → push HEAD:main.
    mutate 는 wt 안의 관제/ 파일만 고친다. 경쟁으로 거절되면 최신 origin/main 위에서 다시(카드 번호도 다시 정한다)."""
    repo = Path(repo)
    last = ""
    for attempt in range(1, attempts + 1):
        _git(repo, "fetch", "origin")
        stage = repo / ".tracks" / ("_card-%d-%d" % (os.getpid(), attempt))
        stage.parent.mkdir(parents=True, exist_ok=True)
        if stage.exists():
            _git(repo, "worktree", "remove", "--force", str(stage))
        rc, out = _git(repo, "worktree", "add", "--detach", "--no-checkout", str(stage), MAIN_REF)
        if rc != 0:
            raise ControlError("관제 임시 폴더를 못 만들었다:\n" + out)
        try:
            _git(stage, "sparse-checkout", "set", CTRL_DIR)
            rc, out = _git(stage, "reset", "--hard", "HEAD")
            if rc != 0:
                raise ControlError("관제 임시 폴더 체크아웃 실패:\n" + out)
            (stage / CARDS_REL).mkdir(parents=True, exist_ok=True)
            mutate(stage)
            (stage / BOARD_REL).write_text(render_board(cards_from_dir(stage)), encoding="utf-8")
            _git(stage, "add", "-A", "--", CTRL_DIR)
            rc, out = _git(stage, "commit", "-q", "-m", msg)
            if rc != 0:
                if "nothing to commit" in out:
                    return None
                raise ControlError("관제 커밋 실패:\n" + out)
            rc, out = _git(stage, "push", "origin", "HEAD:main")
            if rc == 0:
                rc2, sha = _git(stage, "rev-parse", "--short=10", "HEAD")
                _git(repo, "merge", "--ff-only", MAIN_REF)        # main 폴더도 따라오게(실패하면 그냥 둔다 — 거긴 남의 작업대)
                return sha.strip()
            last = out
            lo = out.lower()
            if not ("rejected" in lo or "non-fast-forward" in lo or "fetch first" in lo):
                raise ControlError("관제 push 실패 — main 은 안 바뀌었다:\n" + out)
        finally:
            if not keep_stage:
                _git(repo, "worktree", "remove", "--force", str(stage))
    raise ControlError("%d번 시도했는데 매번 다른 push 가 먼저 들어왔다. 잠시 뒤 다시.\n%s" % (attempts, last))


def install(repo, printer=print):
    """관제를 설치한다 — 관제/cards/.keep · rules.json · claims.json · BOARD.md 를 origin/main 에."""
    if installed(repo):
        printer("이미 설치돼 있다.")
        return None

    def mutate(wt):
        (wt / CARDS_REL / ".keep").write_text("", encoding="utf-8")
        if not (wt / RULES_REL).exists():
            (wt / RULES_REL).write_text(json.dumps(DEFAULT_RULES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not (wt / CLAIMS_REL).exists():
            (wt / CLAIMS_REL).write_text("{}\n", encoding="utf-8")
    sha = _publish(repo, mutate, "관제 설치 — 카드 폴더·규칙·선점표")
    printer("✅ 관제 설치 (main %s)" % sha)
    return sha


def new_card(repo, title, *, reporter="", owner="", done="", track="", body="", approval=None, printer=print):
    """카드 등록 → 번호. approval None 이면 '미정'(finish 가 diff 로 판정해 필요하면 막는다)."""
    title = (title or "").strip()
    if not title:
        raise ControlError("카드 제목이 비었다")
    if not installed(repo):
        raise ControlError("관제가 설치되지 않았다: py tools/control.py install")
    made = {}

    def mutate(wt):
        cards = cards_from_dir(wt)
        n = next_number(cards)
        c = {"번호": n, "제목": title, "상태": "분배" if track else "등록", "등록": _now(), "제보": reporter,
             "판단 주인": owner, "분배": track, "됐다의 기준": done,
             "승인 필요": ("예" if approval else "아니오") if approval is not None else "미정(finish 가 diff 로 판정)",
             "승인": "", "병합": "", "서버 반영": "", "라이브 실측": "", "재발": "", "요청": body,
             "이력": ["%s 등록%s" % (_now(), (" · 분배 → " + track) if track else "")]}
        rel = card_filename(n, title)
        (wt / rel).write_text(render_card(c), encoding="utf-8")
        made["n"], made["rel"] = n, rel
    sha = _publish(repo, mutate, "관제 카드 등록: %s" % title)
    printer("✅ 관제 카드 %03d 등록 — %s (main %s)" % (made["n"], made["rel"], sha))
    printer("   트랙 열기: py tools/track.py start <트랙명> --card %d" % made["n"])
    return made["n"]


def _edit_card(repo, number, editor, msg):
    """카드 하나를 고친다. editor(card_dict) 가 dict 를 바꾼다(이력 한 줄은 여기서 붙인다)."""
    found = {}

    def mutate(wt):
        cards = cards_from_dir(wt)
        c = find_card(cards, number)
        if c is None:
            raise ControlError("없는 카드: %s" % number)
        c["요청"] = _body_section(c["body"])
        note = editor(c)
        if note:
            c["이력"].append("%s %s" % (_now(), note))
        (wt / c["path"]).write_text(render_card(c), encoding="utf-8")
        found["c"] = c
    sha = _publish(repo, mutate, msg)
    return found.get("c"), sha


def _body_section(text):
    m = re.search(r"^## 요청\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    body = (m.group(1).strip() if m else "")
    return "" if body == "(원문 없음)" else body


def link_track(repo, number, track_name, printer=print):
    def ed(c):
        if track_name in c["분배목록"]:
            return None
        c["분배"] = ", ".join(c["분배목록"] + [track_name])
        if c["상태"] in ("등록",):
            c["상태"] = "분배"
        return "분배 → %s" % track_name
    c, sha = _edit_card(repo, number, ed, "관제 %03d 분배: %s" % (int(number), track_name))
    if sha:
        printer("✅ 관제 카드 %03d ← 트랙 %s (main %s)" % (int(number), track_name, sha))
    return c


def set_status(repo, number, state, printer=print):
    if state not in STATES:
        raise ControlError("모르는 상태 %r — 가능: %s" % (state, " · ".join(STATES)))

    def ed(c):
        old = c["상태"]
        c["상태"] = state
        return "상태 %s → %s" % (old, state)
    c, sha = _edit_card(repo, number, ed, "관제 %03d 상태: %s" % (int(number), state))
    printer("✅ 관제 카드 %03d 상태 %s (main %s)" % (int(number), state, sha))
    return c


def approve(repo, number, who, printer=print):
    who = (who or "").strip()
    if not who:
        raise ControlError("승인 근거가 비었다(예: '사장님 구두 2026-09-28 14:10')")

    def ed(c):
        c["승인"] = "%s · %s" % (_now(), who)
        c["승인 필요"] = "예"
        if c["상태"] == "승인대기":
            c["상태"] = "수리"
        return "승인: " + who
    c, sha = _edit_card(repo, number, ed, "관제 %03d 승인" % int(number))
    printer("✅ 관제 카드 %03d 승인 기록 (main %s)" % (int(number), sha))
    return c


def note(repo, number, text, printer=print):
    c, sha = _edit_card(repo, number, lambda c: text.strip(), "관제 %03d 메모" % int(number))
    printer("✅ 관제 카드 %03d 메모 (main %s)" % (int(number), sha))
    return c


def set_field(repo, number, key, value, printer=print):
    if key not in CARD_KEYS:
        raise ControlError("모르는 칸 %r — 가능: %s" % (key, " · ".join(CARD_KEYS)))

    def ed(c):
        c[key] = value
        return "%s: %s" % (key, value)
    c, sha = _edit_card(repo, number, ed, "관제 %03d %s" % (int(number), key))
    printer("✅ 관제 카드 %03d %s 갱신 (main %s)" % (int(number), key, sha))
    return c


def record_merge(repo, numbers, track_name, sha, printer=print):
    """finish 가 병합 뒤 부른다 — 상태 병합, 병합 칸에 sha·시각. 실패해도 병합은 끝났으니 알리기만."""
    def mutate(wt):
        cards = cards_from_dir(wt)
        for n in numbers:
            c = find_card(cards, n)
            if c is None:
                continue
            c["요청"] = _body_section(c["body"])
            c["병합"] = "%s %s (%s)" % (sha, _now(), track_name)
            if _STATE_ORDER.get(c["상태"], 0) < _STATE_ORDER["병합"]:
                c["상태"] = "병합"
            c["이력"].append("%s 병합 %s ← 트랙 %s (반영됨·미검증 — 라이브 실측 전)" % (_now(), sha, track_name))
            (wt / c["path"]).write_text(render_card(c), encoding="utf-8")
    try:
        s = _publish(repo, mutate, "관제 %s 병합 기록 (%s)" % (", ".join("%03d" % n for n in numbers), track_name))
        printer("✅ 관제 카드 %s ← 병합 %s 기록 (main %s)" % (", ".join("%03d" % n for n in numbers), sha, s))
    except ControlError as e:
        printer("ℹ️ 병합은 끝났지만 카드에 기록을 못 남겼다 — 손으로: py tools/control.py note <번호> \"병합 %s\"\n   %s" % (sha, e))


# ── 선점 신고 ─────────────────────────────────────────────────────────

def load_claims(repo, ref=MAIN_REF):
    raw = _show(repo, ref, CLAIMS_REL)
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


def claim(repo, track_name, number, targets, printer=print):
    """대상(파일 또는 파일:함수)을 이 트랙이 선점한다고 신고. 이미 다른 트랙이 쥔 대상은 알리고 덮지 않는다."""
    taken = []

    def mutate(wt):
        p = wt / CLAIMS_REL
        claims = json.loads(p.read_text(encoding="utf-8") or "{}") if p.exists() else {}
        for t in targets:
            t = t.replace("\\", "/")
            cur = claims.get(t)
            if cur and cur.get("track") != track_name:
                taken.append((t, cur))
                continue
            claims[t] = {"track": track_name, "card": int(number), "at": _now()}
        p.write_text(json.dumps(claims, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha = _publish(repo, mutate, "관제 선점: %s ← %s" % (", ".join(targets), track_name))
    for t, cur in taken:
        printer("⚠️ %s 는 이미 트랙 %s(카드 %03d, %s)가 쥐고 있다 — 관제 판단 뒤에 나눠라" % (t, cur.get("track"), cur.get("card", 0), cur.get("at", "")))
    printer("✅ 선점 신고 %d건 (main %s)" % (len(targets) - len(taken), sha))
    return taken


def release(repo, track_name, printer=print):
    """트랙의 선점을 전부 푼다(finish 뒤·close 때)."""
    def mutate(wt):
        p = wt / CLAIMS_REL
        claims = json.loads(p.read_text(encoding="utf-8") or "{}") if p.exists() else {}
        claims = {k: v for k, v in claims.items() if v.get("track") != track_name}
        p.write_text(json.dumps(claims, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        _publish(repo, mutate, "관제 선점 해제: %s" % track_name)
    except ControlError as e:
        printer("ℹ️ 선점 해제 실패(무해): %s" % str(e).splitlines()[0])


def claim_conflicts(claims, track_name, changed_files, changed_funcs=()):
    """다른 트랙이 선점한 대상을 이 병합이 건드리나 → [(대상, 선점 정보)]."""
    out = []
    files = {f.replace("\\", "/") for f in changed_files}
    funcs = set(changed_funcs)
    for target, info in (claims or {}).items():
        if info.get("track") == track_name:
            continue
        if target in files or target in funcs:
            out.append((target, info))
        elif ":" in target and target.split(":", 1)[0] in files and not funcs:
            out.append((target, info))          # 함수 단위 선점인데 함수 목록을 못 뽑았으면 파일이 겹치는 것으로 경고
    return out


# ── finish 관문 ─────────────────────────────────────────────────────────

class GateResult:
    def __init__(self, ok, fails, notes, cards):
        self.ok, self.fails, self.notes, self.cards = ok, list(fails), list(notes), list(cards)


def finish_gate(repo, stage, br, track_name, printer=print, ownership=None):
    """finish 가 merge_gate 통과 뒤·커밋 전에 부른다(stage = 병합만 된 임시 폴더).
    ① 카드: 트랙에 분배된 카드 또는 커밋 메시지의 '관제 N' — 없으면 실패
    ② 승인: diff 가 고객 화면·과금·고객 데이터에 닿으면 카드에 '승인:' 있어야 함
    ③ 선점: 다른 트랙이 쥔 파일을 건드리면 경고
    ④ 소유권: 주인 함수 시그니처가 지도 밖 파일에 새로 나타나면 실패(ownership_check)"""
    if not installed(repo):
        printer("관제 관문: 미설치 — 건너뜀 (py tools/control.py install)")
        return GateResult(True, [], [], [])
    rules = load_rules(repo)
    g = rules.get("card_gate", DEFAULT_RULES["card_gate"])
    fails, notes = [], []

    cards = cards_from_ref(repo)
    linked = cards_for_track(cards, track_name)
    refs = refs_in_branch(repo, MAIN_REF, br)
    for n in sorted(refs):
        c = find_card(cards, n)
        if c and c not in linked:
            linked.append(c)
        elif c is None:
            notes.append("커밋 메시지의 카드 %03d 는 없는 번호" % n)
    if not linked and g.get("require_card", True):
        fails.append("이 트랙에 관제 카드가 없다 — 카드 없는 병합은 없다(관제 원칙 1).\n"
                     "    등록: py tools/control.py new \"제목\" --track %s\n"
                     "    또는 있는 카드에 연결: py tools/control.py link <번호> %s" % (track_name, track_name))
    else:
        notes.append("카드: " + ", ".join("%03d %s" % (c["번호"], c["제목"]) for c in linked))

    rc, out = _git(stage, "diff", "--cached", "--name-only", "HEAD")
    if rc != 0:
        fails.append("병합 변경 목록을 못 읽었다:\n" + out)
        return GateResult(False, fails, notes, linked)
    changed = [x.strip() for x in out.splitlines() if x.strip()]
    _, diff = _git(stage, "diff", "--cached", "-U0", "HEAD")

    reasons = approval_reasons(changed, diff, rules)
    if reasons and g.get("require_approval", True):
        approved = [c for c in linked if c["승인"].strip()]
        if not approved:
            fails.append("고객에게 보이거나 돈·데이터가 바뀌는 변경인데 카드에 승인이 없다(0순위-A1c):\n"
                         + "\n".join("    · " + r for r in reasons)
                         + "\n    사장님 승인을 받은 뒤: py tools/control.py approve <번호> \"사장님 구두 %s\"" % time.strftime("%Y-%m-%d"))
        else:
            notes.append("승인 필요 변경 %d건 — 카드 %s 승인 있음" % (len(reasons), ", ".join("%03d" % c["번호"] for c in approved)))
    elif reasons:
        notes.append("승인 필요 변경 %d건(규칙상 검사 꺼짐)" % len(reasons))

    for target, info in claim_conflicts(load_claims(repo), track_name, changed):
        notes.append("⚠️ 선점 충돌: %s 는 트랙 %s(카드 %03d)가 쥐고 있다 — 병합은 하되 관제 판단이 필요하다"
                     % (target, info.get("track"), info.get("card", 0)))

    if g.get("ownership_check", True):
        try:
            import ownership_check as oc
            own = ownership if ownership is not None else oc.load_map(repo, MAIN_REF)
            if own is None:
                notes.append("소유권 지도(관제/ownership.json)가 main 에 없다 — 소유권 검사 건너뜀")
            else:
                new_hits = oc.compare_refs(repo, own, base_ref="HEAD", head_index_cwd=stage, changed=changed)
                if new_hits:
                    fails.append("판단 주인 함수의 시그니처가 지도 밖 파일에 **새로** 나타났다(같은 판단 두 벌 — 0순위-B/C):\n"
                                 + "\n".join("    · %s ← %s (%s)" % (h["file"], h["판단"], h["sig"]) for h in new_hits)
                                 + "\n    주인 함수를 부르게 고치거나, 정말 다른 판단이면 관제/ownership.json 의 예외에 사유와 함께 적어라")
                else:
                    notes.append("소유권 검사 통과 (판단 %d개 시그니처, 변경 %d파일)" % (len(own.get("판단", [])), len(changed)))
        except Exception as e:      # noqa: BLE001 — 검사 도구가 죽으면 조용히 통과가 아니라 실패
            fails.append("소유권 검사 도구가 죽었다(조용히 통과하지 않는다): %r" % e)

    for n in notes:
        printer("  관제: " + n)
    return GateResult(not fails, fails, notes, linked)


# ── cli ───────────────────────────────────────────────────────────────

def _print_cards(cards):
    if not cards:
        print("카드 없음.  등록: py tools/control.py new \"제목\"")
        return
    for c in cards:
        appr = " · 승인 " + c["승인"] if c["승인"] else (" · ★승인 필요" if c["승인 필요"].startswith("예") else "")
        print("%03d [%s] %s  — 분배 %s%s" % (c["번호"], c["상태"], c["제목"], c["분배"] or "-", appr))


def main(argv=None):
    try:
        import merge_gate
        merge_gate.make_output_safe()
    except Exception:       # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="관제 — 카드·보드·승인·선점")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install", help="관제 설치(관제/cards·rules·claims 를 main 에)")
    p = sub.add_parser("new", help="카드 등록")
    p.add_argument("title")
    p.add_argument("--from", dest="reporter", default="")
    p.add_argument("--owner", default="", help="판단 주인 파일:함수")
    p.add_argument("--done", default="", help="됐다의 기준(숫자·측정 도구)")
    p.add_argument("--track", default="")
    p.add_argument("--body", default="", help="요청 원문")
    p.add_argument("--approval", choices=["예", "아니오"], default=None)
    sub.add_parser("list", help="카드 목록(origin/main)")
    sub.add_parser("board", help="보드 재생성(main 에 커밋)")
    p = sub.add_parser("show", help="카드 본문")
    p.add_argument("number", type=int)
    p = sub.add_parser("approve", help="승인 표식")
    p.add_argument("number", type=int)
    p.add_argument("who")
    p = sub.add_parser("status", help="상태 변경")
    p.add_argument("number", type=int)
    p.add_argument("state")
    p = sub.add_parser("note", help="이력 메모")
    p.add_argument("number", type=int)
    p.add_argument("text")
    p = sub.add_parser("set", help="칸 값 변경(판단 주인·됐다의 기준·라이브 실측 …)")
    p.add_argument("number", type=int)
    p.add_argument("key")
    p.add_argument("value")
    p = sub.add_parser("link", help="카드에 트랙 분배")
    p.add_argument("number", type=int)
    p.add_argument("track")
    p = sub.add_parser("claim", help="선점 신고")
    p.add_argument("track")
    p.add_argument("number", type=int)
    p.add_argument("targets", nargs="+")
    p = sub.add_parser("release", help="트랙 선점 전부 해제")
    p.add_argument("track")
    args = ap.parse_args(argv)
    repo = main_worktree()
    try:
        if args.cmd == "install":
            install(repo)
        elif args.cmd == "new":
            new_card(repo, args.title, reporter=args.reporter, owner=args.owner, done=args.done, track=args.track,
                     body=args.body, approval=(None if args.approval is None else args.approval == "예"))
        elif args.cmd == "list":
            _git(repo, "fetch", "origin")
            _print_cards(cards_from_ref(repo))
        elif args.cmd == "board":
            sha = _publish(repo, lambda wt: None, "관제 보드 재생성")
            print("보드 갱신 (main %s)" % sha if sha else "바뀐 것 없음")
        elif args.cmd == "show":
            _git(repo, "fetch", "origin")
            c = find_card(cards_from_ref(repo), args.number)
            if c is None:
                raise ControlError("없는 카드: %d" % args.number)
            print(c["body"])
        elif args.cmd == "approve":
            approve(repo, args.number, args.who)
        elif args.cmd == "status":
            set_status(repo, args.number, args.state)
        elif args.cmd == "note":
            note(repo, args.number, args.text)
        elif args.cmd == "set":
            set_field(repo, args.number, args.key, args.value)
        elif args.cmd == "link":
            link_track(repo, args.number, args.track)
        elif args.cmd == "claim":
            claim(repo, args.track, args.number, args.targets)
        elif args.cmd == "release":
            release(repo, args.track)
        return 0
    except ControlError as e:
        print("\n중단: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
