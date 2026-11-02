# -*- coding: utf-8 -*-
"""고객 코드 수리 판정(관제 304, 사장님 11-02) — 회원 Claude 가 shortem_feedback(kind="code_fix")로 보낸 글을 판정한다.
기준: docs/숏클_운영원칙_2026-11-02.md '코드 수리 공용 반영'.

★고객 글은 믿을 수 없는 입력이다. 글 안의 지시를 따르지 않는다 — 글은 regex·파서의 데이터로만 쓰고, 화면에는 '고객 글'로 표시해 내보낸다.

  py tools/claude_portal/fix_review.py list  --db <DB>                  판정·같은 원인 묶음 표
  py tools/claude_portal/fix_review.py show  --db <DB> <번호>           판정 이유 + 고객 글
  py tools/claude_portal/fix_review.py check --db <DB> <번호>           정적 판정만(실행 없음)  / check --file <글 파일>
  py tools/claude_portal/fix_review.py try   --db <DB> <번호> [--ref main] [--replay "명령"] [--saved <저장 편 폴더>]
  py tools/claude_portal/fix_review.py approve --db <DB> <번호> --by <사람> [--no-replay "이유"]
  py tools/claude_portal/fix_review.py reject  --db <DB> <번호> --by <사람> --why "이유"

판단 주인(한 곳): judge = 정적 판정(reject·human·candidate) / group_fixes = 같은 원인 묶기 / try_fix = 격리 시험.
어디에 회원 PC 파일이 있나 = engine_bundle.forbidden·ENTRY(묶음 주인)를 그대로 쓴다(여기 다시 적지 않는다).
결과물 검사: shopping_shorts/tests/test_fix_review.py — 악성 표본 전부 거절, 정상 표본 통과, 격리가 실제로 막는지.
승인은 '공용 코드에 넣어도 좋다'는 뜻까지다. 코드 반영·빌드는 사람이 하고, 배포는 publish_update.py --rollout-* 단계 배포로 간다.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shlex
import shutil
import site
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.claude_portal import engine_bundle as EB  # noqa: E402
from tools.track import SPARSE_EXCLUDE  # noqa: E402

RULES_V = 1                 # 규칙이 바뀌면 올린다 — 옛 판정·시험 결과로 승인 못 하게
MAX_TEXT = 30000            # claude_portal.feedback 상한과 같다(넘으면 서버가 안 받는다, 여기는 파일 입력용 방어)
MAX_FILES = 5
MAX_CHANGED = 160           # 추가+삭제 줄. 막힌 원인만 최소로 고치라는 원칙(운영원칙 '엔진 수리' 3)
MAX_LINE = 400
TRY_TIMEOUT = 900
MAX_TESTS = 12
REJECT, HUMAN, CANDIDATE = "reject", "human", "candidate"

# ── 금지 파일 ─────────────────────────────────────────────────────────────
ENGINE_ROOTS = ("tools/calcopy/", "shopping_shorts/")      # fast_release.target 이 engine/ 으로 보내는 곳 중 코드(channel/ 은 묶음 금지)
_SEG = r"(?:^|[/_.-])"
_END = r"(?:[/_.-]|$)"
FORBIDDEN_FILE = re.compile(
    _SEG + r"(licen[sc]e|sessions?|firewall|leases?|updater?|install\w*|quality|gates?|checks?|audit|guard|answer|auth|secrets?|keys?|vault|"
    r"billing|payment|consent|ad_mark|mark|rules?|lint|forbid\w*|ban|policy|selftest|portal|sandbox)" + _END, re.I)
FORBIDDEN_NAME = re.compile(r"(^|/)(tests?|fixtures|gate_fixtures)/|(^|/)(test_[^/]*|[^/]*_test\.py|conftest\.py|setup\.py|__init__\.py|sitecustomize\.py|flow\.py)$|\.pth$", re.I)

# ── 금지 코드(추가된 줄) ──────────────────────────────────────────────────
NETWORK = re.compile(r"\b(requests|httpx|aiohttp|urllib\d?|http\.client|socket|websockets?|ftplib|smtplib|telnetlib|paramiko|boto3|grpc|ssl)\b"
                     r"|urlopen|\bfetch\s*\(|XMLHttpRequest|Invoke-(WebRequest|RestMethod)|\bcurl\b|\bwget\b|\b(https?|wss?|ftp)://|\b\d{1,3}(\.\d{1,3}){3}\b", re.I)
SHELL = re.compile(r"\bsubprocess\b|\bPopen\b|\bos\.(system|popen|exec\w*|spawn\w*|startfile|posix_spawn\w*)\b|\bfrom\s+os\s+import\b.*\b(system|popen|exec\w*|spawn\w*|startfile)\b"
                   r"|shell\s*=\s*True|\bpty\b|create_subprocess|child_process")
EVAL = re.compile(r"(?<![\w.])(eval|exec|execfile|compile)\s*\(|__import__|\bimportlib\b|\bimport_module\b|__builtins__|\bbuiltins\b|__globals__|__subclasses__|__getattribute__|__code__"
                  r"|__dict__|__class__|\bglobals\s*\(\)|\bctypes\b|\bcffi\b|\bmarshal\b|\bpickle\b|\bshelve\b|\bdill\b|\brunpy\b|\bgetattr\s*\(\s*(os|sys|subprocess|socket)\b"
                  r"|\bsys\.(modules|meta_path|path_hooks|settrace|setprofile|addaudithook)\b|\bsetattr\s*\(\s*(os|sys|subprocess|socket)\b|\bvars\s*\(\s*(os|sys)\b")
BLOB = re.compile(r"[A-Za-z0-9+/_-]{100,}={0,2}|(\\x[0-9a-fA-F]{2}){8,}|(\\u[0-9a-fA-F]{4}){8,}|\b[bB](64|32|16|85)(en|de)code\b|\ba85decode\b|\bbase64\b|\bcodecs\b|\bfromhex\b|\bbinascii\b"
                  r"|\bzlib\b|\blzma\b|\bbz2\b|\bgzip\b|(\bchr\s*\(\s*\d+\s*\)\s*[,+]\s*){2,}|rot_?13")
KEYS = [re.compile(p) for p in (r"sk-ant-[\w-]{8,}", r"\bsk-[A-Za-z0-9_-]{20,}", r"\bgh[pousr]_\w{20,}", r"github_pat_\w+", r"xox[abpr]-[\w-]+", r"\bAKIA[0-9A-Z]{12,}",
                                r"-----BEGIN [A-Z ]*PRIVATE KEY", r"Bearer\s+[A-Za-z0-9._-]{16,}", r"\b[0-9a-fA-F]{40,}\b",
                                r"(?i)(api[_-]?key|token|secret|passw(or)?d)\w*\s*[=:]\s*[\"'][^\"']{8,}[\"']")] + [re.compile(p) for p in EB.SECRETS]
SOFT = re.compile(r"\b(environ|getenv)\b|\bparents?\b\s*[\[.]|\.unlink\s*\(|\bos\.(remove|unlink|rmdir|rename|replace)\b|\bshutil\.\w+|^\s*while\s+True\b")   # 정상일 수도 있다 — 사람이 본다
PATH_OUT = re.compile(r"(?i)[\"'][a-z]:[\\/]|\.\.[\\/]|expanduser|Path\.home|gethomedir|\bHOME\b|USERPROFILE|APPDATA|PROGRAMDATA|[\"']~[\\/]"
                      r"|[\"']/(etc|root|home|usr|var|bin|sbin|opt|users|mnt|dev|proc|sys|tmp)\b|\.ssh\b|authorized_keys|\.claude\b|\.aws\b|\.env\b|\.git[\\/]|CLAUDE\.md|AGENTS\.md"
                      r"|startup[\\/]|crontab|schtasks|launchctl|\breg(\.exe)?\s+add|HKEY_|HKCU|HKLM|sudoers|bashrc|zshrc|profile\.ps1"
                      r"|\bshutil\.(rmtree|chown)\b|\bos\.(chmod|chown|link|symlink)\b|\bsymlink_to\b|\.pem\b")
LICENSE = re.compile(r"(?i)licen[sc]e|라이선스|라이센스|\blease\w*|entitle|fingerprint|_fp_hash|revoked|min_engine|_front\b|is_staff|구독|결제|claude_portal|x-shortem|shortem_[a-z_]*(key|token|dev|skip)")
BYPASS = re.compile(r"(?i)\b(skip|bypass|no|disable|ignore|without)[_-]?(checks?|gates?|verify|validation|audit|guard|qc|lint|review)\w*|\bSKIP_\w+|\bBYPASS\w*|--no-verify|우회|(검사|판정|반려)\s*(생략|건너|끄|끈)"
                    r"|pytest\.(skip|xfail)|mark\.(skip|xfail)|\b(if|while)\s+(False|0|not\s+True)\s*:|\bif\s+True\s*:|\bor\s+True\b|\band\s+False\b"
                    r"|quality_gate|master_guard|\bchecks\.\w+\s*=")
GETATTR_DYN = re.compile(r"\bgetattr\s*\([^,]+,\s*(?![\"'])")
HIDDEN = re.compile("[­​-‏‪-‮⁠-⁩﻿\U000e0000-\U000e007f]|[\x00-\x08\x0b-\x1f\x7f]")
HOMOGLYPH = re.compile("[Ͱ-ϿЀ-ԯＡ-ｚ]")
INJECTION = re.compile(
    r"(?i)ignore\s+(all\s+|any\s+)?(the\s+|your\s+)?(previous|prior|above|earlier|instructions?|rules?)|disregard\s+(the\s+|all\s+|your\s+)?(previous|prior|above|rules?|instructions?)"
    r"|system\s*prompt|you\s+are\s+now|new\s+instructions?|auto[- ]?approve|approve\s+this|mark\s+(this\s+|it\s+)?as\s+(safe|approved|candidate|verified)"
    r"|this\s+(patch|diff|change|fix|code)\s+(is|has\s+been)\s+(safe|verified|approved|reviewed)|do\s+not\s+(flag|report|review|reject|check)|skip\s+(the\s+)?review"
    r"|<\s*/?\s*(system|assistant|instructions?)\s*>|\[\s*(system|inst)\s*\]|\bverdict\s*[:=]|\breviewer\s*:|\bassistant\s*:|as\s+an\s+ai"
    r"|(이전|위|앞|기존)\s*의?\s*(지시|명령|규칙|안내).{0,10}(무시|잊)|(지시|규칙|검사|판정|금지).{0,8}(무시|따르지\s*마)|(승인|통과)\s*(해\s*(줘|주세요|라)|하세요|바람|처리|시켜)|자동\s*승인"
    r"|안전(합니다|하다고)\s*(판단|표시|처리)?\s*(하세요|해\s*줘|하라)?|(검토|리뷰|검사)\s*(없이|생략|불필요)|리뷰어(님)?\s*(에게|께|는|:)|후보로\s*(올|표시|판정)|시스템\s*프롬프트|너는\s*이제|당신은\s*이제|관리자\s*지시")

CHECK_LINE = re.compile(r"\bassert\b|\braise\b|\b\w*(check|verify|validate|gate|guard|audit|lint|reject|forbid|ban|block|fail|deny|refuse)\w*\s*\(|\b(qc|rejects?|fails?|errors?|problems?|issues?|bad)\s*\.\s*append\b|검사|금지|판정|반려", re.I)
CHECK_FUNC = re.compile(r"(?i)(check|verify|validate|gate|guard|audit|lint|reject|forbid|qc|judge|score|grade|review|검사|판정)")
EARLY_OK = re.compile(r"^\s*(return\s+(True|None|\[\]|\{\}|\(\)|0|\"\"|''|\{[\"']ok[\"']\s*:\s*True)|pass\s*$|continue\s*$)")
THRESHOLD_NAME = re.compile(r"(?i)min|max|limit|thresh|floor|ceil|cap\b|bound|cutoff|ratio|rate|score|margin|tol|budget|기준|문턱|하한|상한|한도")
UP_IS_LAX = re.compile(r"(?i)(^|[^a-z])(max|ceil|cap|limit|upper|budget|tol|margin)|상한|한도")
DOWN_IS_LAX = re.compile(r"(?i)(^|[^a-z])(min|floor|lower|thresh|cutoff|score)|하한|문턱|기준")
SEVERITY_DOWN = (re.compile(r"(?i)\b(reject|fail|error|fatal|block|stop|반려|실패|오류|중단)\b"), re.compile(r"(?i)\b(warn\w*|advisory|info|notice|pass|ok|권고|경고|통과)\b"))
SAFE_IMPORT = {"re", "json", "math", "typing", "collections", "itertools", "functools", "dataclasses", "datetime", "time", "string", "unicodedata", "textwrap",
               "statistics", "difflib", "decimal", "fractions", "copy", "enum", "bisect", "heapq", "logging", "pathlib", "random", "operator", "__future__",
               "tools", "shopping_shorts", "numpy"}


@dataclass
class FileDiff:
    path: str = ""                    # 정규화한 저장소 경로
    raw_paths: set = field(default_factory=set)
    added: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    pairs: list = field(default_factory=list)       # 같은 변경 덩어리의 (지운 줄, 넣은 줄) — 기준 바꾸기 판정
    funcs: list = field(default_factory=list)
    hunks: list = field(default_factory=list)       # 원문 줄(정규화 diff 를 다시 쓸 때)
    new_file: bool = False
    meta: list = field(default_factory=list)        # 금지 헤더(삭제·이름 바꾸기·모드·바이너리)


@dataclass
class Fix:
    cause: str = ""
    diff: str = ""
    files: list = field(default_factory=list)
    garbage: list = field(default_factory=list)     # 파서가 못 읽은 줄 — 파서와 git 의 해석 차이 틈을 막는다


def norm_path(p: str) -> str:
    p = p.strip().strip('"').replace("\\", "/")
    p = re.sub(r"^[ab]/", "", p, count=1)
    return re.sub(r"^engine/(?=tools/|shopping_shorts/)", "", p, count=1)   # 회원 복사본은 engine/ 아래. tools/calcopy/engine/ 은 건드리지 않는다


def parse_fix(text: str) -> Fix:
    """code_fix 글 → 원인 + 파일별 변경. 서식 없는 글(diff 없음)도 받는다."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = next((i for i, x in enumerate(lines) if re.match(r"(diff --git |--- \S|\+\+\+ \S|@@ )", x)), None)
    if start is None:
        return Fix(cause=text.strip())
    fix = Fix(cause="\n".join(x for x in lines[:start] if not x.startswith("```")).strip(), diff="\n".join(lines[start:]))
    cur: FileDiff | None = None
    prose: list = []
    i, n = start, len(lines)

    def open_file():
        nonlocal cur
        cur = FileDiff()
        fix.files.append(cur)

    while i < n:
        x = lines[i]
        if x.startswith("diff --git "):
            open_file()
            m = re.match(r'diff --git (\S+|"[^"]+") (\S+|"[^"]+")$', x)
            if m:
                cur.raw_paths |= {m[1], m[2]}
            else:
                cur.meta.append("diff 머리줄을 읽을 수 없음")
        elif re.match(r"(new file mode|index [0-9a-f]+\.\.)", x):
            if cur is None:
                open_file()
            if x.startswith("new file"):
                cur.new_file = True
                if not x.endswith("100644"):
                    cur.meta.append(f"실행·링크 권한 새 파일: {x}")
        elif re.match(r"(deleted file mode|old mode|new mode|similarity index|dissimilarity index|rename |copy |Binary files|GIT binary patch)", x):
            if cur is None:
                open_file()
            cur.meta.append(x[:60])
        elif x.startswith("--- ") or x.startswith("+++ "):
            if cur is None or (x.startswith("--- ") and cur.hunks):
                open_file()
            p = x[4:].split("\t")[0].strip()
            if p == "/dev/null":
                cur.new_file = cur.new_file or x.startswith("--- ")
                if x.startswith("+++ "):
                    cur.meta.append("파일 삭제")
            else:
                cur.raw_paths.add(p)
        elif x.startswith("@@ "):
            m = re.match(r"@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@(.*)$", x)
            if cur is None or not m:
                fix.garbage.append(x[:80])
                i += 1
                continue
            a, b = int(m[1] if m[1] is not None else 1), int(m[2] if m[2] is not None else 1)
            f = re.search(r"\b(?:def|class)\s+(\w+)", m[3])
            if f:
                cur.funcs.append(f[1])
            cur.hunks.append(x)
            rem, add = [], []
            i += 1
            while i < n and (a > 0 or b > 0):
                y = lines[i]
                if y.startswith("\\"):
                    pass
                elif y.startswith("-"):
                    a -= 1
                    rem.append(y[1:])
                elif y.startswith("+"):
                    b -= 1
                    add.append(y[1:])
                elif y.startswith(" ") or y == "":
                    a -= 1
                    b -= 1
                    cur.pairs.append((rem, add))
                    cur.removed += rem
                    cur.added += add
                    rem, add = [], []
                else:
                    fix.garbage.append(y[:80])
                    break
                cur.hunks.append(y)
                i += 1
            cur.pairs.append((rem, add))
            cur.removed += rem
            cur.added += add
            continue
        elif x.startswith("\\") or x.strip() in ("", "```") or x.startswith("-- "):
            pass
        elif x[0] in "+-@":                  # 덩어리 줄 수 밖의 변경 줄 — git 과 해석이 갈리는 틈(밀수)
            fix.garbage.append(x[:80])
        else:
            prose.append(x)                  # diff 뒤 설명 글 — 적용되지 않는다(clean_diff 가 덩어리만 다시 쓴다). 글로 친다
        i += 1
    if prose:
        fix.cause = (fix.cause + "\n" + "\n".join(prose)).strip()
    fix.files = [f for f in fix.files if f.raw_paths or f.hunks or f.meta]
    for f in fix.files:
        ps = {norm_path(p) for p in f.raw_paths}
        f.path = sorted(ps)[0] if ps else ""
        if len(ps) > 1:
            f.meta.append(f"앞뒤 파일 이름이 다름: {sorted(ps)[:2]}")
    return fix


