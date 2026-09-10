"""화면 검증용 프레임·멀티모달 호출·비교 로그. 다운로드는 하지 않는다."""
import hashlib
import io
import json
import sys
from pathlib import Path


def frame(seg, sid, work):
    if work is None:
        return None
    try:
        from PIL import Image
        from shopping_shorts.frame_extract import extract_seg_thumb
        work = Path(work)
        vid = str(seg.get("video_id") or "")
        if any(not x or x in (".", "..") or any(c in x for c in '/\\:')
               for x in (str(sid or ""), vid)):
            raise ValueError("잘못된 장면/영상 ID")
        cached = work / "seg_thumbs" / f"{sid}.jpg"
        if not cached.is_file():
            src = next((work / vid).glob("*.mp4"), None)
            if src is None:
                raise FileNotFoundError(f"기존 소스 없음: {vid}")
            cached = extract_seg_thumb(src, cached.parent, seg, cached.name)
            if cached is None:
                raise RuntimeError("프레임 추출 실패")
        data = cached.read_bytes()
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        return data
    except Exception as e:  # noqa: BLE001 — 종전 텍스트 경로로 폴백
        print(f"[verify_screens] 이미지 확보 실패: {e!r}", file=sys.stderr)
        return None


def image_call(prompt, schema, image):
    from google.genai import types
    from shopping_shorts.frame_script import _call_with_key_rotation, loads_lenient
    part = types.Part.from_bytes(data=image, mime_type="image/jpeg")

    def once(client, model):
        response = client.models.generate_content(
            model=model, contents=[prompt, part],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=schema))
        return loads_lenient(response.text)

    return _call_with_key_rotation(once, what="verify_screens")


def invoke(call, *args):
    try:
        result = call(*args)
        if isinstance(result, dict) and type(result.get("ok")) is bool:
            return {"ok": result["ok"], "why": str(result.get("why") or "")}
        print("[verify_screens] 판정 없음/응답 형식 오류", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — fail-open
        print(f"[verify_screens] 모델 호출 실패: {e!r}", file=sys.stderr)
    return None


def fingerprint(beat, scene, image):
    return hashlib.sha256(json.dumps(
        [1, beat.get("narration"), beat.get("primary"), scene,
         hashlib.sha256(image).hexdigest() if image else None],
        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def log(record, work):
    line = json.dumps(record, ensure_ascii=False)
    print(f"[verify_screens] {line}", file=sys.stderr)
    if work is not None:
        try:
            Path(work).mkdir(parents=True, exist_ok=True)
            with (Path(work) / "screen_verify.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception as e:  # noqa: BLE001 — 로그 실패가 제작을 막지 않는다
            print(f"[verify_screens] 로그 저장 실패: {e!r}", file=sys.stderr)


def candidates(beat, seg_map, used_ids, limit=10):
    """어긋난 칸을 구제할 후보 장면을 **싼 순서로** 내놓는다 (2026-09-10).

    ★왜 순서가 중요한가: 후보 하나마다 모델 호출 1회다. 실측(어긋난 22칸)에서
      맞는 화면은 **95%가 같은 영상 안에** 있었고, 그중엔 바로 옆 컷도 있었다
      ("스마트폰까지 거치돼서"에 빈 뒷좌석이 붙었는데 옆 컷에 폰이 꽂혀 있었다).
      그래서 ①대본이 지목한 대안 → ②같은 영상의 이웃 컷 → ③나머지 순으로 준다.
    ★이미 다른 칸이 쓰는 장면(used_ids)은 뺀다 — 같은 그림이 두 번 나오면
      고친 것보다 나쁘다.
    ★edge(첫·끝 컷)는 자동 배치에서 종전대로 제외한다(non_edge_segs 계보)."""
    from shopping_shorts.edit_plan import non_edge_segs
    pool = non_edge_segs(seg_map) or {}
    cur = (beat.get("primary") or {})
    out, seen = [], set(used_ids or ())
    seen.add(cur.get("seg_id"))

    def push(sid):
        if not sid or sid in seen or sid not in pool:
            return
        seen.add(sid)
        out.append(pool[sid])

    for a in (beat.get("alternates") or []):
        push((a or {}).get("seg_id"))
    same = [s for sid, s in pool.items() if s.get("video_id") == cur.get("video_id")]
    start = float(cur.get("start") or 0)
    for s in sorted(same, key=lambda s: abs(float(s.get("start") or 0) - start)):
        push(s.get("seg_id"))
    for sid in pool:
        push(sid)
    return out[:max(0, int(limit))]


# ⚠️여러 칸을 한 요청에 묶는 배치도 만들어 재봤다(2026-09-10): job당 1회 호출·2.9초.
#   판정이 1차와 3칸(5.7%) 달라져 "묶으면 모델이 칸을 섞는다"고 봤는데, **그 결론은 틀렸다**
#   — 칸을 동시에 묻는 방식(호출은 단건 그대로)에서도 같은 비율로 3칸이 달랐고, 겹치는 건
#   1칸뿐이었다. 흔들리는 칸은 "미국도 당황한 천재 발명품" 같은 **화면 증거를 요구하지 않는
#   훅 문장**이다 — 경계선이라 모델 답이 매번 조금 다르다. 배치의 문제가 아니었다.
#   지금은 동시 물음을 쓴다(4.7초). 더 줄여야 하면 배치를 되살려도 된다 — 정확도 차이는
#   확인된 바 없다(표본 3칸으로는 못 가른다).
