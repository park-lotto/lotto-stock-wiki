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
        number(caption.get("boxClear",0),0,90)   # 자막박스 투명도 %(2026-09-24)
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
        if "dim" in effect:   # 어둡게(관제 124): 영상 칸 밝기 level(0.1~1)을 장면 시작부터 sec초(0=장면 내내)
            dim=effect["dim"]
            if not isinstance(dim,dict):
                raise ValueError("어둡게 형식이 올바르지 않습니다")
            number(dim.get("level"),.1,1);number(dim.get("sec",0),0,10)
        number(effect.get("zoomIn",0),0,3)
        if effect.get("zoomMove",'in') not in ("in","pull","inout"):   # 확대 방식: 0.5초 확대 / 장면 내내 쭉 당기기 / 확대 후 돌아오기
            raise ValueError("확대 방식이 올바르지 않습니다")
        if not isinstance(effect.get("fxAutoPlaced",False),bool):   # 자동 배치가 넣은 칸 표식
            raise ValueError("자동 배치 표식이 올바르지 않습니다")
        if not isinstance(effect.get("shock",False),bool):   # 흑백 충격(흑백·지지직·흔들림)
            raise ValueError("흑백 충격 형식이 올바르지 않습니다")   # 확대 움직임(관제 124): 장면 시작부터 zoomIn초 동안 1배→zoom 배로 빨려 들어감(0=멈춘 확대)
        if "fxAuto" in effect and effect["fxAuto"] not in ("jump","emph"):
            raise ValueError("자동 효과 표식이 올바르지 않습니다")
        if "masks" in effect:
            from .deco_frame import _norm_masks
            if not isinstance(effect["masks"],list):
                raise ValueError("가림막 형식이 올바르지 않습니다")
            normalized=[]
            for mask in effect["masks"]:
                if not isinstance(mask,dict):
                    raise ValueError("가림막 항목이 올바르지 않습니다")
                base=_norm_masks([{**mask,"kind":"shape" if mask.get("kind") in ("graphic","image") else mask.get("kind")}])
                if not base:
                    continue
                item=base[0]
                if mask.get("kind")=="graphic":
                    if not re.fullmatch(r"[a-z_]{1,32}",str(mask.get("graphic") or "")):
                        raise ValueError("도형 종류가 올바르지 않습니다")
                    item.update(kind="graphic",graphic=mask["graphic"])
                if mask.get("kind")=="image":
                    # 로고(관제 065): 계정 폴더의 PNG만. 파일이 없으면 버린다(없는 그림을 렌더가 기다리지 않게).
                    src=str(mask.get("src") or "")
                    if not re.fullmatch(r"장면꾸미기_로고/\d{1,9}/[0-9a-f]{16}\.png",src) or not (ROOT/"out"/src).is_file():
                        continue
                    item.update(kind="image",src=src)
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
    per_frame = value.get("fontSets")
    if per_frame is not None:
        # 틀(훅/본문)별 글꼴 — 2026-09-24 사장님 "프리셋은 한 개, 훅·본문 스타일은 따로".
        if not isinstance(per_frame, dict) or len(per_frame) > 4:
            return None
        for frame, fid in per_frame.items():
            if frame not in ("hook", "body", "frame") or not re.fullmatch(r"[a-z0-9_-]{0,32}", str(fid or "")):
                return None
    if not re.fullmatch(r"[a-z0-9_-]{0,32}", str(value.get("fontSet") or "")):   # precision20-ui.js FONT_SETS의 id
        raise ValueError("폰트 템플릿 값이 올바르지 않습니다")
    if not re.fullmatch(r"[a-z0-9_-]{0,32}", str(value.get("titleDeco") or "")):   # precision20-ui.js DECOS의 id(훅 제목 꾸밈)
        raise ValueError("제목 꾸밈 값이 올바르지 않습니다")
    for key, old, label in (("textWeight", ("", "bold", "heavy"), "글자 두께"), ("textShadow", ("", "soft", "strong"), "글자 그림자")):
        look = value.get(key)
        # 2026-09-29: 새 저장값은 0~100(5단위), 09-28의 3단계 문자열은 기존 작업 재열기용으로 계속 허용한다.
        if isinstance(look, dict):
            if set(look) - {"channel", "titleLarge", "titleSmall", "caption"} or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or v > 100 or v % 5
                for v in look.values()
            ):
                raise ValueError(f"{label} 값이 올바르지 않습니다")
        elif look is not None and look not in old and (isinstance(look, bool) or not isinstance(look, (int, float)) or look < 0 or look > 100 or look % 5):
            raise ValueError(f"{label} 값이 올바르지 않습니다")
    for key, lo, hi, label in (("textSpacing", -20, 60, "자간"), ("textLeading", -30, 100, "행간")):      # 글자 설정(관제 103) — precision20-ui.js LOOK_ROWS 와 짝
        look = value.get(key)
        if look is not None and (not isinstance(look, dict) or set(look) - {"channel", "titleLarge", "titleSmall", "caption"} or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi for v in look.values())):
            raise ValueError(f"{label} 값이 올바르지 않습니다")
    if value.get("bodyCaptionMotion") not in (None, "", "rise", "grow", "pop", "slide", "drop", "fade", "wide"):   # precision20-ui.js BODY_CAPTION_MOTIONS와 짝
        raise ValueError("본문 자막 효과 값이 올바르지 않습니다")
    word_fx = value.get("wordFx")
    if word_fx is not None:
        # 단어 강조(관제 102) — precision20-ui.js WORD_FX_STYLES 와 짝. color 빈칸 = 템플릿 포인트 색(자동).
        if (not isinstance(word_fx, dict) or set(word_fx) - {"style", "color", "grow"}
                or word_fx.get("style", "") not in ("", "box", "color")
                or word_fx.get("grow", "") not in ("", "hold", "pop", True, False)      # 옛 값(참/거짓)도 받는다 — 참 = hold
                or not re.fullmatch(r"(#[0-9a-fA-F]{6})?", str(word_fx.get("color", "")))):
            raise ValueError("단어 강조 값이 올바르지 않습니다")
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
    if "manualText" in value and value["manualText"] != 2:      # 글자 직접 조절 표식(관제 103) — precision20-ui.js manualText 와 짝
        raise ValueError("글자 조절 방식 값이 올바르지 않습니다")
    if "plainCaption" in value and value["plainCaption"] != 2:
        raise ValueError("원본 자막 표시가 올바르지 않습니다")
    if value.get("frameRule") not in (None, *FRAME_RULES):
        raise ValueError("장면 틀 규칙이 올바르지 않습니다")
    allowed = {"version", "frameRule", "plainCaption", "manualText", "mode", "presetId", "sceneIndex", "frameKind", "hookMotion", "hookBandRise", "hookBandMotion", "bodyCaptionMotion", "wordFx", "fontSet", "fontSets", "titleDeco", "textWeight", "textShadow", "textSpacing", "textLeading", "hookMotionSpeed", "hookCaptionMode", "branding", "text", "fontScales", "textOffsets", "textDrags", "colors", "fixedLayouts", "fixedColors", "captionTexts", "captionDrags", "captionPositions", "captionLayouts", "effects"}
    return {key: val for key, val in value.items() if key in allowed}