def code_part(line: str) -> str:
    """파이썬 주석을 뗀 줄(따옴표 안 # 는 남긴다)."""
    q = None
    i = 0
    while i < len(line):
        ch = line[i]
        if q:
            if ch == "\\":
                i += 1
            elif ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#":
            return line[:i]
        i += 1
    return line


def squash(line: str) -> str:
    """'sub'+'process' · "ev" "al" 같은 쪼개기를 붙여 본다."""
    return re.sub(r"[\"']\s*\+?\s*[\"']", "", line)


def _changed_numbers(a: str, b: str):
    """숫자만 다른 두 줄이면 (옛 값들, 새 값들), 아니면 None."""
    num = r"(?<![\w.])-?\d+(?:\.\d+)?"
    if a.strip() == b.strip() or re.sub(num, "#", a).strip() != re.sub(num, "#", b).strip():
        return None
    return [float(x) for x in re.findall(num, a)], [float(x) for x in re.findall(num, b)]


def _threshold_verdict(old: str, new: str):
    """기준 숫자를 바꾼 줄 — 느슨해지면 reject, 방향을 모르면 human, 조여지거나 기준이 아니면 None."""
    got = _changed_numbers(old, new)
    if not got:
        return None
    before, after = got
    code = code_part(new)
    delta = next(((x, y) for x, y in zip(before, after) if x != y), None)
    if not delta:
        return None
    up = delta[1] > delta[0]
    cmp_m = re.search(r"(>=|<=|>|<)\s*-?\d", code)
    if cmp_m:
        lax = (not up) if cmp_m[1].startswith(">") else up
        return REJECT if lax else None
    name = code.split("=")[0] if "=" in code else code
    if not THRESHOLD_NAME.search(name):
        return None
    if UP_IS_LAX.search(name):
        return REJECT if up else None
    if DOWN_IS_LAX.search(name):
        return REJECT if not up else None
    return HUMAN


