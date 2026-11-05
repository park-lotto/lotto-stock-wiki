# -*- coding: utf-8 -*-
"""회원이 올린 프리셋 묶음(spec.json · job.template.json · fonts · prompts) → 우리 프리셋 폴더(frame.json · defaults.json · r7.json · manifest.json)
(관제 319 · 2026-11-06 사장님 "숏박스 회원이 올린 프리셋을 우리 거에 넣고 그대로 돌려 보게").

    PYTHONUTF8=1 py tools/calcopy/engine/member_import.py <회원 preset 폴더> <우리 프리셋 폴더> [--member 2226] [--accept-unknown]
    → <우리 프리셋 폴더>/frame.json · defaults.json · r7.json · manifest.json(import_table) · job.template.json

판단 주인 = 이 파일 RULES 한 곳: 회원 spec 칸마다 셋 중 하나로 가른다.
  옮김          우리 칸에 회원 값을 **그대로**(단위만 바꿈: 0x090D26 → [9,13,38], 줄 가운데 y 둘 → 첫 줄 칸 위 끝·줄 높이) 넣는다
  우리 칸 없음  우리 틀·기본값에 그 칸이 없다 — 회원 값을 manifest.member_values 에 고치지 않고 보관
  옮길 수 없음  회원 스크립트(make_short.py)·회원 Claude 프롬프트 안에만 있는 판단 — 값은 보관, 우리 엔진은 그 판단을 안 한다
회원 값은 고치지 않는다(사장님 '그대로'). 우리 고정 규칙(−14 LUFS·확대 1.0 등)과 다르면 차이만 manifest.rule_diffs 에 적는다.
RULES 에 없는 칸 = 모르는 칸 → 멈춘다(규격 2판 원칙 5 · 잡도리 J78 '모르는 칸 조용히 무시'). --accept-unknown 이면 보관하고 accepted_unknown 에 적는다.
글꼴: 우리 렌더러 등록 글꼴(schema.font_families)에 없는 글꼴은 대체하지 않는다(J17) — 그 층은 만들지 않고 표에 '글꼴 없음'.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import schema  # noqa: E402

MADE_BY = "member_import v1"
MOVED, NO_SLOT, SCRIPT_ONLY = "옮김", "우리 칸 없음", "옮길 수 없음"
VAR = "$per_video"

# (회원 spec 칸 → (갈래, 우리 자리 또는 사유)). 앞부분 맞춤이 아니라 칸 이름 그대로.
RULES = {
    "name": (NO_SLOT, "manifest.member_values(이름)"),
    "version": (NO_SLOT, "manifest.member_version"),
    "measured_from": (NO_SLOT, "manifest.member_values(근거 글)"),
    "canvas.w": (MOVED, "frame.canvas[0]"),
    "canvas.h": (MOVED, "frame.canvas[1]"),
    "layout.background": (MOVED, "layers[bg].rgb"),
    "layout.video_y": (MOVED, "layers[video].y"),
    "layout.video_size": (MOVED, "layers[video].w·h"),
    "title.font": (MOVED, "layers[text:title].font(우리 등록 글꼴이면)"),
    "title.size": (MOVED, "layers[text:title].size"),
    "title.band_h": (NO_SLOT, "제목 띠 = 바탕과 같은 색(투명 판) — 띠 층 없음"),
    "title.line_centers_y": (MOVED, "layers[text:title].y·line_h(두 줄 기준 계산 — 한 줄 제목을 아래 줄 y≈316 에 두는 회원 규칙은 우리 valign 에 없음)"),
    "title.base": (MOVED, "layers[text:title].line_rgb[0]·rgb"),
    "title.highlight": (MOVED, "layers[text:title].line_rgb[-1](두 줄 = 아랫줄)"),
    "title.max_lines": (MOVED, "layers[text:title].lines"),
    "title.max_chars_per_line": (NO_SLOT, "제목 글자 수 상한 — 우리 틀 칸 없음(제목 쓰는 쪽 규칙)"),
    "title.max_width": (MOVED, "layers[text:title].w"),
    "title.font_note": (NO_SLOT, "글꼴 메모"),
    "title.space_em": (NO_SLOT, "띄어쓰기 폭 0.28em — 우리 word_spacing 은 px 덧셈이라 같은 값으로 못 옮김(바꾸지 않고 보관)"),
    "subtitle.font": (MOVED, "layers[text:caption].font(우리 등록 글꼴이면)"),
    "subtitle.size": (MOVED, "layers[text:caption].size"),
    "subtitle.color": (MOVED, "layers[text:caption].rgb"),
    "subtitle.box_alpha": (NO_SLOT, "자막 상자 불투명도 0.5 — 우리 box 는 rgb·pad·radius 뿐(투명도 칸 없음)"),
    "subtitle.pad_x": (MOVED, "layers[text:caption].box.pad"),
    "subtitle.pad_top": (NO_SLOT, "위 여백 따로 — 우리 box.pad 하나"),
    "subtitle.glyph_h": (NO_SLOT, "글자 잉크 높이(측정값)"),
    "subtitle.last_line_center_y": (MOVED, "layers[text:caption].y(아래 줄 기준 계산)"),
    "subtitle.line_pitch": (MOVED, "layers[text:caption].line_h"),
    "subtitle.box_bottom_y": (NO_SLOT, "상자 아래 끝 고정 — 우리 상자는 글자 둘레"),
    "subtitle.max_chars_per_line": (NO_SLOT, "자막 한 줄 글자 수 — 우리 틀 칸 없음"),
    "subtitle.max_lines": (MOVED, "layers[text:caption].lines"),
    "subtitle.min_card_s": (SCRIPT_ONLY, "subs_speechmatics.py 카드 나누기"),
    "subtitle.split_pause_s": (SCRIPT_ONLY, "subs_speechmatics.py 카드 나누기"),
    "burned_subtitle_probe": (SCRIPT_ONLY, "make_short.burned_subtitle_span — 원본 박힌 자막 찾기(자막 다시 얹을지·자르기 범위)"),
    "logo.center_y": (MOVED, "layers[image] 상자 y(그림은 상자 안 contain·가운데 = 회원 render_logo 와 같은 맞춤)"),
    "logo.box": (MOVED, "layers[image].w·h 상한"),
    "ending_card": (NO_SLOT, "끝 검정 + 로고 1초 — 우리 틀에 끝 카드 칸 없음(r7.end 는 잰 값 칸)"),
    "crop.mode": (MOVED, "r7.crop.mode=center · 영상 창 cover 가운데 자르기"),
    "crop.scene_threshold": (SCRIPT_ONLY, "make_short.detect_shots 컷 나누기"),
    "crop.snap_to_center_px": (SCRIPT_ONLY, "make_short.crop_plan"),
    "crop.face_k": (SCRIPT_ONLY, "make_short.crop_plan(face 모드)"),
    "crop.face_max_shift_px": (SCRIPT_ONLY, "make_short.crop_plan(face 모드)"),
    "crop.note": (NO_SLOT, "근거 글"),
    "crop.burned_text": (SCRIPT_ONLY, "make_short.burned_text_span — 컷마다 박힌 예능 자막이 정사각형 안에 들게 x 를 옮김"),
    "segment": (SCRIPT_ONLY, "prompts/pick_segment.txt — 회원 Claude/AGY 가 구간 고름(30~75초 한 덩어리)"),
    "audio.keep_if_lufs_between": (NO_SLOT, "원본 −18~−10 이면 그대로 — 우리 마스터는 −14 고정(master_guard)"),
    "audio.target_lufs": (NO_SLOT, "−14 — 우리 고정 규칙과 같음"),
    "audio.true_peak": (NO_SLOT, "−1.0 dBTP"),
    "audio.tail_fade_s": (NO_SLOT, "끝 0.12초 페이드"),
    "encode": (NO_SLOT, "x264 medium crf18 — 우리 인코딩 주인 = engine/encoder.venc"),
    "tts_voice": (MOVED, "defaults.json tts(보조 — 클립 모드는 원음, TTS 안 씀)"),
    "enhance": (SCRIPT_ONLY, "make_short.enhance_square — Real-ESRGAN(우리 엔진에 없음)"),
}
JOB_RULES = {
    "source": (MOVED, "편마다 소재(재료)"), "start": (MOVED, "편마다 구간 시작"), "end": (MOVED, "편마다 구간 끝"),
    "title": (MOVED, "layers[text:title].text($per_video)"), "highlight": (SCRIPT_ONLY, "한 줄 제목 낱말 강조 — 우리 제목 층에 낱말 강조 없음"),
    "subtitles": (MOVED, "r7.orig_caption.mode(auto=박힌 자막 그대로)"), "logo": (MOVED, "layers[image].src($per_video)"),
    "delogo": (SCRIPT_ONLY, "ffmpeg delogo"), "ending_seconds": (NO_SLOT, "끝 카드 길이"), "ending_jingle": (NO_SLOT, "끝 징글"),
    "enhance": (SCRIPT_ONLY, "Real-ESRGAN"), "out": (NO_SLOT, "출력 경로"), "play": (NO_SLOT, "재생"), "upload": (NO_SLOT, "업로드 문안"),
    "_메모": (NO_SLOT, "메모"),
}
# 움직임(사장님 11-06 '자막 움직임까지') — 회원 spec 에 움직임 칸이 없다. make_short.py 는 제목·로고 = 처음부터 끝까지 정지 PNG,
# 자막 카드 = concat 으로 바로 켜고 바로 끔(페이드 없음), 소리만 끝 afade. 그래서 우리 칸 = 제목 enter null · 자막 enter none.
MOTION = [
    {"what": "제목 등장", "member": "정지 PNG overlay 0초~끝(make_short.render_title·overlay)", "status": MOVED, "ours": "layers[text:title].enter=null"},
    {"what": "자막 카드 등장·퇴장", "member": "concat 카드 바로 켬·끔, 효과 없음(make_short.sub_track)", "status": MOVED, "ours": "layers[text:caption].enter={kind:none}"},
    {"what": "로고", "member": "정지 PNG overlay", "status": MOVED, "ours": "layers[image] 정지"},
    {"what": "영상 자르기 움직임", "member": "컷마다 x 계단 바꿈(crop_expr if(lt(t,..)))", "status": SCRIPT_ONLY, "ours": "가운데 고정(컷 안·컷 사이 이동 없음)"},
    {"what": "소리 끝 페이드", "member": "afade 0.12초", "status": NO_SLOT, "ours": "없음"},
]


def _flat(d: dict, pre: str = "") -> dict:
    out = {}
    for k, v in d.items():
        p = f"{pre}{k}"
        if p in RULES or not isinstance(v, dict):
            out[p] = v
        else:
            out.update(_flat(v, p + "."))
    return out


def _rgb(s: str) -> list:
    h = str(s).replace("0x", "").replace("#", "")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def classify(spec: dict, job: dict, accept_unknown: bool = False) -> tuple[list, list]:
    """(판단 주인) 회원 spec·job 칸 → 옮김 표 행들. 모르는 칸은 멈춘다(accept_unknown 이면 보관 행)."""
    rows, unknown = [], []
    for src, table in (("spec", _flat(spec)), ("job", job)):
        rules = RULES if src == "spec" else JOB_RULES
        for k, v in table.items():
            if k not in rules:
                unknown.append(f"{src}.{k}")
                rows.append({"src": src, "key": k, "value": v, "status": NO_SLOT, "ours": "모르는 칸(보관)"})
                continue
            st, ours = rules[k]
            rows.append({"src": src, "key": k, "value": v, "status": st, "ours": ours})
    if unknown and not accept_unknown:
        raise ValueError(f"모르는 칸 {len(unknown)}개 — RULES 에 갈래를 정하거나 --accept-unknown: {unknown}")
    return rows, unknown


def build_frame(spec: dict, fonts: frozenset, rows: list) -> dict:
    """회원 값 그대로 우리 틀. 글꼴이 우리 등록 글꼴에 없으면 그 층을 만들지 않고 표 행 상태를 바꾼다(대체 금지)."""
    T, S, L = spec["title"], spec["subtitle"], spec["layout"]
    W, H = spec["canvas"]["w"], spec["canvas"]["h"]
    layers = [{"kind": "bg", "rgb": _rgb(L["background"])},
              {"kind": "video", "x": 0, "y": L["video_y"], "w": L["video_size"], "h": L["video_size"], "radius": 0, "cuts": None, "anchor": None}]
    def font_of(fn):
        return Path(fn).stem.replace("-", "") if Path(fn).stem.replace("-", "") in fonts else (Path(fn).stem if Path(fn).stem in fonts else None)
    tf = font_of(T["font"])
    cy = T["line_centers_y"]
    lh = (cy[-1] - cy[0]) / (len(cy) - 1) if len(cy) > 1 else T["size"] * 1.15
    if tf:
        layers.append({"kind": "text", "role": "title", "x": W // 2, "y": round(cy[0] - lh / 2, 1), "w": T["max_width"], "align": "center",
                       "lines": T["max_lines"], "font": tf, "size": T["size"], "line_h": round(lh, 1), "rgb": _rgb(T["base"]),
                       "line_rgb": [_rgb(T["base"])] * (T["max_lines"] - 1) + [_rgb(T["highlight"])], "line_scale": None,
                       "outline": None, "line_outline": None, "shadow": None, "glow": None, "box": None, "italic": False,
                       "letter_spacing": 0, "word_spacing": 0, "valign": "center", "enter": None, "emphasis": None, "text": VAR})
    else:
        _mark(rows, "title.font", "글꼴 없음 — 제목 층 안 만듦(대체 금지)")
    sf = font_of(S["font"])
    if sf:
        n = S["max_lines"]
        layers.append({"kind": "text", "role": "caption", "x": W // 2, "y": round(S["last_line_center_y"] - S["line_pitch"] * (n - 0.5), 1),
                       "w": 1000, "align": "center", "lines": n, "font": sf, "size": S["size"], "line_h": S["line_pitch"], "rgb": _rgb(S["color"]),
                       "line_rgb": None, "line_scale": None, "outline": None, "line_outline": None, "shadow": None, "glow": None,
                       "box": {"rgb": [0, 0, 0], "pad": S["pad_x"], "radius": 0}, "italic": False, "letter_spacing": 0, "word_spacing": 0,
                       "valign": "center", "enter": {"kind": "none", "ms": 0}, "emphasis": None, "text": None})
    else:
        for k in ("subtitle.font", "subtitle.size", "subtitle.color", "subtitle.pad_x", "subtitle.last_line_center_y", "subtitle.line_pitch", "subtitle.max_lines"):
            _mark(rows, k, f"글꼴 {S['font']} 우리 등록 글꼴에 없음 — 자막 층 안 만듦(대체 금지, 값 보관)")
    lg = spec["logo"]
    layers.append({"kind": "image", "src": VAR, "x": (W - lg["box"][0]) // 2, "y": lg["center_y"] - lg["box"][1] // 2, "w": lg["box"][0], "h": lg["box"][1]})
    frame = {"canvas": [W, H], "template_off": None, "made_by": MADE_BY, "source": "member_spec", "layers": layers}
    schema.validate({**frame, "layers": [l if l.get("text") != VAR and l.get("src") != VAR else {**l, **({"text": "가"} if l.get("text") == VAR else {"src": "x.png"})} for l in layers]})
    return frame


def _mark(rows, key, why):
    for r in rows:
        if r["src"] == "spec" and r["key"] == key:
            r["status"], r["ours"] = NO_SLOT, why


def convert(member_dir: Path, out_dir: Path, member: str = "", accept_unknown: bool = False) -> dict:
    member_dir, out_dir = Path(member_dir), Path(out_dir)
    spec = json.loads((member_dir / "spec.json").read_text(encoding="utf-8"))
    job = json.loads((member_dir / "job.template.json").read_text(encoding="utf-8"))
    rows, unknown = classify(spec, job, accept_unknown)
    fonts = schema.font_families()
    frame = build_frame(spec, fonts, rows)
    tv = spec.get("tts_voice") or {}
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    defaults = {"_rule": "회원 프리셋 값 그대로(member_import) — 읽는 곳 tools/calcopy/preview_request.preset_defaults",
                "_from": f"회원 {member} spec.json tts_voice · job.template.json subtitles",
                "tts": {"provider": tv.get("provider"), "voice_id": tv.get("voice_id"), "name": tv.get("name"), "tempo": tv.get("tempo"),
                        "use": tv.get("use")},
                "caption": {"mode": "keep_burned" if job.get("subtitles") == "auto" else job.get("subtitles")},
                "audio": {"source": "original", **(spec.get("audio") or {})}}
    end = spec.get("ending_card") or {}
    r7 = {"made_by": MADE_BY, "updated_at": now, "per_video": {},
          "summary": {"crop": {"mode": (spec.get("crop") or {}).get("mode"), "zoom": 1.0, "core": True, "why": "회원 spec crop.mode"},
                      "orig_caption": {"mode": "burned" if job.get("subtitles") == "auto" else "reburn", "core": False, "why": "회원 job subtitles"},
                      "title": {"lines": spec["title"]["max_lines"], "chars": [1, spec["title"].get("max_chars_per_line")], "core": False},
                      "end": {"sec": end.get("seconds"), "kind": end.get("background"), "optional": end.get("optional"), "core": True}}}
    font_list = []
    for f in sorted((member_dir / "fonts").glob("*.otf")) + sorted((member_dir / "fonts").glob("*.ttf")):
        fam = f.stem.replace("-", "")
        font_list.append({"name": f.name, "sha256": _sha(f), "license": "fonts/LICENSE.txt·GmarketSans_NOTICE.txt",
                          "in_store": fam in fonts or f.stem in fonts})
    prompts = [{"id": p.name, "sha256": _sha(p)} for p in sorted((member_dir / "prompts").glob("*.txt"))]
    rule_diffs = []
    A = spec.get("audio") or {}
    if A.get("keep_if_lufs_between"):
        rule_diffs.append({"rule": "−14 LUFS 마스터(우리 고정)", "member": f"원본 {A['keep_if_lufs_between']} 안이면 그대로, 밖이면 {A.get('target_lufs')}"})
    if (spec.get("crop") or {}).get("burned_text", {}).get("enabled"):
        rule_diffs.append({"rule": "확대 1.0·가운데 자르기", "member": "확대 1.0 같음 · 박힌 글자 따라 컷마다 x 이동(우리 엔진에 없음)"})
    if tv.get("provider") == "typecast" and tv.get("name"):
        rule_diffs.append({"rule": "칼카피 시험 TTS = 피쉬 차분한 해설가", "member": f"타입캐스트 {tv['name']}(보조 — 클립 모드는 원음)"})
    counts = {s: sum(r["status"] == s for r in rows) for s in (MOVED, NO_SLOT, SCRIPT_ONLY)}
    manifest = {"slug": out_dir.parents[1].name if len(out_dir.parents) > 1 else None, "style": out_dir.name, "made_by": MADE_BY,
                "rule": "회원 값 그대로 — member_import.RULES 갈래", "created_at": now, "updated_at": now,
                "variables": ["layers[text:title].text", "layers[image].src"], "sources": [{"id": f"member{member}", "kind": "member_preset",
                "spec_sha256": _sha(member_dir / "spec.json"), "version": spec.get("version")}],
                "format": "숏폼", "member_version": spec.get("version"), "fonts": font_list, "member_prompts": prompts,
                "import_counts": counts, "import_table": rows, "motion": MOTION, "rule_diffs": rule_diffs,
                "accepted_unknown": [{"path": u, "who": "member_import --accept-unknown", "when": now} for u in unknown],
                "member_values": {"spec": spec}}
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, obj in (("frame.json", frame), ("defaults.json", defaults), ("r7.json", r7), ("manifest.json", manifest), ("job.template.json", job)):
        (out_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("member_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--member", default="")
    ap.add_argument("--accept-unknown", action="store_true")
    a = ap.parse_args(argv)
    M = convert(Path(a.member_dir), Path(a.out_dir), a.member, a.accept_unknown)
    print(json.dumps(M["import_counts"], ensure_ascii=False))
    for r in M["import_table"]:
        print(f"{r['status']:<8} {r['src']}.{r['key']:<32} → {r['ours']}")


if __name__ == "__main__":
    main()
