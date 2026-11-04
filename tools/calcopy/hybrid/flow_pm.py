# -*- coding: utf-8 -*-
"""PC제작형 — 숏클 회원 길을 PC 제작 라인(engine/preset_make)과 같게(사장님 11-03 "그냥 완벽하게 똑같이", handoff/숏클_썰템쇼_PC라인_설계.md).

PC 담당이 썰템쇼 작품1~10을 만든 순서 그대로: 소재 → 근거.md → 원본 → 대본.json → 짤 → 재료.json(자를 칸) → preset_make 계획 → 완성.
- 굽기·검사 = 회원 PC 실행기 c_pm(preset_make.make_one) 한 곳 — 여기는 묻고 받아 넘기기만 한다(판단 두 벌 금지).
- 질문 = PC 노하우 문서 그대로(production_guide 04·05·07 · channel/<slug>/_engine_ready.md · 스타일분석 · 대본 줄판독 · 작품 본보기).
  노하우는 서버에만 있고 회원 PC 에 가지 않는다(engine_bundle 원칙).
- 박힌 글자 = src_crop 으로 잘라 뺀다(흐림 없음) · 쿠팡 단계 없음(PC 10편 쿠팡 0 · 지침서 🛑9).
- 렌더 전에 정하고 렌더는 한 번: 계획(c_pm plan) 관문이 걸린 행만 다시 묻는다.
flow.py 가 FORMAT_STAGES['PC제작형']·FORMAT_PHASES['PC제작형'] 로 이 파일 PHASES 를 등록한다."""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GUIDE = ROOT / "channel" / "production_guide"

STAGES = [("setup", "준비 확인"), ("bench", "소재 확인"), ("research", "근거 조사"), ("material", "원본 모으기"), ("script", "대본 쓰기"),
          ("sign", "짤 고르기"), ("plan", "장면 맞추기"), ("render", "목소리·영상 만들기"), ("check", "완성본 검사"), ("done", "완성")]
MATERIAL_N = [2, 9]          # 원본 영상 개수 — PC 썰템쇼 10편 편마다 2~9개(수리자료 3-3)
SCRIPT_MAX, PLAN_MAX, MAKE_MAX = 4, 8, 2
MEME_PER_TONE = 14


def F():
    from tools.calcopy.hybrid import flow
    return flow


def _doc(p: Path, limit: int = 12000, part: str | None = None) -> str:
    """노하우 문서 — part 를 주면 그 '## ' 절만."""
    try:
        t = Path(p).read_text(encoding="utf-8")
    except OSError:
        return ""
    if part:
        m = re.search(rf"^## {re.escape(part)}.*?(?=^## |\Z)", t, re.S | re.M)
        t = m.group(0) if m else t
    return t[:limit]


def preset_dir(st: dict) -> Path:
    """이 편 판(version)의 회원 프리셋 폴더 — channel/<slug>/preset/<틀>/line.json version 이 같은 것."""
    _, slug = F().flow_format_of(st["version"])
    for lp in sorted((ROOT / "channel" / slug / "preset").glob("*/line.json")):
        if json.loads(lp.read_text(encoding="utf-8")).get("version") == st["version"]:
            return lp.parent
    raise F()._Stop("이 프리셋을 지금 준비할 수 없어요", "다시 시도해 주시면 이어 갈게요", detail=f"{slug} 프리셋 line.json 에 {st['version']} 없음")


def _slug_dir(st) -> Path:
    return preset_dir(st).parents[1]


def _rel_preset(st) -> str:
    return preset_dir(st).relative_to(ROOT).as_posix()


def _examples(st, n: int = 2) -> list[Path]:
    """본보기 작품(PC 납품 — 대본 검사를 통과하는 편부터). 작품 폴더 = channel/<slug>/작품N_*/"""
    from tools.calcopy.hybrid import script_audit as SA
    out = []
    for w in sorted(_slug_dir(st).glob("작품*_*")):
        try:
            r = SA.audit(w / "대본.json", version=st["version"])
        except Exception:  # noqa: BLE001 — 못 재는 편은 본보기에서 뺀다
            continue
        if all(x["ok"] for x in r["rules"]) and (w / "근거.md").exists():
            out.append(w)
        if len(out) >= n:
            break
    return out


