# -*- coding: utf-8 -*-
"""표기(광고·AI 콘텐츠·출처) 결과물 검사 — 관제 239. 진짜 렌더(video_assemble.assemble)와 진짜 캡컷 조립
(capcut_draft.assemble_draft_folder)을 돌려 **결과물**에서 잰다.

잰다:
  ① 렌더 두 갈래(옛 경로 / 장면꾸미기 경로) × 표기 없음/있음 — 오른쪽 위 영역 픽셀이 표기 있을 때만 바뀌고,
     나머지 화면은 그대로인가(표기 없는 기존 영상은 한 픽셀도 안 바뀌어야 한다).
  ② 영상 처음·끝 근처 프레임 모두에 표기가 있나(전 구간).
  ③ 캡컷 초안: 'disclosure' 트랙이 영상 전체 길이로 있고, 복사된 PNG 가 렌더가 쓴 그림과 같은가(md5).
사용: py tools/travel/check_disclosure.py <작업폴더>      (rc=0 통과)
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts import video_assemble as va, capcut_draft   # noqa: E402

DISC = {"disclosure": {"ad": True, "ai": True, "source": "출처: 여기어때"}}
BOX = (680, 30, 1080, 300)          # 오른쪽 위(표기 자리) — x0,y0,x1,y1
STORY = {"mode": "story", "presetId": "t11", "captionTexts": {}, "effects": {}}


def _md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def _frame(mp4, t, out):
    va._run_ffmpeg(["ffmpeg", "-y", "-ss", str(t), "-i", str(mp4), "-frames:v", "1", str(out)])
    return np.asarray(Image.open(out).convert("RGB")).astype(int)


def _diff(a, b, box=None):
    if box:
        x0, y0, x1, y1 = box
        a, b = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
    return float(np.abs(a - b).mean())


def main():
    work = Path(sys.argv[1] if len(sys.argv) > 1 else "disclosure_check").resolve()
    work.mkdir(parents=True, exist_ok=True)
    src = work / "source.mp4"
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=3", "-f", "lavfi",
                    "-i", "sine=frequency=440:sample_rate=44100", "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)])
    tts = work / "voice.wav"
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=44100", "-t", "1", str(tts)])
    caps = ["첫 번째 자막", "두 번째 자막", "마지막 자막"]
    plan = {"beats": [{"beat_idx": i, "narration": c, "caption_lines": [c], "tts_path": str(tts), "target_seconds": 1,
                       "role": "hook" if i == 0 else "body", "primary": {"video_id": "s0", "start": i, "end": i + 1}}
                      for i, c in enumerate(caps)]}
    tts_map = {i: str(tts) for i in range(3)}
    fails = 0
    for label, base in (("옛 경로", {}), ("장면꾸미기", {"scene_style": STORY})):
        outs = {}
        for tag, deco in (("없음", dict(base)), ("있음", dict(base, **DISC))):
            out = work / ("final_%s_%s.mp4" % (label, tag))
            with va.preview_preset():
                va.assemble(plan, tts_map, {"s0": str(src)}, str(out), deco=deco)
            outs[tag] = out
        res = {}
        for t in (0.2, 2.7):
            a = _frame(outs["없음"], t, work / ("f_%s_없음_%s.png" % (label, t)))
            b = _frame(outs["있음"], t, work / ("f_%s_있음_%s.png" % (label, t)))
            mask = np.ones(a.shape[:2], bool)
            x0, y0, x1, y1 = BOX
            mask[y0:y1, x0:x1] = False
            res[t] = (_diff(a, b, BOX), float(np.abs(a - b)[mask].mean()))
        ok = all(inside > 6 and outside < 1.5 for inside, outside in res.values())
        fails += not ok
        print("%s 렌더 %s — 표기 영역 변화 %s / 나머지 변화 %s" % (
            "✅" if ok else "❌", label,
            ", ".join("%.1f초 %.1f" % (t, v[0]) for t, v in res.items()),
            ", ".join("%.1f초 %.2f" % (t, v[1]) for t, v in res.items())))
    # 캡컷
    tl = va._beat_timeline(plan, tts_map)
    cc = work / "capcut"
    proj, _, _ = capcut_draft.assemble_draft_folder(str(cc), "C:/capcut_check", plan=plan, timeline=tl,
                                                    source_video_paths={"s0": str(src)}, tts_paths=tts_map,
                                                    project_name="disclosure_check", deco=dict(DISC))
    draft = json.loads((Path(proj) / "draft_content.json").read_text(encoding="utf-8"))
    tr = [t for t in draft["tracks"] if t.get("name") == "disclosure"]
    seg = tr[0]["segments"][0] if tr and tr[0]["segments"] else None
    ref = va.disclosure_layer_png(DISC, work / "ref_disclosure.png")
    same = (Path(proj) / "disclosure.png").exists() and _md5(Path(proj) / "disclosure.png") == _md5(ref)
    full = bool(seg) and seg["target_timerange"]["start"] == 0 and abs(seg["target_timerange"]["duration"] - draft["duration"]) <= 1
    ok = bool(seg) and same and full
    fails += not ok
    print("%s 캡컷 — 표기 트랙 %s · 전 구간 %s · 렌더와 같은 그림(md5) %s" % ("✅" if ok else "❌", bool(seg), full, same))
    # 표기 없는 캡컷엔 트랙이 없어야 한다
    proj2, _, _ = capcut_draft.assemble_draft_folder(str(cc), "C:/capcut_check", plan=plan, timeline=tl,
                                                     source_video_paths={"s0": str(src)}, tts_paths=tts_map,
                                                     project_name="no_disclosure", deco={})
    d2 = json.loads((Path(proj2) / "draft_content.json").read_text(encoding="utf-8"))
    none_ok = not any(t.get("name") == "disclosure" for t in d2["tracks"])
    fails += not none_ok
    print("%s 캡컷(표기 없음) — 표기 트랙 없음 %s" % ("✅" if none_ok else "❌", none_ok))
    print("문구:", va.disclosure_texts(DISC), "· 결과물:", work)
    print("결과:", "통과" if not fails else "실패 %d" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
