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
import gate_modules  # noqa: E402  — 제작 라인 모듈 목록 정본(관제 085)
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
TOOL_RELS = gate_modules.TOOL_RELS   # 정본은 tools/gate_modules.py(관제 085)
AUDIO_TOOL = "final_audio_audit.py"     # ⑥ 소리 대조(편성표 vs 완성본 소리) — 영상 비교가 구운 임시 완성본을 그대로 잰다
CL_TOOL = "clean_left_audit.py"         # ⑦ 자막 남음(청소본이 있어야 할 칸인데 원본 재료) — 영상 비교는 원본을 틀어 장면이 같게 나와 못 본다
CC_TOOL = "capcut_export_audit.py"      # ⑤ 캡컷·내보내기 대조(완성본 컷 계획 vs 캡컷 초안 vs ZIP 조각) — 영상 비교 뒤 같은 작업에
PATCH_RELS = gate_modules.PATCH_RELS   # 서버 PATCH_DIR 안의 자리 ← 저장소 경로. 정본은 tools/gate_modules.py(관제 085) —
#   새 제작 라인 모듈은 거기 한 곳에만 적는다(전엔 6벌이 서로 어긋나 있었다: seg_snap·clean_left_audit 누락 등).
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


def module_stmt_names(src):
    """최상위 **문장**(함수·클래스 밖)의 (시작줄, 끝줄, [이름], 종류). 대입·주석 대입·누적 대입은 대상 이름을 준다.
    import·호출(Expr)·if 등은 이름 없이 종류만 — 영향을 못 정하므로 호출부가 '실행'으로 본다. 파싱 실패면 None."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        names = []
        if isinstance(node, ast.Assign):
            for t in node.targets:
                names += [n.id for n in ast.walk(t) if isinstance(n, ast.Name)]
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        out.append((node.lineno, node.end_lineno, names, type(node).__name__))
    return out


def _module_stmt_of(stmts, ln):
    for s, e, names, kind in stmts:
        if s <= ln <= e:
            return names, kind
    return None


def app_touches_video(old_src, new_src, diff_u0, cfg):
    """app.py 변경이 제작 라인(미리보기 굽기·렌더·청소·캡컷 라우트)에 닿나 → (실행?, 사유)."""
    old_lines, new_lines = diff_changed_lines(diff_u0)
    if not old_lines and not new_lines:
        return False, "app.py: 빈 줄·주석만 바뀜"
    name_keys = [k.lower() for k in cfg.get("app_name_keys", [])]
    route_keys = cfg.get("app_route_keys", [])
    hits, names, consts = [], set(), set()
    for src, lines in ((old_src, old_lines), (new_src, new_lines)):
        if not lines:
            continue
        scopes = top_level_scopes(src or "")
        stmts = module_stmt_names(src or "")
        if scopes is None or stmts is None:
            return True, "app.py: 파싱 실패 — 함수를 못 정해 실행"
        for ln in sorted(lines):
            sc = _scope_of(scopes, ln)
            if sc is None:
                # ★모듈 수준(2026-10-02, 카드 069): 전엔 무조건 실행이라 공개 경로 튜플·요금 템플릿 한 줄에도 20분 관문이 돌고
                #   라이브 잔상(제작 라인 기존 결함)으로 막혔다. 대입문이면 **대상 이름**으로 판정 — 이름에 제작 라인 열쇠가
                #   있으면 실행, 아니면 상수 변경으로 본다. 이름을 못 정하는 문장(import·호출·if)은 종전대로 실행.
                ms = _module_stmt_of(stmts, ln)
                if ms is None or not ms[0]:
                    return True, "app.py: 모듈 수준 변경(%d줄, %s) — 영향을 못 정해 실행" % (ln, ms[1] if ms else "문장 밖")
                for nm in ms[0]:
                    if any(k in nm.lower() for k in name_keys):
                        hits.append(nm)
                    consts.add(nm)
                continue
            name, routes = sc
            names.add(name)
            if any(k in name.lower() for k in name_keys) or \
                    any(r.startswith(k) for r in routes for k in route_keys):
                hits.append(name)
    if hits:
        return True, "app.py: 제작 라인 함수·상수 변경 %s" % sorted(set(hits))
    extra = (" · 모듈 상수 %s" % sorted(consts)[:6]) if consts else ""
    return False, "app.py: 제작 라인 밖 함수만 변경 %s%s" % (sorted(names)[:8], extra)


def needs_video_gate(changed_files, cfg, app_decision=None):
    """변경 파일 목록 → (실행?, 사유 목록, 비교가 못 재는 파일 목록).
    app_decision: app.py 가 바뀌었을 때 부를 () -> (실행?, 사유). None 이면 app.py 변경은 '못 정함 → 실행'."""
    changed = [c.replace("\\", "/") for c in changed_files]
    watch = set(cfg.get("watch_files") or gate_modules.WATCH_FILES)   # 기본 = 정본 목록(관제 085)
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
# 잔상 줄(2026-09-27) — editor_vs_final_video 가 '== 칸' 줄과 **따로** 낸다(그 줄은 위 _SUMMARY 가 줄 끝까지 맞춰 읽는다)
_GHOST = re.compile(r"^== 잔상 (\d+)프레임\(컷 (\d+) · 화면에만 (\d+)프레임\) · 짧은컷\((\d+)프레임 이하\) (\d+)\s*$")
# 번쩍임 줄(2026-10-03 관제 099) — 완성본 한 장 번쩍임(다른 자리 그림 1프레임). editor_vs_final_video 가 따로 낸다.
_FLASH = re.compile(r"^== 번쩍임 (\d+)프레임\(작업 (\d+) · 못 잰 작업 (\d+)\)\s*$")


def parse_report(text):
    """editor_vs_final_video report.txt → dict. 요약 줄이 없거나 모양이 다르면 summary=None(=판정 불가 → 실패)."""
    r = {"summary": None, "summary_line": "", "jobs": [], "skips": [], "scene_jobs": [], "ghost": None, "ghost_line": "",
         "flash": None, "flash_line": ""}
    for line in (text or "").splitlines():
        if line.startswith("== 번쩍임"):
            r["flash_line"] = line
            mf = _FLASH.match(line)
            if mf:
                fr, jb, un = (int(x) for x in mf.groups())
                r["flash"] = {"frames": fr, "jobs": jb, "unknown": un}
            continue
        if line.startswith("== 잔상"):
            r["ghost_line"] = line
            mg = _GHOST.match(line)
            if mg:
                fr, cu, so, _sc, sh = (int(x) for x in mg.groups())
                r["ghost"] = {"frames": fr, "cuts": cu, "screen_only": so, "short": sh}
            continue
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
    elif s["scene"] == 0 and parsed.get("scene_jobs"):
        # 교차 확인은 **요약이 0일 때만**(parse_report: "요약이 0이면 요약을 믿지 않는다"). 전후 비교로 기준이 main 실측(>0)까지
        # 올라가면 작업 줄에 다른 장면이 있는 게 정상이다(2026-10-02, 카드 071).
        fails.append("요약은 다른 장면 %d인데 작업 줄에 다른 장면이 있다(또는 작업 줄 형식을 못 읽음): %s"
                     % (s["scene"], parsed["scene_jobs"]))
    for key, label in (("shift_center", "밀림(가운데)"), ("shift_boundary", "경계 밀림"), ("shift_hold", "정지컷만 밀림")):
        lim = cfg.get("max_" + key)
        if lim is None:
            notes.append("%s %d칸 — 보고만(기준 없음)" % (label, s[key]))
        elif s[key] > int(lim):
            fails.append("%s %d칸 (기준 %d)" % (label, s[key], int(lim)))
    # ★잔상(컷 가장자리 딴 장면 1~3프레임, 2026-09-27) — 기준 키가 있으면 판정, 줄을 못 읽으면 실패(조용히 통과 금지)
    g = parsed.get("ghost")
    for key, gk, label in (("max_ghost", "frames", "잔상"), ("max_ghost_screen_only", "screen_only", "화면에만 있는 잔상")):
        lim = cfg.get(key)
        if lim is None:
            if g is not None:
                notes.append("%s %d프레임 — 보고만(기준 없음)" % (label, g[gk]))
            continue
        if g is None:
            fails.append("잔상 줄(== 잔상 …)을 못 읽었다 — 도구가 옛 판본이거나 형식이 바뀌었다: %r"
                         % parsed.get("ghost_line", "")[:200])
            break
        if g[gk] > int(lim):
            fails.append("%s %d프레임 (기준 %d)" % (label, g[gk], int(lim)))
    # ★번쩍임(관제 099) — 기준 키가 있으면 판정. 줄을 못 읽거나 못 잰 작업이 있으면 실패(조용히 통과 금지)
    if cfg.get("max_flash") is not None:
        fl = parsed.get("flash")
        if fl is None:
            fails.append("번쩍임 줄(== 번쩍임 …)을 못 읽었다 — 도구가 옛 판본이거나 형식이 바뀌었다: %r" % parsed.get("flash_line", "")[:200])
        elif fl["unknown"]:
            fails.append("번쩍임을 못 잰 작업 %d개" % fl["unknown"])
        elif fl["frames"] > int(cfg["max_flash"]):
            fails.append("한 장 번쩍임 %d프레임 (기준 %d) — 완성본에 다른 자리 그림이 한 장 끼었다" % (fl["frames"], int(cfg["max_flash"])))
    ratio_lim = cfg.get("max_shift_ratio")
    if ratio_lim is not None and s["cells"] > 0:
        ratio = s["shift_center"] / s["cells"]
        if ratio > float(ratio_lim):
            fails.append("밀림(가운데) 칸 비율 %.0f%% (기준 %.0f%%)" % (ratio * 100, float(ratio_lim) * 100))
        else:
            notes.append("밀림(가운데) 칸 비율 %.0f%% (기준 %.0f%% 이하)" % (ratio * 100, float(ratio_lim) * 100))
    return not fails, fails, notes


def _cea():
    """캡컷·내보내기 대조 도구 모듈(요약 형식의 주인) — tools/ 가 import 경로에 없어도 파일로 싣는다."""
    import importlib.util
    _sp = importlib.util.spec_from_file_location("capcut_export_audit", str(HERE / "capcut_export_audit.py"))
    m = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(m)
    return m


def capcut_summary(report_text):
    """캡컷·내보내기 대조 report → {"cuts","capcut","export"} 또는 None."""
    return _cea().parse_summary(report_text)


def judge_capcut(report_text, cfg, crash="", benign_skips=("편집안 없음",)):
    """캡컷·내보내기 대조(capcut_export_audit) report → (통과?, 실패 사유, 보고만 하는 줄). 요약 형식은 도구 한 곳(parse_summary).
    기준: 캡컷 불일치 ≤ max_capcut_mismatch · 내보내기 불일치 ≤ max_export_mismatch (없으면 0 — 느슨해지지 않게)."""
    fails, notes = [], []
    s = capcut_summary(report_text)
    if s is None:
        fails.append("캡컷·내보내기 대조 요약 줄(== 컷 …)을 못 읽었다 — 도구가 죽었거나 형식이 바뀌었다")
        return False, fails, notes
    notes.append("캡컷·내보내기 대조: 컷 %d · 캡컷 불일치 %d · 내보내기 불일치 %d · 청소 미생성 %d job(청소 비교 제외)" % (
        s["cuts"], s["capcut"], s["export"], s.get("clean_missing", 0)))
    if s["cuts"] <= 0:
        fails.append("캡컷·내보내기 대조: 비교한 컷이 0 — 아무것도 안 쟀다")
    lc, le = int(cfg.get("max_capcut_mismatch") or 0), int(cfg.get("max_export_mismatch") or 0)
    if s["capcut"] > lc:
        fails.append("캡컷 불일치 %d컷 (기준 %d) — 캡컷 초안이 완성본과 다른 소스·컷·배속" % (s["capcut"], lc))
    if s["export"] > le:
        fails.append("내보내기 불일치 %d컷 (기준 %d) — ZIP 조각이 완성본과 다른 소스·구간·청소" % (s["export"], le))
    skips = [ln for ln in (report_text or "").splitlines() if re.match(r"^\S+ 건너뜀", ln)
             and not any(b in ln for b in benign_skips)]
    if len(skips) > int(cfg.get("max_error_skips") or 0):
        fails.append("캡컷·내보내기 대조: 오류로 건너뛴 작업 %d개: %s" % (len(skips), "; ".join(x[:120] for x in skips)))
    if (crash or "").strip():
        fails.append("캡컷·내보내기 대조 도구가 예외로 끝났다(crash.txt)")
    return not fails, fails, notes


def _faa():
    """소리 대조 도구 모듈(요약 형식의 주인) — 파일로 싣는다(PATCH_DIR 없이 — 순수 함수 parse_summary 만 쓴다)."""
    import importlib.util
    _sp = importlib.util.spec_from_file_location("final_audio_audit", str(HERE / "final_audio_audit.py"))
    m = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(m)
    return m


def audio_summary(report_text):
    """소리 대조 report → {"cells","narr","sfx_miss","bgm","lost","skip","surplus","delay","vcut_mis"} 또는 None."""
    return _faa().parse_summary(report_text)


def judge_audio(report_text, cfg, crash="", benign_skips=("음성 없음",)):
    """소리 대조(final_audio_audit) report → (통과?, 실패 사유, 보고 줄). 요약 형식은 도구 한 곳(parse_summary).
    기준(없으면 0 — 느슨해지지 않게): 나레이션 0.15초+ ≤ max_audio_narr · 패킷 잉여 0.05초+ ≤ max_audio_surplus ·
    일정 지연 ≤ max_audio_delay. 효과음 누락·BGM 이상은 키가 있을 때만 판정(관문 임시 완성본엔 효과음·BGM 이 없다)."""
    fails, notes = [], []
    s = audio_summary(report_text)
    if s is None:
        fails.append("소리 대조 요약 줄(== 칸 … 일정 지연 N편)을 못 읽었다 — 도구가 죽었거나 옛 판본이다")
        return False, fails, notes
    notes.append("소리 대조: 칸 %d · 나레이션 0.15초+ %d · 패킷 잉여 0.05초+ %d편 · 일정 지연 %d편 · 효과음 누락 %d · BGM 이상 %d"
                 " · 검출불일치 %d칸(보고만 — 영상 컷 검출이 계획 프레임과 0.1초+ 갈림, 화면 위치는 영상 비교가 잰다)"
                 % (s["cells"], s["narr"], s["surplus"], s["delay"], s["sfx_miss"], s["bgm"], s["vcut_mis"]))
    if s["cells"] <= 0:
        fails.append("소리 대조: 잰 칸이 0 — 아무것도 안 쟀다")
    for key, sk, label in (("max_audio_narr", "narr", "나레이션 0.15초+ 오차"), ("max_audio_surplus", "surplus", "패킷 잉여 0.05초+"),
                           ("max_audio_delay", "delay", "일정 지연"), ("max_audio_lost", "lost", "나레이션 못찾음")):
        lim = int(cfg.get(key) or 0)
        if s[sk] > lim:
            fails.append("%s %d (기준 %d) — 목소리가 화면·자막과 어긋난다" % (label, s[sk], lim))
    for key, sk, label in (("max_audio_sfx_miss", "sfx_miss", "효과음 누락"), ("max_audio_bgm", "bgm", "BGM 이상")):
        lim = cfg.get(key)
        if lim is not None and s[sk] > int(lim):
            fails.append("%s %d (기준 %d)" % (label, s[sk], int(lim)))
    skips = [ln for ln in (report_text or "").splitlines() if re.match(r"^\S+ 건너뜀", ln)
             and not any(b in ln for b in benign_skips)]
    if len(skips) > int(cfg.get("max_error_skips") or 0):
        fails.append("소리 대조: 오류로 건너뛴 작업 %d개: %s" % (len(skips), "; ".join(x[:120] for x in skips)))
    if (crash or "").strip():
        fails.append("소리 대조 도구가 예외로 끝났다(crash.txt)")
    return not fails, fails, notes


def _cla():
    """자막 남음 대조 도구 모듈(요약 형식의 주인) — 파일로 싣는다(순수 함수 parse_summary 만 쓴다)."""
    import importlib.util
    _sp = importlib.util.spec_from_file_location("clean_left_audit", str(HERE / "clean_left_audit.py"))
    m = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(m)
    return m


def clean_left_summary(report_text):
    """자막 남음 대조 report → {"jobs","left","pending","unknown","na","stale"} 또는 None."""
    return _cla().parse_summary(report_text)


def judge_clean_left(report_text, cfg, crash="", label="자막 남음"):
    """자막 남음 대조(clean_left_audit) report → (통과?, 실패 사유, 보고 줄). 요약 형식은 도구 한 곳(parse_summary).
    기준: 자막 남음 ≤ max_clean_left(없으면 0 — 느슨해지지 않게). 증분 대기(청소 뒤 편성 변경 — 렌더 때 동의창)·원인 미상은 보고만."""
    fails, notes = [], []
    s = clean_left_summary(report_text)
    if s is None:
        fails.append("자막 남음 대조 요약 줄(== 작업 … 자막 남음 N칸)을 못 읽었다 — 도구가 죽었거나 형식이 바뀌었다")
        return False, fails, notes
    notes.append("%s 대조: 작업 %d · 자막 남음 %d칸 · 증분 대기 %d칸 · 원인 미상 %d칸 · 대상 아님 %d작업%s" % (
        label, s["jobs"], s["left"], s["pending"], s["unknown"], s["na"],
        (" · 재구성 불가 %d작업" % s["stale"]) if s.get("stale") else ""))
    lim = int(cfg.get("max_clean_left") or 0)
    if s["left"] > lim:
        bad = [l_.split(" | ")[0] + " " + l_.split(" | ")[1] for l_ in (report_text or "").splitlines()
               if " | 자막 남음 [" in l_ and " | 자막 남음 []" not in l_]
        fails.append("%s %d칸 (기준 %d) — 청소본이 있어야 할 칸이 원본 재료(자막 있음)로 나간다: %s"
                     % (label, s["left"], lim, "; ".join(bad)[:600]))
    skips = [l_ for l_ in (report_text or "").splitlines() if " 건너뜀 " in l_]
    if len(skips) > int(cfg.get("max_error_skips") or 0):
        fails.append("%s 대조 오류로 건너뛴 작업 %d개: %s" % (label, len(skips), "; ".join(skips)[:400]))
    if crash.strip():
        fails.append("%s 대조 도구가 예외로 끝났다(crash.txt)" % label)
    return (not fails), fails, notes


def run_clean_left_audit(sh, d, ids, g, *, say, sleep=time.sleep, keep=None):
    """⑦ 영상 비교가 본 그 작업들로 자막 남음 대조(병합본 모듈 PATCH_DIR) → (통과?, 실패 사유, 보고 줄)."""
    if not ids:
        return False, ["자막 남음 대조: 비교할 작업이 없다(영상 비교 report 에 작업 줄 0)"], []
    ids = [i for i in ids if re.fullmatch(r"[0-9A-Za-z_-]{4,64}", i)]
    rc, out = sh("cd %s && set -a && . /etc/shopping-shorts.env && set +a && "
                 "{ PATCH_DIR=%s CL_OUT=%s/cl SEG_SNAP_CACHE_DIR=%s/snapcache setsid nohup python3 %s/_tool/%s %s > %s/cl_run.log 2>&1 < /dev/null & echo PID=$!; }"
                 % (REMOTE_REPO, d, d, d, d, CL_TOOL, " ".join(ids), d))
    m = re.search(r"PID=(\d+)", out)
    if rc != 0 or not m:
        return False, ["자막 남음 대조를 못 띄웠다: %s" % out.strip()[:300]], []
    pid = int(m.group(1))
    say("  자막 남음 대조 시작 — 작업 %d개. pid %d" % (len(ids), pid))
    done, timed_out = _wait_done(sh, "%s/cl/done.txt" % d, pid, int(g.get("clean_left_timeout_sec", 600)),
                                 int(g.get("poll_sec", 20)), sleep)
    if not done:
        sh("kill -- -%d 2>/dev/null; kill %d 2>/dev/null; true" % (pid, pid))
        _, tail = sh("tail -30 %s/cl_run.log 2>/dev/null; cat %s/cl/crash.txt 2>/dev/null" % (d, d))
        return False, ["자막 남음 대조가 %s\n%s" % ("시간 초과" if timed_out else "끝 표식 없이 죽었다", tail.strip()[-1500:])], []
    _, report = sh("cat %s/cl/report.txt 2>/dev/null" % d)
    _, crash = sh("cat %s/cl/crash.txt 2>/dev/null" % d)
    say("\n--- 자막 남음 대조 report (서버 %s/cl/report.txt) ---\n%s\n--- report 끝 ---" % (d, report.rstrip()))
    if keep is not None:
        keep['cl'] = report
        keep['cl_crash'] = crash
    return judge_clean_left(report, g, crash)


def run_audio_audit(sh, d, ids, g, *, say, sleep=time.sleep, keep=None):
    """⑥ 영상 비교가 구운 임시 완성본(d/finals/<job>.mp4)으로 소리 대조 → (통과?, 실패 사유, 보고 줄). 렌더 없음."""
    ids = [i for i in (ids or []) if re.fullmatch(r"[0-9A-Za-z_-]{4,64}", i)]
    if not ids:
        return False, ["소리 대조: 잴 작업이 없다(영상 비교 report 에 작업 줄 0)"], []
    rc, out = sh("cd %s && set -a && . /etc/shopping-shorts.env && set +a && "
                 "{ PATCH_DIR=%s AUDIO_FINAL_DIR=%s/finals AUDIO_OUT=%s/audio setsid nohup python3 %s/_tool/%s %s > %s/audio_run.log 2>&1 < /dev/null & echo PID=$!; }"
                 % (REMOTE_REPO, d, d, d, d, AUDIO_TOOL, " ".join(ids), d))
    m = re.search(r"PID=(\d+)", out)
    if rc != 0 or not m:
        return False, ["소리 대조를 못 띄웠다: %s" % out.strip()[:300]], []
    pid = int(m.group(1))
    say("  소리 대조 시작 — 작업 %d개(영상 비교의 임시 완성본 재사용). pid %d" % (len(ids), pid))
    done, timed_out = _wait_done(sh, "%s/audio/done.txt" % d, pid, int(g.get("audio_timeout_sec", 600)),
                                 int(g.get("poll_sec", 20)), sleep)
    if not done:
        sh("kill -- -%d 2>/dev/null; kill %d 2>/dev/null; true" % (pid, pid))
        _, tail = sh("tail -30 %s/audio_run.log 2>/dev/null; cat %s/audio/crash.txt 2>/dev/null" % (d, d))
        return False, ["소리 대조가 %s\n%s" % ("시간 초과" if timed_out else "끝 표식 없이 죽었다", tail.strip()[-1500:])], []
    _, report = sh("cat %s/audio/report.txt 2>/dev/null" % d)
    _, crash = sh("cat %s/audio/crash.txt 2>/dev/null" % d)
    say("\n--- 소리 대조 report (서버 %s/audio/report.txt) ---\n%s\n--- report 끝 ---" % (d, report.rstrip()))
    if keep is not None:
        keep['au'] = report
        keep['au_crash'] = crash
    return judge_audio(report, g, crash)


def _wait_done(sh, d_done, pid, timeout, poll, sleep):
    """서버 배경 작업을 끝 표식(done.txt 의 '..._DONE')까지 기다린다 → (끝났나, 시간초과인가).
    끝 표식 없이 프로세스가 사라지면 (False, False) — report 가 멀쩡해 보여도 믿지 않는다."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        sleep(poll)
        _rc, out = sh("cat %s 2>/dev/null; echo ---; kill -0 %d 2>/dev/null && echo ALIVE || echo GONE" % (d_done, pid))
        if "_DONE" in out:
            return True, False
        if "GONE" in out:
            return False, False
    return False, True


