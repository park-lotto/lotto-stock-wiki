# -*- coding: utf-8 -*-
"""두유노홈디노(@Home_Design_Note) 프리셋 「전체화면_가운데자막」 — 만들기·채널 규칙 얹기·하나-빼고 렌더 검증 (관제 097, 2026-10-17 오푸스).

    PYTHONUTF8=1 py channel/homedesignnote/preset/hdn_preset.py build      # 손질 설명서 8편 → 프리셋 + 채널 규칙
    PYTHONUTF8=1 py channel/homedesignnote/preset/hdn_preset.py loo        # 편 하나씩 빼고 나머지로 만든 프리셋 → 실제 렌더 → 원본과 잉크 대조

왜 엔진 loo_preset 을 안 쓰나: 그 도구는 제목 층을 필수로 읽고(next(role=title)) 창·제목 띠 항목만 잰다 — 이 채널은 제목·띠가 없고
자막·워터마크만 있는 전체 화면이라 잴 것이 없다(엔진 요청으로 보고). 프리셋 만들기 자체는 엔진 loo_preset.build·preset_save.save 를 그대로 부른다.

틀 판단(사장님 10-17): 인스타 스타일 = 짤 0·효과음 0·틀 띠·제목 띠 없음, 자막만 + 차분한 BGM. 채널명 = 잇썸홈(원본 워터마크 자리·같은 크기).
자막 y 는 편집자가 편마다 고르는 값(50편 bench 띠 위: 480대 5·580대 4·760대 7·930대 13 …) — 창 기준 관계(cap_dy)가 아니다.
"""
from __future__ import annotations

import json
import shutil
import statistics as st
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import loo_preset as L, preset_save as P  # noqa: E402

SLUG, STYLE = "homedesignnote", "전체화면_가운데자막"
PRESET = ROOT / "channel" / SLUG / "preset" / STYLE
WORK = Path("C:/숏템_칼카피/homedesignnote/preset_work")
HAND = Path(__file__).parent / "_hand"   # 손질 설명서(frame_<id>.json) — to_frame 자동본 + 손질 근거(made_from.notes)
MP4 = Path("C:/숏템_칼카피/homedesignnote/mp4")
IDS = ["fQPX6XeXeN0", "DCXQjaWcZ-g", "7Nj6b0mX4HM", "e15KZ_nO1_Y", "R0-bfj7JarA", "Ez7KsS2K_Pk", "seFkrVR-nYs", "orBlWWhejtc"]
CAP_Y = "layers[text:caption].y"
BRAND = "layers[text:brand].text"
CAP_Y_MODE = 927                          # 50편 bench 자막 띠 위 최빈 무리 936(13/45편) − 9(크기 64·줄 칸 74 의 칸 위 여백, 렌더 실측)

# script_frame 공식 F1 칸(1_skeleton.formulas[F1].slots) — 대본 줄마다 맡는 일
ROLES = ["훅", "도입", "설명", "효과", "행동유도"]