# ── 소재 ────────────────────────────────────────────────────────────────
TOPIC = """너는 이 채널(PC 제작 담당과 같은 일을 한다)의 소재 판독 담당이다. 아래 소재 쇼츠(벤치 영상)를 보고 우리 편의 이야기 대상을 정한다.
PC 제작 순서(01 소재)를 그대로 따른다:
{guide}

답: {{"topic": "한 줄(무엇이 왜 화제인가)", "product": "이야기 대상 제품·물건 이름(정식 이름)", "queries": ["원본 영상 유튜브 검색어(영어·현지어·한국어 섞어 3~6개)"],
"research_words": ["근거 찾을 낱말(브랜드·제조사·사건 이름)"]}}"""


def p_bench(st, m, rp, u):
    """소재 영상이 있으면 공용 받기, 주제 시작(#3207 — 쿠팡 제품+주제)이면 받을 것 없이 바로 소재 판독."""
    if st.get("ref"):
        return F().ph_bench(st, m, rp, u)
    st["bench"], st["bench_lines"] = {}, []
    ask = TOPIC.format(guide=_doc(GUIDE / "01_topic.md", 4000)) + "\n\n소재 영상 없음 — 회원이 준 주제: " + st["given_topic"] + \
        ("\n회원이 정한 제품: " + st["given"] if st.get("given") else "")
    return {"review": [F()._rv("pm_topic", ask, [], need=("topic", "product", "queries", "research_words"))], "then": "p_topic_got"}


def p_bench_got(st, m, rp, u):
    b = m.get("bench") or {}
    if b.get("error"):
        raise F()._Stop("영상을 받지 못했어요", "잠시 뒤 다시 시도해 주시면 받기부터 이어 갈게요", auto=True)
    st["bench"] = {k: b.get(k) for k in ("id", "title", "channel", "date", "dur", "desc", "sheet", "big")}
    st["bench_lines"] = b.get("lines") or []
    ask = TOPIC.format(guide=_doc(GUIDE / "01_topic.md", 4000)) + "\n\n제목: " + str(b.get("title")) + "\n채널: " + str(b.get("channel")) + \
        "\n설명: " + str(b.get("desc") or "")[:1500] + "\n받아쓰기: " + " / ".join(str(l.get("text")) for l in st["bench_lines"])[:3000]
    return {"review": [F()._rv("pm_topic", ask, [F()._img(b["sheet"])] if b.get("sheet") else [], need=("topic", "product", "queries", "research_words"))],
            "then": "p_topic_got"}


# ── 근거(근거.md) ────────────────────────────────────────────────────────
RESEARCH = """너는 PC 제작 담당과 같은 근거 조사 담당이다. 웹 검색으로 언론·공식 출처 3~6곳을 찾아 근거.md 를 쓴다(PC 작품마다 3~6곳).
제작 순서(04 조사) 그대로:
{guide}

본보기(PC 납품 작품의 근거.md 그대로 — 꼴·깊이를 맞춘다):
{example}

이번 편: {topic} / 대상: {product} / 찾을 낱말: {words}
답: {{"근거_md": "근거.md 전문(출처 주소 포함)", "facts": ["대본에 쓸 사실 한 줄(출처 번호)"], "queries": ["원본 영상 검색어 — 위 소재 판독 검색어를 근거로 다듬은 것"]}}"""


def p_topic_got(st, m, rp, u):
    r = F()._reply(rp, "pm_topic", ("topic", "product", "queries", "research_words"))
    st["read"] = {"celeb": "", "subject_words": [], "topic": r["topic"], "product_words": [r["product"]]}
    st["product"] = {"name": str(r["product"])[:80], "mode": "none"}
    st["pm_topic"] = r
    return _research_ask(st)


