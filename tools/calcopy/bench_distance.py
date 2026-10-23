# -*- coding: utf-8 -*-
"""벤치와 거리 검사 — 우리 편이 벤치 채널을 베끼지 않았나(표절 관문, 사장님 10-22 "방구석이랑 다르게 · 표절 안 걸리게").

    PYTHONUTF8=1 py tools/calcopy/bench_distance.py <벤치 slug> <대본.json> [--material 재료.json] [--json out.json]

판단 주인 = 이 파일 check() 한 곳. 잡는 것 셋(하나라도 걸리면 실패, 종료 코드 1):
  ① 출처 겹침: 대본 근거(facts url)·재료(url·src 파일 이름)에 벤치 채널 영상 id 가 있다 — 벤치 영상을 소재·화면으로 쓴 것
  ② 문장 겹침: 우리 대본 글(띄어쓰기 뺌)과 벤치 받아쓰기의 가장 긴 같은 토막이 COPY_RUN 자 이상
  ③ 소재 겹침은 실패가 아니다(사장님 10-22 "소재는 같아도 되고 완전 다르게") — 같은 소재 벤치 편을 topic_near 로 알려 준다.
     같은 소재면 그 벤치 편과 문장·구성·화면이 완전히 달라야 하니, Claude 가 그 편을 열어 나란히 본다.
벤치 자료 = channel/<slug>/원자료/titles_all.json(전 편 제목, yt-dlp flat) · 원자료/asr/<id>.json(스피치매틱스 받아쓰기).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COPY_RUN = 12      # 띄어쓰기 뺀 같은 토막 12자 이상 = 문장을 가져온 것(관용구 '알고 보니'·'라고 하더라고요' 는 이보다 짧다)
TOPIC_HIT = 2      # 2자 낱말 2개 이상 또는 3자 이상 낱말(브랜드·제품 꼴 — 10-22 아웃백) 하나가 겹치면 "같은 소재" 알림(실패 아님)
_YT = re.compile(r"(?:v=|youtu\.be/|shorts/|v_)([A-Za-z0-9_-]{11})")


def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def bench(slug: str) -> dict:
    d = ROOT / "channel" / slug / "원자료"
    vids = _j(d / "titles_all.json")["videos"]
    asr = {}
    for f in (d / "asr").glob("*.json"):
        r = _j(f).get("results", [])
        asr[f.stem] = "".join(x["alternatives"][0]["content"] for x in r if x.get("alternatives"))
    return {"ids": {v["id"] for v in vids}, "titles": vids, "asr": asr}


def script_lines(S: dict) -> list[str]:
    fin = S.get("final")
    if isinstance(fin, dict):
        return [l.get("text", "") for l in fin.get("lines", [])]
    if isinstance(fin, list):
        return [l if isinstance(l, str) else l.get("text", "") for l in fin]
    return [l.get("tts") or l.get("text", "") for l in S.get("lines", [])]


def _flat(s: str) -> str:
    return re.sub(r"[\s,.!?~'\"“”‘’·…]", "", s or "")


def _longest(a: str, b: str) -> str:
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return a[m.a:m.a + m.size]


# 소재가 아니라 말버릇인 낱말 — 3자 이상이어도 소재 겹침으로 치지 않는다(10-22 '무조건' 오탐)
STOP = {"무조건", "진짜로", "사람들", "알고보니", "그래서", "때문에", "이렇게", "어떻게", "생각보다", "이유", "진짜", "정체", "충격"}


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", s or "")} - STOP


def check(slug: str, script_path, material_path=None) -> dict:
    B = bench(slug)
    S = _j(script_path)
    blob = json.dumps(S, ensure_ascii=False)
    if material_path:
        blob += json.dumps(_j(material_path), ensure_ascii=False)
    src_hits = sorted({m for m in _YT.findall(blob) if m in B["ids"]})

    ours = _flat("".join(script_lines(S)))
    copies = []
    for vid, txt in B["asr"].items():
        run = _longest(ours, _flat(txt))
        if len(run) >= 6:
            copies.append({"id": vid, "run": run, "chars": len(run)})
    copies.sort(key=lambda c: -c["chars"])

    tw = _words(S.get("topic", "")) | _words(" ".join(S.get("titles", []) if isinstance(S.get("titles"), list) else []))
    near = sorted(({"id": v["id"], "title": v["title"], "hit": sorted(tw & _words(v["title"]))} for v in B["titles"]),
                  key=lambda x: (-max([len(w) for w in x["hit"]] or [0]), -len(x["hit"])))[:5]
    fails = []
    if src_hits:
        fails.append(f"출처 겹침: 벤치 영상 {src_hits} 을 근거·재료로 썼다")
    if copies and copies[0]["chars"] >= COPY_RUN:
        fails.append(f"문장 겹침: '{copies[0]['run']}'({copies[0]['chars']}자) = 벤치 {copies[0]['id']}")
    same_topic = [n for n in near if len(n["hit"]) >= TOPIC_HIT or any(len(w) >= 3 for w in n["hit"])]
    return {"ok": not fails, "fails": fails, "source_hits": src_hits, "copy_top": copies[:3], "topic_near": near, "same_topic": same_topic,
            "bench_asr": len(B["asr"]), "bench_titles": len(B["titles"])}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("script")
    ap.add_argument("--material")
    ap.add_argument("--json")
    A = ap.parse_args(argv)
    r = check(A.slug, A.script, A.material)
    if A.json:
        Path(A.json).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(("통과" if r["ok"] else "실패") + f" — 벤치 받아쓰기 {r['bench_asr']}편·제목 {r['bench_titles']}편과 대조")
    for f in r["fails"]:
        print("  ✗", f)
    print("  가장 긴 같은 토막:", [(c["id"], c["run"]) for c in r["copy_top"]])
    for n in r["same_topic"]:
        print(f"  ! 같은 소재 벤치 편 {n['id']} '{n['title']}' — 이 편과 문장·구성·화면이 완전히 다른지 나란히 본다")
    print("  가까운 벤치 제목(눈 확인):", [(n["title"], n["hit"]) for n in r["topic_near"][:3]])
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
