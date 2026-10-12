# -*- coding: utf-8 -*-
"""bench.py 가 찾은 후보 시각마다 프레임 띠(8칸)를 만들어 Gemini 가 효과 종류를 고른다 (관제 124).

왜: Gemini 에 영상을 통째로 주면 1초에 한 장꼴로만 봐서 0.3초 전환을 놓친다
    (실측 2026-10-05 미스터살림왕: 장면 전환 약 28개 중 11개만, 눈으로 디졸브인 2.6초를 맨 컷이라 함).
    띠는 0.08초 간격이라 겹침·흐림·확대가 그대로 보인다.

후보: cut / soft / zoom_cut (전환 띠: -0.3~+0.3초) · push / punch / shake / whip 중 edit=True (장면 안 띠: 0~+0.9초)
결과: <out> 에 영상별 [{t, cand, label}] — 사람이 시트(<out>_sheets/)로 표본 대조한다.
★실측(2026-10-05 미스터살림왕 10줄): Gemini 3.5 flash 띠 분류 6/10 — 분명한 디졸브를 맨 컷·변화 없음으로 골랐다.
  그래서 기본 판정은 --sheets-only 로 시트를 만들고 눈(서브에이전트)으로 분류한다.

사용: py tools/scene_fx/strip_classify.py --dir <영상폴더> --bench <bench결과.json> --out <결과.json>
"""
import argparse, io, json, os, sys, time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from pipeline.atoms import key_vault  # noqa: E402

KEY_GROUP = "ingest"   # gemini_fx.py 와 같은 이유(쇼츠 전용 키는 서버에만)
MODEL = "gemini-3.5-flash"
ROWS_PER_IMG = 10
TW, TH = 96, 170

LABELS = ["hard_cut", "jump_zoom_cut", "dissolve", "zoom_blur", "whip_pan", "slide_push", "spin",
          "flash_white", "glitch", "fade_black",
          "edit_punch_zoom", "edit_slow_zoom", "edit_shake",
          "camera_motion", "no_change"]

PROMPT = """각 줄은 쇼츠 영상의 한 지점을 0.08초 간격으로 펼친 프레임 8칸이다(왼쪽→오른쪽 시간순). 줄 맨 앞 번호가 지점 번호다.
각 줄마다 아래 라벨 중 하나를 골라라. 편집 프로그램이 넣은 효과인지, 촬영할 때 생긴 움직임인지 구분이 핵심이다.

hard_cut: 한 칸 사이에 다른 장면으로 뚝 바뀜
jump_zoom_cut: 같은 장면이 한 칸 사이에 더 크게/작게 잘려 바뀜
dissolve: 두 장면이 반투명하게 겹쳐 보이는 칸이 있음
zoom_blur: 겹치거나 바뀌면서 방사형으로 흐려지고 확대됨
whip_pan: 한쪽으로 빠르게 쓸리며 흐려지고 다음 장면
slide_push: 다음 장면이 화면을 밀고 들어옴(경계선이 보임)
spin: 회전하며 바뀜
flash_white: 하얗게 번쩍
glitch: 색이 어긋나거나 줄무늬로 깨짐
fade_black: 검게 어두워졌다 밝아짐
edit_punch_zoom: 같은 장면이 1~2칸 만에 기계적으로 확 커짐(편집 확대)
edit_slow_zoom: 같은 장면이 칸마다 아주 매끈하게 조금씩 커지거나 작아짐(편집 확대)
edit_shake: 화면 전체가 기계적으로 좌우·상하로 떨림(편집 흔들림)
camera_motion: 손으로 들고 찍은 흔들림·카메라 이동·물건 움직임(편집 효과 아님)
no_change: 별 변화 없음

JSON 배열로만: [{"i": 지점번호, "label": "..."}]"""

SCHEMA = {"type": "array", "items": {"type": "object", "properties": {
    "i": {"type": "integer"}, "label": {"type": "string", "enum": LABELS}}, "required": ["i", "label"]}}


def strip(cap, fps, t, offs):
    cells = []
    for d in offs:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, (t + d) * 1000))
        ok, f = cap.read()
        cells.append(cv2.resize(f, (TW, TH)) if ok else np.zeros((TH, TW, 3), np.uint8))
    return np.hstack(cells)


