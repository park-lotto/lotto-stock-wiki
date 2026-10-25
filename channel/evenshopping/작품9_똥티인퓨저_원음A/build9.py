# -*- coding: utf-8 -*-
"""작품9 똥티인퓨저 원음 A·B·C 대본.json·재료.json 만들기 (한 곳에서 세 변형)."""
import json, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
SRC = "C:/숏템_칼카피/evenshopping/작품9_똥티인퓨저/src/"
DIM = {"3OHcfkmJusQ": (1080, 1920), "GP6L6Ois1OM": (576, 1024), "MyNgVrGjzx0": (1080, 1920), "Qkqtrq6X8lQ": (1080, 1920),
       "S2QPMWxwtY4": (720, 1280), "YZkIOvmlPmk": (720, 1280), "iCvxf-gZo7c": (720, 1280), "n4xmjLN59W8": (1080, 1920),
       "qcmSDsbfIQg": (720, 720), "sAzdqJD3Bzk": (1080, 1920), "xAWWztiN2H0": (1080, 1920)}
Y = {"3OHcfkmJusQ": 150, "iCvxf-gZo7c": 330, "GP6L6Ois1OM": "cap"}   # 남의 글자·얼굴 띠 피하기
BED = {"iCvxf-gZo7c", "GP6L6Ois1OM"}   # 소리가 현장음·반응인 원본만(나머지는 배경음악·남의 설명 나레)
R = 1080 / 1407


