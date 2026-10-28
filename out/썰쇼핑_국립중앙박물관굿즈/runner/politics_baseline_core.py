#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 정치 엔진 맞춤 스크립트 — 서버(volcano-mcp src/politics/runner_script.py BASELINE)가 내린 본문.
# 고쳐 두신 엔진 파일은 건드리지 않습니다. stdout 에는 JSON 한 덩어리만 나옵니다.
# ★같은 본문이 실행기 팩의 runner/politics_baseline_core.py 에도 들어 있다(바이트까지 같다 — 검사가 대조한다).
#   서버가 이 스크립트를 내리지 못한 옛 지시(10-04 엄격 설치기)를 실행기가 다시 돌릴 때도 같은 판정으로 맞춘다.
import json, os, re, subprocess, sys, time

# ── 엔진 맞춤 (baseline) ───────────────────────────────────────────────────
#   공식 팩의 새 판을 이 작업 폴더의 엔진에 맞춘다. ★**고쳐 두신 파일은 건드리지 않는다.**
#   파일마다 넷 중 하나다 — 지금 판과 같다 · 없다 · 공식 옛 판 그대로다 · 고쳐 썼다(커스텀).
#   없거나 공식 옛 판이면 새 판을 넣고, 커스텀은 그대로 둔다. 커스텀 가운데 새 실행 방식과 맞물리지
#   않는 것(아래 엔진 점검에 걸린 것)만 보존 폴더에 그대로 옮겨 두고 새 판을 넣은 뒤 그 사실을 말한다.
#   공식 옛 판인지는 서버가 준 지문 목록(`known`)으로 안다 — 목록에 없으면 사람이 고친 파일이다.

#: 이 스크립트가 발사 모듈에서 부르는 이름(아래 `_launcher(...)` 를 쓰는 자리) — 엔진 파일끼리의 참조와 같이 센다.
SCRIPT_USES = {"launcher": ("dispatch", "prepare", "current")}

def _physical_path(path):
    """Windows file I/O uses an extended path without changing stored identities."""
    path = os.fsdecode(path)
    if os.name != "nt":
        return path
    path = os.path.abspath(path)
    if path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path

# ── 엔진 점검 — 전부 «읽기» 다 ────────────────────────────────────────────
#   고쳐 둔 파일이 새 엔진과 맞물리는지를 **파일을 읽어서** 안다. 고쳐 둔 코드를 실행하지 않으므로
#   어느 파이썬으로 돌려도(모듈이 깔렸든 아니든) 답이 같고, 점검이 부작용을 내지 않는다.
#   세는 것은 하나다 — «다른 엔진 파일(과 이 스크립트)이 그 파일에서 쓰는데, 공식 새 판에는 있고
#   지금 파일에는 없는 것». 그러니 탓하는 파일은 언제나 «그것을 갖고 있어야 하는 쪽» 하나다.

