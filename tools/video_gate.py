# -*- coding: utf-8 -*-
"""영상 관문 — 영상 제작 라인을 건드린 병합은 '편집 화면 미리보기 vs 완성본' **영상 비교**를 통과해야 들어간다(2026-09-27).

왜: 2026-09-26에 계산끼리 비교해 '됐다'고 세 번 틀렸다. 고객이 보는 건 영상이다. 사람이 기억해서 돌리는 검사는
    안 돌린 날 뚫린다 → track.py finish 가 명령으로 지킨다(설계 확정: 사람이 아니라 명령이 지킨다).

흐름(finish 의 기존 게이트 통과 뒤·커밋 전, 병합 임시 폴더 안):
  ① 병합될 변경(git diff --cached HEAD)에 제작 라인 파일이 있나 → 없으면 건너뜀(한 줄)
     app.py 는 바뀐 줄이 든 **최상위 함수 이름·라우트**로 가른다(ast). 못 정하면 실행.
  ② 서버 /tmp 여유 확인(min_free_gb 미만이면 **실패** — 조용히 넘기지 않는다)
  ③ 병합본 모듈(screen_clips·video_assemble·clean_base·mix_pipeline·app.py·runner.js·scene_play.js)을
     서버 /tmp/gate_<sha>/ 에 올리고 PATCH_DIR 로 editor_vs_final_video 를 최근 N작업에 돌린다(nohup, 폴링)
  ④ 요약 줄 판정: 다른 장면 > max_scene 이면 실패. 밀림은 기준값이 null 이면 보고만.
  ⑤ 성공·실패 모두 서버 폴더 삭제.

★기준값(gate_video.json)은 **병합 전 main 의 것**을 쓴다 — 트랙이 자기 관문 기준을 느슨하게 고쳐 통과하는 길을 막는다
  (main 에 아직 없으면 병합본 것). 기준을 바꾸는 병합은 **다음 병합부터** 적용된다.
★비교 도구(editor_vs_final_video.py·evf_run.py)는 **병합본**을 쓴다 — 도구의 오탐 수리(예: 6005bc510, 옛 판정 43칸 중 5칸 오탐)가
  그 병합 자신에게 적용돼야 하고, main 의 옛 도구는 요약 줄 형식도 다르다(`… 0.15초 이상 밀림 N` 3개 숫자).
  대신 이 병합이 도구를 바꾸면 finish 출력에 큰 경고를 남긴다(관문을 약하게 고쳤는지 사람이 볼 수 있게).
★우회: 환경변수 VIDEO_GATE_SKIP="<사유>" — 사장님 지시가 있을 때만. 쓰면 finish 출력에 큰 경고가 남는다.
"""
import ast
import io
import json
import os
import re
import subprocess
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_REL = "tools/gate_video.json"
TOOL_RELS = ("tools/editor_vs_final_video.py", "tools/evf_run.py")
PATCH_RELS = {                       # 서버 PATCH_DIR 안의 자리 ← 저장소 경로
    "screen_clips.py": "shopping_shorts/screen_clips.py",
    "video_assemble.py": "shopping_shorts/video_assemble.py",
    "clean_base.py": "shopping_shorts/clean_base.py",
    "mix_pipeline.py": "shopping_shorts/mix_pipeline.py",
    "app.py": "shopping_shorts/app.py",
    # screen_clips 는 자기 파일 옆의 runner.js·static/scene_play.js 를 부른다(_HERE 기준) — 같이 올려야
    # 패치된 screen_clips 가 '러너 없음'으로 죽지 않고, 러너·화면 코드 변경도 실제로 재진다.
    "screen_clips_runner.js": "shopping_shorts/screen_clips_runner.js",
    "static/scene_play.js": "shopping_shorts/static/scene_play.js",
}
REMOTE_REPO = "/home/ubuntu/lotto-stock-wiki"
HOST = "ubuntu@shoppingshorts.duckdns.org"          # IP는 바뀐다 — 도메인으로 간다(tools/mirror_live_job.py 와 같다)