CHANNEL_RULES = {
    "_why": "사장님 10-16 밤·10-17 결정 + 50편 bench·asr·judge 실측(값마다 출처)",
    "script_frame": "channel/homedesignnote/대본설명서/script_frame.json",
    "formula": "F1 (훅>도입>설명>효과>행동유도, 49편 중 14편 0.286 — script_frame 1_skeleton)",
    "allow_hype": True,
    "source_credit": False,
    "story_required": True,
    "climax_min": 4,
    "climax_required": ["센 시작", "진짜 핵심 반전", "~까지 난리"],
    "climax_one_of": ["숫자·권위", "심지어 두 번째 반전"],
    "opening_formula": "[누가]+[무엇을 하다가](구체 행동)+[귀찮아서·현타와서·답답해서]+[만들어버렸대요] — 센 말(빡친·열받은·미친) 1편 1회 이하",
    "meme": 0, "sfx": 0, "template": "none", "captions_only": True, "bgm": "calm", "brand": "잇썸홈",
    "check_flip": {"B6": "짤 0 이어야 통과(검수 매뉴얼 B6 '짤 되풀이 없음'을 이 채널은 '짤 0'으로 뒤집는다)",
                   "sfx": "효과음 0 이어야 통과"},
    "shot_contract": {
        "unit": "자막 토막(1줄) = 컷 1개 — 그 토막 말의 핵심 명사·동작이 화면에 그대로(설계서 '장면 계약은 핵심 명사·동작마다')",
        "cut_sec_median": 1.15, "cut_sec_range": [0.72, 2.32], "sub_sec_median": 0.9, "cut_eq_sub_pct": 94.0,
        "cut_per_min": 43.9, "first_cut_sec": 1.03,
        "from": "C:/숏템_칼카피/homedesignnote/bench_main/bench.json criteria T.cut_sec·T.sub_sec·T.cut_eq_sub (45편)",
        "by_role": "script_frame 5_shot_contract.by_role (역할별 장면 종류 비율)"},
    "sound": {
        "narration": "남성 나레 45/49(judge voice: TTS남 35·사람남 10·여 4)", "speech_rate_cps": 8.32,
        "speech_rate_range": [8.06, 8.74], "speech_rate_from": "asr 49편 공백·기호 뺀 글자 ÷ (첫 낱말 시작~끝 낱말 끝), p10~p90",
        "bgm_present": "50/50(judge bgm.present) — 원본 분위기는 '경쾌' 다수(경쾌·밝음 27/50 내외), 사장님 결정으로 우리 판은 차분",
        "bgm_level_db_below_voice": 14.4, "bgm_level_from": "bench A.openvoice 중앙(말 p90 − 바닥) 14.39dB, 바닥 −21.0 dBFS(50편 중앙)",
        "master_lufs": -7.5, "master_lufs_range": [-21.9, -6.0], "master_from": "bench A.lufs 50편 중앙",
        "bgm_candidates": [
            {"id": "honwaka_puppu", "file": "shopping_shorts/assets/bgm_lib/honwaka_puppu.mp3", "lufs": -14.3, "lra": 3.5,
             "why": "제목 'ほんわか'(포근한) MoppySound — 청취·보컬 유무 미검증"},
            {"id": "before_spring_ends", "file": "shopping_shorts/assets/bgm_lib/before_spring_ends.mp3", "lufs": -14.2, "lra": 3.3,
             "why": "Wang OK 'Before spring ends' — 청취·보컬 유무 미검증"}],
        "sfx": 0,
        "voice_candidates": [
            {"name": "박창수", "voice_id": "tc_6059dad0b83880769a50502f", "why": "남성·'친근하고 편안한'(add_typecast_presets) — 원본 '~더라고요' 체험 말투"},
            {"name": "지훈", "voice_id": "tc_61f0859907085fc68561c9a1", "why": "남성 young_adult·Conversational — 대화체"}],
    },
    "watermark": {"orig": "@Maison_HomeDino / @Home_design_notes", "found": "43/50편",
                  "box_px": "x 373~706·y 1423~1475(25편) / x 384~695·y 1431~1466(16편)",
                  "ink_lum": "평균 밝기 220~255(불투명에 가까운 흰 글자 + 옅은 검정 그림자)",
                  "ours": "brand 층 '잇썸홈' x540 가운데·y1422 줄 칸 54·CcHiMelody 46px(잉크 높이 43 vs 원본 35~52)"},
    "excluded": "[광고] 표기(오른쪽 위, 일부 편) — 우리 판에 안 넣음(광고 아님)",
}