def _research_ask(st, more: str = ""):
    r = st["pm_topic"]
    ex = _examples(st, 1)
    ask = RESEARCH.format(guide=_doc(GUIDE / "04_research.md", 4000), example=_doc(ex[0] / "근거.md", 6000) if ex else "(본보기 없음)",
                          topic=r["topic"], product=r["product"], words=", ".join(map(str, r.get("research_words") or []))) + more
    return {"review": [F()._rv("pm_research", ask, [], need=("근거_md", "facts", "queries"))], "then": "p_research_got"}


def _sources_in(md: str) -> int:
    return len(set(re.findall(r"https?://[^\s)\]>\"']+", md or "")))


def p_research_got(st, m, rp, u):
    r = F()._reply(rp, "pm_research", ("근거_md", "facts", "queries"))
    n = _sources_in(r["근거_md"])
    if n < 3 and not st["tries"].get("pm_research"):          # PC 근거는 출처 3~6곳 — 모자라면 한 번 더(그 자리에서)
        st["tries"]["pm_research"] = 1
        return _research_ask(st, f"\n\n★지난 근거.md 출처가 {n}곳뿐이었다 — 언론·공식 출처를 3곳 이상 찾아 다시.")
    st["research"] = {"queries": [str(q) for q in r["queries"] if q][:6] or list(st["pm_topic"].get("queries") or []), "keywords": [], "exclude": [],
                      "facts": [str(x) for x in r["facts"]][:20]}
    st["material_n"] = MATERIAL_N
    st["log"].append(f"근거.md 출처 {n}곳 · 사실 {len(st['research']['facts'])}줄")
    return {"do": [{"id": "save_research", "cmd": "write_doc", "files": {"pm/근거.md": r["근거_md"]}}], "then": "material"}   # material = 공용 원본 찾기(screen)


def p_material_dl(st, m, rp, u):
    files = (m.get("dl") or {}).get("files") or []
    if not files:
        raise F()._Stop("원본 영상을 받지 못했어요", "다시 시도해 주시면 원본 찾기부터 이어 갈게요", retry="material", auto=True)
    st["material"] = {"files": files}
    return {"do": [{"id": "mats", "cmd": "mat_sheets", "files": ["src/" + f["name"] for f in files]}], "then": "p_script"}


# ── 대본(대본.json) ──────────────────────────────────────────────────────
SCRIPT = """너는 PC 제작 담당과 같은 대본 작가다. PC 작품과 똑같은 꼴·결로 대본.json 을 쓴다.
대본 꼴(엔진 준비 문서 §2 그대로 — 이 꼴이 아니면 굽지 못한다):
{form}

채널 대본 결(스타일분석·줄판독 — PC 담당이 따른 것):
{style}

제작 순서(07 대본):
{guide}

본보기(PC 납품 대본 그대로):
{example}

이번 편 근거(사실만 쓴다 — 근거에 없는 사실은 지어내지 않는다):
{facts}
소재 쇼츠 받아쓰기: {bench}
금지선: 질병·효능·금액(가격) 말하지 않는다 · 쿠팡·구매 권유 줄 없음 · 화자 대사 줄(speaker) 1~3줄 · 훅 제목 2줄(\\n).
★줄마다 그 줄 화면이 될 원본 장면을 시트에서 찾아 scene 에 적는다: "원본 파일 이름@초 — 보이는 것". 받은 원본: {files}
  줄이 말하는 대상(브랜드·제품·사람)이 그 장면에 실제로 보여야 한다 — 원본에 없는 대상은 말하지 않는다(장면이 없으면 그 줄을 바꾼다).
답: {{"대본": {{"desktop_title": "…", "frame_vars": {{…}}, "lines": [{{"text": "…/…", "tts": "…", "speaker": "선택", "scene": "src_….mp4@12.4 — 보이는 것"}}]}}}}"""


def p_script(st, m, rp, u):
    st["pm_sheets"] = (m.get("mats") or {}).get("sheets") or st.get("pm_sheets") or []
    return _script_ask(st)