def run_capcut_audit(sh, d, ids, g, *, say, sleep=time.sleep, keep=None):
    """⑤ 영상 비교가 본 그 작업들로 캡컷·내보내기 대조를 돌린다(병합본 모듈 PATCH_DIR) → (통과?, 실패 사유, 보고 줄)."""
    if not ids:
        return False, ["캡컷·내보내기 대조: 비교할 작업이 없다(영상 비교 report 에 작업 줄 0)"], []
    ids = [i for i in ids if re.fullmatch(r"[0-9A-Za-z_-]{4,64}", i)]
    rc, out = sh("cd %s && set -a && . /etc/shopping-shorts.env && set +a && "
                 "{ PATCH_DIR=%s CC_OUT=%s/cc SEG_SNAP_CACHE_DIR=%s/snapcache setsid nohup python3 %s/_tool/%s %s > %s/cc_run.log 2>&1 < /dev/null & echo PID=$!; }"
                 % (REMOTE_REPO, d, d, d, d, CC_TOOL, " ".join(ids), d))
    m = re.search(r"PID=(\d+)", out)
    if rc != 0 or not m:
        return False, ["캡컷·내보내기 대조를 못 띄웠다: %s" % out.strip()[:300]], []
    pid = int(m.group(1))
    say("  캡컷·내보내기 대조 시작 — 작업 %d개. pid %d" % (len(ids), pid))
    done, timed_out = _wait_done(sh, "%s/cc/done.txt" % d, pid, int(g.get("capcut_timeout_sec", 900)),
                                 int(g.get("poll_sec", 20)), sleep)
    if not done:
        sh("kill -- -%d 2>/dev/null; kill %d 2>/dev/null; true" % (pid, pid))
        _, tail = sh("tail -30 %s/cc_run.log 2>/dev/null; cat %s/cc/crash.txt 2>/dev/null" % (d, d))
        return False, ["캡컷·내보내기 대조가 %s\n%s" % ("시간 초과" if timed_out else "끝 표식 없이 죽었다",
                                                   tail.strip()[-1500:])], []
    _, report = sh("cat %s/cc/report.txt 2>/dev/null" % d)
    _, crash = sh("cat %s/cc/crash.txt 2>/dev/null" % d)
    say("\n--- 캡컷·내보내기 대조 report (서버 %s/cc/report.txt) ---\n%s\n--- report 끝 ---" % (d, report.rstrip()))
    if keep is not None:
        keep['cc'] = report
        keep['cc_crash'] = crash
    return judge_capcut(report, g, crash)


