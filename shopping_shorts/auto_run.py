"""원클릭 오케스트레이터 러너 — S1→S2→S3를 자동 관통(스펙 §3·§4·§5, 트랙4).

DI 구조: 단계 어댑터·심사기·알림기를 주입받아 실 엔진 없이 단위테스트한다.
기본 심사기는 무조건 pass(트랙5가 기계 게이트로 교체). 화면 없음 — produce.html 무접촉.
"""
import uuid
from dataclasses import dataclass, field

from shopping_shorts import service, script_generate, mix_pipeline

STAGE_ORDER = ["S1", "S2", "S3"]

# 비용 상수(원, 추정 — 실측 캘리브레이션 대상). 근거:
#  APIFY: 인스타 수집 회당 약 $0.755(스펙 결정4) × 환율 ≈ 1010원
#  GEMINI/TTS: 초안 N개 + eleven_v3 나레이션. 실측 전 보수적 추정.
APIFY_COST_KRW = 1010
GEMINI_COST_KRW = 50
TTS_COST_KRW = 200


@dataclass
class StageResult:
    output_ref: str = ""
    metrics: dict = field(default_factory=dict)   # 'cost_krw' 포함(없으면 0)
    candidates: list = field(default_factory=list)


@dataclass
class Verdict:
    decision: str                                  # 'pass' | 'unsure' | 'fail'
    reasons: list = field(default_factory=list)


def default_judge(stage_name, result, ctx):
    """트랙5(기계 게이트)가 교체할 자리. 지금은 무조건 통과."""
    return Verdict("pass")


def _to_dict(result):
    return {"output_ref": result.output_ref, "metrics": result.metrics,
            "candidates": result.candidates}


def _halt(store, job_id, stage_name, reason, notifier, results, cost):
    store.update_auto_job(job_id, status="waiting_human", current_stage=stage_name,
                          unsure_reason=reason, stage_results=results, cost_krw=cost)
    if notifier:
        try:
            notifier(f"[러너] {stage_name} 확인 필요: {reason}")
        except Exception:
            pass                                   # 알림 실패가 러너를 죽이면 안 된다
    return store.get_auto_job(job_id)


def run_auto_job(job_id, store, *, stages, judge=default_judge, notifier=None,
                 cost_cap_krw=1000, max_retries=2):
    job = store.get_auto_job(job_id)
    results = dict(job.get("stage_results") or {})
    cost = job.get("cost_krw") or 0

    # 재개: current_stage가 이미 있으면 그 다음 단계부터
    done_stage = job.get("current_stage")
    start = STAGE_ORDER.index(done_stage) + 1 if done_stage in STAGE_ORDER else 0

    for stage_name in STAGE_ORDER[start:]:
        ctx = {"job_id": job_id, "store": store, "results": results,
               "job": store.get_auto_job(job_id)}
        store.update_auto_job(job_id, status="running", current_stage=stage_name)

        verdict = None
        for _attempt in range(max_retries + 1):
            result = stages[stage_name](ctx)
            cost += (result.metrics or {}).get("cost_krw", 0) or 0
            results[stage_name] = _to_dict(result)
            store.update_auto_job(job_id, cost_krw=cost, stage_results=results)

            if cost > cost_cap_krw:
                return _halt(store, job_id, stage_name, "cost_cap", notifier, results, cost)

            verdict = judge(stage_name, result, ctx)
            if verdict.decision == "pass":
                break
            if verdict.decision == "unsure":
                return _halt(store, job_id, stage_name,
                             "; ".join(verdict.reasons) or "unsure", notifier, results, cost)
            # fail → 재시도 루프 계속
        else:
            # 재시도 소진 → unsure로 승격
            return _halt(store, job_id, stage_name,
                         "재시도 소진: " + ("; ".join(verdict.reasons) if verdict else ""),
                         notifier, results, cost)

    store.update_auto_job(job_id, status="done", current_stage=STAGE_ORDER[-1],
                          stage_results=results, cost_krw=cost)
    return store.get_auto_job(job_id)


def default_stages(db_path, work_root, *, platform="instagram", target_seconds=20):
    """실 엔진을 감싼 기본 단계 어댑터(트랙4 Task4). 엔진은 호출만 한다.

    ⚠️ S1 pick → S2 입력(structure/full_text) 완전 배선·비용 상수는 라이브 grounding에서
    관측·보정한다. 여기선 올바른 엔진을 올바른 인자로 부르는 것까지 잠근다.
    """
    def s1_rank(ctx):
        items = service.collect(platform)
        if not items:
            return StageResult(output_ref="", metrics={"cost_krw": APIFY_COST_KRW, "empty": True})
        pick = max(items, key=lambda i: i.get("score") or 0)
        top5 = sorted(items, key=lambda i: i.get("score") or 0, reverse=True)[:5]
        return StageResult(output_ref=pick.get("shortcode", ""),
                           metrics={"pick": pick, "score": pick.get("score"),
                                    "cost_krw": APIFY_COST_KRW},
                           candidates=[{"shortcode": i.get("shortcode"),
                                        "score": i.get("score")} for i in top5])

    def s2_script(ctx):
        pick = (ctx["results"].get("S1", {}).get("metrics", {}) or {}).get("pick", {}) or {}
        drafts = script_generate.generate_variations(
            pick.get("structure") or {}, pick.get("full_text") or "",
            {}, {}, mode="remake", my_topic="", subject="", n=3)
        if not drafts:
            return StageResult(output_ref="", metrics={"cost_krw": GEMINI_COST_KRW, "empty": True})
        first = drafts[0]
        return StageResult(output_ref=first.get("script", ""),
                           metrics={"hook": first.get("hook"), "cost_krw": GEMINI_COST_KRW},
                           candidates=drafts)

    def s3_mix(ctx):
        script = ctx["results"].get("S2", {}).get("output_ref", "") or ""
        pick = (ctx["results"].get("S1", {}).get("metrics", {}) or {}).get("pick", {}) or {}
        urls = [pick.get("video_url")] if pick.get("video_url") else []
        store = ctx["store"]
        mix_id = uuid.uuid4().hex[:12]
        store.create_mix_job(mix_id, urls, target_seconds, "free", given_script=script)
        mix_pipeline.run_mix_job(mix_id, str(db_path), str(work_root))
        mix_pipeline.run_render(mix_id, str(db_path), str(work_root))
        job = store.get_mix_job(mix_id) or {}
        store.update_auto_job(ctx["job_id"], mix_job_id=mix_id)
        return StageResult(output_ref=job.get("video_path") or "",
                           metrics={"mix_job_id": mix_id, "status": job.get("status"),
                                    "cost_krw": TTS_COST_KRW})

    return {"S1": s1_rank, "S2": s2_script, "S3": s3_mix}
