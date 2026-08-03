"""Layer 2 — scene_desc가 **실제 화면과 맞는지** 프레임 대조 스팟체크.

Layer 1(`tag_qa`)은 텍스트만 본다. 시간·역할·받아쓰기가 규칙에 맞는지는 계산으로 알 수
있지만, "이 장면 묘사가 진짜 저 화면이냐"는 눈이 없으면 판단이 불가능하다. 그런데 태깅이
틀린 방향은 대개 여기다 — 배경 소품을 주제품으로 오인하면(2026-07-30 '강아지 선풍기' 사고)
슬롯 조합이 아무리 정확해도 엉뚱한 화면이 나간다.

★설계 원칙 — 싸게, 그리고 아무것도 안 바꾼다:
  - **전수 아님(스팟체크)**: 세그 전부를 보면 비용이 세그 수에 비례한다. 대표 3개만 본다.
    훅(첫 세그) + is_key 하나 + 완성/after 하나 — 틀리면 제일 아픈 자리들이다.
  - **모델 호출 1회**: 프레임 3장을 한 번에 보낸다(frame_script와 같은 방식).
  - **기록만 한다**: `tag_qa.frame_score`에 남길 뿐 추출 결과를 고치거나 버리지 않는다.
    재추출 트리거로 쓸지는 실측 숫자를 본 뒤 결정한다(지금 정하면 근거 없는 자동화가 된다).
  - **기본 OFF**: 설정키 `tag_qa_frames_enabled`. 검증 안 된 플래그를 라이브에 켜두면
    조용히 비용만 나간다(2026-07-31 B1 프레임추출 실사고 계보).
  - **fail-open**: ffmpeg·모델·키 어디가 죽어도 None을 돌려주고 추출은 그대로 간다.
"""
import logging

log = logging.getLogger(__name__)

# verdict → 점수. '부분'을 0.5로 둔 이유: 묘사가 대상은 맞는데 상태를 틀리는 경우
# (예: '자르는 중' vs 실제 '자른 뒤')가 실무에서 제일 흔한데, 이걸 0으로 치면 점수가
# 과하게 비관적이 되고 1로 치면 신호가 사라진다.
_VERDICT_SCORE = {"맞음": 1.0, "부분": 0.5, "틀림": 0.0}

_SAMPLE_N = 3          # 대표 세그 수 — 늘리면 비용이 그대로 늘어난다
_MIN_SEG_LEN = 0.4     # 이보다 짧은 세그는 중간시각 프레임이 전환 순간에 걸려 안 뽑는다

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {"verdicts": {"type": "array", "items": {"type": "object", "properties": {
        # ★image_no를 받는 이유(2026-08-01 리뷰 F3): 순서(zip)로 짝지으면 모델이 판정을
        #   **하나라도 빠뜨렸을 때** 그 뒤가 전부 한 칸씩 밀려 엉뚱한 묘사를 채점한다.
        #   프레임 추출 실패 쪽은 이미 방어했지만 모델 응답 쪽은 뚫려 있었다.
        #   번호를 같이 받아 명시적으로 맞추고, 번호가 없거나 이상하면 그 판정은 버린다.
        "image_no": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["맞음", "부분", "틀림"]},
        "reason": {"type": "string"},
    }, "required": ["image_no", "verdict"]}}},
    "required": ["verdicts"],
}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None          # NaN 방어


def _usable(seg):
    """중간시각 프레임을 뽑을 수 있는 세그인가 — 시간이 온전하고 너무 짧지 않아야."""
    a, b = _num(seg.get("start")), _num(seg.get("end"))
    return a is not None and b is not None and b - a >= _MIN_SEG_LEN


def pick_segments(segs, n=_SAMPLE_N):
    """대조할 대표 세그 (인덱스, 세그) 목록. 순수 함수라 모델 없이 테스트된다.

    고르는 순서 = 틀렸을 때 아픈 순서: ①첫 세그(훅 — 0초 화면이 어긋나면 영상 전체가
    어긋나 보인다) ②is_key(제품 기능 실증 = 슬롯 배치의 핵심 재료) ③완성/after(결과 화면).
    같은 세그가 두 조건에 걸리면 한 번만 넣는다(중복 판정에 돈 쓰지 않는다)."""
    usable = [(i, s) for i, s in enumerate(segs or []) if isinstance(s, dict) and _usable(s)]
    if not usable:
        return []
    picked, seen = [], set()

    def take(cand):
        for i, s in cand:
            if i not in seen:
                seen.add(i)
                picked.append((i, s))
                return

    take(usable[:1])                                                   # ①훅
    take([(i, s) for i, s in usable if s.get("is_key")])               # ②실증
    take([(i, s) for i, s in usable
          if (s.get("shot_role") or "") in ("완성", "after")])          # ③결과
    # 셋을 못 채웠으면(짧은 영상 등) 남은 세그로 채운다 — 표본이 1개면 점수가 요동친다.
    for i, s in usable:
        if len(picked) >= n:
            break
        if i not in seen:
            seen.add(i)
            picked.append((i, s))
    return picked[:n]


