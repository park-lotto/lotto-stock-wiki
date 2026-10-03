# -*- coding: utf-8 -*-
"""덧지우기 결과물 검사 (2026-10-03, 관제 095 — 황선희님 817308da1647) — 실제 job 사본으로 끝까지 돌려 **프레임으로** 잰다.

무엇을 재나(전부 결과 파일의 프레임·업체로 보낸 프레임 수 — 계산끼리 비교하지 않는다):
  1단계  3장면 골라 지움                → 그 3장면만 띠(지움), 업체로 간 초 = 고른 초
  2단계  다른 1장면만 골라 다시          → ★앞의 3장면이 지워진 채 유지(원본 복귀 0프레임), 업체로는 새 1장면만
  3단계  이미 지운 장면을 같은 방식으로 다시 → 업체 호출 0, 선택·파일 그대로
  4단계  이미 지운 1장면을 다른 방식으로 다시 → 그 1장면만 업체로, 나머지 유지, 정본에 컷별 등급
  각 단계마다 청소본 파일 + 렌더와 같은 입력으로 조립한 clean_preview.mp4 둘 다 컷별 띠를 잰다.

VMake는 절대 안 부른다: 업체 호출을 '아래 1/4을 검게 칠한 사본'으로 바꾼다(과금 0). 나머지는 실물이다 —
라우트(/api/produce/mix/clean)·동의 관문·큐 인자·run_clean_sources·조립(ffmpeg)·_final_clean_fn·정본.

실행(트랙 폴더):  py shopping_shorts/scripts/clean_topup_e2e.py --job <job_id> [--db shopping_shorts/data/lab.db]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHORTS_CLEAN_FINAL", "1")

ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True)
ap.add_argument("--db", default=str(ROOT / "shopping_shorts" / "data" / "lab.db"))
ap.add_argument("--work-root", default=str(ROOT / "shopping_shorts" / "data" / "mix_jobs"))
ap.add_argument("--first", default="1,2,7", help="1단계에 고를 컷 번호")
ap.add_argument("--more", default="4", help="2단계에 고를 컷 번호(1단계에 없는 것)")
a = ap.parse_args()
sys.argv = [sys.argv[0]]

from shopping_shorts import config as cfg          # noqa: E402
cfg.DB_PATH = a.db
from shopping_shorts import app as A               # noqa: E402
from shopping_shorts import mix_pipeline as mp     # noqa: E402
from shopping_shorts import clean_base as cb       # noqa: E402
from shopping_shorts import store as store_mod     # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

WORK_ROOT = Path(a.work_root)
WORK = WORK_ROOT / a.job
A.DB_PATH = a.db
A._MIX_WORK_DIR = WORK_ROOT
A._need_own_key_or_402 = lambda *x, **k: None
CALLS, FAILS = [], []


def _fake_vmake(src, keys, out, tier=None, **k):
    CALLS.append((mp._probe_fps_frames(src)[2], tier))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                    "-vf", "drawbox=x=0:y=ih*3/4:w=iw:h=ih/4:color=black@1:t=fill",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", str(out)], check=True)
    return str(out)


mp._vmake_clean = _fake_vmake
mp._vmake_keys = lambda s, c=0: ["lab-key"]
mp._charge_clean = lambda s, c, n: 0
QUEUED = []


def _enqueue(self, kind, payload, *x, **k):
    if kind != "clean":
        return 0
    QUEUED.append(dict(payload))
    # 워커(worker.py)와 같은 인자 그대로 — 큐에 실린 것만 넘긴다
    mp.run_clean_sources(payload["job_id"], a.db, str(WORK_ROOT), confirm_clean=payload.get("confirm_clean"),
                         confirm_secs=payload.get("confirm_secs"), pick=payload.get("pick"))
    return 0


store_mod.Store.enqueue = _enqueue


def check(ok, what):
    print(("   ✅ " if ok else "   ❌ ") + what)
    if not ok:
        FAILS.append(what)


def band_profile(path):
    """프레임마다 아래 1/4이 검은가(=지운 띠) → [bool]."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "crop=iw:ih/4:0:ih*3/4,scale=8:2,format=gray",
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return [sum(raw[i:i + 16]) / 16.0 < 24 for i in range(0, len(raw) - 15, 16)]


def cut_ranges(cuts, fps=30.0):
    return [(int(round(float(c["fin"]) * fps)), int(round((float(c["fin"]) + float(c["dur"])) * fps))) for c in cuts]


def band_by_cut(path, cuts):
    """컷마다 띠 있는 프레임 비율(경계 1프레임은 빼고 잰다 — 조립 재인코딩 경계)."""
    prof = band_profile(path)
    out = []
    for s, e in cut_ranges(cuts):
        seg = prof[s + 1:max(s + 2, min(e, len(prof)) - 1)]
        out.append(sum(seg) / max(1, len(seg)))
    return out, len(prof)


