"""스카이베이 경포 3편 시리즈 콘티(shots.json) — Veo 없이 공식 사진·손님 사진으로(사장님 2026-10-22 "veo 안 쓰고").

    py tools/travel/work_skybay/make_eps.py        → ep1/ ep2/ ep3/ 에 shots.json + 숙소 자료 복사

대본 = 2026-10-20 세션에서 쓴 두유노식 3편("~하지 마세요" 첫 줄 · 친구 전언 "~대요").
근거 숫자 = insights.json(후기 7,908건 분석)의 항목을 글자 그대로 찾아 넣는다 — 없으면 멈춘다(지어낸 숫자 금지).
사진 번호 = state.json judged 의 no(1~24) → photos/(no-1).jpg
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ins = json.loads((HERE / "insights.json").read_text(encoding="utf-8"))
ITEMS = {x["item"]: x["count"] for c, it in ins.items() if not c.startswith("_") for x in it}


def P(no):
    return str(HERE / "photos" / ("%02d.jpg" % (no - 1)))


def ev(item):
    if item not in ITEMS:
        sys.exit("후기 분석에 없는 근거: " + item)
    return {"item": item, "count": ITEMS[item]}


EPS = {
    1: [  # 인피니티풀
        {"line": "강릉 가서 바다만 보고 오지 마세요, 친구가 호텔 20층 수영장에서 바다 위에 둥둥 떠 있는 기분이었다더라고요.",
         "emph": "둥둥", "ev": "20층 인피니티풀에서 보는 동해 바다",
         "frames": [{"photo": P(11)}, {"photo": P(1)}, {"photo": P(5)}, {"photo": "g0"}],
         "fx": {"chips": ["20층 인피니티풀"]},
         "comment": {"keys": ["인피니티", "20층"], "topic": "인피니티풀과 그 너머 바다"}},
        {"line": "바다랑 맞닿은 인피니티풀이 겨울에도 온수라서, 찬바람 맞으면서 따뜻한 물에 떠 있으니까 외국 온 것처럼 사진이 나온대요.",
         "emph": "온수", "ev": "겨울에도 따뜻한 온수 인피니티풀",
         "frames": [{"photo": P(6)}, {"photo": "g1"}, {"compare": [P(5), "g0"]}],
         "fx": {"chips": ["겨울에도 온수"]},
         "comment": {"keys": ["온수"], "topic": "온수 인피니티풀 물과 그 너머 바다", "must": ["풀", "수영장"]}},
        {"line": "밤엔 불빛 켜진 야경이 미쳤고, 사람 없이 즐기려면 아침 7시 개장 때 가면 거의 전세 낸 기분이래요.",
         "emph": "7시", "ev": "수영장은 아침 7시 개장 때가 제일 한산해요",
         "frames": [{"photo": "g0"}, {"photo": P(7)}, {"photo": "g1"}],
         "fx": {"chips": ["아침 7시 개장 때 한산"]},
         "comment": {"keys": ["야경", "밤에"], "topic": "밤에 조명이 켜진 인피니티풀 야경", "must": ["풀", "수영장"]}},
        {"line": "대신 투숙객도 수영장은 따로 결제해야 하고요, 다음 편엔 이 호텔 방 고르는 법 알려 드릴게요.",
         "emph": "결제", "ev": "인피니티풀은 투숙객도 유료, 한 번 결제하면 계속 이용",
         "frames": [{"photo": P(12)}, {"photo": P(5)}, {"photo": P(15)}],   # 방 사진은 '다음 편엔 방' 말할 때(마지막 3분의 1)
         "fx": {"strike": "투숙객 무료", "to": "투숙객도 유료"},
         "comment": {"keys": ["유료", "결제"], "topic": "수영장 입구나 이용 안내", "must": ["풀", "수영장"]}},
    ],
}


def main():
    for ep, rows in EPS.items():
        d = HERE / ("ep%d" % ep)
        d.mkdir(exist_ok=True)
        for f in ("state.json", "insights.json"):
            shutil.copy(HERE / f, d / f)
        shots = []
        for n, r in enumerate(rows, 1):
            w = [x for x in r["line"].split() if r["emph"] in x]
            if not w:
                sys.exit("%d편 %d줄 강조 단어가 대본에 없다: %s" % (ep, n, r["emph"]))
            for f in r["frames"]:
                for p in ([f.get("photo"), f.get("fade_to")] + f.get("compare", [])):
                    if p and not p.startswith("g") and not Path(p).exists():
                        sys.exit("사진 없음: " + p)
            shots.append({"n": n, "line": r["line"], "plan": {"emph": r["emph"]}, "evidence": ev(r["ev"]),
                          "frames": r["frames"], "fx": r["fx"], "comment": r["comment"]})
        (d / "shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding="utf-8")
        print("%d편 %d줄 → %s" % (ep, len(shots), d / "shots.json"))


if __name__ == "__main__":
    main()