def _find_key():
    import glob
    return (glob.glob("C:/Users/*/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem")
            + glob.glob(os.path.expanduser("~/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem")) or [""])[0]


# ── 설정 ─────────────────────────────────────────────────────────

def load_config(text=None):
    if text is None:
        text = (HERE / "gate_video.json").read_text(encoding="utf-8")
    return json.loads(text)


# ── ① 실행 여부 (순수 함수) ──────────────────────────────────────

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def diff_changed_lines(diff_u0):
    """`git diff -U0` → (옛 쪽 바뀐 줄번호 집합, 새 쪽 바뀐 줄번호 집합). 빈 줄·주석만 바뀐 줄은 뺀다."""
    old, new = set(), set()
    o = n = 0
    for line in diff_u0.splitlines():
        m = _HUNK.match(line)
        if m:
            # 순수 추가는 새 쪽 줄이, 순수 삭제는 옛 쪽 줄이 자기 함수를 알려준다(옛 소스·새 소스를 각각 본다)
            o, n = int(m.group(1)), int(m.group(3))
            continue
        if line.startswith(("+++", "---", "diff ", "index ")):
            continue
        body = line[1:].strip()
        meaningful = bool(body) and not body.startswith("#")
        if line.startswith("-"):
            if meaningful:
                old.add(o)
            o += 1
        elif line.startswith("+"):
            if meaningful:
                new.add(n)
            n += 1
    return old, new


