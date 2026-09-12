"""manifest.json(볼케이노 재료) → 우리 렌더러(shopping_shorts.video_assemble.assemble)로 재조립

뼈대(대본·컷 시각·이미지·나레이션·효과음 배치)는 볼케이노 것을 그대로 쓰고,
화면(틀·머리카피·자막 폰트·색·위치·전환)은 우리 숏템메이커 프리셋으로 그린다.

원리(코드 수정 없이 기존 배관만 쓴다):
  · 이미지·밈 → 정지 mp4(1080×1920, 흐린 배경 + 원본 contain)로 한 번 굽고 소스로 넣는다
    (_render_mix는 mp4 소스만 -ss/-t로 자른다. PNG는 못 받는다)
  · 컷 하나 = 비트 하나. tts_path·primary(start 0~dur)를 미리 채워 TTS·자동 컷 선택을 건너뛴다
  · 컷별 자막 색(YELLOW/RED/PINK/ORANGE)은 highlight_rules(줄 전체를 키워드로)로 준다.
    WHITE 컷은 프리셋의 기본 자막색을 그대로 쓴다 = "우리 템플릿 색"
  · 효과음은 볼케이노가 컷마다 배치한 파일을 first 타점으로 그대로 얹는다

쓰는 법:
  py tools/volcano_bridge/build.py <manifest.json> --layout sul_even [--channel 채널명] [-o out.mp4]
  --list-layouts 로 프리셋 목록을 본다
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 볼케이노 색 이름 → 우리 렌더러 hex. WHITE는 넣지 않는다(프리셋 기본색이 우리 템플릿 색).
COLOR_HEX = {"YELLOW": "#FFFF00", "RED": "#FF0000", "PINK": "#FEDEFE", "ORANGE": "#F76C0D"}
_STILL_PAD = 1.5   # 정지 mp4 여유(초) — 슬로모/프리즈 기계가 안 돌게 넉넉히


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("ffmpeg 실패:\n" + " ".join(cmd) + "\n" + r.stderr[-1500:])


def make_still(src_png: str, out_mp4: Path, seconds: float, *, plain_bg: str | None = None,
               width: int = 1080, top_pct: float = 48.0):
    """PNG → 1080×1920 정지 mp4.

    ★그림은 화면 **아래쪽 띠**에 놓는다(top_pct 부터). 우리 프리셋의 머리카피(37~63%)·자막(41~63%)
    자리가 화면 한가운데라, 그림을 정중앙에 두면 제목·자막·그림이 한 곳에 몰린다
    (2026-09-12 사장님 캡처: 밈 위에 머리카피와 빨간 자막이 겹침). 위쪽은 흐린 배경(사진) 또는
    단색(밈)으로 비워 글자 자리를 준다.
    plain_bg 를 주면(밈처럼 흐림이 어색한 그림) 그 단색 위에 놓는다."""
    if out_mp4.exists():
        return out_mp4
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    y = int(1920 * top_pct / 100)
    if plain_bg:
        vf = (f"scale={width}:-2:flags=lanczos,pad=1080:1920:(ow-iw)/2:{y}:color={plain_bg},"
              "format=yuv420p")
    else:
        vf = ("split[a][b];"
              "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:2[bg];"
              f"[b]scale={width}:-2:flags=lanczos[fg];"
              f"[bg][fg]overlay=(W-w)/2:{y},format=yuv420p")
    _run(["ffmpeg", "-y", "-loop", "1", "-t", f"{seconds:.3f}", "-i", src_png,
          "-filter_complex", vf, "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
          "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(out_mp4)])
    return out_mp4


def norm_wav(src_wav: str, out_wav: Path, lufs: float = -16.0):
    """나레이션 wav 음량 정규화. 볼케이노 TTS 원음은 -30 LUFS 근처라(실측) 그대로 넣으면
    완성본이 -29 LUFS로 나온다(볼케이노 완성본 -15.6). 렌더러는 정규화를 안 하므로 여기서 한다."""
    if out_wav.exists():
        return out_wav
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-i", src_wav, "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
          "-ar", "44100", str(out_wav)])
    return out_wav


def build(manifest: dict, layout: str, channel: str, out_path: Path, *, sfx: bool = True,
          sfx_volume: int = 35, narr_lufs: float = -16.0):
    from shopping_shorts import deco_frame
    from shopping_shorts.video_assemble import assemble

    if layout not in deco_frame.PRESETS:
        raise SystemExit(f"없는 프리셋: {layout} (--list-layouts 로 확인)")
    preset = deco_frame.PRESETS[layout]
    if "headcopy" not in preset or "caption" not in preset:
        raise SystemExit(f"프리셋 {layout} 에 headcopy/caption 세트가 없다")

    work = Path(manifest["workdir"]) / "bridge"
    src_dir = work / "src"

    # ── 1) 소스: 이미지 슬롯·밈 → 정지 mp4 ─────────────────────────────
    # 슬롯별 필요 길이 = 그 슬롯을 쓰는 컷들의 최대 길이 + 여유
    need = {}
    units = [("card", manifest["card"])] + [(f"c{c['i']}", c) for c in manifest["cuts"]]
    for key, u in units:
        media = u.get("image") or u.get("meme")
        need[media] = max(need.get(media, 0.0), float(u["dur"]))
    source_video_paths, vid_of = {}, {}
    for n, (media, dur) in enumerate(sorted(need.items())):
        vid = f"s{n}"
        is_meme = "/pepe/" in media.replace("\\", "/")
        stem = Path(media).stem + "_" + ("meme" if is_meme else "img")
        # 사진: 폭 1080, 48%부터(=~48~90%) / 밈: 폭 700, 자막(≤63%) 아래 64%부터
        mp4 = make_still(media, src_dir / vid / f"{stem}.mp4", dur + _STILL_PAD,
                         plain_bg="white" if is_meme else None,
                         width=700 if is_meme else 1080, top_pct=64.0 if is_meme else 48.0)
        source_video_paths[vid] = str(mp4)
        vid_of[media] = vid

    # ── 2) 비트: 카드 + 컷 28개 ────────────────────────────────────────
    beats, tts_paths, sfx_paths, rules = [], {}, {}, []
    seen_kw = set()

    def add_beat(idx, u, role="실용", lines=None):
        media = u.get("image") or u.get("meme")
        vid = vid_of[media]
        dur = float(u["dur"])
        wav = str(norm_wav(u["wav"], work / "tts" / Path(u["wav"]).name, narr_lufs))
        beat = {
            "beat_idx": idx, "role": role, "narration": u["text"], "target_seconds": dur,
            "primary": {"video_id": vid, "seg_id": f"{vid}_{idx}", "start": 0.0, "end": dur,
                        "scene_desc": "", "shot_role": "기타"},
            "alternates": [],
            "tts_path": wav,
            "zoom": 1.0,   # 정지 그림엔 켄번즈를 얹지 않는다(role도 훅/반전이 아님)
        }
        if lines and " ".join(lines) == u["text"]:
            beat["caption_lines"] = list(lines)
        if sfx and u.get("sfx") and os.path.exists(u["sfx"]["file"]):
            beat["sfx"] = {"position": "first"}
            sfx_paths[idx] = u["sfx"]["file"]
        beats.append(beat)
        tts_paths[idx] = wav

    add_beat(0, manifest["card"])
    for c in manifest["cuts"]:
        add_beat(int(c["i"]), c, lines=c.get("lines"))
        hexc = COLOR_HEX.get((c.get("color") or "WHITE").upper())
        if hexc:
            for ln in (c.get("lines") or [c["text"]]):
                if ln and ln not in seen_kw:
                    seen_kw.add(ln)
                    rules.append({"keyword": ln, "color": hexc})

    edit_plan = {"structure": "free", "beats": beats}

    # ── 3) 틀·머리카피·자막 스타일 = 프리셋 한 벌 ─────────────────────
    t = manifest.get("title") or {}
    h1, h2 = (t.get("h1") or "").strip(), (t.get("h2") or "").strip()
    headcopy = dict(preset["headcopy"])
    headcopy["text"] = "\n".join(x for x in (h1, h2) if x)
    caption_style = dict(preset["caption"])
    frame = deco_frame.normalize({"preset": layout, "channel": channel})
    png = deco_frame.render_to(frame, deco_frame.cache_path(frame))
    deco = {"preset": layout, "template": {"_abspath": str(png)},
            "highlight_rules": rules, "sfx_volume": int(sfx_volume)}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    job = {"edit_plan": edit_plan, "tts_paths": tts_paths, "source_video_paths": source_video_paths,
           "sfx_paths": sfx_paths, "headcopy": headcopy, "caption_style": caption_style, "deco": deco}
    json.dump(job, open(work / f"job_{layout}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    assemble(edit_plan, tts_paths, source_video_paths, str(out_path), headcopy=headcopy,
             caption_style=caption_style, deco=deco, sfx_paths=sfx_paths or None)
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", nargs="?")
    ap.add_argument("--layout", default="sul_even")
    ap.add_argument("--channel", default="뇌전구")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--no-sfx", action="store_true")
    ap.add_argument("--sfx-volume", type=int, default=35)
    ap.add_argument("--list-layouts", action="store_true")
    a = ap.parse_args(argv)
    if a.list_layouts:
        from shopping_shorts import deco_frame
        for k, v in deco_frame.PRESETS.items():
            ok = "headcopy" in v and "caption" in v
            print(f"{k:14s} {v.get('name','')}{'' if ok else '  (세트 없음)'}")
        return 0
    if not a.manifest:
        ap.error("manifest 경로가 필요하다")
    m = json.load(open(a.manifest, encoding="utf-8"))
    out = Path(a.out) if a.out else Path(m["workdir"]) / "bridge" / f"{m['slug']}_{a.layout}.mp4"
    build(m, a.layout, a.channel, out, sfx=not a.no_sfx, sfx_volume=a.sfx_volume)
    print(f"완성: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
