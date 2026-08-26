# -*- coding: utf-8 -*-
"""스파인 문장 변형 늘리기 — **파일로만 뽑는다. DB는 안 건드린다.**

왜: 조립 경로가 templates에서 문장을 고르는데 후보가 너무 적다.
    실측(2026-08-21) 70개 칸 중 37개(53%)가 후보 2개 이하 → 회전을 넣어도 돌 문장이 없다.

원칙(어긴 결과가 곧 나쁜 대본이다):
  · 슬롯은 **그 칸에 이미 쓰인 것만** 쓴다. 새 슬롯을 만들면 재료가 없어 그 문장은
    영영 안 걸린다(usable_templates가 거른다) — 늘려도 늘어난 게 아니다.
  · 슬롯이 **하나도 없는 변형을 최소 1개** 포함한다. 재료가 모자란 영상에서도 칸이 찬다.
  · 고조어('심지어' 등)는 escalation/escalate 칸에서만. 다른 칸에 넣으면 script_gate가
    "고조 정확히 1회" 규칙으로 반려한다(2026-08-21 실사고와 같은 함정).
  · cta는 헌장 고정 — '받는 것 명시형'. 없는 할인·한정수량 지어내기 금지.

쓰는 법:
  py scripts/expand_spine_templates.py            # 전체(승인 스파인)
  py scripts/expand_spine_templates.py --spine 59 # 하나만
  py scripts/expand_spine_templates.py --want 8   # 칸당 목표 개수(기본 6)
결과: out/spine_templates_expand.json  +  out/spine_templates_expand.md(검수용)
"""
import argparse, json, os, re, sqlite3, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopping_shorts.edit_plan import _vault_call

SLOT_RE = re.compile(r"\{([^}]+)\}")
ESCALATION_ROLES = {"escalation", "escalate"}

