# -*- coding: utf-8 -*-
"""'사용중'에 뭉쳐 있던 장면을 행위 축 다섯으로 다시 태깅한다 (2026-08-20).

## 왜 필요한가

`shot_roles` 모듈이 축을 늘렸지만(설치·조작·도포·정리·실증), **기존 장면은 옛 값 그대로**다.
새 값으로 저장된 게 없으면 슬롯 지시가 여전히 '사용중' 한 통을 가리킨다 = 축을 늘린 효과가 0.

라이브 실측(reference.db, 7,813장면):
    사용중 3,541(45.3%) · (없음) 1,190(15.2%) · 조리 220(2.8%)  ← 이 셋이 대상 = 4,951건
    (완성·after·before·문제·기타는 이미 제 갈래라 건드리지 않는다)

## ★영상을 다시 안 본다

`scene_desc`(화면에 뭐가 보이나)와 `action`이 이미 저장돼 있다. 다섯 갈래를 고르는 데는
그 텍스트로 충분하다 — 프레임을 다시 뽑으면 ffmpeg·업로드까지 다시 도는데 얻는 게 없다.
게다가 **원본 영상이 이미 사라진 옛 추출본도 재태깅된다.**

## 안전장치

- `shot_role_prev`에 옛 값을 남긴다 → 언제든 되돌릴 수 있다(파생물이 원본을 지우지 않는다)
- 배치마다 커밋한다 → 중간에 끊겨도 거기까지 남고, 다시 돌리면 이어서 한다
- 이미 새 갈래인 장면은 건너뛴다(멱등)
- `--dry`면 DB를 안 건드리고 분류 결과만 보여준다

실행(★서버 — DB와 키가 거기 있다):
    python3 tools/retag_shot_roles.py --dry --limit 40      # 먼저 눈으로 본다
    python3 tools/retag_shot_roles.py                        # 전량
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts import shot_roles as SR          # noqa: E402
from shopping_shorts import comment_gen, video_analysis   # noqa: E402
from google.genai import types                         # noqa: E402

# 다시 태깅할 대상. 이 값들만 건드린다(나머지는 이미 제 갈래에 있다).
STALE = {"사용중", "조리", "", None}

BATCH = 40          # 한 번에 묶어 보낼 장면 수. 크게 잡으면 싸지만 모델이 뒤에서 흐려진다.

_TARGETS = [r for r in SR.USE_ROLES if r != "사용중"] + ["사용중"]

SCHEMA = {
    "type": "object",
    "properties": {"roles": {"type": "array", "items": {
        "type": "string", "enum": _TARGETS}}},
    "required": ["roles"],
}

PROMPT = """아래는 쇼핑 쇼츠 영상에서 잘라낸 장면들의 **화면 설명**이다.
각 장면이 어떤 '행위'를 보여주는지 하나씩 골라라.

""" + "\n".join("  %s = %s" % (r, SR.DESCRIPTIONS[r]) for r in _TARGETS) + """

규칙:
- 번호 순서 그대로, 장면 수와 **똑같은 개수**의 roles 배열로 답해라.
- 다섯 갈래 중 어디에도 딱 맞지 않으면 그때만 '사용중'을 써라. 억지로 끼우지 마라.
- 요리 소재라고 무조건 한 갈래로 몰지 마라 — 반죽·섞기는 조작, 오븐에 넣기는 설치가 아니라
  조작이다. **무엇을 하는 손동작인가**로 판단해라.

