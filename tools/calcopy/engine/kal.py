# -*- coding: utf-8 -*-
"""칼카피 한 입구 — "<채널> 칼카피하자" 한마디로 선정→수집→뜯기→판독 묶음→규칙→카피→제작→검증→적용 (관제 097, 2026-10-20).
    PYTHONUTF8=1 py tools/calcopy/engine/kal.py <채널주소|@핸들> [--slug <slug>] [--brand <우리 브랜드>] [--n 6] [--from <단계>] [--hybrid 예|아니오]
                                               [--ours-mp4 <시험편.mp4> --ours-lines <자막표|줄판독.json>]
상태 = channel/<slug>/kal_state.json (단계마다 state·sec·outputs). 끝난 단계는 건너뛴다. --from 으로 그 단계부터 다시.
사람(Claude 눈) 단계에서는 멈추지 않고 **할 일 묶음**(판독 프레임 목록·줄판독 뼈대·워커 브리프)을 만들어 두고 state=waiting_human 으로 끝낸다.
세션은 지침서 `tools/calcopy/칼카피_분석지침서.md` §실행 대본 순서로 묶음을 워커에 나눠 주고, 결과가 들어오면 같은 명령을 다시 돌린다.
판단 주인: 단계 순서·건너뛰기·멈춤 = 이 파일 STEPS/run 한 곳. 각 단계의 판단은 기존 주인 함수(analyze.analyze·kal_analyze.*·to_frame.build·calcopy_board.set_step)를 부른다.
제미나이 금지(사장님 10-18): 뜯기의 LLM 창구 = _claude_llm(claude_cli.ask 어댑터 · 소리 받아쓰기는 못 하므로 실패로 기록된다 — 받아쓰기는 vtt·스피치매틱스).
경계(관제 235 합의 10-20): kal.py = 분석 입구(~판 설정 초안 `_kal/판설정_초안.json`). 제작은 렌더러를 만들지 않고 preset_make / hybrid/run.py 를 부른다. 소리 도구 = tools/calcopy/engine/sound/.
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
DISK_WARN_GB, DISK_STOP_GB = 15, 3                        # 루트 CLAUDE.md 디스크 병목 규칙 + 사장님 10-20 "3GB 밑이면 즉시 멈춤"


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
         "make": "제작 — 소재·대본·재료 준비 뒤 preset_make 로 시험편 1편(TTS 과금은 허락됨) → --ours-mp4/--ours-lines 로 다시 실행"}


KNOWN_VOICES = [  # 지금까지 쓴 목소리(필재 금지 — 시작 문서 §12). 주인 칸은 판 파일 voice 한 곳(여기는 후보 표만)
    {"name": "미나", "voice_id": "kr-mina-expressive", "engine": "일레븐랩스", "tempo": 1.35, "note": "잇썸홈판·키치잇판·스타픽룸판, 배속 1.35 고정"},
    {"name": "박창수", "voice_id": "tc_6059dad0b83880769a50502f", "engine": "타입캐스트", "tempo": 1.2, "note": "재미썸홈판·꿀템노트판·썰템쇼, 남자면 박창수"},
    {"name": "지훈", "voice_id": "tc_61f0859907085fc68561c9a1", "engine": "타입캐스트", "tempo": 1.25, "note": "샥탬스토리(남, f0 129Hz)"},
]
AXES = ("자막", "틀", "장면전환", "장면대사", "스토리", "대본", "소리", "스티커", "썸네일", "소재", "채널")
_AXIS_KW = {"자막": ("자막", "타이핑", "팝", "글꼴", "강조"), "틀": ("틀", "제목", "로고", "창", "출처"), "장면전환": ("컷", "전환", "줌", "정지"), "장면대사": ("장면", "매칭", "시연"),
            "스토리": ("박자", "훅", "반전", "끝", "결말", "흐름"), "대본": ("어미", "전언", "말투", "대본", "나레는", "반말"), "소리": ("효과음", "BGM", "목소리", "LUFS", "덕킹"),
            "스티커": ("스티커", "짤", "빨간 원", "화살표", "이모지"), "썸네일": ("썸네일", "0초", "첫 프레임"), "소재": ("제품", "소재", "해외 원본"), "채널": ("조회", "업로드", "구독")}


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
            rows.setdefault(v["voice_id"], {"name": v.get("name"), "voice_id": v["voice_id"], "engine": "타입캐스트" if v["voice_id"].startswith("tc_") else "일레븐랩스", "tempo": None, "note": "", "used_in": []})
            rows[v["voice_id"]]["used_in"].append(d.get("name") or f.stem)
        for c in v.get("candidates") or []:
            rows.setdefault(c, {"name": c, "voice_id": c, "engine": "타입캐스트" if c.startswith("tc") else "일레븐랩스", "tempo": None, "note": f"{d.get('name')} 후보(사장님 귀 확인 전)", "used_in": []})
    vp = ROOT / "shopping_shorts/assets/voice_presets.json"
    n_el = len(json.loads(vp.read_text(encoding="utf-8"))) if vp.exists() else 0
    out = list(rows.values())
    out.append({"name": f"(일레븐랩스 프리셋 {n_el}종 더 — shopping_shorts/assets/voice_presets.json)", "voice_id": "", "engine": "일레븐랩스", "tempo": None, "note": "", "used_in": []})
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
    return ("박창수 tc_6059dad0b83880769a50502f" if g == "male" else "미나 kr-mina-expressive") + f" (벤치 화자 {'남' if g == 'male' else '여'} {genders.count(g)}/{len(genders)})"


def menu(axis: str = "all") -> list[dict]:
    """장점 카탈로그 — 주인 channel/스타일.json strengths·options 를 읽어 축별로(새 장부 없음). axis·engine·style_cell 키가 없으면 '미기입'(장부에 채울 일)."""
    d = json.loads((ROOT / "channel/스타일.json").read_text(encoding="utf-8"))
    rows = []
    for st, v in (d.get("styles") or {}).items():
        for x in v.get("strengths") or []:
            txt = json.dumps(x, ensure_ascii=False)
            ax = x.get("axis") or next((a for a, kws in _AXIS_KW.items() if any(k in txt for k in kws)), "미기입")
            rows.append({"axis": ax, "axis_src": "장부" if x.get("axis") else "추정", "kind": f"strength/{st}", "what": x.get("what"), "channel": x.get("channel"),
                         "evidence": x.get("evidence") or x.get("strength"), "source": x.get("source"), "engine": x.get("engine") or "미기입", "style_cell": x.get("style_cell") or "미기입"})
    for name, o in (d.get("options") or {}).items():
        if isinstance(o, dict):
            txt = o.get("desc") or ""
            ax = o.get("axis") or next((a for a, kws in _AXIS_KW.items() if any(k in txt for k in kws)), "미기입")
            rows.append({"axis": ax, "axis_src": "장부" if o.get("axis") else "추정", "kind": f"option/{name}", "what": txt, "channel": o.get("bench") or o.get("source"),
                         "evidence": o.get("why"), "source": o.get("judge"), "engine": o.get("engine") or "미기입", "style_cell": o.get("style_cell") or "미기입"})
    return [r for r in rows if axis == "all" or r["axis"] == axis]


def stage_upgrade(S) -> dict:
    """업그레이드 단계 자리(지침서 §2-6-1) — 1차 판 초안을 복사해 upgrades 빈 칸 + 카탈로그 메뉴. 추천 알고리즘·판 반영은 계획(§7 P1)."""
    kd = S.dir / "_kal"
    kd.mkdir(parents=True, exist_ok=True)
    base = kd / f"{S.d['slug']}판_초안.json"
    plan = json.loads(base.read_text(encoding="utf-8")) if base.exists() else {"name": f"{S.d['slug']}판", "_note": "1차 판 초안 없음 — rules 단계 먼저"}
    up = {"name": f"{S.d['slug']}_업그레이드판", "base": plan.get("name"),   # styles.py 가 base 판을 상속(관제 235 6fcdcef89, 예 styles/연예인레시피판.json) — 바꾼 칸만 아래에 덮어쓴다
          "_rule": "뼈대 칸(placement·script·cuts·timing·caption.typing_cps·variant_for·length·sfx_key)은 1차 값 그대로. 겉모양 칸만 근거 있는 장점으로 — 기록 필수(업그레이드_기록.md)",
          "upgrades": [], "_upgrade_item": {"axis": "", "what": "", "why": "수치·채널·편", "source": "스타일.json strengths/options 키 또는 사고 기록", "expect": "나아질 측정값", "verify": "측정값|사람 판정"},
          "menu": menu("all")}
    (kd / f"{S.d['slug']}_업그레이드판_초안.json").write_text(json.dumps(up, ensure_ascii=False, indent=1), encoding="utf-8")
    rec = kd / "업그레이드_기록.md"
    if not rec.exists():
        rec.write_text(f"# {S.d['slug']} 업그레이드 기록 — 무엇을 → 왜(수치·채널·편) → 예상 효과 → 검증(측정값|사람 판정)\n(근거 없이 바꾸는 것 금지 — 지침서 §2-6-1)\n", encoding="utf-8")
    return {"draft": str(kd / f"{S.d['slug']}_업그레이드판_초안.json"), "record": str(rec), "menu_n": len(up["menu"])}


def _slug_of(ref: str) -> str:
    h = re.sub(r"^https?://(www\.)?youtube\.com/", "", ref.strip()).split("/")[0].lstrip("@")
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "_", h).strip("_").lower() or "channel"


class State:
    def __init__(self, slug: str, ref: str, brand: str | None, n: int, hybrid: str | None, voice: str | None = None):
        self.dir = ROOT / "channel" / slug
        self.path = self.dir / "kal_state.json"
        self.d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"slug": slug, "ref": ref, "steps": {}, "asked": {}}
        self.d.update({k: v for k, v in (("brand", brand), ("n", n), ("hybrid", hybrid), ("voice", voice)) if v is not None})
        self.d.setdefault("n", n)

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
def step_select(S: State):
    u = S.d["ref"].rstrip("/")
    if not u.startswith("http"):
        u = "https://www.youtube.com/" + (u if u.startswith("@") else "@" + u)
    u = u if u.endswith("/shorts") else u + "/shorts"
    r = _run(["yt-dlp", "--encoding", "utf-8", "--flat-playlist", "-J", u], timeout=300)
    if r.returncode != 0 or not r.stdout.strip():
        return "failed", {}, f"yt-dlp flat-playlist 실패: {r.stderr[-300:]}"
    d = json.loads(r.stdout)
    E = sorted([e for e in d.get("entries") or [] if e.get("view_count")], key=lambda e: -e["view_count"])
    if not E:
        return "failed", {}, "조회수 있는 편 0"
    views = [e["view_count"] for e in E]
    med = views[len(views) // 2]
    base = DATA / S.d["slug"]
    base.mkdir(parents=True, exist_ok=True)
    (base / "top.json").write_text(json.dumps([{"id": e["id"], "views": e["view_count"], "title": e.get("title", "")} for e in E[:50]], ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {"name": d.get("channel") or d.get("uploader"), "url": u, "subs": d.get("channel_follower_count"), "total": len(E), "view_median": med,
            "view_max": views[0], "top_ids": [e["id"] for e in E[:S.d["n"]]], "views_per_sub": round(med / d["channel_follower_count"], 2) if d.get("channel_follower_count") else None}
    S.d["channel"] = meta
    # 선정 기준(시작 문서 §9 1단계: 구독 대비 조회·업로드 빈도·결) — 숫자는 적고 판정은 사람
    note = f"{meta['name']} 구독 {meta['subs']} 편 {meta['total']} 조회중앙 {med:,} 최대 {views[0]:,} (구독 대비 중앙 {meta['views_per_sub']})"
    return "done", {"top": str(base / "top.json")}, note


def step_collect(S: State):
    why = disk_gate("받기")
    if why:
        return "failed", {}, why
    base = DATA / S.d["slug"] / "src"
    base.mkdir(parents=True, exist_ok=True)
    ids = S.d["channel"]["top_ids"]
    fmt = YTDLP_LITE if S.d.get("lite") else YTDLP_F
    todo = [i for i in ids if not (base / f"{i}.mp4").exists()]

    def dl(vid):
        r = _run(["yt-dlp", "--encoding", "utf-8", "-f", fmt, "--merge-output-format", "mp4", "--write-info-json", "--write-auto-subs", "--sub-langs", "ko",
                  "-o", str(base / "%(id)s.%(ext)s"), f"https://www.youtube.com/shorts/{vid}"], timeout=900)
        return vid, r.returncode, r.stderr[-200:]
    errs = []
    with ThreadPoolExecutor(2) as ex:        # 무거운 프로세스 동시 ≤4(공통규칙) — 받기는 2
        for vid, rc, err in ex.map(dl, todo):
            if rc != 0:
                errs.append(f"{vid}: {err}")
    have = [i for i in ids if (base / f"{i}.mp4").exists()]
    if len(have) < max(2, len(ids) // 2):
        return "failed", {"have": have}, "받은 편이 절반 미만: " + " | ".join(errs)
    return "done", {"src": str(base), "ids": have}, f"받음 {len(have)}/{len(ids)}({'720p lite' if S.d.get('lite') else '1080p'}, C 여유 {disk_free_gb()}GB)" + (f" 실패 {errs}" if errs else "")


def _claude_llm(parts: list, prompt: str, tag: str = ""):
    """analyze 가 넘기는 제미나이 꼴 parts([라벨 str, jpg bytes, …] 또는 [(경로, 'audio/mp3')]) → claude_cli.ask(그림 bytes 만) 어댑터.
    라벨은 프롬프트 앞에 번호로 접어 넣는다. 소리는 Claude 창구가 못 받으므로 실패로 돌려준다(조용히 건너뛰지 않는다 — 받아쓰기는 vtt·스피치매틱스)."""
    from tools.calcopy.engine import claude_cli
    imgs, labels = [], []
    for x in parts or []:
        if isinstance(x, (bytes, bytearray)):
            imgs.append(bytes(x))
        elif isinstance(x, str):
            labels.append(x)
        elif isinstance(x, tuple):
            return None, f"소리 판독({x[1] if len(x) > 1 else '?'})은 Claude 창구 미지원 — 받아쓰기는 vtt/스피치매틱스"
    head = ("그림 순서(Read 로 연 파일 순서)와 라벨: " + " / ".join(f"{i + 1}={lab}" for i, lab in enumerate(labels)) + "\n") if labels else ""
    return claude_cli.ask(imgs, head + prompt, tag)


def step_tteutgi(S: State):
    from tools.calcopy.engine import analyze
    base = DATA / S.d["slug"] / "src"
    out_root = S.dir / "뜯기"
    done, errs = [], []
    for vid in S.step("collect")["outputs"]["ids"]:
        out = out_root / vid
        if (out / "뜯기.json").exists():
            done.append(vid)
            continue
        try:
            analyze.analyze(str(base / f"{vid}.mp4"), str(out), llm=_claude_llm, materials=False)
            done.append(vid)
        except Exception as e:  # 조용한 실패 금지 — 편별로 기록
            errs.append(f"{vid}: {type(e).__name__} {str(e)[:120]}")
    if not done:
        return "failed", {}, "뜯기 0편: " + " | ".join(errs)
    return "done", {"ids": done, "dir": str(out_root)}, f"뜯기 {len(done)}편" + (f" 실패 {errs}" if errs else "") + " (LLM=claude_cli, 받아쓰기 칸은 vtt 로)"


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
        lst = K.frames_cmd(str(base / "src" / f"{vid}.mp4"), str(od), max(0, y0 - 20), min(1920, y1 + 20), 2, 80)
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
        d = K.skeleton(vid, tt, str(vtt) if vtt.exists() else None)
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


def step_rules(S: State):
    kd = S.dir / "_kal"
    kd.mkdir(parents=True, exist_ok=True)      # --from rules(이미 분석한 채널)에서도 돈다
    docs = K._load_docs([str(S.dir / "줄판독")])
    R = K.rules_of(docs)
    (kd / "규칙빈도_초안.md").write_text(K.rules_md(R, S.d["slug"]), encoding="utf-8")
    (kd / "규칙빈도.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    Sc = K.script_of(docs)
    (kd / "대본언어.md").write_text(K.script_md(Sc), encoding="utf-8")
    (kd / "대본언어.json").write_text(json.dumps(Sc, ensure_ascii=False, indent=1), encoding="utf-8")
    P = K.palette_of(docs)
    (S.dir / "팔레트.json").write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")
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
                       "tempo": next((v["tempo"] for v in KNOWN_VOICES if v["voice_id"] == S.d["voice"]), None), "candidates": [], "why": "사장님이 시작할 때 고름(kal.py --voice)"}
                      if S.d.get("voice") else
                      {"name": None, "voice_id": None, "tempo": None, "candidates": [], "why": "미정 — 사장님께(kal.py 시작 질문, 추천: " + voice_recommend(S) + ")"}),
            "cps_target": round(statistics.median(narr_cps), 2) if narr_cps else None,
            "bgm": {"id": None, "db_below_voice": None, "duck_orig_db": None, "fade_out": None, "why": "engine/sound/bgm_fp.py·뜯기 audio"},
            "loudness": {"lufs": -14, "tp": -1.5},
            "length": {"min": round(min(durs), 1) if durs else None, "max": round(max(durs), 1) if durs else None},
            "script": {"brief": [f"{k}: 어미 " + ", ".join(e["ending"] for e in v["endings"][:4]) + f" · 존댓말 {v['honorific_rate']} · 전언 {v['report_rate']} · 자수 중앙 {v['chars']['med']}" for k, v in Sc.items()],
                       "example": (Sc.get("나레") or {}).get("first_lines", [])[:3], "audit": []},
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
    (kd / f"{S.d['slug']}판_초안.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
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


def step_make(S: State):
    why = disk_gate("렌더")
    if why:
        return "failed", {}, why
    om, ol = S.d.get("ours_mp4"), S.d.get("ours_lines")
    if om and ol and Path(om).exists() and Path(ol).exists():
        return "done", {"ours_mp4": om, "ours_lines": ol}, "시험편 있음"
    return "waiting_human", {}, HUMAN["make"]


def step_verify(S: State):
    o = S.step("make")["outputs"]
    bench = K._load_docs([str(S.dir / "줄판독")])
    ours = json.loads(Path(o["ours_lines"]).read_text(encoding="utf-8"))
    win = K._win_arg(None, bench)
    om = K.media_of(o["ours_mp4"], win)
    bm = K.bench_media_src(str(DATA / S.d["slug"] / "src"), [d.get("id") for d in bench], win)
    T = K.match_table(bench, ours, om, bm)
    T["ours_media"], T["bench_media"] = om, bm
    out = S.dir / "_kal" / "재현일치도.md"
    out.write_text(K.match_md(T, S.d["slug"]), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
    return ("done" if T["verdict"] == "통과" else "waiting_human"), {"table": str(out), "verdict": T["verdict"]}, f"재현일치도 {T['verdict']} — 미달이면 어긋난 항목을 고쳐 make 부터"


def step_apply(S: State):
    from shopping_shorts import calcopy_board as B
    ch = S.d.get("channel") or {}
    B.set_step(S.d["slug"], "2", "done", f"kal.py 분석 {len(S.step('tteutgi')['outputs']['ids'])}편 · 재현일치도 {S.step('verify')['outputs'].get('verdict')}",
               [f"channel/{S.d['slug']}/스타일분석.md", f"channel/{S.d['slug']}/팔레트.json"], name=ch.get("name"), url=ch.get("url"), stats={"subs": ch.get("subs"), "total": ch.get("total")})
    todo = S.dir / "_kal" / "장부_할일.md"
    todo.write_text(f"# 장부 반영 할 일({S.d['slug']}) — 사람이 적는다(공유 json 은 다시 읽고 내 항목만)\n"
                    f"- channel/브랜드.json: 우리 브랜드 '{S.d.get('brand') or '(미정 — 사장님께)'}' ↔ 벤치 {S.d['slug']}\n"
                    f"- channel/스타일.json options/strengths: 스타일분석.md §1 규칙(근거 편·숫자·출처)\n- channel/결과물.json: 시험편 등록(preset_make 가 자동)\n"
                    f"- 하이브리드 {S.d.get('hybrid') or '(미정)'} → 하이브리드_판설계.md\n- 반영은 preset_publish.py(요청 때/02:00)\n", encoding="utf-8")
    return "done", {"todo": str(todo)}, "원장 2단계 done · 장부 할일 적음"


RUN = {"select": step_select, "collect": step_collect, "tteutgi": step_tteutgi, "frames": step_frames, "skeleton": step_skeleton, "readlines": step_readlines,
       "rules": step_rules, "copy": step_copy, "make": step_make, "verify": step_verify, "apply": step_apply}


def run(S: State, start: str | None = None, log=print) -> dict:
    i0 = STEPS.index(start) if start else 0
    for name in STEPS[i0:]:
        st = S.step(name)
        if st.get("state") == "done" and not (start and name == start):
            log(f"[건너뜀] {name}: {st.get('note', '')}")
            continue
        t = time.time()
        try:
            state, outputs, note = RUN[name](S)
        except Exception as e:
            state, outputs, note = "failed", {}, f"{type(e).__name__}: {str(e)[:200]}"
        S.mark(name, state, time.time() - t, outputs, note)
        log(f"[{state}] {name} {S.step(name)['sec']}초 — {note}")
        if state != "done":
            log("\n다음(세션이 할 일): " + (HUMAN.get(name, "원인을 고치고 같은 명령을 다시 실행") if state == "waiting_human" else "실패 원인을 고치고 같은 명령을 다시 실행"))
            log(f"상태 파일: {S.path}")
            break
    return S.d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref", help="채널 주소 또는 @핸들")
    ap.add_argument("--slug"); ap.add_argument("--brand"); ap.add_argument("--n", type=int, default=6); ap.add_argument("--from", dest="start", choices=STEPS)
    ap.add_argument("--hybrid", choices=["예", "아니오"]); ap.add_argument("--voice", help="TTS voice_id(사장님이 고른 것 — 판 파일 voice 한 곳에 적힌다)")
    ap.add_argument("--ours-mp4"); ap.add_argument("--ours-lines")
    ap.add_argument("--menu", help="장점 카탈로그만 보기: 축 이름 또는 all (채널 분석 없이)")
    ap.add_argument("--lite", action="store_true", help="시운전·디스크 부족: 720p 까지만 받기")
    ap.add_argument("--stage", choices=["upgrade"], help="upgrade = 업그레이드 단계 자리(1차 판 초안 복사 + 메뉴 + 기록 파일)")
    A = ap.parse_args(argv)
    slug = A.slug or _slug_of(A.ref)
    if A.menu:
        for r in menu(A.menu):
            print(f"[{r['axis']}({r['axis_src']})] {r['kind']} | {str(r['what'])[:90]} | 출처 {r['channel']} | 엔진 {r['engine']} | 판 칸 {r['style_cell']}")
        return 0
    S = State(slug, A.ref, A.brand, A.n, A.hybrid, A.voice)
    if A.lite:
        S.d["lite"] = True
    print(f"C 여유 {disk_free_gb()}GB (경고 {DISK_WARN_GB} · 거절 {DISK_STOP_GB})")
    if A.ours_mp4:
        S.d["ours_mp4"] = A.ours_mp4
    if A.ours_lines:
        S.d["ours_lines"] = A.ours_lines
    ask = [q for q, v in (("우리 브랜드 이름(--brand)", S.d.get("brand")), ("하이브리드 여부(--hybrid)", S.d.get("hybrid")), ("TTS 누구로(--voice <voice_id>)", S.d.get("voice"))) if not v]
    if ask:
        print("사장님께 시작할 때 한 번에 물을 것(답을 받으면 같은 명령에 옵션으로): " + " · ".join(ask) + " · 과금 단계(TTS)는 허락됨")
        if not S.d.get("voice"):
            print("  쓸 수 있는 목소리(필재 금지) — 추천 1순위: " + voice_recommend(S))
            for v in voice_candidates():
                print(f"   - {v['name']} {v['voice_id']} [{v['engine']}] tempo {v['tempo']} 쓰는 판 {','.join(v['used_in']) or '-'} {v['note']}")
    if A.stage == "upgrade":
        S.save()
        r = stage_upgrade(S)
        print(f"업그레이드 단계 자리: 초안 {r['draft']} · 기록 {r['record']} · 메뉴 {r['menu_n']}건 (추천·판 반영은 계획 — 지침서 §2-6-1)")
        return 0
    S.save()
    run(S, A.start)
    times = {k: v.get("sec") for k, v in S.d["steps"].items()}
    print("단계 시간(초): " + json.dumps(times, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
