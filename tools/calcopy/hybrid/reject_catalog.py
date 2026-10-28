# -*- coding: utf-8 -*-
"""반려 사유 전수표(10-27 사장님 "반려할 요소를 다 알고 있나 · 알면 처음부터 안 하게") — 작업 폴더들에 남은 고치기 질문(계획·완성본·대본)을
읽어 사유를 종류별로 세고, 그 종류의 규칙이 **처음 대본·재료 질문(script_*)** 에 들어 있었는지 대조한다. 읽기만 한다.

    PYTHONUTF8=1 py -m tools.calcopy.hybrid.reject_catalog <폴더…> [--ex 3]
    폴더 아래 ask.txt(flow_dev) · request.json(회원 PC shortem_ai) 를 전부 훑는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# (종류, 사유 글 패턴, 처음 질문에 그 규칙이 있나를 볼 열쇠말) — 위에서부터 먼저 맞는 것 하나
KINDS = [
    ("그대로 다시 냄", r"컷 하나도 바뀌지", None),
    ("샷 경계 넘음·전환 걸침", r"원본 샷보다 길다|장면 전환·끊김|장면 전환|샷 끝|원본 장면 경계|들어가는 샷", r"샷 끝을 넘지|샷 표|샷 안에서"),
    ("컷 길이 중앙(너무 김)", r"cut_median|컷 중앙", r"cut_median|컷 길이 중앙|컷 중앙"),
    ("훅 0~3초 컷 경계", r"훅 0\.1~3초", r"훅 0\.1~3초|첫 3초"),
    ("A-B-A 끼움", r"A-B-A|X→Y→X", r"A-B-A|X→Y→X"),
    ("같은 장면 재사용", r"같은 장면|재사용|다시 쓴|거리 3초", r"거리 3초|같은 장면을 다시"),
    ("남의 얼굴", r"얼굴", r"원본 밖.{0,20}얼굴|얼굴.{0,30}(리뷰어|광고 모델)"),
    ("남의 글자·그래픽", r"글자|워터마크|화살표|그래픽|URL|로고", r"남의 (박힌 )?글자|워터마크"),
    ("화면 멈춤", r"멈춤|멈춘 화면|정지|움직임이 없", r"멈춘 화면|정지 화면"),
    ("원본 끝 넘음", r"원본 남음|원본 끝", r"원본 끝|원본 남은"),
    ("완성 길이", r"판 length|완성본 길이|길이 .*판 \d", r"판 length|완성 길이"),
    ("사진 컷", r"사진 컷|photo_share|사진\(그림", r"photo_share_max|사진 컷"),
    ("리듬·꾸밈", r"리듬|꾸밈|덩어리|자막 줄 수", r"리듬"),
    ("출처 규칙", r"출처|source_rule|벤치 쇼츠|다른 출연자", r"출처 규칙|source_rule|출처"),
    ("재료 꼴", r"받은 파일이 아니다|crop|꼴이 틀|cand_dir", r"crop"),
    ("대사↔장면", r"대사와 (화면|장면)|안 맞|see", r"대사의 동작·상태가 그 컷에"),
    ("제품", r"제품", r"제품 컷"),
]
STOP_MARK = ("멈춘 이유(재료를 고쳐라):", "대본 검사에서 걸린 것", "완성본 검사에서 걸린 것", "걸린 것(고쳐라)")


def kind_of(x: str) -> str:
    if x.startswith("대본:"):
        return x.split(" — ")[0]
    for k, pat, _ in KINDS:
        if re.search(pat, x):
            return k
    return "기타"


def _read(f: Path) -> str:
    t = f.read_text(encoding="utf-8", errors="replace")
    if f.suffix == ".json":
        try:
            t = str(json.loads(t).get("prompt") or "")      # 회원 PC shortem_ai 요청 = 질문 글은 prompt 칸
        except (ValueError, AttributeError):
            pass
    return t


def _texts(root: Path):
    """(종류 묶음 이름, 질문 글) — plan·final_fix·script 질문 파일만."""
    for f in list(root.rglob("ask.txt")) + list(root.rglob("request.json")):
        if "_home" in f.parts or "coupang_cache" in f.parts:
            continue
        name = f.parent.name
        grp = "plan" if "plan_" in name else "final" if "final" in name else "script" if "script_" in name else None
        if not grp:
            continue
        yield grp, f, _read(f)


def script_reasons(t: str) -> list[str]:
    """대본 고치기 질문의 '대본 검사에서 걸린 것' = script_audit 결과 JSON 한 줄 → 걸린 칸만 '대본:<kind> — why'(flow.audit_script 의 덧붙인 칸 포함)."""
    i = t.find("## 대본 검사에서 걸린 것")
    if i < 0:
        return []
    line = t[i:].split("\n", 2)[1] if "\n" in t[i:] else ""
    try:
        a = json.loads(line)
    except ValueError:
        return [line[:160]] if line.strip() else []
    out = [f"대본:{r.get('kind')} — {r.get('why')}" for r in a.get("rules") or [] if r.get("ok") is False]
    out += [f"대본:{k} — {str(v)[:120]}" for k, v in a.items() if k in ("title", "claims", "alt_scene", "source_rule", "product_cut", "error") and v]
    return out


def reasons(t: str) -> list[str]:
    """질문 글에서 '멈춘 이유' 칸만 잘라 ; · / 로 나눈다(대본·규칙 본문은 세지 않는다)."""
    if "## 대본 검사에서 걸린 것" in t:
        return script_reasons(t)
    i = max((t.find(m) for m in STOP_MARK), default=-1)
    if i < 0:
        return []
    body = t[i:].split("★한 번에 다 고쳐라")[0].split("\n\n대본:")[0].split("\\n\\n대본:")[0]
    body = body.split(":", 1)[1] if ":" in body[:40] else body
    return [x.strip(" \\n") for x in re.split(r";\s|\s/\s", body) if len(x.strip(" \\n")) > 6]


def first_asks(root: Path) -> list[str]:
    """처음 대본·재료 질문 — 폴더(편)마다 가장 이른 script_* 질문."""
    out = []
    for f in sorted(list(root.rglob("ask.txt")) + list(root.rglob("request.json"))):
        if "script_" in f.parent.name and "_home" not in f.parts:
            out.append(_read(f))
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--ex", type=int, default=2)
    a = ap.parse_args(argv)
    cnt, ex, where = Counter(), defaultdict(list), defaultdict(set)
    firsts = []
    for r in map(Path, a.roots):
        for grp, f, t in _texts(r):
            for x in reasons(t):
                k = kind_of(x)
                cnt[(grp, k)] += 1
                where[k].add(str(r.name))
                if len(ex[k]) < a.ex:
                    ex[k].append(x[:160])
        firsts += first_asks(r)
    print(f"처음 대본·재료 질문 {len(firsts)}편을 대조")
    kinds = sorted({k for _, k in cnt}, key=lambda k: -sum(v for (g, kk), v in cnt.items() if kk == k))
    for k in kinds:
        key = next((kk for kn, _, kk in KINDS if kn == k), None)
        have = sum(1 for t in firsts if key and re.search(key, t))
        by = " ".join(f"{g} {cnt[(g, k)]}" for g in ("script", "plan", "final") if cnt[(g, k)])
        print(f"- {k}: {by} · 편 {len(where[k])} · 처음 질문에 규칙 {have}/{len(firsts)}" + ("" if key else " (해당 없음)"))
        for x in ex[k]:
            print("    · " + x)


if __name__ == "__main__":
    sys.exit(main())
