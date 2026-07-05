"""이상 채널 코드수정 — claude -p(Edit 권한, target별 cwd)로 실제 수정 적용.
파괴적 작업/폭주 방지는 오케스트레이터가 diagnose() 결과와 실제 변경분으로 판단한다
(LLM 자율판단에 맡기지 않음)."""
import json
import os
import re
import subprocess

_SYS = """너는 '로또의 스탁브레인' 크롤링 파이프라인 버그 수정 담당이다.
아래 진단 결과대로 코드를 실제로 수정해라. target_files에 적힌 파일만 고치고 무관한
파일/리팩터링은 건드리지 마라. 다 고쳤으면 반드시 아래 JSON 객체 하나만 마지막에
출력해라(설명·코드펜스 금지):
{"done": true, "summary": "<무엇을 어떻게 고쳤는지 한두 문장>"}"""


def build_prompt(channel, diagnosis):
    files = ", ".join(diagnosis.get("target_files") or []) or "(진단에 명시 안 됨 — 직접 찾아라)"
    return f"""{_SYS}

## 채널
{channel}

## 진단
원인: {diagnosis['root_cause']}
수정 대상 파일: {files}
수정 계획: {diagnosis['fix_plan']}
"""


def parse_fix_result(raw: str):
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(d, dict) or "done" not in d:
        return None
    d.setdefault("summary", "")
    return d


def apply_fix(channel, diagnosis, cwd, claude_bin="claude", model="sonnet", timeout=180):
    prompt = build_prompt(channel, diagnosis)
    try:
        proc = subprocess.run(
            [claude_bin, "-p", prompt, "--model", model,
             "--output-format", "json", "--permission-mode", "bypassPermissions",
             "--disallowedTools", "Bash"],
            cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode != 0 or not proc.stdout:
            return None
        envelope = json.loads(proc.stdout)
        raw = envelope.get("result", "")
    except Exception:
        return None
    return parse_fix_result(raw)


def changed_files(repo_root):
    """git status --porcelain으로 수정된 파일 목록(추적+미추적) 반환."""
    try:
        proc = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root,
                               capture_output=True, encoding="utf-8", errors="replace", timeout=15)
        return [line[3:] for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def snapshot_mtimes(root, relative_paths):
    snap = {}
    for rel in relative_paths:
        p = os.path.join(root, rel)
        try:
            snap[rel] = os.path.getmtime(p)
        except OSError:
            snap[rel] = None
    return snap


def changed_relative_paths(root, relative_paths, before_snapshot):
    changed = []
    for rel in relative_paths:
        p = os.path.join(root, rel)
        try:
            after = os.path.getmtime(p)
        except OSError:
            after = None
        if before_snapshot.get(rel) != after:
            changed.append(rel)
    return changed


def within_file_cap(changed, cap=3):
    return len(changed) <= cap
