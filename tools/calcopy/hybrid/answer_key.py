# -*- coding: utf-8 -*-
"""정답지 검증(볼케이노형 회원 라인, 관제 234·097 2026-10-21) — 집 PC 가 만든 편을 기준으로 회원 경로 결과를 단계마다 대조한다.

    py tools/calcopy/hybrid/answer_key.py cache  <편> --to <캐시 폴더>      # 받아 둔 원본·벤치·재료로 소스 캐시(유튜브 0회 시험용) — 원본 폴더는 복사만
    py tools/calcopy/hybrid/answer_key.py compare <편> --job <회원 작업 폴더> # 합격 표(answer_key_report.md) + 종료코드(0 합격)

정답지 = KEYS[편] (조사.md §1 원본·근거.md 원음 구간·재료·쿠팡 번호). 합격 기준 = 설계 2026-10-21-숏템MCP-볼케이노형-design §8.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import jload  # noqa: E402

KEYS = {
    # 성시경 신라면(10-18 키치잇판) — 받아 둔 원본·재료가 남은 유일한 편(10-21 실측). 쿠팡 번호 없음('쿠팡·마트 어디서나') → 제품은 이름 대조
    "성시경": {
        "src_dir": r"C:\숏템_칼카피\yanshottem\하이브리드_성시경",
        "bench": "sMx9RWuifCA", "origin": "Wy9--jw0ZsM", "product_name": ["신라면"], "coupang": None,
        "orig_spans": [[11.80, 14.82], [15.85, 19.35], [257.2, 259.1]], "materials": ["-o8gedIaYmA", "FaIQ3NIgVbU"],
        "doc": "channel/kitchit/하이브리드_성시경",
    },
    # 잇템로그 ep13 연어 크림(10-24 해외원본형, 잇템로그판_v2 렌더·사장님 대기중) — 관제 263 08 해외원본형 정답지.
    # 한국 재편집 쇼츠가 없는 편(소재후보.json 의 해외 원본에서 바로 만들었다) → 소재 = 해외 원본 MissDarcei 8U0MvYtEAOo, 둘째 원본 = 같은 제품 다른 해외 반응 E7x20fdjn84.
    # E7x20fdjn84 받아 둔 파일은 0~7.5초 구간뿐(mkA_orig — 10-24 VMake 전 원본). 쿠팡 번호는 편에 없음 → 제품은 이름 대조.
    "잇템로그_ep13": {
        "fmt": "해외원본형", "version": "잇템로그판_v2", "src_dir": r"C:\숏템_칼카피\ititemlog\ep13_v3\src",
        "bench": "8U0MvYtEAOo", "origins": ["8U0MvYtEAOo", "E7x20fdjn84"], "product_name": ["메디큐브", "PDRN", "Medicube", "medicube"], "coupang": None,
        "files": {"8U0MvYtEAOo": "d2.mp4", "E7x20fdjn84": "mkA_orig.mp4"},
        "meta": {   # 출처: channel/ititemlog/소재후보.json(10-20 유튜브 API 실측) · ep13 대본 _note·facts f4(E7x20 제목·조회) — 모르는 칸은 비운다(지어내지 않는다)
            "8U0MvYtEAOo": {"title": "Skincare Made Of Salmon WHAT?!?", "channel": "MissDarcei", "upload_date": "20250627", "view_count": 2786775},
            "E7x20fdjn84": {"title": "HAS SKINTOK GONE TOO FAR?", "channel": "milky", "channel_note": "ep13 메모 이름 — 정식 채널 이름 확인 안 함(채널 칸에 한글 메모를 넣으면 is_korean 이 한국 재편집으로 본다)", "upload_date": None, "view_count": 1940000,
                            "note": "받아 둔 파일 = 원본 0~7.5초 구간(mkA_orig)"}},
        "distractors": {   # 같은 제품 다른 반응 후보에 섞는 다른 제품 해외 원본(받아 둔 파일·소재후보 실측 메타) — 판정이 제품을 가르는지
            "Ks61P_NoelQ": r"C:\숏템_칼카피\ititemlog\ep02_v3\src\ks61_orig.mp4", "1fSO371o494": r"C:\숏템_칼카피\ititemlog\ep02_v3\src\darkskin.mp4",
            "ywhirUV8WCA": r"C:\숏템_칼카피\ititemlog\ep02_v3\src\darkest.mp4", "rJh6JD2xSqE": r"C:\숏템_칼카피\ititemlog\ep12_v3\src\daA_orig.mp4"},
        "script_doc": "channel/ititemlog/ep13_salmon_cream_v3", "script_src_map": {"d2.mp4": "8U0MvYtEAOo.mp4", "mkA.mp4": "E7x20fdjn84.mp4"},
        "tts_seed": r"C:\숏템_칼카피\ititemlog\ep13_v3\render",
    },
}


def cache_foreign(name: str, to: Path):
    """해외원본형 정답지 캐시 — yt/<원본 id>.mp4·.info.json · material/<다른 제품 id>.mp4·.info.json · search/_default.json(같은 제품 반응 + 다른 제품) ·
    replay/script_.json(대본 답 = 승인본, 파일 이름만 원본 id 로 — TTS 캐시를 쓰려고) · tts_seed 경로 안내. 원본 폴더는 복사만."""
    K = KEYS[name]
    root = Path(__file__).resolve().parents[3]
    for d in ("yt", "material", "search", "replay"):
        (to / d).mkdir(parents=True, exist_ok=True)
    rows = {r["id"]: r for r in json.loads((root / "channel/ititemlog/소재후보.json").read_text(encoding="utf-8"))["rows"]}
    from tools.calcopy.hybrid.common import probe
    found = []
    for vid, fn in K["files"].items():
        src = Path(K["src_dir"]) / fn
        dst = to / "yt" / f"{vid}.mp4"
        if not dst.exists():
            shutil.copyfile(src, dst)
        w, h, du = probe(dst)
        info = {"id": vid, **K["meta"].get(vid, {}), "duration": round(du, 2), "width": w, "height": h, "_from": "answer_key.KEYS 메타(실측 출처는 KEYS 주석)"}
        (to / "yt" / f"{vid}.info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        if vid != K["bench"]:
            found.append({"id": vid, "title": info.get("title"), "channel": info.get("channel"), "dur": info["duration"], "views": info.get("view_count")})
    for vid, path in K["distractors"].items():
        if not Path(path).exists():
            continue
        dst = to / "material" / f"{vid}.mp4"
        if not dst.exists():
            shutil.copyfile(path, dst)
        r = rows.get(vid) or {}
        info = {"id": vid, "title": r.get("title"), "channel": r.get("channel"), "upload_date": str(r.get("date") or "").replace("-", "") or None,
                "view_count": r.get("views"), "duration": round(probe(dst)[2], 2), "_from": "channel/ititemlog/소재후보.json"}
        (to / "material" / f"{vid}.info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        found.append({"id": vid, "title": info["title"], "channel": info["channel"], "dur": info["duration"], "views": info["view_count"]})
    found = found[1:] + found[:1]          # 정답이 맨 앞에 오지 않게
    (to / "search" / "_default.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    S = json.loads((root / K["script_doc"] / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((root / K["script_doc"] / "재료.json").read_text(encoding="utf-8"))
    mp = K["script_src_map"]
    for l in S.get("lines") or []:
        if l.get("src") in mp:
            l["src"] = mp[l["src"]]
    for cs in (M.get("cuts") or {}).values():
        for c in cs if isinstance(cs, list) else [cs]:
            if c.get("src") in mp:
                c["src"] = mp[c["src"]]
    M.pop("cand_dir", None)
    M["blur"] = {mp.get(k, k): v for k, v in (M.get("blur") or {}).items()}
    G = (root / K["script_doc"] / "근거.md")
    (to / "replay" / "script_.json").write_text(json.dumps({"대본": S, "재료": M, "근거_md": G.read_text(encoding="utf-8") if G.exists() else ""},
                                                            ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"cache": str(to), "tts_seed": K.get("tts_seed"), "files": sorted(p.relative_to(to).as_posix() for p in to.rglob("*") if p.is_file())}, ensure_ascii=False, indent=1))


def cache(name: str, to: Path):
    K = KEYS[name]
    if K.get("fmt") == "해외원본형":
        return cache_foreign(name, to)
    s = Path(K["src_dir"])
    (to / "yt").mkdir(parents=True, exist_ok=True)
    (to / "material").mkdir(parents=True, exist_ok=True)
    (to / "search").mkdir(parents=True, exist_ok=True)
    (to / "channel").mkdir(parents=True, exist_ok=True)
    for f in (s / "bench").glob(f"{K['bench']}*"):
        if f.suffix in (".json", ".vtt", ".mp4"):
            shutil.copyfile(f, to / "yt" / f.name)
    for ext in (".mp4", ".info.json"):
        f = s / "src" / f"{K['origin']}{ext}"
        if f.exists() and not (to / "yt" / f.name).exists():
            shutil.copyfile(f, to / "yt" / f.name)
    found, titles = [], []
    for mid in K["materials"]:
        for f in (s / "src").rglob(f"{mid}*"):
            if f.suffix in (".mp4", ".json") and ".part" not in f.name:
                dst = to / "material" / f.name
                if not dst.exists():
                    shutil.copyfile(f, dst)
    oi = jload(s / "src" / f"{K['origin']}.info.json")
    # 검색·채널 목록 = 원본 1건 + 다른 영상(재료 후보) — 후보가 하나뿐이면 원본 판정이 시험되지 않는다
    found.append({"id": oi["id"], "title": oi.get("title"), "channel": oi.get("channel"), "channel_id": oi.get("channel_id"), "dur": oi.get("duration")})
    titles.append({"id": oi["id"], "title": oi.get("title"), "dur": oi.get("duration")})
    for f in sorted((to / "material").glob("*.info.json")):
        i = jload(f)
        found.append({"id": i["id"], "title": i.get("title"), "channel": i.get("channel"), "channel_id": i.get("channel_id"), "dur": i.get("duration")})
    (to / "search" / "_default.json").write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    (to / "channel" / "_default.json").write_text(json.dumps(titles, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"cache": str(to), "files": sorted(p.relative_to(to).as_posix() for p in to.rglob("*") if p.is_file())}, ensure_ascii=False, indent=1))


def _overlap(a: list, b: list) -> float:
    """원음 구간 겹침 비율(정답 구간 길이 기준)."""
    tot = sum(y - x for x, y in b) or 1
    got = 0.0
    for x, y in a:
        for p, q in b:
            got += max(0.0, min(y, q) - max(x, p))
    return got / tot


def _state(job: Path) -> dict:
    """작업 상태 — 개발 완주(flow_dev)는 flow_state.json, 회원 경로(MCP)는 flow.json 의 서버 서명 payload(본문만 읽는다, 서명은 서버 몫)."""
    if (job / "flow_state.json").exists():
        return jload(job / "flow_state.json")
    import base64
    import zlib
    raw = jload(job / "flow.json")["payload"].split(".")[2]
    return json.loads(zlib.decompress(base64.urlsafe_b64decode(raw.encode())).decode("utf-8"))


def compare(name: str, job: Path) -> int:
    K = KEYS[name]
    st = _state(job)
    rows = []

    def row(stage, what, ok, got, want):
        rows.append((stage, what, "○" if ok else "×", str(got)[:120], str(want)[:120]))
    O = st.get("origin") or {}
    if K.get("fmt") == "해외원본형":
        got = [o.get("id") for o in st.get("origins") or []]
        row("0 형식", "형식", st.get("fmt") == K["fmt"], st.get("fmt"), K["fmt"])
        row("2 원본", "해외 원본 id(순서 무관)", sorted(got) == sorted(K["origins"]), got, K["origins"])
    else:
        row("2 원본", "원본 id", O.get("id") == K["origin"], O.get("id"), K["origin"])
        row("2 원본", "지문 맞은 줄", len(O.get("matched") or []) >= 2, len(O.get("matched") or []), "≥2")
    P = st.get("product") or {}
    if K["coupang"]:
        row("3 제품", "쿠팡 번호", str(P.get("product_id")) == str(K["coupang"]), P.get("product_id"), K["coupang"])
    row("3 제품", "제품 이름", any(w in str(P.get("name") or "") for w in K["product_name"]), P.get("name"), K["product_name"])
    t0 = float(O.get("offset") or 0)
    spans = [[float(s["a"]) + t0, float(s["b"]) + t0] for s in (st.get("research") or {}).get("spans") or []]
    if K.get("orig_spans"):
        ov = _overlap(spans, K["orig_spans"])
        row("4·6 원음", "원음 구간 겹침(정답 대비)", ov >= 0.5, f"{ov:.0%} {spans}", K["orig_spans"])
    S = (st.get("script") or {}).get("S") or {}
    row("7 대본", "대본 줄 수", bool(S.get("lines")), len(S.get("lines") or []), "있음")
    A = st.get("auto") or {}
    row("11 검사", "자동 관문(quality_gate 1단)", bool(A.get("ok")), " · ".join(f"{r.get('what')}{'○' if r.get('ok') else '×'}" for r in A.get("rows") or [] if not r.get("ref")), "전부 ○")
    L = st.get("look") or {}
    row("11 검사", "눈 검수(회원 Claude)", bool(L.get("ok")), L.get("problems"), "ok")
    row("전체", "완성", st.get("phase") == "done", st.get("phase"), "done")
    ok = all(r[2] == "○" for r in rows)
    md = [f"# 정답지 대조 — {name} ({'합격' if ok else '불합격'})", "", "| 단계 | 항목 | | 회원 경로 | 정답지 |", "|---|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows]
    md += ["", f"반려·재시도: {json.dumps(st.get('tries'), ensure_ascii=False)}", f"기록: {json.dumps(st.get('log'), ensure_ascii=False)[:600]}",
           "", "⚠ 눈 검수 ○ 는 회원 Claude 판정 — 집 PC 세션이 완성본 0초 프레임·1초 시트를 직접 보고 확인해야 '됐다'(0순위-A1)."]
    (job / "answer_key_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cache", "compare"])
    ap.add_argument("name")
    ap.add_argument("--to")
    ap.add_argument("--job")
    a = ap.parse_args()
    if a.cmd == "cache":
        cache(a.name, Path(a.to))
    else:
        sys.exit(compare(a.name, Path(a.job)))


if __name__ == "__main__":
    main()
