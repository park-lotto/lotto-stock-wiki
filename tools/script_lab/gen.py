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
    chars = style.get("chars_per_30s") or int(seconds * 4.5)
    target = int(chars * seconds / 30)
    per_beat = max(1, target // max(1, len(style["beats"])))

    return """너는 한국 인스타 릴스 대본 작가다. 아래 **구조를 순서대로** 지켜 대본을 써라.

[스타일: %s]
%s

[소재] %s
[사실 재료(지어내지 마라)] %s

규칙:
- 전체 %d초에 **%d자 안팎**으로 꽉 채워라(이 스타일 히트작의 실제 밀도다).
  칸 하나에 **평균 %d자** — 한 문장으로 끝내지 말고 2~3문장씩 써라. 말이 비면 이 스타일이 아니다.
- 말하듯이 써라. 문어체 금지.
- 각 beat의 role 값을 위와 **똑같이** 돌려줘라(게이트가 검사한다).
- 문장틀이 주어진 role은 그 틀을 쓰되 빈칸만 소재에 맞게 바꿔라. 틀 자체를 새로 짓지 마라.
- 사실 재료에 없는 효능·수치를 지어내지 마라.
""" % (style["name"], "\n".join(lines), topic, facts, seconds, target, per_beat)


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
_REDO_TAIL = ("\n분량이 모자라면 **문장을 더 쪼개고 상황 묘사를 늘려** 채워라. "
              "구조·문장틀은 그대로 두고 살만 붙여라.")


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
        checks, full = check(style, res)
        tries.append({"chars": len(_norm(full)),
                      "fails": [c["name"] for c in checks if not c["ok"]]})
        if all(c["ok"] for c in checks):
            break
        bad = [c for c in checks if not c["ok"]]
        extra = (_REDO_HEAD
                 + "\n".join("- %s: %s" % (c["name"], c["detail"]) for c in bad)
                 + _REDO_TAIL)
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


def check(style, result):
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
    checks.append({"name": "CTA 단어유도", "ok": "남겨주세요" in full,
                   "detail": full[-40:]})
    # ★분량 기준도 스타일별이다 — 히트작 밀도의 70~140%를 벗어나면 그 스타일이 아니다.
    tgt = style.get("chars_per_30s") or 135
    lo, hi = int(tgt * 0.7), int(tgt * 1.4)
    n = len(_norm(full))
    checks.append({"name": "말 밀도(%d~%d자)" % (lo, hi), "ok": lo <= n <= hi,
                   "detail": "%d자 / 이 스타일 히트작 %d자" % (n, tgt)})
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
        checks, full = check(st, res) if res else ([], "")
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
