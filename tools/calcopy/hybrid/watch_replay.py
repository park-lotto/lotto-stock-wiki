"""감시 방식 재생 비교 — 지난 시험 실행 기록(runner.log)을 시간축으로 펼쳐 두 감시 방식이 헛시간을 몇 분째에 잡는지·잘못 울리는지·오푸스를 몇 번 부르는지 잰다
(사장님 10-27 "병목·늦어지는 구간·판단이 빨라야 헛돌지 않는 구간을 확실하게 — 우리랑 고객도 같은 조건").

    py tools/calcopy/hybrid/watch_replay.py <runner.log 가 있는 폴더> [...] [--opus] [--win 180] [--par 6]

시간축 = 실행기 시간 합(오푸스 답 기다린 시간은 뺀다 — 두 방식에 같은 조건). 한 일 안의 줄은 그 일 시간에 고르게 편다.
헛시간(정답지) — 감지기와 따로, 기록 내용으로 정한다:
    반복   같은 실행기 일이 바로 앞 같은 일과 **같은 결과 줄**(숫자 초 빼고)을 낸 두 번째부터 끝까지(10-27 글자 지우기 '박힌 글자 없음' 63번)
    재검색 같은 사이트·같은 검색어를 두 번째 검색한 구간
    느림   한 일이 SLOW_SEC 를 넘긴 뒤 끝날 때까지(원본 찾기 991~1047초 같은 것)
감시 (가) 코드: 같은 결과 두 번째 = 그 일을 시작하는 순간(실제 감시는 do 입력 같음 — 기록엔 입력이 없어 결과 꼴로 대신) · 재검색 = 그 검색을 시작하는 순간 ·
     느림 = 정상 상한(LONG_OK)을 넘기는 순간 오푸스 한 번
     (나) 오푸스: win 초마다 새로 쌓인 일지를 오푸스에게 보여 주고 이상(alarm)인지 묻는다(--opus 일 때만 실제로 부른다)."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUN = re.compile(r"\[runner\] (\S+) ([\d.]+)s (ok|ERR)(.*)")
WEB = re.compile(r"\[web\] (\S+) '(.+)' 영상 주소")
NUM = re.compile(r"\d+(\.\d+)?")
SLOW_SEC = 300          # 한 일이 이보다 길면 그 뒤는 느림(원본 찾기 LONG_OK 와 같은 값)
HALF_SEC = 500          # (가) 느림 경보 시점 — 원본 찾기 예산(약 1000초)의 절반
CLAUDE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")

ASK = """너는 숏폼 영상 자동 제작의 감독이다. 아래는 실행기 일지다(위 = 지금까지 요약, 아래 = 방금 {w}초 동안 새로 쌓인 줄).
헛돌기(같은 결과를 또 만듦)·같은 검색 반복·한 일이 비정상으로 오래 걸림·결과가 계속 비어 있음·방향이 이상함 중 하나라도 **지금** 보이면 alarm=true.
정상 진행이면 false. 확실하지 않으면 false. JSON 하나만: {{"alarm": true|false, "what": "한 줄"}}

## 지금까지(실행기 시간 {t0:.0f}초까지, 일 이름·초만)
{past}

