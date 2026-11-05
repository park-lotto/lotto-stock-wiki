# -*- coding: utf-8 -*-
"""프리셋 한 입구 — "<채널> 프리셋하자" 한마디로 선정→수집→뜯기→판독 묶음→규칙→카피→제작→검증→적용 (관제 097, 2026-10-20).
    PYTHONUTF8=1 py tools/calcopy/engine/kal.py <채널주소|@핸들> [--slug <slug>] [--brand <우리 브랜드>] [--n 6] [--from <단계>] [--hybrid 예|아니오]
                                               [--ours-mp4 <시험편.mp4> --ours-lines <자막표|줄판독.json>]
상태 = channel/<slug>/kal_state.json (단계마다 state·sec·outputs). 끝난 단계는 건너뛴다. --from 으로 그 단계부터 다시.
사람(Claude 눈) 단계에서는 멈추지 않고 **할 일 묶음**(판독 프레임 목록·줄판독 뼈대·워커 브리프)을 만들어 두고 state=waiting_human 으로 끝낸다.
세션은 지침서 `tools/calcopy/칼카피_분석지침서.md` §실행 대본 순서로 묶음을 워커에 나눠 주고, 결과가 들어오면 같은 명령을 다시 돌린다.
판단 주인: 단계 순서·건너뛰기·멈춤 = 이 파일 STEPS/run 한 곳. 각 단계의 판단은 기존 주인 함수(analyze.analyze·kal_analyze.*·to_frame.build·calcopy_board.set_step)를 부른다.
뜯기 판독 창구 = engine/tear_llm.ask 한 곳(11-06): 그림 claude_cli(사장님 10-18 그림 판독 제미나이 금지) · 받아쓰기 스피치매틱스 · 소리 판독 제미나이(메모리 10-25 허용).
경계(관제 235 합의 10-20): kal.py = 분석 입구(~판 설정 초안 `_kal/판설정_초안.json`). 제작은 렌더러를 만들지 않고 preset_make.make_one 을 부른다(--work, 11-06 make-00). 소리 도구 = tools/calcopy/engine/sound/.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import kal_analyze as K  # noqa: E402

DATA = Path("C:/숏템_칼카피")
YTDLP_F = "137+ba[ext=m4a]/bv*[height>=1080]+ba/b"       # 담당_공통규칙 (web 클라이언트, android 금지)
YTDLP_LITE = "bv*[height<=720]+ba/b[height<=720]/b"       # 시운전·디스크 부족 때(--lite): 720p 까지만
DISK_WARN_GB, DISK_STOP_GB = 15, 3
LONG_MIN_S = 480                                          # outside-01 롱폼 갈래: 가로 8분+ (개정안 outside-01 회원 값)
DETAIL_MAX = 18                                           # select-07: 업로드일을 재려고 상세(yt-dlp -J)를 여는 상한 편 수
STALL_SEC = 60                                            # collect-01: 받는 파일이 이 동안 안 자라면 멈춘 것(yt_fetch.STALL_SEC 와 같은 값)
GUIDE_FILES = ("tools/calcopy/칼카피_분석지침서.md", "channel/production_guide/98_error_log.md")   # common-17 시작 때 읽음 확인                        # 루트 CLAUDE.md 디스크 병목 규칙 + 사장님 10-20 "3GB 밑이면 즉시 멈춤"


def disk_free_gb(path: str = "C:/") -> float:
    import shutil
    return round(shutil.disk_usage(path).free / 1e9, 1)


def disk_gate(what: str) -> str | None:
    """받기·렌더 전 관문 — 3GB 미만이면 이유 문자열(거절), 15GB 미만이면 경고만 출력."""
    g = disk_free_gb()
    if g < DISK_STOP_GB:
        return f"C 여유 {g}GB < {DISK_STOP_GB}GB — {what} 시작 거절(사장님 10-20). 남의 파일은 지우지 말고 보고"
    if g < DISK_WARN_GB:
        print(f"[경고] C 여유 {g}GB < {DISK_WARN_GB}GB — {what} 는 최소로(표본 2편·720p·렌더 1편)")
    return None
STEPS = ["select", "collect", "tteutgi", "frames", "skeleton", "readlines", "rules", "copy", "make", "verify", "apply"]
HUMAN = {"readlines": "줄판독(눈) — 묶음 _kal/워커묶음.json 을 워커에 나눠 주고 줄판독/<id>.json 을 채운다 → check 통과 뒤 다시 실행",
         "rules": "규칙 판정 — _kal/스타일분석_초안.md 를 보고 channel/<slug>/스타일분석.md 를 쓴다(붙는 조건 규칙 채택은 사람) → 다시 실행",
         "copy": "프리셋 손질 — frames/frame_<id>.json 을 _hand/ 로 손질(실측 근거 notes) → preset_save → 다시 실행",
         "make": "제작 — 소재·대본·재료(작업 폴더: 대본.json·재료.json) 준비 뒤 --work <작업 폴더> 로 다시 실행 → make 가 preset_make.make_one 으로 렌더(TTS 과금은 허락됨)",
         "verify": "시청 판정 — _kal/시청묶음 을 보고 _kal/시청판정.json(sha256·verdict) 을 적은 뒤 다시 실행"}


from tools.calcopy.engine.voices import KNOWN_VOICES, BANNED_VOICES  # noqa: E402,F401 — 명단 주인 = engine/voices.py
AXES = ("자막", "틀", "장면전환", "장면대사", "스토리", "대본", "소리", "스티커", "썸네일", "소재", "채널")
_AXIS_KW = {"자막": ("자막", "타이핑", "팝", "글꼴", "강조"), "틀": ("틀", "제목", "로고", "창", "출처"), "장면전환": ("컷", "전환", "줌", "정지"), "장면대사": ("장면", "매칭", "시연"),
            "스토리": ("박자", "훅", "반전", "끝", "결말", "흐름"), "대본": ("어미", "전언", "말투", "대본", "나레는", "반말"), "소리": ("효과음", "BGM", "목소리", "LUFS", "덕킹"),
            "스티커": ("스티커", "짤", "빨간 원", "화살표", "이모지"), "썸네일": ("썸네일", "0초", "첫 프레임"), "소재": ("제품", "소재", "해외 원본"), "채널": ("조회", "업로드", "구독")}


def tempo_of(voice_id: str) -> str:
    """말속도는 판 파일에 적지 않는다(관제 235 합의 10-20, 두 벌 금지) — 주인을 부른다:
    일레븐랩스 = voice_presets.json default_speed(narr_align.fixed_tempo) / 타입캐스트 = 판의 cps_target(렌더러가 atempo 계산)."""
    if not voice_id:
        return "-"
    try:
        from tools.calcopy.engine.narr_align import fixed_tempo
        t = fixed_tempo(voice_id)
    except Exception as e:
        return f"확인 실패({e.__class__.__name__})"
    return f"{t} 고정(voice_presets)" if t else "판 cps_target 로 맞춤(타입캐스트)"


def voice_candidates() -> list[dict]:
    """쓸 수 있는 목소리 표 — 판 파일(styles/*.json voice·candidates) + KNOWN_VOICES + 일레븐랩스 프리셋 수. 값은 저장소에서 읽는다(추측 금지)."""
    rows = {v["voice_id"]: dict(v, used_in=[]) for v in KNOWN_VOICES}
    for f in sorted((ROOT / "tools/calcopy/hybrid/styles").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        v = d.get("voice") or {}
        if v.get("voice_id"):
            rows.setdefault(v["voice_id"], {"name": v.get("name"), "voice_id": v["voice_id"], "engine": "타입캐스트" if v["voice_id"].startswith("tc_") else "일레븐랩스", "note": "", "used_in": []})
            rows[v["voice_id"]]["used_in"].append(d.get("name") or f.stem)
        for c in v.get("candidates") or []:
            rows.setdefault(c, {"name": c, "voice_id": c, "engine": "타입캐스트" if c.startswith("tc") else "일레븐랩스", "note": f"{d.get('name')} 후보(사장님 귀 확인 전)", "used_in": []})
    vp = ROOT / "shopping_shorts/assets/voice_presets.json"
    n_el = len(json.loads(vp.read_text(encoding="utf-8"))) if vp.exists() else 0
    out = [r for r in rows.values() if r["voice_id"] not in BANNED_VOICES]
    out.append({"name": f"(일레븐랩스 프리셋 {n_el}종 더 — shopping_shorts/assets/voice_presets.json)", "voice_id": "", "engine": "일레븐랩스", "note": "", "used_in": []})
    return out


def voice_recommend(S) -> str:
    """추천 1순위 — 뜯기 소리 칸의 화자 성별(있으면)로: 남 → 박창수, 여 → 미나(시작 문서 §12 확정 규칙). 없으면 '미측정'."""
    genders = []
    for vid in (S.step("tteutgi").get("outputs") or {}).get("ids") or []:
        p = S.dir / "뜯기" / vid / "뜯기.json"
        if p.exists():
            a = json.loads(p.read_text(encoding="utf-8")).get("audio") or {}
            for sp in ((a.get("asr_extra") or {}).get("speakers") or (a.get("composition") or {}).get("speakers") or []):
                if isinstance(sp, dict) and sp.get("gender"):
                    genders.append(sp["gender"])
    if not genders:
        return "미측정(뜯기에 화자 성별 없음 — 줄판독 뒤 engine/sound/narr_report.py 닮은 목소리 순위로)"
    g = max(set(genders), key=genders.count)
    pool = [v["name"] for v in KNOWN_VOICES if v["gender"] == ("남" if g == "male" else "여")]
    return " / ".join(pool) + f" 중에서 (벤치 화자 {'남' if g == 'male' else '여'} {genders.count(g)}/{len(genders)})"


def menu(axis: str = "all") -> list[dict]:
    """장점 카탈로그 — 주인 channel/스타일.json strengths·options 를 읽어 요소별로(새 장부 없음).
    축 = 장부의 `element`(표준 §2-3 요소 15종 — 05 가 채움) > `axis`. 엔진 지원(○△×)·판 칸 = 장부 `engine`·`style_cell`. 장부에 없으면 '미기입'(짐작해 채우지 않는다 — 채울 일이 보이게).
    axis 인자 = 'all' · 15종 이름(upgrade_table.AXES15) · 장부의 옛 axis 값(예 '화면')."""
    d = json.loads((ROOT / "channel/스타일.json").read_text(encoding="utf-8"))
    rows = []

    def row(x: dict, kind: str, what, channel, evidence, source, views=None):
        el = x.get("element") or x.get("axis") or "미기입"
        rows.append({"axis": el, "axis_src": "장부" if (x.get("element") or x.get("axis")) else "미기입", "axis_old": x.get("axis"), "kind": kind,
                     "what": what, "channel": channel, "evidence": evidence, "source": source, "views": views,
                     "engine": x.get("engine") or "미기입", "style_cell": x.get("style_cell") or "미기입"})
    for st, v in (d.get("styles") or {}).items():
        for x in v.get("strengths") or []:
            row(x, f"strength/{st}", x.get("what"), x.get("channel"), x.get("evidence") or x.get("strength"), x.get("source"))
    for name, o in (d.get("options") or {}).items():
        if isinstance(o, dict):
            vs = [b.get("views_median") for b in (o.get("bench") or {}).values() if isinstance(b, dict) and isinstance(b.get("views_median"), (int, float))]
            row(o, f"option/{name}", o.get("desc"), ",".join((o.get("bench") or {}).keys()) or o.get("source"), o.get("why") or o.get("bench"), o.get("judge") or o.get("source"),
                max(vs) if vs else None)
    return [r for r in rows if axis == "all" or axis in (r["axis"], r["axis_old"])]


_ENGINE_RANK = {"○": 0, "△": 1, "×": 2}


def _views_of(r: dict) -> float:
    """근거 조회 — 장부 views_median, 없으면 evidence 글 속 '조회 …만'·'…만' 최대값(ⓑ 근거 조회가 큰 쪽)."""
    if isinstance(r.get("views"), (int, float)):
        return float(r["views"])
    best = 0.0
    for num, unit in re.findall(r"(\d[\d,.]*)\s*(만|억)", str(r.get("evidence") or "")):
        try:
            best = max(best, float(num.replace(",", "")) * (1e4 if unit == "만" else 1e8))
        except ValueError:
            pass
    return best


def _base_style(slug: str) -> tuple[str | None, dict]:
    """1차 판 = styles/*.json 중 bench.channel == slug 이고 base 없는 판(초안 이름 ititemlog판 ≠ 실제 판 잇템로그판 — 10-25 실측)."""
    sd = ROOT / "tools/calcopy/hybrid/styles"
    for p in sorted(sd.glob("*.json")):
        if p.stem.startswith("_"):
            continue
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if (st.get("bench") or {}).get("channel") == slug and not st.get("base"):
            return st.get("name") or p.stem, st
    return None, {}


def _kyeol(slug: str, plan: dict) -> tuple[list[str], str]:
    """같은 결(스타일.json styles = 소리 구성 축) — ① styles.*.bench 에 slug 가 있으면 그것 ② 없으면 1차 판 script.audit count 로(원음+나레 = 현장썰 · 나레만 = 나레썰 · 원음만 = 자막썰)."""
    d = json.loads((ROOT / "channel/스타일.json").read_text(encoding="utf-8"))
    hit = [k for k, v in (d.get("styles") or {}).items() if slug in (v.get("bench") or {})]
    if hit:
        return hit, "장부 styles.*.bench"
    cnt = {a.get("of"): a.get("min", 0) for a in ((plan.get("script") or {}).get("audit") or []) if a.get("kind") == "count"}
    if cnt.get("orig", 0) >= 1 and cnt.get("tts", 0) >= 1:
        return ["현장썰"], "추정 — 1차 판 audit count 원음·나레 둘 다"
    if cnt.get("tts", 0) >= 1:
        return ["나레썰"], "추정 — 1차 판 audit count 나레만"
    if cnt.get("orig", 0) >= 1:
        return ["자막썰"], "추정 — 1차 판 audit count 원음만"
    return [], "결 모름(1차 판 audit count 없음)"


SKELETON_EL = ("script", "cut_rhythm", "speech", "cap_enter", "sfx")   # 지침서 §5-1 뼈대(script·cuts·timing·typing_cps·variant_for·sfx 규칙) — 바꾸려면 사장님


def recommend(slug: str, plan: dict) -> dict:
    """업그레이드 추천 후보(지침서 §2-6-1 ②) — 카탈로그에서 같은 결·상위 편 근거·엔진 ○ 우선, 같은 요소끼리 부딪치면 ⓐ 같은 결 ⓑ 근거 조회 ⓒ 엔진 ○ ⓓ 사람.
    ★후보일 뿐 — 판에 자동으로 넣지 않는다(사람이 고른다). 이 채널 자신의 옵션(bench 에 slug)은 1차 몫이라 뺀다. 엔진 × 는 '못 만듦'으로 따로."""
    kyeol, ksrc = _kyeol(slug, plan)
    d = json.loads((ROOT / "channel/스타일.json").read_text(encoding="utf-8"))
    own = {f"option/{k}" for k, o in (d.get("options") or {}).items() if isinstance(o, dict) and slug in (o.get("bench") or {})}
    cands, cant = [], []
    for r in menu("all"):
        if r["kind"] in own:
            continue
        same = r["kind"].startswith("strength/") and r["kind"].split("/", 1)[1] in kyeol
        c = {"element": r["axis"], "kind": r["kind"], "what": r["what"], "channel": r["channel"], "same_kyeol": same, "views": _views_of(r),
             "engine": r["engine"], "style_cell": r["style_cell"], "skeleton": r["axis"] in SKELETON_EL, "evidence": r["evidence"], "source": r["source"]}
        (cant if r["engine"] == "×" else cands).append(c)
    cands.sort(key=lambda c: (not c["same_kyeol"], -c["views"], _ENGINE_RANK.get(c["engine"], 3)))
    groups: dict = {}
    for i, c in enumerate(cands):
        c["rank"] = i + 1
        groups.setdefault(c["element"], []).append(c["rank"])
    for c in cands:
        g = groups[c["element"]]
        if len(g) > 1:
            first, second = cands[g[0] - 1], cands[g[1] - 1]
            tie = (first["same_kyeol"], first["views"], first["engine"]) == (second["same_kyeol"], second["views"], second["engine"])
            c["conflict"] = {"with": g, "rule": "ⓓ 사람(사장님) — ⓐⓑⓒ 로 못 가름" if tie else "ⓐ 같은 결 → ⓑ 근거 조회 → ⓒ 엔진 ○ 순으로 위가 앞"}
    return {"kyeol": kyeol, "kyeol_src": ksrc, "candidates": cands, "cannot_build": cant,
            "rule": "후보 — 사람이 고른다(자동 반영 금지). skeleton:true = 뼈대 요소(지침서 §5-1) — 바꾸려면 사장님 확인"}


def stage_upgrade(S) -> dict:
    """업그레이드 단계(지침서 §2-6-1) — 1차 판(styles/ bench.channel==slug)을 base 로 상속하는 초안 + upgrades 빈 칸 + 추천 후보(recommend) + 카탈로그 메뉴.
    측정 = engine/upgrade_table.py(판·완성본이 생긴 뒤). 추천은 후보일 뿐 판에 자동 반영하지 않는다."""
    kd = S.dir / "_kal"
    kd.mkdir(parents=True, exist_ok=True)
    name, plan = _base_style(S.d["slug"])
    if not name:
        base = kd / f"{S.d['slug']}판_초안.json"
        plan = json.loads(base.read_text(encoding="utf-8")) if base.exists() else {"name": f"{S.d['slug']}판", "_note": "1차 판 초안 없음 — rules 단계 먼저"}
        name = plan.get("name")
    rec = recommend(S.d["slug"], plan)
    up = {"name": f"{name}_v2", "base": name,   # styles.py 가 base 판을 상속(관제 235 6fcdcef89, 예 styles/연예인레시피판.json) — 바꾼 칸만 아래에 덮어쓴다
          "_rule": "뼈대 칸(placement·script·cuts·timing·caption.typing_cps·variant_for·length·sfx_key)은 1차 값 그대로. 겉모양 칸만 근거 있는 장점으로 — 기록 필수(업그레이드_기록.md). 뼈대를 바꾸는 항목은 사장님 확인(skeleton:true)",
          "upgrades": [], "_upgrade_item": {"axis": "표준 §2-3 15종 중 하나", "what": "", "why": "수치·채널·편", "source": "스타일.json strengths/options 키 또는 사고 기록·커밋", "expect": "나아질 측정값", "verify": "측정값|사람 판정"},
          "recommend": rec, "menu": menu("all"),
          "measure": f"PYTHONUTF8=1 py tools/calcopy/engine/upgrade_table.py {name}_v2 <doc> <work>"}
    (kd / f"{S.d['slug']}_업그레이드판_초안.json").write_text(json.dumps(up, ensure_ascii=False, indent=1), encoding="utf-8")
    one = []                                                     # apply-17(Jev 해결 0.60): 추천 후보 위 3개를 칸 하나씩 바꾼 초안(_v2a·b·c) — 뼈대 칸은 0
    for tag, c in zip("abc", [c for c in rec["candidates"] if not c["skeleton"] and c.get("style_cell") not in (None, "미기입")][:3]):
        d1 = {"name": f"{name}_v2{tag}", "base": name, "upgrades": [{"axis": c["element"], "what": c["what"], "source": c["kind"], "cell": c["style_cell"]}],
              "_rule": "칸 하나만(apply-17) — 바꾼 칸 = upgrades[0].cell"}
        bad = one_cell_check(d1)
        (kd / f"{S.d['slug']}_업그레이드판_v2{tag}.json").write_text(json.dumps({**d1, "_check": bad or "칸 하나 · 뼈대 0"}, ensure_ascii=False, indent=1), encoding="utf-8")
        one.append({"draft": f"v2{tag}", "cell": c["style_cell"], "check": bad or "ok"})
    recp = kd / "업그레이드_기록.md"
    if not recp.exists():
        recp.write_text(f"# {S.d['slug']} 업그레이드 기록 — 무엇을 → 왜(수치·채널·편) → 예상 효과 → 검증(측정값|사람 판정)\n(근거 없이 바꾸는 것 금지 — 지침서 §2-6-1)\n", encoding="utf-8")
    return {"one_cell": one, "draft": str(kd / f"{S.d['slug']}_업그레이드판_초안.json"), "record": str(recp), "menu_n": len(up["menu"]), "base": name,
            "kyeol": rec["kyeol"], "kyeol_src": rec["kyeol_src"], "candidates": rec["candidates"], "cannot_build": rec["cannot_build"]}


def _is_video_ref(r: str) -> bool:
    return Path(r).is_file() or bool(re.search(r"(shorts/|watch\?v=|youtu\.be/|/reel/|/video/)", r))


def _expand_refs(refs: list[str]) -> list[str]:
    """폴더면 안의 mp4 전부(이름순)."""
    out = []
    for r in refs:
        p = Path(r)
        out += [str(x) for x in sorted(p.glob("*.mp4"))] if p.is_dir() else [r]
    return out


SKELETON_CELLS = ("placement", "script", "cuts", "timing", "caption.typing_cps", "variant_for", "length", "sfx_key")   # stage_upgrade _rule 의 뼈대 칸


def one_cell_check(d: dict) -> list[str]:
    """(판단 주인 · apply-17) 업그레이드 초안이 base 와 다른 칸이 정확히 1개이고 뼈대 칸(SKELETON_CELLS)은 0개인가."""
    cells = [u.get("cell") for u in d.get("upgrades") or []]
    bad = []
    if len(cells) != 1:
        bad.append(f"바꾼 칸 {len(cells)}개(정확히 1개여야)")
    sk = [c for c in cells if any(str(c or "").startswith(x) for x in SKELETON_CELLS)]
    if sk:
        bad.append(f"뼈대 칸을 바꿈 {sk} — 사장님 확인")
    return bad


def _slug_of(ref: str) -> str:
    h = re.sub(r"^https?://(www\.)?youtube\.com/", "", ref.strip()).split("/")[0].lstrip("@")
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "_", h).strip("_").lower() or "channel"


def ref_key(ref) -> str:
    """같은 벤치인가 대조용 — 주소 꼴(https·www·/shorts·/videos·끝 /)·대소문자를 접는다. 목록 입구(common-23)는 정렬한 목록 글."""
    if isinstance(ref, (list, tuple)):
        return "|".join(sorted(ref_key(x) for x in ref))
    r = str(ref).strip().rstrip("/")
    r = re.sub(r"^https?://(www\.|m\.)?", "", r)
    r = re.sub(r"/(shorts|videos)$", "", r)
    return r.replace("youtube.com/", "").lower()


class State:
    def __init__(self, slug: str, ref, brand: str | None, n: int, hybrid: str | None, voice: str | None = None, fmt: str | None = None):
        self.dir = ROOT / "channel" / slug
        self.path = self.dir / "kal_state.json"
        self.d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"slug": slug, "ref": ref, "steps": {}, "asked": {}}
        if ref_key(self.d.get("ref")) != ref_key(ref):   # select-12(Jev 해결 0.67): 같은 slug 에 다른 채널 상태를 이어 쓰지 않는다
            raise ValueError(f"{self.path} 는 다른 벤치({self.d.get('ref')}) 상태다 — 이번 ref {ref}. --slug 새 이름으로 다시(옛 상태 이어 쓰기 금지)")
        self.d.update({k: v for k, v in (("brand", brand), ("n", n), ("hybrid", hybrid), ("voice", voice), ("format", fmt)) if v is not None})
        self.d.setdefault("n", n)
        self.d.setdefault("format", "shorts")

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), encoding="utf-8")

    def step(self, name) -> dict:
        return self.d["steps"].setdefault(name, {"state": "todo"})

    def mark(self, name, state, sec, outputs=None, note=""):
        self.step(name).update({"state": state, "sec": round(sec, 1), "at": time.strftime("%Y-%m-%d %H:%M"), "outputs": outputs or {}, "note": note})
        self.save()


def _run(cmd: list[str], timeout=1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


# ------------------------------------------------------------------ 단계들 (각각 (state, outputs, note) 를 돌려준다)
def _detail(vid: str) -> dict:
    """편 하나 상세(yt-dlp -J, 받지 않음) — 업로드일·길이. 실패면 {}(이유는 부르는 쪽이 셈)."""
    r = _run(["yt-dlp", "--encoding", "utf-8", "--skip-download", "-J", f"https://www.youtube.com/watch?v={vid}"], timeout=120)
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {}
    return {"upload_date": d.get("upload_date"), "duration": d.get("duration"), "title": d.get("title")}


def _per_day(views, upload_date: str | None, now: float) -> float | None:
    """select-07(Jev 해결 0.78): 누적 조회를 경과일로 나눈다(측정 시각 기준, 최소 1일)."""
    if not upload_date or not views:
        return None
    try:
        t = time.mktime(time.strptime(str(upload_date), "%Y%m%d"))
    except ValueError:
        return None
    return round(views / max(1.0, (now - t) / 86400), 1)


def write_pick_table(base: Path, rows: list[dict], meta: dict) -> Path:
    """select-04(Jev 해결 0.69): 레퍼런스 선정표 — 편마다 주소·제목·조회·업로드일·길이·하루당 조회·주제(사람 칸). 빈 칸이 있으면 부르는 쪽이 멈춘다."""
    L = [f"# 레퍼런스 선정표 — {meta.get('name')} ({meta.get('url')}) · 측정 {meta.get('measured_at')} · 형식 {meta.get('format')}", "",
         "| 순 | id | 주소 | 제목 | 조회 | 업로드일 | 길이(초) | 하루당 조회 | 주제(한 줄 — 사람) |", "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        L.append(f"| {i} | {r['id']} | {r['url']} | {str(r.get('title') or '').replace('|', '/')} | {r.get('views')} | {r.get('upload_date') or ''} | {r.get('duration') or ''} | {r.get('per_day') or ''} | |")
    p = base / "선정표.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p


def step_select(S: State):
    base = DATA / S.d["slug"]
    base.mkdir(parents=True, exist_ok=True)
    now = time.time()
    fmt = S.d.get("format") or "shorts"
    if S.d.get("given"):       # common-23: 영상 주소·파일 목록 입구 — 채널 목록을 읽지 않고 그 편만(엔진이 편을 더하지 않는다)
        rows = [{"id": g["id"], "url": g["url"], "title": g.get("title") or "", "views": g.get("views"), **({} if Path(g["url"]).is_file() else _detail(g["id"]))} for g in S.d["given"]]
        for r in rows:
            r["per_day"] = _per_day(r.get("views"), r.get("upload_date"), now)
        meta = {"name": "(지정 편)", "url": None, "subs": None, "total": len(rows), "view_median": None, "view_max": None,
                "top_ids": [r["id"] for r in rows], "views_per_sub": None, "measured_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(now)), "format": fmt, "given": True}
        (base / "top.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        S.d["channel"] = meta
        pt = write_pick_table(base, rows, meta)
        return "done", {"top": str(base / "top.json"), "pick_table": str(pt)}, f"지정 편 {len(rows)}편(select 건너뜀 — 목록 그대로)"
    u = S.d["ref"].rstrip("/")
    if not u.startswith("http"):
        u = "https://www.youtube.com/" + (u if u.startswith("@") else "@" + u)
    tab = "/videos" if fmt == "long" else "/shorts"            # outside-01: 형식 한 칸(State.format)이 탭·길이 하한을 정한다
    u = re.sub(r"/(shorts|videos)$", "", u) + tab
    r = _run(["yt-dlp", "--encoding", "utf-8", "--flat-playlist", "-J", u], timeout=300)
    if r.returncode != 0 or not r.stdout.strip():
        return "failed", {}, f"yt-dlp flat-playlist 실패: {r.stderr[-300:]}"
    d = json.loads(r.stdout)
    E = sorted([e for e in d.get("entries") or [] if e.get("view_count")], key=lambda e: -e["view_count"])
    if fmt == "long":
        E = [e for e in E if (e.get("duration") or 0) >= LONG_MIN_S]
    if not E:
        return "failed", {}, "조회수 있는 편 0" + (f"(롱폼 {LONG_MIN_S}초 이상)" if fmt == "long" else "")
    views = [e["view_count"] for e in E]
    med = views[len(views) // 2]
    rows = [{"id": e["id"], "url": f"https://www.youtube.com/{'watch?v=' if fmt == 'long' else 'shorts/'}{e['id']}", "views": e["view_count"],
             "title": e.get("title", ""), "duration": e.get("duration"), "upload_date": e.get("upload_date")} for e in E[:50]]
    k = min(len(rows), max(DETAIL_MAX, S.d["n"] * 3))            # select-07: 업로드일은 flat 목록에 없어 상위 k 편만 상세를 연다
    miss = [x for x in rows[:k] if not x.get("upload_date")]
    with ThreadPoolExecutor(4) as ex:
        for x, det in zip(miss, ex.map(lambda x: _detail(x["id"]), miss)):
            x.update({kk: v for kk, v in det.items() if v and not x.get(kk)})
    for x in rows:
        x["per_day"] = _per_day(x["views"], x.get("upload_date"), now)
    ranked = sorted(rows[:k], key=lambda x: -(x["per_day"] if x["per_day"] is not None else -1))   # 정렬 = 하루당 조회(못 잰 편은 뒤)
    no_date = [x["id"] for x in rows[:k] if x["per_day"] is None]
    (base / "top.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {"name": d.get("channel") or d.get("uploader"), "url": u, "subs": d.get("channel_follower_count"), "total": len(E), "view_median": med,
            "view_max": views[0], "top_ids": [x["id"] for x in ranked[:S.d["n"]]], "views_per_sub": round(med / d["channel_follower_count"], 2) if d.get("channel_follower_count") else None,
            "measured_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(now)), "format": fmt, "rank": "하루당 조회(select-07)"}
    S.d["channel"] = meta
    pt = write_pick_table(base, ranked[:S.d["n"]], meta)
    # 선정 기준(시작 문서 §9 1단계: 구독 대비 조회·업로드 빈도·결) — 숫자는 적고 판정은 사람
    note = (f"{meta['name']} 구독 {meta['subs']} 편 {meta['total']} 조회중앙 {med:,} 최대 {views[0]:,} (구독 대비 중앙 {meta['views_per_sub']}) · 하루당 조회순 상위 {S.d['n']}"
            + (f" · 업로드일 못 잼 {len(no_date)}편(뒤로)" if no_date else ""))
    return "done", {"top": str(base / "top.json"), "pick_table": str(pt)}, note


def _sha256_file(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dedupe_ids(base: Path, ids: list[str]) -> tuple[list[str], list[str]]:
    """collect-m01(Jev 해결 0.79): 받은 mp4 sha256 이 같은 편은 앞 편 하나만 남긴다 → (남긴 ids, 뺀 'id=앞id' 목록)."""
    seen, keep, drop = {}, [], []
    for i in ids:
        h = _sha256_file(base / f"{i}.mp4")
        if h in seen:
            drop.append(f"{i}={seen[h]}")
            continue
        seen[h] = i
        keep.append(i)
    return keep, drop


def _fmt_alts(fmt: str) -> list[str]:
    return [a for a in fmt.split("/") if a]


def fetch_one(base: Path, vid: str, url: str, fmt: str, ytdlp=None) -> tuple[int, str]:
    """collect-01(Jev 해결 0.57): 받기 = yt_fetch.ytdlp(멈춤 감시 STALL_SEC · 로그인 쿠키 · 화질 상한 한 곳). 멈춤·형식 없음이면 fmt 의 '/' 대안을 하나씩 따로 다시."""
    if ytdlp is None:
        from tools.calcopy.engine.yt_fetch import ytdlp
    args = ["--encoding", "utf-8", "--merge-output-format", "mp4", "--write-info-json", "-o", str(base / "%(id)s.%(ext)s"), url]
    tried = []
    for f in [fmt] + _fmt_alts(fmt)[1:]:
        try:
            r = ytdlp(["-f", f, *args], timeout=900, stall_sec=STALL_SEC, watch=base / vid)
        except PermissionError as e:       # 전용 계정 없음 — 로그인 없이 회선 두드리지 않는다(조용히 넘기지 않고 실패)
            return 1, f"로그인 계정 없음: {e}"
        why = "멈춤" if r.stalled else "시간 초과" if r.timed_out else "형식 없음" if "Requested format is not available" in (r.stderr or "") else ""
        if r.returncode == 0 and (base / f"{vid}.mp4").exists():
            return 0, ("" if not tried else f"대안 형식 {f} 로 받음(앞: {tried})")
        tried.append(f"{f}:{why or 'rc=' + str(r.returncode)}")
        if not why:                         # 멈춤·형식 없음이 아닌 실패(404 등)는 대안을 돌려도 같다
            break
    return 1, " | ".join(tried) + " " + (r.stderr or "")[-160:]


def step_collect(S: State):
    why = disk_gate("받기")
    if why:
        return "failed", {}, why
    base = DATA / S.d["slug"] / "src"
    base.mkdir(parents=True, exist_ok=True)
    ids = S.d["channel"]["top_ids"]
    given = {g["id"]: g for g in S.d.get("given") or []}
    fmt = YTDLP_LITE if S.d.get("lite") else YTDLP_F
    todo = [i for i in ids if not (base / f"{i}.mp4").exists()]

    def dl(vid):
        g = given.get(vid)
        if g and Path(g["url"]).is_file():          # common-23: 로컬 파일은 복사만
            import shutil
            shutil.copyfile(g["url"], base / f"{vid}.mp4")
            return vid, 0, "로컬 파일 복사"
        url = (g or {}).get("url") or (f"https://www.youtube.com/watch?v={vid}" if S.d.get("format") == "long" else f"https://www.youtube.com/shorts/{vid}")
        # 영상·info 먼저, 자막·댓글은 따로 — 자막 429 하나로 영상까지 버리던 결함(10-27 별헤는쏭 3/5편 실패)
        rc, err = fetch_one(base, vid, url, fmt)
        if rc == 0 and not list(base.glob(f"{vid}*.vtt")):
            s = _run(["yt-dlp", "--encoding", "utf-8", "--skip-download", "--write-auto-subs", "--sub-langs", "ko",
                      "-o", str(base / "%(id)s.%(ext)s"), url], timeout=300)
            if s.returncode != 0:
                print(f"[경보] {vid} 자막(ko.vtt) 못 받음 — 영상은 받음, 받아쓰기는 스피치매틱스로: {s.stderr[-120:]}")
        if rc == 0 and not (base / f"{vid}.comments.json").exists():     # collect-04(Jev 해결 0.61): 댓글 전부 따로(추리지 않음) — 실패해도 영상은 성공
            c = _run(["yt-dlp", "--encoding", "utf-8", "--skip-download", "--write-comments", "--extractor-args", "youtube:max_comments=all",
                      "-o", str(base / f"{vid}.comments.%(ext)s"), url], timeout=600)
            got = list(base.glob(f"{vid}.comments*.info.json"))
            if c.returncode != 0 or not got:
                print(f"[경보] {vid} 댓글 못 받음 — 영상은 받음: {c.stderr[-120:]}")
            else:
                try:
                    cm = json.loads(got[0].read_text(encoding="utf-8")).get("comments") or []
                    (base / f"{vid}.comments.json").write_text(json.dumps(cm, ensure_ascii=False), encoding="utf-8")
                    got[0].unlink()
                except (ValueError, OSError) as e:
                    print(f"[경보] {vid} 댓글 파일 읽기 실패: {e}")
        return vid, rc, err
    errs, notes = [], []
    with ThreadPoolExecutor(2) as ex:        # 무거운 프로세스 동시 ≤4(공통규칙) — 받기는 2
        for vid, rc, err in ex.map(dl, todo):
            if rc != 0:
                errs.append(f"{vid}: {err}")
            elif err:
                notes.append(f"{vid}: {err}")
    have = [i for i in ids if (base / f"{i}.mp4").exists()]
    have, dup = dedupe_ids(base, have)
    if len(have) < max(2, len(ids) // 2) and not (given and len(have) == len(ids) - len(dup)):
        return "failed", {"have": have}, "받은 편이 절반 미만: " + " | ".join(errs) + (f" · 같은 파일 뺌 {dup}" if dup else "")
    return "done", {"src": str(base), "ids": have}, (f"받음 {len(have)}/{len(ids)}({'720p lite' if S.d.get('lite') else '1080p'}, C 여유 {disk_free_gb()}GB)"
                                                     + (f" 실패 {errs}" if errs else "") + (f" · 같은 파일(sha256) 뺌 {dup}" if dup else "") + (f" · {notes}" if notes else ""))


def _stale_tear(p: Path) -> str | None:
    """옛 뜯기.json 을 다시 뜯어야 하나 — 꾸밈 판독을 건너뛴 것(materials=False 시절)·받아쓰기를 claude_cli 로 물어 '미지원' 실패한 것은 다시(11-06 감시 빈 곳 2·3)."""
    try:
        J = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "읽기 실패"
    if "건너뜀" in str((J.get("overlay_rules") or {}).get("failed") or ""):
        return "꾸밈 판독 건너뜀"
    if "미지원" in str(((J.get("audio") or {}).get("transcript") or {}).get("failed") or ""):
        return "받아쓰기 창구 미지원"
    return None


def step_tteutgi(S: State):
    """뜯기 — analyze.analyze 를 materials=True(꾸밈·제작법 판독, tteutgi-29 · Jev 해결 0.77)·llm=tear_llm.ask(그림 claude_cli / 받아쓰기 스피치매틱스 + 소리 판독 제미나이,
    Jev 해결 0.82)로 부른다. 옛 결과가 _stale_tear 에 걸리면 다시 뜯는다(옛 결과 재사용 금지)."""
    from tools.calcopy.engine import analyze, tear_llm
    base = DATA / S.d["slug"] / "src"
    out_root = S.dir / "뜯기"
    done, errs, redo = [], [], []
    extra = [v for v in S.step("collect")["outputs"]["ids"] if v not in ((S.d.get("channel") or {}).get("top_ids") or [])]
    if extra:      # select-04 J137: 선정(또는 회원 지정) 밖 편을 엔진이 뜯지 않는다
        return "failed", {}, f"선정 밖 편 {extra} — select 의 top_ids/지정 편만 뜯는다(select 부터 다시)"
    for vid in S.step("collect")["outputs"]["ids"]:
        out = out_root / vid
        if (out / "뜯기.json").exists():
            why = _stale_tear(out / "뜯기.json")
            if not why:
                done.append(vid)
                continue
            redo.append(f"{vid}({why})")
        try:
            analyze.analyze(str(base / f"{vid}.mp4"), str(out), llm=tear_llm.ask, materials=True)
            done.append(vid)
        except Exception as e:  # 조용한 실패 금지 — 편별로 기록
            errs.append(f"{vid}: {type(e).__name__} {str(e)[:120]}")
    if not done:
        return "failed", {}, "뜯기 0편: " + " | ".join(errs)
    return "done", {"ids": done, "dir": str(out_root)}, (f"뜯기 {len(done)}편" + (f" 다시 뜯음 {redo}" if redo else "") + (f" 실패 {errs}" if errs else "")
                                                         + " (판독=tear_llm: 그림 claude_cli · 받아쓰기 스피치매틱스 · 소리 판독 제미나이)")


def _win(tt: dict):
    w = (tt.get("layout") or {}).get("window")
    return (w[1], w[1] + w[3]) if w and len(w) == 4 else (0, 1920)


def step_frames(S: State):
    base = DATA / S.d["slug"]
    outs = {}
    for vid in S.step("tteutgi")["outputs"]["ids"]:
        od = base / "kal" / f"frames_{vid}"
        if (od / f"판독목록_{vid}.json").exists():
            outs[vid] = str(od)
            continue
        tt = json.loads((S.dir / "뜯기" / vid / "뜯기.json").read_text(encoding="utf-8"))
        y0, y1 = _win(tt)
        from tools.calcopy.engine.readline_tools.build_lr import bands_for   # 띠·창 주인 = readline_tools(지시서 13)
        bd = bands_for(S.d["slug"], tt.get("layout"), vid=vid, mp4=str(base / "src" / f"{vid}.mp4"))
        lst = K.frames_cmd(str(base / "src" / f"{vid}.mp4"), str(od), max(0, y0 - 20), min(1920, y1 + 20), 2, 80,
                           window=tuple(bd["window"]), cap_band=tuple(bd["cap_band"]) if bd["cap_band"] else None, cap_mode=bd["mode"])
        lst.setdefault("readline", {})["bands_why"] = bd["why"]
        (od / f"판독목록_{vid}.json").write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")
        outs[vid] = str(od)
    return "done", {"dirs": outs}, f"시트·0.1초 띠 {len(outs)}편"


def step_skeleton(S: State):
    base = DATA / S.d["slug"]
    ld = S.dir / "줄판독"
    ld.mkdir(parents=True, exist_ok=True)
    kd = S.dir / "_kal"
    kd.mkdir(exist_ok=True)
    made = []
    for vid in S.step("tteutgi")["outputs"]["ids"]:
        p = ld / f"{vid}.json"
        if p.exists():
            continue
        tt = json.loads((S.dir / "뜯기" / vid / "뜯기.json").read_text(encoding="utf-8"))
        vtt = base / "src" / f"{vid}.ko.vtt"
        mp4 = base / "src" / f"{vid}.mp4"
        try:
            loud = K.loud_track(str(mp4)) if mp4.exists() else None     # skeleton-01 0.25초 음량 열
        except Exception as e:  # noqa: BLE001 — 음량 열만 빠지고 뼈대는 만든다(이유를 남김)
            loud = None
            print(f"[경보] {vid} 음량 열 못 잼: {type(e).__name__} {str(e)[:80]}")
        d = K.skeleton(vid, tt, str(vtt) if vtt.exists() else None, loud=loud)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        made.append(vid)
    ids = S.step("tteutgi")["outputs"]["ids"]
    bundle = {"slug": S.d["slug"], "brief": str(kd / "줄판독_브리프.md"), "rule_doc": "tools/calcopy/칼카피_분석지침서.md §2단계 자막 축 A",
              "jobs": [{"id": v, "mp4": str(base / "src" / f"{v}.mp4"), "frames": str(base / "kal" / f"frames_{v}"), "tteutgi": str(S.dir / "뜯기" / v / "뜯기.json"),
                        "skeleton": str(ld / f"{v}.json")} for v in ids],
              "workers": max(1, min(4, (len(ids) + 1) // 2)), "per_worker": 2}
    (kd / "워커묶음.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    tmpl = (ROOT / "channel/starpickroom/_tools/줄판독_브리프.md").read_text(encoding="utf-8")
    brief = tmpl.replace("starpickroom", S.d["slug"]).replace("스타픽룸", S.d.get("channel", {}).get("name") or S.d["slug"])
    brief = ("# " + S.d["slug"] + " 줄판독 브리프 (kal.py 가 스타픽룸 견본에서 만든 초안 — 지휘자가 '지금까지 본 것' 절을 이 채널 것으로 고친 뒤 워커에 준다)\n"
             "★칸·어휘는 `tools/calcopy/칼카피_분석지침서.md` 2단계 자막 축 A 가 주인(role·fit·자간·행간 칸 포함). 뼈대 json 의 _todo 칸을 전부 채우고 `kal_analyze.py check --strict` 통과시킨다.\n\n" + brief)
    if not (kd / "줄판독_브리프.md").exists():      # 지휘자가 고친 '지금까지 본 것'을 다시 돌릴 때 견본으로 덮지 않는다(10-27)
        (kd / "줄판독_브리프.md").write_text(brief, encoding="utf-8")
    return "done", {"skeletons": made, "bundle": str(kd / "워커묶음.json"), "brief": str(kd / "줄판독_브리프.md")}, f"뼈대 {len(made)}편 새로, 묶음 {len(ids)}편"


def step_readlines(S: State):
    """사람 단계 — 줄판독이 다 채워져 check 를 통과해야 done."""
    ld = S.dir / "줄판독"
    ids = S.step("tteutgi")["outputs"]["ids"]
    bad = {}
    for vid in ids:
        p = ld / f"{vid}.json"
        if not p.exists():
            bad[vid] = ["파일 없음"]
            continue
        r = K.check_doc(json.loads(p.read_text(encoding="utf-8")), strict=True)
        if r["errors"]:
            bad[vid] = r["errors"][:5]
    if bad:
        return "waiting_human", {"pending": bad}, f"줄판독 미완 {len(bad)}/{len(ids)}편 — " + HUMAN["readlines"]
    return "done", {"ids": ids}, f"줄판독 {len(ids)}편 strict 통과"


HAND_KEYS = {("bench", "channel"), ("bench", "ko"), ("frame", "window"), ("voice",)}   # 사람이 고른 값 — 있으면 새 초안 값이 이기지 못한다


def _empty(v) -> bool:
    return v is None or v == [] or v == {} or v == ""


def _keep_hand(old, new, path=()):
    """판 초안 병합: 새 값이 비었으면 옛 값(사람이 채운 칸)을 쓰고, HAND_KEYS 칸은 옛 값이 있으면 언제나 옛 값. 그 밖엔 새 집계 값."""
    if path == ("voice",):                         # 목소리는 고른 id 가 있을 때만 옛 값(미정 칸은 새 추천으로)
        return old if isinstance(old, dict) and old.get("voice_id") and not (isinstance(new, dict) and new.get("voice_id")) else new
    if path in HAND_KEYS and not _empty(old):
        return old
    if isinstance(old, dict) and isinstance(new, dict):
        out = dict(new)
        for k, ov in old.items():
            out[k] = _keep_hand(ov, new[k], path + (k,)) if k in new else ov
        return out
    return old if _empty(new) and not _empty(old) else new


def step_rules(S: State):
    kd = S.dir / "_kal"
    kd.mkdir(parents=True, exist_ok=True)      # --from rules(이미 분석한 채널)에서도 돈다
    docs = K._load_docs([str(S.dir / "줄판독")])
    out = K.write_rules(S.dir, docs, S.d["slug"])        # 쓰는 자리 한 곳(회원 흐름 bm_rules 와 같은 함수)
    R, Sc, P = out["rules"], out["script"], out["palette"]
    draft = S.dir / "_kal" / "스타일분석_초안.md"
    draft.write_text("# 스타일분석 초안(kal.py rules — 규칙빈도·대본언어·팔레트 자동 집계. 사람이 §3 꼴로 옮겨 적고 규칙을 채택한다)\n\n"
                     + K.rules_md(R, S.d["slug"]) + "\n" + K.script_md(Sc) + "\n## 팔레트(channel/<slug>/팔레트.json)\n"
                     + "\n".join(f"- {role}: " + ", ".join(f"{g['hex']}×{g['n_lines']}줄/{g['n_docs']}편" for g in lst[:6]) for role, lst in P["roles"].items() if lst) + "\n", encoding="utf-8")
    # 판 설정 초안 — tools/calcopy/hybrid/styles/<판>.json 스키마(주인 = 관제 235, README.md·_common.json) 꼴로 **초안만** `_kal/<slug>판_초안.json`.
    # styles/ 에 넣는 것·새 칸 추가는 그쪽 세션(스키마 주인). 정밀 측정값(자간·행간·팔레트·키프레임)은 판 파일에 안 넣고 channel/<slug>/ 파일을 경로로 가리킨다.
    sp = R["by_speaker"]
    def mode(k):
        e = (sp.get(k) or {}).get("enter") or {}
        return max(e, key=e.get) if e else None
    durs = [e["dur"] for e in R["episodes"] if e["dur"]]
    tts = {}
    for vid in S.step("tteutgi")["outputs"]["ids"][:1]:
        p = S.dir / "뜯기" / vid / "뜯기.json"
        if p.exists():
            tts = json.loads(p.read_text(encoding="utf-8"))
    lay = tts.get("layout") or {}
    narr_cps = [e["narr_cps"] for e in R["episodes"] if e.get("narr_cps")]
    plan = {"name": f"{S.d['slug']}판", "renderer": "bench",
            "_note": f"kal.py rules 초안({time.strftime('%Y-%m-%d')}) — 칸 이름은 styles/README.md 스키마. null 칸은 사람이 채운다(_todo). 정밀값은 bench.analysis·palette 경로로.",
            "bench": {"ko": (S.d.get("channel") or {}).get("name"), "channel": S.d["ref"], "analysis": f"channel/{S.d['slug']}/스타일분석.md",
                      "line_reads": f"channel/{S.d['slug']}/줄판독/", "src_dir": str(DATA / S.d["slug"] / "src"), "sfx_events": None, "sfx_key": None,
                      "palette": f"channel/{S.d['slug']}/팔레트.json", "rules_counted": f"channel/{S.d['slug']}/_kal/규칙빈도.json"},
            "voice": ({"name": next((v["name"] for v in KNOWN_VOICES if v["voice_id"] == S.d["voice"]), S.d["voice"]), "voice_id": S.d["voice"],
                       "candidates": [], "why": "사장님이 시작할 때 고름(kal.py --voice)"}
                      if S.d.get("voice") else
                      {"name": None, "voice_id": None, "candidates": [], "why": "미정 — 사장님께(kal.py 시작 질문, 추천: " + voice_recommend(S) + ")"}),
            "cps_target": round(statistics.median(narr_cps), 2) if narr_cps else None,
            "bgm": {"id": None, "db_below_voice": None, "duck_orig_db": None, "fade_out": None, "why": "engine/sound/bgm_fp.py·뜯기 audio"},
            "loudness": {"lufs": -14, "tp": -1.5},
            "length": {"min": round(min(durs), 1) if durs else None, "max": round(max(durs), 1) if durs else None,
                       "by_form": R.get("by_form") or {}},      # rules-05 형식별 길이(줄판독 form 칸)
            "script": {"brief": [f"{k}: 어미 " + ", ".join(e["ending"] for e in v["endings"][:4]) + f" · 존댓말 {v['honorific_rate']} · 전언 {v['report_rate']} · 자수 중앙 {v['chars']['med']}"
                      + f" · 같은 어미 연달아 {v.get('same_ending_run')} · 잇는:맺는 {v.get('connect_vs_close')}" for k, v in Sc.items() if not k.startswith("_")]
                     + [f"박자: {r} 첫 등장 {b['med_pct']}%({b['min_pct']}~{b['max_pct']}, {b['n']}편)" for r, b in (R.get("beat_pos") or {}).items()],
                       "example": (Sc.get("나레") or {}).get("first_lines", [])[:3], "audit": [],
                       "beat_pos": R.get("beat_pos") or {}, "tail_s": R.get("tail_s"),           # rules-09 박자 시점 %·끝 꼬리 초
                       "end_forms": Sc.get("_end_forms"), "title_stats": Sc.get("_title_stats")},  # rules-11·25
            "frame": {"window": lay.get("window"), "title": [], "logo": None, "credit": None, "watermark": None, "comment": None},
            "caption": {"pack": None, "pack_default": None, "variant_for": {}, "typing_cps": (sp.get("나레") or {}).get("cps")},
            "timing": None, "cuts": None, "sfx_files": None,
            "placement": {"rules": {"narr_enter": mode("나레"), "orig_enter": mode("원음"),
                                    "fx_rate": {k: round(v["any"] / v["n"], 2) for k, v in sp.items() if v["n"]},
                                    "plain_rate": round(R["plain"]["n"] / max(1, R["plain"]["denom"]), 2),
                                    "by_pos": {k: round(v["any"] / v["n"], 2) for k, v in R["by_pos"].items() if v["n"]},
                                    "strong": [f"{c['cond']} → {c['effect']} {c['k']}/{c['n']}" for c in R["rules"] if c["grade"] == "강"][:20]},
                          "counted": {}},
            "_todo": ["voice·bgm·sfx = engine/sound 결과", "frame.title/logo/credit = 스타일분석 §틀", "caption.pack = caption-motions.js 팩 이름(없으면 요청서)", "timing·cuts·sfx_files = 견본 styles/키치잇판.json 꼴"]}
    pp = kd / f"{S.d['slug']}판_초안.json"
    if pp.exists():                                # 다시 돌 때 사람이 채운 손칸(ref·창·목소리·제목…)을 비우지 않는다(06 보고 10-25 — rules_only 재집계가 덮어썼다)
        try:
            plan = _keep_hand(json.loads(pp.read_text(encoding="utf-8")), plan)
        except (ValueError, OSError):
            pass
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    if not (S.dir / "스타일분석.md").exists():
        return "waiting_human", {"draft": str(draft), "plan_draft": str(kd / f"{S.d['slug']}판_초안.json")}, HUMAN["rules"]
    return "done", {"draft": str(draft), "palette": str(S.dir / "팔레트.json"), "plan_draft": str(kd / f"{S.d['slug']}판_초안.json")}, "규칙빈도·대본언어·팔레트·판 설정 초안 + 스타일분석.md 있음"


def step_copy(S: State):
    fr = DATA / S.d["slug"] / "frames"
    fr.mkdir(parents=True, exist_ok=True)
    made, errs = [], []
    for vid in S.step("tteutgi")["outputs"]["ids"]:
        out = fr / f"frame_{vid}.json"
        if out.exists():
            made.append(vid)
            continue
        r = _run([sys.executable, str(ROOT / "tools/calcopy/engine/to_frame.py"), str(S.dir / "뜯기" / vid / "뜯기.json"), "--out", str(out), "--no-ocr"], timeout=600)
        (made if r.returncode == 0 else errs).append(vid if r.returncode == 0 else f"{vid}: {r.stderr[-160:]}")
    presets = [p for p in (S.dir / "preset").glob("*/manifest.json")] if (S.dir / "preset").exists() else []
    if not presets:
        return "waiting_human", {"frames": made, "errs": errs}, HUMAN["copy"] + f" (견본 channel/starpickroom/preset/spr_preset.py · 자동본 {fr})"
    return "done", {"frames": made, "preset": str(presets[0].parent)}, f"자동 설명서 {len(made)}편 · 프리셋 {presets[0].parent.name}"


def _rendered(mp4: str) -> bool:
    """렌더 기록이 있는 완성본인가 — 옆 run_log.json(preset_make 가 씀) final.md5 == 파일 md5. 파일만 있는 것은 인정 안 함(감시 적발 kal.py:524)."""
    import hashlib
    p = Path(mp4)
    lp = p.parent / "run_log.json"
    if not (p.is_file() and lp.is_file()):
        return False
    try:
        want = (json.loads(lp.read_text(encoding="utf-8")).get("final") or {}).get("md5")
    except ValueError:
        return False
    return bool(want) and hashlib.md5(p.read_bytes()).hexdigest() == want


def preset_fonts(pdir: Path) -> list[str]:
    """프리셋 frame.json 글 층 글꼴 이름($ 자리표 뺌) → 파일 경로(fontmatch.font_paths 이름 대조). 못 찾은 이름은 '없음:<이름>'."""
    from tools.calcopy.engine.fontmatch import font_paths
    names = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "font" and isinstance(v, str) and v and not v.startswith("$"):
                    names.add(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for f in pdir.glob("frame*.json"):
        try:
            walk(json.loads(f.read_text(encoding="utf-8")))
        except ValueError:
            pass
    by = {Path(p).stem.lower(): p for p in font_paths()}
    return [by.get(Path(n).stem.lower(), f"없음:{n}") for n in sorted(names)]


def glyph_gate(pdir: Path, wdir: Path) -> list[str]:
    """(make-화면자막-06 · Jev 해결 0.57) 렌더 전 — 대본 모든 줄 글자를 판 글꼴마다 fontmatch.missing_glyphs 로 대조. 빠진 글자·못 찾은 글꼴 목록."""
    from tools.calcopy.engine.fontmatch import missing_glyphs
    sp = wdir / "대본.json"
    if not sp.exists():
        return []
    S_ = json.loads(sp.read_text(encoding="utf-8"))
    text = "".join(str(l.get("text") or l.get("line") or "") for l in (S_.get("lines") or S_.get("spine55") or [])).replace("/", "")
    out = []
    for fp in preset_fonts(pdir):
        if fp.startswith("없음:"):
            out.append(f"글꼴 파일 못 찾음 {fp[3:]}")
            continue
        m = missing_glyphs(fp, text)
        if m:
            out.append(f"{Path(fp).name}: {''.join(m[:10])!r}")
    return out


def step_make(S: State):
    """제작 — 판단 주인 preset_make.make_one 을 부른다(make-00 Jev 해결 0.88 · 구현 방식 해결 0.74). 입력 = copy 단계 프리셋 폴더 + --work 작업 폴더(대본.json·재료.json).
    출력 = final.mp4 + 우리줄.json(kal_analyze.ours_from_preset_make). make_one 미달·멈춤 = failed. --ours-mp4 직접 넣기는 렌더 기록(_rendered)이 있을 때만."""
    why = disk_gate("렌더")
    if why:
        return "failed", {}, why
    om, ol = S.d.get("ours_mp4"), S.d.get("ours_lines")
    wd = S.d.get("work")
    if om and ol and not wd:
        if not (Path(om).exists() and Path(ol).exists()):
            return "failed", {}, f"--ours-mp4/--ours-lines 파일 없음: {om} · {ol}"
        if not _rendered(om):
            return "failed", {}, f"렌더 기록 없는 완성본({om} 옆 run_log.json final.md5 짝 없음) — 파일만으로는 done 안 함. --work <작업 폴더> 로 preset_make 를 돌려라"
        return "done", {"ours_mp4": om, "ours_lines": ol}, "시험편 있음(렌더 기록 md5 일치)"
    if not wd:
        return "waiting_human", {}, HUMAN["make"]
    pdir = (S.step("copy").get("outputs") or {}).get("preset")
    if not pdir or not (Path(pdir) / "manifest.json").exists():
        return "failed", {}, f"copy 단계 프리셋 폴더 없음({pdir}) — copy 부터"
    miss = glyph_gate(Path(pdir), Path(wd))
    if miss:
        return "failed", {}, f"판 글꼴에 없는 대본 글자 — {miss[:6]} (글꼴 몰래 바꾸기 금지 · make-화면자막-06)"
    from types import SimpleNamespace
    from tools.calcopy.engine import preset_make
    a = SimpleNamespace(plan=False, allow_tts=True, tts=None, test=True, out=str(Path(wd) / f"kal_make_{time.strftime('%m%d_%H%M%S')}"), tag=None, cache=None,   # common-10: 매번 새 이름(지난 편 덮어쓰기 금지)
                        desktop_dir=str(Path.home() / "Desktop"), results=str(preset_make.RESULTS))   # test=True: 바탕화면·결과물 등록은 사람 판정(verify) 뒤
    try:
        r = preset_make.make_one(Path(pdir), Path(wd), a)
    except (Exception, SystemExit) as e:   # make_one 은 칸 없음을 SystemExit 로 멈춘다 — 조용히 넘기지 않고 이유를 적는다
        return "failed", {}, f"preset_make 멈춤: {type(e).__name__} {str(e)[:300]}"
    out = Path(r.get("out") or "")
    if not r.get("ok"):
        return "failed", {"out": str(out)}, f"preset_make 자동 검사 미달: {r.get('note')}"
    lines = K.ours_from_preset_make(out, Path(wd))
    lp = out / "우리줄.json"
    lp.write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    S.d["ours_mp4"], S.d["ours_lines"] = str(out / "final.mp4"), str(lp)
    return "done", {"ours_mp4": str(out / "final.mp4"), "ours_lines": str(lp), "out": str(out)}, f"preset_make 통과 {r.get('seconds')}초 · {r.get('note')}"


def frame_texts(S: State) -> list[str]:
    """copy 단계 프리셋 설명서(frame.json·manifest)의 글 칸(text·title·brand·channel_name) 전부 — 화면 틀 글 관문(verify-m01) 재료."""
    out = []
    pd = (S.step("copy").get("outputs") or {}).get("preset")

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("text", "title", "brand", "channel_name", "label") and isinstance(v, str):
                    out.append(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    if pd and Path(pd).exists():
        for f in Path(pd).glob("*.json"):
            try:
                walk(json.loads(f.read_text(encoding="utf-8")))
            except ValueError:
                pass
    return out


def _sha256(p: str) -> str:
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def step_verify(S: State):
    """검증 — 줄 단위 자 + 픽셀·소리 자(with_pixel) 하나의 판정. 벤치 mp4 가 없으면 픽셀 층을 건너뛰지 않고 미달·failed(감시 A2, Jev 해결 0.74).
    자동 통과 뒤에도 사람 시청 판정(_kal/시청판정.json, 지금 ours_mp4 sha256 짝)이 있어야 done(verify-07, Jev 해결 0.78) — 없으면 시청 묶음을 만들고 waiting_human."""
    o = S.step("make")["outputs"]
    bench = K._load_docs([str(S.dir / "줄판독")])
    ours = json.loads(Path(o["ours_lines"]).read_text(encoding="utf-8"))
    K.attach_bench_asr(bench, S.dir / "뜯기")          # readlines-09·11 받아쓰기 자(벤치 = 뜯기 transcript)
    win = K._win_arg(None, bench)
    om = K.media_of(o["ours_mp4"], win)
    bm = K.bench_media_src(str(DATA / S.d["slug"] / "src"), [d.get("id") for d in bench], win)
    T = K.match_table(bench, ours, om, bm)
    T["ours_media"], T["bench_media"] = om, bm
    texts = [str(l.get("text") or "") for l in K._ours_lines(ours)[0]] + frame_texts(S)
    ch = S.d.get("channel") or {}
    T["name_check"] = K.name_check(texts, [ch.get("name") or "", S.d["slug"]], S.d.get("brand"))     # verify-m01
    T["hygiene"] = K.text_hygiene(texts)                                                             # verify-14
    if T["name_check"] or T["hygiene"]:
        T["verdict"] = "미달"
    kd = S.dir / "_kal"
    kd.mkdir(parents=True, exist_ok=True)
    out = kd / "재현일치도.md"
    bmp4 = next((p for p in (DATA / S.d["slug"] / "src" / f"{d.get('id')}.mp4" for d in bench) if p.exists()), None)
    if bmp4:   # 1차 프리셋 관문 하나 = 줄 단위 자 + 픽셀·소리 자(compare) — 둘 다 통과여야 통과(지침서 맨 위 엔진 순서)
        K.with_pixel(T, str(bmp4), o["ours_mp4"], str(kd / "재현일치도_픽셀"))
    else:
        T["pixel"] = {"verdict": "미측정", "n_in": 0, "n_criteria": 0, "out": [], "failed": ["벤치 mp4 없음 — 픽셀·소리 자 못 잼"], "table": ""}
        T["line_verdict"], T["verdict"] = T["verdict"], "미달"
        print(f"[경보] 벤치 mp4 없음({DATA / S.d['slug'] / 'src'}) — 픽셀·소리 자를 건너뛰지 않고 미달로 둔다")
    out.write_text(K.match_md(T, S.d["slug"]), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
    res = {"table": str(out), "verdict": T["verdict"]}
    if T["name_check"] or T["hygiene"]:
        return "failed", res, f"글 관문 미달 — 채널명 {T['name_check']} · 금지 낱말 {T['hygiene']}"
    if not bmp4:
        return "failed", res, "벤치 mp4 없음 — collect 를 다시 돌려 벤치 원본을 받은 뒤 verify"
    if T["verdict"] != "통과":
        return "waiting_human", res, f"재현일치도 {T['verdict']} — 미달이면 어긋난 항목을 고쳐 make 부터"
    wp = kd / "시청판정.json"
    sha = _sha256(o["ours_mp4"])
    W = {}
    if wp.exists():
        try:
            W = json.loads(wp.read_text(encoding="utf-8"))
        except ValueError:
            W = {}
    if W.get("sha256") == sha and W.get("verdict") == "통과":
        return "done", {**res, "watch": str(wp)}, f"재현일치도 통과 + 사람 시청 판정 통과({W.get('who') or '?'})"
    if W.get("sha256") == sha and W.get("verdict") == "미달":
        return "failed", {**res, "watch": str(wp)}, f"사람 시청 판정 미달: {W.get('why')}"
    pack = K.watch_pack(str(bmp4), o["ours_mp4"], kd / "시청묶음")
    tmpl = json.dumps({"sha256": sha, "verdict": "통과|미달", "who": "", "why": ""}, ensure_ascii=False)
    return "waiting_human", {**res, "watch_pack": pack}, f"재현일치도 통과 — 사람 시청 판정 없음(또는 다른 편 판정). 시청 묶음 {kd / '시청묶음'} 를 보고 {wp} 에 {tmpl} 를 적은 뒤 다시 실행"


def step_apply(S: State):
    from shopping_shorts import calcopy_board as B
    kd = S.dir / "_kal"
    kd.mkdir(parents=True, exist_ok=True)
    mo = S.step("make").get("outputs") or {}
    if mo.get("out") and (Path(mo["out"]) / "timeline.json").exists():      # apply-15(Jev 해결 0.64): 완료 보고에 장면표 — 행 = 컷, 빈칸 0
        md, empty = K.scene_table(mo["out"])
        (kd / "장면표.md").write_text(f"# 장면표 — {mo.get('ours_mp4')}\n\n" + md, encoding="utf-8")
        if empty:
            return "waiting_human", {"scene_table": str(kd / "장면표.md")}, f"장면표 빈칸 {len(empty)}: {empty[:6]} — 채운 뒤 다시"
    top = DATA / S.d["slug"] / "top.json"
    pp = kd / f"{S.d['slug']}판_초안.json"
    if top.exists() and pp.exists():                                          # apply-08(Jev 해결 0.62): 벤치 제목 꼴 → 판 초안 upload.title
        plan = json.loads(pp.read_text(encoding="utf-8"))
        plan.setdefault("upload", {})["title"] = {**K.title_of(json.loads(top.read_text(encoding="utf-8"))), "_rule": "편마다 3안은 이 꼴로(사람) · 같은 문장 0"}
        pp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    ch = S.d.get("channel") or {}
    up = kd / "업로드글.txt"
    if up.exists():                                                         # apply-09: 업로드 글 금지 낱말·해시태그
        from tools.calcopy.engine import upload_pack
        plan = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
        ub = upload_pack.check(up.read_text(encoding="utf-8"), (plan.get("upload") or {}))
        if ub:
            return "waiting_human", {"upload": str(up)}, f"업로드 글 관문 {ub}"
    pdir = (S.step("copy").get("outputs") or {}).get("preset")
    W = (S.step("verify").get("outputs") or {}).get("watch")
    froze = None
    if pdir and W and Path(W).exists() and mo.get("ours_mp4"):            # apply-05: 시청 판정 통과 시험편으로 확정 기록
        from tools.calcopy.engine import preset_save
        Wd = json.loads(Path(W).read_text(encoding="utf-8"))
        froze = preset_save.freeze(Path(pdir), mo["ours_mp4"], Wd.get("verdict"), f"kal verify 시청 판정({Wd.get('who')}) · 재현일치도 통과")
    gone = cleanup(S) if froze else None                                    # apply-06: 확정 뒤에만 중간물 정리
    om = (S.step("make").get("outputs") or {}).get("ours_mp4")
    if om and om not in (S.d.get("made") or []):
        S.d.setdefault("made", []).append(om)          # 확정 시험편 = 지킬 파일(common-10 write_guard)
    B.set_step(S.d["slug"], "2", "done", f"kal.py 분석 {len(S.step('tteutgi')['outputs']['ids'])}편 · 재현일치도 {S.step('verify')['outputs'].get('verdict')}",
               [f"channel/{S.d['slug']}/스타일분석.md", f"channel/{S.d['slug']}/팔레트.json"], name=ch.get("name"), url=ch.get("url"), stats={"subs": ch.get("subs"), "total": ch.get("total")})
    todo = S.dir / "_kal" / "장부_할일.md"
    todo.write_text(f"# 장부 반영 할 일({S.d['slug']}) — 사람이 적는다(공유 json 은 다시 읽고 내 항목만)\n"
                    f"- channel/브랜드.json: 우리 브랜드 '{S.d.get('brand') or '(미정 — 사장님께)'}' ↔ 벤치 {S.d['slug']}\n"
                    f"- channel/스타일.json options/strengths: 스타일분석.md §1 규칙(근거 편·숫자·출처)\n- channel/결과물.json: 시험편 등록(preset_make 가 자동)\n"
                    f"- 하이브리드 {S.d.get('hybrid') or '(미정)'} → 하이브리드_판설계.md\n- 반영은 preset_publish.py(요청 때/02:00)\n", encoding="utf-8")
    return "done", {"todo": str(todo), "frozen": bool(froze), "cleanup": gone}, "원장 2단계 done · 장부 할일 적음" + (f" · 확정 v{froze.get('version')}" if froze else "") + (f" · 정리 {gone['removed']}개" if gone else "")


CLEAN_DROP = ("kal/frames_*", "kal/*/strips")                 # apply-06 지울 것(확정 뒤 다시 만들 수 있는 판독 시트·띠) — DATA/<slug> 기준
CLEAN_KEEP = ("src/*.mp4", "src/*.info.json", "src/*.vtt", "src/*.comments.json", "top.json", "선정표.md", "frames/frame_*.json")   # 남길 것(원본·유료 결과·설명서)


def cleanup(S: State) -> dict:
    """(판단 주인 · apply-06 Jev 해결 0.71) 확정(frozen) 뒤 중간물 정리 — 지울 목록·남길 목록 한 곳. 지운 뒤 두 목록을 다시 세어 검사(남길 것이 줄면 RuntimeError)."""
    import shutil
    base = DATA / S.d["slug"]
    keep0 = sorted(str(p) for g in CLEAN_KEEP for p in base.glob(g))
    removed = 0
    for g in CLEAN_DROP:
        for p in base.glob(g):
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
            removed += 1
    keep1 = sorted(str(p) for g in CLEAN_KEEP for p in base.glob(g))
    left = [str(p) for g in CLEAN_DROP for p in base.glob(g)]
    if keep1 != keep0 or left:
        raise RuntimeError(f"정리 검사 실패 — 남길 것 {len(keep0)}→{len(keep1)} · 안 지워진 것 {left[:3]}")
    return {"removed": removed, "kept": len(keep1)}


RUN = {"select": step_select, "collect": step_collect, "tteutgi": step_tteutgi, "frames": step_frames, "skeleton": step_skeleton, "readlines": step_readlines,
       "rules": step_rules, "copy": step_copy, "make": step_make, "verify": step_verify, "apply": step_apply}


def guard_snapshot(S: State) -> dict:
    """common-10(Jev 해결 0.52): 지킬 파일 md5 — 확정 프리셋(manifest.frozen_at 있는 channel/<slug>/preset/*/ 전부) + 지난 시험편(S.d.made 에 적힌 완성본)."""
    import hashlib
    out = {}
    for m in sorted((S.dir / "preset").glob("*/manifest.json")) if (S.dir / "preset").exists() else []:
        try:
            frozen = json.loads(m.read_text(encoding="utf-8")).get("frozen_at")
        except ValueError:
            frozen = None
        if frozen:
            for f in sorted(m.parent.rglob("*")):
                if f.is_file():
                    out[str(f)] = hashlib.md5(f.read_bytes()).hexdigest()
    for f in S.d.get("made") or []:
        if Path(f).is_file():
            out[f] = hashlib.md5(Path(f).read_bytes()).hexdigest()
    return out


def write_guard(before: dict, after: dict) -> list[str]:
    """단계 전후 md5 대조 — 바뀌거나 없어진 지킬 파일 목록(새로 생긴 것은 문제 아님)."""
    return [f"{k}({'없어짐' if k not in after else '바뀜'})" for k, v in before.items() if after.get(k) != v]


def guide_check(S: State) -> list[str]:
    """common-17(Jev 해결 0.60): 지침서·98 오류 기록 md5 를 지난번 읽은 값과 대조 — 바뀐 파일과 바뀐 절 제목(## 줄) 목록을 돌려주고 State 에 읽음 기록.
    바뀌었으면 사람 단계(readlines·rules·copy)를 todo 로 돌려 다시 재게 한다(바뀐 규칙으로 done 을 그대로 두지 않는다)."""
    import hashlib
    seen = S.d.setdefault("read_md5", {})
    heads = S.d.setdefault("read_heads", {})
    changed = []
    for rel in GUIDE_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        h = hashlib.md5(t.encode("utf-8")).hexdigest()
        hs = [ln.strip() for ln in t.splitlines() if ln.startswith("#")]
        if seen.get(rel) and seen[rel] != h:
            new = [x for x in hs if x not in set(heads.get(rel) or [])]
            changed.append(f"{rel} 바뀜" + (f" — 새/바뀐 절: {new[:8]}" if new else ""))
        seen[rel], heads[rel] = h, hs
    if changed:
        for k in ("readlines", "rules", "copy"):
            if S.step(k).get("state") == "done":
                S.step(k)["state"] = "todo"
    return changed


def run(S: State, start: str | None = None, log=print) -> dict:
    i0 = STEPS.index(start) if start else 0
    for c in guide_check(S):
        log(f"[지침 바뀜] {c} — 사람 단계(readlines·rules·copy)를 다시 잰다")
    for name in STEPS[i0:]:
        st = S.step(name)
        if st.get("state") == "done" and not start:     # --from = 그 단계부터 **뒤 단계 전부** 다시(10-27: 받기 5편 늘었는데 frames·skeleton 이 옛 2편으로 건너뜀)
            log(f"[건너뜀] {name}: {st.get('note', '')}")
            continue
        t = time.time()
        g0 = guard_snapshot(S)
        try:
            state, outputs, note = RUN[name](S)
        except Exception as e:
            state, outputs, note = "failed", {}, f"{type(e).__name__}: {str(e)[:200]}"
        bad = write_guard(g0, guard_snapshot(S))
        if bad:
            state, note = "failed", f"지킬 파일(확정 프리셋·지난 시험편)이 {name} 단계에서 바뀜: {bad[:5]} — " + note
        S.mark(name, state, time.time() - t, outputs, note)
        log(f"[{state}] {name} {S.step(name)['sec']}초 — {note}")
        if state != "done":
            log("\n다음(세션이 할 일): " + (HUMAN.get(name, "원인을 고치고 같은 명령을 다시 실행") if state == "waiting_human" else "실패 원인을 고치고 같은 명령을 다시 실행"))
            log(f"상태 파일: {S.path}")
            break
    return S.d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref", nargs="+", help="채널 주소·@핸들 하나, 또는 영상 주소·영상 파일·폴더 목록(common-23 — 그 편만 분석)")
    ap.add_argument("--format", dest="fmt", choices=["shorts", "long"], help="shorts(기본) | long(가로 8분+ 롱폼 갈래, outside-01)")
    ap.add_argument("--slug"); ap.add_argument("--brand"); ap.add_argument("--n", type=int, default=6); ap.add_argument("--from", dest="start", choices=STEPS)
    ap.add_argument("--hybrid", choices=["예", "아니오"]); ap.add_argument("--voice", help="TTS voice_id(사장님이 고른 것 — 판 파일 voice 한 곳에 적힌다)")
    ap.add_argument("--ours-mp4"); ap.add_argument("--ours-lines")
    ap.add_argument("--work", help="제작 작업 폴더(대본.json·재료.json) — make 단계가 preset_make.make_one 으로 렌더한다")
    ap.add_argument("--menu", help="장점 카탈로그만 보기: 축 이름 또는 all (채널 분석 없이)")
    ap.add_argument("--lite", action="store_true", help="시운전·디스크 부족: 720p 까지만 받기")
    ap.add_argument("--stage", choices=["upgrade"], help="upgrade = 업그레이드 단계 자리(1차 판 초안 복사 + 메뉴 + 기록 파일)")
    A = ap.parse_args(argv)
    refs = _expand_refs(A.ref)
    given = None
    if len(refs) > 1 or _is_video_ref(refs[0]):
        from tools.calcopy.engine.bench_member import given_videos   # 영상 주소·파일 → id 주인 한 곳
        given = given_videos(refs)
        if not A.slug:
            raise SystemExit("영상 목록 입구는 --slug 를 정해 주세요(채널 핸들에서 이름을 못 뽑는다)")
    A.ref = refs if given else refs[0]
    slug = A.slug or _slug_of(A.ref)
    if A.menu:
        for r in menu(A.menu):
            print(f"[{r['axis']}({r['axis_src']})] {r['kind']} | {str(r['what'])[:90]} | 출처 {r['channel']} | 엔진 {r['engine']} | 판 칸 {r['style_cell']}")
        return 0
    S = State(slug, A.ref, A.brand, A.n, A.hybrid, A.voice, A.fmt)
    if given:
        S.d["given"], S.d["n"] = given, len(given)        # 지정 편이 있으면 엔진이 n 을 늘리지 않는다(select-04)
    if A.lite:
        S.d["lite"] = True
    print(f"C 여유 {disk_free_gb()}GB (경고 {DISK_WARN_GB} · 거절 {DISK_STOP_GB})")
    if A.ours_mp4:
        S.d["ours_mp4"] = A.ours_mp4
    if A.ours_lines:
        S.d["ours_lines"] = A.ours_lines
    if A.work:
        S.d["work"] = str(Path(A.work).resolve())
    ask = [q for q, v in (("우리 브랜드 이름(--brand)", S.d.get("brand")), ("하이브리드 여부(--hybrid)", S.d.get("hybrid")), ("TTS 누구로(--voice <voice_id>)", S.d.get("voice"))) if not v]
    if ask:
        print("사장님께 시작할 때 한 번에 물을 것(답을 받으면 같은 명령에 옵션으로): " + " · ".join(ask) + " · 과금 단계(TTS)는 허락됨")
        if not S.d.get("voice"):
            print("  쓸 수 있는 목소리(필재 금지) — 추천 1순위: " + voice_recommend(S))
            for v in voice_candidates():
                print(f"   - {v['name']} {v['voice_id']} [{v['engine']}] 배속 {tempo_of(v['voice_id'])} 쓰는 판 {','.join(v['used_in']) or '-'} {v['note']}")
    if A.stage == "upgrade":
        S.save()
        r = stage_upgrade(S)
        print(f"업그레이드 단계: base {r['base']} · 결 {r['kyeol']}({r['kyeol_src']}) · 초안 {r['draft']} · 기록 {r['record']} · 메뉴 {r['menu_n']}건")
        print(f"추천 후보 {len(r['candidates'])}건(사람이 고른다 — 자동 반영 없음) · 엔진 × 못 만듦 {len(r['cannot_build'])}건")
        for c in r["candidates"]:
            print(f"  {c['rank']:2d}. [{c['element']}{' 뼈대' if c['skeleton'] else ''}] {c['kind']} 같은결={'○' if c['same_kyeol'] else '×'} 조회 {int(c['views']):,} 엔진 {c['engine']}"
                  f"{' · 부딪침 ' + str(c['conflict']['with']) + ' ' + c['conflict']['rule'] if c.get('conflict') else ''} | {str(c['what'])[:60]}")
        print("측정: PYTHONUTF8=1 py tools/calcopy/engine/upgrade_table.py <업그레이드판> <doc> <work>")
        return 0
    S.save()
    run(S, A.start)
    times = {k: v.get("sec") for k, v in S.d["steps"].items()}
    print("단계 시간(초): " + json.dumps(times, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
