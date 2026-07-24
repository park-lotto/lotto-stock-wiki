"""부품은행 Phase 0 시드 — 사장님 제공 스타일 부품 + 네거티브(F5).

배포 후 프로덕션에서 1회 실행하면 큐레이션 페이지가 비어있지 않게 된다.
스타일 부품(후킹/어미/담화부사)만 리터럴로 승인 상태로 넣는다 — Gemini 불필요.
IG 3개 대본 등 '내용' 있는 소재는 페이지에서 붙여넣기(ingest)로 분해한다.

멱등: 같은 (bucket, canonical) 재삽입은 store.add_pattern_item의 dedup이 흡수
(freq만 증가). 재실행해도 중복 행은 안 생긴다.

    python -m shopping_shorts.scripts.seed_pattern_bank
"""
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts import pattern_bank

# 사장님 제공 (2026-07-21)
HOOKS = [
    "여러분 이거 때문에 진짜 깜짝 놀랐어요",
    "와 이거 진짜 대박인데요??",
    "여러분 이런 게 있었네요??",
    "와 이걸 왜 이제 알았죠??",
    "여러분 이거 저만 몰랐나요??",
    "와 이거 만든 사람 천재 아닌가요??",
    "여러분 이거 절대 하지 마세요",
    "와 저 이거 몰라서",
]
ENDINGS = [
    "~데", "~는데", "~인데", "~니", "~길래",
    "~하니깐", "~있으니깐", "~까",
    "~나요??", "~있죠??",
    "~라서", "~해서", "~며", "~여서", "~고",
    "~네요", "~더라구요", "~든요",
    "~세요", "~돼요", "~예요", "~게요",
]
ADVERBS = ["심지어", "게다가", "이게 또 대박인게", "진짜", "할 말이 없게", "놀랍게도"]

# F5 네거티브 — 요약체/AI냄새 (오늘 비교분석에서 관측)
NEGATIVES = [
    ("ending", "확인하셨어요"),
    ("ending", "너무 좋아합니다"),
    ("ending", "완벽해요"),
]


def _seed_style(store, bucket, texts):
    n = 0
    for t in texts:
        item_id = store.add_pattern_item(bucket, t)
        store.set_pattern_item_status(item_id, "approved")
        n += 1
    return n


def main():
    store = Store(DB_PATH)
    added = {
        "hook": _seed_style(store, "hook", HOOKS),
        "ending": _seed_style(store, "ending", ENDINGS),
        "adverb": _seed_style(store, "adverb", ADVERBS),
    }
    neg = 0
    for bucket, text in NEGATIVES:
        pattern_bank.ingest_negative(store, text, bucket)
        neg += 1
    print(f"seeded style: {added}, negatives: {neg}")
    print("done - 큐레이션 페이지 /pattern_bank.html 에서 확인")


if __name__ == "__main__":
    main()
