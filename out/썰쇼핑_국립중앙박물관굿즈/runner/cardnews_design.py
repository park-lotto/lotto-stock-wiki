# -*- coding: utf-8 -*-
"""**골라 둔 디자인**을 읽는다 — 소재와 따로 정한다.

■ 왜 이 자리가 있나 (2026-08-17 · 사장님 지적)
    *"디자인만 선택하게 하고, 무엇을 소재로 할지는 사용자가 MCP 에서 하는 게
    제일 간편한 거 아니야?"* — 맞다. 그 전 판은 순서가 거꾸로였다:
    미리보기에서 **이미 만들어 둔 세트**를 골라야 다시 그릴 수 있었으니,
    디자인을 정하려면 먼저 소재가 있어야 했다.

    지금은 이렇게 갈린다.

        미리보기(브라우저)   눈으로 보고 **디자인만** 정한다 → [적용]
        MCP(Claude Code)     소재만 준다 → 서버가 골라 둔 디자인을 그대로 쓴다

■ ★값을 여기서 만들지 않는다
    이 파일은 **읽기만** 한다. 무엇이 유효한 템플릿·강조인지는 서버가 안다.
    읽은 값을 서버에 실어 보내고, 목록 밖 값이면 **서버가 반려한다**.
    실행기가 검사하면 서버가 규격을 고쳐도 안 따라온다.

■ ★없는 것은 없다고 답한다
    골라 둔 것이 없으면 `{}` 다. 그러면 서버가 분류에 맞춰 자동으로 정한다 —
    그것도 정상 경로다. 여기서 기본값을 지어내면 아무도 안 고른 값이
    "고른 값" 인 척 흘러간다.
"""

import json
import os

#: 골라 둔 디자인이 앉는 자리. 미리보기가 쓰고 여기서 읽는다.
#: ★`~/.volcano/keys/` 와 **같은 부모**를 쓰지만 키가 아니다 — 여기에는
#:   템플릿 이름 같은 것만 들어간다. 키를 여기 적지 마라.
PATH = os.path.join(os.path.expanduser("~"), ".volcano", "cardnews_design.json")

#: 실어 보낼 칸. **여기 없는 이름은 안 보낸다** — 화면이 아무 값이나 적어
#: 보내면 어느 칸이 먹히는지 아무도 모르게 된다.
KEYS = ("template", "highlight", "accent", "fontId", "fontVariant",
        "size", "titleSizePx", "reference",
        # ★10-08: 레퍼런스 표지 번호 · 내 레퍼런스 그림(경로·잰 명세·글자 지운 사본) · 내 계정명.
        #   이 칸이 없으면 미리보기에서 골라도 MCP 로 만들 때 **조용히 빠진다**(08-17 `CHOICE_KEYS` 와 같은 부류).
        "referenceCover", "referenceImage", "referenceSpec", "referenceTextFree", "handle", "cardEngine")


def load(path=None):
    """골라 둔 디자인 → dict. 없거나 못 읽으면 `{}` (막지 않는다).

    돌려주는 모양: `{"design": {...}, "from": <경로>, "found": bool}`
    """
    p = path or PATH
    if not os.path.exists(p):
        return {"design": {}, "from": p, "found": False,
                "note": "골라 둔 디자인이 없습니다 — 서버가 분류에 맞춰 정합니다."}
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        # ★못 읽은 것을 "없다" 로 뭉개지 않는다. 사람이 고칠 수 있게 말한다.
        return {"design": {}, "from": p, "found": False,
                "note": f"디자인 파일을 못 읽었습니다 ({type(e).__name__}) — "
                        "미리보기에서 다시 [적용] 하세요."}
    got = {k: raw[k] for k in KEYS if raw.get(k) not in (None, "")}
    return {"design": got, "from": p, "found": bool(got),
            "savedAt": raw.get("savedAt"),
            "note": ("미리보기에서 골라 둔 디자인을 씁니다."
                     if got else "파일은 있는데 고른 값이 없습니다.")}


def save(design, path=None):
    """미리보기가 부른다. **로컬 파일 하나**다 — 서버에 보관하지 않는다.

    ★서버에 두면 480명분 설정을 우리가 들고 있게 된다(§2 와 같은 판단).
      디자인은 그 사람 PC 에서 정하고 그 PC 에서 쓴다.
    """
    p = path or PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    got = {k: design[k] for k in KEYS if design.get(k) not in (None, "")}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(got, f, ensure_ascii=False, indent=2)
    return {"saved": p, "design": got}


def open_samples(url):
    """번호 견본 페이지를 이 PC 의 기본 브라우저로 연다(10-09 쇼츠대폭발 «카드뉴스 만든다고 하면 견본 페이지가 뜨는 거지?»).

    ★주소는 서버가 준다(`volcano_cardnews.REF_SAMPLES_URL`) — volcanoai.io 가 아니면 열지 않는다(남이 넣은 주소를 열지 않게).
    ★못 열어도 실패가 아니다 — 주소를 돌려주면 Claude Code 가 대화창에 그대로 보여 준다.
    """
    import webbrowser
    u = str(url or "")
    if not u.startswith("https://volcanoai.io/"):
        return {"opened": False, "url": u, "note": "volcanoai.io 주소만 엽니다."}
    try:
        ok = bool(webbrowser.open(u, new=2))
    except webbrowser.Error as e:
        return {"opened": False, "url": u, "note": f"브라우저를 못 열었습니다({e}) — 주소를 회원에게 보여 주세요."}
    return {"opened": ok, "url": u,
            "note": "견본 페이지를 열었습니다." if ok else "브라우저를 못 열었습니다 — 주소를 회원에게 보여 주세요."}
