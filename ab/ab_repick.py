# -*- coding: utf-8 -*-
"""매칭 A/B 하네스 — 같은 비트·같은 인벤토리에 **모델만** 바꿔 재픽시킨다.

★왜 이렇게 짜나 (CLAUDE.md 0순위-B):
  판정 규칙(_SCENE_PLACEMENT_RULES·_want_shots_for_role·_REPICK_SCHEMA)을 여기에
  베끼지 않는다. 프로덕션 함수 `edit_plan._repick_weak_beats`를 **그대로 호출**하고
  `call=`만 갈아끼운다. 규칙이 바뀌면 A/B도 자동으로 따라간다.

★왜 재픽만 떼나 (2026-08-18 실측된 방법):
  3단계 전체(다운로드·전사·TTS·렌더)를 돌려야만 아는 건 "영상이 좋아 보이나" 하나뿐이다.
  `_repick_weak_beats(beats, seg_map, call=...)`가 호출 함수를 인자로 받으므로
  라이브 잡의 진짜 비트·세그를 넣고 재픽만 돌릴 수 있다.

오푸스 호출은 `claude -p --model opus` (구독 = API 과금 0원).
  ⚠️ Agent SDK 구독 크레딧은 보류 상태 — PC에서 CLI를 부르는 이 경로만 0원이다.
"""
import io
import json
import os
import re
import subprocess
import sys
import time


_ROOT = r"C:/Users/CH/Desktop/로또의 주식"
sys.path.insert(0, _ROOT)

from shopping_shorts import edit_plan  # noqa: E402


# ── 오푸스 호출 (구독 CLI) ───────────────────────────────────────────────
def _extract_json(text):
    """CLI 출력에서 JSON 객체만 건진다.

    ⚠️ 2026-06-22 사고(골드 페이지 파괴)의 교훈: 에이전트는 stdout에 잡담·요약을
    섞을 수 있다. 그래서 파싱을 관대하게 하되, **못 건지면 None**(fail-open)으로
    돌려 프로덕션 함수가 원본을 그대로 두게 한다.
    """
    if not text:
        return None
    t = text.strip()
    # ```json ... ``` 펜스 제거
    m = re.search(r"```(?:json)?\s*(.+?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    # 첫 { 부터 마지막 } 까지
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(t[i:j + 1])
    except json.JSONDecodeError:
        return None


def make_claude_call(model, log_dir, tag):
    """edit_plan이 기대하는 call(prompt, schema) -> dict 를 만든다."""
    n = {"i": 0}

    def _call(prompt, schema, max_tries=1, key_offset=0):
        n["i"] += 1
        # 스키마를 프롬프트에 명시 — Gemini는 response_schema로 강제되지만 CLI는 아니다.
        full = (prompt
                + "\n\n[출력 형식] 아래 JSON 스키마를 정확히 따르는 **JSON 객체만** 출력해라. "
                  "설명·인사·코드펜스 없이 순수 JSON만.\n"
                + json.dumps(schema, ensure_ascii=False))
        t0 = time.time()
        try:
            r = subprocess.run(
                ["claude", "-p", "--model", model],
                input=full, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600,
            )
        except subprocess.TimeoutExpired:
            print("      [%s] 호출 %d 타임아웃(600s)" % (tag, n["i"]), flush=True)
            return None
        dt = time.time() - t0
        out = r.stdout or ""
        # 원문을 남긴다 — 아침에 "왜 이렇게 골랐나"를 볼 수 있어야 한다.
        with open(os.path.join(log_dir, "%s_call%d.txt" % (tag, n["i"])),
                  "w", encoding="utf-8") as f:
            f.write("=== RC=%s (%.1fs) ===\n--- PROMPT ---\n%s\n--- STDOUT ---\n%s\n--- STDERR ---\n%s"
                    % (r.returncode, dt, full, out, (r.stderr or "")[:2000]))
        if r.returncode != 0:
            print("      [%s] 호출 %d 실패 rc=%s" % (tag, n["i"], r.returncode), flush=True)
            return None
        got = _extract_json(out)
        print("      [%s] 호출 %d %.1fs → %s"
              % (tag, n["i"], dt, "picks %d개" % len(got.get("picks", [])) if got else "파싱실패"),
              flush=True)
        return got

    return _call


def make_gemini_call(log_dir, tag):
    """대조군 — 프로덕션이 실제로 쓰는 제미니 경로 그대로."""
    n = {"i": 0}

    def _call(prompt, schema, max_tries=4, key_offset=0):
        n["i"] += 1
        t0 = time.time()
        got = edit_plan._vault_call(prompt, schema, max_tries=max_tries, key_offset=key_offset)
        dt = time.time() - t0
        with open(os.path.join(log_dir, "%s_call%d.txt" % (tag, n["i"])),
                  "w", encoding="utf-8") as f:
            f.write("--- PROMPT ---\n%s\n--- RESULT (%.1fs) ---\n%s"
                    % (prompt, dt, json.dumps(got, ensure_ascii=False, indent=1) if got else "None"))
        print("      [%s] 호출 %d %.1fs → %s"
              % (tag, n["i"], dt, "picks %d개" % len(got.get("picks", [])) if got else "없음"),
              flush=True)
        return got

    return _call