# ── 전후 비교(2026-10-02 사장님 "쓸데없는 것까지 하는 거 아닌가", 카드 071) ─────────────────────────────
#   종전엔 병합본 영상이 **완벽한가**(잔상 0·다른 장면 0 …)를 봤다 → main 에도 있는 차이(옛 완성본·기존 결함)로 무관한 병합이 막혔다
#   (10-01 062·063·064 세 건, 2기모집 1차, 관문선정 11차 — 카드 067 실측: main 코드 그대로 돌려도 같은 2칸).
#   이제 같은 작업을 **main 코드로 먼저** 재고 기준 = max(설정값, main 실측) 으로 병합본을 같은 작업 목록에서 판정한다.
#   → 병합본이 **더 나빠졌을 때만** 막는다. 설정 gate.compare_main=false 면 종전(절대 기준) 그대로.
MAIN_CACHE_DIR = "/home/ubuntu/gate_main_cache"
MAIN_CACHE_TTL = 6 * 3600


def baseline_limits(g, parsed_main, reports):
    """main 실측으로 기준을 **올린다**(설정값보다 낮추지 않는다). 보고만 하는 기준(None)은 그대로 → (g2, 올린 목록)."""
    g2, raised = dict(g), []

    def up(key, val, label):
        cur = g.get(key)
        if val is None or cur is None:
            return
        if int(val) > int(cur):
            g2[key] = int(val)
            raised.append("%s %d→%d" % (label, int(cur), int(val)))
    s_ = parsed_main.get("summary") or {}
    up("max_scene", s_.get("scene"), "다른 장면")
    for k, label in (("shift_center", "밀림(가운데)"), ("shift_boundary", "경계 밀림"), ("shift_hold", "정지컷만 밀림")):
        up("max_" + k, s_.get(k), label)
    gh = parsed_main.get("ghost") or {}
    up("max_ghost", gh.get("frames"), "잔상")
    up("max_ghost_screen_only", gh.get("screen_only"), "화면에만 있는 잔상")
    up("max_flash", (parsed_main.get("flash") or {}).get("frames"), "한 장 번쩍임")
    cc = capcut_summary(reports["cc"]) if reports.get("cc") else None
    if cc:
        up("max_capcut_mismatch", cc.get("capcut"), "캡컷 불일치")
        up("max_export_mismatch", cc.get("export"), "내보내기 불일치")
    au = audio_summary(reports["au"]) if reports.get("au") else None
    if au:
        for key, sk, label in (("max_audio_narr", "narr", "나레이션 0.15초+"), ("max_audio_surplus", "surplus", "패킷 잉여"),
                               ("max_audio_delay", "delay", "일정 지연"), ("max_audio_lost", "lost", "나레이션 못찾음"),
                               ("max_audio_sfx_miss", "sfx_miss", "효과음 누락"), ("max_audio_bgm", "bgm", "BGM 이상")):
            up(key, au.get(sk), label)
    cl = clean_left_summary(reports["cl"]) if reports.get("cl") else None
    if cl:
        up("max_clean_left", cl.get("left"), "자막 남음")
    return g2, raised


