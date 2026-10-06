# -*- coding: utf-8 -*-
"""감정짤 결과물 검사(관제 139) — job 하나의 '짤 컷'이 규칙대로 계획됐나.

쓰는 법(서버, 운영 DB 읽기 전용 — 편성표를 고치지 않는다):
    python3 tools/scene_cover/meme_check.py <job_id> [--json]
잰다(짤이 붙은 칸마다):
  ① 계획 첫 컷이 짤인가(video_id == cutaway.vid, 시작 0초)
  ② 짤 컷 길이 vs head_sec, 그리고 그 줄 음성에서 신호어를 다 말한 초(TTS 정밀 시각)와의 차
     (신호어 끝이 1.0~2.0초 밖이면 자른 값과 비교 — 기대값 = clamp(신호어 끝 − head_trim, 1.0, 2.0))
  ③ 짤 뒤 장면 컷 중 1.0초 미만 수
  ④ 신호어 [1]·[3] 줄인데 짤이 없는 칸(이유는 서버 로그 [meme] 줄에 있다)
컷 목록 = 편집 화면 계산(scene_play.js planClips)을 서버 러너로 돌린 값(screen_clips.warm — 렌더·캡컷·ZIP 이 받는 그 컷).
⚠️ 계획 검사다 — 완성본 프레임 대조는 렌더 뒤 tools/editor_vs_final_video.py 로 따로 한다.
"""
import json
from pathlib import Path
import os
import sys

ROOT = os.environ.get("SS_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
DB = os.environ.get("SS_DB") or os.path.join(ROOT, "shopping_shorts", "data", "reference.db")

from shopping_shorts import screen_clips, storyboard, tts_timestamps   # noqa: E402
from shopping_shorts.store import Store                                # noqa: E402

TOL = 0.035      # 한 프레임(1/30초) + 반올림


def check(job_id):
    job = Store(DB).get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return {"job": job_id, "error": "job/편성 없음"}
    beats = job["edit_plan"].get("beats") or []
    n = screen_clips.warm(job)          # 화면 컷 계산(메모리 캐시) — DB 에 쓰지 않는다
    rows, bad = [], 0
    for b in beats:
        cw = b.get("cutaway") or {}
        rank = b.get("sig_rank")
        is_meme = cw.get("match_type") == "meme" and cw.get("head_sec")
        if not is_meme:
            if rank in storyboard.MEME_RANKS:
                rows.append({"beat": b.get("beat_idx"), "rank": rank, "meme": False, "note": "신호어 [%s] 줄인데 짤 없음" % rank})
            continue
        r = {"beat": b.get("beat_idx"), "rank": rank, "meme": True, "emotion": cw.get("emotion"),
             "head_sec": float(cw["head_sec"]), "problems": []}
        k = screen_clips.beat_key(b)
        cuts = ((screen_clips._CACHE.get(k) or {}).get("c")) if k else None
        if not cuts:
            r["problems"].append("화면 컷 없음(warm %d칸)" % n)
        else:
            c0 = cuts[0]
            r["first"] = {"v": c0.get("v"), "s": c0.get("s"), "d": c0.get("d")}
            if c0.get("v") != cw.get("vid") or abs(float(c0.get("s") or 0)) > 1e-3:
                r["problems"].append("첫 컷이 짤 아님")
            elif abs(float(c0["d"]) - r["head_sec"]) > TOL:
                r["problems"].append("짤 길이 %.3f ≠ head_sec %.3f" % (float(c0["d"]), r["head_sec"]))
            short = [round(float(c["d"]), 2) for c in cuts[1:] if float(c.get("d") or 0) < storyboard.MEME_SCENE_MIN - 1e-3]
            r["scenes"] = len(cuts) - 1
            r["short_scenes"] = short
            if short:
                r["problems"].append("1.0초 미만 장면 %d개" % len(short))
        # ★배치(mix_pipeline._apply_memes)와 같은 시각 — 실제 음성 길이에 맞춘 낱말 시각(_beat_words_src). 원시 사이드카(words_from_mp3)로
        #   재면 늘린·뺀 음성과 어긋나 1.20초 짤을 1.44초가 기대값이라고 오판했다(10-06 라이브 job 3b9c12052fb8)
        words = None
        if b.get("tts_path") and Path(b["tts_path"]).exists():
            from shopping_shorts import mix_pipeline as _mp
            words, _src = _mp._beat_words_src(str(b["tts_path"]), _mp._probe_duration(str(b["tts_path"])),
                                              removed=tts_timestamps.load_removed(str(b["tts_path"])))
        end = storyboard.signal_end_sec(b.get("narration") or "", b.get("signal") or "", words) if words else None
        if end is None:
            r["signal_end"] = None
            r["note"] = "TTS 정밀 시각 없음(받아쓰기 폴백 칸) — 신호어 시각 대조 생략"
        else:
            r["signal_end"] = round(end, 3)
            want = round(min(storyboard.MEME_MAX_SEC, max(storyboard.MEME_MIN_SEC, end - float(b.get("head_trim") or 0))), 2)
            r["signal_gap"] = round(r["head_sec"] - (end - float(b.get("head_trim") or 0)), 3)   # +면 짤이 신호어보다 길다(하한 1초로 늘린 몫)
            if abs(want - r["head_sec"]) > TOL:
                r["problems"].append("head_sec %.2f ≠ 기대 %.2f(신호어 끝 %.2f)" % (r["head_sec"], want, end))
        bad += bool(r["problems"])
        rows.append(r)
    return {"job": job_id, "beats": len(beats), "meme_beats": sum(1 for r in rows if r.get("meme")),
            "bad": bad, "rows": rows, "screen": (screen_clips._JOB_STATE.get(job_id) or {})}


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")      # 윈도 콘솔(cp949)에서도 한글 출력
    except (AttributeError, ValueError) as e:
        print("stdout 인코딩 변경 실패: %r" % e, file=sys.stderr)
    if len(argv) < 2:
        print(__doc__)
        return 2
    res = check(argv[1])
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        if res.get("error"):
            print(res["error"])
            return 1
        print("job %s · 칸 %d · 짤 칸 %d · 문제 칸 %d · 화면 %s" % (res["job"], res["beats"], res["meme_beats"], res["bad"],
                                                         res["screen"].get("screen")))
        for r in res["rows"]:
            if not r.get("meme"):
                print("  칸%-3s [%s] %s" % (r["beat"], r["rank"], r["note"]))
                continue
            print("  칸%-3s [%s] %s 짤 %.2f초 · 신호어 끝 %s · 차 %s · 장면 %s(1초 미만 %s) %s" % (
                r["beat"], r["rank"], r.get("emotion"), r["head_sec"], r.get("signal_end"), r.get("signal_gap"),
                r.get("scenes"), r.get("short_scenes"), ("문제: " + " / ".join(r["problems"])) if r["problems"] else "통과"))
    return 1 if res.get("bad") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
