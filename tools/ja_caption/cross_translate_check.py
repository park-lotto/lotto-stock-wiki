"""네 언어 바로 옮기기 실측(관제 254, 2026-10-23) — 실제 쇼츠 원문(ko·ja·zh·en)을 나머지 세 언어로 옮기고 결과를 잰다.

잰다: 줄 수 일치 · 그 언어로 쓰였나(_is_lang) · 글말/번역투 · 줄 길이 · 원문 말투(존댓말/반말) 유지 · 같은 끝맺음 3연속.
  py tools/ja_caption/cross_translate_check.py <sources.json>   ({"ko": [...], "ja": [...], "zh": [...], "en": [...]})
  → sources.json 옆 cross_result.json + 표
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

WRITTEN = {   # 언어별 글말·번역투 — 일본 쇼츠 9편 실측 0건(ja), 그 외는 각 지시문의 금지 목록과 같은 것
    "ja": re.compile(r"(ということ[。！!]*$|消え去|である[。]*$|における|となっております|にて)"),
    "ko": re.compile(r"(하는 것이다|것입니다\.?$|에 있어서|되어지|을 통해|를 통해)"),
    "zh": re.compile(r"(之|(?<![尤极])其(?![实他中次])|乃|予以|进行|该产品)"),
    "en": re.compile(r"\b(hereby|thus|therefore|whereby)\b", re.I),
}
MAXLEN = {"ja": 32, "ko": 32, "zh": 24, "en": 90}


def _ending(x, lang):
    t = re.sub(r"[\s。！？!?.,、，…~～]+$", "", x)
    return t[-2:] if lang in ("ja", "ko", "zh") else " ".join(t.split()[-1:]).lower()


def check(lines, lang, src_register):
    from shopping_shorts import script_translate as st
    ends = [_ending(x, lang) for x in lines]
    triple = sum(1 for i in range(2, len(ends)) if ends[i] == ends[i - 1] == ends[i - 2])
    reg = st.register_of(lines, lang) if lang in ("ko", "ja") else None
    return {
        "not_lang": [x for x in lines if not st._is_lang(x, lang)],
        "written": [x for x in lines if WRITTEN[lang].search(x)],
        "too_long": [x for x in lines if len(x) > MAXLEN[lang]],
        "same_end_3": triple,
        "register": reg, "register_ok": (reg is None or reg == src_register),
    }


def main(path):
    from shopping_shorts import script_translate as st
    src = json.loads(Path(path).read_text(encoding="utf-8"))
    res = []
    for s_lang, lines in src.items():
        s_reg = st.register_of(lines, s_lang)
        for t_lang in ("ko", "ja", "zh", "en"):
            if t_lang == s_lang:
                continue
            try:
                out = st.translate(lines, t_lang, source=s_lang)
                c = check(out, t_lang, s_reg)
            except ValueError as e:
                out, c = [], {"error": str(e)}
            res.append({"from": s_lang, "to": t_lang, "src": lines, "out": out, "check": c})
            print(f"{s_lang}->{t_lang}", json.dumps(c, ensure_ascii=False)[:220], flush=True)
    Path(path).with_name("cross_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
