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
    # 목소리 = 칼카피 명단(engine/voices.py — 사장님 10-20 확정, 필재 금지)만. 10-21 실측: 설정 화면에 필재·명단 밖(김건·용식이·발키리)이 나오고 미나가 없었다.
    #   타입캐스트 = 회원 타입캐스트 키 · 미나(일레븐랩스) = 회원 일레븐랩스 키(사장님 10-21)
    from tools.calcopy.engine.voices import KNOWN_VOICES, BANNED_VOICES, PROVIDERS, TC_EMOTIONS
    presets = json.loads((ROOT / "shopping_shorts" / "assets" / "voice_presets.json").read_text(encoding="utf-8"))
    voices = []
    for k in KNOWN_VOICES:
        if k["voice_id"] in BANNED_VOICES:
            continue
        p = next((v for v in presets if v.get("base_voice_id") == k["voice_id"] or v.get("preset_id") == k["voice_id"]), {})
        voices.append({"voice_id": k["voice_id"], "name": k["name"], "preset_id": p.get("preset_id") or k["voice_id"],
                       "engine": "elevenlabs" if k["engine"] == "일레븐랩스" else "typecast", "about": p.get("one_liner") or k.get("note") or ""})
    return {"fonts": fonts, "caption_enter": list(schema.CAPTION_ENTER_KINDS), "emphasis": list(schema.EMPH_STYLES),
            "caption_mode": ["accumulate", "replace"], "voices": voices, "tts_emotions": list(TC_EMOTIONS), "tts_providers": list(PROVIDERS), "bgm": bgm_lib.list_tracks(), "default_pack": default_pack(),
            "preset_defaults": preset_defaults_table(),   # 프리셋마다 기본값(원본 영상 기준) — packFor 가 엔진 기본 팩 위에 얹는다
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
    # 효과음: 설치본 팩 장부(CALCOPY_PACK_ROOT/packs_manifest.json — 설치팩 build_packs 가 동봉 팩01~09 로 만든다)가 있으면
    #   팩01 의 오프너=시작·뽁=강조·띵=끝(우리 장부 번호 80·1473·78 자리 그대로의 역할). 짤 번호는 우리 PC 서버 번호라 고객 PC 엔 없다 → 비운다.
    man = MK._pack_assets()
    by = {(a.get("pack"), a.get("slot")): a["id"] for a in man.values() if a.get("pack")}
    if by:
        out["sfx_pool"] = {"start": [by[("팩01", "opener")]], "point": [by[("팩01", "pop")]], "end": [by[("팩01", "ding")]]}
        out["meme_pool"] = {"kinds": (out.get("meme_pool") or {}).get("kinds") or [], "ids": []}
    out["brand"] = {k: v for k, v in (out.get("brand") or {}).items() if not k.startswith("_")}
    out["tts"] = {k: v for k, v in (out.get("tts") or {}).items() if not k.startswith("_")}
    return out


PRESET_DEFAULTS_FILE = ROOT / "tools" / "calcopy" / "preset_defaults.json"   # 설치본: 빌드 때 프리셋마다 만든 표({고객용 id: 기본값})


def preset_defaults(preset: str | pathlib.Path) -> dict:
    """★규칙(사장님 10-20): 기본값은 **그 프리셋의 원본 영상에 맞춘다 — 모든 프리셋**. 회원이 설정에서 바꾼 칸만 회원 값
    (shortem_client local_settings.packFor = 엔진 기본 팩 ← 이 값 ← 회원이 바꾼 칸). 엔진 기본 팩(my_packs "1")은 프리셋에 없는 칸만 채운다.
      글꼴·자막 외곽선 = 프리셋 틀(frame.json — 원본 실측) 그대로.
      목소리·빠르기·배경음악·자막 쌓기 = 프리셋 폴더 defaults.json(사장님이 그 프리셋으로 만든 편 기록, 근거는 그 파일 _from).
    10-20 실측 사고: 프리셋 5개가 모두 팩 하나(잘난고딕·프리텐다드·외곽선 0·남자 필재)로 덮여 4개가 원본과 달랐다(숏템리폿 외곽선 13→0)."""
    pdir = pathlib.Path(preset)
    pdir = pdir if pdir.is_absolute() else ROOT / pdir
    out: dict = {}
    frame = json.loads((pdir / "frame.json").read_text(encoding="utf-8")) if (pdir / "frame.json").is_file() else None
    if frame:
        man = json.loads((pdir / "manifest.json").read_text(encoding="utf-8")) if (pdir / "manifest.json").is_file() else {}
        if man.get("variable_stats"):   # 편마다 값($per_video) = 프리셋이 잰 중앙값 — 만들 때와 같은 주인(per_video.fill_defaults)
            from shopping_shorts.calcopy_frame import per_video as PV
            frame, _ = PV.fill_defaults(frame, man["variable_stats"])
        real = lambda v: v if isinstance(v, str) and v and "$per_video" not in v else None   # noqa: E731 — 못 채운 칸은 기본값으로 안 쓴다
        layers = [L for fr in (frame.get("frames") or [frame]) for L in fr.get("layers", []) if L.get("kind") == "text"]
        title = next((L for L in layers if L.get("role") == "title" and real(L.get("font"))), None)
        cap = next((L for L in layers if L.get("role") == "caption" and real(L.get("font"))), None)
        text = {}
        if title:
            text["title_font"] = title["font"]
        if cap:
            text["caption_font"] = cap["font"]
            o = cap.get("outline")
            if o is None or isinstance(o, dict):
                o = o or {}
                text["caption"] = {"outline_px": o.get("px") or 0, **({"outline_rgb": list(o["rgb"])} if isinstance(o.get("rgb"), list) else {})}
        if text:
            out["text"] = text
    own = pdir / "defaults.json"
    if own.is_file():
        d = json.loads(own.read_text(encoding="utf-8"))
        for k in ("tts", "bgm"):
            if isinstance(d.get(k), dict):
                out[k] = {x: v for x, v in d[k].items() if not x.startswith("_")}
        if (d.get("caption") or {}).get("mode"):
            out.setdefault("text", {}).setdefault("caption", {})["mode"] = d["caption"]["mode"]
    return out


def preset_defaults_table() -> dict:
    try:
        return json.loads(PRESET_DEFAULTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


EDITABLE = {"brand": ("channel_name", "colors"), "text": ("title_font", "caption_font", "caption"),
            "tts": ("provider", "voice_id", "name", "preset_id", "tempo", "alternates", "emotion"), "bgm": ("candidates", "gain"),
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
    # 목소리 = provider 별 검증(관제 266, 사장님 10-26 — 추천 성우·세 엔진 검색 성우·타입캐스트 감정까지). 명단(cat voices)은 추천일 뿐.
    #   판단 주인 = engine/voices.check_tts(필재는 어느 provider 든 거절·voice_id 형식·provider 값·emotion 허용 값)
    from tools.calcopy.engine.voices import check_tts
    err += check_tts(tts)
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