# ★화면 전용 값(2026-09-28 사장님 job 8c63b0691924 실사고): 편집기 저장값에는 '보고 있던 장면(sceneIndex)·틀(frameKind)'이 담긴다.
#   렌더는 장면마다 show(i)를 다시 부르므로 이 둘은 그림에 영향이 없다. 그런데 서버가 저장값을 통째로 비교해
#   렌더가 끝난 뒤 편집기를 열어 다른 장면을 구경하고 [닫기]만 눌러도 "설정이 바뀌었다"며 완성본을 버렸다.
#   '설정이 바뀌었나'는 전부 이 함수를 거친다 — app._save_render_inputs(무효화) · mix_pipeline._render_stamp(도장) ·
#   편집기 scene-style-produce.js sameSnapshot(올릴지 말지)가 같은 키 목록을 본다.
VIEW_ONLY_KEYS = ("sceneIndex", "frameKind")
#   text.caption 도 화면 전용이다 — 편집기 syncCaption()이 장면을 넘길 때마다 그 장면 자막 글로 덮어쓴다(precision20-ui.js).
#   장면별 자막 편집은 captionTexts 에 따로 담기므로 비교에서 text.caption 을 빼도 진짜 편집은 잡힌다(check_reopen_keeps_render ③ 실측).
VIEW_ONLY_TEXT_KEYS = ("caption",)


def render_view(snapshot):
    """렌더에 영향 있는 부분만 남긴 저장값 — 비교·도장 전용(저장은 원본 그대로)."""
    if not isinstance(snapshot, dict):
        return snapshot
    view = {k: v for k, v in snapshot.items() if k not in VIEW_ONLY_KEYS}
    if isinstance(view.get("text"), dict):
        view["text"] = {k: v for k, v in view["text"].items() if k not in VIEW_ONLY_TEXT_KEYS}
    return view


def deco_render_view(deco):
    """deco 전체에서 scene_style만 render_view로 정규화한 사본."""
    if isinstance(deco, dict) and isinstance(deco.get("scene_style"), dict):
        return {**deco, "scene_style": render_view(deco["scene_style"])}
    return deco