def _run_side(sh, d, blob, job_arg, g, cfg, *, say, sleep, label, g_fn=None):
    """서버 폴더 d 에 묶음을 올려 영상 비교 → 캡컷 → 소리 → 자막 남음 대조. 판정은 g 로.
    → (통과?, 실패, 보고, parsed, reports, 돌았나). 못 돌았으면(올리기·띄우기·시간 초과) 돌았나=False."""
    reports = {}
    rc, out = sh("rm -rf %s && mkdir -p %s && tar xzf - -C %s && mkdir -p %s/static %s/out && "
                 "ln -s %s/shopping_shorts/static/fonts %s/static/fonts && ln -s %s/shopping_shorts/assets %s/assets && echo UP_OK"
                 % (d, d, d, d, d, REMOTE_REPO, d, REMOTE_REPO, d), stdin=blob, timeout=300)
    if rc != 0 or "UP_OK" not in out:
        return False, ["영상 관문(%s): 서버에 모듈을 못 올렸다\n%s" % (label, out.strip()[:400])], [], {}, reports, False
    # ★& 는 중괄호 안의 한 명령에만 — `a && b && c &` 로 쓰면 && 사슬 전체가 배경 셸이 되고 그 셸이 ssh 출력을
    #   붙잡아 ssh 가 안 끝난다(2026-09-27 시험 실행에서 120초 시간 초과로 실측).
    # ★SEG_SNAP_CACHE_DIR: 장면 전환 캐시를 관문 임시 폴더에 — 고객 폴더에 쓰지 않는다. EVF_KEEP_FINAL: 소리 대조가 같은 임시 완성본을 잰다.
    rc, out = sh("cd %s && set -a && . /etc/shopping-shorts.env && set +a && "
                 "{ PATCH_DIR=%s EVF_OUT=%s/out EVF_KEEP_FINAL=%s/finals SEG_SNAP_CACHE_DIR=%s/snapcache setsid nohup python3 %s/_tool/evf_run.py %s > %s/run.log 2>&1 < /dev/null & echo PID=$!; }"
                 % (REMOTE_REPO, d, d, d, d, d, job_arg, d))
    m = re.search(r"PID=(\d+)", out)
    if rc != 0 or not m:
        return False, ["영상 관문(%s): 비교를 못 띄웠다\n%s" % (label, out.strip()[:400])], [], {}, reports, False
    pid = int(m.group(1))
    say("  [%s] 비교 시작 — 작업 %s (작업당 26~72초). pid %d" % (label, job_arg, pid))
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
            say("  … [%s] report %d줄 (%.0f초)" % (label, k, time.time() - t0))
            seen = k
        if "GONE" in out:
            break
    if not done:
        sh("kill -- -%d 2>/dev/null; kill %d 2>/dev/null; true" % (pid, pid))
        _, tail = sh("tail -30 %s/run.log 2>/dev/null; cat %s/out/crash.txt 2>/dev/null" % (d, d))
        return False, ["영상 관문(%s): 비교가 %s\n%s" % (
            label, "시간 초과(%d초)" % timeout if time.time() - t0 >= timeout else "끝 표식 없이 죽었다", tail.strip()[-2000:])], [], {}, reports, False
    _, report = sh("cat %s/out/report.txt 2>/dev/null" % d)
    _, crash = sh("cat %s/out/crash.txt 2>/dev/null" % d)
    say("\n--- [%s] 영상 비교 report (서버 %s/out/report.txt) ---\n%s\n--- report 끝 ---" % (label, d, report.rstrip()))
    if crash.strip():
        say("--- [%s] 도구 비정상 종료 ---\n%s" % (label, crash.strip()[-2000:]))
    parsed = parse_report(report)
    ids = [j["job"] for j in parsed.get("jobs", [])]
    ran_audits = []
    for key, fn in (("cc", run_capcut_audit), ("au", run_audio_audit), ("cl", run_clean_left_audit)):
        ran_audits.append((key, fn(sh, d, ids, g, say=say, sleep=sleep, keep=reports)))
    # ★판정은 측정이 다 끝난 뒤 한 번에(2026-10-03 카드 088) — 병합본 쪽은 main 실측 기준(g_fn)이 나올 때까지 기다렸다 판정한다.
    #   판정 함수는 보고서 글만 보는 순수 함수라, 같은 보고서·같은 기준이면 종전(차례 실행)과 결과가 같다.
    gj = g_fn() if g_fn else g
    ok, fails, notes = judge(parsed, gj, tuple(cfg.get("benign_skips", ["음성 없음"])))
    if crash.strip():
        ok = False
        fails.append("도구가 예외로 끝났다(crash.txt)")
    judges = {"cc": judge_capcut, "au": judge_audio, "cl": judge_clean_left}
    for key, first in ran_audits:
        a_ok, a_fails, a_notes = (judges[key](reports[key], gj, reports.get(key + "_crash", ""))
                                  if key in reports else first)       # 못 돌았으면 그때의 실패 그대로
        ok = ok and a_ok
        fails += a_fails
        notes += a_notes
    return ok, fails, notes, parsed, reports, True


