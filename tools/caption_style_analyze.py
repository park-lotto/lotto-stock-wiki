"""자막 스타일 실측 — 영상 + 글꼴 견본 시트를 제미니에 같이 넣고 표를 채운다.

★키 로테이션·업로드·재시도는 video_analysis/comment_gen 배관을 **그대로 재사용**한다
  (0순위-B: 키 고르는 곳을 새로 만들지 않는다. 새로 짜면 로테이션이 또 놀게 된다 —
   2026-08-04 '키 로테이션이 통째로 놀았다' 사고).

★서버에서 돌린다(키·GPU·네트워크가 거기 있다):
    python3 tools/caption_style_analyze.py /tmp/capsurvey/yt /tmp/cap_yt.json youtube
"""
import json
import pathlib
import sys
import time

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from google.genai import types  # noqa: E402

from pipeline.atoms import key_vault  # noqa: E402  ★video_analysis와 같은 자리에서 가져온다
from shopping_shorts import comment_gen  # noqa: E402
from shopping_shorts.video_analysis import _MODEL, _client_for_key  # noqa: E402
from tools.caption_style_survey import CAPTION_SCHEMA, PROMPT, SHEET  # noqa: E402

# ★모델명을 여기서 새로 정하지 않는다 — 라이브(video_analysis)가 쓰는 것을 그대로 빌린다.
#   손으로 박아뒀더니 단종된 이름이었다(2026-08-25: gemini-2.5-flash → 404 '더 이상
#   제공 안 함'). 모델은 갈리는데 값이 두 벌이면 조사만 통째로 날린다(0순위-B).
MODEL = _MODEL


def analyze_one(video_path, sheet_bytes, max_retries=4):
    """영상 1편 → 자막 스타일 dict. 실패하면 None(빈 값으로 뭉개지 않는다)."""
    prompt = PROMPT % json.dumps(CAPTION_SCHEMA, ensure_ascii=False, indent=2)
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            print("  키 풀 소진", flush=True)
            return None
        client = _client_for_key(key)
        fobj = None
        try:
            with open(video_path, "rb") as fh:
                fobj = client.files.upload(
                    file=fh, config=types.UploadFileConfig(mime_type="video/mp4"))
            # 업로드 직후엔 PROCESSING 상태 — ACTIVE가 될 때까지 기다린다
            for _ in range(60):
                fobj = client.files.get(name=fobj.name)
                if str(getattr(fobj, "state", "")).endswith("ACTIVE"):
                    break
                time.sleep(2)
            resp = client.models.generate_content(
                model=MODEL,
                contents=[fobj,
                          types.Part.from_bytes(data=sheet_bytes, mime_type="image/png"),
                          prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                time.sleep(key_vault.retry_delay_seconds(e) or 8)
                continue
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 4)
                continue
            print(f"  실패: {e!r}"[:200], flush=True)
            return None
        finally:
            if fobj is not None:
                try:
                    client.files.delete(name=fobj.name)
                except Exception:
                    pass
    return None


def main():
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2])
    platform = sys.argv[3] if len(sys.argv) > 3 else "youtube"
    sheet_bytes = SHEET.read_bytes()
    vids = sorted(src.glob("*.mp4"))
    print(f"{platform}: {len(vids)}편 분석 시작", flush=True)
    # ★중간에 끊겨도 이어서 — 120편은 한 번에 안 끝난다
    out = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else []
    done = {r["file"] for r in out}
    for i, v in enumerate(vids, 1):
        if v.name in done:
            print(f"[{i}/{len(vids)}] {v.name} 이미함", flush=True)
            continue
        r = analyze_one(v, sheet_bytes)
        if r:
            out.append({"platform": platform, "file": v.name, **r})
            dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{i}/{len(vids)}] {v.name} {'OK' if r else 'FAIL'}", flush=True)
    print(f"완료 {len(out)}/{len(vids)} → {dst}", flush=True)


if __name__ == "__main__":
    main()
