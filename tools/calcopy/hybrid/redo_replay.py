# -*- coding: utf-8 -*-
"""회원 flow 실행 기록을 다시 돌려 '고치기 안내' 진행 줄이 어떻게 바뀌는지 전/후 표로(사장님 10-26 "고객도 반려가 이해될 수 있게").

  py tools/calcopy/hybrid/redo_replay.py C:/숏템_칼카피/flowtest/ititemlog12_member

입력 = <폴더>.out(flow_dev 기록 — 옛 진행 줄) + <폴더>/job/reviews(질문마다 지난 반려 속사정).
반려마다 flow._tries·_out 을 그대로 불러 새 진행 줄을 만든다(원인 키 = flow._script_causes·_plan_causes 와 같은 사전).
옛 기록에서 '멈춤 → 다시 시도'가 있었던 자리는 다시 시도처럼 셈을 새로 한다. 영상·돈 0.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402

HEAD_S = "## 대본 검사에서 걸린 것(고쳐라)"
HEAD_P = "멈춘 이유(재료를 고쳐라):"


def _hms(s: str) -> int:
    h, m, x = (int(v) for v in s.split(":"))
    return h * 3600 + m * 60 + x + (86400 if h < 12 else 0)        # 자정 넘김(23시 → 01시)


def events(root: Path) -> list:
    """반려 한 번 = (시각, 종류, 원인 키, at)."""
    out = []
    for d in sorted((root / "job" / "reviews").iterdir()):
        if not d.is_dir() or not (d / "ask.txt").exists():
            continue
        t = (d / "ask.txt").read_text(encoding="utf-8")
        hhmmss = d.name[:6]
        sec = _hms(f"{hhmmss[:2]}:{hhmmss[2:4]}:{hhmmss[4:]}")
        if "_script_" in d.name and HEAD_S in t:
            w = t[t.index(HEAD_S) + len(HEAD_S):]
            if w.lstrip().startswith("배치 충돌"):
                out.append((sec, "conflict", ["conflict"], "script"))
            elif w.lstrip().startswith("장면 확인에서 대본·목소리"):
                out.append((sec, "conflict", ["voice_speed"], "script"))
            elif '"orig_heard"' in w[:40]:
                out.append((sec, "script", ["orig_heard"], None))
            else:
                a = {"rules": [{"kind": k, "ok": False, "why": why} for k, why in re.findall(r'"kind": "([\w:]+)", "ok": false, "why": "([^"]*)"', w)]}
                for k in ("title", "claims", "alt_scene", "source_rule", "product_cut"):
                    if re.search(rf'"{k}": \[', w):
                        a[k] = [1]
                out.append((sec, "script", F._script_causes(a) or ["form"], None))
        elif "_plan_" in d.name and (d / "answer.json").exists():
            try:
                ans = json.loads((d / "answer.json").read_text(encoding="utf-8"))
            except ValueError:
                continue
            if ans.get("ok") and not ans.get("재료"):
                continue
            over = t[t.index(HEAD_P) + len(HEAD_P):].split("\n")[0].split(" / ") if HEAD_P in t else []
            texts = [x for x in over if x.strip()] or [str(p) for p in ans.get("problems") or []]
            out.append((sec + 1, "plan", F._plan_causes(texts), None))
    return out


def old_lines(out_file: Path) -> list:
    rows, day = [], 0
    for ln in out_file.read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(ln)
        except ValueError:          # 반려 줄은 속사정 JSON 이 길어 잘려 있을 수 있다 — 앞 칸만 읽는다
            mm = re.match(r'\{"t": "([\d:]+)", "call": (\d+), "status": "(\w+)", "msg": "((?:[^"\\]|\\.)*)", "phase": "(\w+)"', ln)
            if not mm:
                continue
            j = {"t": mm.group(1), "call": int(mm.group(2)), "status": mm.group(3), "msg": json.loads('"' + mm.group(4) + '"'), "phase": mm.group(5)}
        if "call" in j and "t" in j:
            rows.append((_hms(j["t"]), j["status"], j.get("msg") or "", j.get("phase")))
    return rows


def replay(root: Path) -> list:
    old = old_lines(root.with_suffix(".out")) if root.with_suffix(".out").exists() else old_lines(Path(str(root) + ".out"))
    stops = [s for s, st_, _, _ in old if st_ == "stop"]
    st = {"sid": "r", "version": "v", "fmt": "해외원본형", "phase": "script_got", "tries": {}, "log": [], "_shown_stage": "script"}
    rows, last = [], 0
    for sec, kind, cs, at in events(root):
        if any(last < s <= sec for s in stops):                     # 옛 기록에서 멈춤 → 다시 시도 = 셈 새로
            st["tries"] = {k: v for k, v in st["tries"].items() if k == "length"}
            st.pop("redo_hist", None)
        last = sec
        ph = {"script": "script_got", "conflict": "plan_look", "plan": "plan_look"}[kind]
        st["phase"] = ph
        before = next((m for s, _, m, p in old if s >= sec - 1), "")
        try:
            if kind == "conflict":
                F._tries(st, "conflict", 2, cs, at=at)
                st["tries"]["script"] = 0
                ph2 = "script_got"
            elif kind == "script":
                F._tries(st, "script", F.LIMITS["script"], cs)
                ph2 = "script_got"
            else:
                F._tries(st, "plan", F.LIMITS["plan"], cs)
                ph2 = "plan"
            st["phase"] = ph2
            after = F._out(st, "reject" if kind != "plan" else "execute", ph2)["message"]
        except F._Stop as e:
            after = "[멈춤] " + F.member_stop(e.why, e.fix)[0] + " — " + F.member_stop(e.why, e.fix)[1]
            st["tries"] = {k: v for k, v in st["tries"].items() if k == "length"}
            st.pop("redo_hist", None)
        rows.append((sec, kind, cs, before, after))
    return rows


if __name__ == "__main__":
    for sec, kind, cs, b, a in replay(Path(sys.argv[1])):
        h, m = divmod(sec % 86400, 3600)
        print(f"{h:02d}:{m // 60:02d} {kind:8s} {','.join(cs)[:40]:40s} | 전: {b[:40]:40s} | 후: {a}")
