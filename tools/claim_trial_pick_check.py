"""claim_trial_video.pick_scene 꼬다리 규칙 점검 (서버 없이 로컬에서 돈다).

  py tools/claim_trial_pick_check.py

같은 소스 이어진 컷 둘(1.6초×2)로 3.6초 문장을 채울 때 '다른 소스 조각 모으기'가 아니라
'같은 소스 잇기+1.2배 늦추기'를 골라야 통과. 10-01 두피 빗 job 에서 6문장 전부 조각이 났던 꼴을 잡는다.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_pick_scene(path):
    src = io.open(path, encoding="utf-8").read()
    ns = {}
    exec(src[src.index("SLOW_MAX = 1.2"):src.index("def _hstrip")], ns)   # 서버 전용 import 를 피한다
    return ns["pick_scene"]


CASES = [
    ("같은소스 둘+늦추기가 다른소스 조각보다 먼저",
     [{"no": 1, "src": "A", "start": 0.0, "end": 1.6, "claims": ["C1"]},
      {"no": 2, "src": "A", "start": 1.6, "end": 3.2, "claims": ["C1"]},
      {"no": 3, "src": "B", "start": 0.0, "end": 1.0, "claims": ["C1"]}],
     3.6, [1, 2], "2이어붙이기+늦추기"),
    ("한 컷이 충분하면 한 컷",
     [{"no": 1, "src": "A", "start": 0.0, "end": 4.0, "claims": ["C1"]},
      {"no": 2, "src": "A", "start": 4.0, "end": 5.0, "claims": ["C1"]}],
     3.6, [1], "1한컷"),
    ("같은소스로도 1.2배까지 모자라면 그때 다른 소스",
     [{"no": 1, "src": "A", "start": 0.0, "end": 1.0, "claims": ["C1"]},
      {"no": 2, "src": "A", "start": 1.0, "end": 2.0, "claims": ["C1"]},
      {"no": 3, "src": "B", "start": 0.0, "end": 2.0, "claims": ["C1"]}],
     3.6, [3, 1, 2], "4다른소스합치기"),
]


def main():
    ps = load_pick_scene(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "claim_trial_video.py"))
    bad = 0
    for name, cuts, need, want_nos, want_how in CASES:
        nos, how, _ = ps({"lines": [0], "claims": ["C1"], "cuts": []}, [{"need": need}], cuts)
        ok = nos == want_nos and how == want_how
        bad += not ok
        print("%s %s → %s %s" % ("PASS" if ok else "FAIL", name, nos, how))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
