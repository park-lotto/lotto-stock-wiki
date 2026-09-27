# -*- coding: utf-8 -*-
"""이야기 작가 — 씨앗 결로 쓰고 화면은 나중에 붙인다 (2026-09-22 사장님 승인).

★왜 새 모듈인가: 기존 `backbone_assemble.write_lines*`는 **화면 묶음(groups_out)을 먼저 받아**
  그 화면에 맞춰 대본을 쓴다. 그래서 화면이 대본을 끌고 갔다(핸드오프: "두 달간 14번 전부
  문장↔장면 매칭을 더 잘하는 법이었다. 전부 두더지").
  여기서는 **대본이 먼저**다. 노바 작가(썰쇼핑 1위)가 쓰는 순서와 같다(2026-09-22 영상 정독).

★2026-09-27부터 안마다 **모델 한 번**(write_styled): 스타일 칸 틀(자동 1안은 씨앗 흐름) + 씨앗 + 재료 태깅을 주면
  칸 순서대로 줄과 줄마다 컷 번호를 같이 낸다. 코드는 검사만(styled_problems) — 걸리면 이유를 붙여 한 번 다시 쓴다.
  종전의 특징 뽑기·고정 칸 양식·신호어 세트·순서 돌리기는 스타일 칸을 버리고 A·B를 같게 만들어 걷어냈다(git 기록에 있음).

★플랫폼으로 갈린다(실측): 유튜브 썰 = 반말·CTA 없음 / 인스타 = 존댓말 1인칭·`~더라고요`. 말투는 _VOICE 한 곳.

★표현은 자유다(2026-09-22 "어짜피 이건 후킹싸움이야", 09-27 "지어내고 어그로 있어도 상관없어"):
  과장·지어낸 상황·인물 다 된다. 단 줄마다 화면에 붙일 컷은 있어야 한다.

시험대 원본: tools/seed_analyzer/ · 한 번 호출 시험: tools/script_diff/nova_style_proto.py · 결과물 검사: tools/script_diff/check_styled.py
"""
import re

from shopping_shorts import script_generate as _sg


# ── 길이 프리셋(2026-09-22 사장님 "두 개 다 프리셋으로 — 길이 숫자 말고 재밌게") ──────────────
#   short 한입썰 = 히트작 기준(썰 601편 중앙 203자·23초, 30초 이하 84%) — 지금 기본.
#   full  풀코스썰 = 긴 구조(345자·약 46초: 고조1 뒤 장면 풀이 3~4줄 + 심지어 2줄 + 마지막 셀링 3줄).
#   풀코스는 재료 화면보다 길어질 수 있다 — 화면 길이로 자르지 않는다(사용자가 배속을 올려 맞춘다).
LENGTH_PRESETS = {
    "short": {"label": "한입썰", "seconds": 25, "cap_by_footage": True},
    "full":  {"label": "풀코스썰", "seconds": 46, "cap_by_footage": False},
}


def _seed_word_hits(text, seed_points, product=""):
    """문장 속에 씨앗 셀링포인트의 **특징 낱말**이 몇 개 나오나(제품명 낱말은 뺀다 — 어느 줄에나 나온다)."""
    skip = set(_words(product))
    sw_ = {w for w in _words(" ".join(seed_points or [])) if w not in skip}
    t = re.sub(r"\s+", "", text or "")
    return sorted(w for w in sw_ if w in t)


def _gram_share(a, b, n=4):
    """a의 n글자 조각 중 b에도 있는 비율(글자만)."""
    ca, cb = re.sub(r"[^가-힣A-Za-z0-9]", "", a or ""), re.sub(r"[^가-힣A-Za-z0-9]", "", b or "")
    ga = {ca[i:i + n] for i in range(max(0, len(ca) - n + 1))}
    gb = {cb[i:i + n] for i in range(max(0, len(cb) - n + 1))}
    return len(ga & gb) / len(ga) if ga else 0.0


# ── 재료 태깅을 모델이 읽을 글로 (불편 컷을 앞에) ─────────────────────────────
#   근거(라이브 실측 2026-09-22, 최근 57 job·3,880 세그): shot_role '문제' 132·'before' 339,
#   57 job 중 43개(75%)에 문제/before 세그가 있다 — 뽑는 사람이 없었을 뿐이다.
PROBLEM_ROLES = {"문제", "before"}
PROBLEM_WORDS = re.compile(r"불편|어려움|번거|귀찮|지저분|엉키|엉망|힘들|고생|낭비|"
                           r"문제|손상|망가|샌다|흘러|끈적|답답|공감")


def source_block(sources):
    """태깅을 모델이 읽을 형태로. 문제/before 컷을 앞에 모아 눈에 띄게 한다."""
    prob, normal = [], []
    for v in sources or []:
        for x in (v.get("segments") or []) if isinstance(v, dict) else []:
            role = x.get("shot_role") or ""
            up = (x.get("use_point") or "")
            line = "  [%s] %s | 화면:%s%s%s%s" % (
                x.get("seg_id"), role, (x.get("scene_desc") or "")[:70],
                (" | 변화:%s" % (x.get("change") or "")[:40]) if x.get("change") else "",
                (" | 용처:%s" % up[:70]) if up else "",
                (" | 특징:%s" % " / ".join(str(b) for b in (x.get("product_benefits") or [])[:2]))
                if x.get("product_benefits") else "")
            (prob if (role in PROBLEM_ROLES or PROBLEM_WORDS.search(up)) else normal).append(line)
    out = []
    if prob:
        out += ["[불편을 보여주는 컷 — pain은 여기서 가져와라]"] + prob[:20] + [""]
    out.append("[나머지 컷]")
    out += normal[:60]
    return "\n".join(out)