def _count(rx, lines) -> int:
    return sum(len(rx.findall(squash(code_part(x)))) for x in lines)


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _file_rules(f: FileDiff, add) -> None:
    """파일 하나의 금지 파일·금지 코드·검사 약화."""
    p = f.path
    if not re.fullmatch(r"[\w가-힣][\w가-힣./-]*", p or "") or ".." in p.split("/"):      # 콜론(NTFS 스트림)·공백·따옴표·절대경로 포함
        add(REJECT, "path", f"바깥 경로: {p!r}")
        return
    bad = EB.forbidden(p)
    if bad:
        add(REJECT, "forbidden_file", f"회원 PC 묶음 금지 파일: {p} ({bad})")
    if not p.endswith(".py"):
        add(REJECT, "forbidden_file", f"파이썬 엔진 파일만 받는다: {p}")
    if FORBIDDEN_FILE.search(p.rsplit("/", 1)[-1]) or FORBIDDEN_NAME.search(p):
        add(REJECT, "forbidden_file", f"금지 파일(검사·금지선·라이선스·세션·firewall·lease·updater·install 등): {p}")
    if not p.startswith(ENGINE_ROOTS):
        add(REJECT, "forbidden_file", f"엔진 밖 파일: {p}")
    elif p.startswith("shopping_shorts/") and p not in EB.ENTRY:
        add(HUMAN, "not_in_bundle", f"회원 PC 묶음 입구 목록에서 확인되지 않음: {p}")
    if f.meta:
        add(REJECT, "meta", f"{p}: 삭제·이름 바꾸기·권한·바이너리 변경 금지 — {f.meta[:2]}")
    if f.new_file:
        add(HUMAN, "new_file", f"새 파일: {p}")

    for ln in f.added:
        if len(ln) > MAX_LINE:
            add(REJECT, "long_line", f"{p}: {len(ln)}자 긴 줄")
        if HIDDEN.search(ln):
            add(REJECT, "hidden", f"{p}: 숨은 문자(제어·너비 0·방향 바꾸기)")
        if HOMOGLYPH.search(code_part(ln)):
            add(REJECT, "hidden", f"{p}: 다른 글자로 꾸민 문자")
        if BLOB.search(ln):
            add(REJECT, "blob", f"{p}: 인코딩 덩어리·풀기 코드 — {ln.strip()[:60]}")
        if any(k.search(ln) for k in KEYS):
            add(REJECT, "secret", f"{p}: 키·토큰 꼴(값은 표시 안 함)")
        if INJECTION.search(ln):
            add(REJECT, "injection", f"{p}: 코드 안 지시 글귀 — 엔진 글은 회원 Claude 에게 전달될 수 있다")
        c = squash(code_part(ln))
        if EVAL.search(c):
            add(REJECT, "eval", f"{p}: 동적 실행·내부 접근 — {ln.strip()[:60]}")
        if PATH_OUT.search(c):
            add(REJECT, "path_out", f"{p}: 작업 폴더 밖 접근 — {ln.strip()[:60]}")
        if LICENSE.search(c):
            add(REJECT, "license", f"{p}: 라이선스·기기·구독 관련 변경 — {ln.strip()[:60]}")
        if BYPASS.search(c):
            add(REJECT, "bypass", f"{p}: 검사 우회 — {ln.strip()[:60]}")
        if SOFT.search(c):
            add(HUMAN, "soft", f"{p}: 환경변수·상위 폴더·지우기·끝없는 반복 — {ln.strip()[:60]}")
        if GETATTR_DYN.search(c):
            add(HUMAN, "getattr", f"{p}: 동적 속성 — {ln.strip()[:60]}")
        m = re.match(r"\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", c)
        if m and (m[1] or m[2]).split(".")[0] not in SAFE_IMPORT:
            add(HUMAN, "new_import", f"{p}: 새 import — {ln.strip()[:60]}")
        if re.search(r"except\b[^:]*:\s*(pass|continue)\s*$", c):
            add(HUMAN, "silent_except", f"{p}: 조용한 실패 — {ln.strip()[:60]}")

    for code, rx, label in (("network", NETWORK, "네트워크 호출"), ("shell", SHELL, "쉘 실행")):
        up = _count(rx, f.added) - _count(rx, f.removed)
        if up > 0:
            add(REJECT, code, f"{p}: {label} 추가")
        elif _count(rx, f.added):
            add(HUMAN, code, f"{p}: 기존 {label} 줄을 바꿈 — 사람이 본다")

    # 검사 지우기 — 없어진 검사 줄(주석 처리 포함)
    kept = {_norm_ws(code_part(x)) for x in f.added}
    gone = [x for x in f.removed if CHECK_LINE.search(code_part(x)) and code_part(x).strip() and _norm_ws(code_part(x)) not in kept]
    fresh = [x for x in f.added if CHECK_LINE.search(code_part(x))]
    if len(gone) > len(fresh):
        add(REJECT, "weaken", f"{p}: 검사 삭제 — {gone[0].strip()[:60]}")
    elif gone:
        add(HUMAN, "weaken", f"{p}: 검사 줄을 바꿈 — {gone[0].strip()[:60]}")
    if any(CHECK_FUNC.search(fn) for fn in f.funcs) and any(EARLY_OK.match(x) for x in f.added):
        add(REJECT, "weaken", f"{p}: 검사 함수 안에 무조건 통과 추가")

    for rem, adds in f.pairs:
        for old, new in zip(rem, adds):
            t = _threshold_verdict(old, new)
            if t:
                add(t, "threshold", f"{p}: 기준 변경 {old.strip()[:40]} → {new.strip()[:40]}")
            if SEVERITY_DOWN[0].search(code_part(old)) and SEVERITY_DOWN[1].search(code_part(new)) and not SEVERITY_DOWN[1].search(code_part(old)):
                add(REJECT, "severity", f"{p}: 실패를 경고로 낮춤 — {new.strip()[:60]}")
            a, b = code_part(old), code_part(new)
            if re.search(r"(>=|<=|==|!=|<|>)", a) and re.sub(r"(>=|<=|==|!=|<|>)", "@", a).strip() == re.sub(r"(>=|<=|==|!=|<|>)", "@", b).strip() and a.strip() != b.strip():
                add(HUMAN, "compare", f"{p}: 비교 연산 변경 — {new.strip()[:60]}")