def _script_ask(st, more: str = ""):
    ex = _examples(st, 1)
    sd = _slug_dir(st)
    ask = SCRIPT.format(form=_doc(sd / "_engine_ready.md", 5000, part="2."), style=_doc(sd / "스타일분석.md", 9000) + "\n" + _doc(sd / "대본스타일_줄판독_2026-10-17.md", 5000),
                        guide=_doc(GUIDE / "07_script.md", 7000), example=_doc(ex[0] / "대본.json", 5000) if ex else "(본보기 없음)",
                        facts="\n".join(st["research"].get("facts") or []), bench=" / ".join(str(l.get("text")) for l in st.get("bench_lines") or [])[:2000],
                        files=", ".join(f["name"] for f in (st.get("material") or {}).get("files") or [])) + more
    return {"review": [F()._rv("pm_script", ask, [F()._img(x) for x in st.get("pm_sheets") or []][:4], need=("대본",))], "then": "p_script_got"}


def script_problems(st, S: dict) -> list[str]:
    """대본 검사 = PC 제작기 관문과 같은 함수(script_audit.audit · 판 = 이 프리셋 짝 판)."""
    from tools.calcopy.hybrid import script_audit as SA
    if not isinstance(S, dict) or not S.get("lines") or not S.get("frame_vars"):
        return ["대본 꼴이 아니다(frame_vars·lines 필요 — 엔진 준비 문서 §2)"]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "대본.json"
        p.write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
        r = SA.audit(p, version=st["version"])
    bad = [f"{x['kind']}: {str(x['why'])[:160]}" for x in r["rules"] if not x["ok"]]
    e = r.get("engine")
    if e and not e.get("ok"):
        bad.append(f"대본 엔진: {(e.get('points') or {}).get('why')}")
    return bad + scene_problems(st, S)


def scene_problems(st, S: dict) -> list[str]:
    """줄마다 장면 증거(scene = '원본@초 — 보이는 것') — 받은 원본 이름이어야 하고 초·보이는 것이 있어야 한다.
    11-03 베이글 편: '트레이더조' 줄에 원본에 없는 대상 → 다른 브랜드 병(Jev 뿌리 0.86·해결 0.77). 보이는 것이 대상과 맞나는 재료·렌더 전 눈이 본다."""
    names = {f["name"] for f in (st.get("material") or {}).get("files") or []}
    if not names:
        return []
    bad = []
    for i, l in enumerate(S.get("lines") or []):
        m = re.match(r"\s*([^@\s]+)@(\d+(?:\.\d+)?)\s*[—\-:]\s*(\S.*)", str(l.get("scene") or ""))
        if not m:
            bad.append(f"줄{i + 1} 장면 증거 없음 — scene 에 '원본@초 — 보이는 것'")
        elif m.group(1) not in names:
            bad.append(f"줄{i + 1} 장면 원본 '{m.group(1)}' 은 받은 원본이 아니다({', '.join(sorted(names))})")
    return bad


def p_script_got(st, m, rp, u):
    S = F()._reply(rp, "pm_script", ("대본",))["대본"]
    bad = script_problems(st, S)
    if bad:
        st["tries"]["pm_script"] = st["tries"].get("pm_script", 0) + 1
        if st["tries"]["pm_script"] > SCRIPT_MAX:
            raise F()._Stop("대본을 채널 규칙에 맞추지 못했어요", "다시 시도해 주시면 대본부터 다시 쓸게요", retry="p_script", detail="; ".join(bad)[:400])
        return _script_ask(st, "\n\n★지난 대본이 걸린 것(이것만 고쳐 다시):\n- " + "\n- ".join(bad))
    st["pm_script"] = S
    return _meme_ask(st)


# ── 짤 ──────────────────────────────────────────────────────────────────
MEMES = """너는 PC 제작 담당과 같은 짤 담당이다. PC 작품은 편마다 짤 2~5개(줄 끝 반응·감탄 자리)를 넣었다.
아래 대본 줄에 어울리는 짤 후보를 6~10개 골라 stems 로 답한다(받아 본 뒤 2~5개를 재료에 넣는다). 목록 밖 이름은 쓰지 않는다.
대본:
{lines}

짤 목록(감정별 — meme:<이름> 의 이름 | 제목):
{cat}
답: {{"stems": ["이름", …]}}"""