def _pick_ids(sh, blob, n, remote_tmp="/tmp"):
    """서버에서 비교할 작업을 **먼저** 고른다(도구의 _pick_jobs 그대로) — main·병합본이 같은 작업을 동시에 재게(카드 088). 실패면 []."""
    dp = "%s/gate_pick_%d" % (remote_tmp.rstrip("/"), os.getpid())
    rc, out = sh("rm -rf %s && mkdir -p %s && tar xzf - -C %s && cd %s && python3 -c \"import sys,sqlite3;"
                 "sys.path.insert(0,'%s/_tool');import editor_vs_final_video as e;"
                 "print('IDS=' + ' '.join(e._pick_jobs(sqlite3.connect('shopping_shorts/data/reference.db'),%d)))\"; rm -rf %s"
                 % (dp, dp, dp, REMOTE_REPO, dp, int(n), dp), stdin=blob, timeout=300)
    m = re.search(r"IDS=([0-9A-Za-z_ -]*)", out or "")
    ids = [i for i in (m.group(1).split() if m else []) if re.fullmatch(r"[0-9A-Za-z_-]{4,64}", i)]
    return ids


def _measure_parallel(sh, d, ck, cpath, ids, main_blob, merged_blob, g, cfg, *, say, sleep, remote_tmp, lead):
    """main·병합본을 **동시에** 잰다(2026-10-03 사장님 "둘 다 해", 카드 088 — 종전엔 main 다 재고 병합본을 차례로: 영상 관문 ~20분).
    병합본은 측정만 먼저 하고, 판정은 main 실측 기준(max(설정, main))이 나온 뒤에 한다 → 판정은 종전과 같다."""
    import threading
    dm = "%s/gate_main_%s" % (remote_tmp.rstrip("/"), ck)
    job_arg = " ".join(ids)
    got, ready, res = {}, threading.Event(), {}
    say("  [main·병합본] 같은 작업 %d개를 동시에 잰다(기준 = max(설정, main 실측)): %s" % (len(ids), job_arg))

    def g_for_merged():
        ready.wait()
        return got.get("g_use", g)

    def run_main():
        try:
            res["m"] = _run_side(sh, dm, main_blob, job_arg, g, cfg, say=say, sleep=sleep, label="main")
        except Exception as e:  # noqa: BLE001 — main 을 못 재면 종전 절대 기준
            res["m"] = (False, ["main 측정 예외: %r" % e], [], {}, {}, False)
        finally:
            try:
                _ok, _f, _n, parsed_m, rep_m, ran_m = res["m"]
                if ran_m and parsed_m.get("summary") is not None and parsed_m.get("jobs"):
                    g2, raised = baseline_limits(g, parsed_m, rep_m)
                    base = {"t": time.time(), "ids": [j["job"] for j in parsed_m["jobs"]], "g2": g2, "raised": raised,
                            "summary_line": parsed_m.get("summary_line", "")}
                    sh("mkdir -p %s && cat > %s" % (MAIN_CACHE_DIR, cpath), stdin=json.dumps(base, ensure_ascii=False).encode("utf-8"))
                    g_use = dict(g)
                    g_use.update(g2)
                    if len(base["ids"]) < int(g.get("min_jobs_compared") or 0):
                        g_use["min_jobs_compared"] = len(base["ids"])
                    got["g_use"] = g_use
                    lead.append("기준 = max(설정, main 실측) — main 이 같은 작업 %d개에서 잰 값: %s · main 요약: %s"
                                % (len(base["ids"]), ", ".join(raised) or "전부 설정값 이하", base["summary_line"][:120]))
                else:
                    lead.append("⚠️ main 을 못 재서 종전 절대 기준으로 판정한다(main: %s)" % ("; ".join(_f)[:200] or "요약 줄 없음"))
            finally:
                ready.set()
                sh("rm -rf %s" % dm)

    t0 = time.time()
    tm = threading.Thread(target=run_main, daemon=True)
    tm.start()
    ok, fails, notes, parsed, _reps, _ran = _run_side(sh, d, merged_blob, job_arg, g, cfg, say=say, sleep=sleep,
                                                     label="병합본", g_fn=g_for_merged)
    tm.join()
    lead.append("main·병합본 동시 측정 %.0f초" % (time.time() - t0))
    return ok, fails, lead + notes, (parsed or {}).get("summary_line", "")


