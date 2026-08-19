"""대본 스타일 실험실 — 생성기(서버에서 실행).

스타일 2개를 골라 같은 소재로 대본 2안을 만들고, **구조를 실제로 지켰는지 게이트로 검사**한다.
지금 라이브(script_generate.generate_mix)는 같은 프롬프트를 n번 굴려 운 좋은 걸 고르는 구조라
3안이 다 비슷할 수 있다. 여기는 스타일별로 프롬프트가 갈리므로 **서로 다른 구조가 보장**된다.

라이브 코드는 한 줄도 안 건드린다 — 여기서 모양을 확정한 뒤에 옮긴다.

실행(서버):
    set -a && . /etc/shopping-shorts.env && set +a
    python3 tools/script_lab/gen.py --styles siworld,silpae --topic "주방 기름때 청소 세제" \
        --facts "뿌리고 닦기만 하면 됨 / 후드 필터도 녹음 / 냄새 적음"
결과: tools/script_lab/out/<타임스탬프>.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

from shopping_shorts.config import SHORTS_GEMINI_KEYS          # noqa: E402
from shopping_shorts import comment_gen                        # noqa: E402
from google.genai import types                                 # noqa: E402

_MODEL = "gemini-3.5-flash"
STYLES_PATH = Path(__file__).with_name("styles.json")

_SCHEMA = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["role", "text"],
            },
        },
    },
    "required": ["beats"],
}


def load_styles():
    return json.loads(STYLES_PATH.read_text(encoding="utf-8"))["styles"]


# ★분량 기준은 **여기 한 곳에서만** 정한다(0순위-B).
#   프롬프트("몇 자 써라")와 게이트("몇 자면 통과")가 따로 계산하면 언젠가 어긋난다 —
#   실제로 게이트만 seconds를 안 곱해서 25초 대본을 30초 기준으로 재고 있었다(2026-08-19).
_DENS_LO, _DENS_HI = 0.9, 1.25
_CHARS_PER_CLAUSE = 14.5          # 다이소 히트작 16편 실측(절당 14.5자)


def density_band(style, seconds):
    """(목표자수, 하한, 상한, 목표절수) — 프롬프트와 게이트가 같이 쓴다."""
    chars = (style or {}).get("chars_per_30s") or int((seconds or 30) * 4.5)
    target = int(chars * max(5, int(seconds or 30)) / 30.0)
    return (target, int(target * _DENS_LO), int(target * _DENS_HI),
            max(3, int(round(target / _CHARS_PER_CLAUSE))))


def build_prompt(style, topic, facts, seconds):
    """스타일의 beats를 **순서대로 못 박아** 프롬프트를 만든다.

    ★핵심: 'AI야 잘 써줘'가 아니라 '이 칸을 이 순서로 채워라'다. 칸 이름(role)을 그대로
    돌려받아야 게이트가 검사할 수 있으므로 role을 출력 스키마에 넣는다.
    """
    lines = []
    for i, b in enumerate(style["beats"], 1):
        t = b.get("templates") or []
        tmpl = ("\n     쓸 수 있는 문장틀(빈칸만 소재에 맞게 채워라): "
                + " / ".join('"%s"' % x for x in t)) if t else ""
        lines.append('  %d) role="%s" — %s%s' % (i, b["role"], b["desc"], tmpl))

    # ★말 밀도는 스타일의 일부다(2026-08-15 실측). 일반 기준(4.5자/초)을 쓰면 30초에 135자가
    #   나오는데, 채이홈 히트작 실측은 264~377자 — **절반 이하**로 눌린다. 빠르게 몰아치는 것
    #   자체가 그 스타일이라, 목표 글자수는 스타일의 실적 대본에서 가져온다.
    # ★"칸 하나에 평균 N자"를 빼고 **절(節) 개수**로 바꿨다(2026-08-19 실측).
    #   다이소 히트작 16편을 재보니 절당 14.5자·13.4절인데 생성물은 13.1자·12절이었다.
    #   칸당 글자수는 칸이 7개면 26자가 나와 "2~3문장씩 써라"와 자기모순이었고, 모델은
    #   작은 숫자 쪽을 따랐다. 절은 문장 단위라 모델이 세기 쉽고 자기모순도 없다.
    # ★"N자 이상"이라고만 시켰더니 첫 시도가 224·251·259·248자로 **줄곧 넘쳤다**.
    #   게이트가 보는 밴드를 그대로 알려준다 — 통과 조건을 숨기고 맞히라고 할 이유가 없다.
    target, lo, hi, clauses = density_band(style, seconds)
    # ⚠️ 아래 반환문은 %-포맷 문자열이다. 프롬프트 본문에 퍼센트 기호를 쓰려면 반드시 %% 로
    #    적어라 — "56%"를 그대로 넣었다가 TypeError로 죽었다(2026-08-19).


    return """너는 한국 인스타 릴스 대본 작가다. 아래 **구조를 순서대로** 지켜 대본을 써라.