def _module_names(tree):
    """모듈 맨 위에서 생기는 이름과 함수별 인자 이름({함수: 이름들 | None=**kwargs}).
    다 알 수 없는 모듈(별표 import · __getattr__)이면 (None, {}) — «다 있다» 로 본다."""
    import ast
    names, params, opaque = set(), {}, []

    def walk(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
                if node.name == "__getattr__":
                    opaque.append(node.name)
                a = node.args
                params[node.name] = (None if a.kwarg is not None else
                                     {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs})
            elif isinstance(node, ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
            elif isinstance(node, ast.Import):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if any(a.name == "*" for a in node.names):
                    opaque.append("*")
                names.update(a.asname or a.name for a in node.names)
            else:
                # if/try/with/for/while 안에서 맨 위 이름을 만드는 경우(조건부 정의)까지 따라간다.
                for part in ("body", "orelse", "finalbody"):
                    inner = getattr(node, part, None)
                    if isinstance(inner, list):
                        walk(inner)
                for handler in getattr(node, "handlers", None) or []:
                    walk(handler.body)
                bound = [getattr(node, "target", None)] + [item.optional_vars
                                                            for item in getattr(node, "items", None) or []]
                for target in bound:
                    if target is not None:
                        names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
    walk(tree.body)
    return (None, {}) if opaque else (names, params)

def _module_uses(tree, modules, package):
    """이 모듈이 형제 모듈에서 쓰는 것 — (이름 {형제: {이름}}, 키워드 인자 {형제: {(함수, 인자)}})."""
    import ast
    alias, direct, names, keywords = {}, {}, {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if (node.level == 1 and not base) or (node.level == 0 and base == package):
                for a in node.names:
                    if a.name in modules:
                        alias[a.asname or a.name] = a.name
                continue
            sibling = (base if node.level == 1 else
                       base[len(package) + 1:] if node.level == 0 and base.startswith(package + ".") else None)
            if sibling in modules:
                for a in node.names:
                    if a.name != "*":
                        names.setdefault(sibling, set()).add(a.name)
                        direct[a.asname or a.name] = (sibling, a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.asname and a.name.startswith(package + ".") and a.name[len(package) + 1:] in modules:
                    alias[a.asname] = a.name[len(package) + 1:]
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in alias:
            names.setdefault(alias[node.value.id], set()).add(node.attr)
        if isinstance(node, ast.Call):
            f = node.func
            owner = None
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in alias:
                owner = (alias[f.value.id], f.attr)
            elif isinstance(f, ast.Name):
                owner = direct.get(f.id)
            if owner:
                for kw in node.keywords:
                    if kw.arg:
                        keywords.setdefault(owner[0], set()).add((owner[1], kw.arg))
    return names, keywords

def _engine_stale(folder, official):
    """새 엔진과 맞물리지 않는 엔진 파일 — ({파일 이름: [없는 것…]}, [읽지 못한 파일…]).

    folder    지금 엔진의 파이썬 꾸러미 폴더(…/politics/politics)
    official  (파일 이름) → 공식 새 판의 본문(글자). 공식 팩에 없는 파일이면 None.
    없는 것   이름(함수·상수) · `함수(인자=)` 키워드 인자 · 발사 모듈이 run 에 넘기는 `--옵션`
    """
    import ast

    def parse(text):
        try:
            return ast.parse(text) if text is not None else None
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            return None
    try:
        listing = sorted(os.listdir(_physical_path(folder)))
    except OSError:
        return {}, []
    modules = [n[:-3] for n in listing if n.endswith(".py")]
    texts, trees = {}, {}
    for m in modules:
        try:
            with open(_physical_path(os.path.join(folder, m + ".py")), encoding="utf-8", errors="replace") as fh:
                texts[m] = fh.read()
        except OSError:
            texts[m] = None
        trees[m] = parse(texts[m])
    unread = [m + ".py" for m in modules if trees[m] is None]
    need_names = {m: set(v) for m, v in SCRIPT_USES.items()}
    need_keywords = {}
    for m in modules:
        if trees[m] is None:
            continue
        names, keywords = _module_uses(trees[m], set(modules), "politics")
        for target, wanted in names.items():
            if target != m:
                need_names.setdefault(target, set()).update(wanted)
        for target, wanted in keywords.items():
            if target != m:
                need_keywords.setdefault(target, set()).update(wanted)
    option = re.compile(r"[\x22\x27](--[a-z][a-z0-9-]*)[\x22\x27]")
    stale = {}
    for m in modules:
        if trees[m] is None:
            continue
        text = official(m + ".py")
        if text is None or text == texts[m]:
            continue                      # 공식 팩에 없는 파일(직접 만든 파일)이거나 공식 새 판 그대로다
        reference = parse(text)
        if reference is None:
            continue
        have, have_params = _module_names(trees[m])
        want, want_params = _module_names(reference)
        why = []
        if have is not None and want is not None:
            why += sorted((need_names.get(m, set()) & want) - have)
            for func, arg in sorted(need_keywords.get(m, ())):
                ours, theirs = have_params.get(func), want_params.get(func)
                if ours is not None and theirs is not None and arg in theirs and arg not in ours:
                    why.append("%s(%s=)" % (func, arg))
        if m == "run" and texts.get("launcher") is not None:
            passed = set(option.findall(texts["launcher"]))
            why += sorted((passed & set(option.findall(text))) - set(option.findall(texts[m])))
        if why:
            stale[m + ".py"] = why
    return stale, unread

def _sha256_path(path):
    import hashlib
    h = hashlib.sha256()
    with open(_physical_path(path), "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def _engine_path(wd, rel):
    """팩 안 이름(`politics/politics/run.py`) → 이 컴퓨터의 경로. 이름이 폴더 밖을 가리키면 멈춘다."""
    parts = str(rel).split("/")
    if not parts or any(p in ("", ".", "..") or ":" in p or "\\" in p for p in parts):
        raise ValueError("잘못된 엔진 파일 이름: %r" % (rel,))
    return os.path.join(wd, *parts)

def _write_whole(target, data):
    """같은 폴더의 임시 파일에 다 쓴 뒤 이름만 바꾼다 — 반쯤 쓰인 파일이 남지 않는다."""
    import tempfile
    folder = _physical_path(os.path.dirname(target))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".baseline-", dir=folder)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if os.name == "nt":
            # ★윈도우는 «읽기 전용» 속성이 붙은 파일을 os.replace 로 바꾸지 못한다(매번 WinError 5).
            #   여기 오는 파일은 새 판을 넣기로 정한 것(없음·공식 옛 판·보존 폴더로 옮겨 둔 커스텀)뿐이다.
            try:
                import stat
                mode = os.stat(_physical_path(target)).st_mode
                if not mode & stat.S_IWRITE:
                    os.chmod(_physical_path(target), mode | stat.S_IWRITE)
            except OSError:
                pass                          # 대상이 아직 없다 — 바꿀 속성도 없다
        for attempt in range(100):
            try:
                os.replace(tmp, _physical_path(target))
                break
            except PermissionError:
                # 윈도우는 대상 파일을 다른 프로그램(백신 등)이 잠깐 쥐고 있으면 거부한다 — 잠깐 뒤 다시.
                if os.name != "nt" or attempt == 99:
                    raise
                time.sleep(0.02)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def _is_link(path):
    """연결(심볼릭 링크·윈도우 정션)인가. 정션은 islink 가 못 본다 — 파일 속성의 재분석 지점 표시로 본다."""
    try:
        info = os.lstat(_physical_path(path))
    except OSError:
        return False
    import stat
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)

#: 연결 폴더를 사본으로 바꿀 때 사본 맨 위에 남기는 기록 — 엔진(politics/resume.py `RELOCATED`)이 같은 이름을 읽는다.
RELOCATED = "_volcano_relocated.json"

def _location(path):
    """엔진의 identity 와 같은 꼴(politics/resume.py `location`) — 대소문자를 정규화한 실제 경로."""
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))

def _relocation_record(path, copied):
    """연결을 사본으로 바꾸기 **직전**(사본 안에) «옛 뿌리 → 이 자리» 를 남긴다 (2026-10-06 · 검토 7회차 major r9).
    그 연결로 띄운 제작의 기록(발사 영수증·재개 입력·검증 근거)은 연결 **대상**의 실제 경로로 적혀 있다. 엔진은 이 기록이
    **이 자리의 것일 때만**(to == 지금 뿌리) 그 경로를 이 사본 아래 같은 자리로 읽는다 — 그래야 떼기 뒤에도 이어 만든다
    (예전에는 영수증이 전부 «작업 폴더를 옮겼다»(receipt_moved)로 막혀 유료 새 제작만 남았다). 기록 파일 바이트는 고치지 않는다.
    사본에 이미 기록이 있으면(연결 대상도 예전에 이렇게 만든 사본) 그 옛 뿌리도 이 자리로 이어 준다.
    ★바꾸기 전에 사본 안에 쓴다 — 바꾸기와 기록이 함께 되거나(이름 바꾸기 한 번) 함께 안 된다(바꾸다 실패하면 임시 폴더째 지운다)."""
    src = _location(path)
    dst = os.path.normcase(os.path.join(os.path.realpath(os.path.dirname(os.path.abspath(path))), os.path.basename(path)))
    moves = []
    try:
        with open(os.path.join(copied, RELOCATED), encoding="utf-8") as fh:
            old = json.load(fh)
    except (OSError, ValueError):
        old = None
    for move in (old.get("moves") if isinstance(old, dict) and isinstance(old.get("moves"), list) else []):
        if isinstance(move, dict) and isinstance(move.get("from"), str) and isinstance(move.get("to"), str):
            moves.append(move)
            if os.path.normcase(move["to"]) == src and os.path.normcase(move["from"]) != dst:
                moves.append({"from": move["from"], "to": dst, "by": "politics_baseline", "via": src})
    move = {"from": src, "to": dst, "by": "politics_baseline", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    moves.append(move)
    with open(os.path.join(copied, RELOCATED), "w", encoding="utf-8") as fh:
        json.dump({"schema": 1, "moves": moves[-32:]}, fh, ensure_ascii=False, indent=1)
    return move

def _detach(path):
    """연결 폴더를 이 작업 폴더만의 복사본으로 바꾼다 — 연결 대상(공용 원본)은 **읽기만** 한다.
    실행기의 자산 풀기(`volcano_drive._pack_detach`)와 같은 처방: 복사 → 연결을 옆으로 → 복사본을 그 자리로 → 연결만 지운다.
    중간에 실패하면 원래 연결을 되돌려 놓는다. 사본 맨 위에 옮긴 기록(`RELOCATED`)을 남기고 그 한 쌍을 돌려준다."""
    import shutil, tempfile
    temp = tempfile.mkdtemp(prefix=_COW, dir=_physical_path(os.path.dirname(path)))
    copied, aside = os.path.join(temp, "copy"), os.path.join(temp, "link")
    try:
        # 어느 이름의 연결인지 먼저 적는다 — 두 번의 이름 바꾸기 사이에서 끊기면 다음 실행이 이것으로 되돌린다(`_cow_recover`).
        with open(os.path.join(temp, "for"), "w", encoding="utf-8") as fh:
            fh.write(os.path.basename(path))
        # 잠금 파일은 옮기지 않는다 — 내용 없는 표식이고(쓸 때 새로 만든다), 윈도우는 남이 쥔 잠금 파일을 읽지 못한다.
        shutil.copytree(_physical_path(path), copied, symlinks=True, ignore=shutil.ignore_patterns("*.lock"))
        move = _relocation_record(path, copied)
        os.replace(_physical_path(path), aside)
        try:
            os.replace(copied, _physical_path(path))
        except OSError:
            os.replace(aside, _physical_path(path))
            raise
        # 정션·폴더 연결은 rmdir 로 «연결만» 지운다(대상 안은 건드리지 않는다). 심볼릭 링크는 unlink.
        try:
            os.rmdir(aside)
        except OSError:
            os.unlink(aside)
    finally:
        if not os.path.lexists(aside):
            shutil.rmtree(temp, ignore_errors=True)
    return move

_COW = ".volcano-cow-"

# 엔진 파일까지 가는 폴더들(얕은 것부터) — 'politics' · 'politics/politics' …
def _engine_folders(files):
    return sorted({"/".join(rel.split("/")[:depth]) for rel in files
                   for depth in range(1, rel.count("/") + 1)}, key=lambda f: (f.count("/"), f))

# 지난 실행이 연결 엔진을 복사본으로 바꾸다 끊기고 남긴 임시 폴더들 — (임시 폴더, 그 폴더 옆에 있어야 할 엔진 폴더 이름들).
#   우리 `_detach` 의 것(for·link)도, 실행기 자산 풀기(`volcano_drive._pack_detach` · copy·original)의 것도 같은 이름 꼴이다.
def _cow_leftovers(wd, files):
    found = []
    siblings = {}
    expect = {}
    for prefix in _engine_folders(files):
        path = _engine_path(wd, prefix)
        siblings.setdefault(os.path.dirname(path), set()).add(os.path.basename(path))
        # 그 엔진 폴더 안에 있어야 할 파일들(그 폴더 기준 상대 경로) — 흔적이 정말 이 엔진 폴더의 것인지 볼 때 쓴다
        expect[path] = [rel[len(prefix) + 1:] for rel in files if rel.startswith(prefix + "/")]
    for parent in sorted(siblings):
        try:
            names = os.listdir(_physical_path(parent))
        except OSError:
            continue
        for name in sorted(names):
            temp = os.path.join(parent, name)
            if name.startswith(_COW) and os.path.isdir(_physical_path(temp)) and not _is_link(temp):
                found.append((temp, {name: expect.get(os.path.join(parent, name)) or []
                                     for name in sorted(siblings[parent])}))
    return found

# 끊긴 `_detach` 하나를 마무리한다 — 원래 연결이 옆으로 비켜 있고 그 자리가 비었으면 **연결을 제자리로** 되돌리고
#   (고쳐 두신 파일·작업물이 든 원래 엔진이 다시 보인다), 복사본이 이미 들어가 있으면 비켜 둔 연결만 지운다. 공용 원본은 읽지도
#   않는다. 되돌렸으면 'restored' · 연결만 지웠으면 'cleaned' · 남은 복사 조각만 지웠으면 'removed'.
def _cow_recover(temp, siblings=()):
    import shutil
    aside = os.path.join(temp, "link")
    if not os.path.lexists(_physical_path(os.path.join(temp, "for"))) and not os.path.lexists(_physical_path(aside)):
        return _runner_cow_recover(temp, siblings)
    what = "removed"
    if os.path.lexists(_physical_path(aside)):
        try:
            with open(_physical_path(os.path.join(temp, "for")), encoding="utf-8") as fh:
                name = fh.read().strip()
        except OSError:
            name = ""
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise RuntimeError("끊긴 엔진 복사 흔적(%s)을 해석하지 못했습니다 — 그 안 link 가 원래 연결입니다"
                               % os.path.basename(temp))
        target = os.path.join(os.path.dirname(temp), name)
        if not os.path.lexists(_physical_path(target)):
            os.replace(_physical_path(aside), _physical_path(target))
            what = "restored"
        else:
            try:
                os.rmdir(_physical_path(aside))
            except OSError:
                os.unlink(_physical_path(aside))
            what = "cleaned"
    # 연결이 아직 안에 있으면 지우지 않는다(위에서 옮기거나 지웠다) — 지우는 것은 복사 조각과 표지뿐이다.
    if not os.path.lexists(_physical_path(aside)):
        shutil.rmtree(_physical_path(temp), ignore_errors=True)
    return what

# 실행기 자산 풀기(`volcano_drive._pack_detach`)가 끊기고 남긴 흔적 — `copy`(복사 조각)·`original`(옆으로 비킨 원래 연결).
#   ★예전에는 우리 표지(for·link)가 없다고 «남은 복사 조각» 으로 보고 통째로 지웠다 — `original` 이 학생이 고친 엔진·작업물로
#   가는 **유일한 연결**인데 그것을 지우고 공식 판 30개를 새로 깔았다(1차 검토 3회차 minor · 맥·win-01 재현). 실행기가 작업
#   폴더 연결을 떼다 멈춘 같은 부류(누락 점검 M8)는 실행기 쪽이 «알리기만» 하고 고친다(B 묶음) — 여기서도 지우지 않는다:
#     원래 연결이 비켜 있고 그 자리(옆에 있어야 할 엔진 폴더 가운데 **하나만** 없음)가 비었다 → 연결을 제자리로 되돌린다.
#     자리가 차 있다(복사본이 들어갔다) → 손대지 않고 알린다(그 뒤 진행이 복사본에 쌓였을 수 있어 사람이 고른다).
#     없는 자리가 둘 이상이라 어느 것인지 모른다 → 맞추지 않고 멈춘다(빈 자리에 공식 판을 깔면 고친 엔진을 잃는다).
#   남은 것이 복사 조각뿐(original 없음)이면 원래 연결은 그대로 제자리다 — 조각만 지운다.
def _runner_cow_recover(temp, siblings):
    import shutil
    original = os.path.join(temp, "original")
    if not os.path.lexists(_physical_path(original)):
        shutil.rmtree(_physical_path(temp), ignore_errors=True)
        return "removed"
    parent = os.path.dirname(temp)
    missing = [name for name in siblings if not os.path.lexists(_physical_path(os.path.join(parent, name)))]
    if len(missing) == 1:
        # ★그 연결이 정말 이 엔진 폴더의 것인지 먼저 본다(2026-10-06 검토 5회차 minor · 1회차 F4) — 새 작업 폴더는 엔진 자리가
        #   비어 있는 것이 정상이라(맞춤이 깐다), 실행기가 **다른 폴더**(예: runner/)를 떼다 남긴 흔적이 그 빈 자리로 옮겨져
        #   엔진 자리가 공용 실행기 폴더로 가는 연결이 됐다. 그 폴더 안에 이 엔진 파일이 절반 넘게 있을 때만 엔진의 흔적으로 본다
        #   (우리 팩에서 나온 엔진 폴더는 전부 · 고친 엔진도 거의 전부 갖고 있고, 남의 폴더는 거의 없다 — 문턱은 이 판단의 값이다).
        expected = (siblings.get(missing[0]) if isinstance(siblings, dict) else None) or []
        present = sum(1 for sub in expected if os.path.isfile(_physical_path(os.path.join(original, *sub.split("/")))))
        if not expected or present * 2 <= len(expected):
            return "foreign"
        os.replace(_physical_path(original), _physical_path(os.path.join(parent, missing[0])))
        shutil.rmtree(_physical_path(temp), ignore_errors=True)
        return "restored"
    if missing:
        raise RuntimeError("실행기가 엔진 연결을 떼다 멈춘 흔적(%s)이 있는데 어느 폴더의 연결인지 하나로 정할 수 없습니다 — 그 안 "
                           "original 이 원래 연결입니다. 고쳐 두신 엔진을 공식 판으로 덮지 않으려고 맞추지 않았습니다. 원래 이름(%s 중 하나)으로 "
                           "되돌린 뒤 같은 단계를 다시 실행하세요" % (os.path.basename(temp), ", ".join(missing)))
    return "kept"

def _hold_lock(path):
    """기다리지 않는 배타 잠금 — 잡았으면 파일 객체, 남이 쥐고 있으면 None. (엔진·실행기와 같은 잠금 파일·같은 방식)"""
    os.makedirs(_physical_path(os.path.dirname(path)), exist_ok=True)
    f = open(_physical_path(path), "a+b")
    try:
        f.seek(0, 2)
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None

def _baseline_state(spec):
    try:
        with open(_physical_path(spec["state"]), encoding="utf-8") as fh:
            value = json.load(fh)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None

def _baseline_save(spec, **value):
    if "relocated" not in value:
        # 옮긴 기록(연결을 사본으로 바꾼 자리)은 어느 저장에서도 잃지 않는다 — 실패·대기 저장도 그대로 이어 적는다.
        prior = (_baseline_state(spec) or {}).get("relocated")
        if isinstance(prior, list) and prior:
            value["relocated"] = prior
    value = dict({"version": 1, "target": spec["target"]}, **value)
    _write_whole(spec["state"], json.dumps(value, ensure_ascii=False, indent=1).encode("utf-8"))
    return value

def _process_facts(pid):
    """그 번호의 프로세스 — (시작 시각(유닉스 초), 프로그램 이름) · 없으면 None · 알 수 없으면 ().

    윈도우는 GetProcessTimes(커널32) · 맥/리눅스는 `ps -o lstart=,comm=`(C 로케일 — 요일·달 이름이 영어로 고정).
    ★윈도우에서 os.kill(pid, 0) 은 신호 0 이라도 프로세스를 **죽인다** — 쓰지 않는다(아래 `_alive` 와 같은 이유)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # 부르는 함수마다 인자 모양을 적는다(HANDLE 은 포인터 크기 — 적지 않으면 C int 로 넘어간다 · 2026-10-06).
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetExitCodeProcess.restype = wintypes.BOOL
        k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.GetProcessTimes.restype = wintypes.BOOL
        k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                   ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None if ctypes.get_last_error() == 87 else ()   # 87 = 그런 번호 없음 · 그 밖(권한)은 «모름»
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return ()
            if code.value != 259:                            # STILL_ACTIVE 가 아니면 끝난 프로세스다
                return None
            times = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return ()
            ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            size = wintypes.DWORD(1024)
            name = ctypes.create_unicode_buffer(1024)
            image = (name.value if k32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)) else "")
            return (ticks / 1e7 - 11644473600.0, image)
        finally:
            k32.CloseHandle(handle)
    try:
        done = subprocess.run(["ps", "-o", "lstart=,comm=", "-p", str(pid)], capture_output=True, text=True,
                              timeout=30, env=dict(os.environ, LC_ALL="C", LANG="C"))
    except (OSError, subprocess.SubprocessError):
        return ()
    line = done.stdout.strip()
    if done.returncode != 0 or not line:
        return None
    parts = line.split(None, 5)
    try:
        started = time.mktime(time.strptime(" ".join(parts[:5]), "%a %b %d %H:%M:%S %Y"))
    except (ValueError, OverflowError):
        return ()
    return (started, parts[5] if len(parts) > 5 else "")

def _production_running(root):
    """옛 실행 방식(pid 파일)으로 띄운 제작이 **지금 돌고 있다는 확실한 증거**가 있을 때만 True.
    새 실행 방식은 엔진이 잠금 파일을 쥐고 있어 그쪽에서 잡힌다.

    ★번호만 보면 속는다 — 옛 제작이 죽은 뒤 운영체제가 그 번호를 **다른 프로그램**에 다시 준다.
      옛 실행 방식은 파이프라인(파이썬)을 띄운 **뒤에** pid 파일을 썼다. 그러니 그 번호의 프로세스가
      pid 파일보다 늦게 시작했거나 파이썬이 아니면 우리 제작이 아니다. 여유 2초는 잴 수 있는 가장 거친
      시각 단위다(`ps` 시작 시각 1초 단위 · FAT 계열 파일 시각 2초 단위)."""
    work = os.path.join(root, "work")
    pid_file = os.path.join(work, "_volcano_run.pid")
    try:
        with open(_physical_path(pid_file), encoding="utf-8") as fh:
            pid = int(fh.read().splitlines()[0])
        written = os.stat(_physical_path(pid_file)).st_mtime
    except (OSError, ValueError, IndexError):
        return False
    try:
        with open(_physical_path(os.path.join(work, "_volcano_result.json")), encoding="utf-8") as fh:
            status = str((json.load(fh) or {}).get("status") or "")
    except (OSError, ValueError, AttributeError):
        status = ""
    if status in ("verified", "failed"):
        return False          # 끝난 제작이다 — 그 번호를 다른 프로그램이 다시 쓰고 있어도 속지 않는다
    facts = _process_facts(pid)
    if not facts:
        return False          # 없거나(None) 알 수 없다(()) — 확실한 증거가 아니다
    started, image = facts
    if started > written + 2.0:
        return False          # pid 파일을 쓴 뒤에 시작한 프로세스 — 번호만 같은 남의 프로그램이다
    return "python" in os.path.basename(str(image)).lower()

def baseline(cfg):
    """엔진을 새 판에 맞춘다. 끝났으면 ok=True 와 «그대로 둔 것·옮긴 것» 을, 못 끝냈으면 ok=False 와 사유를 말한다."""
    spec = cfg.get("baseline_sync")
    if not isinstance(spec, dict):
        return {"ok": False, "why": "맞춤 설정이 없습니다"}
    try:
        return _baseline_sync(cfg, spec)
    except Exception as exc:
        # 끝내지 못했다는 사실을 남긴다 — 관문이 반쯤 맞춘 엔진으로 제작을 시작하지 않게.
        why = _baseline_why(exc, cfg.get("workdir"))
        previous = _baseline_state(spec) or {}
        try:
            _baseline_save(spec, complete=False, why=why, kept=previous.get("kept") or [],
                           replaced=previous.get("replaced") or [])
        except OSError as failed:
            sys.stderr.write("맞춤 상태를 남기지 못했습니다: %s\n" % _baseline_why(failed, cfg.get("workdir")))
        return {"ok": False, "why": why, "kept": previous.get("kept") or [], "replaced": [], "warnings": []}

def _baseline_why(exc, workdir):
    """사람이 읽을 사유 — 작업 폴더·홈 폴더 경로는 빼고 말한다(이 사유는 서버로도 간다)."""
    import shutil
    if isinstance(exc, shutil.Error):
        rows = exc.args[0] if exc.args and isinstance(exc.args[0], list) else []
        names = sorted({os.path.basename(str(row[0])) for row in rows if isinstance(row, tuple) and row})[:5]
        text = ("연결된(공용) 엔진 폴더를 이 작업 폴더로 복사하지 못했습니다" + (" (%s)" % ", ".join(names) if names else "")
                + " — 그 폴더를 다른 프로그램이 쓰고 있으면 끝난 뒤 같은 단계를 다시 실행하면 이어서 맞춥니다. 공용 원본은 그대로입니다")
        return text[:600]
    if isinstance(exc, PermissionError):
        name = os.path.basename(str(getattr(exc, "filename2", None) or getattr(exc, "filename", None) or ""))
        text = ("엔진 파일을 바꿀 권한이 없습니다" + (" (%s)" % name if name else "")
                + " — 다른 프로그램(편집기·백신·동기화 도구)이 그 파일을 쥐고 있거나 폴더가 읽기 전용입니다. "
                  "그 프로그램을 닫거나 폴더의 쓰기 권한을 돌려놓은 뒤 같은 단계를 다시 실행하면 이어서 맞춥니다")
    else:
        text = "%s: %s" % (type(exc).__name__, exc)
    for path, label in ((workdir, "<작업 폴더>"), (os.path.expanduser("~"), "~")):
        if isinstance(path, str) and len(path) > 3:
            for form in sorted({path, os.path.abspath(path), _physical_path(os.path.abspath(path))}, key=len, reverse=True):
                # 예외 글에는 경로가 repr 꼴(역슬래시 두 겹)로도 들어온다
                for shown in (form.replace("\\", "\\\\"), form):
                    text = text.replace(shown, label)
    return text[:600]

def _baseline_sync(cfg, spec):
    wd, root = os.path.abspath(cfg["workdir"]), os.path.abspath(cfg["root"])
    files, known = spec["files"], set(spec.get("known") or ())
    recovered = []
    leftovers = _cow_leftovers(wd, files)
    if leftovers:
        # 지난 실행이 연결 엔진을 복사본으로 바꾸다 끊겼다 — 엔진을 들여다보기 **전에** 먼저 제자리로(맞춤 잠금 안에서).
        lock = _hold_lock(os.path.join(wd, ".politics-baseline-upgrade.lock"))
        if lock is None:
            previous = _baseline_state(spec) or {}
            return _baseline_wait(spec, previous, previous.get("kept") or [], previous.get("replaced") or [], [],
                                  "다른 실행이 이 엔진을 맞추는 중입니다")
        try:
            recovered = [_cow_recover(temp, siblings) for temp, siblings in leftovers]
        finally:
            lock.close()
    rows = {}
    for rel, want in files.items():
        path = _engine_path(wd, rel)
        if os.path.isdir(_physical_path(path)):
            raise RuntimeError("엔진 파일 자리에 폴더가 있습니다: %s" % rel)
        if not os.path.isfile(_physical_path(path)):
            rows[rel] = ("missing", None)
            continue
        have = _sha256_path(path)
        # 공식 옛 판 지문은 앞부분만 온다(응답 크기) — 같은 길이로 잘라 견준다.
        rows[rel] = ("current" if have == want else
                     "official" if any(have.startswith(k) for k in known if len(k) >= 16) else "custom", have)
    todo = sorted(rel for rel, row in rows.items() if row[0] in ("missing", "official"))
    custom = sorted(rel for rel, row in rows.items() if row[0] == "custom")
    package = os.path.basename(root) + "/politics/"
    previous = _baseline_state(spec) or {}
    history = [row for row in (previous.get("replaced") or [])
               if isinstance(row, dict) and row.get("path") in files and isinstance(row.get("backup"), str)]
    installed, warnings, detached = [], [], []
    # 옮긴 기록(연결을 사본으로 바꾼 자리의 «옛 뿌리 → 이 자리») — 맞춤 상태에도 남긴다(사람·서버가 보는 기준 기록 · 엔진은 사본 맨 위의
    #   `RELOCATED` 를 읽는다). 지난 맞춤의 것도 이어 적는다.
    relocated = [row for row in (previous.get("relocated") or [])
                 if isinstance(row, dict) and isinstance(row.get("from"), str) and isinstance(row.get("to"), str)]
    if "restored" in recovered:
        warnings.append("지난번에 끊긴 연결 엔진 복사를 되돌렸습니다(공용 원본은 그대로)")
    if "foreign" in recovered:
        warnings.append("실행기가 엔진이 아닌 다른 폴더의 연결을 떼다 멈춘 흔적(.volcano-cow-*/original)이 있어 손대지 않았습니다 — "
                        "엔진은 그와 상관없이 맞춥니다. original 은 원래 가리키던 폴더로 가는 연결입니다(실행기 쪽 안내를 따라 정리하세요)")
    if "kept" in recovered:
        warnings.append("실행기가 엔진 연결을 떼다 멈춘 흔적(.volcano-cow-*/original)이 남아 있습니다 — 엔진 자리에는 그때 만든 복사본이 "
                        "들어가 있어 그대로 두었습니다. original 은 원래 가리키던 폴더로 가는 연결입니다(어느 쪽을 쓸지 정한 뒤 정리하세요)")

    def folders():
        return _engine_folders(files)

    def linked():
        return any(_is_link(_engine_path(wd, prefix)) for prefix in folders())

    def own():
        """엔진 파일까지 가는 폴더 가운데 연결(공용 폴더)이 있으면 이 작업 폴더만의 복사본으로 바꾼다 — 남의 작업 폴더가
        같이 쓰는 공용 엔진에 새 판을 써 넣지 않는다(그 폴더는 아무 안내도 못 받는다).
        ★엔진 안의 잠금(politics/work/*.lock)을 잡기 **전에** 한다 — 잡은 뒤에 바꾸면 우리가 쥔 잠금은 공용 쪽에 남고
          복사본에는 아무 잠금도 없게 되며, 윈도우는 쥔 잠금 파일을 복사조차 못 한다(win-01 WinError 33 · 10-05)."""
        for prefix in folders():
            if _is_link(_engine_path(wd, prefix)):
                move = _detach(_engine_path(wd, prefix))
                detached.append(prefix)
                relocated.append({"prefix": prefix, "from": move["from"], "to": move["to"], "at": move["at"]})

    def official(rel):
        """보관 폴더의 공식 새 판 한 파일 — 지문을 확인한 바이트."""
        source = _engine_path(spec["staged"], rel)
        if not os.path.isfile(_physical_path(source)):
            raise RuntimeError("보관해 둔 공식 원본이 없습니다(%s) — 같은 단계를 다시 실행하면 다시 받습니다" % rel)
        with open(_physical_path(source), "rb") as fh:
            data = fh.read()
        import hashlib
        if hashlib.sha256(data).hexdigest() != files[rel]:
            raise RuntimeError("보관해 둔 공식 원본이 달라졌습니다(%s) — 같은 단계를 다시 실행하면 다시 받습니다" % rel)
        return data

    def put(rel):
        data = official(rel)
        target = _engine_path(wd, rel)
        _write_whole(target, data)
        if target.endswith(".py"):
            # 고정된 팩 시각 때문에 옛 .pyc 가 유효해 보일 수 있다 — 바꾼 파일의 것만 지운다.
            cache = os.path.join(os.path.dirname(target), "__pycache__")
            stem = os.path.basename(target)[:-3] + "."
            if os.path.isdir(_physical_path(cache)):
                for name in os.listdir(_physical_path(cache)):
                    if name.startswith(stem) and name.endswith(".pyc"):
                        os.unlink(_physical_path(os.path.join(cache, name)))
        installed.append(rel)

    def stale():
        """고쳐 둔 파일 가운데 새 엔진과 맞물리지 않는 것 — {팩 이름: [없는 것…]}."""
        if not any(rel.startswith(package) and rel.endswith(".py") for rel in custom):
            return {}
        found, unread = _engine_stale(
            os.path.join(root, "politics"),
            lambda name: official(package + name).decode("utf-8", "replace") if package + name in files else None)
        for name in unread:
            note = "읽지 못해 점검하지 않은 엔진 파일: %s" % name
            if package + name in custom and note not in warnings:
                warnings.append(note)
        return {package + name: why for name, why in found.items() if package + name in custom}

    pending = {} if todo else stale()
    if todo or pending:
        held = []
        inner = ((os.path.join(root, "work", "_volcano_launch.lock"), "제작 발사를 확인하는 중입니다"),
                 (os.path.join(root, "work", "_volcano_pipeline.lock"), "이 작업 폴더에서 제작이 돌고 있습니다"))

        def take(locks):
            """잠금들을 차례로 잡는다 — 못 잡은 것의 사유(잡은 것은 `held` 에 남는다) · 다 잡았으면 None."""
            for path, busy in locks:
                lock = _hold_lock(path)
                if lock is None:
                    return busy
                held.append(lock)
            return None
        try:
            busy = take(((os.path.join(wd, ".politics-baseline-upgrade.lock"), "다른 실행이 이 엔진을 맞추는 중입니다"),))
            if busy is None:
                # 그 엔진에서 제작이 돌고 있으면 아무것도 바꾸지 않고 기다린다(도는 제작이 쓰는 폴더를 바꿔치기하지 않는다).
                busy = take(inner) or ("이 작업 폴더에서 제작이 돌고 있습니다" if _production_running(root) else None)
            if busy is None and linked():
                # 연결을 바꾸기 **전에** «끝나지 않았다» 를 남긴다 — 바꾸다 끊기면 관문이 반쯤 된 엔진으로 제작을 시작하지 않게.
                _baseline_save(spec, complete=False, why="엔진 맞춤이 중간에 끊겼습니다", kept=custom, replaced=history)
                # 엔진 안 잠금은 연결 폴더를 복사본으로 바꾼 **뒤의** 폴더에서 쥐어야 한다(→ own) — 놓고, 바꾸고, 다시 잡는다.
                while len(held) > 1:
                    held.pop().close()
                own()
                if relocated:
                    _baseline_save(spec, complete=False, why="엔진 맞춤이 중간에 끊겼습니다", kept=custom, replaced=history,
                                   relocated=relocated)
                busy = take(inner)
            if busy is not None:
                return _baseline_wait(spec, previous, custom, history, held, busy)
            _baseline_save(spec, complete=False, why="엔진 맞춤이 중간에 끊겼습니다", kept=custom, replaced=history)
            for rel in todo:
                put(rel)
            # 공식 파일을 다 맞춘 뒤에 본다 — 그래야 «새 엔진이 그 파일에서 쓰는 것» 이 정해진다.
            for _ in range(len(custom) + 1):
                found = stale()
                if not found:
                    break
                for rel in sorted(found):
                    digest = rows[rel][1]
                    backup = "/".join((str(spec.get("preserve") or ".politics-preserved"), digest[:12], rel))
                    kept_at = _engine_path(wd, backup)
                    if not (os.path.isfile(_physical_path(kept_at)) and _sha256_path(kept_at) == digest):
                        with open(_physical_path(_engine_path(wd, rel)), "rb") as fh:
                            _write_whole(kept_at, fh.read())
                        if _sha256_path(kept_at) != digest:
                            raise RuntimeError("고쳐 두신 파일을 옮기는 중에 내용이 바뀌었습니다: %s" % rel)
                    history = ([row for row in history if row.get("backup") != backup]
                               + [{"path": rel, "backup": backup, "needs": found[rel][:8]}])
                    # 옮긴 자리부터 남긴다 — 여기서 끊겨도 원래 파일이 어디 있는지 잃지 않는다.
                    _baseline_save(spec, complete=False, why="엔진 맞춤이 중간에 끊겼습니다", kept=custom, replaced=history)
                    put(rel)
                    custom.remove(rel)
                    rows[rel] = ("current", files[rel])
        finally:
            for lock in reversed(held):
                lock.close()
    # 지금도 공식 판인 채로 있는 것만 다시 알린다 — 같은 수정을 새 파일에 넣으셨으면(=커스텀) 더 말하지 않는다.
    replaced = [row for row in history if row["path"] not in custom]
    state = dict(complete=True, why=None, kept=custom, replaced=history, **({"relocated": relocated} if relocated else {}),
                 at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    # ★견주는 것은 **지금 디스크의 상태**다 — 함수 머리에서 읽은 `previous` 가 아니다(2026-10-22 신고 · 윈도우 정치 «엔진 맞춤이
    #   중간에 끊겼습니다»). 맞출 파일이 있으면 위에서 complete=False 를 먼저 써 두는데, 끝 상태가 머리의 상태와 같으면(같은 커스텀·
    #   같은 판으로 다시 맞춤) 옛 비교는 저장을 건너뛰어 그 «끊김» 표지가 남았고, 관문이 다음 발사를 막았다.
    now = _baseline_state(spec) or {}
    if any(now.get(k) != v for k, v in state.items() if k != "at") or now.get("target") != spec["target"]:
        _baseline_save(spec, **state)
    return {"ok": True, "target": spec["target"], "installed": installed, "kept": custom,
            "unpatched": sorted(set(custom) & set(spec.get("updated") or ())),
            "replaced": replaced, "warnings": warnings, "detached": detached,
            # 떼며 옮긴 기록을 남긴 자리 — 이 판의 떼기는 언제나 남긴다(서버 안내가 «기록도 이어진다» 를 말해도 되는지 아는 표지).
            "relocated": list(detached)}

def _baseline_wait(spec, previous, custom, history, held, busy):
    """지금은 엔진을 바꿀 수 없다 — 아무것도 바꾸지 않고, 끝나지 않았다는 사실만 남긴다."""
    why = busy + " — 끝난 뒤 같은 단계를 다시 실행하면 엔진을 맞춥니다"
    if held:
        # 첫 잠금(맞춤 자체)을 잡았을 때만 상태를 쓴다 — 못 잡았으면 다른 실행이 쓰는 중이다.
        _baseline_save(spec, complete=False, why=why, kept=custom, replaced=history)
    return {"ok": False, "why": why, "kept": custom, "replaced": [], "warnings": []}

def main():
    if len(sys.argv) < 2:
        result = {"ok": False, "why": "설정 파일 경로가 없습니다"}
    else:
        try:
            with open(_physical_path(sys.argv[1]), encoding="utf-8") as fh:
                result = baseline(json.load(fh))
        except (OSError, ValueError) as exc:
            result = {"ok": False, "why": "설정 파일을 못 읽었습니다: %s" % type(exc).__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()

if __name__ == "__main__":
    main()