def _meme_ask(st):
    cat = json.loads((ROOT / "tools/calcopy/hybrid/meme_catalog.json").read_text(encoding="utf-8"))["memes"]
    by: dict = {}
    for x in cat:
        by.setdefault(x["tone"] or "기타", []).append(x)
    lines = "\n".join(f"{i + 1}. {l.get('text')}" for i, l in enumerate(st["pm_script"]["lines"]))
    catt = "\n".join(f"[{t}] " + " · ".join(f"{x['stem']}|{x['title'][:18]}" for x in xs[:MEME_PER_TONE]) for t, xs in by.items())
    return {"review": [F()._rv("pm_memes", MEMES.format(lines=lines, cat=catt), [], need=("stems",))], "then": "p_memes_got"}


def p_memes_got(st, m, rp, u):
    stems = [str(s) for s in F()._reply(rp, "pm_memes", ("stems",))["stems"] if s][:10]
    return {"do": [{"id": "memes", "cmd": "memes", "stems": stems}], "then": "p_rows"}    # stems → 받을 주소 = 서버 claude_flow.sign_memes


# ── 재료(재료.json) ─────────────────────────────────────────────────────
ROWS = """너는 PC 제작 담당과 같은 재료 담당이다. 자막 조각마다 한 행으로 재료.json 을 쓴다(엔진 준비 문서 §2 재료 꼴 그대로).
{form}

제작 순서(05 재료):
{guide}

★자막 조각(행 수 = 조각 수, 순서 그대로 — 같은 컷을 이으려면 {{"cont": true}}):
{pieces}
★원본 파일(src 에 이 이름 그대로) — 시트 칸마다 원본 초가 적혀 있다(ss = 그 초):
{files}
★짤(받은 것만 — src "meme:<이름>"):
{memes}
★박힌 글자(남의 자막·로고·워터마크)는 src_crop [x, y, w, h](원본 px)로 잘라 칸 밖으로 뺀다 — 흐림 없음. 칸 비율 = {win} · 확대 2.3배 이하.
★제품·사람 얼굴이 칸 가운데 오게 src_crop 을 잡는다(crop_x 만 주면 가로 자리만).
★대본 줄이 브랜드·제품·사람을 말하면 그 컷 화면에 바로 그것이 나와야 한다(다른 브랜드 병 금지 — 원본에 없으면 그 줄은 제품이 안 보이는 장면·짤로).
★한 컷 안에서 원본 장면이 바뀌지 않게(ss~ss+길이가 한 장면 안) — 원본 시트로 장면 경계를 확인한다.
답: {{"재료": {{"shots": [{{"src": "src_….mp4", "ss": 12.4, "kind": "제품영상", "seen": "무엇이 보이나", "src_crop": [x, y, w, h]}}, {{"cont": true}}, {{"src": "meme:…", "ss": 0, "kind": "짤", "seen": "…"}}]}}}}"""


def _pieces(st) -> list[dict]:
    from tools.calcopy.engine import preset_make as PM
    cfg = PM.load_preset(preset_dir(st))[1]
    return PM.accumulate_pieces(st["pm_script"]["lines"], cfg)


def p_rows(st, m, rp, u):
    mm = m.get("memes") or {}
    st["pm_memes"] = mm.get("got") or []
    st["pm_meme_sheet"] = mm.get("sheet")
    return _rows_ask(st)