[스타일: %s]
%s

[소재] %s
[사실 재료(지어내지 마라)] %s

규칙:
- 전체 %d초 분량이다. 한글·숫자만 세어 **%d자~%d자 사이**로 써라(목표 %d자, 이 스타일 히트작의
  실제 밀도다). 이 범위를 벗어나면 되돌려 다시 시킨다 — 넘치는 것도 실패다.
  절(節)이 **%d개쯤** 나와야 한다 — 한 절은 '~는데', '~더니', '~거든요'처럼 끊기는 한 토막이고
  실측 히트작은 한 절이 평균 14~15자다. 짧은 절을 여러 개 이어 붙여 몰아치듯 말해라.
- ★**남의 말을 그대로 옮겨라.** 실측 히트작 16편 중 9편(56%%)이 등장인물의 말을 인용한다
  ("너는 어쩜 새 양말만 사냐고 화를 내시는 거예요" / "그거 한 번에 빼는 방법도 모르냐며").
  요약해서 "혼났어요"라고 쓰지 말고 **그 사람이 한 말을 문장으로 살려라** — 이게 분량과
  현장감을 동시에 만든다.
- 말하듯이 써라. 문어체 금지.
- 각 beat의 role 값을 위와 **똑같이** 돌려줘라(게이트가 검사한다).
- 문장틀이 주어진 role은 그 틀을 쓰되 빈칸만 소재에 맞게 바꿔라. 틀 자체를 새로 짓지 마라.
- 사실 재료에 없는 효능·수치를 지어내지 마라.
""" % (style["name"], "\n".join(lines), topic, facts, seconds, lo, hi, target, clauses)


def gen_once(style, topic, facts, seconds, extra="", max_tries=4):
    prompt = build_prompt(style, topic, facts, seconds) + extra
    last = ""
    if not SHORTS_GEMINI_KEYS:
        return None, prompt, "SHORTS_GEMINI_KEYS 비어있음(/etc/shopping-shorts.env 로드했나?)"
    # 키 로테이션은 element_stats.cluster_element_values와 같은 패턴 — 소진 키는 표시하고 다음으로.
    for _ in range(max_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            last = "키 풀 소진"
            break
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA))
            return json.loads(resp.text), prompt, ""
        except Exception as e:                    # noqa: BLE001 — 키별 실패는 다음 키로
            last = "%s: %s" % (type(e).__name__, e)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            time.sleep(2)
    return None, prompt, last


_REDO_HEAD = "\n\n[재작성 지시 — 방금 쓴 것이 아래를 어겼다. 그대로 고쳐라]\n"
_KEEP = "\n구조·문장틀·구간 순서는 **그대로 두고** 고쳐라."
_TAIL_SHORT = ("\n분량이 모자라면 **등장인물이 한 말을 그대로 인용해** 채워라 "
               "— 요약한 문장('혼났어요')을 실제 대사('너는 어쩜 새 양말만 사냐고 화를 내시는 거예요')로 "
               "바꾸면 분량과 현장감이 같이 는다. 그 다음 상황 묘사를 늘려라." + _KEEP)
_TAIL_LONG = ("\n분량이 넘쳤으면 **설명하는 절부터 지워라** — 효능을 두 번 말한 곳, 부사"
              "('진짜·완전·너무'), 같은 뜻 반복이 먼저다. 대사 인용과 결과 대비는 이 스타일의 "
              "핵심이니 **지우지 마라**." + _KEEP)


def _redo_tail(bad):
    """★실패 방향에 맞는 지시만 붙인다(2026-08-19 실측).

    예전엔 항상 "모자라면 채워라"가 붙어서, **넘쳐서 실패했을 때도 채우라고 시켰다.**
    그래서 재작성이 259자 → 166자 → 252자로 출렁이며 밴드를 못 맞췄다 —
    프롬프트 안에 서로 반대되는 지시가 같이 있으면 모델은 둘 사이를 튕긴다.
    """
    dens = next((c for c in bad if c["name"].startswith("말 밀도")), None)
    if dens is None:
        return _KEEP                       # 밀도는 맞았다 — 분량 얘기를 꺼내지도 마라
    return _TAIL_LONG if "넘겼다" in dens["detail"] else _TAIL_SHORT


def gen_one(style, topic, facts, seconds, rewrites=2):
    """★게이트가 실패를 잡으면 **자동으로 다시 쓴다**(2026-08-15).

    프롬프트로 '길게 써라'라고 부탁만 했더니 목표 300자에 117자(1차) → 203자(2차)로
    여전히 미달이었다. 부탁은 복불복이고 되돌리는 것만이 확정이다. 그래서 실패한
    검사 항목을 **그대로 지시문에 실어** 다시 요청한다. 그래도 안 되면 실패로 남긴다
    — 조용히 통과시키지 않는다(그게 지금 라이브의 병이다).
    """
    extra, res, prompt, err, tries = "", None, "", "", []
    for _ in range(rewrites + 1):
        res, prompt, err = gen_once(style, topic, facts, seconds, extra)
        if not res:
            break
        checks, full = check(style, res, seconds)
        tries.append({"chars": len(_norm(full)),
                      "fails": [c["name"] for c in checks if not c["ok"]]})
        if all(c["ok"] for c in checks):
            break
        bad = [c for c in checks if not c["ok"]]
        extra = (_REDO_HEAD
                 + "\n".join("- %s: %s" % (c["name"], c["detail"]) for c in bad)
                 + _redo_tail(bad))
    return res, prompt, err, tries


# ---------------- 게이트: 구조를 실제로 지켰는가 ----------------

def _norm(s):
    return re.sub(r"[\s\.,!?~]+", "", s or "")


def _template_matches(text, templates):
    """문장틀의 빈칸을 느슨한 정규식으로 바꿔 실제 문장이 그 틀인지 본다.

    ★빈칸을 먼저 쪼갠 뒤 조각만 이스케이프한다(2026-08-15). 통째로 re.escape하면 중괄호가
      이스케이프되고, 그걸 다시 치환할 때 앞의 백슬래시가 남아 리터럴 점이 돼 절대 안 맞는다
      — 실측: 틀을 지킨 문장을 FAIL로 잡았다.
    ★빈칸 뒤 조사는 받침에 따라 바뀐다("{제품}이라고" → "세제라고"). 빈칸 다음 조각의 맨 앞
      조사 한 글자는 있으나 없으나 통과시킨다 — 조사까지 강제하면 맞는 문장을 튕긴다.
    """
    josa = ("이", "가", "은", "는", "을", "를", "라", "과", "와")
    for t in templates:
        parts = []
        for i, p in enumerate(re.split(r"\{[^}]*\}", t)):
            n = _norm(p)
            if i > 0 and n[:1] in josa:
                n = n[1:]
            parts.append(re.escape(n))
        pat = ".{0,16}".join(x for x in parts if x)
        if pat and re.search(pat, _norm(text)):
            return True
    return False


def check(style, result, seconds=30):
    """불변식 검사 — 안 지키면 '재작성 대상'으로 표시한다(부탁이 아니라 판정)."""
    beats = (result or {}).get("beats") or []
    got = [b.get("role", "") for b in beats]
    want = [b["role"] for b in style["beats"]]
    checks = [{"name": "구간 순서", "ok": got == want,
               "detail": "기대 %s / 실제 %s" % (want, got)}]

    for want_b in style["beats"]:
        tmpl = want_b.get("templates") or []
        if not tmpl:
            continue
        hit = [b for b in beats if b.get("role") == want_b["role"]]
        text = hit[0].get("text", "") if hit else ""
        checks.append({"name": "%s 문장틀 준수" % want_b["role"],
                       "ok": bool(text) and _template_matches(text, tmpl),
                       "detail": text[:60] or "(해당 role 없음)"})

    full = " ".join(b.get("text", "") for b in beats)
    # ★라이브(script_gate.check)는 이미 어간 '남겨주'로 본다. 여기만 "남겨주세요"로 남아
    #   있어서 정답인 "댓글에 OO 남겨주시면 ~ 보내드릴게요"를 FAIL로 잡았다(2026-08-19 실측).
    #   같은 판단이 두 군데 적혀 어긋난 전형(0순위-B) — 라이브 기준에 맞춘다.
    checks.append({"name": "CTA 단어유도", "ok": "남겨주" in _norm(full),
                   "detail": full[-40:]})
    # ★버그 2건 수정(2026-08-19 실측).
    #  ① seconds를 무시했다 — chars_per_30s를 **30초 기준 그대로** 하한에 썼다.
    #     25초 대본을 시켜놓고(목표 188자) 30초 기준 158자를 하한으로 봤고, 15초를
    #     시키면 목표 113자인데 하한이 158자라 **절대 통과 못 하는** 구간이 생긴다.
    #     프롬프트의 target과 같은 식(chars*seconds/30)으로 맞춘다.
    #  ② 하한 0.7배가 너무 헐거웠다 — 목표의 86%만 써도 PASS라 **재작성 루프가 안 돌았다**.
    #     실측: 히트작 절당 14.5자·13.4절인데 생성물은 13.1자·12절로 전 구간 10% 미달.
    #     구조 결함이 아니라 균일한 미달이라, 되돌려 다시 시키면 채워진다 → 하한을 올린다.
    #     천장은 1.4→1.25. 길게 쓰는 건 영상 길이를 넘기는 문제라 여기도 조인다.
    tgt, lo, hi, _ = density_band(style, seconds)   # ← 프롬프트와 같은 함수(0순위-B)
    n = len(_norm(full))
    _d = ("%d자 — %d자에 모자란다. **%d자 이상**으로 채워라. 히트작은 이 시간에 그만큼 말한다."
          % (n, lo, lo)) if n < lo else (
         ("%d자 — %d자를 넘겼다. %d자 이하로 줄여라." % (n, hi, hi)) if n > hi
         else "%d자 (목표 %d자)" % (n, tgt))
    checks.append({"name": "말 밀도(%d~%d자)" % (lo, hi), "ok": lo <= n <= hi, "detail": _d})
    return checks, full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles", required=True, help="쉼표로 2개 (예: siworld,silpae)")
    ap.add_argument("--topic", default="")
    ap.add_argument("--facts", default="")
    # ★진짜 쓰임새(2026-08-15 사장님): 스타일은 채이홈에서 뽑았지만 **소재는 다른 영상**이다.
    #   담긴 영상의 전사(script_extracts)를 재료로 넣고 그 스타일로 쓰게 해야 쓸모가 있다.
    ap.add_argument("--source", default="", help="소재로 쓸 영상 shortcode(script_extracts에서 읽음)")
    ap.add_argument("--seconds", type=int, default=30)
    args = ap.parse_args()

    if args.source:
        import sqlite3
        from shopping_shorts.config import DB_PATH
        conn = sqlite3.connect("file:%s?mode=ro" % DB_PATH, uri=True)
        row = conn.execute("select script_json from script_extracts where shortcode=?",
                           (args.source,)).fetchone()
        if not row:
            print("그 shortcode의 전사가 없다:", args.source)
            return 1
        src = json.loads(row[0])
        # 소재 = 그 영상이 실제로 말한 것. 훅·CTA 같은 '스타일'은 우리 스타일이 정하므로
        # 여기서는 **사실 재료만** 뽑아 넘긴다(문장을 통째로 베끼면 표절이고 스타일도 섞인다).
        benefits = []
        for b in src.get("segments") or []:
            benefits += [x for x in (b.get("product_benefits") or []) if x]
        seen, uniq = set(), []
        for b in benefits:
            if b not in seen:
                seen.add(b); uniq.append(b)
        args.facts = args.facts or " / ".join(uniq[:8]) or (src.get("full_text") or "")[:300]
        args.topic = args.topic or (src.get("subject") or args.source)
        print("[소재] %s (%s)" % (args.topic, args.source))
        print("[사실 재료] %s" % args.facts[:200])
    if not args.topic:
        print("--topic 또는 --source 가 필요하다")
        return 1

    all_styles = {s["id"]: s for s in load_styles()}
    picked = [all_styles[i.strip()] for i in args.styles.split(",") if i.strip() in all_styles]
    if not picked:
        print("스타일을 못 찾음. 가능한 id:", ", ".join(all_styles))
        return 1

    out = {"topic": args.topic, "facts": args.facts, "seconds": args.seconds, "drafts": []}
    for st in picked:
        t0 = time.time()
        res, prompt, err, tries = gen_one(st, args.topic, args.facts, args.seconds)
        checks, full = check(st, res, args.seconds) if res else ([], "")
        passed = bool(checks) and all(c["ok"] for c in checks)
        out["drafts"].append({
            "style_id": st["id"], "style_name": st["name"],
            "evidence_views": st.get("evidence_views") or [],
            "source": st.get("source", ""),
            "beats": (res or {}).get("beats") or [], "full_text": full,
            "checks": checks, "passed": passed, "tries": tries,
            "error": err, "sec": round(time.time() - t0, 1), "prompt": prompt,
        })
        print("[%s] %s %ss 시도%d회 %s %s" % (
            "PASS" if passed else "FAIL", st["name"], out["drafts"][-1]["sec"],
            len(tries), " → ".join("%d자" % t["chars"] for t in tries),
            "" if not err else "오류=" + err), flush=True)
        for c in checks:
            print("    %s %s: %s" % ("O" if c["ok"] else "X", c["name"], c["detail"]), flush=True)

    d = Path(__file__).with_name("out")
    d.mkdir(exist_ok=True)
    p = d / ("%d.json" % int(time.time()))
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장:", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
