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

from shopping_shorts.channelkit import spec


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


def quality(path):
    """규격·화질 — 기계로 잰다(막지 않고 기록만). → {"w","h","ratio","blur","why"} 또는 None."""
    try:
        import cv2
    except ImportError:
        return None
    from .photos import imread
    img = imread(path)
    if img is None:
        return None
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(g, cv2.CV_64F).var())
    why = []
    if min(w, h) < spec.PHOTO_MIN_SIDE:
        why.append(f"작다({w}×{h})")
    if blur < spec.PHOTO_BLUR_MIN:
        why.append(f"흐리다({blur:.0f})")
    return {"w": w, "h": h, "ratio": round(w / h, 3) if h else 0,
            "blur": round(blur, 1), "why": " · ".join(why)}


def rules_ask():
    """기준표 → 모델에게 묻는 말. ★여기서만 만든다 — 표에 한 줄 더하면 질문도 따라온다."""
    parts = []
    for r in spec.PHOTO_RULES:
        if r["ask"]:
            parts.append(r["ask"])
    return "\n\n".join(parts)


def rules_json_shape():
    """기준표 → 모델이 돌려줄 JSON 모양."""
    return ('{"verdict": "accepted 또는 retry",'
            ' "visual_kind": "photo 또는 illustration",'
            ' "fabricated_text": ["지어낸 기록만"],'
            ' "who_what": "그림에 실제로 찍힌 것 한 문장",'
            ' "matches_subtitle": true 또는 false,'
            ' "product_ok": true 또는 false,'
            ' "single_scene": true 또는 false,'
            ' "reason": "보이는 것을 근거로 한 판정 이유"}')


def build_review_request(path, subtitle, want="", topic=""):
    """모델에게 보낼 질문. 사진 한 장 + 그 컷 자막 (+ 그 자리에 무엇을 찾으려 했는지 + 소재 한 줄).

    ★`topic` 은 이 편이 무엇에 관한 것인지(제목). 「제품이 맞나」 판정에 필요하다 —
      소재를 모르면 모델이 «이 파우치가 그 제품인가»를 판단할 근거가 없다.

    ★세 가지를 한 번에 묻는다:
      ① 이게 **사진인가 그림인가**(볼케이노가 묻는 것)
      ② **지어낸 기록**이 있나
      ③ 이 사진이 **이 자막에 맞나**(볼케이노는 안 묻는다 — 우리가 더한다)

    ★`want` 는 그 슬롯의 검색어·프롬프트다. 이게 있어야 «무엇을 찾으려 했는데 무엇이 왔나»를
      대조할 수 있다 — 없으면 모델이 사진만 보고 "말이 되네" 하고 넘긴다(아래 실사고).
    """
    return (
        "첨부한 그림 한 장을 보고 판정하라. 추측하지 말고 **보이는 것만** 근거로 삼아라.\n"
        "★답은 반드시 한국어로 쓴다(who_what·reason 포함).\n"
        "\n"
        f"[이 그림이 쓰일 자막] «{subtitle}»\n"
        + (f"[이 자리에 넣으려던 것] {want}\n" if want else "")
        + (f"[소재] {topic}\n" if topic else "")
        + "\n"
        "먼저 한 문장으로 적어라: 이 그림에 **실제로 무엇이 찍혀 있나**(who_what).\n"
        "\n"
        # ★묻는 말은 기준표(spec.PHOTO_RULES)에서만 나온다 — 표에 한 줄 더하면 여기도 따라온다
        + rules_ask()
        + "\n\n"
        "★'이 자리에 넣으려던 것'이 주어졌으면 **그것이 실제로 왔는지** 대조하라.\n"
        "  «검색: 1980년대 어음 용지» 라고 했는데 사람 인터뷰 사진이 왔으면 matches_subtitle=false 다.\n"
        "  «생성 이미지» 라고 적혀 있으면 검색 대조는 건너뛰고 위 기준만 본다.\n"
        "★어느 항목이든 어긋난 것을 적었으면 verdict는 반드시 retry다. 둘을 어긋나게 내지 마라.\n"
        "\n"
        "JSON 하나만 출력하라:\n"
        + rules_json_shape() + "\n"
    )