_DIFF_STOP = {"제품", "사용", "가능", "있음", "있는", "없이", "쉽게", "간편", "다른", "용도", "형태", "구성", "한번",
              "하나", "바로", "매우", "정말", "진짜", "특징", "기능", "장점", "효과", "개선", "제공", "적용", "완벽"}
_JOSA = re.compile(r"(으로|에서|에게|까지|부터|이나|이랑|처럼|보다|하고|으로도|로도|에도|과|와|이|가|을|를|은|는|에|의|도|로|만)$")


def _words(t):
    out = []
    for w in re.findall(r"[가-힣A-Za-z0-9]+", t or ""):
        w = _JOSA.sub("", w)
        w = re.sub(r"(한|하게|적인|스러운|로운|진|된|되는|하는|있는)$", "", w)
        if len(w) >= 2 and w not in _DIFF_STOP:
            out.append(w)
    return out


def _share_cuts(lines, bs, seg_index):
    """컷이 하나도 없는 줄에 **남는 컷을 나눠 준다**. 돌려준 값 = 끝내 빈 줄 번호들.
    ★assign_cuts는 앞 줄부터 '길이+여유+최소 2컷'을 채워 재료가 빠듯하면 뒤 줄이 빈손이 된다
      (2026-09-22 실측 job 13d4cab55fba: 쓸 컷 27개를 9줄 중 8줄이 다 쓰고 마무리 줄 0컷).
      빈 줄은 3단계 채우기가 대본을 안 보고 메우므로, 넉넉한 줄에서 **빼도 대사 길이를 덮는 컷만** 옮긴다."""
    from shopping_shorts import backbone_assemble as ba

    def secs(s):
        return (seg_index.get(s) or {}).get("secs") or 0.0
    empty = []
    for i, b in enumerate(bs):
        if b and b.get("segs"):
            continue
        need, got = ba._secs(lines[i]["text"]), []
        while sum(secs(s) for s in got) < need:
            donors = [(len(d["segs"]), j) for j, d in enumerate(bs) if j != i and d and len(d.get("segs") or []) > 1
                      and sum(secs(s) for s in d["segs"][:-1]) >= ba._secs(lines[j]["text"])]
            if not donors:
                break
            j = max(donors)[1]
            got.append(bs[j]["segs"].pop())
        bs[i] = {"role": lines[i]["role"], "seg": got[0] if got else "", "segs": got}
        if not got:
            empty.append(i)
    return empty


# ★"~더라고요/~거든요/~는데요/~잖아요"가 빠져 있었다(2026-09-22 말맛 센서스 실측): 인스타 대표 어미(docstring에도
#   95~98%라 적어 놓고!)를 안 세어, 차량용 홀더 씨앗("더라고요"×3)이 존댓말 어절 2개로 잡혀 **썰(반말)로 써졌다**.
_POLITE_ENDS = r"(어요|아요|에요|예요|해요|세요|네요|죠|니다|니까|더라고요|더라구요|거든요|는데요|잖아요|고요|나요|까요|래요|대요|돼요|져요|봐요|줘요|워요|와요)"
_POLITE_WORD = re.compile(_POLITE_ENDS + r"[.!?~…]*$")
_POLITE_SPLIT = re.compile(_POLITE_ENDS + r"(?=[가-힣])")     # 어미 목록은 위 한 곳(0순위-B)


def seed_platform(seed_text):
    """씨앗의 결 → "ig"(존댓말 체험담) | "yt"(반말 썰). **어절 단위**로 센다.
    ★전사엔 문장부호가 거의 없다(실측 524자에 2개) — 문장으로 나눠 끝말을 보면 한 덩어리가 돼 판정이 무의미하다."""
    # ★자막을 이어 붙인 전사는 문장 사이 띄어쓰기가 없다("안 돼요저도 매번사실") → 어미 뒤에서 한 번 끊어 준다.
    #   히트작 1,116편 대조(2026-09-22): 인스타 존댓말 놓침 38→26, 썰 소개체 362편 오판 0.
    #   문턱(3개·3%)은 그대로 — 2개로 낮추면 놓침 16이 되지만 썰 소개체 12편이 인스타로 넘어간다.
    t = _POLITE_SPLIT.sub(r"\1 ", seed_text or "")
    ws = t.split()
    pol = sum(1 for w in ws if _POLITE_WORD.search(w))
    return "ig" if pol >= 3 and pol / max(1, len(ws)) >= 0.03 else "yt"


def _norm_text(t):
    return re.sub(r"\s+", "", str(t or ""))