from .video_assemble import _LEAD_ABSORB as _TINY_GAP   # 이보다 짧은 '자막 없는 틈'은 장면으로 세지 않는다(초) — 값은 video_assemble 한 곳


def _absorb_tiny_gaps(scenes):
    """자막이 비는 아주 짧은 **뒤** 틈을 앞 자막 장면에 붙인다.

    ★칸 **앞** 틈(cap_lead)은 여기서 판단하지 않는다(2026-09-27) — 자막 시각의 주인 caption_schedule 이
      absorb_lead(caption_lead_absorb)로 첫 자막을 칸 시작부터 띄워 오므로, 앞 틈 장면은 애초에 생기지 않는다.
      종전엔 여기서만 앞 틈을 흡수해 3단계 화면·음성 미리보기(말 시작부터)와 완성본(칸 시작부터)이 갈렸다.
    (아래는 종전 설명 — 앞 틈 부분은 caption_schedule 로 옮겨 갔다)

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
        out.append(dict(sc))                     # 앞 틈은 caption_schedule 이 이미 흡수했다 — 남았다면 그대로(진짜 틈)
    return out


MY_CHANNEL_KEY = "deco_my_channel"      # 계정별 내 채널명(app의 /api/produce/frame/my_channel과 같은 키)
DEFAULT_CHANNEL = "숏템메이커"


def account_channel(job_id):
    """이 작업 주인의 **내 채널명**(계정 설정). 없거나 못 읽으면 "".
    ★2026-09-29 이유준님 제보: 새 편집기 '내 프리셋'은 문구(text)를 빼고 저장하므로, 새 작업의 채널명은
      여기 기본값이 정한다 — 종전엔 계정에 '오탐구'가 있어도 늘 '숏템메이커'가 박혔다(0순위-B: 값의 주인은 계정 한 곳)."""
    if not job_id:
        return ""
    try:
        from .store import Store
        from .config import DB_PATH
        st = Store(DB_PATH)
        job = st.get_mix_job(job_id) or {}
        cid = int(job.get("customer_id") or 0)
        return (st.get_pref(MY_CHANNEL_KEY, customer_id=cid) or "").strip() if cid else ""
    except Exception as exc:          # 못 읽어도 꾸미기는 떠야 한다 — 단 조용히 넘기지 않는다
        print(f"[scene_style] 내 채널명 읽기 실패 job={job_id}: {exc}", file=sys.stderr)
        return ""


FRAME_RULES = ("hook_body", "hook_all", "body_all")   # 썰훅 · 훅만 · 썰만(관제 058, 2026-10-02 사장님 5버튼)


def frame_kind(index, rule):
    """장면 index의 틀(hook/body) — **판단의 주인은 이 함수 하나**. 편집기 미리보기는 서버가 준 scenes[i].kind를 그대로 따르고,
    렌더·썸네일·캡컷 레이어도 같은 context_for를 거친다. rule이 없거나 모르는 값이면 종전(첫 장면 훅·나머지 본문)."""
    if rule == "hook_all":
        return "hook"
    if rule == "body_all":
        return "body"
    return "hook" if index == 0 else "body"


def _word_key(text):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text or "")


def attach_scene_words(scenes, timeline):
    """장면(자막 구절)마다 **어절이 켜지는 시각**(초, 영상 기준)을 scene["words"] 에 붙인다 — 단어 강조의 주인(관제 102).

    화면·렌더·캡컷은 이 값만 읽는다(`out/precision20-ui.js` wordFxTimes). 여기서 정하는 것:
      · 구절의 어절을 음성 정렬 단어(beat["words"], tts_timestamps.words_relative)와 **순서대로** 맞춘다.
      · 시각은 정렬의 절대값이 아니라 **구절 창 [start,end) 안의 비율**로 옮긴다. 구절 창은 caption_schedule 이
        트림·리드인·배속을 다 갚은 값이라, 여기에 비율로 얹으면 자막이 바뀌는 순간과 단어 강조가 절대 어긋나지 않는다.
      · 정렬이 없거나 글자가 안 맞는 구절에는 words 를 안 붙인다 → 화면 쪽이 글자수 비례로 나눈다(추정은 그 한 곳).
    """
    cursor = {}
    # [curious] 같은 음성 지시 태그는 정렬에는 있지만 자막 글이 아니다 — 뺀다(안 빼면 첫 어절부터 어긋난다, 실측 409f894230c6).
    words_of = {beat["beat_idx"]: [w for w in (beat.get("words") or [])
                                   if _word_key(w.get("word")) and w.get("start") is not None
                                   and not re.fullmatch(r"\[[^\]]*\]", str(w.get("word")).strip())]
                for beat in timeline}
    for scene in scenes:
        tokens = (scene.get("caption") or "").split()
        words = words_of.get(scene.get("beat_idx")) or []
        if not tokens or not words:
            continue
        k, starts = cursor.get(scene["beat_idx"], 0), []
        for token in tokens:
            want, got, first = _word_key(token), "", None
            if not want:                      # 기호뿐인 어절 — 앞 어절과 같이 켠다
                starts.append(starts[-1] if starts else None)
                continue
            while k < len(words) and len(got) < len(want):      # 정렬이 어절을 더 잘게 쪼갠 경우 이어 붙인다
                got += _word_key(words[k]["word"])
                first = words[k]["start"] if first is None else first
                k += 1
            if got != want:
                starts = None
                break
            starts.append(first)
        if not starts or all(s is None for s in starts):      # 글자가 안 맞음 → 이 구절은 화면 쪽 추정에 맡긴다
            continue
        cursor[scene["beat_idx"]] = k
        head = next(s for s in starts if s is not None)
        starts = [head if s is None else s for s in starts]
        tail = words[k]["start"] if k < len(words) else (words[k - 1].get("end") or starts[-1])
        span = max(1e-6, float(tail) - float(head))
        a, b = float(scene["start"]), float(scene["end"])
        scene["words"] = [round(a + (b - a) * max(0.0, min(1.0, (float(s) - float(head)) / span)), 3) for s in starts]
    return scenes


def overlay_spans(scenes, layers, folder):
    """캡컷에 올릴 장면 레이어 구간 [{path,start,end}]. 단어 강조가 켜진 장면은 단어마다 한 장씩 쪼갠다.

    완성본은 compose 가 프레임 묶음(animation)으로 굽지만 캡컷은 정지 그림 클립만 받는다 — 렌더러가 단어 상태마다
    남긴 그림(layer["wordSpans"])을 그 구간에 올린다. 없으면 종전대로 장면당 한 장."""
    folder, out = Path(folder), []
    for scene, layer in zip(scenes, layers):
        if not layer or not layer.get("file"):
            continue
        start, end = float(scene["start"]), float(scene["end"])
        spans = layer.get("wordSpans") or []
        if not spans:
            out.append({"path": str(folder / layer["file"]), "start": start, "end": end})
            continue
        for index, span in enumerate(spans):
            a = start + span["frame"] / 30
            b = start + spans[index + 1]["frame"] / 30 if index + 1 < len(spans) else end
            if b > a:
                out.append({"path": str(folder / span["file"]), "start": a, "end": b})
    return out


# 중요 장면 종류(관제 124, 사장님 2026-10-05 "제품 정체 드러날 때나 cta나 훅이나 고조나 중요 장면들") —
#   대본 비트 역할 이름 → 훅/제품 공개/고조/CTA. 이름은 고객 작업 500개 실측 분포(고조1 783·고조2 539·훅 337·공개 309·
#   CTA 168·반전 152·hook 147·cta 111·escalation 51·reveal 13·twist 12·bait 9 …)에서 뽑았다. 판단은 여기 한 곳.
_MOMENT_ROLES = {
    "hook": ("훅", "hook", "title", "미끼", "bait"),
    "reveal": ("공개", "reveal", "정체", "정체공개"),
    "peak": ("고조", "고조1", "고조2", "고조3", "escalation", "반전", "twist"),
    # 문제·실수·비포 — 흑백 충격을 거는 자리(사장님 2026-10-05 "충격이나 잘못된 비포 장면"). 실측 problem 113.
    "problem": ("문제", "problem", "페인포인트", "페인", "pain", "before", "비포", "실수"),
}


def moment_of(role):
    """비트 역할 → 'hook'|'reveal'|'peak'|'problem'|'cta'|None. CTA 이름은 edit_plan._CTA_ROLES 를 그대로 쓴다."""
    from .edit_plan import _CTA_ROLES
    r = str(role or "").strip()
    if not r:
        return None
    if r in _CTA_ROLES or r.lower() in {x.lower() for x in _CTA_ROLES}:
        return "cta"
    for moment, names in _MOMENT_ROLES.items():
        if r in names or r.lower() in names:
            return moment
    return None


def context_for(timeline, headcopy=None, snapshot=None, job_id=None):
    from .video_assemble import caption_schedule, caption_lead_absorb
    from .template_copy import scene_text
    _absorb = caption_lead_absorb({"scene_style": snapshot or True})   # 장면꾸미기 = 칸 앞 짧은 틈을 첫 자막에
    scenes = []
    hide_hook_captions = (snapshot or {}).get("hookCaptionMode") == "hidden"
    for index, beat in enumerate(timeline):
        start, end = float(beat["t0"]), float(beat["t0"] + beat["dur"])
        cursor = start
        kind = frame_kind(index, (snapshot or {}).get("frameRule"))
        moment = moment_of(beat.get("role"))   # 중요 장면 종류(관제 124) — 편집기 '중요 장면에 한 번에'가 쓴다
        caption_visible = not (kind == "hook" and index == 0 and hide_hook_captions)   # 숨김은 첫 훅 문장만(썰훅만 본문 자막은 보인다, 10-02)
        for caption, t0, t1 in caption_schedule(beat, absorb_lead=_absorb):
            a, b = max(cursor, start, float(t0)), min(end, float(t1))
            if b <= a:
                continue
            if a > cursor + .001:
                scenes.append({"start":cursor,"end":a,"caption":"","caption_visible":caption_visible,"beat_idx":beat["beat_idx"],"kind":kind,"moment":moment})
            scenes.append({"start":a,"end":b,"caption":caption,"caption_visible":caption_visible,"beat_idx":beat["beat_idx"],"kind":kind,"moment":moment})
            cursor = b
        if cursor < end - .001:
            scenes.append({"start":cursor,"end":end,"caption":"","caption_visible":caption_visible,"beat_idx":beat["beat_idx"],"kind":kind,"moment":moment})
    scenes = attach_scene_words(_absorb_tiny_gaps(scenes), timeline)
    copy = dict(headcopy) if isinstance(headcopy, dict) else {}
    if not (copy.get("text") or "").strip():
        # ★제목이 비면 **대본의 제목 줄(첫 문장)**을 쓴다. AI 후보(ai_copy)는 그 줄이
        #   두 줄 상한에 안 담겨 낱말이 버려질 때만 쓴다 — 판단은 hook_from_script 한 곳.
        #   (2026-09-23 사장님 "대본에 있는 제목 훅이 안 들어온다")
        from .template_copy import hook_from_script
        copy["text"], copy["hook_source"] = hook_from_script(
            (timeline[0].get("narration") if timeline else "") or "", copy.get("ai_copy") or "")
    text = {"channel": account_channel(job_id) or DEFAULT_CHANNEL, **scene_text(copy)}
    auto_text = {k: text.get(k, "") for k in ("hook1", "hook2", "bodyTitle")}   # 편집기가 원본→템플릿으로 바꿀 때 빈 제목을 채우는 데 쓴다
    saved_text = {k:v for k,v in (snapshot or {}).get("text",{}).items() if k != "caption"}
    # ★템플릿(썰쇼핑)에서 제목 세 칸이 **전부 빈칸**으로 저장됐으면 자동 제목(대본 첫 줄)을 그대로 둔다(2026-09-25 사장님 "썰쇼핑 돌려놓고").
    #   빈칸이 저장본을 이기면 제목 띠가 텅 빈 채로 나왔다(실측 job cafa17d6856b: hook1·hook2·bodyTitle 모두 ""). 일부만 비운 건 사용자 뜻이라 존중.
    #   원본(plain, 인스타식)은 제목 없이 자막만 쓰는 게 정상이라 그대로 둔다.
    if (snapshot or {}).get("presetId") != "plain" and all(not str(saved_text.get(k) or "").strip() for k in ("hook1", "hook2", "bodyTitle")):
        for k in ("hook1", "hook2", "bodyTitle"):
            saved_text.pop(k, None)
    text.update(saved_text)
    return {"jobId":job_id,"text":text,"autoText":auto_text,"scenes":scenes}


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


def media_geometry(layer, effect):
    """장면 레이어의 영상 칸(media) 안에 원본을 어떻게 앉히는지 — 렌더(compose)와 썸네일 후보(compose_still)가 같이 쓴다.
    반환 (width, height, top, zw, zh, crop_x, crop_y): 원본을 width×height에 꽉 채워(cover) 가운데 자르고,
    zw×zh로 확대한 뒤 (crop_x, crop_y)에서 width×height를 잘라 top 높이에 둔다(나머지는 검정)."""
    from . import video_assemble as va
    top=round(layer["media"]["top"]*va._OUT_H/100/2)*2
    height=min(va._OUT_H-top,max(2,round(layer["media"]["height"]*va._OUT_H/100/2)*2))
    zoom,_,_=va.scene_zoom_of({"scene_zoom":(effect or {}).get("zoom",1)})
    width=va._OUT_W
    zw,zh=round(width*zoom/2)*2,round(height*zoom/2)*2
    crop_x=round((zw-width)*(1-(effect or {}).get("panX",0))/2)
    crop_y=round((zh-height)*(1-(effect or {}).get("panY",0))/2)
    return width,height,top,zw,zh,crop_x,crop_y


def zoom_move_vf(effect, width, height, zw, zh, crop_x, crop_y, frames=0):
    """영상 칸 확대 필터. zoomIn>0 이면 장면 시작부터 zoomIn초 동안 1배→zoom 배로 **움직이며** 확대(관제 124, 사장님
    2026-10-05 "그냥 확대 장면을 보여주는 건 의미가 없다, 0.5초로 제품에 확대되는 거"). 곡선은 1-(1-t)² (처음 빠르고 끝에서 멈춤) —
    편집기 미리보기(scene-style-connect.js, cubic-bezier(.5,1,.89,1) = 같은 곡선)와 짝. 도착점은 멈춘 확대와 같은 자리(panX·panY).
    zoompan 은 정수 좌표라 떨리므로 2배로 키운 뒤 돌린다. 반환: crop 뒤에 이어 붙일 필터 문자열."""
    move=float((effect or {}).get("zoomIn") or 0)
    zoom=zw/max(1,width)
    if move<=0 or zoom<=1.0001:
        return f"scale={zw}:{zh},crop={width}:{height}:{crop_x}:{crop_y}"
    n=max(1,round(move*30))
    fx=crop_x/max(1,zw-width); fy=crop_y/max(1,zh-height)          # 도착했을 때 잘리는 자리(0~1)
    way=(effect or {}).get("zoomMove") or "in"
    N=max(n+1,int(frames or 0))
    if way=="pull":      # 장면 내내 쭉 당기기 — 처음·끝이 부드러운 3t²-2t³ (사장님 "2배로 쭉 땡기면서 집중")
        e=f"(3*pow(min(1,on/{N-1}),2)-2*pow(min(1,on/{N-1}),3))"
    elif way=="inout":   # 들어가고, 끝에서 원본 크기로 돌아온다(사장님 "다시 원본 크기로 돌아오기")
        n=max(1,min(n,int(N*0.4)))   # 짧은 장면(1초 이하)도 반드시 돌아오게 — 들어가기·돌아오기를 장면의 40%까지(zoom_curve·편집기와 같은 규칙)
        b=f"max(0,(on-{N-n})/{n})"
        e=f"((1-pow(1-min(1,on/{n}),2))*(1-(3*pow({b},2)-2*pow({b},3))))"
    else:
        e=f"(1-pow(1-min(1,on/{n}),2))"
    return (f"scale={width*2}:{height*2},zoompan=z='1+{zoom-1:.5f}*{e}':x='(iw-iw/zoom)*{fx:.5f}':y='(ih-ih/zoom)*{fy:.5f}'"
            f":d=1:s={width}x{height}:fps=30")


def shock_vf(effect, width, height):
    """흑백 충격(관제 124, 사장님 2026-10-05 "흑백은 충격·잘못된 비포 장면에, 흑백과 지지직 효과·약간 흔들리는 느낌") — 영상 칸에만.
    흑백+대비 · 필름 잡티(noise) · 흔들림(프레임마다 ±1.2% 이동) · 지지직(13프레임마다 2프레임 크게 찢기듯 밀림+번쩍).
    흔들려도 가장자리가 안 보이게 6% 키워 두고 자른다. 편집기 미리보기(scene-style-connect.js)는 같은 모양을 CSS로 흉내 낸다."""
    if not (effect or {}).get("shock"):
        return ""
    g="lt(mod(n,13),2)"
    bw,bh=round(width*1.06/2)*2,round(height*1.06/2)*2
    return (f",hue=s=0,eq=contrast=1.28:brightness=-0.03,noise=c0s=22:c0f=t,scale={bw}:{bh},"
            f"crop={width}:{height}:x='(iw-ow)/2+ow*(0.012*sin(n*12.9898)+{g}*0.045*sin(n*7.31))'"
            f":y='(ih-oh)/2+oh*0.009*sin(n*78.233)',eq=brightness=0.16:enable='{g}'")


def dim_of(effect, frames):
    """장면 영상 칸을 어둡게 하는 값 — 완성본(compose)·썸네일(compose_still)·캡컷(dim_spans)이 같이 쓴다(관제 124).
    반환 (밝기 0.1~1, 어둡게 할 프레임 수) 또는 None. 장면 시작부터 sec초(0이면 장면 내내, frames 로 자른다)."""
    dim=(effect or {}).get("dim")
    if not isinstance(dim,dict):
        return None
    level=float(dim.get("level") or 1)
    if level>=1:
        return None
    sec=float(dim.get("sec") or 0)
    n=frames if sec<=0 else min(frames,max(1,round(sec*30)))
    return level,n


def dim_spans(scenes, snapshot, layers, folder):
    """캡컷용 어둡게 구간 [{path,start,end}] — 영상 칸 자리만 반투명 검정 PNG(투명도 1-밝기).
    완성본은 영상에 밝기를 곱하고, 캡컷은 같은 구간에 검정 막을 얹는다(같은 dim_of)."""
    from PIL import Image
    from . import video_assemble as va
    folder,out=Path(folder),[]
    effects=(validate_snapshot(snapshot) or {}).get("effects") or {}
    for index,(scene,layer) in enumerate(zip(scenes,layers)):
        if not layer:
            continue
        start,end=float(scene["start"]),float(scene["end"])
        frames=round(end*30)-round(start*30)
        got=dim_of(effects.get(str(index)),frames)
        if not got:
            continue
        level,n=got
        _,height,top,*_=media_geometry(layer,effects.get(str(index)))
        img=Image.new("RGBA",(va._OUT_W,va._OUT_H),(0,0,0,0))
        img.paste((0,0,0,round(255*(1-level))),(0,top,va._OUT_W,top+height))
        path=folder/f"scene-style-dim-{index}.png";img.save(path)
        out.append({"path":str(path),"start":start,"end":min(end,start+n/30)})
    return out


def zoom_curve(t, dur, zoom, way="in", zoom_in=0.5):
    """장면 시작부터 t초에서의 확대 배율 — 완성본 zoom_move_vf(ffmpeg 식)와 같은 곡선을 캡컷 키프레임용으로(관제 124).
    in: 1-(1-u)² (u=t/zoom_in) · pull: 3u²-2u³ (u=t/dur) · inout: in 곡선 × (1 - 끝 zoom_in 초의 3b²-2b³)."""
    if zoom <= 1.0001 or zoom_in <= 0:
        return zoom
    clamp = lambda x: max(0.0, min(1.0, x))
    if way == "pull":
        u = clamp(t / max(1e-6, dur)); e = 3 * u * u - 2 * u ** 3
    else:
        if way == "inout":
            zoom_in = max(1 / 30, min(zoom_in, int(dur * 30 * 0.4) / 30))   # 짧은 장면도 돌아오게(zoom_move_vf 와 같은 규칙)
        u = clamp(t / zoom_in); e = 1 - (1 - u) ** 2
        if way == "inout":
            b = clamp((t - (dur - zoom_in)) / zoom_in); e *= 1 - (3 * b * b - 2 * b ** 3)
    return 1 + (zoom - 1) * e


def shock_spans(scenes, snapshot):
    """캡컷용 흑백 충격 구간 [{start,end}] — 캡컷 초안은 채도·대비·밝기·위치 키프레임으로 흉내 낸다(완성본 shock_vf 와 짝)."""
    effects=(validate_snapshot(snapshot) or {}).get("effects") or {}
    return [{"start":float(sc["start"]),"end":float(sc["end"])} for i,sc in enumerate(scenes) if (effects.get(str(i)) or {}).get("shock")]


def capcut_fx_spans(scenes, snapshot, layers=None):
    """캡컷 내보내기가 받는 장면 효과 구간 하나로(관제 124) — 확대(zoom_spans)와 흑백 충격(shock_spans)을 장면별로 합친다.
    한 장면에 둘 다 켜면(사장님 '중복으로 선택') 한 구간에 zoom·move·shock 를 같이 싣는다(캡컷 조각 하나에 키프레임을 같이 찍게)."""
    out = [dict(sp) for sp in zoom_spans(scenes, snapshot, layers)]
    for sh in shock_spans(scenes, snapshot):
        hit = next((sp for sp in out if abs(sp["start"] - sh["start"]) < 1e-6 and abs(sp["end"] - sh["end"]) < 1e-6), None)
        if hit:
            hit["shock"] = True
        else:
            out.append({**sh, "zoom": 1.0, "shock": True})
    return out


def zoom_spans(scenes, snapshot, layers=None):
    """캡컷용 장면별 영상 확대 구간 [{start,end,zoom,tx,ty}] (관제 124 점프 줌·강조 확대 + 손으로 맞춘 확대).
    배율 뜻은 완성본과 같은 video_assemble.scene_zoom_of 한 곳. 이동(tx,ty)은 캡컷 clip.transform —
    단위 '캔버스 절반'(pyJianYingDraft ClipSettings: 水平位移 单位为半个画布宽, 자막 기본 -0.8 → 위가 +).
    완성본(media_geometry)이 화면을 미는 픽셀만큼 민다: x = panX·(z-1), y = -panY·(z-1)·영상칸높이비율.
    ★캡컷 초안은 원래 영상을 전체 화면에 깔아 완성본(영상 칸)과 구도가 조금 다르다 — 그 차이는 그대로다(관제 018)."""
    from . import video_assemble as va
    effects=(validate_snapshot(snapshot) or {}).get("effects") or {}
    out=[]
    for index,scene in enumerate(scenes):
        effect=effects.get(str(index)) or {}
        zoom,_,_=va.scene_zoom_of({"scene_zoom":effect.get("zoom",1)})
        if zoom>1.0001:
            frac=((layers[index] or {}).get("media") or {}).get("height",100)/100 if layers and index<len(layers) else 1.0
            out.append({"start":float(scene["start"]),"end":float(scene["end"]),"zoom":zoom,
                        "tx":round(float(effect.get("panX",0))*(zoom-1),4),
                        "ty":round(-float(effect.get("panY",0))*(zoom-1)*frac,4),
                        # 확대 움직임(관제 124) — 캡컷은 이 값으로 크기·위치 키프레임을 찍는다(zoom_curve)
                        "move":effect.get("zoomMove","in"),"zoomIn":float(effect.get("zoomIn") or 0)})
    return out


def compose_still(frame_path, timeline, snapshot, work, index, out_path, headcopy=None, job_id=None):
    """장면 하나를 **완성본과 같은 구도**의 정지 그림(1080×1920)으로 만든다 — 썸네일 후보(2026-09-26 사장님 "썸네일로 보냈는데 비율이 안 맞는다").
    ★여태 핀은 원본 프레임 전체(9:16) 위에 레이어를 그냥 얹어, 영상 칸(media)에 맞춰 줄이지 않았다 —
      제목 띠가 원본 윗부분(얼굴)을 덮고 아랫부분만 보였다. 여기선 compose의 ffmpeg 필터와 같은 기하(media_geometry)로 앉힌다."""
    from PIL import Image
    from . import video_assemble as va
    snapshot=validate_snapshot(snapshot)
    layer_png=render_layer_one(timeline,snapshot,work,index,headcopy,job_id)
    layers=json.loads((Path(work).resolve()/"scene-style-layers.json").read_text(encoding="utf-8"))
    layer=layers[int(index)]
    effect=(snapshot.get("effects") or {}).get(str(index)) or {}
    width,height,top,zw,zh,crop_x,crop_y=media_geometry(layer,effect)
    src=Image.open(frame_path).convert("RGB")
    s=max(width/src.width,height/src.height)                    # scale=W:H:force_original_aspect_ratio=increase
    cw,ch=max(width,round(src.width*s)),max(height,round(src.height*s))
    img=src.resize((cw,ch),Image.LANCZOS)
    img=img.crop(((cw-width)//2,(ch-height)//2,(cw-width)//2+width,(ch-height)//2+height))   # crop=W:H (가운데)
    img=img.resize((zw,zh),Image.LANCZOS).crop((crop_x,crop_y,crop_x+width,crop_y+height))
    if effect.get("shock"):   # 흑백 충격 장면 썸네일은 흑백(완성본 첫 프레임과 같은 색)
        img=img.convert("L").convert("RGB")
    if dim_of(effect,1):   # 썸네일 = 장면 첫 프레임 — 완성본도 장면 시작부터 어둡다(관제 124)
        level=dim_of(effect,1)[0];img=img.point(lambda v:round(v*level))
    canvas=Image.new("RGBA",(width,va._OUT_H),(0,0,0,255))    # pad=W:OUT_H:0:top:black
    canvas.paste(img,(0,top))
    over=Image.open(layer_png).convert("RGBA")
    if over.size!=canvas.size:
        over=over.resize(canvas.size)
    Image.alpha_composite(canvas,over).convert("RGB").save(str(out_path),quality=92)
    return out_path


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
        effect=(snapshot.get("effects") or {}).get(str(index)) or {}
        width,height,top,zw,zh,crop_x,crop_y=media_geometry(layer,effect)
        dim=dim_of(effect,last_frame-first_frame)   # 어둡게(관제 124) — 영상 칸에만, 틀·자막 레이어는 밝게 남는다
        dim_f=(f",colorchannelmixer=rr={dim[0]:.3f}:gg={dim[0]:.3f}:bb={dim[0]:.3f}:enable='lt(n,{dim[1]})'" if dim else "")
        vf=f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},{zoom_move_vf(effect,width,height,zw,zh,crop_x,crop_y,last_frame-first_frame)}{shock_vf(effect,width,height)}{dim_f},pad={width}:{va._OUT_H}:0:{top}:black,setsar=1"
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
