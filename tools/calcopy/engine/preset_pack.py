# -*- coding: utf-8 -*-
"""프리셋 묶음 zip 한 곳 — apply-01(관제 319, 11-06 · Jev 해결 0.54·위험 0.47·신뢰 0.89).
판단 주인: 무엇을 넣나(PACK_EXCLUDE 빼고 프리셋 폴더 전부) · 결정적 묶기(이름 정렬·ZipInfo 시각 1980-01-01 고정) · 묶은 뒤 검사(절대경로·키 꼴 문자열 0).
kal.py step_apply 가 확정(freeze) 뒤 부른다. 회원 흐름 runner_ops c_bm_brief 의 zip 블록을 이 함수로 바꾸는 것은 다음(그 파일은 이번 대상 아님).
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

PACK_EXCLUDE = ("_hand/", "_cache/", ".lock", ".part", "__pycache__/", ".pyc", "Thumbs.db")
TEXT_EXT = (".json", ".md", ".txt", ".py", ".csv", ".yaml", ".yml")
ABS_RE = re.compile(r"(?i)(?:\b[a-z]:[\\/]|/users/|/home/|\\\\users\\\\)")
KEY_RE = re.compile(r"(?:AIza[0-9A-Za-z_\-]{30,}|sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_\-]{20,}|AKIA[0-9A-Z]{16}|(?i:api[_-]?key)\s*[\"':=]\s*[\"']?[0-9A-Za-z_\-]{16,})")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _files(preset_dir: Path) -> list[Path]:
    out = []
    for p in sorted(preset_dir.rglob("*"), key=lambda x: x.relative_to(preset_dir).as_posix()):
        rel = p.relative_to(preset_dir).as_posix()
        if p.is_file() and not any(x in rel or rel.endswith(x) for x in PACK_EXCLUDE):
            out.append(p)
    return out


def scan(name: str, data: bytes) -> list[str]:
    """텍스트 파일 한 개에서 절대경로·키 꼴 문자열(값은 앞 6자만 보고에)."""
    if not name.lower().endswith(TEXT_EXT):
        return []
    t = data.decode("utf-8", "replace")
    bad = [f"{name}: 절대경로 '{m.group(0)}'" for m in ABS_RE.finditer(t)][:3]
    bad += [f"{name}: 키 꼴 '{m.group(0)[:6]}…'" for m in KEY_RE.finditer(t)][:3]
    return bad


def pack(preset_dir: Path, out: Path) -> dict:
    """프리셋 폴더 → 결정적 zip. 묶은 뒤 zip 안 텍스트를 훑어 절대경로·키 꼴이 1건이라도 있으면 zip 을 지우고 {ok: False, bad}."""
    preset_dir, out = Path(preset_dir), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    files = _files(preset_dir)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            zi = zipfile.ZipInfo(p.relative_to(preset_dir).as_posix(), FIXED_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, p.read_bytes())
    bad = []
    with zipfile.ZipFile(out) as z:
        for n in z.namelist():
            bad += scan(n, z.read(n))
    if bad:
        out.unlink(missing_ok=True)
        return {"ok": False, "bad": bad, "n": len(files)}
    return {"ok": True, "zip": str(out), "n": len(files)}
