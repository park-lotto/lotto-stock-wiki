# -*- coding: utf-8 -*-
"""고객 PC 설정·편집 화면의 미리보기 요청 — 완성본과 **같은 함수**로 만든 장면꾸미기 입력(관제 234 5판, 사장님 10-19
"보여주기식 하지 말고 / PC 에서 수정을 볼 수 있게").

    py tools/calcopy/preview_request.py preview   (stdin JSON: {preset, pack, title?, captions?, topic_dir?})
    py tools/calcopy/preview_request.py catalog   (고를 수 있는 값 — 렌더러·틀 규칙이 아는 이름만 + 기본 팩)
    py tools/calcopy/preview_request.py check     (stdin JSON: {pack} → 고객이 바꾼 값이 목록 안에 있나 — 저장 전 관문)

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
    from shopping_shorts.calcopy_frame import schema, to_snapshot
    html = (ROOT / "out" / "scene-style-ui-showcase.html").read_text(encoding="utf-8")
    fonts = sorted({m.group(1) for m in re.finditer(r'@font-face\s*\{[^}]*?font-family:\s*"?([A-Za-z0-9_-]+)"?;', html)})
    voices, seen = [], set()
    for v in json.loads((ROOT / "shopping_shorts" / "assets" / "voice_presets.json").read_text(encoding="utf-8")):
        vid = str(v.get("base_voice_id") or "")
        if vid.startswith("tc_") and vid not in seen:                 # 목소리 = 타입캐스트(고객 키)
            seen.add(vid)
            voices.append({"voice_id": vid, "name": v["name"], "preset_id": v.get("preset_id"), "about": v.get("one_liner") or ""})
    return {"fonts": fonts, "caption_enter": list(schema.CAPTION_ENTER_KINDS), "emphasis": list(schema.EMPH_STYLES),
            "caption_mode": ["accumulate", "replace"], "voices": voices, "bgm": bgm_lib.list_tracks(), "default_pack": default_pack(),
            # 숏템메이커 템플릿(썰20·고정20) — 이름만(견본 그림은 벤치 화면이라 고객에게 안 보낸다). 고르면 렌더러가 그 자리에서 그린다
            "templates": [{"mode": m, "id": r["id"], "name": r["name"]} for m in ("story", "continuous") for r in to_snapshot.template_rows(m)]}


def default_pack() -> dict:
    """고객 PC 첫 설정 = 엔진 기본 팩(my_packs.json "1") — 우리 PC 경로(dir·manifest)·설명 칸은 빼서 설치 폴더 자산(CALCOPY_PACK_ROOT)을 쓰게."""
    from shopping_shorts import calcopy_make as MK
    p = json.loads(MK.REPO_PACKS.read_text(encoding="utf-8"))["1"]
    out = {k: v for k, v in p.items() if not k.startswith("_") and k not in ("name", "base_preset")}
    for pool in ("sfx_pool", "meme_pool"):
        out[pool] = {k: v for k, v in (out.get(pool) or {}).items() if k not in ("dir", "manifest")}
    out["bgm"] = {k: v for k, v in (out.get("bgm") or {}).items() if k != "lib"}
    out["brand"] = {k: v for k, v in (out.get("brand") or {}).items() if not k.startswith("_")}
    out["tts"] = {k: v for k, v in (out.get("tts") or {}).items() if not k.startswith("_")}
    return out


EDITABLE = {"brand": ("channel_name", "colors"), "text": ("title_font", "caption_font", "caption"),
            "tts": ("provider", "voice_id", "name", "preset_id", "tempo", "alternates"), "bgm": ("candidates", "gain"),
            "sfx_pool": ("start", "point", "end"), "meme_pool": ("kinds", "ids"), "template": None}


def check(pack: dict, cat: dict | None = None) -> list:
    """저장 전 관문 — 모르는 칸·목록 밖 값은 거절한다(조용히 버리면 '저장했는데 안 바뀐다', channel_profile.validate 와 같은 원칙)."""
    cat = cat or catalog()
    err = []
    for k, v in pack.items():
        if k not in EDITABLE:
            err.append(f"모르는 칸: {k}")
        elif k == "template":
            if v != "none" and not (isinstance(v, dict) and set(v) == {"mode", "id"}
                                    and any(x["mode"] == v["mode"] and x["id"] == v["id"] for x in cat["templates"])):
                err.append(f"모르는 템플릿: {v}")
        elif not isinstance(v, dict) or any(x not in EDITABLE[k] for x in v):
            err.append(f"모르는 칸: {k}.{sorted(set(v) - set(EDITABLE[k])) if isinstance(v, dict) else v}")
    b, tx, tts, bgm = pack.get("brand") or {}, pack.get("text") or {}, pack.get("tts") or {}, pack.get("bgm") or {}
    if not isinstance(b.get("channel_name", ""), str) or len(b.get("channel_name", "")) > 30 or re.search(r"[<>{}$\\]", b.get("channel_name", "")):
        err.append("채널명은 30자 이하 글자여야 합니다")
    for key in ("title_font", "caption_font"):
        if tx.get(key) and tx[key] not in cat["fonts"]:
            err.append(f"모르는 글꼴: {tx[key]}")
    cap = tx.get("caption") or {}
    if set(cap) - {"mode", "enter", "emphasis", "outline_px", "outline_rgb"}:
        err.append(f"모르는 자막 칸: {sorted(set(cap) - {'mode', 'enter', 'emphasis', 'outline_px', 'outline_rgb'})}")
    o = cap.get("outline_rgb")
    if o is not None and not (isinstance(o, list) and len(o) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in o)):
        err.append("외곽선 색은 [R,G,B] 0~255")
    if cap.get("mode") and cap["mode"] not in cat["caption_mode"]:
        err.append(f"모르는 자막 쌓기: {cap['mode']}")
    e = cap.get("enter")
    if e not in (None, "none") and not (isinstance(e, dict) and e.get("kind") in cat["caption_enter"] and 0 <= float(e.get("ms", 300)) <= 5000):
        err.append(f"모르는 자막 등장: {e}")
    m = cap.get("emphasis")
    if m not in (None, "none") and not (isinstance(m, dict) and m.get("words") == "auto" and m.get("style") in cat["emphasis"]
                                         and isinstance(m.get("rgb"), list) and len(m["rgb"]) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in m["rgb"])):
        err.append(f"모르는 낱말 강조: {m}")
    if "outline_px" in cap and not (isinstance(cap["outline_px"], (int, float)) and 0 <= cap["outline_px"] <= 20):
        err.append("자막 외곽선은 0~20px")   # 화면 막대는 0~12(넘으면 글자가 뭉개진다), Claude 가 말로 키우는 건 20까지
    if tts.get("voice_id") and tts["voice_id"] not in {v["voice_id"] for v in cat["voices"]}:
        err.append(f"모르는 목소리: {tts.get('name') or tts['voice_id']}")
    if tts.get("tempo") is not None and not (isinstance(tts["tempo"], (int, float)) and 0.8 <= tts["tempo"] <= 1.8):
        err.append("말 빠르기는 0.8~1.8")
    ids = {x["id"] for x in cat["bgm"]}
    for x in bgm.get("candidates") or []:
        if x not in ids:
            err.append(f"모르는 배경음악: {x}")
    if bgm.get("gain") is not None and not (isinstance(bgm["gain"], (int, float)) and 0 <= bgm["gain"] <= 0.5):
        err.append("배경음악 크기는 0~0.5")
    return err


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if argv[:1] == ["catalog"]:
            out = {"catalog": catalog()}
        elif argv[:1] == ["check"]:
            out = {"errors": check((json.loads(sys.stdin.buffer.read().decode("utf-8")) or {}).get("pack") or {})}
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