def crop(v):
    w, h = DIM[v]
    if Y.get(v) == "cap":            # 위쪽 영어 자막 띠(높이 12~35%) 밖
        ch = 655; cw = int(ch * R) // 2 * 2
        return [(w - cw) // 2, h - ch, cw, ch]
    ch = min(h, int(w / R)); cw = int(ch * R) // 2 * 2
    y = Y.get(v, (h - ch) // 2)
    return [(w - cw) // 2, y, cw, ch]


def shot(cap, v, ss, see, cont=False, orig=False):
    if cont:
        return {"caption": cap, "cont": True, "src": "+"}
    r = {"caption": cap, "kind": "product", "cont": cont, "seen": see, "url": f"https://www.youtube.com/shorts/{v}",
         "src": SRC + v + ".mp4", "ss": ss, "src_crop": crop(v)}
    if v in BED:
        r["bed"] = True
    if orig:
        r["orig"] = True
    return r

ORIG = {
    "disgust": {"src": "iCvxf-gZo7c.mp4", "spans": [[3.05, 5.33]], "text": "“아, 역겨운 냄새…”", "en": "Ah, the smell of disgusting",
                "see": "똥 인퓨저 걸린 컵에 차가 우러나는 장면(원음 그 자리)", "ss": 3.05, "emph": "역겨운 냄새"},
    "goose": {"src": "GP6L6Ois1OM.mp4", "spans": [[10.2, 12.15]], "text": "“와, 소름 돋았어!”", "en": "I have goosebumps",
              "see": "주황 찻물이 가득 우러난 컵(원음 그 자리)", "ss": 10.2, "emph": "소름 돋았어"},
}
OCOL = "#7FD3FF"   # 원음 번역 자막 색(나레 강조 #54C09F 와 다른 색)


def L(text, role, shots, tts=None, emph=None):
    return {"text": text, "tts": tts or text, "role": role, "shots": shots, **({"emph": emph} if emph else {})}


def O(key):
    o = ORIG[key]
    return {"kind": "orig", "src": o["src"], "spans": o["spans"], "text": o["text"], "role": "orig", "orig_en": o["en"],
            "emph": [{"word": o["emph"], "color": OCOL}],
            "shots": [shot(o["text"], o["src"][:-4], o["ss"], o["see"], orig=True)]}


def lines(variant):
    out = []
    out.append(L("전 세계 차 마니아들 기립박수 치게 만든 천재의 발명품.", "title", [
        shot("전 세계 차 마니아들", "3OHcfkmJusQ", 8.0, "빨간 천 위 컵에 엉덩이 걸고 똥 인퓨저가 물에 잠긴 모습"),
        shot("기립박수 치게 만든", "Qkqtrq6X8lQ", 26.6, "남자가 똥 인퓨저 차를 마시고 활짝 웃는 얼굴"),
        shot("천재의 발명품.", "+", 0, "", cont=True)], emph=["천재의 발명품"]))
    if variant == "A":
        out.append(L("생긴 건 딱 장난감인데 처음 본 사람 반응이 이래.", "bait", [
            shot("생긴 건 딱 장난감인데", "qcmSDsbfIQg", 2.0, "말랑한 엉덩이 장난감을 손으로 쥐는 장면"),
            shot("처음 본 사람", "Qkqtrq6X8lQ", 5.6, "남자가 인퓨저 냄새를 맡으며 찡그림"),
            shot("반응이 이래.", "+", 0, "", cont=True)]))
        out.append(O("disgust"))
    else:
        out.append(L("생긴 건 딱 장난감인데 SNS에서 난리라는데,", "bait", [
            shot("생긴 건 딱 장난감인데", "qcmSDsbfIQg", 2.0, "말랑한 엉덩이 장난감을 손으로 쥐는 장면"),
            shot("SNS에서 난리라는데,", "iCvxf-gZo7c", 4.15, "똥 인퓨저 걸린 컵에 차가 우러남(원음 질색 소리가 낮게 깔림)")], emph=["난리"]))
        if variant == "B":   # 깔기형은 원음 단독 줄이 없어 25초 미달 — 깔린 반응 소리를 받는 줄 하나(질색·감탄 원본 컷)
            out.append(L("보는 사람마다 질색하다가도 결국 소름 돋는다는데,", "bait2", [
                shot("보는 사람마다", "Qkqtrq6X8lQ", 5.6, "남자가 인퓨저 냄새를 맡으며 찡그림"),
                shot("질색하다가도", "+", 0, "", cont=True),
                shot("결국 소름 돋는다는데,", "GP6L6Ois1OM", 10.2, "주황 찻물이 가득 우러난 컵(원음 'I have goosebumps'가 낮게 깔림)")],
                emph=["소름"]))
    out.append(L("근데 반전은 이게 장난감이 아니라 진짜 똥 모양 티 인퓨저라는 거.", "reveal", [
        shot("근데 반전은 이게", "MyNgVrGjzx0", 0.3, "엉덩이·똥 인퓨저를 열어 찻잎을 담는 손"),
        shot("장난감이 아니라", "+", 0, "", cont=True),
        shot("진짜 똥 모양", "3OHcfkmJusQ", 3.0, "똥 인퓨저를 열어 찻잎을 담는 손"),
        shot("티 인퓨저라는 거.", "+", 0, "", cont=True)], emph=["반전은", "티 인퓨저"]))
    out.append(L("근데 진짜 놀라운 건 컵에 걸면 똥이 변기에 앉은 모양이 된다는 거.", "point", [
        shot("근데 진짜 놀라운 건", "GP6L6Ois1OM", 3.6, "똥 인퓨저를 물컵에 내려 거는 장면"),
        shot("컵에 걸면 똥이", "+", 0, "", cont=True),
        shot("변기에 앉은 모양이", "sAzdqJD3Bzk", 0.0, "컵 가장자리에 엉덩이가 앉고 속에 똥이 잠긴 모습"),
        shot("된다는 거.", "+", 0, "", cont=True)], emph=["변기에 앉은"]))
    out.append(L("심지어 실리콘이라 펄펄 끓는 물을 부어도 멀쩡하고,", "more", [
        shot("심지어 실리콘이라", "S2QPMWxwtY4", 3.0, "말랑한 실리콘 인퓨저를 벌려 찻잎을 담음"),
        shot("펄펄 끓는 물을", "qcmSDsbfIQg", 24.0, "인퓨저 걸린 유리잔에 김 나는 뜨거운 물을 붓는 장면"),
        shot("부어도 멀쩡하고,", "+", 0, "", cont=True)], emph=["실리콘"]))
    out.append(L("이게 미친 포인트인 게 물 부으면 찻물이 진짜 똥물처럼 스멀스멀 우러나버림.", "climax", [
        shot("이게 미친 포인트인 게", "sAzdqJD3Bzk", 9.0, "똥 인퓨저 걸린 컵에 물을 붓는 장면"),
        (shot("물 부으면 찻물이", "YZkIOvmlPmk", 4.9, "금색 머그에 똥 인퓨저를 걸어 둔 모습") if variant == "B" else
         shot("물 부으면 찻물이", "n4xmjLN59W8", 5.5, "물컵에 똥 인퓨저가 잠김")),
        shot("진짜 똥물처럼", "Qkqtrq6X8lQ", 19.45, "구멍 사이로 검은 찻물이 구름처럼 피어오르는 근접"),
        shot("스멀스멀 우러나버림.", "+", 0, "", cont=True)], emph=["똥물처럼", "스멀스멀"]))
    if variant in ("A", "C"):
        out.append(L("이걸 본 사람 반응은?" if variant == "A" else "이 똥물 차를 처음 본 사람 반응은?", "bridge", [
            shot("이걸 본 사람 반응은?", "xAWWztiN2H0", 0.5, "남자가 변기 앞에서 들여다보는 반응")] if variant == "A" else [
            shot("이 똥물 차를", "xAWWztiN2H0", 0.3, "남자가 변기 앞에서 들여다보는 반응"),
            shot("처음 본 사람 반응은?", "+", 0, "", cont=True)]))
        out.append(O("goose"))
    out.append(L(("근데 웃긴 건 " if variant == "B" else "근데 ") + "이 똥물 차로 떼돈을 벌었다고.", "end", [
        *([shot("근데 웃긴 건", "n4xmjLN59W8", 9.25, "엉덩이 걸린 컵에 주황 찻물이 우러나는 모습"),
           shot("이 똥물 차로", "qcmSDsbfIQg", 40.6, "노랗게 다 우러난 차, 엉덩이를 들어 인퓨저를 꺼냄")] if variant == "B" else
          [shot("근데 이 똥물 차로", "qcmSDsbfIQg", 40.6, "노랗게 다 우러난 차, 엉덩이를 들어 인퓨저를 꺼냄")]),
        shot("떼돈을 벌었다고.", "+", 0, "", cont=True)], emph=["떼돈"]))
    return out


SNAP = {"presetId": "s0101", "captionPack": "clean", "motionPack": "1", "hookMotion": "zoom-punch", "hookBandMotion": "rise"}
for v, name in (("A", "번갈아"), ("B", "깔기"), ("C", "혼합")):
    d = ROOT / f"작품9_똥티인퓨저_원음{v}"
    d.mkdir(parents=True, exist_ok=True)
    ls = lines(v)
    rows = []
    for l in ls:
        rows += l.pop("shots")
    S = {"채널": "재미썸홈", "channel": "재미썸홈", "preset": "channel/evenshopping/preset/숏템템플릿/manifest.json",
         "topic": "똥 모양 티 인퓨저(나레+원음 " + name + "형)", "variant": f"원음{v}_{name}",
         "voice": {"name": "진우", "voice_id": "tc_632293f759d649937b97f323"},
         "desktop_title": f"똥티인퓨저_원음{v}_{name}",
         "title_slots": {"hook1": "차 마니아 기립박수", "hook2": "천재의 발명품", "bodyTitle": "똥물 우러나는 티 인퓨저?"},
         "snapshot": SNAP, "lines": ls}
    if v in ("B", "C"):
        S["source_audio"] = {"keep": True, "volume": 30, "duck_db": 14}
    (d / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "재료.json").write_text(json.dumps({"_note": f"작품9 똥티인퓨저 원음{v} — build9.py", "cand_dir": SRC, "shots": rows},
                                            ensure_ascii=False, indent=1), encoding="utf-8")
    print(d, len(ls), "줄", len(rows), "행")