def error_phrase(cause: str) -> str:
    """같은 원인 묶기용 오류 문구 — 숫자·경로·따옴표 값을 지워 회원마다 달라지는 부분을 없앤다."""
    named = re.search(r"\b\w*(?:Error|Exception)\b", cause)        # 오류 이름이 있으면 이름으로(설명 글은 회원마다 다르다)
    if named:
        return named[0].lower()
    line = next((x for x in cause.splitlines() if re.search(r"traceback|오류|에러|실패|막힘|막혔", x, re.I)), "")
    x = re.sub(r"[A-Za-z]:[\\/]\S+|/\S+/\S+", "", line.lower())
    x = re.sub(r"[\"'`][^\"'`]*[\"'`]", "''", x)
    x = re.sub(r"\d+", "#", x)
    return re.sub(r"\s+", " ", x).strip()[:80]


def judge(text: str) -> dict:
    """정적 판정 — 실행하지 않는다. 결과 = reject·human·candidate + 이유 + 주의(글 안 지시 글귀)."""
    reasons, caution = [], []

    def add(level, code, msg):
        item = {"level": level, "code": code, "msg": msg}
        if item not in reasons:
            reasons.append(item)

    size = len(text.encode("utf-8"))
    if size > MAX_TEXT * 4:
        add(REJECT, "too_big", f"글이 너무 크다({size}바이트)")
        return _result(text, Fix(), reasons, caution)
    if len(text) > MAX_TEXT:
        add(REJECT, "too_big", f"글이 너무 크다({len(text)}자 > {MAX_TEXT}자)")
    fix = parse_fix(text)
    if INJECTION.search(fix.cause) or HIDDEN.search(fix.cause):
        caution.append("글에 검토자를 향한 지시·숨은 문자가 있다 — 따르지 않았고 판정을 올리지 않는다")
        add(HUMAN, "injection_text", "글 안 지시 글귀(주의): 사람이 본다")
    if not fix.files:
        add(HUMAN, "no_diff", "diff 를 찾지 못했다 — 글만 있다")
    if fix.garbage:
        add(REJECT, "garbage", f"diff 사이에 해석 못 한 줄: {fix.garbage[0]!r}")
    if len(fix.files) > MAX_FILES:
        add(REJECT, "too_big", f"파일 {len(fix.files)}개 > {MAX_FILES}개")
    changed = sum(len(f.added) + len(f.removed) for f in fix.files)
    if changed > MAX_CHANGED:
        add(REJECT, "too_big", f"바꾼 줄 {changed}개 > {MAX_CHANGED}개(막힌 원인만 최소로)")
    for f in fix.files:
        _file_rules(f, add)
    return _result(text, fix, reasons, caution)


