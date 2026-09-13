# -*- coding: utf-8 -*-
"""사진 검수 — 만든 그림을 **실제로 보고** 판정한다. 볼케이노 `photo_check` 구조를 따른다.

왜 필요한가 (사장님 2026-09-13 "두더지 아니야?"):
  프롬프트에서 낱말을 막는 방식은 계속 샌다. 실제로 두 번 샜다 —
  `computer screen`을 막으니 `digital sign`으로 나왔고, 그걸 막으니 또 다른 표현이 나온다.
  내가 "이런 표현이 나올 것"을 미리 다 적을 수 없기 때문이다.

볼케이노 실측(next_payload.photo_check):
  · 편 A 10장 검사 → **모델에게 보낸 건 1장뿐**. 편 B·C는 0장.
    기계 지표로 먼저 거르고 **의심스러운 것만** 모델에게 보낸다(돈이 든다).
  · 지표: flat(평평한 면 비율)·grad_med(가장자리 세기 중앙값)
    문턱: flat_max=0.55 · grad_med_min=1.0 → 넘으면 why="평평한 면이 넓다"
  · 모델 판정: {"verdict": "accepted|retry", "decisions":[{"visual_kind":"photo|illustration", "reason": …}]}
    실제 판정문: "피부의 모공·주름·눈가 잔주름, 머리카락 한 올 단위의 질감…
                 윤곽선이나 셀 셰이딩 같은 만화·일러스트 특징이 없다"
  · review_policy = {"provider": "client"} — 서버가 아니라 **클라이언트 AI**가 본다. 우리도 같다.
"""
import json
import os

from . import spec