def press(client, cuts):
    """화면과 같은 순서: 누름 → 409면 그 초로 확인하고 다시. 반환 (마지막 응답, 확인창이 보여준 안내 또는 None)."""
    body, asked = {"job_id": a.job, "cuts": cuts}, None
    for _ in range(3):
        r = client.post("/api/produce/mix/clean", json=body)
        d = r.json()
        if not (r.status_code == 409 and d.get("need_clean_confirm")):
            return d, asked
        asked = d
        body = dict(body, confirm_clean=True, confirm_secs=d.get("seconds"))
    return d, asked


def expect_bands(label, path, cuts, want_idx):
    ratios, nfr = band_by_cut(path, cuts)
    bad = [(i, round(r, 2)) for i, r in enumerate(ratios) if (r < 0.9) == (i in want_idx) and (i in want_idx or r > 0.1)]
    check(not bad, "%s: 지워진 컷 = %s (어긋난 컷 %s)" % (
        label, sorted(i for i, r in enumerate(ratios) if r >= 0.9), bad or "없음"))
    return nfr


def main():
    store = store_mod.Store(a.db)
    store.set_setting("clean_base_enabled", "1")
    assert WORK.exists(), "job 폴더 없음: %s" % WORK
    for pat in ("final_clean_*", "partial_*", "cb*.mp4", "clean_preview.mp4", cb.BASE_FILE, ".vmake_pending.json"):
        for f in WORK.glob(pat):
            if f.is_file():
                f.unlink()
    job = store.get_mix_job(a.job)
    assert job and job.get("edit_plan"), "편성표 없음"
    plan = job["edit_plan"]
    for b in plan.get("beats") or []:        # 서버 사본의 tts 경로를 이 폴더로(안 바꾸면 TTS를 새로 만들어 컷 길이가 달라진다)
        tp = b.get("tts_path")
        if tp:
            loc = WORK / "tts" / Path(tp).name
            assert loc.exists(), "로컬에 TTS 없음: %s" % loc
            b["tts_path"] = str(loc)
    store.update_mix_job(a.job, edit_plan=plan, subtitle_removal=1, clean_status=None, clean_sources=None,
                         clean_cuts=None, clean_tier="pro", clean_video_path=None)
    client = TestClient(A.app)

    def pick_list():
        d = client.get("/api/produce/mix/clean_pick/" + a.job).json()
        assert d.get("ok") and d.get("partial_ok"), d
        return d

    d0 = pick_list()
    cuts = d0["cuts"]
    first = [int(x) for x in a.first.split(",")]
    more = [int(x) for x in a.more.split(",")]
    key = lambda idx: [cuts[i]["key"] for i in idx]      # noqa: E731
    secs = lambda idx: sum(cuts[i]["dur"] for i in idx)  # noqa: E731
    print("컷 %d개 · 1단계 %s · 2단계 %s" % (len(cuts), first, more))
    check(not any(c["kept"] for c in cuts), "처음엔 지운 장면 표시가 없다")

    print("\n[1단계] %s 고름(고급)" % first)
    d, asked = press(client, key(first))
    job = store.get_mix_job(a.job)
    check(d.get("ok") and job.get("clean_status") == "ready", "청소 완료(status=%s, err=%s)" % (job.get("clean_status"), job.get("clean_error")))
    check(len(CALLS) == 1 and abs(CALLS[0][0] / 30.0 - secs(first)) < 0.2 and CALLS[0][1] == "pro",
          "업체로 간 것 = 고른 %.2f초 1콜 (실제 %s)" % (secs(first), CALLS))
    base1 = cb.load_base(WORK)
    file1 = Path(base1["path"])
    mcuts = base1["cuts"]                      # 그 파일을 만든 지도
    check(base1.get("cut_map") == "assembled" and file1.with_suffix(".cuts.json").exists(), "정본 지도 = 조립 지도, 청소본 옆에 지도 파일")
    n1 = expect_bands("청소본", file1, mcuts, set(first))
    expect_bands("렌더 입력 조립본(clean_preview)", WORK / "clean_preview.mp4", mcuts, set(first))
    keep1 = WORK / "_e2e_step1.mp4"
    keep1.write_bytes(file1.read_bytes())

    print("\n[2단계] %s 만 골라 다시(고급) — 앞의 %s 는 유지돼야 한다" % (more, first))
    d1 = pick_list()
    check([i for i, c in enumerate(d1["cuts"]) if c["kept"]] == sorted(first) and d1.get("topup") is True,
          "화면 목록: 지운 장면 표시 = %s, 덧지우기 가능" % sorted(first))
    d, asked = press(client, key(more))
    job = store.get_mix_job(a.job)
    check(asked is not None and abs(float(asked["seconds"]) - secs(more)) < 0.2 and asked.get("reason") == "topup",
          "확인창 = 새로 지울 %.2f초만 (안내 %s초 · %s)" % (secs(more), asked and asked.get("seconds"), asked and asked.get("message")))
    check(job.get("clean_status") == "ready", "청소 완료(err=%s)" % job.get("clean_error"))
    check(len(CALLS) == 2 and abs(CALLS[1][0] / 30.0 - secs(more)) < 0.2, "업체로 간 것 = 새 %.2f초만 (실제 %s)" % (secs(more), CALLS[1:]))
    check(sorted(mp.clean_selection_of(job) or []) == sorted(key(first + more)), "저장된 선택 = 이미 지운 것 ∪ 고른 것")
    check(QUEUED[-1].get("pick") == key(more), "큐 인자에 이번에 고른 컷이 실렸다")
    base2 = cb.load_base(WORK)
    file2 = Path(base2["path"])
    n2 = expect_bands("★청소본", file2, mcuts, set(first + more))
    expect_bands("★렌더 입력 조립본(clean_preview)", WORK / "clean_preview.mp4", mcuts, set(first + more))
    check(n1 == n2, "프레임 수 불변 %d = %d" % (n1, n2))
    # 앞 청소본과 프레임 대조 — 새로 지운 컷 밖에서 띠가 달라진 프레임이 0이어야 한다(원본 복귀 0)
    p1, p2 = band_profile(keep1), band_profile(file2)
    new_fr = set()
    for i in more:
        s, e = cut_ranges(mcuts)[i]
        new_fr.update(range(s, e))
    moved = [i for i in range(min(len(p1), len(p2))) if p1[i] != p2[i] and i not in new_fr]
    check(not moved, "새로 지운 컷 밖에서 띠가 바뀐 프레임 %d개(0이어야 — 원본 복귀 없음)" % len(moved))

    print("\n[3단계] 이미 지운 %s 를 같은 방식(고급)으로 다시" % first[:1])
    ncall = len(CALLS)
    d, asked = press(client, key(first[:1]))
    job = store.get_mix_job(a.job)
    check(asked is None and len(CALLS) == ncall, "확인창 없음 · 업체 호출 0")
    check(sorted(mp.clean_selection_of(job) or []) == sorted(key(first + more)) and job.get("clean_status") == "ready",
          "선택 그대로 · 완료 상태")
    expect_bands("청소본", cb.load_base(WORK)["path"], mcuts, set(first + more))

    print("\n[4단계] 이미 지운 %s 를 다른 방식(기본)으로 다시" % first[:1])
    store.update_mix_job(a.job, clean_tier="basic")
    d4 = pick_list()
    check(d4["cuts"][first[0]]["done"] == {"basic": False, "pro": True}, "화면 목록: 그 컷은 고급으로만 지워져 있다")
    d, asked = press(client, key(first[:1]))
    job = store.get_mix_job(a.job)
    check(asked is not None and abs(float(asked["seconds"]) - secs(first[:1])) < 0.2, "확인창 = 그 1장면 %.2f초만" % secs(first[:1]))
    check(len(CALLS) == ncall + 1 and CALLS[-1][1] == "basic" and abs(CALLS[-1][0] / 30.0 - secs(first[:1])) < 0.2,
          "업체로 간 것 = 그 1장면만, 기본 등급 (실제 %s)" % (CALLS[ncall:],))
    base4 = cb.load_base(WORK)
    check(job.get("clean_status") == "ready" and (base4.get("cut_tiers") or {}).get(cuts[first[0]]["key"]) == "basic",
          "정본에 컷별 등급 기록(%s)" % json.dumps(base4.get("cut_tiers"), ensure_ascii=False))
    n4 = expect_bands("★청소본", base4["path"], mcuts, set(first + more))
    expect_bands("★렌더 입력 조립본(clean_preview)", WORK / "clean_preview.mp4", mcuts, set(first + more))
    check(n4 == n1, "프레임 수 불변 %d = %d" % (n1, n4))
    d5 = pick_list()
    check(d5["cuts"][first[0]]["done"] == {"basic": True, "pro": False}
          and [i for i, c in enumerate(d5["cuts"]) if c["kept"]] == sorted(first + more), "화면 목록이 덧지운 결과를 그대로 보여준다")

    print("\n업체 호출 전체: %s" % CALLS)
    print("결과: %s" % ("FAIL %d건 — %s" % (len(FAILS), FAILS) if FAILS else "PASS"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