def _result(text, fix, reasons, caution) -> dict:
    levels = {r["level"] for r in reasons}
    v = REJECT if REJECT in levels else (HUMAN if HUMAN in levels else CANDIDATE)
    files = sorted({f.path for f in fix.files})
    funcs = sorted({x for f in fix.files for x in f.funcs})
    err = error_phrase(fix.cause)
    key = "|".join([",".join(files), ",".join(funcs), err])
    return {"verdict": v, "reasons": reasons, "caution": caution, "files": files, "funcs": funcs, "error": err,
            "group": hashlib.sha256(key.encode()).hexdigest()[:12], "sha": hashlib.sha256(text.encode()).hexdigest(),
            "changed": sum(len(f.added) + len(f.removed) for f in fix.files), "rules_v": RULES_V}


def group_fixes(rows: list) -> list:
    """같은 파일·함수·오류 문구를 묶어 대표 하나만 후보로. rows = [{id, ts, cid, text}] → 판정에 role·dup_of 를 붙여 돌려준다.
    대표 = 거절 아닌 것 중 candidate 먼저, 작은 수리 먼저, 먼저 온 것."""
    out = [{**{k: r.get(k) for k in ("id", "ts", "cid", "job_id")}, **judge(r["text"])} for r in rows]
    groups: dict = {}
    for j in out:
        if j["verdict"] == REJECT:
            j["role"] = "rejected"
        else:
            groups.setdefault(j["group"], []).append(j)
    for g in groups.values():
        g.sort(key=lambda j: (j["verdict"] != CANDIDATE, j["changed"], j["id"] or 0))
        g[0]["role"], g[0]["same"] = "lead", len(g)
        for j in g[1:]:
            j["role"], j["dup_of"] = "duplicate", g[0]["id"]
    return out


# ── 격리 시험 ─────────────────────────────────────────────────────────────
GUARD = r'''# 격리 시험 지킴이 — fix_review 가 저장소 밖에 쓴다. PYTHONPATH 로 모든 파이썬 프로세스(자식 포함)에 먼저 실린다.
import os, re, sys
list2 = lambda x: " ".join(os.fsdecode(i) for i in x) if x else ""
_R = [os.path.normcase(os.path.abspath(x)) for x in os.environ["FIX_SANDBOX_ROOTS"].split(os.pathsep)]
_L = os.environ["FIX_SANDBOX_LOG"]
_EXE = set(os.environ.get("FIX_SANDBOX_EXE", "").split(","))
_SECRET = (".pem", ".env", ".ssh", ".claude", "id_rsa", "id_ed25519", ".aws")
_PY = tuple(os.path.normcase(os.path.abspath(x)) + os.sep for x in {sys.prefix, sys.base_prefix})   # 파이썬 설치 폴더 안 패키지 이름은 비밀이 아니다
_busy = [False]
_open = open
def _deny(kind, what):
    if not _busy[0]:
        _busy[0] = True
        try:
            with _open(_L, "a", encoding="utf-8") as f:
                f.write(f"{kind}\t{str(what)[:200]}\n")
        finally:
            _busy[0] = False
    raise PermissionError(f"격리 시험: {kind} 차단: {what}")
def _local(h):
    return str(h) in ("localhost", "127.0.0.1", "::1", "", "None")
def _inside(p):
    if p.lower() in ("/dev/null", "nul", "\\\\.\\nul"):
        return True
    p = os.path.normcase(os.path.abspath(p))
    return any(p == r or p.startswith(r + os.sep) for r in _R)
def _hook(ev, a):
    if _busy[0]:
        return
    if ev == "socket.connect" or ev == "socket.sendto":
        addr = a[1]
        if isinstance(addr, tuple) and not _local(addr[0]):
            _deny("network", addr)
    elif ev in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
        if not _local(a[0]):
            _deny("network", a[0])
    elif ev == "subprocess.Popen":
        exe = a[0]
        if not exe:                                  # 윈도우는 args 가 한 줄 글로 올 수 있다
            line = a[1] if isinstance(a[1], str) else list2(a[1])
            m = re.match(r'\s*"([^"]+)"|\s*(\S+)', line)
            exe = (m[1] or m[2]) if m else ""
        name = os.path.basename(str(exe)).lower().removesuffix(".exe")
        tail = a[1].split() if isinstance(a[1], str) else [os.fsdecode(i) for i in (a[1] or ())]
        if name not in _EXE or (name.startswith("py") and {"-I", "-S", "-E", "-P"} & set(tail)):     # 파이썬 자식이 지킴이를 벗는 길
            _deny("process", exe)
    elif ev in ("os.system", "os.exec", "os.spawn", "os.posix_spawn", "os.startfile"):
        _deny("process", a[0] if a else ev)
    elif ev == "open":
        path, mode, flags = a
        if isinstance(path, (str, bytes)) and not isinstance(path, int):
            p = os.fsdecode(path)
            low = p.replace("\\", "/").lower()
            wr = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
            if wr and not _inside(p):
                _deny("write", p)
            if not _inside(p) and any(s in low for s in _SECRET) and not os.path.normcase(os.path.abspath(p)).startswith(_PY):
                _deny("read", p)
    elif ev == "sqlite3.connect":
        p = a[0]
        if isinstance(p, (str, bytes)) and os.fsdecode(p) != ":memory:" and not _inside(os.fsdecode(p)):
            _deny("read", p)
    elif ev in ("os.remove", "os.rename", "os.rmdir", "shutil.rmtree", "os.mkdir"):
        p = a[0]
        if isinstance(p, (str, bytes)) and not _inside(os.fsdecode(p)):
            _deny("write", p)
sys.addaudithook(_hook)
'''
SANDBOX_EXE = "python,python3,py,ffmpeg,ffprobe"      # git·node 는 지킴이가 안 따라간다 — 필요한 시험은 실패로 드러나고 사람이 본다
ENV_KEEP = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL")