# ── 한 번 호출 작가(2026-09-27 사장님 "노바 작가처럼 — 영상 태깅을 보고, 스타일 틀을 지키고, 기능·특징·장점을 써라.
#    웹에서 하나씩 물으면 되는데 API로 하면 왜 안 되나" / "지어내고 어그로가 있어도 상관없어, 최대한 후킹").
#    종전 길(특징 뽑기 → 코드가 고르기 → 고정 칸 양식 → 순서 돌리기 → 규칙 글)은 고른 스타일의 칸을 버렸고(「OO의 정체」를
#    골라도 미끼·화제 칸이 없음) A·B 안이 같은 특징 배치로 똑같이 나왔다. 같은 재료로 한 번 호출 시험(work 348b6b0e2e3d,
#    스타일 70·74 — tools/script_diff/nova_style_proto.py)에서 칸 순서 그대로·없는 컷 번호 0.
#    → 판단은 모델 한 번, 코드는 **검사만** 하고 걸리면 이유를 붙여 한 번 다시 쓰게 한다.
STYLED_SCHEMA = {"type": "object", "properties": {
    "seed_points": {"type": "array", "items": {"type": "string"}},
    "lines": {"type": "array", "items": {"type": "object", "properties": {
        "role": {"type": "string"}, "text": {"type": "string"},
        "cuts": {"type": "array", "items": {"type": "string"}}}, "required": ["role", "text", "cuts"]}}},
    "required": ["seed_points", "lines"]}

_VOICE = {
    "yt": "남 얘기 전하는 썰(반말). 보는 사람에게 말을 걸지 마라. 줄 끝: ~는데 · ~는 거 · ~다는데 · ~다고 · ~버림 · ~였음",
    "ig": "겪은 일을 이야기하는 존댓말 1인칭. 줄 끝: ~더라고요 · ~거든요 · ~어요. 유튜브 썰 어미(~다는데·~는 거임)는 쓰지 마라",
}

STYLED_BRIEF = """너는 한국 쇼핑 숏폼 나레이션 작가다. 이 제품으로 **팔릴 수밖에 없는 대본**을 써라.

[씨앗 대본]은 이 제품으로 이미 터진 영상의 말이다. [재료]는 같은 제품을 찍은 다른 영상들의 장면 태깅이다.

■ 틀 — %(frame_rule)s
■ 차별점 = 기능·특징·장점 — 씨앗이 이미 자랑한 셀링포인트는 **%(open_rule)s 말고는** 쓰지 마라.
  나머지 칸은 [재료]를 보고 **사람들이 좋아할 만한** 기능·특징·장점(씨앗에 없는 것)으로 채운다.
■ 후킹이 전부다 — 과장·어그로·지어낸 상황·인물·반응 다 좋다. 세게, 구체적으로, 끝까지 보게 써라.
  단 **실존 인물 이름은 쓰지 마라**(연예인·셰프·유튜버·기업 대표 등) — 사람은 이 제품을 쓸 법한 직업·집단의 보통명사로.
%(copy_rule)s
  단 줄마다 화면에 붙일 컷은 있어야 한다(말과 영 딴판인 화면이 되지 않게).
■ 말투 — %(voice)s
■ 분량 — 전체 약 %(chars)d자(읽으면 약 %(secs)d초).
■ 줄마다 cuts에 그 말에 어울리는 컷 번호를 [재료]에서 1~2개 적어라(목록에 있는 번호만). 컷은 줄끼리 되도록 겹치지 않게.
■ seed_points에는 씨앗이 자랑한 셀링포인트를 짧게 적어라."""


# ── 공통 문구 자산(2026-09-27 사장님 "미끼·마지막 부분 등 공통적으로 들어가는 부분을 많이 만들어놓고 랜덤으로 선택을
#    못한다면 순번대로 / 공통부분을 많이 자산으로 만들어놓는 게 자산 / 조금씩 변형도 / 어떤 게 들어가든 상관없는 지점").
#    제품과 무관한 칸만. 원본 = 스타일의 그 칸 예시, 자산 = 예시마다 변형(shopping_shorts/story_common_bank.json,
#    만든 도구 tools/spine_presets/make_common_bank.py). 모델에게 고르게 하면 첫 번째만 쓴다(12작업 중 5개 같은 마무리,
#    2026-09-27 실측) → **코드가 작업마다 고른다**(작업 번호 해시 = 순번). 모델은 {빈칸}만 채운다.
COMMON_ROLES = {"yt": ["bait", "fame", "land"], "ig": ["hook", "proof", "notice", "cta", "regret"]}
_BANK = None
_SPICY = {}
# ★자극 확장은 빈칸 없는 칸에만, 과한 말은 뺀다(2026-09-27 사장님 "자극적인 게 너무 오바해서 쓴 게 심하네").
#   10작업 비교 실측: 빈칸 있는 자극 문장에 효능을 채우면 "전 기능 초토화시키는 40시간 몬스터 재생력"처럼 문장이 깨졌다.
OVER_TOP = re.compile(r"초토화|멘붕|씹어먹|몬스터|기절|박살|경악|마비|미쳐버|전율|소름|사기급|괴물|난리법석|개박살|싹쓸이")
# ★고조 칸은 3줄 흐름(2026-09-27 사장님 "고조 3줄 흐름이 없으니 안 좋네") — 옛 대본의 강점: ①그 순간 ②그때의 불편(~하던 그 지옥을)
#   ③제품이 없애 버림. 공식은 **머리말만** 고정하고(이게 말도 안 되는게·심지어·게다가) 그 아래 3줄은 모델이 재료로 쓴다.
#   GOJO_OPEN(기존 한계 등)은 ①②만 쓰고 바로 다음 칸(해결)이 ③을 맡는다.
GOJO3 = {"more", "escalation", "escalate", "benefit", "good", "power", "extra"}
GOJO_OPEN = {"limit", "pain", "vs"}



