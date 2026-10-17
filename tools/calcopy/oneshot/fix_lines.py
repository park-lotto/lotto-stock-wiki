# -*- coding: utf-8 -*-
"""원샷링크딸깍 — 엔진 대본의 '남은 줄만' 사람이 고치고 같은 검사를 다시 돌린다(사장님 10-18 "자동으로 쓰고 검수해서 탈락하면 교정,
그래도 남으면 손으로 — 처음부터 손으로 쓰지 말고").

    PYTHONUTF8=1 py tools/calcopy/oneshot/fix_lines.py <엔진 대본.json> <고침.json>
    고침.json = [{"i": 줄번호(0부터), "text": "새 줄", "facts": ["f1"], "point": "와우", "answer_at": 3, "why": "왜 고쳤나"}, …]
      i 가 기존 줄 수와 같으면 끝에 붙이고, "drop": true 면 그 줄을 뺀다.
검사는 엔진 것을 그대로 부른다(script_engine.check_frame + support_check) — 여기서 새로 판정하지 않는다.
결과: 같은 폴더 대본.json 을 고친 판으로 덮고(원본은 대본_엔진원본.json 으로 한 번만 보관), final.hand_fixes 에 고친 줄·이유를 남긴다.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def apply(engine_json: Path, fixes: list[dict]) -> dict:
    from tools.calcopy.engine import script_engine as SE
    from tools.calcopy.engine import topic_find as TF
    p = Path(engine_json)
    S = json.loads(p.read_text(encoding="utf-8"))
    keep = p.with_name("대본_엔진원본.json")
    if not keep.exists():
        shutil.copyfile(p, keep)
    lines = [dict(l) for l in S["final"]["lines"]]
    for f in sorted(fixes, key=lambda x: -int(x["i"])):
        i = int(f["i"])
        if f.get("drop"):
            lines.pop(i)
            continue
        row = {"text": f["text"].strip(), "facts": f.get("facts") or [], "point": f.get("point") or "", "node": f.get("node") or "",
               "fn": f.get("fn") or f.get("node") or ""}
        if f.get("answer_at") is not None:
            row["answer_at"] = int(f["answer_at"])
        if i >= len(lines):
            lines.append(row)
        else:
            # 고침에 적힌 칸은 빈 값이어도 그대로 덮는다(point:"" = 표시 지우기 — 10-18 실측: 빈 값을 걸러 잉 표시가 안 지워졌다)
            lines[i] = {**lines[i], **{k: row[k] for k in row if k in f or k in ("text", "facts")}}
            if "answer_at" not in f:
                lines[i].pop("answer_at", None)
    frame = SE.find_frame(S.get("slug"))
    for l, kind in zip(lines, SE.shot_kinds_for(lines, frame)):
        l["shot_kind"] = kind
    llm = TF.LLM(budget=2)
    need = [k for k, l in enumerate(lines) if l.get("facts")]
    sup, serr = SE.support_check([lines[k] for k in need], S["facts"], {"points": {}}, llm) if need else ({}, None)
    support = {need[i]: w for i, w in (sup or {}).items()} if sup is not None else None
    chk = SE.check_frame(lines, frame, S["facts"], [], support, None, S["product"])
    if support is None:
        chk["ok"] = False
        chk["global"].append(f"줄↔근거 판정 실패 {serr}")
    # 교정 기록은 회차마다 쌓는다(10-18: 덮어써서 마지막 회차만 남던 것)
    S["final"] = {"lines": lines, "check": chk, "hand_fixes": (S["final"].get("hand_fixes") or []) + ([{"round": len(S["final"].get("hand_fixes") or []) + 1,
                                                                                                    "fixes": fixes}] if fixes else [])}
    S["status"] = "ok" if chk["ok"] else "failed_checks"
    S["hand_fixed"] = True
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"[손 교정] {p} · {'통과' if chk['ok'] else '반려'} {chk['global']} {chk['bad']}")
    for k, l in enumerate(lines):
        print(f"  {k} [{l.get('point') or ''}] {l['text']} {l.get('facts')}")
    return S


if __name__ == "__main__":
    apply(Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
