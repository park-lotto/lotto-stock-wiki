"""장면꾸미기: 실제 자막 타이밍과 브라우저 템플릿을 최종 합성에서도 공유한다."""
import json
import math
import re
import subprocess
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
    for name in ("text", "fontScales", "textOffsets", "colors", "fixedLayouts", "fixedColors", "captionTexts", "captionDrags", "captionPositions", "captionLayouts", "effects"):
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
    if value.get("hookMotion") not in (None,"zoom-punch","pop","slide","flash"):
        raise ValueError("제목 효과가 올바르지 않습니다")
    if "hookMotionSpeed" in value:
        number(value["hookMotionSpeed"],.5,2)
    allowed = {"version", "mode", "presetId", "sceneIndex", "frameKind", "hookMotion", "hookMotionSpeed", "text", "fontScales", "textOffsets", "colors", "fixedLayouts", "fixedColors", "captionTexts", "captionDrags", "captionPositions", "captionLayouts", "effects"}
    return {key: val for key, val in value.items() if key in allowed}


def context_for(timeline, headcopy=None, snapshot=None, job_id=None):
    from .video_assemble import caption_schedule
    scenes = []
    for index, beat in enumerate(timeline):
        start, end = float(beat["t0"]), float(beat["t0"] + beat["dur"])
        cursor = start
        for caption, t0, t1 in caption_schedule(beat):
            a, b = max(cursor, start, float(t0)), min(end, float(t1))
            if b <= a:
                continue
            if a > cursor + .001:
                scenes.append({"start":cursor,"end":a,"caption":"","beat_idx":beat["beat_idx"],"kind":"hook" if index == 0 else "body"})
            scenes.append({"start":a,"end":b,"caption":caption,"beat_idx":beat["beat_idx"],"kind":"hook" if index == 0 else "body"})
            cursor = b
        if cursor < end - .001:
            scenes.append({"start":cursor,"end":end,"caption":"","beat_idx":beat["beat_idx"],"kind":"hook" if index == 0 else "body"})
    title = str((headcopy or {}).get("text") or (timeline[0].get("narration") if timeline else "") or "").strip()
    parts = title.splitlines()
    if len(parts) < 2 and title:
        words=title.split(); half=max(1,len(words)//2);parts=[" ".join(words[:half])," ".join(words[half:])]
    text = {"channel":"숏템메이커","hook1":parts[0] if parts else "","hook2":" ".join(parts[1:]),"bodyTitle":title}
    text.update({k:v for k,v in (snapshot or {}).get("text",{}).items() if k != "caption"})
    return {"jobId":job_id,"text":text,"scenes":scenes}


def compose(in_video, timeline, snapshot, out_path, work, headcopy=None):
    from . import video_assemble as va
    snapshot=validate_snapshot(snapshot)
    context=context_for(timeline,headcopy,snapshot)
    if not context["scenes"]:
        raise ValueError("장면꾸미기에 연결할 실제 자막 타이밍이 없습니다")
    work=Path(work).resolve()
    request=work/"scene-style-request.json"
    request.write_text(json.dumps({"snapshot":snapshot,"context":context,"output":str(work)},ensure_ascii=False),encoding="utf-8")
    run=subprocess.run(["node",str(ROOT/"tools/render_scene_style.js"),str(request)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=240)
    if run.returncode:
        raise RuntimeError("장면꾸미기 레이어 생성 실패: "+run.stderr[-1500:])
    layers=json.loads((work/"scene-style-layers.json").read_text(encoding="utf-8"))
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
        vf=f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},scale={zw}:{zh},crop={width}:{height},pad={width}:{va._OUT_H}:0:{top}:black,setsar=1"
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
        graph += "[ink]overlay=0:0:shortest=1[final]"
        part=work/f"scene-style-{index:04d}.mp4"
        va._run_ffmpeg(["ffmpeg","-y","-ss",str(first_frame/30),"-i",str(in_video),*layer_input,"-filter_complex",graph,"-map","[final]","-an","-frames:v",str(last_frame-first_frame),"-r","30","-c:v","libx264","-preset",va._preset(),"-crf",va._crf(),*va._threads_args(),"-pix_fmt","yuv420p",str(part)],cwd=str(work))
        parts.append(part)
    listing=work/"scene-style-concat.txt"
    listing.write_text("\n".join(f"file '{p.name}'" for p in parts),encoding="utf-8")
    # 오디오는 장면별로 재인코딩하지 않는다. AAC 지연이 장면마다 누적되는 것을 막는다.
    va._run_ffmpeg(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listing),"-i",str(in_video),"-map","0:v","-map","1:a?","-c","copy","-shortest","-movflags","+faststart",str(out_path)],cwd=str(work))
    return str(out_path)