def _bank():
    global _BANK
    if _BANK is None:
        import json, os
        p = os.path.join(os.path.dirname(__file__), "story_common_bank.json")
        try:
            _BANK = (json.load(open(p, encoding="utf-8")) or {}).get("variants") or {}
        except (OSError, ValueError) as e:     # 자산이 없으면 스타일 예시만으로 돈다 — 조용히 넘기지 않고 남긴다
            import sys
            print("story_common_bank 못 읽음(%r) — 스타일 예시만 씀" % e, file=sys.stderr)
            _BANK = {}
        # ★유튜브 공식 문장 확장(2026-09-27 사장님 "미끼·화제는 터지는 공식 — 약간씩만 바꾸고, 더 자극적으로 확장"):
        #   원문마다 약간 변형 + 더 자극적 확장(story_yt_formula.json, 도구 tools/spine_presets/expand_yt_formula.py).
        #   같은 표(원문 → 후보)에 합친다 — 고르는 곳은 common_pool 하나(0순위-B).
        p2 = os.path.join(os.path.dirname(__file__), "story_yt_formula.json")
        try:
            for xs in ((json.load(open(p2, encoding="utf-8")) or {}).get("roles") or {}).values():
                for x in xs:
                    _BANK.setdefault(x["src"], [])
                    _BANK[x["src"]] = list(_BANK[x["src"]]) + list(x.get("variants") or [])
                    _SPICY[x["src"]] = list(x.get("spicy") or [])
        except (OSError, ValueError, KeyError) as e:
            import sys
            print("story_yt_formula 못 읽음(%r) — 공식 확장 없이 씀" % e, file=sys.stderr)
    return _BANK


def common_pool(sp, role):
    """그 스타일·칸의 공통 문구 후보 = 스타일 예시 + 예시마다의 변형(자산). 순서 고정(순번의 기준)."""
    tpl = sp.get("templates") if isinstance(sp.get("templates"), dict) else {}
    out, seen = [], set()
    for ex in [x.strip() for x in (tpl.get(role) or []) if isinstance(x, str) and x.strip()]:
        # 자극 확장은 빈칸 없는 원문에만, 과한 말(OVER_TOP)은 빼고 — 거르는 곳은 여기 한 곳
        spicy = [v for v in (_SPICY.get(ex) or []) if not OVER_TOP.search(v)] if ("{" not in ex and _bank() is not None) else []
        for v in [ex] + list(_bank().get(ex) or []) + spicy:
            k = re.sub(r"\s+", "", v)
            if k not in seen:
                seen.add(k)
                out.append(v)
    return out


def skeleton_lines(sp, key):
    """스타일 뼈대 {칸: 문장} — 칸마다 후보(예시+변형) 중 하나를 작업 번호로 순번 선택. **보여 주기만** 한다(모델이 새로 씀)."""
    import zlib
    if not sp:
        return {}
    got = {}
    for r in [str(x) for x in sp.get("beat_roles") or []]:
        pool = common_pool(sp, r)
        if pool:
            got[r] = pool[zlib.crc32(("%s|%s" % (key, r)).encode("utf-8")) % len(pool)]
    return got


def common_lines(sp, key):
    """글자 그대로 쓸 공통 문장 {칸: 문장} — 뼈대 중 **빈칸이 없고** 제품과 무관한 칸만.
    ★빈칸 끼우기 금지(2026-09-27 사장님 "빈칸에 억지로 끼워넣는 건 항상 문장이 이상해진다"; 09-20 "빈칸 문장틀 조립 폐기"
      — 조각 조립 15편 전부 문장 깨짐). 유튜브는 빈칸 없는 공식(미끼·화제·마무리 등), 인스타는 COMMON_ROLES 중 빈칸 없는 것.
      고조 칸은 내용 칸이라 고정하지 않는다(모델이 3줄로 새로 씀)."""
    if not sp:
        return {}
    plat = "yt" if sp.get("no_cta") else "ig"
    return {r: ph for r, ph in skeleton_lines(sp, key).items()
            if "{" not in ph and r not in GOJO3 and r not in GOJO_OPEN and r != "title"
            and (plat == "yt" or r in COMMON_ROLES[plat])}


def _pin_share(phrase, text):
    """고정 문장의 글자(빈칸 사이 토막마다, 4글자 조각) 중 줄에 있는 비율 — 빈칸 경계를 넘는 조각은 세지 않는다."""
    ct = re.sub(r"[^가-힣A-Za-z0-9]", "", text or "")
    grams = set()
    for part in re.split(r"\{[^}]*\}", phrase or ""):
        c = re.sub(r"[^가-힣A-Za-z0-9]", "", part)
        grams |= {c[i:i + 4] for i in range(max(0, len(c) - 3))} or ({c} if c else set())
    return sum(1 for g in grams if g in ct) / len(grams) if grams else 1.0


