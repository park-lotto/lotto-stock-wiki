# 만템 줄판독 spec 공용 꼴(06 워커 10-25) — spec 파일이 import 한다. 측정 도구 아님(값을 줄 튜플로 만드는 글꼴만).
WIN = [0, 420, 1080, 1080]
def layout(title_y, credit):
    return {"window": WIN, "caption_band": [1226, 1390], "title_y": title_y, "bg_hex": "#000000",
            "source_y": [1518, 1557], "logo_y": None, "watermark": None, "source_hex": "#FFFFFF",
            "credit_text": credit,
            "note": "검정 바탕 + 2줄 제목(1줄 흰·2줄 민트+끝 낱말 연노랑, 기울임) + 정사각 영상 창 y420~1500 + 창 안 자막(나레 노랑 위 y≈1226 · 원음 아래 y≈1322) + 창 아래 '출처 : <원본 채널>' 흰 32px"}
def title(l1, l2, last):
    return [{"text": l1, "colors": [{"word": l1, "hex": "#FDFDFD"}]},
            {"text": l2, "colors": [{"word": l2.replace(last, "").strip(), "hex": "#A6FEF6"}, {"word": last, "hex": "#F9F59D"}],
             "note": "끝 낱말만 연노랑(1판 8/8)"}]
Y = "나레(노랑)"
def n(a, b, t, role, desc, fit, scene="기타", enter="instant", **ex):
    return (a, b, "나레", t, role, enter, Y, [], [], scene, desc, fit, ex)
def o(who, a, b, t, role, desc, fit, scene="얼굴", enter="instant", variant="원음(흰)", emph=None, sticker=None, **ex):
    return (a, b, "원음:" + who, t, role, enter, variant, emph or [], sticker or [], scene, desc, fit, ex)
def em(word, hexv):
    return {"word": word, "hex": hexv, "grow": None, "outline": "검정(줄과 같음)"}
def st(what, x, y, w, t_in, t_out, anim):
    return {"what": what, "x": x, "y": y, "w": w, "t_in": t_in, "t_out": t_out, "anim": anim}
MINT = "#B4FFF2"; YEL = "#F9F98F"; PINK = "#F891B8"