def _rows_ask(st, more: str = "", extra_imgs: list | None = None):
    from tools.calcopy.engine import preset_make as PM
    cfg = PM.load_preset(preset_dir(st))[1]
    ps = _pieces(st)
    ask = ROWS.format(form=_doc(_slug_dir(st) / "_engine_ready.md", 5000, part="2."), guide=_doc(GUIDE / "05_material.md", 5000),
                      pieces="\n".join(f"{i}. {p['text'].replace(chr(10), ' / ')}" for i, p in enumerate(ps)),
                      files=", ".join(f["name"] for f in st["material"]["files"]), memes=", ".join(st.get("pm_memes") or []) or "(없음)",
                      win=f"{cfg['window'][0]}:{cfg['window'][1]}") + more
    imgs = [F()._img(x) for x in (extra_imgs or [])] + [F()._img(x) for x in st.get("pm_sheets") or []][:6] + ([F()._img(st["pm_meme_sheet"])] if st.get("pm_meme_sheet") else [])
    return {"review": [F()._rv("pm_rows", ask, imgs[:10], need=("재료",))], "then": "p_rows_got"}


def p_rows_got(st, m, rp, u):
    R = F()._reply(rp, "pm_rows", ("재료",))["재료"]
    if not isinstance(R, dict) or not isinstance(R.get("shots"), list):
        return _rows_ask(st, "\n\n★재료 꼴이 아니다 — {\"shots\": [...]} 로.")
    st["pm_rows"] = R
    return _save_and_plan(st)


def _save_and_plan(st):
    pr = _rel_preset(st)
    return {"do": [{"id": "save_pm", "cmd": "write_doc", "files": {"pm/대본.json": st["pm_script"], "pm/재료.json": st["pm_rows"]}, "cand_dir": True},
                   {"id": "crop", "cmd": "pm_sheet", "preset": pr},
                   {"id": "pm", "cmd": "pm", "mode": "plan", "preset": pr}], "then": "p_plan_got"}


def p_plan_got(st, m, rp, u):
    r = m.get("pm") or {}
    crop = (m.get("crop") or {}).get("sheets") or []
    st["pm_crop_sheets"] = crop
    probs = r.get("problems") or ([r["error"]] if r.get("error") else []) or ([r.get("note")] if r.get("ok") is False else [])
    if not probs:                       # 계획 통과(ok None) — 렌더 전에 구워질 칸을 눈으로(렌더 한 번 — 사장님 11-02 '뒤로 안 감')
        st["pm_plan_sheets"] = [x for x in r.get("sheets") or [] if "접촉" in x] or (r.get("sheets") or [])[:1]
        return _plan_eye_ask(st)
    return _plan_fix(st, probs, crop + (r.get("sheets") or [])[:2])


def _plan_fix(st, probs, imgs):
    st["tries"]["pm_plan"] = st["tries"].get("pm_plan", 0) + 1
    if st["tries"]["pm_plan"] > PLAN_MAX:
        raise F()._Stop("장면을 규칙에 맞추지 못했어요", "다시 시도해 주시면 장면 맞추기부터 이어 갈게요", retry="p_rows", detail="; ".join(map(str, probs))[:400])
    st["log"].append(f"계획 관문 {len(probs)}건 → 그 행만 고치기")
    return _rows_ask(st, "\n\n★지금 재료.json(이것을 고쳐 다시 — 걸린 행만 바꾼다):\n" + json.dumps(st["pm_rows"], ensure_ascii=False)[:6000] +
                     "\n\n★계획 관문에 걸린 것(자를 칸 시트 = 빨간 상자가 구워질 칸):\n- " + "\n- ".join(map(str, probs))[:4000], imgs)


PLAN_EYE = """너는 PC 제작 담당처럼 렌더 전에 계획 접촉 시트(컷마다 구워질 칸의 시작·가운데·끝 3장 + 그 컷의 대본 줄)를 눈으로 확인한다.
코드 관문이 이미 잰 것(칸 가장자리 남의 글자·A-B-A·재사용)은 보지 않는다. 코드가 못 보는 것만 컷마다 본다(증거 = 그 컷 3장에서 본 것):
① 원본 장면 전환이 반투명하게 겹쳐 보인다(디졸브 — 두 장면이 섞인 장) ② 대본 줄이 말하는 대상(브랜드·제품·사람)과 화면 대상이 다르다 ③ 제품이 칸 가장자리로 밀렸다
(빠른 하드컷은 이 채널의 정상 편집이다 — 벤치 샷 18%가 0.8초 미만. 걸지 않는다)
대본: {lines}
답: {{"ok": true/false, "cuts": [{{"no": 컷번호, "seen": "3장에서 본 것"}}], "problems": ["#컷번호 무엇(①~③)"]}} — cuts 는 시트의 모든 컷."""


