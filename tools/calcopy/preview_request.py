# -*- coding: utf-8 -*-
"""고객 PC 설정·편집 화면의 미리보기 요청 — 완성본과 **같은 함수**로 만든 장면꾸미기 입력(관제 234 5판, 사장님 10-19
"보여주기식 하지 말고 / PC 에서 수정을 볼 수 있게").

    py tools/calcopy/preview_request.py preview   (stdin JSON: {preset, pack, title?, captions?, topic_dir?})
    py tools/calcopy/preview_request.py catalog   (고를 수 있는 값 — 렌더러·틀 규칙이 아는 이름만)

판단 주인(새로 적지 않는다 — 부르기만):
  팩 합치기 = calcopy_make.merge_preset_pack · 제목 글 = remake_video.title_text · 스냅샷 = calcopy_frame.to_snapshot +
  scene_style.validate_snapshot · 장면 = scene_style.context_for · 자막 시각 = frame_video.timeline_from(완성본 폴더가 있으면 그 timeline.json)
결과물 검사: 고객 화면(로컬 127.0.0.1)에서 이 입력으로 그린 장면 = 같은 팩으로 만든 완성본 프레임(shortem_client/test/ui 대조).
출력: 한 줄 JSON {snapshot, context, applied, title} / {catalog} / 실패 {error}
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SAMPLE_TITLE = "아무도 몰랐던\n이 제품의 뒷이야기"
SAMPLE_LINES = ["처음엔 다들 이게 될 리 없다고 했어", "그런데 한 사람이 끝까지 밀어붙였지", "결국 매장 앞에 줄이 생기기 시작했어",
                "지금은 없어서 못 산다는 그 제품이야"]


def _sample_timeline(lines):
    """자막 줄마다 3초 — 첫 줄은 훅(제목이 보이는 장면). 완성본 폴더가 없을 때만."""
    out, t = [], 0.0
    for i, s in enumerate(lines):
        out.append({"beat_idx": i, "t0": t, "dur": 3.0, "narration": s, "caption_lines": [s], "role": "hook" if i == 0 else "body",
                    "primary": {"video_id": "s0", "start": t, "end": t + 3.0}})
        t += 3.0
    return out


def preview(req: dict) -> dict:
    from shopping_shorts import calcopy_make as MK, scene_style
    from shopping_shorts.calcopy_frame import schema, to_snapshot
    from tools.calcopy.remake_video import title_text
    cfg = MK.merge_preset_pack(str(req["preset"]), req.get("pack") or {})
    frame = cfg["frame"]
    if frame is None:
        raise ValueError("이 프리셋에는 화면 틀이 없습니다")
    spec = schema.validate(frame)
    tl, title = None, req.get("title") or SAMPLE_TITLE
    td = pathlib.Path(req["topic_dir"]) if req.get("topic_dir") else None
    if td and (td / "timeline.json").is_file():                       # 완성본 고치기: 그 편의 자막 시각·제목 그대로
        tl = json.loads((td / "timeline.json").read_text(encoding="utf-8")).get("beats")
        if (td / "대본.json").is_file():
            title = (json.loads((td / "대본.json").read_text(encoding="utf-8")).get("final") or {}).get("title") or title
    tl = tl or _sample_timeline([str(x)[:60] for x in (req.get("captions") or SAMPLE_LINES)][:8])
    head = {"text": title_text(spec, {"title": title})}
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    ctx = scene_style.context_for(tl, head, snap)
    return {"snapshot": snap, "context": ctx, "applied": cfg["applied"], "title": head["text"]}


def catalog() -> dict:
    """고를 수 있는 값 — 각 주인이 아는 이름만(렌더러 @font-face · 틀 규칙 · 목소리 목록 · 곡 목록)."""
    from shopping_shorts import bgm_lib
    from shopping_shorts.calcopy_frame import schema
    html = (ROOT / "out" / "scene-style-ui-showcase.html").read_text(encoding="utf-8")
    fonts = sorted({m.group(1) for m in re.finditer(r'@font-face\s*\{[^}]*?font-family:\s*"?([A-Za-z0-9_-]+)"?;', html)})
    voices, seen = [], set()
    for v in json.loads((ROOT / "shopping_shorts" / "assets" / "voice_presets.json").read_text(encoding="utf-8")):
        vid = str(v.get("base_voice_id") or "")
        if vid.startswith("tc_") and vid not in seen:                 # 목소리 = 타입캐스트(고객 키)
            seen.add(vid)
            voices.append({"voice_id": vid, "name": v["name"], "preset_id": v.get("preset_id"), "about": v.get("one_liner") or ""})
    return {"fonts": fonts, "caption_enter": list(schema.CAPTION_ENTER_KINDS), "emphasis": list(schema.EMPH_STYLES),
            "caption_mode": ["accumulate", "replace"], "voices": voices, "bgm": bgm_lib.list_tracks()}


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if argv[:1] == ["catalog"]:
            out = {"catalog": catalog()}
        elif argv[:1] == ["preview"]:
            out = preview(json.loads(sys.stdin.buffer.read().decode("utf-8")))
        else:
            print(__doc__)
            return 2
    except Exception as e:  # noqa: BLE001 — 화면에 이유 한 줄(조용한 실패 금지)
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
