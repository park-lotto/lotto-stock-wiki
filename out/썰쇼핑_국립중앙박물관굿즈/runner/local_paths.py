"""Resolve existing local inputs without renaming or guessing different media."""
import os
from pathlib import Path
import re
import unicodedata

#: 윈도우 파일 이름에 쓸 수 없는 글자 '?' — 경로에 있으면 실행기 앞단(호스트 콘솔·파일 인코딩)이 비ASCII 글자를 '?' 로
#: 바꿔 넘긴 것이다(#179 · 실물 'E:\\??????\\??\\???\\_input' — 실제 폴더 'E:\\볼케이노작업\\작업\\린박스' 와 글자 수가 같다).
_LOST = '?'
_ENCODING_HINT = (' — 경로 글자가 콘솔 인코딩에서 깨졌습니다(한글 등이 «?» 로 바뀜). 실행기에 경로를 UTF-8 로 넘기거나'
                  '(예: PowerShell 에서 [Console]::OutputEncoding=[Text.Encoding]::UTF8, 또는 python -X utf8) 원래 경로를 다시 지정하세요.')


def _windows():
    return os.name == 'nt'


def _msys_drive(value):
    """Git Bash·MSYS 꼴 '/c/Users/…' → 'C:/Users/…' (윈도우 실행기에서 뜻이 하나뿐인 경우만)."""
    match = re.fullmatch(r'/([A-Za-z])(/.*)?', str(value))
    if not match:
        return None
    return match.group(1).upper() + ':' + (match.group(2) or '/')


def _lost_pattern(part):
    """'?' 하나 = 비ASCII 글자 하나로 보는 이름 틀 — '?' 가 없으면 None."""
    part = unicodedata.normalize('NFC', part)
    if _LOST not in part:
        return None
    return re.compile(''.join('[^\\x00-\\x7f]' if c == _LOST else re.escape(c) for c in part))


def resolve_existing_input(value):
    """Return an existing path; repair only unique NFC/NFD spelling differences.

    Literal paths take priority, including on normalization-insensitive macOS.
    When a path is absent, inspect each existing parent directory rather than
    normalizing the filename and assuming the filesystem stores that spelling.
    No case folding, fuzzy matching, network access or file mutation occurs.
    """
    original = Path(value).expanduser()
    if original.exists():
        return original
    if _windows() and not original.is_absolute() and _msys_drive(value):
        # Git Bash 꼴 '/c/…' 은 윈도우에서 드라이브가 없어 상대경로로 읽힌다 — 뜻이 하나뿐이라 읽어 준다(#179).
        original = Path(_msys_drive(value))
        if original.exists():
            return original
    if not original.is_absolute():
        # 받은 경로를 보여 준다(#179 — 예전에는 어느 경로인지 없어 원인을 가를 수 없었다).
        raise ValueError(f'Input path must be absolute — 받은 경로: {value!r}. 윈도우는 C:\\…, 맥은 /Users/… 꼴의 절대경로를 넣으세요.')
    return _walk(Path(original.anchor), list(original.parts[1:]), original)


def _walk(current, parts, original):
    """남은 이름 조각(parts)을 current 아래에서 찾는다. '?' 로 깨진 조각은 후보가 여럿일 수 있어 **경로 끝까지** 따라가 본 뒤
    끝까지 이어지는 경로가 하나뿐일 때만 고른다(10-20 명화관 신고: 'D:\\????' 에 맞는 폴더가 3개라 첫 조각에서 멈췄다 —
    그 아래 나머지 조각까지 이어지는지는 보지 않았다).
    한 조각씩 디렉터리를 한 번만 읽고, 이어지지 않는 후보는 그 자리에서 버린다."""
    for index, part in enumerate(parts):
        literal = current / part
        if literal.exists():
            current = literal
            continue
        target = unicodedata.normalize('NFC', part)
        try:
            entries = list(current.iterdir())
        except OSError as exc:
            raise FileNotFoundError('입력 파일을 찾을 수 없습니다: ' + str(original) + f' ({current} 를 열 수 없음: {exc})') from exc
        matches = [entry for entry in entries if unicodedata.normalize('NFC', entry.name) == target]
        if len(matches) > 1:
            raise ValueError('여러 파일이 같은 유니코드 이름과 일치합니다. 실제 파일 경로를 지정하세요: ' + str(literal))
        if matches:
            current = matches[0]
            continue
        lost = _lost_pattern(part) if _windows() else None
        if lost is None:
            raise FileNotFoundError('입력 파일을 찾을 수 없습니다: ' + str(original))
        # '?' 하나 = 비ASCII 글자 하나 — 후보마다 나머지 조각을 끝까지 따라가 이어지는 경로가 하나뿐일 때만 복구한다(추측으로 다른 파일을 고르지 않는다).
        candidates = [entry for entry in entries if lost.fullmatch(unicodedata.normalize('NFC', entry.name))]
        rest = parts[index + 1:]
        complete = []
        for entry in candidates:
            try:
                complete.append(_walk(entry, rest, original))
            except (FileNotFoundError, ValueError):
                continue
            if len(complete) > 1:
                break
        if len(complete) == 1:
            return complete[0]
        if complete:
            raise FileNotFoundError('입력 파일을 찾을 수 없습니다: ' + str(original) + _ENCODING_HINT
                                    + f' ({complete[0]} · {complete[1]} 등 이 꼴에 맞는 실제 경로가 여럿이라 고르지 않았습니다)')
        raise FileNotFoundError('입력 파일을 찾을 수 없습니다: ' + str(original) + _ENCODING_HINT
                                + (f' ({current} 안에 맞는 이름이 {len(candidates)}개였지만 그 아래로 이 경로가 이어지는 곳이 없습니다)'
                                   if candidates else ''))
    return current


def resolve_declared_inputs(item):
    """Resolve only server-declared argv inputs and return named observations."""
    argv = list(item['argv'])
    observed = {}
    for rule in item.get('resolve_inputs') or []:
        requested = rule['path']
        if requested not in argv:
            raise ValueError('Declared input is absent from command arguments.')
        actual = str(resolve_existing_input(requested))
        argv = [actual if value == requested else value for value in argv]
        if rule.get('as'):
            observed[rule['as']] = actual
    return dict(item, argv=argv), observed