def os_net_prefix() -> list:
    """리눅스 서버면 네트워크 이름공간까지 뺀다(되는지 실제로 재서 결정). 윈도우는 파이썬 지킴이만."""
    if not sys.platform.startswith("linux") or not shutil.which("unshare"):
        return []
    try:
        if subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=10).returncode == 0:
            return ["unshare", "-rn"]
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[fix_review] unshare 확인 실패 — 파이썬 지킴이만 쓴다: {e}", file=sys.stderr)
    return []


def sandbox_env(sb: Path, roots: list) -> dict:
    """★넘길 것만 적는다(지울 것을 적지 않는다) — 키·토큰은 처음부터 안 들어온다."""
    env = {k: os.environ[k] for k in ENV_KEEP if k in os.environ}
    home = sb / "home"
    tmp = sb / "tmp"
    home.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    guard = sb / "guard"
    guard.mkdir(exist_ok=True)
    (guard / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home), LOCALAPPDATA=str(home), TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp),
               PYTHONPATH=str(guard), PYTHONUSERBASE=site.getuserbase(), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTEST_ADDOPTS="-p no:cacheprovider",
               FIX_SANDBOX_ROOTS=os.pathsep.join(str(x) for x in [*roots, sb]), FIX_SANDBOX_LOG=str(sb / "violations.log"), FIX_SANDBOX_EXE=SANDBOX_EXE)
    return env


def run_sandboxed(cmd: list, cwd: Path, sb: Path, roots: list, timeout=TRY_TIMEOUT) -> dict:
    """격리 실행 하나. 시간 넘기면 프로세스 나무째 끈다. 지킴이가 막은 것은 violations 로 돌려준다."""
    env = sandbox_env(sb, roots)
    log_f = sb / "violations.log"
    start = log_f.stat().st_size if log_f.is_file() else 0
    p = subprocess.Popen([*os_net_prefix(), *cmd], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         encoding="utf-8", errors="replace")
    t0 = time.time()
    try:
        out, _ = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        p.kill()
        out, _ = p.communicate()
        rc = "timeout"
    v = []
    if log_f.is_file():
        with open(log_f, encoding="utf-8") as f:
            f.seek(start)
            v = [x.strip() for x in f if x.strip()]
    return {"cmd": [str(x) for x in cmd], "rc": rc, "sec": round(time.time() - t0, 1), "out": (out or "")[-6000:], "violations": v[:20]}


def _git(repo, *a, check=True, inp=None):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, encoding="utf-8", errors="replace", input=inp)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(map(str, a[:3]))} 실패: {(r.stderr or r.stdout)[-300:]}")
    return r


def clean_diff(fix: Fix) -> str:
    """git 에 넘길 diff — 파서가 읽은 파일·덩어리만 다시 쓴다(파서가 못 본 것이 적용되는 틈을 없앤다)."""
    out = []
    for f in fix.files:
        out += [f"diff --git a/{f.path} b/{f.path}"]
        out += ["new file mode 100644"] if f.new_file else []
        out += ["--- /dev/null" if f.new_file else f"--- a/{f.path}", f"+++ b/{f.path}", *f.hunks]
    return "\n".join(out) + "\n"


def deep_check(before: str, after: str) -> list:
    """적용한 뒤 파일 전체를 AST 로 — 줄 정규식이 못 보는 것(여러 줄에 쪼갠 호출, 합쳐 만든 글자). 실행 없이 본다."""
    def facts(src):
        tree = ast.parse(src)
        names, strs = set(), set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                names |= {(n.module or "").split(".")[0], *(a.name for a in n.names)}
            elif isinstance(n, ast.Attribute):
                names.add(n.attr)
            elif isinstance(n, ast.Name):
                names.add(n.id)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                strs.add(n.value)
            elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
                parts = [x.value for x in ast.walk(n) if isinstance(x, ast.Constant) and isinstance(x.value, str)]
                strs.add("".join(parts))
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "join":
                strs.add("".join(x.value for x in ast.walk(n) if isinstance(x, ast.Constant) and isinstance(x.value, str)))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) >= 2 \
                    and not isinstance(n.args[1], ast.Constant):
                names.add("getattr-dynamic")
        return names, strs

    bad_names = {"eval", "exec", "compile", "__import__", "importlib", "subprocess", "Popen", "system", "popen", "socket", "requests", "urllib", "httpx", "aiohttp",
                 "ctypes", "pickle", "marshal", "getattr-dynamic", "b64decode", "fromhex"}
    n0, s0 = facts(before)
    n1, s1 = facts(after)
    new = sorted(n1 - n0)
    out = [f"새 이름: {x}" for x in new if x in bad_names]
    for s in sorted(s1 - s0):
        if len(s) < 300 and (NETWORK.search(s) or SHELL.search(s) or EVAL.search(s) or PATH_OUT.search(s)):
            out.append(f"새 글자: {s[:50]!r}")
    return out


def related_tests(wt: Path, files: list) -> list:
    """바꾼 모듈 이름을 부르는 시험 파일 — 많이 부르는 순."""
    stems = [Path(f).stem for f in files]
    found = []
    for d in ("shopping_shorts/tests", "tools"):
        root = wt / d
        if not root.is_dir():
            continue
        for t in root.rglob("test_*.py"):
            if t.name == "test_fix_review.py":      # 이 도구의 시험 — 표본 경로로 엔진 파일 이름을 적을 뿐이다
                continue
            try:
                src = t.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            n = sum(len(re.findall(rf"\b{re.escape(s)}\b", src)) for s in stems)
            if n:
                found.append((-n, t.relative_to(wt).as_posix()))
    return [x for _, x in sorted(found)[:MAX_TESTS]]