def _measure_and_judge(sh, stage, br, cfg, g, *, say, sleep=time.sleep, remote_tmp="/tmp", with_summary=False):
    """서버 준비 → (compare_main 이면) main 실측(캐시) → 병합본 판정 → (통과?, 실패, 보고[, 요약 줄])."""
    def ret(ok, fails, notes, line=""):
        return (ok, fails, notes, line) if with_summary else (ok, fails, notes)
    rc, sha = _git(stage, "rev-parse", "--short=10", br)
    sha = sha.strip()
    if rc != 0 or not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        return ret(False, ["영상 관문: 트랙 커밋 해시를 못 읽었다: %r" % sha[:80]], [])
    d = "%s/gate_%s" % (remote_tmp.rstrip("/"), sha)            # remote_tmp 는 시험 실행 때만 바꾼다(/tmp/gatecheck)
    try:
        rc, out = sh("df -BG --output=avail /tmp | tail -1")
        m = re.search(r"(\d+)G", out)
        if rc != 0 or not m:
            return ret(False, ["영상 관문: 서버에 못 붙었다(디스크 확인 실패) — 비교 없이 병합하지 않는다\n%s" % out.strip()[:300]], [])
        free = int(m.group(1))
        if free < int(g.get("min_free_gb", 20)):
            return ret(False, ["영상 관문: 서버 /tmp 여유 %dGB < %dGB — 비교를 못 돌려 실패로 본다(디스크부터 비워라)"
                               % (free, int(g.get("min_free_gb", 20)))], [])
        say("  서버 /tmp 여유 %dGB · 폴더 %s" % (free, d))
        try:
            merged_blob = _bundle(stage, side="merged")
            main_blob = _bundle(stage, side="main") if g.get("compare_main") else None
        except FileNotFoundError as e:
            return ret(False, ["영상 관문: 비교 도구 파일이 없다: %s" % e], [])
        n = int(g.get("jobs", 6))
        g_use, job_arg, lead = g, str(n), []
        if g.get("compare_main"):
            import hashlib
            ck = hashlib.sha256(main_blob + (":jobs=%d" % n).encode()).hexdigest()[:16]
            cpath = "%s/%s.json" % (MAIN_CACHE_DIR, ck)
            base = None
            rc, txt = sh("cat %s" % cpath)
            if rc == 0 and txt.strip():
                try:
                    c = json.loads(txt)
                    if time.time() - float(c.get("t", 0)) < MAIN_CACHE_TTL and c.get("ids"):
                        base = c
                        lead.append("main 실측 캐시 재사용(%s · %d분 전) — main 비교를 다시 안 돌렸다"
                                    % (ck, int((time.time() - float(c["t"])) / 60)))
                except (ValueError, TypeError):
                    base = None
            par_ids = _pick_ids(sh, merged_blob, n, remote_tmp) if base is None and g.get("parallel_sides", True) else []
            if base is None and par_ids:
                return ret(*_measure_parallel(sh, d, ck, cpath, par_ids, main_blob, merged_blob, g, cfg,
                                              say=say, sleep=sleep, remote_tmp=remote_tmp, lead=lead))
            if base is None:
                dm = "%s/gate_main_%s" % (remote_tmp.rstrip("/"), ck)
                say("  [main] 같은 작업을 병합 전 main 코드로 먼저 잰다(기준 = max(설정, main 실측))")
                try:
                    _ok, _f, _n, parsed_m, rep_m, ran_m = _run_side(sh, dm, main_blob, str(n), g, cfg, say=say, sleep=sleep, label="main")
                finally:
                    sh("rm -rf %s" % dm)
                if ran_m and parsed_m.get("summary") is not None and parsed_m.get("jobs"):
                    g2, raised = baseline_limits(g, parsed_m, rep_m)
                    base = {"t": time.time(), "ids": [j["job"] for j in parsed_m["jobs"]], "g2": g2, "raised": raised,
                            "summary_line": parsed_m.get("summary_line", "")}
                    sh("mkdir -p %s && cat > %s" % (MAIN_CACHE_DIR, cpath),
                       stdin=json.dumps(base, ensure_ascii=False).encode("utf-8"))
                else:
                    lead.append("⚠️ main 을 못 재서 종전 절대 기준으로 판정한다(main: %s)" % ("; ".join(_f)[:200] or "요약 줄 없음"))
            if base is not None:
                g_use = dict(g)
                g_use.update(base["g2"])
                ids = list(base["ids"])
                if len(ids) < int(g.get("min_jobs_compared") or 0):
                    g_use["min_jobs_compared"] = len(ids)
                job_arg = " ".join(i for i in ids if re.fullmatch(r"[0-9A-Za-z_-]{4,64}", i))
                lead.append("기준 = max(설정, main 실측) — main 이 같은 작업 %d개에서 잰 값: %s · main 요약: %s"
                            % (len(ids), ", ".join(base.get("raised") or []) or "전부 설정값 이하", base.get("summary_line", "")[:120]))
        ok, fails, notes, parsed, _reps, _ran = _run_side(sh, d, merged_blob, job_arg, g_use, cfg, say=say, sleep=sleep,
                                                         label="병합본" if g.get("compare_main") else "비교")
        return ret(ok, fails, lead + notes, (parsed or {}).get("summary_line", ""))
    finally:
        sh("rm -rf %s" % d)


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
            # ★ServerAlive(관제 107, 2026-10-04 실측): 서버도 PC 도 연결 유지 신호가 꺼져 있어(ClientAliveInterval 0) 출력 없이
            #   10분쯤 지나면 중간 장비가 연결을 조용히 끊었다 → 서버는 끝났는데 PC 는 1시간 timeout 까지 매달렸다
            #   (sleep 330 은 331초에 답, sleep 660 은 서버가 끝난 뒤에도 답 없음). 라이브 실측이 2시간마다 124 로 죽던 뿌리.
            p = subprocess.run(["ssh", "-i", key, "-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
                                "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=6", host, cmd],
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


def _patch_rels(stage):
    """올릴 모듈 목록 — **병합본** gate_modules 의 PATCH_RELS(2026-10-05 관제 123).
    서버 도구(_tool/gate_modules.py)는 병합본이라 새 모듈(fish_tts)을 얹으려 하는데, 올리는 목록을 main 판본에서
    읽으면 그 파일이 안 올라가 병합본 tts.py 가 ImportError 로 죽었다(새 모듈을 만드는 병합마다 막히는 구조).
    병합본을 못 읽으면 main 판본 목록."""
    data = _merged_blob(stage, "tools/gate_modules.py")
    if data is None:
        return PATCH_RELS
    ns = {"__name__": "_merged_gate_modules"}
    try:
        exec(compile(data.decode("utf-8"), "gate_modules(merged)", "exec"), ns)
        return dict(ns["PATCH_RELS"])
    except Exception as e:
        print("  ! 병합본 gate_modules 목록을 못 읽어 main 목록을 쓴다: %r" % (e,))
        return PATCH_RELS


def _bundle(stage, side="merged"):
    """PATCH_DIR 묶음(side="merged": 병합본 모듈 / "main": 병합 전 main 모듈) + _tool/(병합본 도구 — 양쪽 같은 자) → tar.gz 바이트.
    ★결정적이다(2026-10-02, 카드 071): mtime·gzip 시각을 0으로 — 같은 내용이면 같은 바이트라 main 실측 캐시의 열쇠로 쓴다."""
    import gzip
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        def add(name, data):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            ti.mode = 0o644
            ti.mtime = 0
            tf.addfile(ti, io.BytesIO(data))
        for dst, rel in _patch_rels(stage).items():
            if side == "main":
                rc, data = _git_bytes(stage, "show", "HEAD:%s" % rel)
                data = data if rc == 0 else None
            else:
                data = _merged_blob(stage, rel)
            if data is not None:
                add(dst, data)
        for rel in TOOL_RELS:
            data = _merged_blob(stage, rel)
            if data is None:
                raise FileNotFoundError(rel)
            add("_tool/" + Path(rel).name, data)
    return gzip.compress(buf.getvalue(), mtime=0)


def _p(printer, s):
    printer(s)
    return s


# ★관문이 말한 것(영상·자막·소리·캡컷 report 포함)을 **파일로 남긴다**(2026-10-02 관제 070).
#   실측 10-01: 실패 사유(어느 작업·어느 칸)가 화면 출력에서 잘려(tail) 서버에서 비교를 다시 돌려야 했다(+7분×2).
#   자리: <stage 의 부모 = .tracks>/_gate_reports/<브랜치>_<시각>.txt — 트랙 폴더 옆, gitignore 안(.tracks/).
def _keep_log(stage, br, lines, now=None):
    try:
        d = Path(stage).resolve().parent / "_gate_reports"
        d.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(br).replace("track/", ""))
        f = d / ("%s_%s.txt" % (safe, ts))
        f.write_text("\n".join(str(x) for x in lines) + "\n", encoding="utf-8")
        return f
    except Exception:      # noqa: BLE001 — 보관 실패가 관문 판정을 바꾸면 안 된다
        return None