# ★씨앗 결(A안) 틀 — 옛 작가가 쓰던 히트작 실측 틀을 되살린다(2026-09-28 사장님 "씨앗 결 이야기는 왜 이렇게 짧고 부실해?").
#   새 작가가 A안에 "씨앗 흐름을 칸으로" 한 줄만 줘서 10작업이 5~6줄·173~260자·고조 0~1줄로 나왔다(옛 A안 8~11줄·272~341자·고조 6줄).
#   칸 크기 = 썰 히트작 49편 실측(옛 SHORT_BLOCK) · 고조는 2칸, 칸마다 순간 → 지옥 → 없애 버렸다는 거.
SEED_FRAME = {
    "yt": {"roles": ["훅", "미끼", "공개", "고조1", "고조2", "반전", "마무리"], "gojo": {"고조1": 3, "고조2": 3},
           "rows": ["훅: 씨앗 첫 줄의 꼴을 빌려 새로(약 16자)",
                    "미끼: 누가·어디서 난리 났는지 궁금하게(약 53자)",
                    "공개: 이건 바로 (제품) (약 11자)",
                    "고조1: 【3줄】 ①\"이게 말도 안 되는게\" + 그 순간(기존 것과 달리·무엇을 하다가) ②그때 벌어지던 지옥(~하던 그 지옥을) "
                    "③제품이 그걸 없애 버린 것(~로 싹 없애 버렸다는 거) — 합쳐 약 80자",
                    "고조2: 【3줄】 ①\"심지어\" + 또 다른 순간 ②그때의 불편 ③없애 버린 것 — 합쳐 약 39~60자",
                    "반전: \"근데 진짜 충격적인 포인트는\" + 재료에서 가장 센 특징(약 48자)",
                    "마무리: 짧게 한마디(약 12자)"]},
    "ig": {"roles": ["훅", "상황", "고조1", "고조2", "소감", "댓글유도"], "gojo": {"고조1": 2, "고조2": 2},
           "rows": ["훅: 겪은 일로 여는 첫마디(감탄 가능)",
                    "상황: 누구에게서·어디서 알게 됐나(친구·언니·남편 같은 인물, 간접화법)",
                    "고조1: 【2줄】 ①이걸 모를 때 어떻게 하고 있었나(그 장면과 짜증) ②쓰고 나서 어떻게 달라졌나(기능 말고 장면으로)",
                    "고조2: 【2줄】 ①또 다른 불편했던 장면 ②달라진 장면",
                    "소감: 생활의 장면으로 한 줄",
                    "댓글유도: 이 제품에 맞는 말 + 댓글에 '낱말' 남겨주세요"]},
}


def frame_of(sp, key="", platform="yt"):
    """스타일(스파인) → 틀. sp가 None이면 씨앗 결(씨앗 대본의 흐름이 곧 틀).
    돌려주는 것: {name, roles(칸 순서 — 씨앗 결이면 None), block(프롬프트에 싣는 틀 글), pinned(공통 칸 고정 문장)}"""
    if not sp:
        f = SEED_FRAME.get(platform) or SEED_FRAME["yt"]
        return {"name": "씨앗 결 이야기", "roles": list(f["roles"]), "gojo": dict(f["gojo"]), "pinned": {},
                "block": "씨앗 결 이야기 — [씨앗 대본]의 말투를 따르되 아래 칸 순서·크기로 쓴다\n" + "\n".join("  " + r for r in f["rows"])}
    tpl = sp.get("templates") if isinstance(sp.get("templates"), dict) else {}
    roles = [str(r) for r in (sp.get("beat_roles") or []) if str(r).strip()] or [k for k in tpl if tpl.get(k)]
    pinned = common_lines(sp, key)
    skel = skeleton_lines(sp, key)
    yt = bool(sp.get("no_cta"))
    rows = []
    for r in roles:
        if r in pinned:
            rows.append("  %s: 【그대로】「%s」 — 이 문장은 글자 그대로 쓴다" % (r, pinned[r]))
            continue
        line = ("  %s: 뼈대 「%s」" % (r, skel[r])) if r in skel else ("  %s: (예시 없음)" % r)
        if yt and r in GOJO3:
            line += " — 【고조 3줄】 ①그 순간(언제·무엇을 하다가) ②그때 벌어지던 불편 ③이 제품이 그걸 없애 버린 것. 이 칸 이름으로 3줄"
        elif yt and r in GOJO_OPEN:
            line += " — 【고조 2줄】 ①그 순간 ②그때 벌어지던 불편(없애 버림은 다음 칸이 맡는다). 이 칸 이름으로 2줄"
        rows.append(line)
    return {"name": sp.get("name") or "", "roles": roles, "pinned": pinned,
            "gojo": {r: (3 if r in GOJO3 else 2) for r in roles if yt and (r in GOJO3 or r in GOJO_OPEN)},
            "block": "%s\n%s" % (sp.get("name") or "", "\n".join(rows)),
            # 베낌 검사는 화면에 보여준 2개만이 아니라 그 칸의 예시 전부와 댄다
            "examples": {r: [x for x in (tpl.get(r) or []) if isinstance(x, str) and x.strip()] for r in roles},
            # ★유튜브 썰 스타일은 예시가 히트작 관용구(시그널)다 — 그대로 쓰는 게 맞다(베낌 검사 제외).
            #   근거: 이븐쇼핑 22편 `천재` 22/22·`최근` 21/22·`말도 안 되는` 21/22·`이건 바로` 17/22, 관용구는 261→1242편으로
            #   재료를 4.8배 늘려도 +3개뿐(포화) — handoff/장면분량.md "조사 결과". 사장님 09-22 "시그널에는 같은 단어를 쓰는게
            #   맞아, 사람들이 익숙하고 좋아하는 지점"(tools/seed_analyzer/signal_sets.py). 변형은 인스타 스타일만(09-27).
            "keep_idioms": bool(sp.get("no_cta"))}