def metrics(path):
    """그림/사진을 가르는 기계 지표 → {"flat", "grad_med", "why"} 또는 None(못 잼).

    flat     — 이웃 픽셀과 차이가 거의 없는 '평평한' 면의 비율. 일러스트는 색면이 넓어 높다.
    grad_med — 가장자리 세기의 중앙값. 사진은 잔질감(모공·직물·머리카락)이 있어 높다.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    from .photos import imread
    img = imread(path)
    if img is None:
        return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    s = 512 / max(h, w)
    if s < 1:
        g = cv2.resize(g, (max(1, int(w * s)), max(1, int(h * s))))
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    flat = float((mag < 4.0).mean())          # 거의 변화 없는 면
    grad_med = float(np.median(mag))
    why = ""
    if flat > spec.PHOTOCHECK_FLAT_MAX:
        why = "평평한 면이 넓다"
    elif grad_med < spec.PHOTOCHECK_GRAD_MIN:
        why = "잔질감이 모자란다"
    return {"file": path, "flat": round(flat, 4), "grad_med": round(grad_med, 4),
            "flat_max": spec.PHOTOCHECK_FLAT_MAX, "grad_med_min": spec.PHOTOCHECK_GRAD_MIN,
            "why": why}


def build_review_request(path, subtitle):
    """모델에게 보낼 질문. 사진 한 장 + 그 컷 자막.

    ★두 가지를 한 번에 묻는다:
      ① 이게 **사진인가 그림인가**(볼케이노가 묻는 것)
      ② 이 사진이 **이 자막에 맞나**(볼케이노는 안 묻는다 — 우리가 더한다)
    """
    return (
        "첨부한 그림 한 장을 보고 판정하라. 추측하지 말고 **보이는 것만** 근거로 삼아라.\n"
        "\n"
        f"[이 그림이 쓰일 자막] «{subtitle}»\n"
        "\n"
        "[판정 1 — 사진인가 그림인가]\n"
        "  photo        실제 카메라로 찍은 것처럼 보인다(피부 모공·직물 주름·머리카락 질감·자연광 명암)\n"
        "  illustration 윤곽선·평면 색면·셀 셰이딩·과장된 비율이 보인다\n"
        "\n"
        "[판정 2 — 읽히는 글자가 있나]\n"
        "  화면에 **읽을 수 있는** 글자·숫자·로고·상호가 있으면 적어라.\n"
        "  ★지어낸 기록은 특히 위험하다: 없는 채널 이름 밑의 구독자 수, 가짜 주가지수, 실존 회사 간판.\n"
        "  흐릿해서 못 읽는 배경 간판은 문제가 아니다.\n"
        "\n"
        "[판정 3 — 자막과 맞나]\n"
        "  자막이 말하는 장소·사람·행동이 그림에 있나. 나라가 어긋나지 않았나.\n"
        "  예: 자막이 «케냐 슬럼가»인데 한국 지하철이면 어긋난 것이다.\n"
        "\n"
        "JSON 하나만 출력하라:\n"
        '{"verdict": "accepted 또는 retry", "visual_kind": "photo 또는 illustration",'
        ' "legible_text": ["읽히는 글자"], "matches_subtitle": true 또는 false,'
        ' "reason": "보이는 것을 근거로 한 판정 이유"}\n'
    )


def parse_review(raw):
    """모델 응답 → dict. 못 읽으면 '통과'로 둔다 — 검수가 편을 멈추면 안 된다."""
    from .prompt import parse_any
    try:
        d = parse_any(raw)
    except Exception:  # noqa: BLE001
        return {"verdict": "accepted", "reason": "판정을 못 읽어 통과 처리"}
    v = str(d.get("verdict") or "accepted").lower()
    kind = str(d.get("visual_kind") or "photo").lower()
    text = [t for t in (d.get("legible_text") or []) if str(t).strip()]
    match = d.get("matches_subtitle")
    bad = (v == "retry" or kind == "illustration" or bool(text) or match is False)
    return {"verdict": "retry" if bad else "accepted", "visual_kind": kind,
            "legible_text": text, "matches_subtitle": match,
            "reason": str(d.get("reason") or "")[:300]}


def check(files, subtitles, *, reviewer=None, log=print, force_all=True):
    """→ {"checked", "reviewed", "retry": [슬롯…]}

    files      {슬롯: 경로} · subtitles {슬롯: 그 슬롯 자막}
    reviewer   call(prompt, image_path) -> str. 없으면 기계 지표만 본다.
    force_all  기본 True — **전부 모델에게 보낸다**.

    ★볼케이노는 지표로 걸러 10장 중 1장만 보냈지만 **우리는 전수로 본다**. 왜:
      · 우리가 잡으려는 건 볼케이노가 안 보는 것이다 — 지어낸 간판·수치, 자막과 어긋난 장면.
        그건 **잘 그려진 사진**이라 그림/사진 지표에 안 걸린다
        (실측 2026-09-13: 가짜 주가지수 flat 0.177 · 정상 사진 0.035~0.310 — 구분 불가).
      · 우리 그림 39장의 flat 최대가 0.480이라 볼케이노 문턱 0.55로는 **한 장도 안 걸린다**.
        실제로 v8에서 10장 검사에 모델 판정 0장이었다 — 검수가 영영 안 돈다.
      · 값이 싸다: 한 편 10장 전수가 약 1.8원. 이미지 생성비(10장 $0.32)의 0.4%다.
      지표는 버리지 않고 기록만 남긴다 — 나중에 문턱을 정할 근거가 된다.
    """
    out, retry = [], []
    for slot in sorted(files, key=lambda x: int(x)):
        p = files[slot]
        if not p or not os.path.exists(p):
            continue
        m = metrics(p)
        rec = {"slot": slot, "metrics": m}
        suspect = force_all or (m and m.get("why"))
        if suspect and reviewer:
            try:
                raw = reviewer(build_review_request(p, subtitles.get(slot, "")), p)
                rv = parse_review(raw)
            except Exception as e:  # noqa: BLE001 — 검수 실패가 편을 멈추면 안 된다
                log(f"[brainbulb.photocheck] 슬롯 {slot} 검수 실패(통과 처리): {e!r:.70}")
                rv = {"verdict": "accepted", "reason": "검수 호출 실패"}
            rec["review"] = rv
            if rv["verdict"] == "retry":
                retry.append(slot)
                log(f"[brainbulb.photocheck] 슬롯 {slot} 반려 — {rv.get('reason', '')[:70]}")
        out.append(rec)
    log(f"[brainbulb.photocheck] {len(out)}장 검사 · 모델 판정 "
        f"{sum(1 for r in out if 'review' in r)}장 · 반려 {len(retry)}장")
    return {"checked": len(out), "reviewed": out, "retry": retry}
