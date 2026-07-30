"""백테스트 산출물에서 좋은 부품을 채굴해 은행에 적립한다(2026-07-30).

사장님: "은행에 나오는 것들 중 정말 훅/스토리구성/감정표현/수식부사/생동감 있는 어미 등
좋은 것 계속 뽑아서 비교할 수 있게" + "'이게 대박인 게'·'놀랍게도' 같은 놀라는 단어들이
대본 속에 있으면 추출해서 꼭 활용".

원칙:
- **고득점 대본에서만** 뽑는다. 밋밋한 대본의 표현을 적립하면 은행이 오염된다.
- 통째로 베끼면 드리프트(2026-07-26에 기존 부품은행이 꺼진 이유)라 **조각**만 뽑는다.
- 사전을 상상으로 만들지 않는다 — 실제 산출물에 나온 말만 들어간다.

사용:
    python tools/script_bank_mine.py <backtest_out.json> [...]  # 적립
    python tools/script_bank_mine.py --show                      # 은행 열람
"""
import argparse
import io
import json
import re
import sys

from shopping_shorts import script_engine, tone_score

# 이 점수 미만 대본은 채굴하지 않는다(밋밋한 표현이 은행에 들어가면 다음 버전이 오염된다).
MIN_TONE = 0.9

# 놀람·감탄(사장님 지목) — 반전의 심장. 이 말이 든 절을 통째로 뽑아 리듬까지 보존한다.
_SURPRISE = ["대박", "놀랍게도", "놀랐", "놀라", "세상에", "헐 ", "웬걸", "이럴 수가",
             "깜짝", "충격", "믿기지", "말도 안", "설마", "어머", "글쎄"]
# 감정 표현 — '좋아요' 말고 사람이 느낀 것.
_EMOTION = ["뿌듯", "속상", "짜증", "행복", "감동", "억울", "당황", "민망",
            "후회", "설레", "든든", "허무", "찝찝", "개운", "홀가분", "신나", "샘나"]


def _sentences(text):
    return [s.strip() for s in re.split(r"[.!?\n]+", text or "") if s.strip()]


def _clauses(sentence):
    """문장을 절 단위로 — 통문장을 적립하면 베끼기가 되므로 조각으로 쪼갠다.

    ⚠️ 쉼표로 쪼개지 않는다: 인용문("세상에, 이거 어디서 샀어?") 안의 쉼표에서 잘려
    '" 하며 깜짝 놀라더라구요' 같은 부서진 조각이 은행에 들어갔다(2026-07-30 실측).
    접속사 경계로만 나누고, 남은 따옴표는 걷어낸다."""
    parts = re.split(r" 근데 | 그래서 | 그런데 | 하지만 ", sentence)
    return [c.strip().strip('"“”\'') for c in parts if c.strip()]


def mine_one(rec, min_tone=MIN_TONE):
    """대본 1건 → {bucket: [조각...]}. 점수 미달이면 빈 결과."""
    text = "\n".join(n for _, n in rec.get("beats", []) if n)
    if not text:
        return {}
    if tone_score.score_conversational(text)["score"] < min_tone:
        return {}
    beats = [(r, n) for r, n in rec.get("beats", []) if n]
    out = {b: [] for b in script_engine.BUCKETS}

    # 훅 = 첫 비트의 첫 문장(그 자체가 완결된 부품).
    if beats:
        first = _sentences(beats[0][1])
        if first and 6 <= len(first[0]) <= 34:
            out["hook"].append(first[0])

    # 스토리 구성 = 역할 순서(어떤 흐름으로 짰나) 한 줄.
    roles = [r for r, _ in beats if r]
    if len(roles) >= 4:
        out["story"].append(" → ".join(roles))

    for s in _sentences(text):
        for c in _clauses(s):
            if not (6 <= len(c) <= 44):
                continue
            if any(w in c for w in _SURPRISE):
                out["surprise"].append(c)
            elif any(w in c for w in _EMOTION):
                out["emotion"].append(c)
        # 어미 — 생생한 유형(LIVE/QUESTION)일 때만 끝 어절을 뽑는다.
        if tone_score.ending_type(s) in ("LIVE", "QUESTION"):
            tail = " ".join(s.split()[-2:])
            if 3 <= len(tail) <= 18:
                out["ending"].append(tail)

    # 수식·감각 부사/형용사 — 채점기가 실제로 잡아낸 것만(상상 금지).
    out["adverb"] = tone_score.sensory_profile(text)["hits"]
    return {k: v for k, v in out.items() if v}


def merge(bank, mined, cap=60):
    """중복 없이 적립. 버킷마다 상한을 둬 프롬프트가 비대해지지 않게 한다."""
    added = {}
    for b, items in mined.items():
        cur = bank.setdefault(b, [])
        seen = set(cur)
        new = [x for x in items if x and x not in seen and not seen.add(x)]
        if new:
            cur.extend(new)
            added[b] = new
        if len(cur) > cap:                  # 최신 cap개만 유지(프롬프트 비대화 방지)
            bank[b] = cur[-cap:]
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--min-tone", type=float, default=MIN_TONE)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    bank = script_engine.load_bank()
    if a.show:
        for b in script_engine.BUCKETS:
            items = bank.get(b) or []
            print(f"\n■ {script_engine.BUCKET_LABEL[b]} ({len(items)})")
            for x in items[-15:]:
                print("   -", x)
        return

    total, mined_n = 0, 0
    for p in a.paths:
        for rec in json.load(io.open(p, encoding="utf-8")):
            total += 1
            m = mine_one(rec, min_tone=a.min_tone)
            if m:
                mined_n += 1
                merge(bank, m)
    path = script_engine.save_bank(bank)
    print(f"대본 {total}건 중 {mined_n}건 채굴(기준 tone≥{a.min_tone}) → {path}")
    for b in script_engine.BUCKETS:
        print(f"  {script_engine.BUCKET_LABEL[b]}: {len(bank.get(b) or [])}개")


if __name__ == "__main__":
    main()