def top_level_scopes(src):
    """최상위 함수·클래스의 (시작줄(데코레이터 포함), 끝줄, 이름, [라우트 경로]). 파싱 실패면 None."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    out = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        routes = []
        for d in node.decorator_list:
            if isinstance(d, ast.Call) and d.args and isinstance(d.args[0], ast.Constant) \
                    and isinstance(d.args[0].value, str):
                routes.append(d.args[0].value)
        out.append((start, node.end_lineno, node.name, routes))
    return out


def _scope_of(scopes, ln):
    for s, e, name, routes in scopes:
        if s <= ln <= e:
            return name, routes
    return None


def app_touches_video(old_src, new_src, diff_u0, cfg):
    """app.py 변경이 제작 라인(미리보기 굽기·렌더·청소·캡컷 라우트)에 닿나 → (실행?, 사유)."""
    old_lines, new_lines = diff_changed_lines(diff_u0)
    if not old_lines and not new_lines:
        return False, "app.py: 빈 줄·주석만 바뀜"
    name_keys = [k.lower() for k in cfg.get("app_name_keys", [])]
    route_keys = cfg.get("app_route_keys", [])
    hits, names = [], set()
    for src, lines in ((old_src, old_lines), (new_src, new_lines)):
        if not lines:
            continue
        scopes = top_level_scopes(src or "")
        if scopes is None:
            return True, "app.py: 파싱 실패 — 함수를 못 정해 실행"
        for ln in sorted(lines):
            sc = _scope_of(scopes, ln)
            if sc is None:
                return True, "app.py: 모듈 수준 변경(%d줄) — 영향 함수를 못 정해 실행" % ln
            name, routes = sc
            names.add(name)
            if any(k in name.lower() for k in name_keys) or \
                    any(r.startswith(k) for r in routes for k in route_keys):
                hits.append(name)
    if hits:
        return True, "app.py: 제작 라인 함수 변경 %s" % sorted(set(hits))
    return False, "app.py: 제작 라인 밖 함수만 변경 %s" % sorted(names)[:8]


def needs_video_gate(changed_files, cfg, app_decision=None):
    """변경 파일 목록 → (실행?, 사유 목록, 비교가 못 재는 파일 목록).
    app_decision: app.py 가 바뀌었을 때 부를 () -> (실행?, 사유). None 이면 app.py 변경은 '못 정함 → 실행'."""
    changed = [c.replace("\\", "/") for c in changed_files]
    watch = set(cfg.get("watch_files", []))
    hits = [c for c in changed if c in watch]
    reasons = ["제작 라인 파일 변경: %s" % c for c in hits]
    app_rel = cfg.get("app_file", "shopping_shorts/app.py")
    run = bool(hits)
    if app_rel in changed:
        ok, why = app_decision() if app_decision else (True, "app.py: 판정 함수 없음 — 실행")
        reasons.append(why)
        run = run or ok
    unmeasured = [c for c in hits if c in set(cfg.get("not_measured", []))]
    return run, reasons, unmeasured


# ── ④ 요약 판정 (순수 함수) ──────────────────────────────────────

_SUMMARY = re.compile(r"^== 칸 (\d+) · 다른 장면 (\d+) · [\d.]+초 이상 밀림\(가운데\) (\d+) · 경계 밀림 (\d+) · 정지컷만 밀림 (\d+)\s*$")
_JOB = re.compile(r"^(\S+) 칸(\d+)\(청소본 (\d+)\) ")
_SKIP = re.compile(r"^(\S+) 건너뜀 ?(.*)$")
_JOB_SCENE = re.compile(r"\| 다른장면 (\[.*?\]) \| 밀림")


def parse_report(text):
    """editor_vs_final_video report.txt → dict. 요약 줄이 없거나 모양이 다르면 summary=None(=판정 불가 → 실패)."""
    r = {"summary": None, "summary_line": "", "jobs": [], "skips": [], "scene_jobs": []}
    for line in (text or "").splitlines():
        if line.startswith("== 칸"):
            r["summary_line"] = line
            m = _SUMMARY.match(line)
            if m:
                tot, scene, sc, sb, sh = (int(x) for x in m.groups())
                r["summary"] = {"cells": tot, "scene": scene, "shift_center": sc,
                                "shift_boundary": sb, "shift_hold": sh}
            continue
        m = _JOB.match(line)
        if m:
            r["jobs"].append({"job": m.group(1), "cells": int(m.group(2)), "clean": int(m.group(3))})
            ms = _JOB_SCENE.search(line)
            # 작업 줄의 '다른장면' 목록이 비어 있지 않은데 요약이 0이면 요약을 믿지 않는다(교차 확인)
            if ms is None or ms.group(1) != "[]":
                r["scene_jobs"].append(m.group(1))
            continue
        m = _SKIP.match(line)
        if m:
            r["skips"].append({"job": m.group(1), "why": m.group(2).strip()})
    return r


def judge(parsed, cfg, benign_skips=("음성 없음",)):
    """→ (통과?, 실패 사유 목록, 보고만 하는 줄 목록). cfg 는 gate 또는 audit 절."""
    fails, notes = [], []
    s = parsed.get("summary")
    if s is None:
        fails.append("요약 줄(== 칸 …)을 못 읽었다 — 도구가 죽었거나 형식이 바뀌었다: %r" % parsed.get("summary_line", "")[:200])
        return False, fails, notes
    compared = len(parsed.get("jobs", []))
    if s["cells"] <= 0:
        fails.append("비교한 칸이 0 — 아무것도 안 쟀다")
    need = int(cfg.get("min_jobs_compared") or 0)
    if compared < need:
        fails.append("비교한 작업 %d개 < 최소 %d개" % (compared, need))
    err_skips = [k for k in parsed.get("skips", []) if not any(k["why"].startswith(b) for b in benign_skips)]
    if len(err_skips) > int(cfg.get("max_error_skips") or 0):
        fails.append("오류로 건너뛴 작업 %d개: %s" % (len(err_skips), "; ".join("%s(%s)" % (k["job"], k["why"][:80]) for k in err_skips)))
    if s["scene"] > int(cfg.get("max_scene") or 0):
        fails.append("다른 장면 %d칸 (기준 %d)" % (s["scene"], int(cfg.get("max_scene") or 0)))
    elif parsed.get("scene_jobs"):
        fails.append("요약은 다른 장면 %d인데 작업 줄에 다른 장면이 있다(또는 작업 줄 형식을 못 읽음): %s"
                     % (s["scene"], parsed["scene_jobs"]))
    for key, label in (("shift_center", "밀림(가운데)"), ("shift_boundary", "경계 밀림"), ("shift_hold", "정지컷만 밀림")):
        lim = cfg.get("max_" + key)
        if lim is None:
            notes.append("%s %d칸 — 보고만(기준 없음)" % (label, s[key]))
        elif s[key] > int(lim):
            fails.append("%s %d칸 (기준 %d)" % (label, s[key], int(lim)))
    ratio_lim = cfg.get("max_shift_ratio")
    if ratio_lim is not None and s["cells"] > 0:
        ratio = s["shift_center"] / s["cells"]
        if ratio > float(ratio_lim):
            fails.append("밀림(가운데) 칸 비율 %.0f%% (기준 %.0f%%)" % (ratio * 100, float(ratio_lim) * 100))
        else:
            notes.append("밀림(가운데) 칸 비율 %.0f%% (기준 %.0f%% 이하)" % (ratio * 100, float(ratio_lim) * 100))
    return not fails, fails, notes


# ── 서버 실행 ────────────────────────────────────────────────────

@dataclass
class GateResult:
    ok: bool
    ran: bool
    text: str
    lines: list = field(default_factory=list)


def _ssh_runner(key, host=HOST):
    def sh(cmd, stdin=None, timeout=120):
        try:
            p = subprocess.run(["ssh", "-i", key, "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", host, cmd],
                               input=stdin, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124, "ssh 시간 초과(%ds): %s" % (timeout, cmd[:80])
        except OSError as e:
            return 127, "ssh 실행 실패: %s" % e
        out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
        return p.returncode, out
    return sh


def _git_bytes(stage, *args):
    p = subprocess.run(["git", *args], cwd=str(stage), capture_output=True)
    return p.returncode, (p.stdout or b"")


def _git(stage, *args):
    rc, out = _git_bytes(stage, *args)
    return rc, out.decode("utf-8", "replace")


def _merged_blob(stage, rel):
    """병합본(인덱스) 파일 내용 — 작업 폴더가 아니라 git 이 커밋할 그 바이트(줄바꿈 변환 없음). 없으면 None."""
    rc, out = _git_bytes(stage, "show", ":%s" % rel)
    return out if rc == 0 else None


def _main_or_stage(stage, rel):
    """병합 전 main(HEAD) 의 파일 내용. 없으면 병합본 것. 둘 다 없으면 None."""
    rc, out = _git_bytes(stage, "show", "HEAD:%s" % rel)
    return out if rc == 0 else _merged_blob(stage, rel)


def _bundle(stage):
    """PATCH_DIR 묶음(병합본 모듈) + _tool/(main 의 도구) → tar.gz 바이트."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        def add(name, data):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            ti.mode = 0o644
            ti.mtime = int(time.time())
            tf.addfile(ti, io.BytesIO(data))
        for dst, rel in PATCH_RELS.items():
            data = _merged_blob(stage, rel)
            if data is not None:
                add(dst, data)
        for rel in TOOL_RELS:
            data = _merged_blob(stage, rel)
            if data is None:
                raise FileNotFoundError(rel)
            add("_tool/" + Path(rel).name, data)
    return buf.getvalue()


