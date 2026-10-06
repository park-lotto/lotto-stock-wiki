# -*- coding: utf-8 -*-
"""Gemini 가 영상을 보고 '편집으로 넣은' 장면 효과(전환·확대·흔들림 등)를 시각과 함께 분류한다 (관제 124).

왜 따로 두나: bench.py 의 픽셀 판정은 컷 시각은 믿을 만하지만(ffmpeg scdet, 눈 대조), 부드러운 전환·확대가
'편집인지 촬영 움직임인지'는 못 가른다(실측 2026-10-05: 부드러운 전환 후보 24건 중 진짜 4건).
그래서 종류 분류는 Gemini 가 하고, 사람이 프레임으로 표본 대조해 맞는 비율을 같이 남긴다(verify 단계).

키·업로드는 shopping_shorts.video_analysis 와 같은 키 풀(comment_gen)을 쓴다.
사용: py tools/scene_fx/gemini_fx.py --dir <영상폴더> --list <목록.json> --out <결과.json>
"""
import argparse, json, os, sys, time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from google.genai import types  # noqa: E402
from google import genai  # noqa: E402
from shopping_shorts import video_analysis  # noqa: E402
from pipeline.atoms import key_vault  # noqa: E402

# 쇼츠 전용 키(SHORTS_GEMINI_KEYS)는 서버 .env 에만 있다 — 로컬 PC 는 0개(실측). 내부 분석이라 ingest 그룹을 쓴다.
# briefing 그룹은 아침 브리핑이 쓰므로 건드리지 않는다.
KEY_GROUP = "ingest"

TRANSITIONS = ["hard_cut", "jump_zoom_cut", "dissolve", "zoom_blur", "whip_pan", "slide_push",
               "spin", "flash_white", "glitch", "fade_black", "shape_wipe", "other"]
CAMERA = ["punch_zoom_in", "punch_zoom_out", "slow_push_in", "slow_pull_out", "pan_drift", "shake",
          "beat_pulse", "speed_ramp", "freeze_frame", "split_screen", "picture_in_picture", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "transitions": {"type": "array", "items": {"type": "object", "properties": {
            "t": {"type": "number"}, "type": {"type": "string", "enum": TRANSITIONS},
            "dur": {"type": "number"}}, "required": ["t", "type"]}},
        "camera": {"type": "array", "items": {"type": "object", "properties": {
            "t": {"type": "number"}, "type": {"type": "string", "enum": CAMERA},
            "dur": {"type": "number"}, "strength": {"type": "string", "enum": ["weak", "medium", "strong"]},
            "moment": {"type": "string", "enum": ["hook", "product_reveal", "feature", "price", "reaction", "ending", "other"]}},
            "required": ["t", "type"]}},
        "notes": {"type": "string"},
    },
    "required": ["transitions", "camera"],
}

PROMPT = """너는 숏폼 편집자다. 이 쇼츠 영상에서 **편집 프로그램(캡컷 등)으로 넣은** 장면 효과만 시각(초)과 함께 적어라.

반드시 지킬 것:
- 촬영할 때 생긴 움직임(손으로 들고 찍어 흔들림, 카메라를 돌림, 물건을 카메라 쪽으로 들이밈, 화면 속 사물의 움직임)은 효과가 아니다. 적지 마라.
- 편집 효과의 특징: 화면 전체가 한 덩어리로 기계적으로 확대·이동·회전함, 두 장면이 겹쳐 보임, 화면이 번쩍·흐려짐·밀려남.
- transitions: 장면(샷)이 바뀌는 모든 지점. 그냥 뚝 끊기면 hard_cut. 같은 장면을 더 가깝게/멀게 잘라 이으면 jump_zoom_cut.
- camera: 한 장면 안에서 편집으로 준 확대·흔들림·속도 변화 등. strength 는 체감 세기. moment 는 그 순간 대본 역할
  (hook=첫 3초 시선 끌기, product_reveal=제품 처음 등장, feature=기능 시연, price=가격·구매 유도, reaction=놀람·반응, ending=마무리).
- 화면 위 고정 틀(제목 띠·채널명)과 자막 글자 애니메이션은 이번 대상이 아니다.
- 확실하지 않으면 적지 마라. 지어내지 마라.
- notes: 이 영상의 편집 스타일을 한 문장으로(예: "효과 없이 1초마다 맨 컷", "모든 컷이 짧은 디졸브").
JSON 만 출력."""


def classify(path, max_retries=6):
    for attempt in range(max_retries):
        live = key_vault.get_live_keys(KEY_GROUP)
        if not live:
            raise SystemExit(f"Gemini 키 풀({KEY_GROUP}) 소진")
        key = key_vault.pick_paced_key(live)
        client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=180_000))
        fo = None
        try:
            with open(path, "rb") as fh:
                fo = client.files.upload(file=fh, config=types.UploadFileConfig(mime_type="video/mp4"))
            fo = video_analysis._wait_until_active(client, fo)
            resp = client.models.generate_content(
                model=video_analysis._MODEL, contents=[fo, PROMPT],
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=SCHEMA,
                                                   media_resolution="MEDIA_RESOLUTION_LOW"))
            return json.loads(resp.text)
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                print("  키 소진/비활성:", repr(e)[:120])
                try:
                    key_vault.mark_exhausted(KEY_GROUP, key, key_vault.retry_delay_seconds(e))
                except Exception:
                    pass
                continue
            if key_vault.is_quota_error(e):
                time.sleep(key_vault.retry_delay_seconds(e) or 8); continue
            if attempt < max_retries - 1:
                print("  재시도:", repr(e)[:160]); time.sleep(5 * (attempt + 1)); continue
            raise
        finally:
            if fo is not None:
                try:
                    client.files.delete(name=fo.name)
                except Exception:
                    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--list", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    items = json.load(open(a.list, encoding="utf-8"))
    done = {r["id"]: r for r in json.load(open(a.out, encoding="utf-8"))} if os.path.exists(a.out) else {}
    for n, it in enumerate(items):
        if a.limit and n >= a.limit:
            break
        ch, vid = (it["channel"], it["id"]) if isinstance(it, dict) else (it[0], it[1])
        if vid in done:
            continue
        p = os.path.join(a.dir, vid + ".mp4")
        if not os.path.exists(p):
            continue
        try:
            r = classify(p)
        except Exception as e:
            print("실패", vid, repr(e)[:200]); continue
        r.update({"id": vid, "channel": ch})
        done[vid] = r
        tc = {}
        for x in r["transitions"]:
            tc[x["type"]] = tc.get(x["type"], 0) + 1
        print(f"{ch:12s} {vid} 전환{tc} 카메라{[c['type'] for c in r['camera']]} | {r.get('notes','')[:60]}")
        json.dump(list(done.values()), open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
