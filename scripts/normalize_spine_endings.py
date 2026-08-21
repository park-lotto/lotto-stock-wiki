# -*- coding: utf-8 -*-
"""스파인 문장의 **어미만** 플랫폼 문체로 통일한다 — 파일로 뽑고, 반영은 따로.

왜(2026-08-21 사장님): 한 대본 안에서 '~음 / ~요 / ~니다 / ~다 / 명사형'이 뒤섞여 나온다.
  실측 예(오용형): 활용법(명사) → 났는데(연결) → 펀칭기였음(~음) → 한다는 거(명사) → 만들기(명사).
  템플릿 문장들의 어미가 애초에 제각각이라 그렇다.

문체(사장님 확정): 인스타 = ~요체(말하듯) / 유튜브 = ~음·~다(자막체).

지켜야 할 것 — 어기면 그 문장은 **원본을 그대로 둔다**(clean에서 되돌림):
  · 슬롯 {…}은 이름·개수 그대로. 하나라도 바뀌면 조립이 깨진다.
  · 고조어('심지어' 등) 개수 그대로. script_gate가 '정확히 1회'를 본다.
  · 슬롯 **바로 뒤에 조사를 붙이지 않는다**. 값이 완결 문장이라 '높인다마저'가 된다
    (2026-08-21 실사고 — 그 형태 15개를 걷어냈다. 다시 만들면 안 된다).
  · 의미·길이는 그대로. 어미만 바꾼다.

쓰는 법:
  py scripts/normalize_spine_endings.py --from-json <styles.json>
  → out/spine_endings.json / .md
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shopping_shorts.edit_plan import _vault_call

SLOT = re.compile(r"\{([^}]+)\}")
ESC = re.compile(r"심지어|더 대박인 건|더 놀라운 건|더 소름 돋는")
PLAT_FIX = {"단정 명령형": "ig", "가족갈등 반전형": "ig", "물건 발견형": "ig"}
# 값이 완결 문장으로 들어오는 슬롯 — 뒤에 조사를 붙이면 비문이 된다
SENT_SLOTS = {"효능", "효능2", "효능3", "불편함", "차별점", "사용법", "효과",
              "문제", "증거", "비결", "후기", "상황", "계기", "적용대상들"}

SCHEMA = {"type": "object",
          "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
          "required": ["lines"]}

STYLE_RULE = {
    "ig": ("~요체(말하듯 친근하게)",
           "문장 끝을 '~어요/~아요/~거든요/~더라고요/~예요'처럼 **말하는 톤**으로 맞춘다. "
           "'~음/~함/~다'로 끝내지 말고, 명사로 끝내지도 마라(활용법·만들기 → 활용해요·만들어요)."),
    "yt": ("~음·~다(자막체, 단정)",
           "문장 끝을 '~음/~함/~다/~하는 중'처럼 **짧고 단정한 자막 톤**으로 맞춘다. "
           "'~요/~니다'로 끝내지 마라. 명사로 끝내지도 마라(활용법 → 활용법임)."),
}


def platform(sp):
    n = (sp.get("name") or "").strip()
    if n in PLAT_FIX:
        return PLAT_FIX[n]
    s = n + (sp.get("situation_type") or "")
    if "유튜브" in s:
        return "yt"
    if "인스타" in s or "릴스" in s:
        return "ig"
    return "ig"


# 어미를 건드리면 안 되는 칸 — 제목은 명사형이 정상이다.
SKIP_ROLES = {"title"}


def _ends_with_slot(t):
    """문장이 빈칸으로 끝나나 — 그러면 문체를 정하는 건 빈칸 값이지 템플릿이 아니다.

    이런 줄의 앞부분은 연결어미여야 하는데 종결어미로 바꾸면 문장이 끊긴다
    (2026-08-21 시범: "따로 있었는데 {용도끝}" → "따로 있었음 {용도끝}").
    """
    return bool(re.search(r"\}[\s.!?”]*$", (t or "").strip()))


def clean(new_lines, old_lines):
    """규칙을 어긴 줄은 **원본으로 되돌린다**. 프롬프트만 믿지 않는다."""
    out, kept, reverted = [], 0, []
    for i, old in enumerate(old_lines):
        new = re.sub(r"\s+", " ", str((new_lines or [""] * len(old_lines))[i]
                                      if i < len(new_lines or []) else "")).strip()
        why = ""
        if not new:
            why = "빈 응답"
        elif _ends_with_slot(old):
            why = "빈칸으로 끝나는 줄(문체는 빈칸 값이 정한다)"
        elif re.sub(r"[.!?]+$", "", new) != new and re.sub(r"[.!?]+$", "", old) == old:
            why = "원본에 없던 문장부호를 붙임"
        elif sorted(SLOT.findall(new)) != sorted(SLOT.findall(old)):
            why = "슬롯이 바뀜"
        elif len(ESC.findall(new)) != len(ESC.findall(old)):
            why = "고조어 개수가 바뀜"
        elif abs(len(new) - len(old)) > max(14, len(old) * 0.5):
            why = "길이가 크게 달라짐"
        else:
            for m in SLOT.finditer(new):
                if m.group(1) in SENT_SLOTS:
                    tail = new[m.end():]
                    if tail and not tail.startswith((" ", ".", "!", "?", "\u201d")):
                        why = "슬롯 뒤에 조사가 붙음"
                        break
        if why:
            out.append(old); reverted.append((old, why))
        else:
            out.append(new); kept += (new != old)
    return out, kept, reverted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", required=True, dest="from_json")
    ap.add_argument("--spine", type=int, default=None)
    a = ap.parse_args()

    d = json.load(open(a.from_json, encoding="utf-8"))
    spines = [x for x in (d.get("styles") or [])
              if x.get("templates") and (not a.spine or int(x["id"]) == a.spine)]
    print("스파인 %d개" % len(spines))

    result, report = {}, []
    for sp in spines:
        plat = platform(sp)
        label, rule = STYLE_RULE[plat]
        result[str(sp["id"])] = {"name": sp["name"], "platform": plat, "roles": {}}
        report.append("\n## [%s] %s — %s\n" % (sp["id"], sp["name"], label))
        for role, arr in (sp["templates"] or {}).items():
            old = list(arr or [])
            if not old or role in SKIP_ROLES:
                continue
            prompt = (
                "너는 한국 숏폼 대본 편집자다. 아래 문장들의 **어미(문장 끝)만** 고쳐 문체를 통일한다.\n\n"
                "[목표 문체] %s\n%s\n\n"
                "[반드시 지킬 것]\n"
                "· 중괄호 빈칸 {…}은 **이름도 개수도 그대로** 둔다. 새로 만들지도, 없애지도 마라.\n"
                "· 빈칸 **바로 뒤에 조사를 붙이지 마라**(빈칸에는 완결된 문장이 들어와서 "
                "'높인다마저'처럼 말이 안 되게 된다). 빈칸 뒤에는 공백이나 문장부호만 온다.\n"
                "· '심지어' 같은 고조 표현의 **개수를 바꾸지 마라**.\n"
                "· 뜻과 길이는 그대로. 어미만 바꾼다. 이미 목표 문체면 그대로 두어라.\n"
                "· 빈칸으로 **끝나는** 문장은 그대로 두어라(그 문장의 끝은 빈칸 값이 정한다).\n"
                "· 원본에 없던 마침표·느낌표를 새로 붙이지 마라.\n"
                "· 입력과 **같은 개수·같은 순서**로 돌려준다.\n\n"
                "[문장]\n%s\n\n"
                "lines 배열로만 답하라." % (label, rule,
                                        "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(old)))
            )
            raw = _vault_call(prompt, SCHEMA)
            got = (raw or {}).get("lines") if isinstance(raw, dict) else None
            new, changed, reverted = clean(got, old)
            result[str(sp["id"])]["roles"][role] = {"old": old, "new": new}
            report.append("- **%s** — %d줄 중 %d줄 변환%s" % (
                role, len(old), changed,
                ("  (되돌림 %d: %s)" % (len(reverted), reverted[0][1]) if reverted else "")))
            for o, n in zip(old, new):
                if o != n:
                    report.append("    - %s\n      → %s" % (o, n))
            print("  %s.%s %d/%d 변환 (되돌림 %d)" % (sp["id"], role, changed, len(old), len(reverted)))

    os.makedirs("out", exist_ok=True)
    json.dump(result, open("out/spine_endings.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    open("out/spine_endings.md", "w", encoding="utf-8").write(
        "# 어미 통일 — 인스타 ~요체 / 유튜브 ~음·~다\n" + "\n".join(report) + "\n")
    print("\n→ out/spine_endings.json / .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