def post_edit(preset_dir: Path) -> dict:
    """엔진이 만든 프리셋에 이 틀의 판단을 얹는다(엔진 build 가 manifest 를 새로 쓰므로 build 뒤 매번)."""
    M = json.loads((preset_dir / "manifest.json").read_text(encoding="utf-8"))
    vs = M["variable_stats"].get(CAP_Y)
    if vs:
        vs["default"] = CAP_Y_MODE
        vs["how"] = "편마다 고르는 값 — 기본 = 50편 bench 띠 최빈 무리 936(13/45편)−9. (이 프리셋 8편 중앙값은 두 무리 사이라 쓰지 않는다)"
    keys = (M.get("rules") or {}).get("keys") or {}
    if "cap_dy" in keys:
        M.setdefault("rules_removed", {})["cap_dy"] = {"was": keys.pop("cap_dy"),
                                                      "why": "전체 화면 틀 — 자막 y 를 창 아래 끝 관계로 묶으면 두 무리 중앙(528, 원본에 없는 자리)으로 고정된다"}
    # 채널명(brand 글) = 변수 — 기본 '잇썸홈', 다른 채널명은 apply(overrides={BRAND: '…'}) 로 덮어쓴다(같은 자리·크기)
    F = json.loads((preset_dir / "frame.json").read_text(encoding="utf-8"))
    for l in F["layers"]:
        if l.get("role") == "brand":
            l["text"] = P.VAR
    (preset_dir / "frame.json").write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    if BRAND not in M["variables"]:
        M["variables"].append(BRAND)
    M["variable_stats"][BRAND] = {"values": {}, "default": "잇썸홈", "range": None,
                                  "how": "채널명 — 기본 잇썸홈(사장님 10-17), 다른 채널명은 overrides 로(원본 워터마크 자리·크기 그대로)"}
    M["roles"] = ROLES
    M["source_kind"] = "제품비하인드"
    M["channel_rules"] = CHANNEL_RULES
    (preset_dir / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return M


def frames() -> dict:
    return {v: json.loads((HAND / f"frame_{v}.json").read_text(encoding="utf-8")) for v in IDS}


def build():
    old = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8")).get("verification") if (PRESET / "manifest.json").exists() else None
    M = L.build(PRESET, SLUG, IDS, frames(), "오푸스 HDN 손질본(자막 크기·번짐·글꼴 렌더 대조로 고침, 10-17)")
    M = post_edit(PRESET)
    if old:   # 직전 loo 결과는 남긴다(설명서가 바뀌었으면 loo 를 다시 돌려 덮는다)
        M["verification"] = {**old, "note": "build 전 loo 결과 — 이 build 뒤 다시 안 돌렸으면 옛 값"}
        (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print("프리셋", PRESET, "변수", M["variables"])


def _cap_top(F: dict) -> int:
    return next(l for l in F["layers"] if l.get("role") == "caption")["y"] + 9


def clean_clip(vid: str, ink_top: int, out: Path, sec: float = 6.0) -> Path:
    """원본 앞 sec 초 — 원본 자막 띠·워터마크 자리를 칠로 가린 재료(우리 층만 보이게)."""
    if out.exists():
        return out
    y0 = max(0, ink_top - 45)
    vf = f"drawbox=x=0:y={y0}:w=1080:h=170:color=0x8a8580:t=fill,drawbox=x=0:y=1400:w=1080:h=100:color=0x8a8580:t=fill"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(MP4 / f"{vid}.mp4"), "-t", str(sec), "-vf", vf,
                    "-c:v", "libx264", "-crf", "16", "-an", str(out)], check=True)
    return out


def short_J(vid: str, src: Path, sec: float = 6.0) -> tuple[Path, list[float]]:
    J = json.loads((ROOT / "channel" / SLUG / "뜯기" / vid / "뜯기.json").read_text(encoding="utf-8"))
    J["source"] = str(src).replace("\\", "/"); J["probe"]["duration"] = sec
    c = J["captions"]; keep = [k for k, (a, b) in enumerate(c["spans"]) if b <= sec]
    one = {i["i"] for i in c["items"] if len(i.get("text") or []) == 1}
    c["spans"] = [c["spans"][k] for k in keep]; c["items"] = [i for i in c["items"] if i["i"] in keep]
    times = [round((a + b) / 2, 2) for k, (a, b) in enumerate(c["spans"]) if keep[k] in one and b - a >= 0.5][:3]
    p = WORK / "loo" / vid / "J6.json"; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(J, ensure_ascii=False), encoding="utf-8")
    return p, times


def measure(vid: str, ours: Path, t: float, cap_top: int) -> dict:
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "check_overlay.py"), str(MP4 / f"{vid}.mp4"), str(ours), str(t),
                        "--cap-top", str(cap_top)],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout)


TOL = {"cap_y0_px": 4, "cap_h_pct": 12, "cap_w_pct": 10, "brand_cx_px": 6, "brand_cy_px": 8}


def judge_row(m: dict) -> dict:
    o, u = m["caption"]["orig"], m["caption"]["ours"]
    bo, bu = m["brand"]["orig"], m["brand"]["ours"]
    row = {"t": m["t"]}
    if o and u:
        row.update(cap_y0=[o["y0"], u["y0"]], cap_h=[o["h"], u["h"]], cap_w=[o["w"], u["w"]], halo=[o.get("halo"), u.get("halo")],
                   ok_y0=abs(o["y0"] - u["y0"]) <= TOL["cap_y0_px"],
                   ok_h=abs(u["h"] - o["h"]) / o["h"] * 100 <= TOL["cap_h_pct"],
                   ok_w=abs(u["w"] - o["w"]) / o["w"] * 100 <= TOL["cap_w_pct"])
    if bo and bu:
        bco, bcu = ((bo["x0"] + bo["x1"]) / 2, (bo["y0"] + bo["y1"]) / 2), ((bu["x0"] + bu["x1"]) / 2, (bu["y0"] + bu["y1"]) / 2)
        row.update(brand_c=[[round(x) for x in bco], [round(x) for x in bcu]], brand_h=[bo["h"], bu["h"]],
                   ok_brand=abs(bco[0] - bcu[0]) <= TOL["brand_cx_px"] and abs(bco[1] - bcu[1]) <= TOL["brand_cy_px"])
    return row


