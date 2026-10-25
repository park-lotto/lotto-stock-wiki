# 뜨거운사람들 줄판독 spec 공용 꼴(06 워커 10-25) — spec 파일이 import 한다. 측정 도구 아님:
# 이미 잰 readline_tools 결과(capseg --mode dark·cutdet --v2, C:/숏템_칼카피/hotpeople/work/lr6)를 줄 칸으로 옮겨 적을 뿐.
# 이 채널 자막 = 흰 바탕 위 검정 글(외곽 없음) → build_lr.measure(밝은 채움+검정 외곽)가 흰 바탕을 잡으므로 y·fill_hex 는 capseg dark 덩어리 값을 ex 로 넘긴다.
import json
WORK = "C:/숏템_칼카피/hotpeople/work/lr6"
WIN = [0, 484, 1080, 788]
RED = "#E71D21"        # 1판 픽셀(09-25 역분석 §2, RGB 231,29,33) — 이번 px 도구는 외곽 없는 빨강 글을 못 가른다
HL = "#F8EDA5"         # 형광펜 띠 — px box bg13-25px 실측(BzMW t=1.5) · px clusters #F2EDA6
V0 = "기본(검정·흰 바탕)"
VH = "형광펜(옅은 노랑 둥근 띠 뒤 검정 글)"


def layout(title, logo=True, hide_after=None, note=""):
    return {"window": WIN, "caption_band": [1278, 1478], "title_y": [[205, 470]], "bg_hex": "#FAFAFA",
            "source_y": None, "logo_y": [91, 195] if logo else None, "watermark": None, "source_hex": None,
            "headline": title, "headline_hide_after": hide_after,
            "note": "흰 바탕 + 좌상단 원형 불꽃 로고 '뜨거운 사람들 @HotPeople'(y91~195) + 2줄 헤드라인(y≈205~470, 한 줄/낱말 빨강) + 가로 영상 창 y484~1272(1080×788) + 창 아래 흰 바탕 검정 자막 1~2줄(y≈1280~1440) " + note}


def title(l1, l2, red2=True, red_words=None):
    c2 = [{"word": l2, "hex": RED if red2 else "#000000"}]
    out = [{"text": l1, "colors": [{"word": l1, "hex": "#000000"}]}, {"text": l2, "colors": c2}]
    if red_words:
        out[0]["colors"] = [{"word": w, "hex": RED} for w in red_words] + [{"word": l1, "hex": "#000000"}]
    return out


def em(*words):
    return [{"word": w, "hex": RED, "grow": None, "outline": None} for w in words]


def st(what, x, y, w, t_in, t_out, anim):
    return {"what": what, "x": x, "y": y, "w": w, "t_in": t_in, "t_out": t_out, "anim": anim}


def L(a, b, text, role, desc, fit, scene="기타", emph=None, hl=False, sticker=None, **ex):
    return [a, b, "나레", text, role, "cut", VH if hl else V0, emph or [], sticker or [], scene, desc, fit, ex]


def finish(vid, lines):
    """capseg(dark) 덩어리 y·hex · cutdet v2 전환(줄 시작 ±0.15초)·샷 motion 을 ex 로 — spec 이 이미 적은 값이 이긴다."""
    segs = json.load(open(f"{WORK}/seg_{vid}.json"))
    cd = json.load(open(f"{WORK}/cut_{vid}.json"))
    out = []
    for L_ in lines:
        a, b = L_[0], L_[1]
        ex = dict(L_[12])
        best = max(segs, key=lambda s: min(b, s["t1"]) - max(a, s["t0"]))
        ex.setdefault("y", best["yr"])
        ex.setdefault("fill_hex", best["hex"])
        if "transition" not in ex:
            near = [c for c in cd["cuts"] if abs(c["t"] - a) <= 0.15]
            ex["transition"] = near[0]["kind"] if near else ("cut" if a == 0 else "none")
            if near and near[0]["kind"] == "zoomblur":   # 표준 §11-2 ⑯ — 세기(흐린 프레임 수) 기록, 마스크 자(라플라시안 하락)는 02 몫
                c = near[0]
                ex["transition_strength"] = {"blur_frames": c.get("blurfr"), "pre": c.get("blur_pre"), "post": c.get("blur_post"),
                                             "basis": "cutdet --v2 창 라플라시안(자막 띠 밖이라 마스크 불필요) · 눈 확인 tc_*.jpg"}
        if "motion" not in ex:
            mid = (a + b) / 2
            sh = [s for s in cd["shots"] if s["t0"] <= mid < s["t1"]]
            ex["motion"] = sh[0].get("motion", "cam") if sh else "cam"
        ex.setdefault("enter_ms", 0)
        ex.setdefault("exit", "cut")
        out.append(tuple(L_[:12]) + (ex,))
    return out


SOUND_MODE = "자막+배경음(나레 목소리 없음 — 유튜브 자동자막 ko 없음·1판 Whisper 2편 BGM 가사만)"
LAYER = "채널자막"
FONT = {"name": "배민 주아체(BMJUA) 계열 굵게 — 잠정", "basis": "1판 렌더 대조 IoU 0.638(09-25 역분석 §2) — 이번에 다시 안 잼"}
HAND_FONT = {"name": "해당 없음", "basis": "손글씨 줄 없음"}
MADE_BY = "오푸스 실행자 줄판독(눈: segsheet·1초 장면 시트·1프레임 rangesheet / 픽셀: capseg --mode dark·cutdet --v2·px box) 2026-10-25 (관제 263 지시서 06 · hotpeople)"
