# -*- coding: utf-8 -*-
"""사건별 효과음 카테고리 결과물 검사 (관제 237) — 진짜 렌더·진짜 캡컷 조립 함수로 돌려 결과물에서 잰다.

하는 일:
  1) 썰 대본 칸 역할(hook·reveal·how·twist·benefit·cta)로 edit_plan 을 만든다. 목소리는 무음(효과음만 또렷이 재려고).
  2) 팩은 mix_pipeline._resolve_sfx_paths(job=…) 실제 연결로, 타점은 video_assemble.sfx_events_for(렌더·캡컷 공통)로 받는다.
  3) 렌더: video_assemble._burn_captions 로 완성본 mp4 → 소리를 뽑아 각 카테고리 소리 파일과 파형 상관(±40ms)으로 대조.
  4) 캡컷: capcut_draft.assemble_draft_folder 로 초안 폴더 → 복사된 효과음 파일 md5·타점(draft_content.json)을 대조.
  기대: 공개 첫 줄=reveal · 반전 첫 줄=shock · 결과 첫 줄=money 가 두 길 모두에 같은 파일·같은 시각으로 들어간다.
사용: py tools/sfx_bench/category_render_check.py <작업폴더>   (rc=0 이면 통과)
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts import video_assemble as va, mix_pipeline, sfx_pack, capcut_draft   # noqa: E402
from shopping_shorts.edit_plan import narr_secs   # noqa: E402

SR = 44100
LINES = [("hook", "와 이거 진짜 뭐야 처음 보는 물건이다"),
         ("bait", "다들 이걸 보고 처음엔 장난감인 줄 알았대요"),
         ("reveal", "정체는 바로 접이식 실리콘 깔때기였습니다"),
         ("how", "병 입구에 끼우고 그대로 부어주면 끝입니다"),
         ("twist", "근데 진짜 충격적인 포인트는 따로 있었어요"),
         ("benefit", "이거 하나로 주방 도구 세 개를 안 사도 됩니다"),
         ("cta", "궁금하면 고정 댓글 확인해 보세요")]
EXPECT = {2: "reveal", 4: "shock", 5: "money"}      # 칸 번호 → 그 칸 첫 자막 소리(둘째 칸 첫 줄은 첫 넘김 휙+틱 몫이라 공개는 셋째 칸에)


class _Store:
    def get_setting(self, k, d=""):
        return "1" if k == "sfx_pack_enabled" else d

    def get_scene_asset(self, *a, **k):
        return None

    def get_work_state_by_job(self, job_id):
        return {"script_style_id": 70}

    def list_spines(self, status=None):
        return [{"id": 70, "fit_categories": ["발명품형"]}]


def _md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def _audio(mp4):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(float)


def _match(track, path, at):
    """완성본 소리에서 at 근처(±40ms)에 path 소리가 있나 — 정규화 상관 최댓값과 그때 어긋남(ms)."""
    x, sr = sf.read(path)
    x = x.mean(1) if x.ndim > 1 else x
    if sr != SR:
        raise SystemExit("표본율 다름 %s" % path)
    n = min(len(x), int(0.4 * SR))
    x = x[:n]
    best, lag = 0.0, 0
    for d in range(-int(0.04 * SR), int(0.04 * SR) + 1, 22):
        a = int(at * SR) + d
        if a < 0 or a + n > len(track):
            continue
        y = track[a:a + n]
        c = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-12))
        if c > best:
            best, lag = c, d
    return best, lag * 1000.0 / SR


def _all_sounds(pack_dir):
    """이 팩이 낼 수 있는 소리 파일 전부 — 완성본 그 순간에 '어느 파일이 울리나'를 가려낸다."""
    out = [os.path.join(pack_dir, s + ".wav") for s in sfx_pack.SLOTS]
    for s in sfx_pack.CATEGORY_SLOTS:
        d = os.path.join(sfx_pack.CATEGORY_DIR, s)
        out += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".wav")]
    return out


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "category_check").resolve()
    out.mkdir(parents=True, exist_ok=True)
    beats, tts = [], {}
    for i, (role, text) in enumerate(LINES):
        p = out / ("tts_%d.wav" % i)
        sf.write(str(p), np.zeros(int(float(narr_secs(text)) * SR)), SR, subtype="PCM_16")
        beats.append({"beat_idx": i, "narration": text, "role": role})
        tts[i] = str(p)
    plan = {"beats": beats}
    total = sum(va._probe_duration(p) for p in tts.values())
    base = out / "base.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x303030:s=1080x1920:r=30:d=%.3f" % total,
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "%.3f" % total,
                    "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(base)], check=True)
    job = {"job_id": "category_check", "customer_id": 7, "deco": {}, "edit_plan": plan}
    sfx_paths = mix_pipeline._resolve_sfx_paths(_Store(), plan, 7, job=job)
    assert sfx_paths.get("_pack"), "팩이 안 잡혔다"
    tl = va._beat_timeline(plan, tts)
    events = va.sfx_events_for(tl, sfx_paths)          # 렌더·캡컷이 받는 바로 그 목록
    final = out / "final.mp4"
    work = out / "work"; work.mkdir(exist_ok=True)
    va._burn_captions(str(base), plan, tts, str(final), work, deco={}, sfx_paths=sfx_paths)
    track = _audio(final)

    # 캡컷 초안
    cc_root = out / "capcut"
    proj, project, _ = capcut_draft.assemble_draft_folder(str(cc_root), "C:/capcut_check", plan=plan, timeline=tl,
                                                          source_video_paths={}, tts_paths=tts, project_name="category_check",
                                                          deco={}, sfx_events=events)
    draft = json.load(open(Path(proj) / "draft_content.json", encoding="utf-8"))
    cc_aud = {}
    mats = {m["id"]: m for m in draft.get("materials", {}).get("audios", [])}
    for trk in draft.get("tracks", []):
        for s in trk.get("segments", []):
            m = mats.get(s.get("material_id"))
            if m and os.path.basename(m.get("path", "")).startswith("sfx_"):
                cc_aud[os.path.basename(m["path"])] = s["target_timerange"]["start"] / 1e6

    fails = 0
    starts = {b["beat_idx"]: float(b["t0"]) for b in tl}
    print("팩 %s · 길이 %.2f초 · 효과음 %d발" % (sfx_paths["_pack"]["name"], total, len(events)))
    for k, ev in enumerate(events):
        path, at = ev[0], float(ev[1])
        slot = Path(path).parent.name if Path(path).parent.parent == Path(sfx_pack.CATEGORY_DIR) else Path(path).stem
        corr, lag = _match(track, path, at)
        # 그 순간 가장 닮은 파일 — 압축으로 상관이 떨어져도 '다른 소리가 아니라 이 소리'인지는 이것으로 본다
        who = max(_all_sounds(sfx_paths["_pack"]["dir"]), key=lambda q: _match(track, q, at)[0])
        ccf = Path(proj) / ("sfx_%02d%s" % (k, Path(path).suffix))
        cc_ok = ccf.exists() and _md5(ccf) == _md5(path) and abs(cc_aud.get(ccf.name, -9) - at) < 0.002
        beat = max((b for b, t in starts.items() if t <= at + 0.04), default=0)
        want = EXPECT.get(beat) if abs(at - starts.get(beat, -9)) < 0.3 else None
        ok = os.path.normcase(who) == os.path.normcase(path) and cc_ok and (want is None or slot == want)
        fails += not ok
        print("%s %5.2f초 칸%d %-7s 렌더 상관 %.2f(%+.0fms)%s · 캡컷 %s%s  %s" % (
            "✅" if ok else "❌", at, beat, slot, corr, lag, "" if os.path.normcase(who) == os.path.normcase(path) else " ★가장 닮은 건 " + os.path.basename(who), "같은 파일·같은 시각" if cc_ok else "불일치",
            (" · 기대 " + want) if want else "", os.path.relpath(path, HERE)))
    got = {Path(e[0]).parent.name for e in events}
    for want in EXPECT.values():
        if want not in got:
            fails += 1
            print("❌ 기대한 %s 소리가 계획에 없다" % want)
    print("완성본", final, "· 캡컷", proj)
    print("결과:", "통과" if not fails else "실패 %d" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
