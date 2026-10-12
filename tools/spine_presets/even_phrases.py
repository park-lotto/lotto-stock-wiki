"""같은 말투 계열(이븐쇼핑 꼴) 261편 → **자리별 관용구 사전** (2026-09-21 사장님).

사장님: "최근딱봤을때는 / 이것도 다른것 조합안되나 이자리에 비슷한거 /
        충격적포인트 = 진짜 미친포인트 이런것처럼 각 단어들 조합도 갈아끼울수있게"

★왜 채널 하나가 아니라 계열 261편인가(실측):
  이븐쇼핑 22편만 보면 `진짜 충격적인 포인트는`이 22회로 **한 가지뿐**이라 갈아끼울 게 없다.
  같은 말투 표지(`말도 안 되`·`포인트는`·`이건 바로`·`천재`)를 가진 유튜브 261편으로 넓히면
  같은 자리에 쓰는 변형이 드러난다:
    심지어 97 · 진짜 미친 포인트는 38 · 근데 진짜 충격적인 포인트는 33 ·
    근데 진짜 미친 포인트는 23 · 진짜 충격적인 포인트는 20 · 충격적인 건 14 …
  말투가 같으므로 서로 바꿔 껴도 결이 안 깨진다 — **채널이 아니라 말투가 기준이다.**

★재료는 **둘 다** 쓴다(2026-09-21 사장님 "이건 이미 우리가 스파인 많이 뽑았자나 훑어봐"):
  ① 코퍼스 계열 261편  ② **등록된 원문형 스파인 368개 = 칸 2,448개·10만 자**
  스파인 쪽이 더 풍부했다(실측): 심지어 61 · 게다가 23 · 진짜 미친 포인트는 11 ·
  미친 포인트 10 · 근데 진짜 충격적인 포인트는 7 · 대박인 건 7 · 거기다 4 …
  코퍼스만 보면 `심지어 97 / 진짜 미친 포인트는 38`처럼 몇 가지뿐이다.

쓰기(서버):
  python3 tools/spine_presets/even_phrases.py /tmp/hits_cls_all.json /tmp/even_phrases.json       --db /home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db
"""
import json
import re
import sys
import collections

# 이 말투 계열인가 — 채널 이름이 아니라 **문장 표지**로 고른다
FAMILY = re.compile(r"말도 안 ?되|진짜 (?:충격적인|미친) ?포인트|이건 바로|천재")

# 자리별로 서로 바꿔 낄 수 있는 관용구. 최소 등장 횟수를 넘긴 것만 사전에 넣는다
# (1~2회짜리는 그 영상 하나의 표현이라 일반화하면 안 된다 — 중복본 함정과 같은 이유).
SLOT_PATTERNS = {
    "반전도입": (r"(?:근데 )?(?:진짜 )?(?:충격적인|미친|대박인|놀라운|소름돋는)[^\s]{0,3} ?"
                r"(?:포인트는?|건|점은?)|심지어|게다가|거기다|충격적인 건|더 놀라운 건"),
    "고조도입": (r"이(?:게| )?(?:진짜 )?말도 안 ?되는게|이게 미친 포인트인게|"
                r"더 (?:대박|놀라운|미친)인? ?건|말도 안 ?되는|정신 나갈 ?듯?한?|정신 나간"),
    "공개":     r"이건 바로|이게 바로|그게 바로",
    "미끼도입": r"최근 딱 봤을 때는?|최근 이미|최근|언뜻 봤을 [땐때]|딱 봤을 때는?|누가 봐도",
    "평범수식": (r"평범한|평범해 보이는|도저히 용도를 알 ?[기수]? ?(?:힘든|없는|어려운)|"
                r"그냥 보면|무슨"),
    "성과":     r"때돈|떼돈|돈 ?방석|대폭발|난리(?:가 났|났)|품절|무너져 내렸",
    "마무리":   r"이러니 난리|더 이상 (?:안|필요)|끝났다는 거|하네요",
}

MIN_HITS = 3          # 3회 미만은 일반화하지 않는다


def spine_text(db):
    """등록된 원문형 스파인 368개의 칸 원문 — 이미 우리가 뽑아 둔 재료다."""
    import sqlite3
    out = []
    try:
        c = sqlite3.connect(db)
        for (tj,) in c.execute("SELECT templates_json FROM spine"):
            try:
                o = json.loads(tj or "{}").get("_origin")
            except Exception:              # noqa: BLE001
                continue
            if isinstance(o, dict) and o.get("cells"):
                out.append(" ".join((x.get("text") or "") for x in o["cells"]))
    except Exception as e:                 # noqa: BLE001 — DB 없으면 코퍼스만
        print("스파인 읽기 건너뜀: %s" % str(e)[:80])
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    db = ""
    if "--db" in sys.argv:
        db = sys.argv[sys.argv.index("--db") + 1]
    rows = json.load(open(src, encoding="utf-8"))
    fam = [r for r in rows
           if r.get("platform") == "youtube" and FAMILY.search(r.get("text") or "")]
    sp = spine_text(db) if db else []
    print("재료: 코퍼스 계열 %d편 + 등록 스파인 %d개" % (len(fam), len(sp)))
    text = " ".join([r.get("text") or "" for r in fam] + sp)

    out = {"family_videos": len(fam), "spines": len(sp),
           "min_hits": MIN_HITS, "slots": {}}
    for slot, pat in SLOT_PATTERNS.items():
        c = collections.Counter(re.sub(r"\s+", " ", m.group(0)).strip()
                                for m in re.finditer(pat, text))
        keep = [{"text": k, "n": v} for k, v in c.most_common() if v >= MIN_HITS]
        out["slots"][slot] = keep
        print("  %-8s %2d가지 (총 %d회)" % (slot, len(keep), sum(x["n"] for x in keep)))

    n = 1
    for v in out["slots"].values():
        n *= max(1, len(v))
    out["combinations"] = n
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("계열 %d편 · 관용구 조합 %s가지" % (len(fam), format(n, ",")))


if __name__ == "__main__":
    main()
