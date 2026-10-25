# 아이템홈 줄판독 spec 공용 꼴(06 워커 10-25) — spec 파일이 import 한다. 측정 도구 아님(값을 줄 튜플로 만드는 글꼴 + cutdet --v2 결과 읽기만).
import json
WIN = [0, 480, 1080, 1440]
WORK = "C:/숏템_칼카피/itemhome/work/lr6"
def layout(title_y):
    return {"window": WIN, "caption_band": [1209, 1325], "title_y": title_y, "bg_hex": "#090000",
            "source_y": None, "logo_y": None, "watermark": None, "source_hex": None,
            "note": "검정 바탕 + 위 2줄 제목(1줄 흰·2줄 노랑, 굵은 고딕) + 영상 창 y480~1920(세로 1440) + 창 안 자막 1줄(나레 = 굵은 흰+강조 노랑/분홍, 원음 = “ ” 기울인 흰+강조 노랑/분홍) · 화면 출처 표기 없음(설명란 '출처:')"}
def title(l1, l2):
    return [{"text": l1, "colors": [{"word": l1, "hex": "#FCFAFB"}]},
            {"text": l2, "colors": [{"word": l2, "hex": "#FBED03"}], "note": "2줄 통째 노랑(1판 8/8)"}]
NV = "나레(굵은 흰)"; QV = "원음(“ ” 기울인 흰)"
POP = "pop"   # 작게→제 크기(2~4프레임) — 자막 없는 틈 다음 덩어리에서만 보임(capseg 잉크 증가로 확인)
def n(a, b, t, role, desc, fit, scene="얼굴", enter="cut", emph=None, **ex):
    return (a, b, "나레", t, role, enter, NV, emph or [], [], scene, desc, fit, ex)
def o(who, a, b, t, role, desc, fit, scene="얼굴", enter="cut", emph=None, sticker=None, **ex):
    return (a, b, "원음:" + who, t, role, enter, QV, emph or [], sticker or [], scene, desc, fit, ex)
def em(word, hexv):
    return {"word": word, "hex": hexv, "grow": None, "outline": "검정(줄과 같음)"}
WHITE = "#FFFCFA"
YEL = "#F4F91E"; PINK = "#F9B4C0"; RED = "#F93E3D"
def with_motion(vid, lines, zb_real=()):
    """cutdet --v2 샷 광류 motion 을 줄 가운데 시각으로 ex.motion 에(spec 에 motion 이 있으면 그것). 'still?' → still."""
    c = json.load(open(f"{WORK}/{vid}/cut_{vid}.json"))
    out = []
    for L in lines:
        L = list(L)
        ex = dict(L[12]) if len(L) > 12 else {}
        mid = (L[0] + L[1]) / 2
        if "fill_hex" not in ex:      # 바탕 글자색 = px clusters 흰 묶음(Mfpt 0.3/2.5/5.3/12.5/18.4초 #FFFDFA·#FEFCFD·#FFFCFA·#FFFDFA·#FEFBFD 중앙) — 줄 전체가 강조면 강조색
            whole = [e for e in L[7] if e["word"].replace(" ", "") == L[3].replace(" ", "")]
            ex["fill_hex"] = whole[0]["hex"] if whole else WHITE
        zb = [x for x in c["cuts"] if x["kind"] == "zoomblur" and (abs(x["t"] - L[0]) <= 0.05 or x["t"] - 0.05 <= L[0] <= x["t_end"] + 0.05)]
        if zb and "transition" not in ex and not any(abs(x["t"] - z) < 0.05 for x in zb for z in zb_real):
            ex["transition"] = "cut"   # cutdet --v2 zoomblur 를 1프레임 창 시트(work/lr6/<id>/zb*.jpg)로 눈 확인 → 하드컷(원본 소프트포커스·흔들림 흐림)
            ex["transition_note"] = f"cutdet v2 zoomblur({zb[0]['t']}) → 1프레임 시트 눈 확인 하드컷(원본 흐림, 전환 효과 아님)"
        if "motion" not in ex:
            m = next((s.get("motion") for s in c["shots"] if s["t0"] <= mid < s["t1"]), None) or "cam"
            ex["motion"] = m.rstrip("?")
        while len(L) < 13:
            L.append({})
        L[12] = ex
        out.append(tuple(L))
    return out
