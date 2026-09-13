# -*- coding: utf-8 -*-
"""대본 린터 — 규칙표 하나에서 **프롬프트 지시문**과 **판정**을 둘 다 뽑는다.

왜 한 표인가: 숏템메이커에서 헌장은 CTA를 쓰라 하고 게이트는 벌줬다("시켜놓고 벌주기", 2026-08-22).
규칙이 두 곳에 있으면 반드시 어긋난다. 여기서는 규칙의 지시문과 검사가 같은 객체다.

규칙 원천: 볼케이노 서버 반려 원문 13개 + 경고 4개 (channel/volcano/뇌전구_역분석_8편_2026-09-12.md §4, 전편 §2)
판정은 데이터를 고치지 않는다 — 반려(reject)/경고(warn)와 사유만 낸다.
"""
import re
from dataclasses import dataclass, field

from . import spec, layout

REJECT, WARN = "reject", "warn"


@dataclass
class Issue:
    rule: str
    level: str
    where: str
    found: str
    why: str


@dataclass
class Rule:
    id: str
    level: str
    prompt: str                 # LLM에게 주는 지시문 (한 줄)
    check: object               # fn(script, ctx) -> [Issue]
    needs_layout: bool = False


_FORMAL = re.compile(r"(습니다|습니까|십시오)[.!?]?$")
_FORMAL_HARD = re.compile(r"(습니까|십시오)[.!?]?$")

# 어미 두 계열 — 실물은 편마다 **하나로 통일**한다(아래 r_ending_mix 주석의 실측).
_END_NEWS = re.compile(r"(였다|이었다|았다|었다|겠다|한다|된다|않았다|이다|린다|난다|온다|간다)[.!?]?$")
_END_EUM = re.compile(r"(음|함|됨|임|짐|옴|삼|남|셈)[.!?]?$")
# 종결 판정 — 볼케이노 5편 137컷의 어미를 훑어 만든 목록(2026-09-12 실측).
# '~셈'(정점 찍은 셈)·'~ㄴ데'(장비가 아닌데)·'~걸'처럼 종결로 쓰이는 것까지 포함해야 정답 편을 반려하지 않는다.
_CLOSED = re.compile(
    r"(다|임|음|됨|함|감|옴|남|짐"                        # ~다/~임 계열 + 명사형 종결(착수함·다가옴·떠남)
    r"|셈|뿐|요|야|네|지|까|냐|죠|걸|데|군|구나|더라|든|텐데)[.!?]?$")
# ★'~함/~감/~옴/~남'은 볼케이노 대본에서 종결로 쓰인다(실측: '경찰은 감찰에 착수함' · '그리고 그대로 떠남').
#   빠뜨리면 멀쩡히 닫힌 컷을 "안 닫혔다"로 반려한다(2026-09-13 박수홍 편 재작성 4회 소진).
#   반대로 명사로 끝나는 컷('돌아온 곳은 홈쇼핑' · '수천년 쌓인 식물 잔해')은 실제로 다음 컷과 이어지는 정상 문장이다.
_TITLE_PUNCT = re.compile(r'[",?!.…:;]')
_ABSTRACT_TAIL = ("이유", "사연", "진실", "비밀", "정체", "이야기", "상황", "사실", "근황", "결말")


def _groups(s):
    return s.get("groups") or []


def r_title_punct(s, ctx):
    out = []
    for k in ("h1", "h2"):
        v = (s.get("title") or {}).get(k, "") or ""
        if _TITLE_PUNCT.search(v):
            out.append(Issue("title_punct", REJECT, f"title.{k}", v, "제목에는 구두점을 쓰지 않습니다"))
    return out


def r_comma(s, ctx):
    return [Issue("comma", REJECT, f"groups[{i}]", g["text"], "이 채널 자막에 쓰지 않는 부호입니다 [',']")
            for i, g in enumerate(_groups(s)) if "," in g.get("text", "")]


def _nearest_emotion(v):
    """오타 난 감정 이름 → 가장 비슷한 정식 이름. 너무 다르면 None.

    실측 2026-09-13: «의심/떨떠러»(정답 «의심/떨떠름») 한 글자 차이로 7시도가 전부 반려됐다.
    반려 사유를 줘도 모델이 같은 오타를 되풀이했다 — 고쳐 주는 쪽이 맞다.
    """
    import difflib
    m = difflib.get_close_matches(str(v), spec.EMOTIONS, n=1, cutoff=0.7)
    return m[0] if m else None


