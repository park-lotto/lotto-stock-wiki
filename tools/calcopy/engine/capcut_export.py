"""렌더 계획 → 캡컷 초안(관제 266 · 사장님 10-25 "완성본 고치기에서 캡컷 내보내기, 회원 PC 에서").

입력 = render_bench 완성본 폴더(work/render 아래 timeline.json·자막표.json·parts/·cw/·s_*.wav·o_*.wav·bgm_bed.wav·final.mp4).
출력 = 캡컷 초안 폴더(draft_content.json·draft_meta_info.json + 재료). 회원이 캡컷에서 줄 단위로 고칠 수 있게 겹을 나눈다:

  영상 조각(parts/c##.mp4, 렌더 계획 컷 그대로) · 틀(frame.png) · 짤 · 꾸밈 층 · 댓글 카드
  · 자막(장면꾸미기 층 PNG, 줄 하나 = 칸 하나) · 스티커(자막 층에서 떼어 낸 PNG) · 자막 글자(편집용 캡션, 숨김)
  · 썸네일 카드(맨 앞 2프레임) · '광고' 표시 · 나레(줄별) · 원음(토막별) · 배경음(덕킹 구운 한 줄) · 효과음

★초안 JSON 꼴(머티리얼·세그먼트·골격·보관함)의 주인 = shopping_shorts/capcut_draft.py — 여기서 다시 적지 않고 그 함수를 부른다.
  서버 api_mix_capcut 은 제작소 편집안(plan·beats)을 받고, 이 함수는 엔진 렌더 계획(timeline.json cuts·lines)을 받는다 —
  '무엇을 어느 칸에 놓나'만 다르고 '캡컷이 읽는 꼴'은 한 벌.
★완성본과 같은 그림·같은 시각: 조각·자막 층·틀은 렌더가 만든 파일 그대로, 시각은 timeline.json(프레임 누적)·장면꾸미기 요청 그대로.

캡컷에 못 싣는 것(초안 결과의 warnings 에도 적는다): 창 전환(줌블러·검은 프레임)·흰 번쩍임·자막 등장 움직임·최종 음량 맞춤(리미터).

CLI:
  py -m tools.calcopy.engine.capcut_export export <work> [--doc <대본 폴더>] [--out <폴더>] [--capcut]
  py -m tools.calcopy.engine.capcut_export check <초안 폴더> <work> [--doc <대본 폴더>]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts import capcut_draft as CD      # noqa: E402 — 초안 꼴 주인

W, H, FPS = 1080, 1920, 30
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
NOT_CARRIED = ["창 전환(줌블러·검은 프레임)", "흰 번쩍임", "자막 등장 움직임(정지 그림으로 감)", "최종 음량 맞춤(리미터) — 소리가 완성본보다 작을 수 있다"]


# ── 읽기 ────────────────────────────────────────────────────────────────
def _j(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _wh(p: Path) -> tuple[int, int]:
    if Path(p).suffix.lower() in IMG_EXT:
        from PIL import Image
        with Image.open(p) as im:
            return im.size
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def render_dir(work: Path) -> Path:
    work = Path(work)
    return work if (work / "timeline.json").exists() else work / "render"


def guess_doc(work: Path) -> Path | None:
    """완성본 폴더(C:/숏템_칼카피/<채널>/<편>/<판>) → 대본 폴더(channel/<채널>/<편>/<판>). 없으면 None."""
    work = Path(work)
    if work.name == "render":
        work = work.parent
    d = ROOT / "channel" / work.parent.parent.name / work.parent.name / work.name
    return d if (d / "대본.json").exists() else None


def load(work: Path) -> dict:
    """완성본 폴더 읽기 — 렌더가 남긴 계획·배치·장면꾸미기 요청."""
    R = render_dir(work)
    need = ["timeline.json", "자막표.json", "render_info.json", "final.mp4", "frame.png", "parts", "cw/scene-style-request.json", "cw/scene-style-layers.json"]
    miss = [n for n in need if not (R / n).exists()]
    if miss:
        raise FileNotFoundError(f"render_bench 완성본 폴더가 아니다({R}) — 없음: {miss}")
    # 렌더 도중이면 읽지 않는다 — render_info.json 은 render_bench 가 맨 끝에 쓴다. 그보다 새 재료가 있으면 렌더가 다시 돌고 있는 것
    #   (10-26 실측: 이영애 편을 렌더 중에 읽어 컷 18/19·길이 27.83/28.10 이 섞였다 — check 가 잡음)
    t_info = (R / "render_info.json").stat().st_mtime
    newer = [n for n in ("timeline.json", "자막표.json", "caption_timeline.json", "final.mp4", "cw/scene-style-request.json", "parts/list.txt")
             if (R / n).exists() and (R / n).stat().st_mtime > t_info + 1]
    if newer:
        raise RuntimeError(f"렌더가 아직 도는 중(render_info.json 보다 새 파일: {newer}) — 렌더가 끝난 뒤 다시")
    req = _j(R / "cw/scene-style-request.json")
    return {"R": R, "T": _j(R / "timeline.json"), "tab": _j(R / "자막표.json"), "info": _j(R / "render_info.json"),
            "snapshot": req["snapshot"], "scenes": req["context"]["scenes"], "layers": _j(R / "cw/scene-style-layers.json")}


# ── 자리 ────────────────────────────────────────────────────────────────
def place(mw: int, mh: int, box: tuple[float, float, float, float]) -> tuple[float, float, float]:
    """재료(mw×mh)를 완성본 칸 box(x,y,w,h, 크기 안 넘게 맞춤)에 앉히는 캡컷 clip (scale, tx, ty).
    캡컷은 재료를 화면에 맞춰(fit) 가운데 둔다 → 배율 = 원하는 크기 ÷ 맞춘 크기. 이동 단위 = 캔버스 절반, 위가 +(scene_style.capcut_base_y 와 같은 약속)."""
    x, y, w, h = box
    s0 = min(W / mw, H / mh)
    s = min(w / mw, h / mh)
    return round(s / s0, 6), round(((x + w / 2) - W / 2) / (W / 2), 6), round(-((y + h / 2) - H / 2) / (H / 2), 6)


# ── 스티커 떼기 ──────────────────────────────────────────────────────────
def _pack_stickers(row: dict) -> list:
    """자막팩이 자막 층에 같이 그린 스티커(꾸밈 층·짤로 따로 그린 것은 뺀다 — render_bench.fx_effects·meme_overlays 와 같은 가름)."""
    from tools.calcopy.hybrid import render_bench as RB
    out = []
    for s in row.get("stickers") or []:
        drawn_apart = s.get("site") in ("detected", "fixed") and (s.get("kind") in RB.FX_STICKERS or s.get("kind") == "meme")
        if not drawn_apart:
            out.append(s)
    return out


SAME_PX = 0.002      # 다시 그린 층이 완성본 층과 '같다' = 다른 픽셀 0.2% 이하(글자 테두리 반올림 정도)


def _px_diff(a_png: Path, b_png: Path):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(a_png).convert("RGBA")).astype(np.int16)
    b = np.asarray(Image.open(b_png).convert("RGBA")).astype(np.int16)
    return a, np.abs(a - b).max(axis=2) > 24


def split_stickers(D: dict, idxs: list[int], tmp: Path, log=print, warnings: list | None = None) -> dict:
    """스티커가 있는 장면만 장면꾸미기 주인(scene_style.render_layer_one)으로 두 번 다시 그려 자막·스티커를 가른다.
      ① 같은 시간표로 다시 그린 층 = 완성본 층(cw/)인지 먼저 잰다 — 렌더러·자막팩이 그 사이 바뀌었으면 가르지 않는다(완성본과 다른 그림을 내보내지 않게)
      ② 스티커 뺀 시간표로 그린 층 = 자막만, 스티커 = 완성본 층에서 자막만 층과 달라진 픽셀.
    반환 {장면: (자막만 png, 스티커 png)}. 못 가르면 그 장면은 빠진다(자막 층에 스티커가 붙은 채로 간다) — warnings 에 적는다."""
    if not idxs:
        return {}
    import numpy as np
    from PIL import Image
    from shopping_shorts import scene_style
    tl = _j(D["R"] / "caption_timeline.json")
    tl0 = json.loads(json.dumps(tl))
    for b in tl0:
        for m in b.get("caption_marks") or []:
            m.pop("stickers", None)
            m.pop("sticker", None)
    W_ = warnings if warnings is not None else []
    out = {}
    for i in idxs:
        orig = D["R"] / "cw" / D["layers"][i]["file"]
        try:
            same = scene_style.render_layer_one(tl, D["snapshot"], tmp / f"same_{i:02d}", i)
            _, d_same = _px_diff(orig, same)
            if d_same.mean() > SAME_PX:
                W_.append(f"장면 {i} 스티커 못 뗌 — 다시 그린 층이 완성본 층과 {d_same.mean():.1%} 다름(렌더러·자막팩이 바뀜)")
                continue
            cap = scene_style.render_layer_one(tl0, D["snapshot"], tmp / f"cap_{i:02d}", i)
        except Exception as e:      # noqa: BLE001 — 스티커를 못 떼도 초안은 나간다(자막 층에 붙은 채) — 조용히 넘기지 않고 적는다
            W_.append(f"장면 {i} 스티커 못 뗌 — 다시 그리기 실패: {e}")
            continue
        a, diff = _px_diff(orig, cap)
        st = np.zeros_like(a, dtype=np.uint8)
        st[diff] = a[diff].astype(np.uint8)
        sp = tmp / f"sticker_{i:02d}.png"
        Image.fromarray(st, "RGBA").save(sp)
        out[i] = (Path(cap), sp)
        log(f"[스티커] 장면 {i} '{D['scenes'][i].get('caption')}' — 떼어 낸 픽셀 {int(diff.sum())}")
    return out


def _full_canvas(src_png: Path, xy: tuple[int, int], out: Path) -> Path:
    from PIL import Image
    cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im = Image.open(src_png).convert("RGBA")
    cv.alpha_composite(im, (max(0, int(xy[0])), max(0, int(xy[1]))))
    cv.save(out)
    return out


# ── 초안 만들기 ──────────────────────────────────────────────────────────
class _Draft:
    """트랙·머티리얼 모으기 — 세그먼트·머티리얼 꼴은 capcut_draft 함수 그대로."""

    def __init__(self, proj: Path):
        self.proj = proj
        self.mats = {k: [] for k in ("videos", "audios", "texts", "speeds", "beats", "sound_channel_mappings", "vocal_separations",
                                     "placeholder_infos", "material_animations", "canvases")}
        self.tracks = []
        self.media = []
        self.copied = {}

    def bring(self, src: Path, name: str, library: bool = True) -> str:
        """재료를 초안 폴더로 복사 → 캡컷이 볼 절대경로(캡컷은 상대경로를 못 읽는다 — capcut_draft 07-20 실측)."""
        src = Path(src)
        if str(src) in self.copied:
            return self.copied[str(src)]
        dst = self.proj / name
        shutil.copy(src, dst)
        p = dst.resolve().as_posix()
        self.copied[str(src)] = p
        if library:
            is_img = dst.suffix.lower() in IMG_EXT
            is_aud = dst.suffix.lower() in CD._AUDIO_EXT
            wh = (0, 0) if is_aud else _wh(dst)
            self.media.append({"path": p, "name": name, "dur": 5.0 if is_img else _dur(dst), "w": wh[0], "h": wh[1]})
        return p

    def track(self, kind: str, name: str, render_index: int = 0, hidden: bool = False) -> dict:
        t = {"id": CD._uid(), "type": kind, "attribute": 1 if hidden else 0, "flag": 0, "name": name, "is_default_name": False,
             "segments": [], "_ri": render_index}
        self.tracks.append(t)
        return t

    def visual(self, tr: dict, path: str, t0: float, dur: float, *, src_dur: float | None = None, clip=None, video: bool = True):
        """영상·사진 한 칸. 사진은 capcut_draft._photo_material, 영상은 _video_material(+배속 등 동반 소재 — 서버와 같은 묶음)."""
        if dur <= 0:
            return None
        if Path(path).suffix.lower() in IMG_EXT:
            m = CD._photo_material(path, Path(path).name, W, H)
            refs = []
        else:
            vd = src_dur if src_dur is not None else dur
            m = CD._video_material(path, Path(path).name, CD._us(max(vd, dur)), W, H)
            m["has_audio"] = False
            sp, ca, sc, ph, vs = CD._speed(), CD._canvas(), CD._sound_channel_mapping(), CD._placeholder_info(), CD._vocal_separation()
            for x, k in ((sp, "speeds"), (ca, "canvases"), (sc, "sound_channel_mappings"), (ph, "placeholder_infos"), (vs, "vocal_separations")):
                self.mats[k].append(x)
            refs = [sp["id"], ca["id"], sc["id"], ph["id"], vs["id"]]
        self.mats["videos"].append(m)
        seg = CD._base_segment(m["id"], CD._us(t0), CD._us(t0 + dur) - CD._us(t0), source_start=0, render_index=0, volume=0.0, extra_refs=refs)
        seg["track_render_index"] = tr["_ri"]
        if clip:
            sc_, tx, ty = clip
            seg["clip"]["scale"] = {"x": sc_, "y": sc_}
            seg["clip"]["transform"] = {"x": tx, "y": ty}
        tr["segments"].append(seg)
        return seg

    def sound(self, tr: dict, path: str, t0: float, dur: float, volume: float, name: str):
        if dur <= 0:
            return None
        sp, ph, be, sc, vs = CD._speed(), CD._placeholder_info(), CD._beat_material(), CD._sound_channel_mapping(), CD._vocal_separation()
        for x, k in ((sp, "speeds"), (ph, "placeholder_infos"), (be, "beats"), (sc, "sound_channel_mappings"), (vs, "vocal_separations")):
            self.mats[k].append(x)
        m = CD._audio_material(path, name, CD._us(dur))
        self.mats["audios"].append(m)
        seg = CD._base_segment(m["id"], CD._us(t0), CD._us(dur), source_start=0, render_index=0, volume=round(volume, 4),
                               extra_refs=[sp["id"], ph["id"], be["id"], sc["id"], vs["id"]])
        tr["segments"].append(seg)
        return seg

    def caption(self, tr: dict, text: str, t0: float, t1: float):
        anim = CD._sticker_animation()
        self.mats["material_animations"].append(anim)
        tm = CD._text_material(text, CD._DEFAULT_FONT, None)
        self.mats["texts"].append(tm)
        seg = CD._base_segment(tm["id"], CD._us(t0), CD._us(t1) - CD._us(t0), source_timerange=False, render_index=0, extra_refs=[anim["id"]])
        seg["track_render_index"] = tr["_ri"]
        tr["segments"].append(seg)

    def write(self, name: str, total: float) -> dict:
        draft = CD._skeleton(name, W, H, CD._us(total))
        draft["materials"].update(self.mats)
        draft["tracks"] = [{k: v for k, v in t.items() if k != "_ri"} for t in self.tracks if t["segments"]]
        meta = CD.build_meta(name, self.proj.resolve().as_posix(), draft["duration"], media=self.media)
        (self.proj / "draft_content.json").write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        (self.proj / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return draft


def capcut_drafts_root() -> Path | None:
    """이 PC 캡컷 초안 폴더(설치 기본 위치). 없으면 None."""
    la = os.environ.get("LOCALAPPDATA")
    p = Path(la) / "CapCut/User Data/Projects/com.lveditor.draft" if la else None
    return p if p and p.exists() else None


def export(work_dir, out_root=None, doc=None, project_name: str | None = None, log=print) -> Path:
    """render_bench 완성본 폴더 → 캡컷 초안 폴더 경로.
    out_root: 초안 폴더를 만들 곳(기본 <work>/capcut). 캡컷 초안 폴더(capcut_drafts_root)를 주면 캡컷 목록에 바로 뜬다.
    doc: 대본 폴더(썸네일 카드) — 없으면 guess_doc."""
    from tools.calcopy.hybrid import render_bench as RB
    from tools.calcopy.hybrid import styles as ST
    from tools.calcopy.hybrid.common import lufs
    D = load(work_dir)
    R, T, tab, info = D["R"], D["T"], D["tab"], D["info"]
    work = R.parent
    doc = Path(doc) if doc else guess_doc(work)
    st = ST.load(info["version"])
    warnings = list(NOT_CARRIED)
    name = CD.safe_project_name(project_name or f"{work.parent.name} {work.name} {datetime.now().strftime('%H%M')}")
    out_root = Path(out_root) if out_root else work / "capcut"
    proj = out_root / name
    shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True)
    tmp = proj / "_work"
    tmp.mkdir()
    G = _Draft(proj)

    # 1) 영상 조각 — 렌더 계획 컷(parts/c##.mp4) 그대로, 시각은 프레임 누적(완성본과 같은 자리)
    x, y, ww, wh = RB.frame_window(st["frame"])
    tv = G.track("video", "영상 조각", 0)
    f = 0
    for k, c in enumerate(T["cuts"]):
        p = R / "parts" / f"c{k:02d}.mp4"
        n = int(c.get("frames") or (round(c["t1"] * FPS) - round(c["t0"] * FPS)))
        mw, mh = _wh(p)
        G.visual(tv, G.bring(p, f"cut_{k:02d}_{c['line']}.mp4"), f / FPS, n / FPS, src_dur=_dur(p), clip=place(mw, mh, (x, y, ww, wh)))
        f += n
    end = f / FPS

    # 2) 틀
    tf = G.track("video", "틀", 1)
    G.visual(tf, G.bring(R / "frame.png", "frame.png"), 0, end)
    if tab.get("segments"):
        warnings.append("틀이 구간마다 바뀌는 편 — 첫 틀(frame.png) 하나로만 감")

    # 3) 짤 · 꾸밈 층 · 댓글 카드
    tm = G.track("video", "짤", 2)
    for j, m in enumerate(tab.get("memes") or []):
        src = Path(m["src"])
        if not src.is_absolute():
            src = ROOT / src
        if not src.exists():
            warnings.append(f"짤 파일 없음: {m['src']}")
            continue
        mw, mh = _wh(src)
        G.visual(tm, G.bring(src, f"meme_{j:02d}{src.suffix.lower()}"), m["t0"], m["len"], src_dur=None if src.suffix.lower() in IMG_EXT else _dur(src),
                 clip=place(mw, mh, tuple(m["box"])))
    fx = RB.fx_effects(tab)
    if fx and (R / "fx_layer.mov").exists():
        f0 = max(0, min(round(e["T"][0] * FPS) for e in fx))
        f1 = min(f, max(round(e["T"][1] * FPS) for e in fx))
        G.visual(G.track("video", "꾸밈", 3), G.bring(R / "fx_layer.mov", "fx_layer.mov"), f0 / FPS, (f1 - f0) / FPS)
        warnings.append("꾸밈 층 = 투명 mov(qtrle) — 캡컷이 투명을 못 읽으면 검게 보일 수 있다(미확인)")
    C = tab.get("comment")
    if C and (R / "comment.png").exists():
        from PIL import Image
        cw_, ch_ = Image.open(R / "comment.png").size
        F = st["frame"]
        pc = _full_canvas(R / "comment.png", ((W - cw_) // 2, F["comment"]["bottom"] - ch_), tmp / "comment_full.png")
        G.visual(G.track("video", "댓글 카드", 4), G.bring(pc, "comment_card.png"), C["t0"], C["t1"] - C["t0"])

    # 4) 자막(장면꾸미기 층) · 스티커 · 자막 글자(편집용)
    rows, scenes, layers = tab["rows"], D["scenes"], D["layers"]
    same = len(rows) == len(scenes) == len(layers) and all(" ".join(r["text"].split()) == " ".join((s.get("caption") or "").split()) for r, s in zip(rows, scenes))
    if not same:
        warnings.append(f"자막표 줄({len(rows)})과 장면꾸미기 장면({len(scenes)})이 안 맞아 스티커를 안 뗌")
    stk = split_stickers(D, [i for i, r in enumerate(rows) if _pack_stickers(r)] if same else [], tmp, log, warnings)
    tc = G.track("video", "자막", 5)
    ts = G.track("video", "스티커", 6)
    tt = G.track("text", "자막 글자(편집용·숨김)", 7, hidden=True)
    for i, s in enumerate(scenes):
        a, b = float(s["start"]), min(float(s["end"]), end)
        cap_png = stk[i][0] if i in stk else R / "cw" / layers[i]["file"]
        G.visual(tc, G.bring(cap_png, f"caption_{i:02d}.png"), a, b - a)
        if i in stk:
            G.visual(ts, G.bring(stk[i][1], f"sticker_{i:02d}.png"), a, b - a)
        G.caption(tt, s.get("caption") or "", a, b)

    # 5) 썸네일 카드(맨 앞 2프레임) · '광고' 표시(모든 프레임 — 주인 ad_mark)
    from tools.calcopy.engine import ad_mark
    from tools.calcopy.hybrid import thumb as TH
    if doc and (doc / "썸네일.json").exists():
        pk = _j(doc / "썸네일.json").get("pick")
        jpg = doc / "thumb" / f"{pk}.jpg"
        if pk and jpg.exists():
            from PIL import Image
            Image.open(jpg).convert("RGB").resize((W, H)).save(tmp / "thumb_card.jpg", quality=92)
            G.visual(G.track("video", "썸네일 카드", 8), G.bring(tmp / "thumb_card.jpg", "thumb_card.jpg"), 0, TH.THUMB_FRAMES / FPS)
    bp, mg = ad_mark.badge(W, tmp / "ad_badge.png")
    from PIL import Image
    bw = Image.open(bp).size[0]
    G.visual(G.track("video", "광고 표시", 9), G.bring(_full_canvas(bp, (W - bw - mg, mg), tmp / "ad_full.png"), "ad_mark.png"), 0, end)

    # 6) 소리 — 렌더 audio() 와 같은 재료·같은 크기. 최종 음량 맞춤은 최고점이 넘지 않는 만큼만(캡컷엔 리미터가 없다)
    A = info.get("audio") or {}
    rawI, rawTP = lufs(R / "mix_raw.wav") if (R / "mix_raw.wav").exists() else (float("nan"), float("nan"))
    L = st["loudness"]
    mgain = 0.0 if math.isnan(rawI) else min(L["lufs"] - rawI, L["tp"] - rawTP)
    if not math.isnan(rawI) and mgain < L["lufs"] - rawI - 0.5:
        warnings.append(f"전체 소리 +{mgain:.1f}dB 만 올림(완성본은 +{L['lufs'] - rawI:.1f}dB + 리미터) — 캡컷에서 내보낼 때 음량 맞춤 권장")
    k = 10 ** (mgain / 20)
    tn = G.track("audio", "나레", 0)
    for lid, (t0, _t1) in T["lines"].items():
        p = R / f"s_{lid}.wav"
        if p.exists():
            d = min(_dur(p), end - t0)
            G.sound(tn, G.bring(p, f"narr_{lid}.wav"), t0, d, 1.0 * k, f"나레 {lid}")
    to = G.track("audio", "원음", 0)
    og = 10 ** (float(A.get("orig_gain") or 0.0) / 20)
    for j, o in enumerate(T.get("opos") or []):
        p = R / f"o_{j}.wav"
        if p.exists():
            G.sound(to, G.bring(p, f"orig_{o['line']}_{j}.wav"), o["t0"], min(_dur(p), end - o["t0"]), og * k, f"원음 {o['line']}")
    tb = G.track("audio", "배경음", 0)
    if (R / "bgm_bed.wav").exists():
        G.sound(tb, G.bring(R / "bgm_bed.wav", "bgm.wav"), 0, min(_dur(R / "bgm_bed.wav"), end), 1.0 * k, "배경음")
    tx = G.track("audio", "효과음", 0)
    SF = st.get("sfx_files") or {}
    for j, e in enumerate(tab.get("sfx") or []):
        p = RB.SFX_DIR / SF.get(e["kind"], "")
        if e["kind"] in SF and p.exists():
            G.sound(tx, G.bring(p, f"sfx_{j:02d}_{e['kind']}{p.suffix}"), e["t"], min(_dur(p), end - e["t"]),
                    10 ** (float(SF.get("gain_db", -8)) / 20) * k, f"효과음 {e['kind']}")
        else:
            warnings.append(f"효과음 파일 없음: {e['kind']}")

    # 7) 보관함 참고용 완성본(타임라인엔 안 올림 — 소리 두 번)
    G.bring(R / "final.mp4", "final_참고용.mp4")
    draft = G.write(name, end)
    shutil.rmtree(tmp, ignore_errors=True)
    rep = {"made_by": "tools/calcopy/engine/capcut_export.py", "work": str(work), "doc": str(doc) if doc else None, "project": name,
           "duration": end, "tracks": [(t["name"], t["type"], len(t["segments"])) for t in draft["tracks"]],
           "master_gain_db": round(mgain, 2), "stickers_split": sorted(stk), "warnings": warnings}
    (proj / "export_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"캡컷 초안 → {proj} · {end:.3f}초 · 트랙 {len(draft['tracks'])}")
    for w_ in warnings:
        log(f"  [안 감·주의] {w_}")
    return proj


# ── 시험 ────────────────────────────────────────────────────────────────
def script_caps(doc: Path) -> list[str]:
    """대본.json 의 자막 줄(나레 caps·원음 caps_rel) 순서대로."""
    out = []
    for l in _j(doc / "대본.json")["lines"]:
        if l.get("kind") == "orig":
            out += [c[0] for c in l.get("caps_rel") or []]
        else:
            out += [c["text"] for c in l.get("caps") or []]
    return out


def check(draft_dir, work_dir, doc=None) -> dict:
    """초안이 캡컷 꼴로 읽히는지 + 완성본과 같은지. 반환 {"ok", "bad": [...], "facts": {...}}."""
    proj = Path(draft_dir)
    bad = []
    d = _j(proj / "draft_content.json")
    meta = _j(proj / "draft_meta_info.json")
    D = load(work_dir)
    doc = Path(doc) if doc else guess_doc(D["R"].parent)
    for k in ("id", "duration", "canvas_config", "materials", "tracks", "fps"):
        if k not in d:
            bad.append(f"초안 골격 키 없음: {k}")
    ids = {m["id"]: (kind, m) for kind, ms in d["materials"].items() if isinstance(ms, list) for m in ms if isinstance(m, dict) and "id" in m}
    for t in d["tracks"]:
        for s in t["segments"]:
            if s["material_id"] not in ids:
                bad.append(f"[{t['name']}] 세그먼트 머티리얼 없음")
            for r in s.get("extra_material_refs") or []:
                if r not in ids:
                    bad.append(f"[{t['name']}] 동반 소재 없음 {r}")
            m = ids.get(s["material_id"], (None, {}))[1]
            if m.get("path") and not Path(m["path"]).exists():
                bad.append(f"[{t['name']}] 재료 파일 없음 {m['path']}")
    for e in meta["draft_materials"][0]["value"]:
        if not Path(e["file_Path"]).exists():
            bad.append(f"보관함 파일 없음 {e['file_Path']}")
    final = _dur(D["R"] / "final.mp4")
    dur = d["duration"] / 1e6
    if abs(dur - final) > 0.1:
        bad.append(f"길이 {dur:.3f} ≠ 완성본 {final:.3f}")
    ends = {t["name"]: max((s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / 1e6 for s in t["segments"]) for t in d["tracks"]}
    for n, e in ends.items():
        if e > dur + 1 / FPS:
            bad.append(f"[{n}] 끝 {e:.3f} > 초안 길이 {dur:.3f}")
    by = {t["name"]: t for t in d["tracks"]}
    v = by.get("영상 조각")
    if not v:
        bad.append("영상 조각 트랙 없음")
    else:
        acc = 0
        for s in v["segments"]:
            tr = s["target_timerange"]
            if abs(tr["start"] - acc) > 1:
                bad.append(f"영상 조각 틈/겹침 @ {tr['start'] / 1e6:.3f}")
            acc = tr["start"] + tr["duration"]
        if len(v["segments"]) != len(D["T"]["cuts"]):
            bad.append(f"영상 조각 {len(v['segments'])} ≠ 계획 컷 {len(D['T']['cuts'])}")
        if abs(acc / 1e6 - final) > 0.1:
            bad.append(f"영상 조각 끝 {acc / 1e6:.3f} ≠ 완성본 {final:.3f}")
    texts = [json.loads(ids[s["material_id"]][1]["content"])["text"] for s in (by.get("자막 글자(편집용·숨김)") or {"segments": []})["segments"]]
    rows = [r["text"] for r in D["tab"]["rows"]]
    if texts != rows:
        bad.append(f"자막 글자 ≠ 자막표: {[(a, b) for a, b in zip(texts, rows) if a != b][:3]} (수 {len(texts)}/{len(rows)})")
    sc = script_caps(doc) if doc else None
    norm = lambda xs: [" ".join(x.split()) for x in xs]
    if sc is not None and norm(texts) != norm(sc):
        bad.append(f"자막 글자 ≠ 대본: {[(a, b) for a, b in zip(norm(texts), norm(sc)) if a != b][:3]} (수 {len(texts)}/{len(sc)})")
    cap = by.get("자막")
    if not cap or len(cap["segments"]) != len(D["scenes"]):
        bad.append(f"자막 층 {len(cap['segments']) if cap else 0} ≠ 장면 {len(D['scenes'])}")
    narr = sum(1 for lid in D["T"]["lines"] if (D["R"] / f"s_{lid}.wav").exists())
    if len((by.get("나레") or {"segments": []})["segments"]) != narr:
        bad.append("나레 줄 수가 렌더와 다름")
    facts = {"duration": round(dur, 3), "final": round(final, 3), "tracks": [(t["name"], t["type"], len(t["segments"])) for t in d["tracks"]],
             "captions": len(texts), "script_caps": len(sc) if sc is not None else None, "library": len(meta["draft_materials"][0]["value"])}
    return {"ok": not bad, "bad": bad, "facts": facts}


def sim_frame(draft_dir, t: float):
    """초안의 화면 겹을 캡컷 약속대로 겹쳐 t초 한 장(RGB). 약속 = 재료를 화면에 맞춰(fit) 가운데 → clip.scale 배 → transform(캔버스 절반, 위 +).
    숨긴 트랙(attribute 1)은 뺀다. 캡컷 앱을 대신하는 게 아니라 '초안 숫자가 완성본 자리를 가리키나'를 재는 자."""
    from PIL import Image
    import io
    proj = Path(draft_dir)
    d = _j(proj / "draft_content.json")
    mats = {m["id"]: m for m in d["materials"]["videos"]}
    cv = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    us = round(t * 1e6)
    vis = [tr for tr in d["tracks"] if tr["type"] == "video" and not tr.get("attribute")]
    vis.sort(key=lambda tr: tr["segments"][0].get("track_render_index", 0) if tr["segments"] else 0)
    for tr in vis:
        for s in tr["segments"]:
            a, n = s["target_timerange"]["start"], s["target_timerange"]["duration"]
            if not a <= us < a + n:
                continue
            m = mats[s["material_id"]]
            if m["type"] == "photo":
                im = Image.open(m["path"]).convert("RGBA")
            else:
                at = (s["source_timerange"]["start"] + (us - a)) / 1e6
                r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.4f}", "-i", m["path"], "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                                   capture_output=True)
                im = Image.open(io.BytesIO(r.stdout)).convert("RGBA")
            mw, mh = im.size
            k = min(W / mw, H / mh) * float(s["clip"]["scale"]["x"])
            im = im.resize((max(1, round(mw * k)), max(1, round(mh * k))))
            cx = W / 2 + float(s["clip"]["transform"]["x"]) * W / 2
            cy = H / 2 - float(s["clip"]["transform"]["y"]) * H / 2
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer.paste(im, (round(cx - im.size[0] / 2), round(cy - im.size[1] / 2)))
            if float(s["clip"].get("alpha", 1.0)) < 1:
                layer.putalpha(layer.getchannel("A").point(lambda v: round(v * float(s["clip"]["alpha"]))))
            cv.alpha_composite(layer)
            break
    return cv.convert("RGB")


def frames_check(draft_dir, work_dir, out: Path | None = None, n: int = 8) -> dict:
    """완성본과 초안 겹친 그림을 줄 끝 근처(자막 등장 움직임이 끝난 때) n 곳에서 대조 — 픽셀 평균 차이(0~255)와 나란히 시트."""
    import numpy as np
    from PIL import Image
    D = load(work_dir)
    sc = D["scenes"]
    pick = [sc[round(i * (len(sc) - 1) / max(1, n - 1))] for i in range(min(n, len(sc)))]
    fend = _dur(D["R"] / "final.mp4") - 0.1      # 마지막 장면 끝이 완성본 끝보다 길 수 있다(10-26 최은경 편)
    ts = [round(min(fend, max(float(s["start"]) + 0.5, float(s["end"]) - 0.12)), 3) for s in pick]
    rows, res = [], []
    for t in ts:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(D["R"] / "final.mp4"), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        import io
        fin = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        sim = sim_frame(draft_dir, t)
        dif = float(np.abs(np.asarray(fin, dtype=np.int16) - np.asarray(sim, dtype=np.int16)).mean())
        res.append({"t": t, "mean_diff": round(dif, 2)})
        rows.append(Image.fromarray(np.hstack([np.asarray(fin), np.asarray(sim)])).resize((540, 480)))
    if out:
        sheet = Image.new("RGB", (540 * min(4, len(rows)), 480 * math.ceil(len(rows) / 4)))
        for i, im in enumerate(rows):
            sheet.paste(im, ((i % 4) * 540, (i // 4) * 480))
        sheet.save(out, quality=85)
    return {"frames": res, "worst": max(x["mean_diff"] for x in res), "sheet": str(out) if out else None}


def main():
    ap = argparse.ArgumentParser(description="렌더 계획 → 캡컷 초안")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("work"); e.add_argument("--doc"); e.add_argument("--out"); e.add_argument("--name")
    e.add_argument("--capcut", action="store_true", help="이 PC 캡컷 초안 폴더에 바로 만든다(캡컷 목록에 뜬다)")
    c = sub.add_parser("check"); c.add_argument("draft"); c.add_argument("work"); c.add_argument("--doc")
    fr = sub.add_parser("frames", help="완성본 vs 초안 겹친 그림 대조 시트"); fr.add_argument("draft"); fr.add_argument("work"); fr.add_argument("--out"); fr.add_argument("-n", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "frames":
        print(json.dumps(frames_check(a.draft, a.work, Path(a.out) if a.out else Path(a.draft) / "frames_check.jpg", a.n), ensure_ascii=False, indent=1))
        return
    if a.cmd == "export":
        out = a.out
        if a.capcut:
            out = capcut_drafts_root()
            if not out:
                sys.exit("캡컷 초안 폴더를 못 찾았다(%LOCALAPPDATA%/CapCut/User Data/Projects/com.lveditor.draft) — --out 으로 주세요")
        p = export(a.work, out, a.doc, a.name)
        r = check(p, a.work, a.doc)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        sys.exit(0 if r["ok"] else 1)
    r = check(a.draft, a.work, a.doc)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
