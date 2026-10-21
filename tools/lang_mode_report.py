# -*- coding: utf-8 -*-
"""외국어모드(영어·일본어) 작업 한 편의 **결과물 검사**(2026-10-21 관제 248, 사장님 추가 요구 3가지).

서버에서:  cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
           /home/ubuntu/venv/bin/python tools/lang_mode_report.py <job_id> [--ko <한국어 원본 job_id>]

잰다(숫자로):
  ② 길이 — 칸마다 음성 실측(ffprobe) vs 계획(target_seconds·cap_durs 합·speech_cps 추정) vs 한국어 원본 칸 음성.
           음성이 컷보다 0.3초+ 길면 ⚠️. 완성 영상 전체 길이와 쇼츠 한도(60초·3분).
  ③ 렌더 — 완성 영상에서 처음·중간·끝 + 자막이 바뀌는 시각(칸 리드인+구절 경계 중간)마다 프레임 PNG 를
           <job 폴더>/lang_frames/ 에 남긴다(두부·줄넘침은 사람이 눈으로 본다 — 이 도구는 자리만 정확히 찍는다).
  ③ 싱크 — 첫 비트·마지막 비트 음성을 ASR(언어 자동감지)로 받아써 첫 단어 시각 vs 자막 리드인(cap_lead) 차이.
  ③ 캡컷 — work/capcut 아래 draft_content.json 의 자막 머티리얼: 글 몇 개·그 언어 글자 있는 개수·font_path 값·
           첫/끝 구간 시간. 폰트 파일 동봉 여부(draft 폴더 안 ttf/otf 수).
  ③ 썸네일 — 장면꾸미기 레이어/썸네일 PNG 가 있으면 경로를 찍는다(없으면 '해당 없음').
읽기 전용 — 작업 파일을 고치지 않는다(프레임 PNG 만 새로 만든다).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shopping_shorts import config                 # noqa: E402
from shopping_shorts.store import Store            # noqa: E402
from shopping_shorts import script_translate, edit_plan   # noqa: E402

SHORTS_LIMIT = (60.0, 180.0)


def _dur(p):
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                              "-of", "default=nw=1:nk=1", str(p)], stdin=subprocess.DEVNULL).decode().strip())
    except Exception:      # noqa: BLE001 — 못 재면 None 으로 보고
        return None


def _frame(video, t, out):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.2f" % t, "-i", str(video), "-frames:v", "1", str(out)],
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    return r.returncode == 0 and Path(out).exists()


def _beats(job):
    return [b for b in ((job.get("edit_plan") or {}).get("beats") or []) if isinstance(b, dict)]


def length_report(job, ko_job=None):
    print("== ② 길이 (칸 | 음성실측 | 계획 target | cap_durs합 | cps추정 | 한국어원본 음성)")
    rows, warn = [], 0
    ko_beats = _beats(ko_job) if ko_job else []
    for i, b in enumerate(_beats(job)):
        tts = _dur(b["tts_path"]) if b.get("tts_path") and Path(b["tts_path"]).exists() else None
        tgt = float(b.get("target_seconds") or 0)
        cd = sum(float(x) for x in (b.get("cap_durs") or [])) if b.get("cap_durs") else None
        est = edit_plan.narr_secs(b.get("narration") or "")
        ko_tts = None
        if i < len(ko_beats) and ko_beats[i].get("tts_path") and Path(ko_beats[i]["tts_path"]).exists():
            ko_tts = _dur(ko_beats[i]["tts_path"])
        flag = ""
        if tts is not None and tgt and tts > tgt + 0.3:
            flag = "⚠️ 음성>컷 %.2f" % (tts - tgt); warn += 1
        rows.append((b.get("beat_idx"), tts, tgt, cd, est, ko_tts))
        print("  %2s | %5s | %5.2f | %5s | %4.1f | %5s | %-40s %s" % (
            b.get("beat_idx"), ("%.2f" % tts) if tts is not None else "없음", tgt,
            ("%.2f" % cd) if cd is not None else "없음", est, ("%.2f" % ko_tts) if ko_tts is not None else "-",
            (b.get("narration") or "")[:40], flag))
    tot_tts = sum(r[1] for r in rows if r[1]); tot_tgt = sum(r[2] for r in rows); tot_ko = sum(r[5] for r in rows if r[5])
    vid = job.get("video_path"); vdur = _dur(vid) if vid and Path(vid).exists() else None
    print("  합계: 음성 %.2f초 · 계획 %.2f초 · 한국어원본 음성 %.2f초 · 완성영상 %s초 · 음성>컷 0.3초+ %d칸 · 쇼츠 한도 60초 %s / 3분 %s" % (
        tot_tts, tot_tgt, tot_ko, ("%.2f" % vdur) if vdur else "없음", warn,
        "안" if (vdur or 0) <= SHORTS_LIMIT[0] else "밖", "안" if (vdur or 0) <= SHORTS_LIMIT[1] else "밖"))
    # cps 실측(이 작업): norm 글자 / 음성 초
    import re
    norm = sum(len(re.sub(r"[\s\.,!?~'\"、。！？「」…]+", "", b.get("narration") or "")) for b in _beats(job))
    if tot_tts:
        print("  이 작업 실측 말속도: norm %d자 / %.2f초 = %.2f 자/초 (코드 상수 %s)" % (
            norm, tot_tts, norm / tot_tts, edit_plan.speech_cps(lang=script_translate.job_lang(job), norm=True)))
    return vdur


def frames_report(job, vdur):
    vid = job.get("video_path")
    if not vid or not Path(vid).exists():
        print("== ③ 프레임: 완성 영상 없음"); return
    out = Path(vid).parent / "lang_frames"; out.mkdir(exist_ok=True)
    marks = [("start", 0.5)]
    t = 0.0
    for b in _beats(job):
        lead = float(b.get("cap_lead") or 0.0); durs = [float(x) for x in (b.get("cap_durs") or [])]
        if durs:
            cur = t + lead
            for k, d in enumerate(durs):
                marks.append(("b%s_c%d" % (b.get("beat_idx"), k), cur + d / 2)); cur += d
        t += float(b.get("target_seconds") or 0)
    if vdur:
        marks.append(("mid", vdur / 2)); marks.append(("end", max(0.0, vdur - 0.5)))
    ok = 0
    for name, tt in marks:
        if vdur and tt > vdur:
            continue
        if _frame(vid, tt, out / ("%s_%05.2f.png" % (name, tt))):
            ok += 1
    print("== ③ 프레임 %d장 → %s (자막 구절마다 가운데 시각 + 처음·중간·끝)" % (ok, out))


def sync_report(job):
    from shopping_shorts import asr_check
    print("== ③ 싱크 (ASR 자동감지 첫 단어 시각 vs 자막 리드인)")
    bs = _beats(job)
    for b in (bs[:1] + bs[-1:]) if len(bs) > 1 else bs[:1]:
        p = b.get("tts_path")
        if not p or not Path(p).exists():
            print("  칸 %s 음성 없음" % b.get("beat_idx")); continue
        w = asr_check.transcribe_words(p, language=None) or []
        heard = "".join(x.get("word", "") for x in w) if script_translate.lang_of(b.get("narration")) == "ja" \
            else " ".join(x.get("word", "") for x in w)
        first = float(w[0]["start"]) if w else None
        print("  칸 %s ASR: %s | lang_of=%s | 첫 단어 %.2fs vs cap_lead %.2fs → 차 %s | 오류 %s" % (
            b.get("beat_idx"), heard[:80], script_translate.lang_of(heard), (first if first is not None else -1), float(b.get("cap_lead") or 0),
            ("%.2f" % abs(first - float(b.get("cap_lead") or 0))) if first is not None else "-", getattr(asr_check._LAST, "error", "")))


def capcut_report(job):
    work = Path(config.DB_PATH).parent / "mix_jobs" / job["job_id"]
    cc = work / "capcut"
    drafts = list(cc.rglob("draft_content.json")) if cc.exists() else []
    print("== ③ 캡컷 draft_content.json %d개 (폴더 %s)" % (len(drafts), cc))
    lang = script_translate.job_lang(job)
    for d in drafts[:1]:
        data = json.loads(d.read_text(encoding="utf-8"))
        texts = [m for m in ((data.get("materials") or {}).get("texts") or []) if isinstance(m, dict)]
        subs = [m for m in texts if m.get("type") == "subtitle"]
        def _txt(m):
            c = m.get("content") or ""
            try:
                return "".join(x.get("text", "") for x in (json.loads(c).get("styles") or [])) or json.loads(c).get("text", "")
            except Exception:      # noqa: BLE001
                return str(c)
        n_lang = sum(1 for m in subs if script_translate.lang_of(_txt(m)) == lang)
        fonts = sorted({str(m.get("font_path") or "") for m in subs})
        fonts_files = [p.name for p in d.parent.rglob("*") if p.suffix.lower() in (".ttf", ".otf")]
        segs = []
        for tr in (data.get("tracks") or []):
            if tr.get("type") == "text":
                for s in tr.get("segments") or []:
                    tr_ = s.get("target_timerange") or {}
                    segs.append((tr_.get("start", 0) / 1e6, (tr_.get("start", 0) + tr_.get("duration", 0)) / 1e6))
        print("  자막 머티리얼 %d · 그중 %s 글 %d · font_path 값 %s · 동봉 폰트 파일 %d개 · 자막 구간 %d개 첫 %s 끝 %s" % (
            len(subs), script_translate.LANG_LABEL[lang], n_lang, fonts, len(fonts_files), len(segs),
            ("%.2f~%.2f" % segs[0]) if segs else "-", ("%.2f~%.2f" % segs[-1]) if segs else "-"))
        for m in subs[:3]:
            print("   예:", _txt(m)[:60])
    thumbs = [p for p in work.rglob("*.png") if "layer" in p.name or "thumb" in p.name.lower()]
    print("== ③ 썸네일/레이어 PNG %d개 %s" % (len(thumbs), [str(p) for p in thumbs[:3]] if thumbs else "(장면꾸미기 미사용 — 해당 없음)"))


def main():
    args = sys.argv[1:]
    ko = None
    if "--ko" in args:
        k = args.index("--ko"); ko = args[k + 1]; del args[k:k + 2]
    if not args:
        print(__doc__); return 2
    st = Store(config.DB_PATH)
    job = st.get_mix_job(args[0]); ko_job = st.get_mix_job(ko) if ko else None
    if not job:
        print("job 없음", args[0]); return 1
    print("job", job["job_id"], "status", job.get("status"), "lang", script_translate.job_lang(job), "| 한국어 원본", ko or "-")
    vdur = length_report(job, ko_job)
    frames_report(job, vdur)
    sync_report(job)
    capcut_report(job)
    return 0


if __name__ == "__main__":
    sys.exit(main())