장면 목록:
"""


def classify(lines, key):
    body = "\n".join("%d. %s" % (i, t) for i, t in enumerate(lines, 1))
    client = video_analysis._client_for_key(key)
    r = client.models.generate_content(
        model=video_analysis._TRANSLATE_MODEL,
        contents=[PROMPT + body],
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=SCHEMA),
    )
    out = (json.loads(r.text) or {}).get("roles") or []
    return [SR.normalize(x) for x in out]


def _text_of(seg):
    """분류에 쓸 한 줄. 화면 설명이 본체고, action이 있으면 붙인다."""
    d = (seg.get("scene_desc") or "").strip()
    a = (seg.get("action") or "").strip()
    t = (d + (" / " + a if a and a not in d else "")).strip()
    return t[:120]


def collect(db):
    """(shortcode, 세그 인덱스, 텍스트) 목록 — 다시 태깅할 것만."""
    con = sqlite3.connect(db)
    rows = con.execute(
        "select shortcode, script_json from script_extracts where script_json is not null"
    ).fetchall()
    con.close()
    todo = []
    for sc, raw in rows:
        try:
            d = json.loads(raw)
        except Exception:
            continue
        for i, s in enumerate((d.get("segments") or []) if isinstance(d, dict) else []):
            if not isinstance(s, dict):
                continue
            if (s.get("shot_role") or "") not in STALE:
                continue                       # 이미 제 갈래 — 멱등
            t = _text_of(s)
            if not t:
                continue                       # 설명이 없으면 판단 근거가 없다(그대로 둔다)
            todo.append((sc, i, t))
    return todo


def apply_batch(db, items, roles):
    """(shortcode, idx, _) 목록과 고른 값들을 DB에 되쓴다. shortcode 단위로 묶어 한 번만 쓴다."""
    by_doc = {}
    for (sc, i, _t), r in zip(items, roles):
        by_doc.setdefault(sc, []).append((i, r))
    con = sqlite3.connect(db)
    n = 0
    for sc, pairs in by_doc.items():
        row = con.execute(
            "select script_json from script_extracts where shortcode=?", (sc,)).fetchone()
        if not row:
            continue
        d = json.loads(row[0])
        segs = d.get("segments") or []
        for i, r in pairs:
            if 0 <= i < len(segs) and isinstance(segs[i], dict):
                # ★옛 값을 남긴다 — 되돌릴 수 없는 덮어쓰기를 하지 않는다
                segs[i].setdefault("shot_role_prev", segs[i].get("shot_role") or "")
                segs[i]["shot_role"] = r
                n += 1
        con.execute("update script_extracts set script_json=? where shortcode=?",
                    (json.dumps(d, ensure_ascii=False), sc))
    con.commit()
    con.close()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="DB를 안 건드리고 결과만 본다")
    ap.add_argument("--limit", type=int, default=0, help="이만큼만 처리(0=전량)")
    a = ap.parse_args()

    from shopping_shorts.config import DB_PATH
    todo = collect(DB_PATH)
    if a.limit:
        todo = todo[:a.limit]
    print("다시 태깅할 장면: %d건 (BATCH=%d → 호출 약 %d회)"
          % (len(todo), BATCH, (len(todo) + BATCH - 1) // BATCH))
    if not todo:
        return 0

    done = fail = 0
    from collections import Counter
    tally = Counter()
    for off in range(0, len(todo), BATCH):
        chunk = todo[off:off + BATCH]
        key, _ = comment_gen._next_live_key_and_idx()
        if key is None:
            print("  살아있는 키가 없다 — 여기까지"); break
        try:
            roles = classify([t for _sc, _i, t in chunk], key)
        except Exception as e:
            fail += 1
            print("  ERR %d %s" % (off, str(e)[:90]))
            time.sleep(20)
            continue
        if len(roles) != len(chunk):
            # 개수가 어긋나면 **하나도 쓰지 않는다** — 밀려 쓰면 엉뚱한 장면에 값이 박힌다
            fail += 1
            print("  개수 불일치 %d≠%d — 이 묶음 건너뜀" % (len(roles), len(chunk)))
            continue
        tally.update(roles)
        if a.dry:
            for (_sc, _i, t), r in list(zip(chunk, roles))[:8]:
                print("   %-6s %s" % (r, t[:70]))
        else:
            done += apply_batch(DB_PATH, chunk, roles)
        print("  ...%d/%d (기록 %d, 실패묶음 %d)" % (min(off + BATCH, len(todo)), len(todo), done, fail))
        time.sleep(1.0)

    print("\n갈래 분포:", dict(tally.most_common()))
    print("완료: %d건 기록 (dry=%s)" % (done, a.dry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