def _mid(seg):
    return (_num(seg.get("start")) + _num(seg.get("end"))) / 2.0


def score_verdicts(verdicts, picked):
    """판정 배열 → (frame_score, 상세). 모델이 개수를 덜/더 주면 **맞춰진 것만** 센다.

    ★순서(zip)가 아니라 **image_no로 짝짓는다**(2026-08-01 리뷰 F3): 모델이 2번 판정을
    빠뜨리고 1·3번만 주면, 순서로 맞추면 3번 판정이 2번 묘사에 붙어 **엉뚱한 장면을
    채점**한다. 점수가 틀리는 것보다 나쁜 건, 틀린 줄도 모른다는 것이다.
    번호가 없거나 범위를 벗어나면 그 판정은 버린다(추측해서 붙이지 않는다).

    개수가 안 맞는다고 통째로 버리지 않는 이유: 3장 중 2장만 판정돼도 그 2장은 진짜 신호다.
    반대로 없는 판정을 '맞음'으로 채우면 점수가 조용히 부풀어 기준선이 거짓이 된다."""
    picked = picked or []
    pairs, seen = [], set()
    for v in verdicts or []:
        no = (v or {}).get("image_no")
        if not isinstance(no, int) or isinstance(no, bool):
            continue
        idx = no - 1                      # 프롬프트가 1번부터 센다
        if not (0 <= idx < len(picked)) or idx in seen:
            continue                      # 범위 밖·중복 번호는 버린다
        seen.add(idx)
        pairs.append((v, picked[idx]))
    scored = [(v, p) for v, p in pairs if (v or {}).get("verdict") in _VERDICT_SCORE]
    if not scored:
        return None, []
    detail = [{"seg_index": p[0],
               "scene_desc": (p[1].get("scene_desc") or "")[:60],
               "verdict": v["verdict"],
               "reason": (v.get("reason") or "")[:80]} for v, p in scored]
    avg = sum(_VERDICT_SCORE[v["verdict"]] for v, _ in scored) / len(scored)
    return round(avg, 3), detail


def flag_on():
    """설정 조회 — 미설정·실패는 False(기본 OFF). `_frame_flag_on`과 같은 패턴."""
    try:
        from shopping_shorts.store import Store
        from shopping_shorts.config import DB_PATH
        return Store(DB_PATH).get_setting("tag_qa_frames_enabled", "") == "1"
    except Exception:
        return False


def _extract_frames(video_path, picked, dest_dir):
    """대표 세그의 중간시각 프레임 1장씩. 실패한 장은 건너뛴다(그 세그는 판정 대상에서 빠진다).
    반환: (프레임경로 목록, 실제로 뽑힌 picked 목록) — 둘의 순서·길이가 반드시 같아야
    score_verdicts의 zip이 어긋나지 않는다."""
    from shopping_shorts.frame_extract import extract_frame_at
    paths, kept = [], []
    for i, seg in picked:
        try:
            p = extract_frame_at(video_path, dest_dir, _mid(seg), filename=f"qa_{i}.jpg")
        except Exception as e:  # noqa: BLE001
            log.info("tag_qa_frames: 프레임 추출 실패 seg%s — %s", i, e)
            continue
        if p:
            paths.append(p)
            kept.append((i, seg))
    return paths, kept


