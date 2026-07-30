"""대본 엔진 버전 레지스트리 — v2 → v3 → v4로 계속 진화시키기 위한 틀(2026-07-30).

왜 필요한가:
- 프롬프트를 edit_plan에 직접 박아두면 "고쳤다"를 되돌리거나 나란히 비교할 수 없다.
  실제로 오늘 감각어를 강화하자 어미가 무너졌고(tone 1.00→0.67), 어미를 고치자 훅이
  중복됐다. 어느 변경이 어디에 기여했는지 **같은 fixture로 A/B** 할 수 있어야 한다.
- 게다가 실측 결과 **같은 입력·같은 코드로도 실행마다 tone이 ±0.4 흔들린다**(Gemini
  비결정성). 단발 비교는 노이즈다 → 백테스트가 버전×반복으로 평균을 봐야 한다.

설계:
- 엔진 = 프롬프트에 얹는 **추가 블록**들의 묶음. 기본(v2)은 빈 묶음이라 라이브 무변화.
- 새 버전은 여기 dict만 추가하면 된다. edit_plan은 engine 이름만 받는다.
- 은행(few-shot 부품)은 **백테스트 전용 은행**을 쓴다(사장님 확정 2026-07-30).
  기존 부품은행은 2026-07-26에 드리프트로 꺼졌고 그건 그대로 둔다 — 라이브 무영향.

사용:
    from shopping_shorts import script_engine
    cfg = script_engine.get("v3")
    prompt += cfg.extra_rules(bank)      # 빈 문자열이면 무주입
"""
import io
import json
import os
from pathlib import Path

# 백테스트 은행 파일(gitignore 아님 — 좋은 부품은 자산이라 커밋해 쌓는다).
BANK_PATH = Path(__file__).resolve().parents[1] / "docs" / "script_bank" / "bank.json"

# 은행 버킷 = 사장님이 지목한 축 그대로.
# surprise(2026-07-30 사장님 추가): "이게 대박인 게" · "놀랍게도" 같은 **놀람·감탄** 표현.
# 훅과 반전의 심장이라 따로 모은다 — 이게 있고 없고로 스크롤이 멈추냐가 갈린다.
BUCKETS = ("hook", "surprise", "story", "emotion", "adverb", "ending")
BUCKET_LABEL = {
    "hook": "훅(첫 문장)",
    "surprise": "놀람·감탄 표현(반전 순간)",
    "story": "스토리 구성(전개 한 줄 요약)",
    "emotion": "감정 표현",
    "adverb": "수식·감각 부사/형용사",
    "ending": "생동감 있는 어미",
}


def load_bank(path=None):
    """{bucket: [항목...]}. 파일이 없으면 빈 은행(무주입 = 회귀0)."""
    p = Path(path or BANK_PATH)
    if not p.exists():
        return {b: [] for b in BUCKETS}
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {b: [] for b in BUCKETS}
    return {b: list(d.get(b) or []) for b in BUCKETS}


def save_bank(bank, path=None):
    p = Path(path or BANK_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dump({b: list(bank.get(b) or []) for b in BUCKETS},
              io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


def _bank_block(bank, per_bucket=6, seed=0):
    """은행 → 프롬프트 few-shot 블록. 비면 빈 문자열(무주입).

    ★'뼈대'가 아니라 '양념'으로 쓴다 — 기존 부품은행이 2026-07-26에 꺼진 이유가
    통째 주입으로 대본이 은행 표현에 끌려간 드리프트였다. 그대로 베끼지 말라고 명시하고,
    매번 다른 조각이 보이도록 seed로 회전시킨다(같은 훅 반복 방지).
    """
    lines = []
    for b in BUCKETS:
        items = [x for x in (bank.get(b) or []) if x]
        if not items:
            continue
        k = len(items)
        pick = [items[(seed + i) % k] for i in range(min(per_bucket, k))]
        lines.append(f"  · {BUCKET_LABEL[b]}: " + " / ".join(f'"{x}"' for x in pick))
    if not lines:
        return ""
    return ("\n[참고 부품 — 지난 대본들에서 실제로 잘 나온 조각이다. ★뼈대가 아니라 '감각 참고'다: "
            "리듬과 말맛만 참고해 **우리 소재로 새로 써라**. 문장을 그대로 베끼면 반려된다.]\n"
            + "\n".join(lines) + "\n")


class Engine:
    def __init__(self, name, desc, use_bank=False, extra=""):
        self.name = name
        self.desc = desc
        self.use_bank = use_bank
        self._extra = extra

    def extra_rules(self, bank=None, seed=0):
        """프롬프트 끝에 붙일 이 버전만의 추가 블록."""
        out = self._extra
        if self.use_bank:
            out += _bank_block(bank if bank is not None else load_bank(), seed=seed)
        return out

    def __repr__(self):
        return f"<Engine {self.name}: {self.desc}>"


ENGINES = {
    # v2 = 오늘(2026-07-30) 라이브에 넣으려는 상태. 추가 블록 없음 = 현재 프롬프트 그대로.
    "v2": Engine("v2", "역할별 문장길이 + 어미 유형 규칙 + 감각어 4개 + 자가점검 6항목"),
    # v3 = v2 + 백테스트 은행 few-shot 주입(훅/스토리/감정/부사/어미).
    "v3": Engine("v3", "v2 + 백테스트 은행 few-shot", use_bank=True),
}

# 기본 엔진(2026-07-30 사장님 승인으로 v2 → v3). 백테스트 근거:
#   같은 fixture 30건 대 30건에서 tone<0.8(불량) 10건 → 4건, 최저 0.33 → 0.53.
#   평균차 +0.075는 반복 편차(0.19~0.23)보다 작아 단독으론 결론 불가였지만,
#   불량 건수와 최저값은 편차로 설명되지 않았다 → 은행은 상단을 올리기보다 **바닥을 올린다**.
# 되돌리려면 서버 환경변수 SCRIPT_ENGINE=v2 (코드 배포 없이 즉시 롤백).
DEFAULT = os.getenv("SCRIPT_ENGINE", "v3")


def get(name=None):
    """이름으로 엔진을 고른다. 모르는 이름이면 기본(v2) — 오타로 파이프라인을 죽이지 않는다."""
    return ENGINES.get(name or DEFAULT) or ENGINES["v2"]