## 방금 새로 쌓인 일지({t0:.0f}~{t1:.0f}초)
{now}"""


def timeline(log: Path) -> tuple[list[dict], list[dict]]:
    """일(block)과 줄(line, 시각 t) 목록."""
    blocks, lines, pend, t = [], [], [], 0.0
    for ln in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RUN.search(ln)
        if not m:
            pend.append(ln)
            continue
        cmd, sec = m.group(1), float(m.group(2))
        body = [x for x in pend if not x.startswith("[runner]")]
        b = {"cmd": cmd, "sec": sec, "ok": m.group(3), "rest": m.group(4).strip(), "t0": t, "t1": t + sec,
             "body": any(not WEB.search(x) for x in body), "sig": cmd + "|" + NUM.sub("#", "\n".join(x for x in body if not WEB.search(x))) + "|" + NUM.sub("#", m.group(4))}
        n = len(body)
        for k, x in enumerate(body):
            lines.append({"t": t + sec * (k + 1) / (n + 1), "text": x[:220]})
        lines.append({"t": t + sec, "text": ln[:220]})
        blocks.append(b)
        t += sec
        pend = []
    return blocks, lines


LONG_OK = {"render": 900, "plan": 420, "clean_text": 600, "origin_foreign": 300, "bench": 120, "origin_get": 180, "check": 600}   # run_audit 와 같은 값(정상 상한)
EMPTY_CLEAN = re.compile(r"VMake 0회 .*박힌 글자 없음")


def waste(blocks: list[dict], lines: list[dict]) -> list[dict]:
    """정답지 — 감지기(같은 결과 꼴)와 다른 근거로: ① 지울 글자가 없다는 결과를 또 받은 글자 지우기(내용) ② 같은 검색어 재검색(내용)
    ③ 한 일이 정상 상한(LONG_OK)을 넘긴 뒤(병목). 소재 2편 함께 찾기로 두 번 도는 일(bench·origin_get…)은 헛시간이 아니다."""
    out, empty = [], 0
    for b in blocks:
        body = " / ".join(l["text"] for l in lines if b["t0"] < l["t"] <= b["t1"])
        if b["cmd"] == "clean_text" and EMPTY_CLEAN.search(body):
            empty += 1
            if empty >= 2:
                out.append({"kind": "반복", "cmd": b["cmd"], "t0": b["t0"], "t1": b["t1"]})
        lim = LONG_OK.get(b["cmd"], 180)
        if b["sec"] > lim:
            out.append({"kind": "느림", "cmd": b["cmd"], "t0": b["t0"] + lim, "t1": b["t1"]})
    seen = set()
    for ln in lines:
        w = WEB.search(ln["text"])
        if w:
            k = (w.group(1), w.group(2))
            if k in seen:
                b = next(x for x in blocks if x["t0"] <= ln["t"] <= x["t1"])
                out.append({"kind": "재검색", "cmd": b["cmd"], "t0": ln["t"], "t1": ln["t"] + b["sec"] / 8})
            seen.add(k)
    out.sort(key=lambda w: w["t0"])
    merged = []
    for w in out:
        m = merged[-1] if merged else None
        if m and m["kind"] == w["kind"] and m["cmd"] == w["cmd"] and w["t0"] <= m["t1"] + 120:
            m["t1"] = max(m["t1"], w["t1"])
            m["n"] = m.get("n", 1) + 1
        else:
            merged.append(dict(w))
    return merged


def code_alarms(blocks: list[dict], lines: list[dict]) -> list[dict]:
    """(가) — 같은 입력 두 번째(일 시작 순간) · 재검색(검색 시작 순간) · 예산 절반."""
    al, last, seen = [], {}, set()
    for b in blocks:
        p = last.get(b["cmd"])
        if p and p["ok"] == "ok" and p["sig"] == b["sig"] and b["sec"] > 1 and b["body"]:   # 결과 줄이 없는 일은 입력 같음을 기록으로 알 수 없다(실제 감시는 do 입력으로 잰다)
            al.append({"t": b["t0"], "why": f"같은 결과 두 번째 {b['cmd']}"})
        last[b["cmd"]] = b
        lim = LONG_OK.get(b["cmd"], 180)
        if b["sec"] > lim:
            al.append({"t": b["t0"] + lim, "why": f"{b['cmd']} 정상 상한 {lim}초 넘김"})
    for ln in lines:
        w = WEB.search(ln["text"])
        if w:
            k = (w.group(1), w.group(2))
            if k in seen:
                al.append({"t": ln["t"], "why": f"재검색 {k[1][:30]}"})
            seen.add(k)
    return sorted(al, key=lambda a: a["t"])


def _ask(prompt: str) -> dict:
    r = subprocess.run([CLAUDE, "-p", "--model", "opus", "--output-format", "json"], input=prompt, capture_output=True,
                       text=True, encoding="utf-8", timeout=300)
    try:
        txt = json.loads(r.stdout).get("result") or ""
        return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
    except Exception as e:  # noqa: BLE001 — 못 읽은 답은 이유째 남긴다
        return {"alarm": False, "what": f"답 못 읽음 {type(e).__name__}: {r.stdout[:120]} {r.stderr[:120]}"}


def opus_alarms(blocks: list[dict], lines: list[dict], win: float, par: int) -> list[dict]:
    end = blocks[-1]["t1"] if blocks else 0
    jobs = []
    t = 0.0
    while t < end:
        t1 = t + win
        past = " · ".join(f"{b['cmd']} {b['sec']:.0f}초{'' if b['ok'] == 'ok' else ' ERR'}" for b in blocks if b["t1"] <= t)[-3000:]
        now = "\n".join(l["text"] for l in lines if t <= l["t"] < t1)[-6000:] or "(새 줄 없음 — 일이 아직 도는 중)"
        jobs.append((t1, ASK.format(w=int(win), t0=t, t1=t1, past=past or "없음", now=now)))
        t = t1
    with ThreadPoolExecutor(par) as ex:
        res = list(ex.map(lambda j: _ask(j[1]), jobs))
    return [{"t": t1, "why": str(a.get("what"))[:120], "alarm": bool(a.get("alarm"))} for (t1, _), a in zip(jobs, res)], len(jobs)


def score(ws: list[dict], al: list[dict]) -> dict:
    hits, lat = 0, []
    for w in ws:
        a = next((a for a in al if w["t0"] - 1 <= a["t"] <= w["t1"] + 1), None)
        if a:
            hits += 1
            lat.append(a["t"] - w["t0"])
    false = [a for a in al if not any(w["t0"] - 1 <= a["t"] <= w["t1"] + 1 for w in ws)]
    wasted = sum(w["t1"] - w["t0"] for w in ws)
    saved = sum(max(0.0, w["t1"] - a["t"]) for w in ws for a in [next((a for a in al if w["t0"] - 1 <= a["t"] <= w["t1"] + 1), None)] if a)
    return {"잡음": f"{hits}/{len(ws)}", "평균 늦음(초)": round(sum(lat) / len(lat)) if lat else None, "잘못 울림": len(false),
            "헛시간(초)": round(wasted), "잡았으면 아낀 초": round(saved), "false": [f"{a['t']:.0f}초 {a['why']}" for a in false[:6]]}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--opus", action="store_true")
    ap.add_argument("--win", type=float, default=180)
    ap.add_argument("--par", type=int, default=6)
    a = ap.parse_args(argv)
    for d in a.dirs:
        for log in sorted(Path(d).rglob("runner.log")):
            blocks, lines = timeline(log)
            ws = waste(blocks, lines)
            print(f"■ {log.parent}  실행기 시간 {blocks[-1]['t1'] / 60:.1f}분 · 일 {len(blocks)}개")
            for w in ws:
                print(f"   헛시간 {w['kind']:3} {w['cmd']:15} {w['t0'] / 60:6.1f}~{w['t1'] / 60:6.1f}분 ({(w['t1'] - w['t0']) / 60:.1f}분{', ' + str(w['n']) + '번' if w.get('n') else ''})")
            ca = code_alarms(blocks, lines)
            print(f"   (가) 코드 감지 + 오푸스 판단: 오푸스 부름 {len(ca)}번 · " + json.dumps(score(ws, ca), ensure_ascii=False))
            if a.opus:
                oa, n = opus_alarms(blocks, lines, a.win, a.par)
                on = [x for x in oa if x["alarm"]]
                print(f"   (나) 오푸스 {a.win:.0f}초마다: 오푸스 부름 {n}번 · " + json.dumps(score(ws, on), ensure_ascii=False))
                (log.parent / "watch_replay_opus.json").write_text(json.dumps(oa, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
