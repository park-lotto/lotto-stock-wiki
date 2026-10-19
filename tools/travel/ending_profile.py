# -*- coding: utf-8 -*-
"""어미 분포 대조 — 우리 대본의 말끝이 레퍼런스 채널(두유노홈디노 원본 받아쓰기 49편)과 같은 꼴인가 (관제 239).

재는 자는 shopping_shorts.travel_build.speech_profile 하나(대본 관문 speech_issues 와 같은 자 — 판단 두 벌 금지).
레퍼런스 = .tracks/칼카피숏템엔진/channel/homedesignnote/대본설명서/labels/*.json (beats[].text)
사용: py tools/travel/ending_profile.py [state.json …]   — state.json 의 대본 안들을 레퍼런스와 나란히
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from shopping_shorts.travel_build import speech_profile, lines_text, speech_issues   # noqa: E402

REF_GLOB = str(ROOT.parent / "칼카피숏템엔진" / "channel" / "homedesignnote" / "대본설명서" / "labels" / "*.json")


def reference_texts():
    out = []
    for f in sorted(glob.glob(REF_GLOB)):
        d = json.load(open(f, encoding="utf-8"))
        out.append(" ".join(b.get("text", "") for b in d.get("beats") or []))
    return [t for t in out if t.strip()]


def _short(p):
    return {"문장/편": p["sent_per"], "문장 글자": p["sent_len"], "이음/문장": p["conn_per_sent"],
            "나열(고·더니·며)": p["go_deoni"], "끝": dict(list(p["ends"].items())[:6]), "이음": dict(list(p["conns"].items())[:6])}


def main():
    ref = reference_texts()
    print("■ 레퍼런스 두유노홈디노 원본 %d편" % len(ref), json.dumps(_short(speech_profile(ref)), ensure_ascii=False))
    for p in sys.argv[1:]:
        s = json.loads(Path(p).read_text(encoding="utf-8"))
        for key in ("script", "script_story1", "script_hdn"):
            for v in (s.get(key) or {}).get("versions") or []:
                print("■ %s / %s" % (key, v.get("type")), json.dumps(_short(speech_profile(lines_text(v["lines"]))), ensure_ascii=False),
                      "| 지적:", speech_issues(v["lines"]) or "없음")


if __name__ == "__main__":
    main()