def r_enum(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        if g.get("color") not in spec.COLORS:
            out.append(Issue("enum", REJECT, f"groups[{i}].color", str(g.get("color")), f"색은 {'/'.join(spec.COLORS)} 중 하나"))
        if g.get("role") not in spec.ROLES:
            out.append(Issue("enum", REJECT, f"groups[{i}].role", str(g.get("role")), f"역할은 {'/'.join(spec.ROLES)} 중 하나"))
        has_img = isinstance(g.get("img"), int)
        meme = g.get("meme")
        if not has_img and not meme:
            out.append(Issue("enum", REJECT, f"groups[{i}]", g.get("text", ""), "컷마다 img(슬롯 번호) 또는 meme(감정)이 있어야 합니다"))
        # ★오타 한 글자로 편이 통째로 막히면 안 된다(실측 2026-09-13 v10: «의심/떨떠러»를
        #   7번 내리 써서 대본이 실패했다). 가장 비슷한 감정으로 **고쳐서** 넘긴다.
        if meme and meme not in spec.EMOTIONS:
            fixed = _nearest_emotion(meme)
            if fixed:
                g["meme"] = fixed
                meme = fixed
        if meme and meme not in spec.EMOTIONS:
            out.append(Issue("enum", REJECT, f"groups[{i}].meme", str(meme), f"밈 감정은 다음 문자열 그대로: {' · '.join(spec.EMOTIONS)}"))
    return out


def r_nonwhite_run(s, ctx):
    out, run = [], 0
    for i, g in enumerate(_groups(s)):
        run = run + 1 if g.get("color") != "WHITE" else 0
        if run == 3:
            out.append(Issue("nonwhite_run", REJECT, f"groups[{i - 2}..{i}]", g.get("text", ""),
                             "강조색을 이만큼 연달아 쓰지 않습니다 — 사이에 WHITE를 두세요"))
    return out


def r_formal(s, ctx):
    gs = _groups(s)
    out = [Issue("formal", REJECT, f"groups[{i}]", g["text"], "격식체 의문·청유는 이 채널이 쓰지 않습니다")
           for i, g in enumerate(gs) if _FORMAL_HARD.search(g.get("text", "").strip())]
    n = sum(1 for g in gs if _FORMAL.search(g.get("text", "").strip()))
    if gs and n * 2 > len(gs):
        out.append(Issue("formal", REJECT, "groups", f"{n}/{len(gs)}", "격식 종결(-습니다)이 너무 많습니다 — 이 채널은 거의 쓰지 않습니다(반말체: ~였다/~임/~됨)"))
    return out


def r_ending_mix(s, ctx):
    """한 대본 안에서 어미 계열을 섞지 마라 — 뉴스체로 가든 음슴체로 가든 **하나로**.

    ★"~였다가 뉴스 같아서 밋밋하다"가 아니다. 실물 5편을 세어 보면 뉴스체가 정상이다
      (실측 2026-09-14, 135컷):
          박수홍   뉴스 7 · 음슴  0      이동건  뉴스 0 · 음슴 16
          보르네오 뉴스 5 · 음슴  1      테이저건 뉴스 0 · 음슴  9
          박위     뉴스 5 · 음슴  0
      5편 중 3편은 음슴체가 아예 없고 뉴스체로만 쓴다. PUNCH도 「사람이 낸 불이다」
      「이제 침묵이 더 위험하다」처럼 ~다로 닫는다. 그러니 ~였다를 금지하면
      **실물 4편이 반려된다**(골든 회귀가 막는다).

      실물의 규칙은 금지가 아니라 **통일**이다 — 한 편 안에서 어미가 왔다갔다 하지 않는다.
      우리 대본이 밋밋하게 들린 진짜 이유가 이것이다(뉴스 5 · 음슴 4로 섞였다).

    판정: 두 계열이 **둘 다 2컷 이상**이면 반려. 한쪽이 1컷이면 우연이므로 통과
          (보르네오가 뉴스 5 · 음슴 1이라 이 여유가 필요하다).
    """
    gs = _groups(s)
    news = [(i, g.get("text", "").strip()) for i, g in enumerate(gs)
            if _END_NEWS.search(g.get("text", "").strip())]
    eum = [(i, g.get("text", "").strip()) for i, g in enumerate(gs)
           if _END_EUM.search(g.get("text", "").strip())]
    if len(news) >= 2 and len(eum) >= 2:
        minor = news if len(news) <= len(eum) else eum
        keep = "음슴체(~음·~함·~임)" if minor is news else "뉴스체(~였다·~이다)"
        drop = "뉴스체(~였다·~이다)" if minor is news else "음슴체(~음·~함·~임)"
        shown = " · ".join(f"groups[{i}] «{t}»" for i, t in minor[:4])
        return [Issue("ending_mix", REJECT, "groups", f"뉴스체 {len(news)} · 음슴체 {len(eum)}",
                      f"한 편 안에서 어미가 섞였습니다 — {keep}로 통일하고 {drop}를 고치세요. "
                      f"고칠 곳: {shown}")]
    return []


def r_h2_abstract(s, ctx):
    h2 = ((s.get("title") or {}).get("h2") or "").strip()
    if any(h2.endswith(w) for w in _ABSTRACT_TAIL):
        return [Issue("h2_abstract", REJECT, "title.h2", h2, "h2는 이유·사연 같은 추상명사로 끝내지 않습니다 — 숫자·구체어로")]
    return []


def r_card(s, ctx):
    card = ((s.get("title") or {}).get("card") or "").strip()
    if not card:
        return [Issue("card", REJECT, "title.card", "", "오프닝 카드 문장이 없습니다")]
    if len(re.findall(r"[.!?]", card.rstrip(".!?"))) > 0:
        return [Issue("card", REJECT, "title.card", card, "카드는 읽어주는 한 문장입니다 — 낱말로 끊거나 두 문장을 쓰지 않습니다")]
    if len(card) > spec.POLICY_CARD_MAX_CHARS:
        return [Issue("card", REJECT, "title.card", card, f"카드가 너무 깁니다({len(card)}자) — 최소 {len(card) - spec.POLICY_CARD_MAX_CHARS + 6}자를 덜어내 30자 안팎 한 문장으로")]
    if len(card) > spec.POLICY_CARD_LONG_WARN:
        # 44자는 띠가 버티는 물리 한도고, 실제로 쓰이는 건 26~33자다(실물 5편 26·27·28·33·33).
        # 길어지면 반전 없이 기사 문장을 옮긴 것이다(실측 2026-09-13: 40자 카드가 그랬다).
        return [Issue("card", REJECT, "title.card", card,
                      f"카드가 {len(card)}자입니다 — 실제 편은 26~33자입니다. 기사 설명을 빼고 **어긋나는 동사 둘**만 남기세요")]
    return []


def r_words(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        for ln in g.get("lines") or [g.get("text", "")]:
            if len(ln.split()) > spec.POLICY_MAX_WORDS_PER_LINE:
                out.append(Issue("words", REJECT, f"groups[{i}]", ln, "한 줄에 어절이 너무 많습니다"))
    return out


def r_layout(s, ctx):
    """배치 실패 = 두 줄로도 화면에 안 들어감 (서버: '줄나눔은 서버가 하므로 글자를 줄이거나 두 카드로 쪼개라')"""
    return [Issue("layout", REJECT, f["where"], f["found"], "한 줄이 너무 깁니다 — 글자를 줄이거나 두 카드로 쪼개세요")
            for f in (ctx.get("layout_fails") or [])]


def r_punch(s, ctx):
    n = sum(1 for g in _groups(s) if g.get("role") == "PUNCH")
    if n != 1:
        return [Issue("punch", REJECT, "groups", str(n), "PUNCH는 영상당 정확히 1컷(마지막 컷)입니다")]
    return []


def r_first_open(s, ctx):
    gs = _groups(s)
    if gs and _CLOSED.search(gs[0].get("text", "").strip()):
        return [Issue("first_open", WARN, "groups[0]", gs[0]["text"], "첫 장면에서 문장을 끝내면 다음으로 끌고 가는 힘이 약합니다")]
    return []


def r_last_closed(s, ctx):
    gs = _groups(s)
    if not gs:
        return []
    g = gs[-1]
    out = []
    if not _CLOSED.search(g.get("text", "").strip()):
        out.append(Issue("last_closed", WARN, f"groups[{len(gs) - 1}]", g["text"], "마지막 문장이 끝나지 않았습니다. 닫아 주세요"))
    if g.get("color") == "WHITE" or g.get("role") != "PUNCH":
        out.append(Issue("last_punch", WARN, f"groups[{len(gs) - 1}]", g["text"], "마지막 컷은 WHITE로 닫지 않습니다 — RED PUNCH 단정문이 이 채널 결입니다"))
    return out


def r_last_standalone(s, ctx):
    """마지막 컷은 **그 자체로 완결된 한 문장**이어야 한다 — 앞 컷에서 이어지면 반려.

    실측 2026-09-12(테이저건 편): 21컷 «학부모는 분통을» → 22컷 «터뜨리는 중임»으로 한 문장을 잘라
    마지막 컷만 보면 주어가 없었다. 볼케이노 5편은 전부 마지막 컷이 독립 문장이다
    ('사과보다 복귀가 빨랐다' · '사람이 낸 불이다' · '몰랐다는 말로 끝날 일이 아니다').
    """
    gs = _groups(s)
    if len(gs) < 2:
        return []
    prev = gs[-2].get("text", "").strip()
    if prev and not _CLOSED.search(prev):
        return [Issue("last_standalone", REJECT, f"groups[{len(gs) - 1}]", gs[-1].get("text", ""),
                      f"마지막 컷이 앞 컷 «{prev}»에서 이어집니다 — 마지막 컷은 그 자체로 끝나는 한 문장이어야 합니다. 앞 컷을 닫고 마지막을 새 문장으로 쓰세요")]
    return []


def r_line1_end(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        ls = g.get("lines") or []
        if len(ls) > 1 and _CLOSED.search(ls[0].strip()) and ls[0].strip()[-1] in ".!?다":
            out.append(Issue("line1_end", WARN, f"groups[{i}].lines[0]", ls[0], "윗줄에서 문장이 끝났습니다. 아랫줄로 넘기는 쪽이 이 채널 결입니다"))
    return out


def r_meme_ratio(s, ctx):
    gs = _groups(s)
    if not gs:
        return []
    n = sum(1 for g in gs if g.get("meme"))
    r = n / len(gs)
    # 실측 실물 5편: 15·16·14·17·18% — 아주 좁다. 22%를 넘으면 밈이 너무 잦다
    # (실측 2026-09-13: 23컷에 밈 6개=26%가 경고선 25% 밑으로 새어 통과했다).
    if r < 0.10 or r > 0.22:
        return [Issue("meme_ratio", WARN, "groups", f"{n}/{len(gs)} = {r:.0%}",
                      f"밈은 전체의 14~18%가 이 채널 관행입니다(실물 5편 15·16·14·17·18%) — {round(len(gs)*0.16)}컷 안팎")]
    return []


def r_slot_seq(s, ctx):
    """이미지 슬롯은 1부터 빠짐없이 이어져야 한다.

    ★실측 2026-09-13: 대본이 2~9번을 써서 1번이 통째로 없었다. 지시문엔 "img 번호 1부터"라고
      적혀 있는데 **판정이 없어** 그냥 통과했고, 슬롯이 8개로 줄어 사진도 한 장 덜 만들어졌다
      (목표 9~11장). 번호가 비면 카드·컷 배정도 어긋난다.
    """
    slots = sorted({g["img"] for g in _groups(s) if isinstance(g.get("img"), int)})
    if not slots:
        return []
    want = list(range(1, len(slots) + 1))
    if slots != want:
        missing = [n for n in want if n not in slots]
        return [Issue("slot_seq", REJECT, "groups[].img", str(slots),
                      f"슬롯 번호는 1부터 빠짐없이 이어져야 합니다 — 빠진 번호 {missing or '없음'}, {len(slots)}개면 1~{len(slots)}")]
    return []


def r_slot_count(s, ctx):
    """이미지 슬롯 개수 — 실물 5편은 9·9·10·11·11개다.

    ★슬롯이 많으면 그만큼 이미지를 더 만든다(돈이 든다). 지시문엔 9~11이라 적혀 있는데
      판정이 없어 14개짜리가 통과했다(실측 2026-09-13). 12까지는 받고 그 위만 막는다.
    """
    n = len({g["img"] for g in _groups(s) if isinstance(g.get("img"), int)})
    if n and n > spec.POLICY_MAX_SLOTS:
        return [Issue("slot_count", REJECT, "groups[].img", f"{n}개",
                      f"이미지 슬롯이 너무 많습니다 — 실제 편은 9~11개입니다. 한 슬롯을 2~3컷이 나눠 쓰게 묶으세요")]
    return []


def r_card_img(s, ctx):
    """오프닝 카드에 쓸 슬롯 — 없는 슬롯이면 반려, 1번이면 경고.

    ★1번을 쓰면 카드 바로 뒤에 1번 컷이 와서 **같은 사진이 연달아** 보인다
      (실측 2026-09-13 사장님 "첫 후킹 사진이랑 다음 사진이랑 같게 나온다":
       카드·1컷·2컷이 전부 01.png라 확대만 바뀐 화면이 셋 이어졌다).
      단 실물 5편 중 3편도 1번을 쓰므로 **반려는 아니다** — 알리기만 한다.
    """
    ci = s.get("card_img")
    if ci is None:
        return []
    slots = {g["img"] for g in _groups(s) if isinstance(g.get("img"), int)}
    if not isinstance(ci, int) or ci not in slots:
        return [Issue("card_img", REJECT, "card_img", str(ci),
                      f"없는 슬롯입니다 — 대본에 있는 슬롯({min(slots) if slots else '?'}~{max(slots) if slots else '?'}) 중에서 고르세요")]
    if ci == 1:
        return [Issue("card_img", WARN, "card_img", str(ci),
                      "카드가 1번이면 바로 뒤 1번 컷과 같은 사진이 이어집니다 — 3번 이후를 고르세요")]
    return []


def r_copy(s, ctx):
    src = (ctx.get("source_text") or "").replace(" ", "")
    if not src:
        return []
    out = []
    for i, g in enumerate(_groups(s)):
        t = g.get("text", "").replace(" ", "")
        if len(t) >= spec.POLICY_COPY_MIN_CHARS and t in src:
            out.append(Issue("copy", REJECT, f"groups[{i}]", g["text"], "원문 문장을 줄인 것이지 다시 쓴 것이 아닙니다 — 다시 쓰세요"))
    return out


def r_cut_count(s, ctx):
    """컷이 너무 적으면 반려 — 지시문엔 22~32라고 적어놨는데 판정이 없었다(0순위: 규칙은 있는데 판정이 없다).

    실측 2026-09-13: 내용 규칙을 넣은 뒤 모델이 17컷짜리를 냈는데 그대로 통과했다.
    실물 5편은 22·25·28·28·32컷(최소 22)이고, 22컷 미만이면 35초가 안 나온다.
    """
    n = len(_groups(s))
    if not n:
        return []
    lo = ctx.get("min_cuts")            # 시험은 4컷짜리 가짜 대본을 쓴다 — 낮춰 부를 수 있게 연다
    lo = spec.POLICY_MIN_CUTS if lo is None else lo
    if n < lo:
        return [Issue("cut_count", REJECT, "groups", f"{n}컷",
                      f"컷이 모자랍니다 — {lo}~{spec.POLICY_MAX_CUTS}컷으로 늘리세요")]
    if n > spec.POLICY_MAX_CUTS:
        return [Issue("cut_count", WARN, "groups", f"{n}컷",
                      f"컷이 많습니다 — {spec.POLICY_MAX_CUTS}컷 이하가 이 채널 관행입니다")]
    return []


def r_example_copy(s, ctx):
    """지시문에 든 예시 문장을 **남의 기사에** 그대로 쓰면 반려.

    실측 2026-09-13: 카드 예시로 실물 편의 «케냐 봉사 갔다가 봉사 받고 왔다는 백만 유튜버»를 보여줬더니
    같은 소재라 그 문장을 **그대로** 카드로 냈다. 예시는 구조를 보라는 것이지 베끼라는 게 아니다.

    ★단, 그 예시의 주인공이 이 기사의 주인공이면 반려하지 않는다 — 실물 5편 자신이 걸려버린다
      (골든 회귀 시험이 즉시 잡아줬다: 박수홍 편이 «사과보다 복귀가 빨랐다»로 반려됨).
      판정은 "이 기사에 없는 고유명사를 예시에서 데려왔나"로 한다.
    """
    src = (ctx.get("source_text") or "")
    out = []

    def borrowed(text):
        """예시와 같은 문장인데, 그 예시의 고유명사가 이 기사엔 없다 → 남의 것을 베꼈다."""
        t = text.replace(" ", "")
        for ex in spec.PROMPT_EXAMPLES:
            e = ex.replace(" ", "")
            if not e or (t != e and not (len(e) >= 12 and e in t)):
                continue
            names = [w for w in spec.PROMPT_EXAMPLE_NAMES if w.replace(" ", "") in e]
            if not names or any(w not in src for w in names):
                return ex
        return None

    card = (s.get("title") or {}).get("card") or ""
    ex = borrowed(card)
    if ex:
        out.append(Issue("example_copy", WARN, "title.card", card,
                         "지시문 예시를 그대로 베꼈습니다 — 이 기사로 새로 쓰세요"))
    for i, g in enumerate(_groups(s)):
        t = g.get("text", "")
        if len(t.replace(" ", "")) >= 8 and borrowed(t):
            out.append(Issue("example_copy", WARN, f"groups[{i}]", t,
                             "지시문 예시를 그대로 베꼈습니다 — 이 기사로 새로 쓰세요"))
    return out


RULES = [
    Rule("title_punct", REJECT, "제목(h1·h2)에는 구두점을 쓰지 마라 (따옴표·물음표·마침표 포함).", r_title_punct),
    Rule("comma", REJECT, "자막 본문에 쉼표(,)를 쓰지 마라.", r_comma),
    Rule("enum", REJECT, f"색은 {'/'.join(spec.COLORS)}, 역할은 {'/'.join(spec.ROLES)}만. 컷마다 img(슬롯 번호) 또는 meme(감정) 중 하나. 밈 감정은 다음 문자열 그대로: {' · '.join(spec.EMOTIONS)}.", r_enum),
    Rule("nonwhite_run", REJECT, "흰색이 아닌 강조색을 3컷 연달아 쓰지 마라. 사이에 WHITE를 둬라.", r_nonwhite_run),
    Rule("formal", REJECT, "나레는 반말체(~였다/~했다 또는 ~임/~됨). '-습니다'가 과반이면 안 되고 '-습니까/-십시오'는 쓰지 마라.", r_formal),
    Rule("ending_mix", REJECT, "어미는 **한 편 안에서 하나로 통일**하라 — 뉴스체(~였다·~이다)로 갈지 음슴체(~음·~함·~임)로 갈지 먼저 정하고 끝까지 그것만 써라. 둘을 섞으면 반려된다(PUNCH도 같은 계열로 닫아라).", r_ending_mix),
    Rule("h2_abstract", REJECT, "h2(노란 아랫줄)에는 숫자를 넣고, 이유·사연 같은 추상명사로 끝내지 마라.", r_h2_abstract),
    Rule("card", REJECT, f"카드는 오프닝에서 읽어주는 한 문장, {spec.POLICY_CARD_MAX_CHARS}자 안(실제 편 26~33자). 낱말로 끊지 마라.", r_card),
    Rule("words", REJECT, f"한 줄은 {spec.POLICY_MAX_WORDS_PER_LINE}어절 이하. 한 컷은 짧게(12~14자 한 줄 또는 두 줄).", r_words, needs_layout=True),
    Rule("layout", REJECT, "줄나눔은 우리가 한다 — lines를 쓰지 마라. 컷이 두 줄로도 안 들어가면 반려되니 글자를 줄이거나 두 컷으로 쪼개라.", r_layout, needs_layout=True),
    Rule("punch", REJECT, "PUNCH는 마지막 컷 하나뿐. RED 색으로 짧은 단정문.", r_punch),
    Rule("last_standalone", REJECT, "마지막 컷은 앞 컷에서 이어지지 않는 **독립된 한 문장**으로 써라. 앞 컷에서 문장을 끝내고, 마지막 컷만 읽어도 말이 되게 하라.", r_last_standalone),
    Rule("copy", REJECT, "원문을 요약하지 말고 다시 써라. 원문 문장을 그대로 줄여 쓰지 마라.", r_copy),
    Rule("cut_count", REJECT, f"컷은 {spec.POLICY_MIN_CUTS}~{spec.POLICY_MAX_CUTS}개. 모자라면 반려된다.", r_cut_count),
    Rule("slot_count", REJECT, f"이미지 슬롯은 9~11개(최대 {spec.POLICY_MAX_SLOTS}). 한 슬롯을 2~3컷이 나눠 쓴다.", r_slot_count),
    Rule("slot_seq", REJECT, "이미지 슬롯 번호는 1부터 빠짐없이 이어지게 매겨라(1,2,3…). 번호를 건너뛰지 마라.", r_slot_seq),
    Rule("card_img", REJECT, "card_img는 대본에 있는 슬롯 번호. 1번은 피해라 — 카드 뒤 1번 컷과 같은 사진이 이어진다.", r_card_img),
    Rule("example_copy", WARN, "지시문에 든 예시 문장을 그대로 쓰지 마라 — 구조만 따르고 이 기사로 새로 써라.", r_example_copy),
    Rule("first_open", WARN, "첫 컷에서 문장을 끝내지 마라 — 다음 컷으로 끌고 가라.", r_first_open),
    Rule("last_closed", WARN, "마지막 컷은 문장을 닫아라. WHITE가 아니라 RED PUNCH로.", r_last_closed),
    Rule("line1_end", WARN, "(줄나눔 참고) 두 줄 컷의 윗줄에서 문장이 끝나지 않게 컷을 짜라.", r_line1_end, needs_layout=True),
    Rule("meme_ratio", WARN, "밈 컷은 전체의 14~18% (4~5컷). 첫 밈은 6~8번째 컷, 마지막 컷은 밈.", r_meme_ratio),
]


def prompt_block():
    """규칙표 → 프롬프트 지시문. 판정과 같은 객체에서 나오므로 어긋날 수 없다."""
    return "\n".join(f"- {r.prompt}" for r in RULES)


def lint(script, *, source_text="", do_layout=True, fonts_dir=None, min_cuts=None):
    """→ (issues, script_with_lines). 원본 script는 손대지 않는다."""
    ctx = {"source_text": source_text, "min_cuts": min_cuts}
    s = dict(script)
    if do_layout:
        gl, fails = layout.layout_groups(_groups(script), fonts_dir)
        s["groups"] = gl
        ctx["layout_fails"] = fails
    issues = []
    for r in RULES:
        if r.needs_layout and not do_layout:
            continue
        issues += r.check(s, ctx)
    return issues, s


def rejects(issues):
    return [i for i in issues if i.level == REJECT]


def feedback(issues):
    """실패 항목을 재작성 지시로. 규칙의 사유만 나열한다 — script_gate.gate_feedback의 '분량 처방' 자동 첨부 없음(아스트라 지적)."""
    bad = rejects(issues)
    if not bad:
        return ""
    return ("\n\n[재작성 지시 — 방금 쓴 것이 아래를 어겼다]\n"
            + "\n".join(f"- {i.where} «{i.found}»: {i.why}" for i in bad)
            + "\n\n★고치는 법: 지적된 곳 **말고는 글자 하나도 바꾸지 마라**. 대본을 새로 쓰지 마라.\n"
              "  방금 낸 JSON을 그대로 가져와 위 항목만 손보고 전체를 다시 출력하라.\n"
              "  컷 개수·순서·색·역할·img 번호·card_img를 그대로 두면 새 반려가 생기지 않는다.\n"
              "  (실측 2026-09-13: 7번 다시 쓰는 동안 컷 수가 23→24→26으로 계속 바뀌었다 —\n"
              "   한 곳을 고치면서 대본을 새로 써 다른 곳이 깨졌다.)")