def _collapse(roles):
    out = []
    for r in roles:
        if not out or out[-1] != r:
            out.append(r)
    return out


def styled_problems(out, frame, seg_index, seed_text="", product="", seconds=25, avoid_text=""):
    """한 번 호출 결과의 검사(코드는 고치지 않고 **무엇이 틀렸나**만 말한다 → 다시 쓰기 지시로 쓴다)."""
    from shopping_shorts import script_gate
    lines = [L for L in (out or {}).get("lines") or [] if (L.get("text") or "").strip()]
    probs = []
    if len(lines) < MIN_STYLED_LINES:
        return ["대본이 %d줄뿐이다 — 칸을 다 채워라" % len(lines)]
    roles = frame.get("roles")
    if roles:
        got = _collapse([str(L.get("role") or "") for L in lines])
        if got != roles:
            probs.append("칸 순서가 틀이 아니다 — 나온 순서 %s / 틀 %s. 틀의 칸을 빠짐없이 순서대로" % (" → ".join(got), " → ".join(roles)))
    n_open = 2 if roles else 1
    exs = {} if frame.get("keep_idioms") else (frame.get("examples") or {})
    pinned = frame.get("pinned") or {}
    for r, ph in pinned.items():
        mine = [L for L in lines if str(L.get("role")) == r]
        if mine and _pin_share(ph, mine[0].get("text")) < PIN_SHARE:
            probs.append("%s 칸은「%s」을 글자 그대로 써야 한다" % (r, ph))
    for r, n in (frame.get("gojo") or {}).items():
        k = sum(1 for L in lines if str(L.get("role")) == r)
        if k and k < n:
            probs.append("%s 칸은 고조 %d줄(순간 → 불편%s)인데 %d줄뿐이다" % (r, n, " → 없애 버림" if n == 3 else "", k))
    for i, L in enumerate(lines):
        if REAL_PERSON.search(L.get("text") or ""):
            probs.append("%d번 줄에 실존 인물 이름이 있다 — 보통명사(요리사·주부 등)로" % (i + 1))
        if str(L.get("role")) in pinned:
            continue                      # 고정 문장 칸은 예시를 쓰는 게 맞다
        for x in exs.get(str(L.get("role")), []):
            if _gram_share(L.get("text"), x) >= TEMPLATE_COPY_SHARE:
                probs.append("%d번 줄이 틀 예시「%s」를 거의 그대로 옮겼다 — 뼈대만 두고 말을 바꿔라" % (i + 1, x))
                break
    open_roles = set(roles[:2]) if roles else set()
    pts = [str(p) for p in (out or {}).get("seed_points") or [] if str(p).strip()]
    for i, L in enumerate(lines):
        if (roles and str(L.get("role")) in open_roles) or (not roles and i < n_open):
            continue
        hits = _seed_word_hits(L.get("text"), pts, product)
        if len(hits) >= 2:
            probs.append("%d번 줄이 씨앗이 이미 말한 셀링포인트(%s)를 되풀이한다 — 씨앗에 없는 기능·특징·장점으로" % (i + 1, "·".join(hits)))
    bad = [i + 1 for i, L in enumerate(lines) if not [c for c in (L.get("cuts") or []) if c in seg_index]]
    if len(bad) * 3 > len(lines):
        probs.append("%s번 줄에 [재료]에 있는 컷 번호가 없다" % ",".join(map(str, bad)))
    secs = script_gate.est_seconds(" ".join(L["text"] for L in lines))
    if secs > seconds * 1.5:
        probs.append("너무 길다(약 %d초) — %d초 안팎으로 줄여라" % (secs, seconds))
    elif secs < seconds * 0.6:
        probs.append("너무 짧다(약 %d초) — %d초 안팎으로 늘려라" % (secs, seconds))
    if avoid_text and _gram_share(" ".join(L["text"] for L in lines), avoid_text) > AB_MAX_SHARE:
        probs.append("[다른 안]과 문장이 너무 겹친다 — 다른 특징·다른 말로")
    return probs