def run_video_gate(stage, br, *, printer=print, sh=None, cfg=None, env=None, sleep=time.sleep, remote_tmp="/tmp"):
    """finish 에서 부른다. GateResult(ok=False)면 병합을 버려야 한다. 말한 것은 전부 _keep_log 로 남긴다."""
    kept = []
    def _printer(s):
        kept.append(s)
        return printer(s)
    try:
        return _run_video_gate(stage, br, printer=_printer, sh=sh, cfg=cfg, env=env, sleep=sleep, remote_tmp=remote_tmp)
    finally:
        f = _keep_log(stage, br, kept)
        if f is not None:
            _p(printer, "  (관문 기록 저장: %s)" % f)


def _stage_config(stage):
    raw = _main_or_stage(stage, CONFIG_REL)
    return load_config(raw.decode("utf-8") if raw else None)


def gate_decision(stage, cfg=None):
    """이 병합에 영상 관문이 도나 — **판정은 여기 한 곳**(run_video_gate 와 track 의 락 놓기가 같이 쓴다, 2026-10-02 카드 075).
    → (오류문|None, 변경 파일, 실행?, 사유, 못 재는 파일)."""
    cfg = cfg or _stage_config(stage)
    rc, out = _git(stage, "-c", "core.quotepath=off", "diff", "--cached", "--name-only", "HEAD")
    if rc != 0:
        return out, [], True, [], []
    changed = [x.strip() for x in out.splitlines() if x.strip()]

    def app_decision():
        rel = cfg.get("app_file", "shopping_shorts/app.py")
        _, old = _git(stage, "show", "HEAD:%s" % rel)
        new = (_merged_blob(stage, rel) or b"").decode("utf-8", "replace")
        _, d = _git(stage, "diff", "--cached", "-U0", "HEAD", "--", rel)
        return app_touches_video(old, new, d, cfg)

    run, reasons, unmeasured = needs_video_gate(changed, cfg, app_decision)
    return None, changed, run, reasons, unmeasured


