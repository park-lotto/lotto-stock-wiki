# 연출의 주인: 어떤 장면이 어떤 모션을 쓸지 여기서만 정한다. 같은 모션은 전부 한 바퀴 돌기 전에 다시 나오지 않는다.
import math, random
from .settings import CFG
STAGES = ["push", "pull", "window", "slant", "slant_r", "strips", "iris", "tilt", "cinema", "duo", "offset"]
MOVES = ["in", "out", "rise", "sink"]
NUMBERS = ["orbit", "side", "gauge", "slam", "flood", "echo"]
BARS = ["bar", "lollipop", "blocks", "rail", "rings", "bubble"]
TYPES = ["rise", "slam", "drop", "spread", "type", "wipe"]
LABELS = ["chain", "list", "flow"]
VERSUS = ["panels", "diagonal", "stacked"]
QUOTES = ["center", "rail"]
CUTS = list(CFG["cuts"])   # 판마다 다르다(channel.json cuts)
WIPES = ["diagonal", "blinds", "split"]
BUMPERS = ["lines", "shutter", "rings"]
NOTES = ["leader", "slash", "ribbon", "block"]
TINTS = ["base", "navy", "wine", "teal"]
BEAT_SEC = CFG["beat_sec"]   # 한 사진 샷 안에서 무대를 바꾸는 간격

class Bag:
    """한 바퀴를 다 쓰기 전에 같은 것을 다시 꺼내지 않는 주머니."""
    def __init__(self, items, seed):
        self.items, self.rng, self.now, self.recent = list(items), random.Random(seed), [], []
    def take(self, ok=None):
        if not self.now:   # 새 바퀴의 앞쪽에는 방금 쓴 것을 두지 않는다(꺼내는 쪽이 목록 끝)
            fresh = self.items[:]; self.rng.shuffle(fresh); self.now = [x for x in fresh if x in self.recent] + [x for x in fresh if x not in self.recent]
        order = sorted(range(len(self.now) - 1, -1, -1), key=lambda i: self.now[i] in self.recent)   # 조건이 좁은 샷도 방금 쓴 것은 피한다
        for i in order:
            if ok is None or ok(self.now[i]):
                x = self.now.pop(i); self.recent = (self.recent + [x])[-min(3, len(self.items) - 1):]; return x
        x = next(x for x in self.items if ok(x) and x not in self.recent[-1:]) if any(ok(x) and x not in self.recent[-1:] for x in self.items) else next(x for x in self.items if ok(x))
        self.recent = (self.recent + [x])[-min(3, len(self.items) - 1):]; return x

def bar_fits(s):
    vals = [it[1] for it in s["items"]]
    if min(vals) < 0: return ["bar", "rail"]
    if s.get("ref"): return ["bar", "lollipop", "blocks", "rail"]
    if len(vals) > 4: return ["rail", "bar"]
    if s.get("orient") == "h": return ["rail", "bar", "lollipop", "blocks"]
    return BARS

def direct(tl):
    """샷마다 모션을 배정한다. 같은 대본이면 언제나 같은 결과(구간 렌더가 서로 어긋나지 않게)."""
    if tl.get("directed"): return tl
    bags = {k: Bag(v, i * 37 + 5) for i, (k, v) in enumerate(dict(stage=STAGES, move=MOVES, number=NUMBERS, bar=BARS, type=TYPES, label=LABELS, versus=VERSUS,
                                                                  quote=QUOTES, cut=CUTS, wipe=WIPES, bumper=BUMPERS, note=NOTES, tint=TINTS).items())}
    for j, s in enumerate(tl["shots"]):
        s["cut"] = "none" if j == 0 else bags["cut"].take(); s["tint"] = bags["tint"].take(); ty = s["type"]; T = s["t1"] - s["t0"]
        if ty in ("stock", "ai"):
            n = max(1, math.ceil(T / BEAT_SEC)); s["beats"] = [(T * b / n, bags["stage"].take(lambda x: not s.get("big") or x in ("push", "pull")), bags["move"].take(), bags["cut"].take() if b else None) for b in range(n)]
            s["note"] = bags["note"].take()
        elif ty == "bignum": s["look"] = bags["number"].take()
        elif ty == "bar":
            fits = bar_fits(s); s["look"] = bags["bar"].take(lambda x: x in fits)
            if T > 2 * BEAT_SEC:   # 다 찬 그래프가 오래 머물면 도중에 다른 모양으로 바꿔 보여 준다
                n = math.ceil(T / (2 * BEAT_SEC)); s["swaps"] = [(T * b / n, bags["bar"].take(lambda x: x in fits), bags["cut"].take()) for b in range(1, n)]
        elif ty == "typo": s["modes"] = [bags["type"].take() for _ in s["items"]]
        elif ty == "labels": s["look"] = bags["label"].take()
        elif ty == "vs":
            s["look"] = bags["versus"].take()
            if T > 2 * BEAT_SEC: s["swaps"] = [(T / 2, bags["versus"].take(), bags["cut"].take())]
        elif ty == "quote": s["look"] = bags["quote"].take()
    for e in tl["events"]:
        if e["kind"] == "wipe": e["look"] = bags["wipe"].take()
        elif e["kind"].startswith("bumper"): e["look"] = bags["bumper"].take()
    tl["directed"] = True
    return tl