def _plan_eye_ask(st):
    lines = " / ".join(str(l.get("text")) for l in st["pm_script"]["lines"])
    return {"review": [F()._rv("pm_plan_eye", PLAN_EYE.format(lines=lines), [F()._img(x) for x in st.get("pm_plan_sheets") or []][:2],
                               need=("ok", "cuts", "problems"))], "then": "p_plan_eye_got"}


def p_plan_eye_got(st, m, rp, u):
    a = F()._reply(rp, "pm_plan_eye", ("ok", "cuts", "problems"))
    probs = [str(x) for x in a.get("problems") or []]
    if a.get("ok") is True and not probs and len(a.get("cuts") or []) >= 3:
        st["log"].append("계획 통과 + 렌더 전 눈 확인 통과 → 완성(렌더 한 번)")
        return p_make(st, m, rp, u)
    if len(a.get("cuts") or []) < 3 and not probs:
        probs = ["렌더 전 눈 확인 증거 부족(컷마다 본 것을 적는다)"]
    return _plan_fix(st, ["렌더 전 눈 확인: " + x for x in probs], (st.get("pm_crop_sheets") or []) + (st.get("pm_plan_sheets") or [])[:1])


# ── 완성·확인 ─────────────────────────────────────────────────────────────
EYE = """너는 PC 제작 담당처럼 완성본 1초 시트를 눈으로 확인한다. 화면에서 읽은 것을 증거로 적는다(증거 없는 '좋음'은 합격이 아니다).
본다: 남의 박힌 글자·로고가 화면에 남았나 · 제품이 칸 가장자리로 밀렸나 · 대사 줄(화자) 장면이 말과 맞나 · 같은 장면 반복 · 끝 멈춤.
대본: {lines}
답: {{"ok": true/false, "title_seen": "화면 제목 글", "scenes": [{{"t": 초, "seen": "보인 것"}}], "problems": ["행 번호·무엇"]}}"""


def p_make(st, m, rp, u):
    """만들기(굽기·검사 = 회원 PC c_pm → preset_make) 한 번 — 눈 확인 통과 뒤, 제작자 과제 답(back·waive) 뒤."""
    return {"do": [{"id": "pm", "cmd": "pm", "mode": "make", "preset": _rel_preset(st)}], "then": "p_make_got"}


TASK_BACK = {"script": "p_script", "plan": "p_rows", "render": "p_make", "check": "p_make"}


def task_goto(st, act: str, stage: str) -> dict | None:
    """(판단 주인 — PC제작형 제작자 과제 답 back·waive·submit → PC 처리기) 단계 이름은 STAGES 의 key.
    보통 라인 처리기(f_render·_fix_review — st['script'] 전제)로 보내지 않는다(11-04 회원 시험: waive → goto 'render' → KeyError 'script' → http_500 영영).
    PC 관문은 넘기기로 건너지 않는다(preset_gates '우회 없음') — waive 는 남은 것을 경고로 적고 만들기를 한 번 더. None = 이 답으로는 못 이어 감(멈춤 안내)."""
    if act == "back":
        return {"goto": TASK_BACK[stage]} if stage in TASK_BACK else None
    if act == "waive" and stage in ("plan", "render", "check"):
        st.setdefault("warn", []).append({"stage": stage, "causes": ["제작자 권고 넘기기"], "why": str((st.get("_task") or {}).get("detail") or "")[:300]})
        r = st.get("pm_final") or {}
        if stage == "check" and r.get("final"):
            return {"done": {"video": r["final"], "title": st["pm_script"].get("desktop_title") or "", "auto_ok": not st.get("pm_b_fails"), "look_ok": False,
                             "look_left": list(st.get("pm_b_fails") or [])[:6] or ["마지막 확인을 끝까지 못 했어요"], "note": "확인에서 남은 것 있음"}}
        return {"goto": "p_make"}
    return None          # submit(직접 만든 결과)·대본 넘기기 — PC 라인은 판정할 길이 없다


