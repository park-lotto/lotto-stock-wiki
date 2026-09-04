# -*- coding: utf-8 -*-
"""전 과정을 **혼자 끝까지** 돈다 — 한계 없이, 사람이 안 봐도 된다 (2026-09-05).

사장님 지시: "한계를 정하지말고 정교하게" / "대충하지말고" / "백그라운드에서해" / "토큰먹지말고"

## 무엇을 하나

    ① 발굴   쿼터가 마를 때까지 계속 (수렴하면 씨앗 바꿔 재시도)
    ② 수집   통과 채널 전부, 채널당 상한 없음
    ③ 선별   안 걸린 것 **전부** + 대조군 전부
    ④ 전사   **전량**. 실패는 재시도. 끊겨도 이어서
    ⑤ 분석   정규식 6축 + ★n-gram 고정어구 채굴

## 사람 손이 필요 없게

- 각 단계는 **재개 가능**하다. 죽으면 다시 실행하면 이어서 한다.
- 진행은 `out/sul_survey/progress.txt` 한 줄로만 갱신한다(로그 폭주 없음).
- 결과는 `out/sul_survey/REPORT.md` 로 떨어진다 — 그것만 읽으면 된다.

실행:
    nohup py scripts/run_all.py > out/run_all.log 2>&1 &
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "out" / "sul_survey"
OUT.mkdir(parents=True, exist_ok=True)
PROG = OUT / "progress.txt"
PY = sys.executable


def note(s):
    line = "[%s] %s" % (datetime.now().strftime("%m-%d %H:%M"), s)
    PROG.write_text(line + "\n", encoding="utf-8")
    print(line, flush=True)


def run(args, timeout=None):
    try:
        r = subprocess.run([PY] + args, cwd=str(BASE), capture_output=True, timeout=timeout)
        return r.returncode, (r.stdout or b"").decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


def n_transcribed():
    d = OUT / "transcripts"
    return len(list(d.glob("*.json"))) if d.exists() else 0


def n_videos():
    f = OUT / "videos.json"
    if not f.exists():
        return 0
    try:
        return len(json.loads(f.read_text(encoding="utf-8")))
    except Exception:
        return 0


def main():
    # ── ① 발굴: 쿼터 마를 때까지 ────────────────────────────────────
    note("① 발굴 시작")
    for attempt in range(4):
        rc, out = run(["scripts/harvest_sul_local.py", "--rounds", "40"], timeout=7200)
        st = OUT / "state.json"
        n = len(json.loads(st.read_text(encoding="utf-8"))["passed"]) if st.exists() else 0
        note("① 발굴 %d차 끝 — 통과 %d채널" % (attempt + 1, n))
        if "소진" in out or "수렴" in out:
            break

    # ── ② 수집: 채널 전부 ──────────────────────────────────────────
    note("② 영상 수집 시작")
    run(["scripts/transcribe_hits.py", "--collect"], timeout=10800)
    note("② 수집 끝 — %d편" % n_videos())

    # ── ③ 선별: 상한 없이 전부 ─────────────────────────────────────
    note("③ 전사 대상 선별")
    run(["scripts/pick_unknown.py", "--n-unknown", "999999",
         "--n-known", "999999"], timeout=3600)

    # ── ④ 전사: 전량. 남은 게 없을 때까지 반복 ──────────────────────
    note("④ 전사 시작")
    stall = 0
    while True:
        before = n_transcribed()
        run(["scripts/transcribe_hits.py", "--transcribe", "-n", "500"], timeout=7200)
        after = n_transcribed()
        note("④ 전사 %d편 완료" % after)
        if after == before:
            stall += 1
            if stall >= 2:
                break
            time.sleep(20)
        else:
            stall = 0

    # ── ⑤ 분석 ────────────────────────────────────────────────────
    note("⑤ 분석")
    _, six = run(["scripts/classify_scripts.py", "--min-n", "5"], timeout=3600)
    _, ph3 = run(["scripts/mine_phrases.py", "--min-ch", "3", "--top", "80"], timeout=7200)
    _, ph6 = run(["scripts/mine_phrases.py", "--min-ch", "6", "--top", "60"], timeout=7200)

    rep = OUT / "REPORT.md"
    rep.write_text(
        "# 썰채널 전수조사 결과\n\n생성: %s\n\n"
        "전사 %d편 / 영상목록 %d편\n\n"
        "---\n\n## 1. 6축 분포 + 뭉치는 덩어리\n\n```\n%s\n```\n\n"
        "---\n\n## 2. ★고정 어구 — 채널 3개 이상에서 반복\n\n```\n%s\n```\n\n"
        "---\n\n## 3. ★★고정 어구 — 채널 6개 이상 (진짜 장르 문법)\n\n```\n%s\n```\n"
        % (datetime.now().strftime("%Y-%m-%d %H:%M"), n_transcribed(), n_videos(),
           six.strip(), ph3.strip(), ph6.strip()),
        encoding="utf-8")
    note("⑤ 끝 — out/sul_survey/REPORT.md")


if __name__ == "__main__":
    main()