def loo(ids=None):
    ids = ids or IDS
    F_all = frames()
    jobs = []
    for held in ids:
        rest = [x for x in IDS if x != held]
        d = WORK / "loo" / held
        pdir = d / "preset" / STYLE
        Mh = L.build(pdir, SLUG, rest, {k: F_all[k] for k in rest}, "loo")
        Mh = post_edit(pdir)
        pre, Mh = P.load(pdir)
        y_held = F_all[held]["layers"][[l.get("role") for l in F_all[held]["layers"]].index("caption")]["y"]
        F = P.apply(pre, None, {CAP_Y: y_held}, Mh["variable_stats"], None, Mh["rules"])   # 자막 y = 편집자가 고르는 값(뺀 편 값을 준다)
        F_def = P.apply(pre, None, None, Mh["variable_stats"], None, Mh["rules"])           # 기본값만
        fp = d / "frame.json"; fp.write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
        src = clean_clip(held, _cap_top(F_all[held]), d / "clean6.mp4")
        jp, times = short_J(held, src)
        jobs.append((held, fp, jp, times, d, F, F_def, y_held))
    procs = []
    for held, fp, jp, times, d, *_ in jobs:          # 렌더 동시 ≤3
        while len([p for p in procs if p.poll() is None]) >= 3:
            import time; time.sleep(3)
        if not (d / "vid" / "ours.mp4").exists():
            procs.append(subprocess.Popen([sys.executable, "tools/calcopy/frame_video.py", str(fp), str(jp), str(d / "vid")], cwd=str(ROOT),
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for p in procs:
        p.wait()
    res = {}
    for held, fp, jp, times, d, F, F_def, y_held in jobs:
        ours = d / "vid" / "ours.mp4"
        if not ours.exists():
            res[held] = {"failed": "렌더 없음"}; continue
        rows = [judge_row(measure(held, ours, t, _cap_top(F_all[held]))) for t in times]
        cap = next(l for l in F["layers"] if l.get("role") == "caption")
        cap_def = next(l for l in F_def["layers"] if l.get("role") == "caption")
        res[held] = {"times": times, "rows": rows, "font": cap["font"], "size": cap["size"], "y_given": y_held, "y_default": cap_def["y"],
                     "pass": all(r.get("ok_y0", False) and r.get("ok_h", False) and r.get("ok_w", False) and r.get("ok_brand", False) for r in rows) and bool(rows)}
        print(held, "통과" if res[held]["pass"] else "미달", json.dumps(rows, ensure_ascii=False))
    (WORK / "loo" / "loo_hdn.json").write_text(json.dumps({"tol": TOL, "results": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(v.get("pass", False) for v in res.values())
    rows = [x for v in res.values() for x in v.get("rows", [])]
    cap = [x for x in rows if "cap_y0" in x]
    summ = {"at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "tool": "channel/homedesignnote/preset/hdn_preset.py loo",
            "tol": TOL, "videos_all_pass": f"{n}/{len(res)}",
            "items": {"자막 잉크 위 y": f"{sum(x['ok_y0'] for x in cap)}/{len(cap)}", "자막 높이": f"{sum(x['ok_h'] for x in cap)}/{len(cap)}",
                      "자막 폭": f"{sum(x['ok_w'] for x in cap)}/{len(cap)}",
                      "브랜드 중심": f"{sum(x.get('ok_brand', False) for x in rows if 'ok_brand' in x)}/{sum('ok_brand' in x for x in rows)}"},
            "halo_median": {"orig": st.median(x["halo"][0] for x in cap if x["halo"][0] is not None),
                            "ours": st.median(x["halo"][1] for x in cap if x["halo"][1] is not None)},
            "detail": str(WORK / "loo" / "loo_hdn.json")}
    M = json.loads((PRESET / "manifest.json").read_text(encoding="utf-8"))
    M["verification"] = summ
    (PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False))
    print(f"LOO {n}/{len(res)} 편 통과(자막 y0 ±{TOL['cap_y0_px']}px·높이 ±{TOL['cap_h_pct']}%·폭 ±{TOL['cap_w_pct']}%·브랜드 중심 ±{TOL['brand_cx_px']}/{TOL['brand_cy_px']}px)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "loo": lambda: loo(sys.argv[2:] or None)}[cmd]()