def _failed(out: str) -> set:
    return set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M))


def _replay(cmd, saved, wt, sb, roots, label):
    """저장 편 재현 — 저장 폴더는 복사본으로(재현 도구가 덮어쓴다, plan_replay 주의문)."""
    args = shlex.split(cmd, posix=True)
    work = None
    if saved:
        work = sb / f"saved_{label}"
        shutil.copytree(saved, work)
        args = [a.replace("{saved}", str(work)) for a in args]
    args = [sys.executable if a in ("py", "python", "python3") else a for a in args]
    return run_sandboxed(args, wt, sb, [*roots, *( [work] if work else [])], timeout=TRY_TIMEOUT)


def try_fix(text: str, repo, ref="HEAD", tests=None, replay=None, saved=None, human_ok="", timeout=TRY_TIMEOUT) -> dict:
    """임시 worktree 에 적용 → 정적·AST 재판정 → 격리 pytest → 저장 편 재현. 고객 코드는 정적 판정을 통과해야 비로소 실행된다."""
    j = judge(text)
    res = {"status": "refused", "verdict": j["verdict"], "sha": j["sha"], "rules_v": RULES_V, "ref": ref, "at": int(time.time()), "isolation": "os_net+guard" if os_net_prefix() else "guard_only"}
    if j["verdict"] == REJECT:
        return {**res, "why": "정적 판정 거절 — 실행하지 않는다", "reasons": j["reasons"]}
    if j["verdict"] == HUMAN and not human_ok:
        return {**res, "why": "사람 확인 대상 — 사람이 읽고 --human-ok <이름> 을 줄 때만 실행한다", "reasons": j["reasons"]}
    fix = parse_fix(text)
    if not fix.files:
        return {**res, "why": "적용할 diff 가 없다"}
    res["human_ok"] = human_ok
    sb = Path(tempfile.mkdtemp(prefix="fixtry_"))
    wt = sb / "wt"
    added = False
    try:
        _git(repo, "worktree", "add", "--no-checkout", "--detach", str(wt), ref)
        added = True
        # 코드가 안 읽는 무거운 폴더만 뺀다(트랙과 같은 목록). ★코드 폴더를 골라 담으면 pipeline/ 같은 것이 빠져 시험이 안 돈다
        _git(wt, "sparse-checkout", "set", "--no-cone", "/*", *("!" + x for x in SPARSE_EXCLUDE))
        _git(wt, "checkout", "--quiet", "HEAD")
        patch = sb / "fix.diff"
        patch.write_text(clean_diff(fix), encoding="utf-8", newline="\n")
        r = _git(wt, "apply", "--check", "--whitespace=nowarn", str(patch), check=False)
        if r.returncode:
            return {**res, "status": "apply_failed", "why": (r.stderr or r.stdout)[-400:]}
        _git(wt, "apply", "--whitespace=nowarn", str(patch))
        _git(wt, "add", "-N", ".")
        actual = _git(wt, "diff", "HEAD").stdout
        names = sorted(x for x in _git(wt, "diff", "HEAD", "--name-only").stdout.splitlines() if x)
        if names != sorted({f.path for f in fix.files}):
            return {**res, "status": "refused", "why": f"적용된 파일이 판정한 파일과 다르다: {names}"}
        j2 = judge(actual)
        if j2["verdict"] == REJECT:
            return {**res, "status": "refused", "why": "적용 결과를 다시 판정하니 거절", "reasons": j2["reasons"]}
        deep = []
        for p in names:
            before = "" if any(f.path == p and f.new_file for f in fix.files) else _git(wt, "show", f"HEAD:{p}").stdout
            try:
                deep += deep_check(before, (wt / p).read_text(encoding="utf-8"))
            except SyntaxError as e:
                return {**res, "status": "failed", "why": f"문법 오류 {p}: {e}"}
        if deep:
            return {**res, "status": "refused", "why": "AST 재판정 거절 — 실행하지 않는다", "deep": deep[:10]}

        roots = [wt]
        picked = tests if tests is not None else related_tests(wt, names)
        res["tests"] = picked
        res["pytest"] = None
        ok = True
        if not picked:
            res["why"] = "관련 시험을 찾지 못했다"
            ok = False
        else:
            cmd = [sys.executable, "-m", "pytest", "-q", "--tb=line", "-rfE", *picked]
            after = run_sandboxed(cmd, wt, sb, roots, timeout)
            res["pytest"] = after
            m = re.search(r"(\d+) passed", after["out"])
            res["passed_n"] = int(m[1]) if m else 0
            if after["rc"] not in (0, 1):              # 시간 초과·pytest 자체 오류·수집 0건
                ok = False
                res["why"] = f"시험이 끝까지 돌지 못했다(rc={after['rc']})"
            elif after["rc"] == 1:                     # 고치기 전에도 실패하던 것은 수리 탓이 아니다
                _git(wt, "apply", "-R", "--whitespace=nowarn", str(patch))
                base = run_sandboxed(cmd, wt, sb, roots, timeout)
                _git(wt, "apply", "--whitespace=nowarn", str(patch))
                new_fail = sorted(_failed(after["out"]) - _failed(base["out"]))
                res["base_failed"] = sorted(_failed(base["out"]))[:30]
                res["new_failed"] = new_fail[:30]
                ok = not new_fail and bool(_failed(after["out"]))
            if ok and not res["passed_n"]:             # ★오류가 고치기 전과 같아도 아무것도 안 돈 것이다(11-02 실사고)
                ok = False
                res["why"] = "시험이 실제로 돌지 않았다 — 통과한 시험 0개"
            if after["violations"]:
                ok = False
        res["replay"] = []
        for i, c in enumerate(replay or []):
            _git(wt, "apply", "-R", "--whitespace=nowarn", str(patch))
            base = _replay(c, saved, wt, sb, roots, f"base{i}")
            _git(wt, "apply", "--whitespace=nowarn", str(patch))
            after = _replay(c, saved, wt, sb, roots, f"fix{i}")
            res["replay"].append({"cmd": c, "before_rc": base["rc"], "before": base["out"][-1500:], "after": after})
            ok = ok and after["rc"] == 0 and not after["violations"]
        res["status"] = "passed" if ok else "failed"
        return res
    finally:
        if added:                       # ★worktree prune 금지(D 드라이브 트랙 등록이 지워진다) — 내 것만 뗀다
            r = _git(repo, "worktree", "remove", "--force", str(wt), check=False)
            if r.returncode:
                print(f"[fix_review] 임시 worktree 제거 실패 — 손으로 치워야 한다: {wt}: {r.stderr[-200:]}", file=sys.stderr)
        shutil.rmtree(sb, ignore_errors=True)
        if sb.exists():
            print(f"[fix_review] 임시 폴더가 남았다: {sb}", file=sys.stderr)