# 줄 수 하한은 '비었나'만 본다 — 길이는 초(분량 검사)로 잰다. 옛 MIN_LINES(5)는 고정 칸 양식용이라 씨앗 흐름이 4칸인
#   씨앗(b2b1480b3fd8 식기세척기, 4줄·분량은 맞음)을 통째로 버렸다(2026-09-27 check_styled 실측).
MIN_STYLED_LINES = 3
# 줄이 틀 예시 문장을 옮겼나 — 줄의 4글자 조각 중 예시에도 있는 비율. 2026-09-27 사장님 "뼈대는 같아도 변형하면
#   다른 내용처럼 보인다"(사회증거형 6작업이 "주변에서 하나둘 다 이거 쓰길래 저만 모르나 싶었어요"를 거의 그대로 씀).
TEMPLATE_COPY_SHARE = 0.6
COPY_RULE = {
    False: "■ 예시 문장은 **뼈대(말 순서·끝말)만** 빌리고 낱말은 이 제품·이 상황의 말로 바꿔라. 예시를 그대로 옮기면\n"
           "  이 스타일을 고른 모든 영상이 같은 말로 시작하고 끝난다(훅·미끼·마무리처럼 제품과 무관한 칸도 마찬가지).",
    True: "■ 뼈대의 관용구 머리말(최근 딱 봤을 때는·이게 말도 안 되는게·이건 바로·심지어·근데 진짜 충격적인 포인트는)은\n"
          "  히트작 시그널이다 — 그 머리말로 문장을 열고, 머리말 뒤는 [재료]를 보고 이 제품 이야기로 새로 쓴다.",
}
PIN_SHARE = 0.8        # 고정 문장의 글자(빈칸 뺀 것) 4글자 조각 중 줄에 있어야 하는 비율
# 실존 인물 표지 — 목록은 한정적이다(모델이 자주 넣는 이름 위주). 지시문이 1차, 이건 새는 것만 잡는다.
REAL_PERSON = re.compile(r"백종원|이연복|최현석|안성재|에드워드 ?리|고든 ?램지|유재석|강호동|아이유|손흥민|일론 ?머스크|스티브 ?잡스|이재용|정주영")
AB_MAX_SHARE = 0.4      # 두 안의 4글자 조각 겹침 상한(0.4 = 조각 열에 넷이 같다). 실측 근거는 tools/script_diff/check_styled.py


def write_styled(product, seed_text, frame, vis, seg_index, platform="yt", seconds=25, note=None, avoid_text=""):
    """틀 + 씨앗 + 재료 태깅 → 한 번 호출로 줄(role·text·cuts). 검사에 걸리면 이유를 붙여 **한 번** 다시 쓴다
    (문제가 덜한 쪽을 쓴다). note: auth·retry·problems(남은 문제)."""
    from shopping_shorts import script_gate
    note = note if note is not None else {}
    chars = int(seconds * script_gate.SPEECH_CHARS_PER_SEC)
    # ★빈칸 채우기가 아니다(09-21 검증 tools/simple_writer/brief_style.txt: 3.6 Flash 20/20) — 뼈대는 말투·칸 순서의 본보기다.
    frame_rule = ("**빈칸 채우기가 아니다.** [스타일 틀]의 **칸 순서와 말투**를 그대로 따르되, 칸마다 뼈대 문장을 본보기로 삼아 "
                  "[재료]를 보고 이 제품 이야기로 **새로 쓴다**. 【그대로】 줄만 글자 그대로 쓴다. 칸 하나에 1~2줄(고조 칸은 표시된 줄 수), "
                  "role에는 칸 이름을 그대로 적는다. 칸을 빼거나 순서를 바꾸지 마라."
                  if frame.get("roles") else
                  "[씨앗 대본]의 흐름을 그대로 따라 쓴다(문장은 새로). role에는 그 줄이 하는 일(훅·미끼·공개·고조·반전·마무리 등)을 적는다.")
    brief = STYLED_BRIEF % {"frame_rule": frame_rule, "copy_rule": COPY_RULE[bool(frame.get("keep_idioms"))], "open_rule": "앞 두 칸" if frame.get("roles") else "첫 줄",
                            "voice": _VOICE.get(platform, _VOICE["yt"]), "chars": chars, "secs": int(seconds)}
    prompt = "%s\n\n[제품] %s\n\n[씨앗 대본]\n%s\n\n[스타일 틀]\n%s\n\n[재료]\n%s" % (
        brief, product or "(미상)", (seed_text or "").strip()[:1500], frame["block"], source_block(vis))
    if avoid_text:
        prompt += "\n\n[다른 안 — 이것과 다른 특징·다른 문장으로 써라]\n" + avoid_text[:600]
    out = _sg._call_json(prompt, STYLED_SCHEMA, note=note) or {}
    probs = styled_problems(out, frame, seg_index, seed_text, product, seconds, avoid_text)
    if probs:
        n2 = {}
        out2 = _sg._call_json(prompt + "\n\n■ 다시 써라 — 앞 원고의 문제:\n- " + "\n- ".join(probs), STYLED_SCHEMA, note=n2) or {}
        p2 = styled_problems(out2, frame, seg_index, seed_text, product, seconds, avoid_text)
        note["retry"] = probs
        if out2.get("lines") and len(p2) <= len(probs):
            out, probs = out2, p2
    # 빈칸 없는 고정 문장은 코드가 끼운다(모델이 끝내 안 따랐어도 결과는 고정 문장) — 검사가 아니라 결정
    for r, ph in (frame.get("pinned") or {}).items():
        if "{" in ph:
            continue
        for L in out.get("lines") or []:
            if str(L.get("role")) == r:
                if _pin_share(ph, L.get("text")) < PIN_SHARE:
                    L["text"] = ph
                    note["pinned_fixed"] = (note.get("pinned_fixed") or 0) + 1
                break
    note["pinned"] = frame.get("pinned") or {}
    note["problems"] = probs
    note["seed_points"] = [str(p) for p in out.get("seed_points") or [] if str(p).strip()]
    lines = []
    for L in out.get("lines") or []:
        # 틀 글의 「」를 줄에 그대로 옮겨 오는 일이 있다(2026-09-27 실측 25작업 중 4작업) — 읽는 글에 괄호는 없다
        t = re.sub(r"^[「『\"']+|[」』\"']+$", "", (L.get("text") or "").strip()).strip()
        if t:
            lines.append({"role": str(L.get("role") or ""), "text": t,
                          "cuts": [c for c in (L.get("cuts") or []) if c in seg_index]})
    return lines