VIDEO_PASS_TTL = 6 * 3600


def _video_pass_key(stage, g):
    """(지문, 기억 파일) — 서버에 올리는 두 묶음(병합본·main) + 기준값의 지문. 못 만들면 (None, None)."""
    import hashlib
    try:
        h = hashlib.sha256()
        h.update(_bundle(stage, side="merged"))
        h.update(_bundle(stage, side="main"))
        h.update(json.dumps(g, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        fp = h.hexdigest()[:16]
    except Exception:  # noqa: BLE001 — 지문을 못 만들면 늘 잰다
        return None, None
    return fp, Path(stage).resolve().parent / "_gate_cache" / ("video_pass_%s.json" % fp)


def _run_video_gate(stage, br, *, printer=print, sh=None, cfg=None, env=None, sleep=time.sleep, remote_tmp="/tmp"):
    env = os.environ if env is None else env
    log = []
    say = lambda s: log.append(_p(printer, s))           # noqa: E731

    if cfg is None:
        cfg = _stage_config(stage)
    g = cfg["gate"]

    err, changed, run, reasons, unmeasured = gate_decision(stage, cfg)
    if err:
        say("❌ 영상 관문: 병합 변경 목록을 못 읽었다 — 실패로 본다\n" + err)
        return GateResult(False, False, "\n".join(log), log)
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

    # ★같은 묶음이면 결과도 같다(2026-10-03 카드 089) — 서버에 올리는 것(병합본·main 제작 라인 파일 + 관문 도구) + 기준이 같으면
    #   재시도·재finish 때 20분짜리 서버 비교를 다시 돌리지 않는다. 통과만 기억한다(실패는 늘 다시 잰다). 6시간 지나면 다시 잰다.
    vfp, vpath = _video_pass_key(stage, g)
    if vpath is not None and not (env.get("VIDEO_GATE_FRESH") or "").strip():
        try:
            c = json.loads(vpath.read_text(encoding="utf-8"))
            age = time.time() - float(c.get("t", 0))
            if age < VIDEO_PASS_TTL:
                say("판정 근거(재사용): %s" % c.get("summary_line", ""))
                say("✅ 영상 관문 통과 — 같은 묶음(%s)이 %d분 전에 통과했다. 서버 비교를 다시 안 돌렸다(VIDEO_GATE_FRESH=1 이면 다시)."
                    % (vfp, int(age / 60)))
                return GateResult(True, True, "\n".join(log), log)
        except (OSError, ValueError):
            pass
    ok, fails, notes, summary_line = _measure_and_judge(sh, stage, br, cfg, g, say=say, sleep=sleep, remote_tmp=remote_tmp,
                                                        with_summary=True)
    if ok and vpath is not None:
        try:
            vpath.parent.mkdir(parents=True, exist_ok=True)
            vpath.write_text(json.dumps({"t": time.time(), "summary_line": summary_line}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    say("판정 근거: %s" % (summary_line or "(요약 줄 없음)"))
    for f_ in fails:
        say("  ✗ " + f_)
    for n_ in notes:
        say("  · " + n_)
    say("✅ 영상 관문 통과" if ok else "❌ 영상 관문 실패")
    return GateResult(ok, True, "\n".join(log), log)