# ── 기록·명령 ─────────────────────────────────────────────────────────────
def review_dir() -> Path:
    from shopping_shorts import claude_portal as cp
    d = cp.store_dir() / "fix_review"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _rec_path(fid) -> Path:
    return review_dir() / f"{int(fid)}.json"


def load_rec(fid) -> dict:
    p = _rec_path(fid)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_rec(fid, **kw) -> dict:
    rec = {**load_rec(fid), **kw}
    tmp = _rec_path(fid).with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _rec_path(fid))
    return rec


def load_fixes(store) -> list:
    from shopping_shorts import claude_portal as cp
    cp.ensure_schema(store)
    with cp._tx(store) as c:
        return cp._rows(c, "SELECT id, ts, cid, text, job_id FROM claude_feedback WHERE kind='code_fix' ORDER BY id")


def _one(store, fid) -> tuple:
    rows = load_fixes(store)
    row = next((r for r in rows if r["id"] == fid), None)
    if not row:
        raise SystemExit(f"[fix_review] code_fix #{fid} 없음")
    return row, next(j for j in group_fixes(rows) if j["id"] == fid)


def approve(row: dict, grouped: dict, by: str, no_replay: str = "") -> dict:
    """승인 관문 — 대표 수리 + 지금 규칙으로도 거절 아님 + 같은 글로 격리 시험 통과 + 저장 편 재현(없으면 사유) + 사람 이름."""
    if not str(by or "").strip():
        raise SystemExit("[fix_review] 승인한 사람 이름(--by)이 필요하다")
    if grouped["verdict"] == REJECT:
        raise SystemExit("[fix_review] 거절 판정은 승인할 수 없다")
    if grouped.get("role") == "duplicate":
        raise SystemExit(f"[fix_review] 대표는 #{grouped['dup_of']} 이다")
    t = load_rec(row["id"]).get("try") or {}
    if t.get("status") != "passed" or t.get("sha") != grouped["sha"] or t.get("rules_v") != RULES_V:
        raise SystemExit("[fix_review] 이 글·이 규칙으로 통과한 격리 시험이 없다 — try 를 먼저")
    if not t.get("replay") and not no_replay.strip():
        raise SystemExit("[fix_review] 저장 편 재현이 없다 — try --replay 또는 --no-replay \"이유\"")
    return save_rec(row["id"], state="approved", by=by.strip(), at=int(time.time()), no_replay=no_replay.strip())


def _plain(s: str) -> str:
    """터미널 제어 문자를 지워 고객 글이 화면을 조작하지 못하게."""
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]|\x1b\[[0-9;]*[A-Za-z]", " ", s)


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("list", "show", "check", "try", "approve", "reject"))
    ap.add_argument("id", nargs="?", type=int)
    ap.add_argument("--db")
    ap.add_argument("--file", help="check·try: 서버 DB 대신 글 파일")
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--replay", action="append", default=[], help="저장 편 재현 명령. {saved} = --saved 복사본")
    ap.add_argument("--saved", help="저장 편 폴더(복사본으로 돈다)")
    ap.add_argument("--tests", nargs="*", help="시험 파일을 직접 지정")
    ap.add_argument("--human-ok", default="", help="사람 확인 대상을 사람이 읽었다 — 이름")
    ap.add_argument("--by", default="")
    ap.add_argument("--why", default="")
    ap.add_argument("--no-replay", default="", help="approve: 재현 없이 승인하는 이유")
    a = ap.parse_args(argv)
    if a.file:
        text = Path(a.file).read_text(encoding="utf-8")
        if a.cmd == "check":
            print(json.dumps(judge(text), ensure_ascii=False, indent=1))
            return 0
        if a.cmd == "try":
            r = try_fix(text, a.repo, a.ref, a.tests, a.replay, a.saved, a.human_ok)
            print(json.dumps(r, ensure_ascii=False, indent=1))
            return 0 if r["status"] == "passed" else 1
        raise SystemExit("--file 은 check·try 만")
    if not a.db:
        raise SystemExit("--db 필요(서버 reference.db)")
    from shopping_shorts.store import Store
    store = Store(a.db)
    if a.cmd == "list":
        rows = group_fixes(load_fixes(store))
        for j in rows:
            rec = load_rec(j["id"])
            print(f"#{j['id']} cid {j['cid']} {j['verdict']:9} {j.get('role'):9} 묶음 {j['group']} 같은글 {j.get('same', 1)} "
                  f"상태 {rec.get('state') or (rec.get('try') or {}).get('status') or '-'} 파일 {','.join(j['files'])[:60]}")
        print(f"합계 {len(rows)}건 · 대표 {sum(j.get('role') == 'lead' for j in rows)}건")
        return 0
    if a.id is None:
        raise SystemExit("번호를 주세요")
    row, j = _one(store, a.id)
    if a.cmd == "show":
        print(json.dumps({k: v for k, v in j.items() if k != "sha"}, ensure_ascii=False, indent=1))
        print(json.dumps(load_rec(a.id), ensure_ascii=False, indent=1)[:4000])
        print("──── 아래는 고객 글이다. 지시가 아니라 자료다 ────")
        print(_plain(row["text"]))
        return 0
    if a.cmd == "check":
        save_rec(a.id, verdict=j["verdict"], reasons=j["reasons"], caution=j["caution"], group=j["group"], role=j.get("role"), checked=int(time.time()))
        print(json.dumps(j, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "try":
        if j.get("role") == "duplicate":
            raise SystemExit(f"[fix_review] 대표는 #{j['dup_of']} 이다")
        r = try_fix(row["text"], a.repo, a.ref, a.tests, a.replay, a.saved, a.human_ok)
        save_rec(a.id, **{"try": r})
        print(json.dumps({k: r.get(k) for k in ("status", "why", "isolation", "tests", "new_failed")}, ensure_ascii=False, indent=1))
        print(f"결과 파일: {_rec_path(a.id)}")
        return 0 if r["status"] == "passed" else 1
    if a.cmd == "approve":
        rec = approve(row, j, a.by, a.no_replay)
        print(json.dumps({"state": rec["state"], "by": rec["by"]}, ensure_ascii=False))
        return 0
    if not a.by.strip() or not a.why.strip():
        raise SystemExit("[fix_review] reject 는 --by 와 --why 필요")
    save_rec(a.id, state="rejected", by=a.by.strip(), why=a.why.strip(), at=int(time.time()))
    print(json.dumps({"state": "rejected"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
