# -*- coding: utf-8 -*-
"""소재창고 워커의 단계 → 엔진 잇기 (관제 097, 2026-10-16). 설계: docs/superpowers/specs/2026-10-16-소재창고-보드-워커-design.md

판단 주인: 어떤 단계를 어떤 엔진 함수로 돌리나 = STEPS 한 표. 다음 일감·상태 전이·검수 자리·비용 상한은 **서버 API** 가 정한다
(이 파일은 판단하지 않는다). 단계 함수는 실패를 **예외로** 올린다 — 조용히 통과하지 않는다.
  StepError(이유, artifacts)   엔진이 돌았지만 결과가 기준 미달(대본 검사 미통과·벤치 0편 등). 산출물은 같이 보고한다.
  NotImplementedError          엔진 모듈이 아직 없다(다른 담당이 만드는 중) — 워커가 이유로 적고 멈춘다.

단계 함수 모양(서버 규격 docs/superpowers/specs/2026-10-16-소재창고-api.md §1·§4 advance):
  fn(topic, ctx) -> {"artifacts": {파일이름: 로컬경로}, "outputs": {이름표: 파일이름}, "cost": {"gemini": n, "typecast": n},
                     "data": {source|bench|score|assign|rights: {...}}}       (find 만 "rows": [{name, source}] 를 준다)
  step 마다 서버가 요구하는 것: bench=data.bench · score=data.score.criteria 5기준 · assign=data.assign.channel·preset ·
  script=outputs.script · source=data.rights · plan=outputs.plan · produce=outputs.final · check=outputs.verdict
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REMAKE = ROOT / "tools" / "calcopy" / "engine" / "remake.py"


class StepError(Exception):
    """엔진이 돌았지만 결과가 기준 미달 — 이유와 그때까지의 산출물을 함께 올린다."""

    def __init__(self, reason: str, artifacts: dict | None = None, cost: dict | None = None):
        super().__init__(reason)
        self.reason, self.artifacts, self.cost = reason, artifacts or {}, cost or {}


def _run(cmd: list[str], timeout: int) -> tuple[int, str]:
    env = {**os.environ, "PYTHONUTF8": "1"}
    p = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=timeout, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or ""))[-1500:]


@dataclass
class Ctx:
    out_root: Path
    channel: str
    category: str
    track: str
    preset: str | None = None          # 없으면 topic.assign.preset → channel slug
    llm_budget: int = 6                # 무료 제미나이 한 단계 상한(topic_find.LLM)
    find_n: int = 5
    run: Callable[[list[str], int], tuple[int, str]] = _run
    log: Callable[[str], None] = print
    extra: dict = field(default_factory=dict)
    worker: str = ""                   # 장부(worker_ledger) 한도 — 비면 장부를 안 쓴다(시험)

    def workdir(self, topic: dict) -> Path:
        d = Path(self.out_root) / str(topic["id"])
        d.mkdir(parents=True, exist_ok=True)
        return d

    def preset_of(self, topic: dict | None) -> str:
        return ((topic or {}).get("assign") or {}).get("preset") or self.preset or self.channel


def _net(TF, ctx: Ctx) -> dict:
    """유튜브 통로를 장부 한도(4워커 합 시간당 300편) 뒤에 둔다 — 조회 전에 take, 넘으면 LimitHit(이유)."""
    if not ctx.worker:
        return TF.NET
    from tools.calcopy.engine import worker_ledger as L
    net = dict(TF.NET)

    def search(q, n=10, months=None, _f=TF.NET["yt_search"]):
        L.take(ctx.worker, "yt", int(n), f"검색 {q}")          # 요청 편수만큼 먼저 잡고(한도 보호)
        res = _f(q, n, months)
        got = len([x for x in res or [] if x.get("id")])
        if got < int(n):                                       # 실제로 온 편수만 남긴다(10-16 실측: 0~4편 오는 검색이 10편씩 먹어 한도 300 이 몇 분에 찼다)
            L.add(ctx.worker, "yt", got - int(n), f"검색 {q} 반환 — 실제 {got}편")
        return res

    def detail(vid, *a, _f=TF.NET["yt_detail"], **k):
        L.take(ctx.worker, "yt", 1, f"상세 {vid}")
        return _f(vid, *a, **k)
    net["yt_search"], net["yt_detail"] = search, detail
    for k, f in TF.NET.items():                     # 그 밖 유튜브 통로(날짜·메타…)는 1편씩
        if k.startswith("yt_") and k not in ("yt_search", "yt_detail"):
            def one(*a, _f=f, _k=k, **kw):
                L.take(ctx.worker, "yt", 1, f"{_k} {a[0] if a else ''}")
                return _f(*a, **kw)
            net[k] = one
    return net


def _llm(TF, ctx: Ctx):
    """무료 제미나이 창구를 장부 한도(워커당 시간당 40회) 뒤에 둔다. 429·쿼터면 장부에 pause(30분 쉼)."""
    if not ctx.worker:
        return TF.LLM(budget=ctx.llm_budget)
    from tools.calcopy.engine import worker_ledger as L

    class Guarded(TF.LLM):
        def __call__(self, prompt, tag):
            if len(self.calls) < self.budget:
                L.take(ctx.worker, "gemini", 1, tag)
            d, err = super().__call__(prompt, tag)
            if err and any(x in str(err) for x in ("429", "RESOURCE_EXHAUSTED", "quota", "쿼터")):
                L.add(ctx.worker, "pause", 1, f"제미나이 {str(err)[:150]}")
            return d, err
    return Guarded(budget=ctx.llm_budget)


def _engine(name: str):
    """엔진 모듈 불러오기 — 없으면 NotImplementedError(이유 원문). 다른 담당이 만드는 중인 모듈이 여기서 걸린다."""
    try:
        return importlib.import_module(f"tools.calcopy.engine.{name}")
    except ImportError as e:
        raise NotImplementedError(f"엔진 없음: tools/calcopy/engine/{name}.py ({type(e).__name__}: {e})") from e


def _preset(TF, ctx: Ctx, topic: dict | None) -> dict:
    try:
        return TF.load_preset(ctx.preset_of(topic))
    except SystemExit as e:          # load_preset 은 못 찾으면 SystemExit — 워커를 죽이지 말고 이유로
        raise StepError(f"프리셋: {e}") from None


def _cid(topic: dict) -> str:
    """엔진 후보 id — topic_find 프롬프트 예시가 'c1' 꼴이라 숫자만 주면 모델이 'c1' 로 바꿔 답한다(10-16 실측: 점수 '응답에 이 후보 없음')."""
    return f"c{topic['id']}"


def _cand(topic: dict) -> dict:
    src = topic.get("source") or {}
    return {"id": _cid(topic), "topic": topic.get("name") or "", "query": src.get("query") or topic.get("name") or "",
            "key": src.get("key") or src.get("query") or "", "source": src}


def _llm_n(llm) -> int:
    """실제로 나간 호출 수(상한에 막혀 안 나간 'budget' 은 빼고) — 서버 하루 장부 gemini 로 보고."""
    return sum(1 for c in llm.calls if c.get("failed") != "budget")


def _exists(d: dict) -> dict:
    return {k: str(v) for k, v in d.items() if v and Path(v).exists()}


# ── 단계 ──────────────────────────────────────────────────────────────────
def step_find(topic, ctx: Ctx) -> dict:
    """소재 후보 모으기 → 새 행. 검색어 만들기·통로는 topic_find.run 앞부분과 **같은 함수**를 같은 순서로 부른다
    (해외영상+검색어 없음 = db_candidates, 그 밖 = target_queries+gather). ★엔진에 find_candidates() 가 생기면 그걸 부르고 이 순서는 지운다."""
    TF = _engine("topic_find")
    if hasattr(TF, "find_candidates"):
        r = TF.find_candidates(ctx.preset_of(None), ctx.find_n, keywords=ctx.extra.get("keywords"), net=_net(TF, ctx), llm=_llm(TF, ctx), log=ctx.log)
        cands, failed = r["candidates"], r["failed"]
    else:
        P = _preset(TF, ctx, None)
        kind = (P["manifest"] or {}).get("source_kind") or ctx.extra.get("source_kind")
        if kind not in TF.SOURCE_KINDS:
            raise StepError(f"소재 출처 유형 없음/모름: {kind!r} (manifest.source_kind 또는 --source-kind)")
        top = TF._read_json(P["chdir"] / "원자료" / "top50.json") or []
        limits, kws_in = TF.Limits(), ctx.extra.get("keywords")
        try:
            if kind == "해외영상" and not kws_in and hasattr(TF, "db_candidates"):
                cands, failed, queries = TF.db_candidates(_net(TF, ctx), _llm(TF, ctx), ctx.find_n, ctx.log, limits=limits)
            else:
                if not kws_in:
                    raise StepError(f"'{kind}' 은 검색어(구체 명사)가 필요 — warehouse_channels.json keywords (엔진: 우리 과거 제목에서 뽑지 않는다)")
                R = TF._read_json(Path(P["rules"])) if P.get("rules") else {}
                angles = tuple((R or {}).get("topic_angles") or getattr(TF, "DEFAULT_ANGLES", ()))
                tq = TF.target_queries(kind, kws_in, limits.max_queries, angles) if angles else TF.target_queries(kind, kws_in, limits.max_queries)
                kws = [q["q"] for q in tq]
                ctx.log(f"[검색어] {kws}")
                cands, failed = TF.gather(kind, kws, ctx.find_n, ctx.extra.get("months", 6), {v["id"] for v in top}, _net(TF, ctx), ctx.log,
                                          limits, brands=list(kws_in))
        except StepError:
            raise
        except Exception as e:  # noqa: BLE001 — 장부 한도(LimitHit)·엔진 오류는 이유로
            raise StepError(f"찾기 멈춤: {type(e).__name__}: {e}") from None
        if limits.stopped:
            failed.append({"where": "limits", "why": limits.stopped})
    if not cands:
        raise StepError("후보 0 — " + "; ".join(f"{f.get('where')}: {f.get('why')}" for f in failed)[:300])
    rows = [{"name": c["topic"], "source": {**c["source"], "via": c["source"].get("kind"), "query": c["query"], "key": c.get("key", ""),
                                            "found_at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00")}} for c in cands]
    return {"rows": rows, "failed": failed}


def step_bench(topic, ctx: Ctx) -> dict:
    TF = _engine("topic_find")
    wd = ctx.workdir(topic)
    llm = _llm(TF, ctx)
    b = TF.bench(_cand(topic), wd, _net(TF, ctx), llm, ctx.extra.get("bench_n", 4), limits=TF.Limits())
    arts = _exists({"벤치.md": wd / "벤치" / f"{_cid(topic)}.md", "벤치.json": wd / "벤치" / f"{_cid(topic)}.json"})
    cost = {"gemini": _llm_n(llm)}
    if not b["points"]:
        raise StepError("벤치 포인트 0 — " + "; ".join(b["failed"])[:300], arts, cost)
    return {"artifacts": arts, "cost": cost, "outputs": {"bench": "벤치.md"},
            "data": {"bench": {"n_videos": len(b["videos"]), "points": b["points"], "best_angle": b["best_angle"], "failed": b["failed"]}}}


def step_score(topic, ctx: Ctx) -> dict:
    TF = _engine("topic_find")
    P = _preset(TF, ctx, topic)
    llm = _llm(TF, ctx)
    c = _cand(topic)
    rows, err = TF.score([c], {c["id"]: topic.get("bench") or {}}, P["slug"], llm)
    cost = {"gemini": _llm_n(llm)}
    if not err and c["id"] not in rows and len(rows) == 1:   # 후보 1개만 보냈다 — 답 id 를 바꿔 적어도 그 한 줄이 이 후보
        rows = {c["id"]: next(iter(rows.values()))}
    if err or c["id"] not in rows:
        raise StepError(f"점수 LLM 실패: {err or '응답에 이 후보 없음'}", cost=cost)
    cs = TF._clean_scores(rows[c["id"]])           # 근거 없는 점수는 None — 서버에 숫자로 속여 넣지 않는다
    ov = TF.overlap(c["topic"], TF.made_corpus(P["chdir"]))
    names = dict(TF.CRITERIA)
    crit = {names[k]: v for k, v in cs["scores"].items() if v["score"] is not None}
    if len(crit) < 5:
        raise StepError(f"근거 있는 점수 {len(crit)}개 < 5 — {cs['flags']}", cost=cost)
    return {"cost": cost, "data": {"score": {"criteria": crit, "total": TF.total(cs["scores"], ov), "overlap": ov["score"],
                                             "overlap_with": ov.get("with"), "flags": cs["flags"], "angle": rows[c["id"]].get("angle") or ""}}}


def step_assign(topic, ctx: Ctx) -> dict:
    """이 워커의 채널 프리셋을 붙인다. 어떤 행이 배정 대상인지는 서버가 거른다(이 함수는 고르지 않는다)."""
    return {"data": {"assign": {"channel": ctx.channel, "preset": ctx.preset or ctx.channel}}}


def step_script(topic, ctx: Ctx) -> dict:
    SE = _engine("script_engine")
    TF = _engine("topic_find")
    wd = ctx.workdir(topic) / "대본"
    bench_md = ctx.workdir(topic) / "벤치" / f"{_cid(topic)}.md"
    llm = _llm(TF, ctx)
    wd.mkdir(parents=True, exist_ok=True)
    tj = wd / "소재.json"     # script_engine.load_topic 이 읽는 꼴({topic,…}) — 5기준·각도가 대본_계획.md 에 실린다
    sc = topic.get("score") or {}
    eng = {name: k for k, name in TF.CRITERIA}     # 서버엔 한국어 기준 이름(criteria) — 엔진 소재.json 은 영문 키 {score, why}
    tj.write_text(json.dumps({"id": topic["id"], "topic": topic.get("name") or "", "angle": sc.get("angle") or "",
                              "scores": {eng[n]: v for n, v in (sc.get("criteria") or {}).items() if n in eng},
                              "overlap": {"score": sc.get("overlap"), "with": sc.get("overlap_with")}, "total": sc.get("total"),
                              "source": topic.get("source") or {}},
                             ensure_ascii=False, indent=1), encoding="utf-8")
    S = SE.run(ctx.preset_of(topic), str(tj), wd, str(bench_md) if bench_md.exists() else None, ctx.extra.get("facts_path"), llm=llm, log=ctx.log)
    arts = _exists({"대본.json": wd / "대본.json", "대본_검사.md": wd / "대본_검사.md", "대본_계획.md": wd / "대본_계획.md"})
    cost = {"gemini": _llm_n(llm)}
    chk = (S.get("final") or {}).get("check") or {}
    if not chk.get("ok"):
        raise StepError("대본 검사 미통과: " + json.dumps(chk, ensure_ascii=False)[:300], arts, cost)
    return {"artifacts": arts, "cost": cost, "outputs": {"script": "대본.json"}}


def _remake_args(TF, ctx: Ctx, topic: dict) -> tuple[list[str], Path]:
    P = _preset(TF, ctx, topic)
    if not P.get("tteutgi") or not P.get("frame"):
        raise StepError(f"프리셋에 뜯기/틀 없음: tteutgi={P.get('tteutgi')} frame={P.get('frame')}")
    out = ctx.workdir(topic) / "제작"
    return [sys.executable, str(REMAKE), str(P["tteutgi"]), str(P["frame"]), "--out", str(out)], out


def step_source(topic, ctx: Ctx) -> dict:
    """remake.py 후보 모드 — 재료 후보 시트 + 재료_뼈대.json 까지(고르기는 사람/오푸스 자리)."""
    TF = _engine("topic_find")
    _engine("remake")
    cmd, out = _remake_args(TF, ctx, topic)
    q = (topic.get("source") or {}).get("query") or topic.get("name") or ""
    if ctx.worker:                                     # remake 후보 모드는 검색 1번에 쇼츠 최대 12편을 받는다(remake.search_shorts n=12)
        from tools.calcopy.engine import worker_ledger as L
        L.take(ctx.worker, "yt", 12, f"재료 후보 {q}")
    rc, tail = ctx.run(cmd + ["--queries", q], 1800)
    arts = _exists({"재료_뼈대.json": out / "재료_뼈대.json"})
    cand = out / "재료후보"
    sheets = sorted(cand.glob("*.jpg")) if cand.is_dir() else []
    if sheets:
        arts["재료후보_시트.jpg"] = str(sheets[0])
    if rc != 2 or "재료_뼈대.json" not in arts:
        raise StepError(f"재료 후보 모드 rc={rc}(기대 2) — {tail[-300:]}", arts)
    hook = ctx.extra.get("materials_hook")      # 만들기 입구: 뼈대 → 재료 자동 초안(팩 기본값 주입은 calcopy_make.draft_materials 한 곳)
    if hook and not (out / "재료.json").exists():
        M = hook(json.loads((out / "재료_뼈대.json").read_text(encoding="utf-8")))
        (out / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
        arts["재료.json"] = str(out / "재료.json")
    vids = sorted(cand.glob("v_*.mp4")) + sorted(out.glob("v_*.mp4"))
    rights = {v.name: "유튜브 쇼츠(재료 후보·참고, 사용 전 사람 확인)" for v in vids}
    if not rights:
        raise StepError("재료 후보 영상 0개 — 출처(rights)를 적을 재료가 없다", arts)
    return {"artifacts": arts, "data": {"rights": rights}, "outputs": {"materials_skeleton": "재료_뼈대.json"}}


def step_plan(topic, ctx: Ctx) -> dict:
    """remake.py --plan-only → 계획.md·계획_시트.jpg (선검수 자료)."""
    TF = _engine("topic_find")
    _engine("remake")
    cmd, out = _remake_args(TF, ctx, topic)
    mats, script = out / "재료.json", ctx.workdir(topic) / "대본" / "대본.json"
    if not mats.exists():
        raise StepError(f"재료.json 없음 — 재료_뼈대.json 을 채워 {mats} 로 두어야 한다(재료 고르기는 사람/오푸스 자리)")
    if not script.exists():
        raise StepError(f"대본.json 없음: {script}")
    rc, tail = ctx.run(cmd + ["--materials", str(mats), "--script", str(script), "--plan-only"], 1800)
    arts = _exists({"계획.md": out / "계획.md", "계획_시트.jpg": out / "계획_시트.jpg"})
    if rc != 3 or "계획.md" not in arts:
        raise StepError(f"계획 rc={rc}(기대 3) — {tail[-300:]}", arts)
    outs = {"plan": "계획.md"}
    if "계획_시트.jpg" in arts:
        outs["plan_sheet"] = "계획_시트.jpg"
    return {"artifacts": arts, "outputs": outs}


def step_produce(topic, ctx: Ctx) -> dict:
    """remake.py 전체 → final.mp4 + 대조 + 1초 시트. 나레 꼴이면 타입캐스트 1회(비용 상한은 서버가 claim 때 막는다)."""
    TF = _engine("topic_find")
    _engine("remake")
    cmd, out = _remake_args(TF, ctx, topic)
    mats, script = out / "재료.json", ctx.workdir(topic) / "대본" / "대본.json"
    tts = out / "narr_full.mp3"
    had_tts = tts.exists()
    t0 = time.time()
    extra = ["--tts", str(tts)] if had_tts else ["--make-tts"]
    ra = ctx.extra.get("remake_args") or {}                  # 내 팩 키트(목소리·빠르기·자막 꼴·BGM) — calcopy_make.merge_preset_pack 이 정한 값
    for k, flag in (("voice", "--voice"), ("tempo", "--tempo"), ("caption_mode", "--caption-mode"), ("bgm", "--bgm"), ("bgm_ratio", "--bgm-ratio")):
        if ra.get(k) is not None:
            extra += [flag, str(ra[k])]
    rc, tail = ctx.run(cmd + ["--materials", str(mats), "--script", str(script)] + extra, 3600)
    cost = {"typecast": int(tts.exists() and not had_tts)}
    ctx.log(f"[제작] {round(time.time() - t0)}초 rc={rc}")
    arts = _produce_arts(out)
    if rc not in (0, 1) or "final.mp4" not in arts:      # 1 = 대조 '밖' 판정(만들기는 됨) — 판정은 check·사람
        raise StepError(f"제작 rc={rc} — {tail[-300:]}", arts, cost)
    return {"artifacts": arts, "cost": cost, "outputs": _produce_outputs(arts)}


def _produce_arts(out: Path) -> dict:
    return _exists({"final.mp4": out / "final.mp4", "final_sheet_1s.jpg": out / "final_sheet_1s.jpg", "차이표.md": out / "대조" / "차이표.md",
                    "side_by_side.jpg": out / "대조" / "side_by_side.jpg", "remake_log.json": out / "remake_log.json"})


def _produce_outputs(arts: dict) -> dict:
    lab = {"final.mp4": "final", "final_sheet_1s.jpg": "sheet_1s", "차이표.md": "diff", "side_by_side.jpg": "side_by_side"}
    return {lab[k]: k for k in arts if k in lab}


def step_check(topic, ctx: Ctx) -> dict:
    """제작이 남긴 대조 결과를 모아 최종 검수 자료로 올린다(판정은 사람)."""
    TF = _engine("topic_find")
    _engine("compare")
    cmd, out = _remake_args(TF, ctx, topic)
    arts = _produce_arts(out)
    need = [k for k in ("final_sheet_1s.jpg", "차이표.md", "side_by_side.jpg") if k not in arts]
    vj = out / "대조" / "verdict.json"
    if need or not vj.exists():
        raise StepError(f"대조 산출물 없음: {need + ([] if vj.exists() else ['대조/verdict.json'])}", arts)
    arts = {k: v for k, v in arts.items() if k != "final.mp4"}        # 완성본은 produce 때 이미 올렸다
    arts["verdict.json"] = str(vj)
    outs = {**_produce_outputs(arts), "verdict": "verdict.json"}
    J = json.loads(Path(cmd[2]).read_text(encoding="utf-8"))
    if J.get("source") and Path(J["source"]).exists():
        arts["original" + Path(J["source"]).suffix] = str(J["source"])
        outs["original"] = "original" + Path(J["source"]).suffix
    return {"artifacts": arts, "outputs": outs}


STEPS: dict[str, Callable[[dict, Ctx], dict]] = {
    "find": step_find, "bench": step_bench, "score": step_score, "assign": step_assign, "script": step_script,
    "source": step_source, "plan": step_plan, "produce": step_produce, "check": step_check,
}


def run_step(step: str, topic: dict | None, ctx: Ctx) -> dict:
    fn = STEPS.get(step)
    if fn is None:
        raise StepError(f"워커가 할 수 없는 단계: {step!r} (할 수 있는 것 {sorted(STEPS)})")
    try:
        return fn(topic, ctx)
    except SystemExit as e:      # 엔진 CLI 함수들이 입력 오류를 SystemExit 로 올린다 — 워커를 죽이지 말고 이유로
        raise StepError(f"{step}: 엔진이 멈춤(SystemExit {e})") from None
