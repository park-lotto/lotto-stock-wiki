# -*- coding: utf-8 -*-
"""Claude 창구 — `claude -p`(Claude Code 헤드리스)로 글·그림 판독 → JSON (관제 097, 2026-10-18 밤).

왜: 사장님 10-18 밤 "제미나이 쓰지 말고" — 로컬·서버 제미나이 = 같은 키 묶음, 고객 서비스와 분당 천장 17~19건을 같이 쓴다
(handoff/제미니죽은키.md). 판독 = Claude 눈, 단순 작업 = 하이쿠(channel/칼카피_시작.md §11).
방식(seed_analyzer/match_compare.py 실측 그대로): 프롬프트는 표준입력(인자로 넘기면 잘려 빈 답), 빈 임시 폴더에서 부른다
(프로젝트 폴더면 CLAUDE.md·훅이 붙어 요약만 돌아온다). 그림은 그 임시 폴더에 파일로 두고 Read 로 열게 한다.

    ask(parts, prompt, tag="", model="haiku") -> (dict|None, err)    parts = 그림 bytes 목록(jpg)
material_auto.LLM 의 기본 창구다(fn(parts, prompt, tag)).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

TIMEOUT = 420
SONNET_TAGS = ("ma_fit", "ma_ref")      # 대사↔장면 판정·참고 쇼츠 판독 = 판단이라 소넷, 나머지(칸 설명·짝짓기·검색어) = 하이쿠


def model_for(tag: str) -> str:
    return "sonnet" if str(tag).startswith(SONNET_TAGS) else "haiku"


def _json_of(txt: str):
    t = (txt or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:  # noqa: BLE001 — 앞뒤 설명이 붙은 답은 가장 바깥 {} 만
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                return None
    return None


def ask(parts: list, prompt: str, tag: str = "", model: str | None = None) -> tuple[dict | None, str | None]:
    model = model or model_for(tag)
    d = Path(tempfile.mkdtemp(prefix="claude_ma_"))
    try:
        names = []
        for k, b in enumerate(parts or []):
            f = d / f"img_{k}.jpg"
            f.write_bytes(b)
            names.append(f.name)
        head = ""
        if names:
            head = ("먼저 Read 도구로 이 폴더의 그림 파일을 연다: " + ", ".join(names)
                    + ". 그림에서 실제로 보이는 것만 근거로 답한다.\n\n")
        full = head + prompt + "\n\n답은 오직 JSON 객체 하나. 앞뒤 설명·마크다운 금지."
        t0 = time.time()
        try:
            p = subprocess.run(["claude", "-p", "--model", model, "--output-format", "text", "--allowedTools", "Read"],
                               input=full, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=TIMEOUT, cwd=str(d), stdin=None)
        except subprocess.TimeoutExpired:
            return None, f"timeout {TIMEOUT}s"
        out = _json_of(p.stdout)
        if out is None:
            return None, f"rc={p.returncode} 빈/깨진 답 {round(time.time() - t0)}s: {(p.stdout or p.stderr or '')[:160]}"
        return out, None
    finally:
        shutil.rmtree(d, ignore_errors=True)


def analyze_llm(parts: list, prompt: str, tag: str = ""):
    """뜯기(analyze.py)가 넘기는 제미나이 꼴 parts([라벨 str, jpg bytes, …] 또는 [(경로, 'audio/mp3')]) → ask(그림 bytes 만) 어댑터.
    analyze 의 기본 창구(사장님 10-18 제미나이 금지 — 관제 235·097 합의 10-20, 주인 한 곳). 라벨은 프롬프트 앞에 번호로 접어 넣는다.
    소리는 이 창구가 못 받으므로 실패로 돌려준다(조용히 건너뛰지 않는다 — 받아쓰기는 vtt·스피치매틱스)."""
    imgs, labels = [], []
    for x in parts or []:
        if isinstance(x, (bytes, bytearray)):
            imgs.append(bytes(x))
        elif isinstance(x, str):
            labels.append(x)
        elif isinstance(x, tuple):
            return None, f"소리 판독({x[1] if len(x) > 1 else '?'})은 Claude 창구 미지원 — 받아쓰기는 vtt/스피치매틱스"
    head = ("그림 순서(Read 로 연 파일 순서)와 라벨: " + " / ".join(f"{i + 1}={lab}" for i, lab in enumerate(labels)) + "\n") if labels else ""
    return ask(imgs, head + prompt, tag)