def make_drafts(spines, job, seconds=25, job_id="", preset="short", seed_text="", seed_product=""):
    """(drafts, why) — app._backbone_drafts와 같은 계약(비면 why에 이유, 조용한 폴백 금지).

    자동 1안(씨앗 결 그대로) + 고른 스타일 1안. 모델 호출 = 안마다 1회(검사에 걸리면 +1회, write_styled).
    ★화면은 씨앗 영상을 안 쓴다(backbone_assemble.assemble과 같은 규칙, 2026-09-21 사장님).

    seed_text/seed_product (2026-09-26): **사용자가 2단계에서 고른 씨앗**의 원문·제품. 씨앗은 화면 재료에서
      빼기(useFootage=false) 때문에 job에 없어서, 종전엔 "job 안에서 가장 긴 한국어 글"이 씨앗 노릇을 했다 —
      실사고 work ea29430903d3: 고른 씨앗은 유튜브 썰(반말)인데 인스타 s5(존댓말 "여러분 다이소에서…")가 씨앗이
      되어 "씨앗 결 이야기"가 다이소 존댓말로 나왔다. 명시값이 오면 그것이 씨앗이고, 없으면 종전 규칙.
    """
    from shopping_shorts import backbone_assemble as ba
    srcs = ba.sources_from_extract((job or {}).get("extract") or {})
    if not srcs:
        return [], "재료 분석(extract)이 아직 없음"
    seed_text = (seed_text or "").strip()
    if len(seed_text) >= 60:
        seed_src = None
        seed_from = "explicit"
        # 고른 씨앗과 같은 글의 영상이 job에도 담겨 있으면 그건 화면에서 뺀다(씨앗 화면 금지 규칙 그대로)
        key = _norm_text(seed_text)
        vis = [s for s in srcs
               if _norm_text(s.get("full_text_ko") or s.get("full_text")) != key]
        product = (seed_product or "").strip()
    else:
        seed_src = ba.seed_source(srcs, (job or {}).get("backbone_main"))
        seed_text = ((seed_src or {}).get("full_text_ko") or (seed_src or {}).get("full_text") or "").strip()
        if len(seed_text) < 60:
            return [], "씨앗 영상의 말이 너무 짧음(%d자)" % len(seed_text)
        seed_from = "job:%s" % (seed_src.get("video_id") or "")
        vis = ba._drop_seed(srcs, seed_src)
        product = ((seed_src.get("source_brief") or {}).get("product") or "").strip()
    seg_index = ba._seg_index(vis)
    if not seg_index:
        return [], "재료 컷이 없음(씨앗 말고 담긴 영상이 없다)"
    preset = preset if preset in LENGTH_PRESETS else "short"
    if preset != "short":
        seconds = LENGTH_PRESETS[preset]["seconds"]
    # ★안마다 한 번 호출(write_styled). 자동 1안 = 씨앗 결(씨앗 흐름이 틀), 2안 = 고른 스타일의 칸 틀.
    #   두 번째 안은 첫 안을 [다른 안]으로 받아 다른 특징·다른 말로 쓴다(A·B 똑같음 방지 — 검사 AB_MAX_SHARE).
    plans = [(None, seed_platform(seed_text))]
    for sp in (spines or [])[:1]:
        plans.append((sp, "yt" if sp.get("no_cta") else "ig"))
    drafts, whys, prev_text = [], [], ""
    for sp, plat in plans:
        frame = frame_of(sp, job_id or product, platform=plat)
        name = frame["name"]
        n = {}
        lines = write_styled(product, seed_text, frame, vis, seg_index, platform=plat, seconds=seconds,
                             note=n, avoid_text=prev_text)
        if len(lines) < MIN_STYLED_LINES:
            whys.append("%s: 대본이 %d줄뿐(%s)" % (name, len(lines), n.get("reason") or "; ".join(n.get("problems") or []) or "빈 응답"))
            continue
        bs = [{"role": L["role"], "seg": (L["cuts"] or [""])[0], "segs": list(L["cuts"])} for L in lines]
        no_cut = _share_cuts(lines, bs, seg_index)     # 컷을 못 적은 줄만 남는 컷을 빌린다
        meta = {"product": product, "spine": {"id": (sp or {}).get("id"), "name": name}, "note": n}
        d = ba.to_draft("\n".join(L["text"] for L in lines), bs, meta)
        d["made_by"] = "이야기작가"
        d["length_preset"] = preset
        d["auto_pick"] = sp is None
        d["platform"] = plat
        d["seed_from"] = seed_from          # 점검용: 씨앗이 고른 영상(explicit)인가 job 대체(job:vid)인가
        d["writer_note"] = {k: v for k, v in (("writer", "한번호출"), ("auth", n.get("auth")), ("retry", n.get("retry")),
                                               ("problems", n.get("problems")), ("no_cut_lines", no_cut),
                                               ("pinned", n.get("pinned")), ("pinned_fixed", n.get("pinned_fixed"))) if v}
        d["seed_points"] = n.get("seed_points") or []   # 점검용: 씨앗이 이미 말한 셀링포인트(차별점 잣대)
        drafts.append(d)
        prev_text = prev_text or d.get("script") or ""
    return drafts, "; ".join(whys)
