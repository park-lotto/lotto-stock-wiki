# 안나픽 줄판독 spec 공용 꼴(06 워커 10-25) — spec 파일이 import 한다. 측정 도구 아님(값을 줄 튜플로 만드는 글꼴 + cutdet --v2 결과 읽기만).
import json
WIN = [0, 419, 1080, 1082]
WORK = "C:/숏템_칼카피/annapick/work/lr6"
def layout(title_y, credit, cap_band):
    return {"window": WIN, "caption_band": cap_band, "title_y": title_y, "bg_hex": "#000000",
            "source_y": [1518, 1551], "logo_y": [1748, 1830], "watermark": None, "source_hex": "#7D7D7D",
            "credit_text": credit, "logo_text": "anna pick(회색 2줄)",
            "note": "검정 바탕 + 위 2줄 제목(1줄 흰 “ ”, 2줄 노랑 인물+분홍 제품) + 정사각 창 y419~1501 + 창 안 자막 1줄(자리는 편마다·줄마다 다름) + 창 아래 회색 '출처 : <원본 채널>' + 맨 아래 회색 'anna pick'"}
def title(l1, l2):
    """l1·l2 = [(낱말, hex)…] — 편마다 색 조합이 다르다(흰·하늘 #CEFFFC·연노랑 #FCFFB7·노랑 #FAEB75·분홍 #F375CB, px clusters)."""
    return [{"text": " ".join(w for w, _ in ln), "colors": [{"word": w, "hex": h} for w, h in ln]} for ln in (l1, l2)]
T_W = "#FFFFFF"; T_SKY = "#CEFFFC"; T_LY = "#FCFFB7"; T_Y = "#FAEB75"; T_PK = "#F375CB"
BASE = "기본(굵은 흰 고딕+검정 외곽)"; HAND = "손글씨 가는체(흰)"; ITAL = "기울임(흰)"
def L(spk, a, b, t, role, desc, fit, variant=BASE, scene="얼굴", enter="cut", emph=None, sticker=None, **ex):
    return (a, b, spk, t, role, enter, variant, emph or [], sticker or [], scene, desc, fit, ex)
def n(a, b, t, role, desc, fit, **kw):
    return L("나레", a, b, t, role, desc, fit, **kw)
def em(word, hexv, grow=None):
    return {"word": word, "hex": hexv, "grow": grow, "outline": "검정(줄과 같음)"}
def st(what, x, y, w, t_in, t_out, anim):
    return {"what": what, "x": x, "y": y, "w": w, "t_in": t_in, "t_out": t_out, "anim": anim}
WHITE = "#FFFFFD"; YEL = "#F1FF11"; GRN = "#A7F907"; SKY = "#DFFDFF"; PUR = "#BEB0E9"; CYAN = "#D2F8F8"; PINK = "#F375CB"; RED = "#F93E3D"
def with_motion(vid, lines, zb_real=()):
    """cutdet --v2 샷 광류 motion 을 줄 가운데 시각으로 ex.motion 에 · 바탕 글자색(줄 전체 강조면 강조색) · v2 zoomblur 는 눈 확인 목록(zb_real) 밖이면 cut."""
    c = json.load(open(f"{WORK}/{vid}/cut_{vid}.json"))
    out = []
    for Lx in lines:
        Lx = list(Lx)
        ex = dict(Lx[12]) if len(Lx) > 12 else {}
        mid = (Lx[0] + Lx[1]) / 2
        if "fill_hex" not in ex:
            whole = [e for e in Lx[7] if e["word"].replace(" ", "") == Lx[3].replace(" ", "")]
            ex["fill_hex"] = whole[0]["hex"] if whole else WHITE
        zb = [x for x in c["cuts"] if x["kind"] == "zoomblur" and (abs(x["t"] - Lx[0]) <= 0.05 or x["t"] - 0.05 <= Lx[0] <= x["t_end"] + 0.05)]
        if zb and "transition" not in ex and not any(abs(x["t"] - z) < 0.05 for x in zb for z in zb_real):
            ex["transition"] = "cut"
            ex["transition_note"] = f"cutdet v2 zoomblur({zb[0]['t']}) → 1프레임 시트 눈 확인 하드컷"
        if "motion" not in ex:
            m = next((s.get("motion") for s in c["shots"] if s["t0"] <= mid < s["t1"]), None) or "cam"
            ex["motion"] = m.rstrip("?")
        Lx = Lx[:12] + [ex]
        out.append(tuple(Lx))
    return out