def p_make_got(st, m, rp, u):
    r = m.get("pm") or {}
    if not r.get("final"):
        st["tries"]["pm_make"] = st["tries"].get("pm_make", 0) + 1
        if st["tries"]["pm_make"] > MAKE_MAX:
            raise F()._Stop("영상을 만들지 못했어요", "다시 시도해 주시면 이어 갈게요", retry="p_rows", detail=str(r.get("error") or r.get("problems"))[:400])
        return _rows_ask(st, "\n\n★완성 단계에서 걸린 것(걸린 행만 고친다):\n- " + "\n- ".join(map(str, r.get("problems") or [r.get("error")]))[:4000], st.get("pm_crop_sheets") or [])
    st["pm_final"] = r
    bad = [f"{x.get('B')} {x.get('항목')} {x.get('값')}" for x in r.get("rows") or [] if not x.get("ok")]
    st["pm_b_fails"] = bad
    lines = " / ".join(str(l.get("text")) for l in st["pm_script"]["lines"])
    return {"review": [F()._rv("pm_eye", EYE.format(lines=lines) + (("\n\n자동 검사에서 걸린 것: " + "; ".join(bad)) if bad else ""),
                               [F()._img(x) for x in r.get("sheets") or [] if "sheet_1s" in x][:1], need=("ok", "title_seen", "scenes", "problems"))], "then": "p_eye_got"}


def p_eye_got(st, m, rp, u):
    a = F()._reply(rp, "pm_eye", ("ok", "title_seen", "scenes", "problems"))
    proof = bool(str(a.get("title_seen") or "").strip()) and len(a.get("scenes") or []) >= 3
    if a.get("ok") is True and proof and not st.get("pm_b_fails"):
        r = st["pm_final"]
        return {"done": {"video": r["final"], "title": st["pm_script"].get("desktop_title") or "", "auto_ok": True, "look_ok": True, "look_left": [], "note": ""}}
    st["tries"]["pm_eye"] = st["tries"].get("pm_eye", 0) + 1
    probs = [str(x) for x in a.get("problems") or []] + list(st.get("pm_b_fails") or []) + ([] if proof else ["눈 확인 증거 부족(제목·장면 3개 이상)"])
    if st["tries"]["pm_eye"] > MAKE_MAX:      # 한도 — 멈추지 않고 남은 것을 알리고 완성(사장님 10-31 '멈추지 말고')
        r = st["pm_final"]
        return {"done": {"video": r["final"], "title": st["pm_script"].get("desktop_title") or "", "auto_ok": not st.get("pm_b_fails"), "look_ok": False,
                         "look_left": probs[:6], "note": "확인에서 남은 것 있음"}}
    return _rows_ask(st, "\n\n★완성본 확인에서 걸린 것(걸린 행만 고친다):\n- " + "\n- ".join(probs)[:4000], st.get("pm_crop_sheets") or [])


PHASES = {"bench": p_bench, "bench_got": p_bench_got, "p_topic_got": p_topic_got, "p_research_got": p_research_got, "material_dl": p_material_dl,
          "p_script": p_script, "p_script_got": p_script_got, "p_memes_got": p_memes_got, "p_rows": p_rows, "p_rows_got": p_rows_got,
          "p_plan_got": p_plan_got, "p_plan_eye_got": p_plan_eye_got, "p_make": p_make, "p_make_got": p_make_got, "p_eye_got": p_eye_got}
PHASE_STAGE = {"p_topic_got": "bench", "p_research_got": "research", "material_dl": "material", "p_script": "script", "p_script_got": "script",
               "p_memes_got": "sign", "p_rows": "plan", "p_rows_got": "plan", "p_plan_got": "plan", "p_plan_eye_got": "plan", "p_make": "render", "p_make_got": "render", "p_eye_got": "check"}