def _p(printer, s):
    printer(s)
    return s


def run_video_gate(stage, br, *, printer=print, sh=None, cfg=None, env=None, sleep=time.sleep, remote_tmp="/tmp"):
    """finish 에서 부른다. GateResult(ok=False)면 병합을 버려야 한다."""
    env = os.environ if env is None else env
    log = []
    say = lambda s: log.append(_p(printer, s))           # noqa: E731

    if cfg is None:
        raw = _main_or_stage(stage, CONFIG_REL)
        cfg = load_config(raw.decode("utf-8") if raw else None)
    g = cfg["gate"]

    rc, out = _git(stage, "-c", "core.quotepath=off", "diff", "--cached", "--name-only", "HEAD")
    if rc != 0:
        say("❌ 영상 관문: 병합 변경 목록을 못 읽었다 — 실패로 본다\n" + out)
        return GateResult(False, False, "\n".join(log), log)
    changed = [x.strip() for x in out.splitlines() if x.strip()]

    def app_decision():
        rel = cfg.get("app_file", "shopping_shorts/app.py")
        _, old = _git(stage, "show", "HEAD:%s" % rel)
        new = (_merged_blob(stage, rel) or b"").decode("utf-8", "replace")
        _, d = _git(stage, "diff", "--cached", "-U0", "HEAD", "--", rel)
        return app_touches_video(old, new, d, cfg)

    run, reasons, unmeasured = needs_video_gate(changed, cfg, app_decision)
    if not run:
        say("영상 관문: 건너뜀 — 제작 라인 변경 없음 (변경 %d파일%s)" % (
            len(changed), "; " + "; ".join(reasons) if reasons else ""))
        return GateResult(True, False, "\n".join(log), log)

    say("영상 관문: 실행 — " + " / ".join(reasons))
    for u in unmeasured:
        say("  ⚠️ %s 변경은 이 비교(편집 화면 vs 완성본)가 재지 않는다 — 캡컷·내보내기는 따로 확인해야 한다" % u)

    tool_changed = [c for c in changed if c in TOOL_RELS or c == CONFIG_REL]
    if tool_changed:
        say("  ⚠️⚠️ 이 병합이 영상 관문 자체를 바꾼다: %s — 도구는 병합본으로 재고, 기준값은 main 것을 쓴다. "
            "관문을 약하게 만든 변경이 아닌지 diff 를 확인하라." % tool_changed)

    skip = (env.get("VIDEO_GATE_SKIP") or "").strip()
    if skip:
        bar = "!" * 64
        say("\n%s\n!!  영상 관문 건너뜀 (사유: %s)\n!!  사장님 지시가 있을 때만 쓴다. 비교 없이 병합된다.\n%s\n" % (bar, skip, bar))
        return GateResult(True, False, "\n".join(log), log)

    if sh is None:
        key = _find_key()
        if not key:
            say("❌ 영상 관문: SSH 키(LightsailDefaultKey)를 못 찾았다 — 비교 없이 병합하지 않는다")
            return GateResult(False, True, "\n".join(log), log)
        sh = _ssh_runner(key)

    rc, sha = _git(stage, "rev-parse", "--short=10", br)
    sha = sha.strip()
    if rc != 0 or not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        say("❌ 영상 관문: 트랙 커밋 해시를 못 읽었다: %r" % sha[:80])
        return GateResult(False, True, "\n".join(log), log)
    d = "%s/gate_%s" % (remote_tmp.rstrip("/"), sha)            # remote_tmp 는 시험 실행 때만 바꾼다(/tmp/gatecheck)

    try:
        rc, out = sh("df -BG --output=avail /tmp | tail -1")
        m = re.search(r"(\d+)G", out)
        if rc != 0 or not m:
            say("❌ 영상 관문: 서버에 못 붙었다(디스크 확인 실패) — 비교 없이 병합하지 않는다\n%s" % out.strip()[:300])
            return GateResult(False, True, "\n".join(log), log)
        free = int(m.group(1))
        if free < int(g.get("min_free_gb", 20)):
            say("❌ 영상 관문: 서버 /tmp 여유 %dGB < %dGB — 비교를 못 돌려 실패로 본다(디스크부터 비워라)"
                % (free, int(g.get("min_free_gb", 20))))
            return GateResult(False, True, "\n".join(log), log)
        say("  서버 /tmp 여유 %dGB · 폴더 %s" % (free, d))

        try:
            blob = _bundle(stage)
        except FileNotFoundError as e:
            say("❌ 영상 관문: 비교 도구 파일이 없다: %s" % e)
            return GateResult(False, True, "\n".join(log), log)
        rc, out = sh("rm -rf %s && mkdir -p %s && tar xzf - -C %s && mkdir -p %s/static %s/out && "
                     "ln -s %s/shopping_shorts/static/fonts %s/static/fonts && ln -s %s/shopping_shorts/assets %s/assets && echo UP_OK"
                     % (d, d, d, d, d, REMOTE_REPO, d, REMOTE_REPO, d), stdin=blob, timeout=300)
        if rc != 0 or "UP_OK" not in out:
            say("❌ 영상 관문: 서버에 모듈을 못 올렸다\n%s" % out.strip()[:400])
            return GateResult(False, True, "\n".join(log), log)

        n = int(g.get("jobs", 6))
        # ★& 는 중괄호 안의 한 명령에만 — `a && b && c &` 로 쓰면 && 사슬 전체가 배경 셸이 되고 그 셸이 ssh 출력을
        #   붙잡아 ssh 가 안 끝난다(2026-09-27 시험 실행에서 120초 시간 초과로 실측).
        rc, out = sh("cd %s && set -a && . /etc/shopping-shorts.env && set +a && "
                     "{ PATCH_DIR=%s EVF_OUT=%s/out setsid nohup python3 %s/_tool/evf_run.py %d > %s/run.log 2>&1 < /dev/null & echo PID=$!; }"
                     % (REMOTE_REPO, d, d, d, n, d))
        m = re.search(r"PID=(\d+)", out)
        if rc != 0 or not m:
            say("❌ 영상 관문: 비교를 못 띄웠다\n%s" % out.strip()[:400])
            return GateResult(False, True, "\n".join(log), log)
        pid = int(m.group(1))
        say("  비교 시작 — 최근 작업 %d개 (작업당 26~72초). pid %d" % (n, pid))

        t0 = time.time()
        timeout = int(g.get("timeout_sec", 1500))
        poll = int(g.get("poll_sec", 20))
        done, seen = False, 0
        while time.time() - t0 < timeout:
            sleep(poll)
            rc, out = sh("cat %s/out/done.txt 2>/dev/null; echo ---; wc -l < %s/out/report.txt 2>/dev/null; "
                         "kill -0 %d 2>/dev/null && echo ALIVE || echo GONE" % (d, d, pid))
            if "EVF_DONE" in out:
                done = True
                break
            lines = re.search(r"---\s*(\d+)", out)
            k = int(lines.group(1)) if lines else 0
            if k != seen:
                say("  … report %d줄 (%.0f초)" % (k, time.time() - t0))
                seen = k
            if "GONE" in out:
                break                         # done.txt 없이 죽었다 → 아래에서 실패
        if not done:
            sh("kill -- -%d 2>/dev/null; kill %d 2>/dev/null; true" % (pid, pid))
            _, tail = sh("tail -30 %s/run.log 2>/dev/null; cat %s/out/crash.txt 2>/dev/null" % (d, d))
            say("❌ 영상 관문: 비교가 %s — 실패로 본다\n%s" % (
                "시간 초과(%d초)" % timeout if time.time() - t0 >= timeout else "끝 표식 없이 죽었다", tail.strip()[-2000:]))
            return GateResult(False, True, "\n".join(log), log)

        _, report = sh("cat %s/out/report.txt 2>/dev/null" % d)
        _, crash = sh("cat %s/out/crash.txt 2>/dev/null" % d)
        say("\n--- 영상 비교 report (서버 %s/out/report.txt) ---\n%s\n--- report 끝 ---" % (d, report.rstrip()))
        if crash.strip():
            say("--- 도구 비정상 종료 ---\n%s" % crash.strip()[-2000:])
        parsed = parse_report(report)
        ok, fails, notes = judge(parsed, g, tuple(cfg.get("benign_skips", ["음성 없음"])))
        if crash.strip():
            ok = False
            fails.append("도구가 예외로 끝났다(crash.txt)")
        say("판정 근거: %s" % (parsed.get("summary_line") or "(요약 줄 없음)"))
        for f_ in fails:
            say("  ✗ " + f_)
        for n_ in notes:
            say("  · " + n_)
        say("✅ 영상 관문 통과" if ok else "❌ 영상 관문 실패")
        return GateResult(ok, True, "\n".join(log), log)
    finally:
        sh("rm -rf %s" % d)
