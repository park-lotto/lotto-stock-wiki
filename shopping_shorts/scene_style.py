"""장면꾸미기: 실제 자막 타이밍과 브라우저 템플릿을 최종 합성에서도 공유한다."""
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_snapshot(value):
    if not isinstance(value, dict) or len(json.dumps(value, ensure_ascii=False)) > 250_000:
        raise ValueError("장면꾸미기 설정이 올바르지 않습니다")
    mode = value.get("mode")
    if mode not in ("story", "continuous"):
        raise ValueError("템플릿 종류가 올바르지 않습니다")
    data_file = "precision20-data.js" if mode == "story" else "continuous20-data.js"
    raw = (ROOT / "out" / data_file).read_text(encoding="utf-8-sig").strip()
    rows = json.loads(raw.split("=", 1)[1].rstrip(";\r\n "))
    if value.get("presetId") not in {p["id"] for p in rows}:
        raise ValueError("알 수 없는 템플릿입니다")
    def walk(obj, depth=0):
        if depth > 8:
            raise ValueError("설정이 너무 복잡합니다")
        if isinstance(obj, dict):
            for key, child in obj.items():
                if key in ("__proto__", "constructor", "prototype"):
                    raise ValueError("허용하지 않는 설정 키입니다")
                walk(child, depth+1)
        elif isinstance(obj, list):
            if len(obj)>12:
                raise ValueError("가림막·스티커는 최대 12개입니다")
            for child in obj:
                walk(child,depth+1)
        elif isinstance(obj, (float, int)) and (not math.isfinite(obj) or abs(obj) > 10000):
            raise ValueError("설정 수치가 범위를 벗어났습니다")
        elif isinstance(obj, str) and len(obj) > 2000:
            raise ValueError("문구가 너무 깁니다")
    walk(value)
    for name in ("text", "fontScales", "textOffsets", "textDrags", "colors", "fixedLayouts", "fixedColors", "captionTexts", "captionDrags", "captionPositions", "captionLayouts", "effects"):
        if name in value and not isinstance(value[name], dict):
            raise ValueError(f"{name} 설정이 올바르지 않습니다")
    for color in (value.get("colors") or {}).values():
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("색상 형식이 올바르지 않습니다")
    for palette in (value.get("fixedColors") or {}).values():
        if not isinstance(palette, dict) or any(not isinstance(c, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in palette.values()):
            raise ValueError("팔레트 형식이 올바르지 않습니다")
    def number(v, low, high):
        if not isinstance(v, (int,float)) or isinstance(v,bool) or not low <= v <= high:
            raise ValueError("설정 수치가 범위를 벗어났습니다")
    for name,low,high in (("fontScales",.5,3),("textOffsets",-18,18),("captionPositions",-1,1)):
        for v in (value.get(name) or {}).values():
            number(v,low,high)
    for layout in (value.get("fixedLayouts") or {}).values():
        if not isinstance(layout,dict):
            raise ValueError("레이아웃 형식이 올바르지 않습니다")
        number(layout.get("top"),0,50);number(layout.get("bottom"),0,35)
        if layout["top"]+layout["bottom"] > 75:
            raise ValueError("영상 영역이 너무 작습니다")
    for drag in (value.get("captionDrags") or {}).values():
        if not isinstance(drag,dict):
            raise ValueError("자막 위치 형식이 올바르지 않습니다")
        number(drag.get("x"),-100,100);number(drag.get("y"),-100,100)
    for caption in (value.get("captionLayouts") or {}).values():
        if not isinstance(caption,dict) or caption.get("placement") not in ("title","free"):
            raise ValueError("자막 배치 형식이 올바르지 않습니다")
        number(caption.get("w",100),20,100);number(caption.get("h",7),4,25)
        for key in ("background","color"):
            if key in caption and (not isinstance(caption[key],str) or len(caption[key])>500):
                raise ValueError("자막 색상 형식이 올바르지 않습니다")
    for texts in (value.get("text") or {},value.get("captionTexts") or {}):
        if any(not isinstance(t,str) for t in texts.values()):
            raise ValueError("문구는 텍스트여야 합니다")
    for effect in (value.get("effects") or {}).values():
        if not isinstance(effect,dict):
            raise ValueError("효과 형식이 올바르지 않습니다")
        number(effect.get("zoom",1),1,3)
        number(effect.get("panX",0),-1,1)
        number(effect.get("panY",0),-1,1)
        if "masks" in effect:
            from .deco_frame import _norm_masks
            if not isinstance(effect["masks"],list):
                raise ValueError("가림막 형식이 올바르지 않습니다")
            normalized=[]
            for mask in effect["masks"]:
                if not isinstance(mask,dict):
                    raise ValueError("가림막 항목이 올바르지 않습니다")
                base=_norm_masks([{**mask,"kind":"shape" if mask.get("kind")=="graphic" else mask.get("kind")}])
                if not base:
                    continue
                item=base[0]
                if mask.get("kind")=="graphic":
                    if not re.fullmatch(r"[a-z_]{1,32}",str(mask.get("graphic") or "")):
                        raise ValueError("도형 종류가 올바르지 않습니다")
                    item.update(kind="graphic",graphic=mask["graphic"])
                if mask.get("motion") in ("none","point","pulse","spin","float","reveal"):
                    item["motion"]=mask["motion"]
                if item["kind"]=="badge":
                    item["text"]=str(mask.get("text") or "")[:24]
                    if mask.get("badgeStyle") in ("pill","ticket","glass","burst"):
                        item["badgeStyle"]=mask["badgeStyle"]
                normalized.append(item)
            effect["masks"]=normalized
        hl=effect.get("highlight") or {}
        if not isinstance(hl,dict):
            raise ValueError("강조 형식이 올바르지 않습니다")
        if hl:
            for key,default,lo,hi in (("cx",.5,0,1),("cy",.55,0,1),("r",.22,.06,.9),("zoom",2,1.1,4)):
                number(hl.get(key,default),lo,hi)
    if value.get("hookMotion") not in (None,"zoom-punch","pop","slide","flash","rise","push-in","shake"):
        raise ValueError("제목 효과가 올바르지 않습니다")
    if value.get("hookBandMotion") not in (None, "", "rise", "grow"):
        raise ValueError("흰 띠 효과 값이 올바르지 않습니다")
    if not re.fullmatch(r"[a-z0-9_-]{0,32}", str(value.get("fontSet") or "")):   # precision20-ui.js FONT_SETS의 id
        raise ValueError("폰트 템플릿 값이 올바르지 않습니다")
    if not re.fullmatch(r"[a-z0-9_-]{0,32}", str(value.get("titleDeco") or "")):   # precision20-ui.js DECOS의 id(훅 제목 꾸밈)
        raise ValueError("제목 꾸밈 값이 올바르지 않습니다")
    if value.get("bodyCaptionMotion") not in (None, "", "rise", "grow", "pop", "slide", "drop", "fade", "wide"):   # precision20-ui.js BODY_CAPTION_MOTIONS와 짝
        raise ValueError("본문 자막 효과 값이 올바르지 않습니다")
    if "hookBandRise" in value and not isinstance(value["hookBandRise"], bool):
        raise ValueError("흰 띠 스윽 올라오기 값이 올바르지 않습니다")
    if "hookMotionSpeed" in value:
        number(value["hookMotionSpeed"],.5,2)
    if value.get("hookCaptionMode") not in (None,"visible","hidden"):
        raise ValueError("훅 말자막 설정이 올바르지 않습니다")
    if "branding" in value:
        if not isinstance(value["branding"],dict):
            raise ValueError("워터마크 설정이 올바르지 않습니다")
        for item in value["branding"].values():
            if not isinstance(item,dict) or not isinstance(item.get("text",""),str) or len(item.get("text",""))>40:
                raise ValueError("표시 문구는 40자 이내입니다")
            for key,default,lo,hi in (("x",5,0,100),("y",5,0,100),("size",3,1,10),("opacity",100,10,100)):
                number(item.get(key,default),lo,hi)
            if not re.fullmatch(r"#[0-9a-fA-F]{6}",item.get("color","#ffffff")):
                raise ValueError("표시 색상이 올바르지 않습니다")
    allowed = {"version", "mode", "presetId", "sceneIndex", "frameKind", "hookMotion", "hookBandRise", "hookBandMotion", "bodyCaptionMotion", "fontSet", "titleDeco", "hookMotionSpeed", "hookCaptionMode", "branding", "text", "fontScales", "textOffsets", "textDrags", "colors", "fixedLayouts", "fixedColors", "captionTexts", "captionDrags", "captionPositions", "captionLayouts", "effects"}
    return {key: val for key, val in value.items() if key in allowed}


_TINY_GAP = 0.35   # 이보다 짧은 '자막 없는 틈'은 장면으로 세지 않는다(초)


def _absorb_tiny_gaps(scenes):
    """자막이 비는 아주 짧은 틈(음성이 비트 시작보다 살짝 늦는 cap_lead 등)을 이웃 자막 장면에 붙인다.

    2026-09-22 사장님 "본문 첫 자막이 없음": job d29a2bd26032 본문 첫 비트가 3.58~3.74(0.16초) 빈 장면 → 편집기에
    '5/35 장면'으로 빈 띠가 뜨고, 렌더에도 5프레임 빈 띠가 들어갔다. 훅 맨 앞 0.21초도 같은 꼴.
    같은 비트 안에서만 붙인다(비트 경계는 넘지 않는다). 앞 틈은 뒤 자막에, 뒤 틈은 앞 자막에. 0.35초 이상 틈은 그대로(진짜 무자막 구간).
    편집기·렌더러·캡컷이 모두 이 context를 쓰므로 셋이 같이 바뀐다."""
    out = []
    for sc in scenes:
        if sc["caption"] or (sc["end"] - sc["start"]) >= _TINY_GAP:
            out.append(dict(sc)); continue
        if out and out[-1]["beat_idx"] == sc["beat_idx"] and out[-1]["caption"]:
            out[-1]["end"] = sc["end"]           # 뒤 틈 → 앞 자막이 끝까지
            continue
        out.append(dict(sc, _lead=True))         # 앞 틈 → 다음 자막이 오면 거기에 붙인다
    result = []
    for sc in out:
        if result and result[-1].get("_lead") and result[-1]["beat_idx"] == sc["beat_idx"] and sc["caption"]:
            sc = dict(sc, start=result[-1]["start"]); result.pop()
        result.append(sc)
    for sc in result:
        sc.pop("_lead", None)
    return result


def context_for(timeline, headcopy=None, snapshot=None, job_id=None):
    from .video_assemble import caption_schedule
    from .template_copy import scene_text
    scenes = []
    hide_hook_captions = (snapshot or {}).get("hookCaptionMode") == "hidden"
    for index, beat in enumerate(timeline):
        start, end = float(beat["t0"]), float(beat["t0"] + beat["dur"])
        cursor = start
        kind = "hook" if index == 0 else "body"
        caption_visible = not (kind == "hook" and hide_hook_captions)
        for caption, t0, t1 in caption_schedule(beat):
            a, b = max(cursor, start, float(t0)), min(end, float(t1))
            if b <= a:
                continue
            if a > cursor + .001:
                scenes.append({"start":cursor,"end":a,"caption":"","caption_visible":caption_visible,"beat_idx":beat["beat_idx"],"kind":kind})
            scenes.append({"start":a,"end":b,"caption":caption,"caption_visible":caption_visible,"beat_idx":beat["beat_idx"],"kind":kind})
            cursor = b
        if cursor < end - .001:
            scenes.append({"start":cursor,"end":end,"caption":"","caption_visible":caption_visible,"beat_idx":beat["beat_idx"],"kind":kind})
    scenes = _absorb_tiny_gaps(scenes)
    copy = dict(headcopy) if isinstance(headcopy, dict) else {}
    if not (copy.get("text") or "").strip():
        copy["text"] = (timeline[0].get("narration") if timeline else "") or ""
    text = {"channel": "숏템메이커", **scene_text(copy)}
    text.update({k:v for k,v in (snapshot or {}).get("text",{}).items() if k != "caption"})
    return {"jobId":job_id,"text":text,"scenes":scenes}


def _layer_render_timeout(context):
    """장면꾸미기 레이어 생성 제한시간(초) — **영상 길이에 비례**한다.

    ★2026-09-17 실측(김성현님 job eeb35a6e9878, 29.7초·33장면, 워터마크 '둥둥'):
      움직이는 워터마크가 있으면 전 장면을 **프레임마다** 캡처한다(render_scene_style.js).
      925장을 245.1초에 만들었다(초당 약 3.8장). 고정 240초 제한에 5초 모자라 **세 번 연속**
      실패했고, 고객은 두 번의 렌더 대기(약 20분) 끝에 실패만 봤다.
    ★30fps 프레임 수 × 0.5초 + 여유 120초. 짧은 영상은 종전 240초 그대로, 상한 900초.
      (전체 렌더가 10분 넘으면 _render_is_stale이 죽은 렌더로 보므로 상한을 거기 맞춘다.)
    """
    scenes = (context or {}).get("scenes") or []
    total = max((float(sc.get("end") or 0) for sc in scenes), default=0.0)
    return int(min(900, max(240, 120 + total * 30 * 0.5)))


def render_layers(timeline, snapshot, output, headcopy=None, job_id=None):
    """브라우저 미리보기와 외부 편집기가 함께 쓰는 투명 장면 레이어를 만든다."""
    snapshot = validate_snapshot(snapshot)
    context = context_for(timeline, headcopy, snapshot, job_id)
    if not context["scenes"]:
        raise ValueError("장면꾸미기에 연결할 실제 자막 타이밍이 없습니다")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    request = output / "scene-style-request.json"
    request.write_text(
        json.dumps({"snapshot": snapshot, "context": context, "output": str(output)},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    node_env = os.environ.copy()
    if sys.platform.startswith("linux"):
        # 운영 Ubuntu는 AppArmor가 unprivileged user namespace를 막아 Chrome의
        # 기본 sandbox가 기동하지 않는다. 이 자식 프로세스는 우리가 만든 로컬 HTML만
        # 렌더하므로 Linux에서만 Puppeteer의 기존 opt-in 플래그를 켠다.
        node_env.setdefault("SCENE_STYLE_NO_SANDBOX", "1")
    run = subprocess.run(
        ["node", str(ROOT / "tools/render_scene_style.js"), str(request)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=_layer_render_timeout(context),
        env=node_env,
    )
    if run.returncode:
        raise RuntimeError("장면꾸미기 레이어 생성 실패: " + run.stderr[-1500:])
    return json.loads((output / "scene-style-layers.json").read_text(encoding="utf-8"))


def render_layer_one(timeline, snapshot, output, index, headcopy=None, job_id=None):
    """장면 하나(index)의 꾸미기 레이어 PNG만 만든다 — 썸네일 후보(2026-09-23 사장님 "훅 장면을 쓰고 싶은 건데").
    render_layers와 같은 렌더러·같은 context — only=[index]·still로 한 장만 찍어 몇 초면 끝난다. 반환: PNG 경로."""
    snapshot = validate_snapshot(snapshot)
    context = context_for(timeline, headcopy, snapshot, job_id)
    if not context["scenes"] or not (0 <= int(index) < len(context["scenes"])):
        raise ValueError("장면 번호가 범위 밖입니다")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    request = output / "scene-style-request.json"
    request.write_text(json.dumps({"snapshot": snapshot, "context": context, "output": str(output),
                                   "only": [int(index)], "still": True}, ensure_ascii=False), encoding="utf-8")
    node_env = os.environ.copy()
    if sys.platform.startswith("linux"):
        node_env.setdefault("SCENE_STYLE_NO_SANDBOX", "1")
    run = subprocess.run(["node", str(ROOT / "tools/render_scene_style.js"), str(request)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=node_env)
    if run.returncode:
        raise RuntimeError("장면꾸미기 레이어 생성 실패: " + run.stderr[-1500:])
    layers = json.loads((output / "scene-style-layers.json").read_text(encoding="utf-8"))
    layer = layers[int(index)] if int(index) < len(layers) else None
    if not layer or not layer.get("file"):
        raise RuntimeError("레이어 파일이 없습니다")
    return output / layer["file"]


def compose(in_video, timeline, snapshot, out_path, work, headcopy=None):
    from . import video_assemble as va
    snapshot=validate_snapshot(snapshot)
    context=context_for(timeline,headcopy,snapshot)
    work=Path(work).resolve()
    layers=render_layers(timeline,snapshot,work,headcopy)
    parts=[]
    for index,(scene,layer) in enumerate(zip(context["scenes"],layers,strict=True)):
        first_frame, last_frame = round(scene["start"]*30), round(scene["end"]*30)
        if last_frame <= first_frame:
            continue
        top=round(layer["media"]["top"]*va._OUT_H/100/2)*2
        height=min(va._OUT_H-top,max(2,round(layer["media"]["height"]*va._OUT_H/100/2)*2))
        effect=(snapshot.get("effects") or {}).get(str(index)) or {}
        zoom,_,_=va.scene_zoom_of({"scene_zoom":effect.get("zoom",1)})
        width=va._OUT_W
        zw,zh=round(width*zoom/2)*2,round(height*zoom/2)*2
        crop_x=round((zw-width)*(1-effect.get("panX",0))/2)
        crop_y=round((zh-height)*(1-effect.get("panY",0))/2)
        vf=f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},scale={zw}:{zh},crop={width}:{height}:{crop_x}:{crop_y},pad={width}:{va._OUT_H}:0:{top}:black,setsar=1"
        hl=va.highlight_fc({"scene_hl":effect.get("highlight")},vf,grow=False)
        prefix=f"[1:v]tpad=stop_mode=clone:stop_duration={(last_frame-first_frame)/30}[ink];" if layer.get("animation") else "[1:v]null[ink];"
        graph=prefix+(hl+";" if hl else f"[0:v]{vf}[out];")
        layer_input=["-framerate","30","-i",str(work/layer["animation"]["pattern"])] if layer.get("animation") else ["-loop","1","-i",str(work/layer["file"])]
        from .deco_frame import render_blur_mask, blur_sigma
        masks=effect.get("masks") or []
        blur=render_blur_mask({"masks":masks})
        if blur is not None:
            mask_path=work/f"scene-style-blur-{index}.png";blur.save(mask_path)
            layer_input += ["-loop","1","-i",str(mask_path)]
            graph += f"[out]split[clear][soft];[soft]gblur=sigma={blur_sigma(masks)}[blur];[2:v]format=rgba,alphaextract[mask];[blur][mask]alphamerge[masked];[clear][masked]overlay=0:0:shortest=1[under];[under]"
        else:
            graph += "[out]"
        graph += "[ink]overlay=0:0:shortest=1[composed]"
        camera=layer.get("camera") or []
        if any(abs(frame.get("zoom",1)-1)>.00001 for frame in camera):
            # The browser owns the motion curve; sample values apply to the complete composition.
            def expression(key, default):
                expr=str(default)
                for frame_no in range(len(camera)-1,-1,-1):
                    val=camera[frame_no][key]
                    if abs(val-default)>.000001:
                        expr=f"if(eq(on,{frame_no}),{val:.7f},{expr})"
                return expr
            z,dx,dy=expression("zoom",1),expression("dx",0),expression("dy",0)
            graph+=f";[composed]zoompan=z='{z}':x='(iw-iw/zoom)/2-({dx})*iw/zoom':y='(ih-ih/zoom)/2-({dy})*ih/zoom':d=1:s={width}x{va._OUT_H}:fps=30[final]"
        else:
            graph+=";[composed]null[final]"
        part=work/f"scene-style-{index:04d}.mp4"
        va._run_ffmpeg(["ffmpeg","-y","-ss",str(first_frame/30),"-i",str(in_video),*layer_input,"-filter_complex",graph,"-map","[final]","-an","-frames:v",str(last_frame-first_frame),"-r","30","-c:v","libx264","-preset",va._preset(),"-crf",va._crf(),*va._threads_args(),"-pix_fmt","yuv420p",str(part)],cwd=str(work))
        parts.append(part)
    listing=work/"scene-style-concat.txt"
    listing.write_text("\n".join(f"file '{p.name}'" for p in parts),encoding="utf-8")
    # 오디오는 장면별로 재인코딩하지 않는다. AAC 지연이 장면마다 누적되는 것을 막는다.
    va._run_ffmpeg(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listing),"-i",str(in_video),"-map","0:v","-map","1:a?","-c","copy","-shortest","-movflags","+faststart",str(out_path)],cwd=str(work))
    return str(out_path)