SCHEMA = {
    "type": "object",
    "properties": {
        "variants": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["variants"],
}


def db_path():
    for p in ("shopping_shorts/data/reference.db", "shopping_shorts/data/app.db"):
        if os.path.exists(p):
            try:
                c = sqlite3.connect(p)
                if c.execute("SELECT count(*) FROM spine WHERE status='approved'").fetchone()[0]:
                    return p
            except Exception:
                pass
    return ""


def load_spines(path, only_id=None):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    out = []
    for r in c.execute("SELECT * FROM spine WHERE status='approved'"):
        roles = json.loads(r["beat_roles_json"] or "[]")
        if not roles:
            continue
        if only_id and int(r["id"]) != int(only_id):
            continue
        out.append({
            "id": r["id"], "name": r["name"], "situation_type": r["situation_type"] or "",
            "beat_roles": roles, "templates": json.loads(r["templates_json"] or "{}"),
            "beat_chain": json.loads(r["beat_chain_json"] or "[]"),
            "emotion_arc": r["emotion_arc"] or "", "appeal": r["appeal"] or "",
            "chars_per_30s": r["chars_per_30s"],
        })
    return out


def build_prompt(sp, role, existing, want):
    slots = sorted({m for t in existing for m in SLOT_RE.findall(t)})
    lens = [len(t) for t in existing] or [40]
    lo, hi = max(12, min(lens) - 8), max(lens) + 12
    rules = [
        "· 한국어 구어체. 실제 숏폼에서 말하듯 자연스럽게.",
        "· 기존 문장들과 **같은 역할·같은 톤**을 유지한다. 새로운 정보를 지어내지 않는다.",
        "· 빈칸은 %s 만 쓴다. **다른 빈칸을 새로 만들지 마라**(재료가 없어 안 쓰인다)." % (
            ", ".join("{%s}" % s for s in slots) if slots else "(없음 — 빈칸 없이 쓴다)"),
        "· 빈칸을 **하나도 안 쓰는 변형을 최소 1개** 넣어라(재료가 모자란 영상에서도 쓰이게).",
        "· 길이는 %d~%d자." % (lo, hi),
        "· 기존 문장과 **같은 말을 다르게 쓴 것**이면 안 된다 — 표현·어순·진입 방식이 실제로 달라야 한다.",
    ]
    if role in ESCALATION_ROLES:
        rules.append("· 이 칸은 '고조'다. '심지어·더 대박인 건' 같은 고조 연결어를 **정확히 1개** 넣어라.")
    else:
        rules.append("· '심지어' 같은 고조 연결어는 **쓰지 마라**(고조 칸에만 허용된다).")
    if role == "cta":
        rules.append("· 댓글에 무엇을 남기면 **무엇을 받는지** 반드시 말한다. "
                     "'남겨주세요'로만 끝내지 마라. 없는 할인·한정수량은 지어내지 마라.")
    where = ""
    if sp["beat_chain"]:
        where = "이 갈래의 서사: " + " / ".join(sp["beat_chain"][:6])
    return (
        "너는 한국 숏폼(릴스·쇼츠) 대본 작가다.\n"
        "'%s' 스타일의 '%s' 칸에 쓸 문장 변형을 만든다.\n\n"
        "[스타일] %s\n%s\n[감정선] %s\n\n"
        "[이 칸의 기존 문장]\n%s\n\n"
        "[규칙]\n%s\n\n"
        "기존 것과 겹치지 않는 새 변형 %d개를 variants 배열로만 답하라."
        % (sp["name"], role, sp["situation_type"], where, sp["emotion_arc"],
           "\n".join("- " + t for t in existing), "\n".join(rules), want)
    )


def clean(variants, existing, allowed_slots, role):
    """모델이 규칙을 어긴 것을 여기서 거른다 — 프롬프트만 믿지 않는다."""
    seen = {re.sub(r"\s+", "", t) for t in existing}
    out, dropped = [], []
    for v in variants or []:
        v = re.sub(r"\s+", " ", str(v or "")).strip().strip('"').strip("'")
        key = re.sub(r"\s+", "", v)
        if not v or key in seen:
            dropped.append((v, "중복")); continue
        used = set(SLOT_RE.findall(v))
        bad = used - allowed_slots
        if bad:
            dropped.append((v, "없는 빈칸 " + ",".join(sorted(bad)))); continue
        esc = len(re.findall(r"심지어|더 대박인 건|더 놀라운 건", v))
        if role in ESCALATION_ROLES and esc != 1:
            dropped.append((v, "고조어 %d회(1회여야)" % esc)); continue
        if role not in ESCALATION_ROLES and esc:
            dropped.append((v, "고조 칸이 아닌데 고조어")); continue
        seen.add(key); out.append(v)
    return out, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spine", type=int, default=None)
    ap.add_argument("--from-json", default="", dest="from_json",
                    help="reference.db 대신 /api/script/styles 형태의 JSON에서 읽는다"
                         "(라이브 DB가 서버에만 있고 276MB라 로컬로 못 받는다)")
    ap.add_argument("--want", type=int, default=6, help="칸당 목표 후보 수(기존 포함)")
    a = ap.parse_args()

    if a.from_json:
        d = json.load(open(a.from_json, encoding="utf-8"))
        spines = [{"id": x["id"], "name": x["name"],
                   "situation_type": x.get("situation_type") or "",
                   "beat_roles": x.get("beat_roles") or [],
                   "templates": x.get("templates") or {},
                   "beat_chain": x.get("beat_chain") or [],
                   "emotion_arc": x.get("emotion_arc") or "",
                   "appeal": x.get("appeal") or "",
                   "chars_per_30s": x.get("chars_per_30s")}
                  for x in (d.get("styles") or [])
                  if (x.get("beat_roles") and (not a.spine or int(x["id"]) == a.spine))]
        print("JSON=%s / 스파인 %d개" % (a.from_json, len(spines)))
    else:
        path = db_path()
        if not path:
            print("승인 스파인이 있는 DB를 못 찾았습니다 — --from-json 을 쓰거나 "
                  "서버에서 shopping_shorts/data/reference.db를 받아오세요"); return 1
        spines = load_spines(path, a.spine)
        print("DB=%s / 스파인 %d개" % (path, len(spines)))

    result, report = {}, []
    for sp in spines:
        result[str(sp["id"])] = {"name": sp["name"], "roles": {}}
        report.append("\n## [%s] %s\n" % (sp["id"], sp["name"]))
        for role in sp["beat_roles"]:
            existing = list(sp["templates"].get(role) or [])
            need = max(0, a.want - len(existing))
            if not existing or need <= 0:
                report.append("- **%s** — 기존 %d개, 추가 불필요" % (role, len(existing)))
                continue
            allowed = {m for t in existing for m in SLOT_RE.findall(t)}
            raw = _vault_call(build_prompt(sp, role, existing, need + 2), SCHEMA)
            got = (raw or {}).get("variants") if isinstance(raw, dict) else None
            kept, dropped = clean(got, existing, allowed, role)
            kept = kept[:need]
            result[str(sp["id"])]["roles"][role] = {"existing": existing, "new": kept}
            report.append("- **%s** — 기존 %d → +%d개%s" % (
                role, len(existing), len(kept),
                ("  (거른 것 %d: %s)" % (len(dropped), dropped[0][1]) if dropped else "")))
            for v in kept:
                report.append("    - %s" % v)
            print("  %s.%s +%d (거름 %d)" % (sp["id"], role, len(kept), len(dropped)))

    os.makedirs("out", exist_ok=True)
    with open("out/spine_templates_expand.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open("out/spine_templates_expand.md", "w", encoding="utf-8") as f:
        f.write("# 스파인 문장 변형 후보 (검수용)\n"
                "\n승인한 것만 DB에 넣습니다. 빼고 싶은 줄은 지우고 알려주세요.\n"
                + "\n".join(report) + "\n")
    print("\n→ out/spine_templates_expand.json / .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