def parse_review(raw):
    """모델 응답 → dict. 못 읽으면 '통과'로 둔다 — 검수가 편을 멈추면 안 된다."""
    from shopping_shorts.channelkit.prompt import parse_any
    try:
        d = parse_any(raw)
    except Exception:  # noqa: BLE001
        return {"verdict": "accepted", "reason": "판정을 못 읽어 통과 처리"}
    # 옛 이름 호환: legible_text → fabricated_text
    if d.get("legible_text") and not d.get("fabricated_text"):
        d["fabricated_text"] = d["legible_text"]

    # ★어긋난 항목을 **기준표로** 가린다 — 조건을 여기 손으로 적지 않는다.
    #   표에 blocking 항목을 더하면 판정도 자동으로 따라온다(0순위-B).
    failed = []
    for r in spec.PHOTO_RULES:
        if not r["blocking"] or not r["field"] or r["bad"] is None:
            continue
        if r["bad"](d.get(r["field"]), d):
            failed.append(r["key"])

    said_retry = str(d.get("verdict") or "accepted").lower() == "retry"
    text = [t for t in (d.get("fabricated_text") or []) if str(t).strip()]
    return {"verdict": "retry" if (failed or said_retry) else "accepted",
            "failed": failed,                 # ★어느 기준에 걸렸나 — 화면·재시도 사유가 여기서 나온다
            "visual_kind": str(d.get("visual_kind") or "photo").lower(),
            "fabricated_text": text,
            "matches_subtitle": d.get("matches_subtitle"),
            "product_ok": d.get("product_ok"),
            "single_scene": d.get("single_scene"),
            # ★그림에 실제로 무엇이 찍혔는지를 받아 둔다 — 나중에 "왜 통과했나"를 볼 때
            #   판정 이유보다 이게 더 빠르다(실측: 「어음 용지」 자리에 한복 할머니가 왔다).
            "who_what": str(d.get("who_what") or "")[:200],
            "reason": str(d.get("reason") or "")[:300]}


def fail_reason(rv):
    """반려 사유 한 줄 — 다시 만들 때 프롬프트에 붙이고, 화면에도 그대로 쓴다."""
    names = {r["key"]: r["label"] for r in spec.PHOTO_RULES}
    hit = [names.get(k, k) for k in (rv.get("failed") or [])]
    head = " · ".join(hit) if hit else "반려"
    if rv.get("fabricated_text"):
        head += f" ({', '.join(str(t)[:20] for t in rv['fabricated_text'][:2])})"
    return f"{head} — {rv.get('reason', '')[:120]}"


def check(files, subtitles, *, reviewer=None, log=print, force_all=True, wants=None,
          topic="", searched=None):
    """→ {"checked", "reviewed", "retry": [슬롯…]}

    files      {슬롯: 경로} · subtitles {슬롯: 그 슬롯 자막}
    wants      {슬롯: 그 자리에 넣으려던 것} — 검색어나 프롬프트. 있으면 대조에 쓴다.
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
        # ★기록만 하는 두 항목(막지 않는다) — 나중에 문턱을 정할 근거가 된다
        rec = {"slot": slot, "metrics": m, "quality": quality(p),
               "searched": (searched or {}).get(slot)}
        suspect = force_all or (m and m.get("why"))
        if suspect and reviewer:
            try:
                raw = reviewer(build_review_request(p, subtitles.get(slot, ""),
                                                    (wants or {}).get(slot, ""), topic), p)
                rv = parse_review(raw)
            except Exception as e:  # noqa: BLE001 — 검수 실패가 편을 멈추면 안 된다
                log(f"[brainbulb.photocheck] 슬롯 {slot} 검수 실패(통과 처리): {e!r:.70}")
                rv = {"verdict": "accepted", "failed": [], "reason": "검수 호출 실패"}
            rec["review"] = rv
            if rv["verdict"] == "retry":
                retry.append(slot)
                log(f"[brainbulb.photocheck] 슬롯 {slot} 반려 — {fail_reason(rv)[:90]}")
        out.append(rec)
    log(f"[brainbulb.photocheck] {len(out)}장 검사 · 모델 판정 "
        f"{sum(1 for r in out if 'review' in r)}장 · 반려 {len(retry)}장")
    return {"checked": len(out), "reviewed": out, "retry": retry}
