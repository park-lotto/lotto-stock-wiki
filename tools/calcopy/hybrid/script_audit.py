"""하이브리드 대본 점검 — 잇썸홈판은 두유노홈디노 설명서, 재미썸홈판은 이븐쇼핑 설명서의 같은 자로 잰다(판단 주인 = engine/script_frame).

    PYTHONUTF8=1 py tools/calcopy/hybrid/script_audit.py <대본.json> [<대본.json> …]

대본.json = 하이브리드 v2(lines[{id|slot, tts|text, facts?, point?, answer_at?}]). 원음(O·kind=orig) 줄은 빼고 TTS 줄만 잰다.
판 구분 = 경로에 '재미썸홈' 이 있으면 이븐쇼핑, 아니면 두유노. 여기서 기준을 새로 정하지 않는다 — 설명서·points.json 을 그대로 부른다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import script_frame as SF  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FRAME = {"itssum": ROOT / "channel/homedesignnote/대본설명서/script_frame.json",
         "jaemi": ROOT / "channel/evenshopping/대본설명서/points.json"}


def tts_lines(d: dict) -> list[dict]:
    out = []
    for l in d.get("lines") or []:
        if l.get("kind") == "orig" or l.get("id") == "O":
            continue
        t = l.get("tts") or l.get("text") or ""
        if t:
            out.append({**l, "text": t})
    return out


def audit(path: Path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    kind = "jaemi" if "재미썸홈" in str(path) else "itssum"
    lines = tts_lines(d)
    text = " ".join(l["text"] for l in lines)
    res = {"file": str(path), "kind": kind, "n_lines": len(lines), "chars": len(text.replace(" ", ""))}
    if kind == "itssum":
        frame = json.loads(FRAME["itssum"].read_text(encoding="utf-8"))
        j = SF.judge_like([l["text"] for l in lines], frame)
        res["judge"] = {"score": round(j["score"], 3), "pass": j["pass"], "hard_fail": j["hard_fail"],
                        "bad_parts": [k for k, v in j["parts"].items() if not v.get("ok")]}
        f = SF.features(text)
        res["endings"] = [SF.ending_of(s) for s in SF.sentences(text)]
        res["features"] = {k: f[k] for k in ("sent_len_mean", "connect_per_sent", "person1_ratio", "polite_ratio")}
        pc = SF.load_points(FRAME["itssum"])
    else:
        pc = json.loads(FRAME["jaemi"].read_text(encoding="utf-8"))
        res["polite"] = sum(1 for l in lines if l["text"].rstrip(" .,").endswith(("요", "니다")))
    pcr = SF.points_check(lines, pc)
    if pcr is not None:
        res["points"] = {"ok": pcr["ok"], "why": pcr["why"], "bad": pcr["bad"], "wow": [w for _, w in pcr["wow"]], "ing": pcr["ing"]}
    res["narr"] = [SF.narr_rules(l["text"]) for l in lines]
    return res


def main():
    for p in sys.argv[1:]:
        print(json.dumps(audit(Path(p)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