def _judge(frame_paths, picked):
    """프레임 N장 + 각 묘사 → 모델이 일치 여부 판정. 실패는 [](호출부 fail-open)."""
    import json
    from shopping_shorts import comment_gen
    from shopping_shorts.video_analysis import _MODEL
    try:
        from google.genai import types
    except Exception:
        # ★조용히 돌아가지 마라(2026-08-01 실사고). 아래 key 분기와 같은 이유.
        log.info("tag_qa_frames._judge 건너뜀 — google.genai 없음")
        return []
    key, _ = comment_gen._current_key_and_idx()
    if key is None:
        # ★실사고(확대 실측 30회 중 21회): 앞 6건이 성공한 뒤 나머지가 전부 측정 실패로
        #   떨어졌는데 **로그가 한 줄도 없었다** — 예외가 아니라 이 early return이라서다.
        #   Layer 2를 켜면 담기마다 모델을 한 번 더 쓰므로 키 풀이 먼저 마르는데, 그때
        #   frame_score가 아무 흔적 없이 빠진다. "측정 못 함"이 안 보이면 그 지표는
        #   있으나 마나다(이 파일이 None≠0.0으로 지키려던 바로 그 원칙의 관측 쪽 짝).
        log.info("tag_qa_frames._judge 건너뜀 — 쓸 수 있는 Gemini 키가 없다(키 풀 소진?)")
        return []
    lines = "\n".join(f"{n+1}번 이미지의 묘사: {(s.get('scene_desc') or '(없음)')}"
                      for n, (_, s) in enumerate(picked))
    prompt = (
        f"영상에서 뽑은 프레임 {len(frame_paths)}장이다(순서대로). 각 이미지가 아래 묘사와 "
        f"맞는지 판정해라.\n{lines}\n\n"
        "★중요 — 묘사는 **수 초짜리 구간 전체**를 요약한 것이고, 이미지는 그 구간의 "
        "**중간 한 장**이다. 그러므로 묘사에 적힌 동작이 이 한 장에 다 담겨 있지 않은 것은 "
        "**정상이며 감점 사유가 아니다**. 예: 묘사가 '가루를 담고 액체를 부어 섞는 과정'인데 "
        "이미지엔 붓는 장면만 있다면 그것은 '맞음'이다.\n"
        "판정 기준:\n"
        "· '맞음' = 묘사의 **주 대상**이 화면의 주 대상과 같고, 이미지가 그 구간의 한 장면으로 "
        "자연스럽다(동작 일부만 보여도 맞음).\n"
        "· '부분' = 대상은 맞지만 묘사가 화면과 **모순**된다(예: '깨끗해진 상태'라는데 아직 "
        "더러움, 전혀 다른 공정).\n"
        "· '틀림' = 주 대상 자체가 다르다. 배경 소품·장식을 주제품처럼 적었으면 '틀림'이다.\n"
        "verdicts 배열로 출력하되 **각 항목에 image_no(1부터)를 반드시 넣어라** — 어느 이미지의 "
        "판정인지 번호로 명시해야 한다. 모든 이미지를 빠짐없이 판정하고, reason은 한국어 한 줄로 짧게.")
    parts = [prompt]
    for fp in frame_paths:
        try:
            with open(fp, "rb") as fh:
                parts.append(types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg"))
        except Exception as e:  # noqa: BLE001
            # 장수가 어긋나면 판정↔묘사 짝이 밀린다 — 통째로 포기하되 이유는 남긴다.
            log.info("tag_qa_frames._judge 건너뜀 — 프레임을 못 읽었다(%s): %s", fp, e)
            return []
    try:
        resp = comment_gen._client_for_key(key).models.generate_content(
            model=_MODEL, contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=_VERDICT_SCHEMA))
        return json.loads(resp.text).get("verdicts", []) or []
    except Exception as e:  # noqa: BLE001
        log.info("tag_qa_frames._judge 실패(무해) — %s", e)
        return []


def spot_check(result, video_path, dest_dir, *, _frames_fn=None, _judge_fn=None):
    """대표 프레임 대조 → {"frame_score", "checked", "detail"} 또는 None.

    None을 주는 경우 = 판단할 수 없었던 경우(세그 없음·프레임 실패·모델 실패). 이때 호출부는
    아무것도 기록하지 않는다 — **모르는 것을 0점으로 적으면 나중에 '태깅이 나빠졌다'는
    거짓 신호가 된다.** 점수와 '측정 못 함'은 반드시 구분한다.

    ★단 '기록하지 않는다'가 '아무도 모르게'는 아니다(2026-08-01): None으로 돌아가는 세 갈래
    전부 이유를 로그로 남긴다. `_judge`의 키 없음만 고쳐도 확대 실측의 21건은 설명되지만,
    프레임을 한 장도 못 뽑은 경우와 판정이 전부 버려진 경우는 여전히 흔적이 없었다 —
    frame_score가 안 붙었을 때 '왜'를 물을 수 있어야 이 지표가 쓸모 있다."""
    picked = pick_segments((result or {}).get("segments") or [])
    if not picked:
        log.info("tag_qa_frames: 측정 못 함 — 대조할 세그가 없다(세그 0개거나 전부 너무 짧다)")
        return None
    frames_fn = _frames_fn or _extract_frames
    paths, kept = frames_fn(video_path, picked, dest_dir)
    if not paths:
        log.info("tag_qa_frames: 측정 못 함 — 대표 %d개 중 프레임을 한 장도 못 뽑았다(%s)",
                 len(picked), video_path)
        return None
    verdicts = (_judge_fn or _judge)(paths, kept)
    score, detail = score_verdicts(verdicts, kept)
    if score is None:
        # 판정이 0건이거나 image_no가 전부 안 맞아 버려진 경우. _judge가 이미 이유를 남겼을
        # 수도 있지만(키 없음 등), 판정이 왔는데 전부 버려진 경우는 여기서만 보인다.
        log.info("tag_qa_frames: 측정 못 함 — 쓸 수 있는 판정이 0건이다(프레임 %d장, 판정 %d건)",
                 len(paths), len(verdicts or []))
        return None
    return {"frame_score": score, "checked": len(detail), "detail": detail}