def candidates(r):
    out = []
    for e in r["events"]:
        k = e["kind"]
        if k in ("cut", "soft", "zoom_cut"):
            out.append((e["t"], k, [-0.32 + 0.08 * j for j in range(9) if j != 4]))
        elif k in ("push", "punch", "shake", "whip") and e.get("edit"):
            step = 0.12 if k == "push" else 0.06
            out.append((e["t"], k, [step * j for j in range(8)]))
    # 같은 시각(±0.1초) 후보는 하나로
    out.sort(key=lambda x: x[0])
    dedup = []
    for c in out:
        if not dedup or c[0] - dedup[-1][0] > 0.1:
            dedup.append(c)
    return dedup


def ask(images):
    for attempt in range(6):
        live = key_vault.get_live_keys(KEY_GROUP)
        if not live:
            raise SystemExit(f"Gemini 키 풀({KEY_GROUP}) 소진")
        key = key_vault.pick_paced_key(live)
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=180_000))
        try:
            parts = [types.Part.from_bytes(data=b, mime_type="image/jpeg") for b in images] + [PROMPT]
            resp = client.models.generate_content(model=MODEL, contents=parts, config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=SCHEMA))
            return json.loads(resp.text)
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                key_vault.mark_exhausted(KEY_GROUP, key, key_vault.retry_delay_seconds(e)); continue
            if key_vault.is_quota_error(e):
                time.sleep(key_vault.retry_delay_seconds(e) or 8); continue
            if attempt < 5:
                print("  재시도:", repr(e)[:140]); time.sleep(5 * (attempt + 1)); continue
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--sheets-only", action="store_true",
                    help="띠 시트만 만든다(사람·서브에이전트가 눈으로 분류). Gemini 띠 분류는 실측 정확도 6/10 이라 기본 판정으로 쓰지 않는다")
    a = ap.parse_args()
    sheets = a.out.replace(".json", "_sheets")
    os.makedirs(sheets, exist_ok=True)
    done = {r["id"]: r for r in json.load(open(a.out, encoding="utf-8"))} if os.path.exists(a.out) else {}
    for r in json.load(open(a.bench, encoding="utf-8")):
        if a.only and r["id"] not in a.only:
            continue
        if r["id"] in done:
            continue
        cands = candidates(r)
        if not cands:
            continue
        cap = cv2.VideoCapture(os.path.join(a.dir, r["id"] + ".mp4"))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        rows = []
        for n, (t, k, offs) in enumerate(cands):
            s = strip(cap, fps, t, offs)
            lab = np.zeros((TH, 44, 3), np.uint8)
            cv2.putText(lab, str(n), (2, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            rows.append(np.hstack([lab, s]))
        cap.release()
        imgs, labels = [], {}
        for b in range(0, len(rows), ROWS_PER_IMG):
            g = np.vstack(rows[b:b + ROWS_PER_IMG])
            ok, buf = cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, 82])
            imgs.append(buf.tobytes())
            buf.tofile(os.path.join(sheets, f'{r["id"]}_{b // ROWS_PER_IMG}.jpg'))
        # 훅 시트: 첫 3.2초를 0.1초 간격 32칸(2줄) — 훅에서 확대·전환을 어떻게 쓰는지 레퍼런스 그대로 본다
        cap = cv2.VideoCapture(os.path.join(a.dir, r["id"] + ".mp4"))
        hook = [strip(cap, fps, 0.0, [0.1 * j for j in range(16)]), strip(cap, fps, 1.6, [0.1 * j for j in range(16)])]
        cap.release()
        cv2.imencode(".jpg", np.vstack(hook), [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tofile(
            os.path.join(sheets, f'{r["id"]}_hook.jpg'))
        if a.sheets_only:
            json.dump([{"n": n, "t": t, "cand": k} for n, (t, k, _) in enumerate(cands)],
                      open(os.path.join(sheets, r["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            print(r["channel"], r["id"], "후보", len(cands), "시트", len(imgs))
            continue
        for chunk in range(0, len(imgs), 4):           # 한 번에 그림 4장(40줄)까지
            for x in ask(imgs[chunk:chunk + 4]):
                labels[x["i"]] = x["label"]
        res = [{"t": t, "cand": k, "label": labels.get(n, "?")} for n, (t, k, _) in enumerate(cands)]
        done[r["id"]] = {"id": r["id"], "channel": r["channel"], "dur": r["dur"], "items": res}
        c = {}
        for x in res:
            c[x["label"]] = c.get(x["label"], 0) + 1
        print(f'{r["channel"]:12s} {r["id"]} 후보{len(res)} {c}')
        json.dump(list(done.values()), open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
