"""프레임 태깅 추출전환 B1 (2026-07-29) — 순수 조립 로직.

영상 통째 업로드(느림의 정체) 대신: 파이썬이 컷 경계(scene_cut)로 구간을 나누고, 오디오를
Whisper로 워드 타임스탬프 전사(asr_check.transcribe_words)해 구간별 나레이션을 붙인다. 제미니는
프레임 몇 장만 받아 구간별 시각 태그(scene_desc/shot_role/is_key/product_benefits)를 단다.

이 모듈은 **순수 함수만** — 컷·워드·태그를 받아 세그먼트로 조립한다(ffmpeg·Gemini I/O 없음).
그래서 단위테스트가 빠르고, script_extract(accident zone)를 건드리지 않는다. 조립기(I/O 붙는
extract_script_frames)는 이 함수들을 쓴다.
설계: docs/superpowers/specs/2026-07-29-프레임태깅-추출전환-design.md
"""

# shot_role 어휘는 `shot_roles`가 혼자 정한다(0순위-B). 아래 프롬프트 문구와 JSON enum이
# **같은 목록**에서 나오게 하려고 모듈 최상단에서 들여온다(_TAGS_SCHEMA가 로드 시점에 쓴다).
import os

from shopping_shorts import shot_roles as _shot_roles


def segments_from_cuts_and_words(cuts, words):
    """컷 경계(오름차순 타임스탬프)와 워드 타임스탬프 → [{start,end,text}].

    cuts=[t0,t1,...] 이면 구간은 [t0,t1),[t1,t2),... (경계 개수-1개). 경계가 1개 이하면
    구간을 못 만들어 [] (호출부가 기존 경로로 폴백). 워드는 start가 구간 [s,e)에 들면 그
    구간 text에 순서대로 붙인다(경계에 걸친 start==e는 다음 구간으로 — 누락 방지).
    words가 None/빈값이면 모든 구간 text는 빈칸(무자막·키없음, fail-open)."""
    ts = [float(c) for c in (cuts or [])]
    if len(ts) < 2:
        return []
    segs = [{"start": ts[i], "end": ts[i + 1], "text": ""} for i in range(len(ts) - 1)]
    buckets = [[] for _ in segs]
    for w in (words or []):
        try:
            st = float(w["start"])
            word = str(w["word"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not word:
            continue
        for i, seg in enumerate(segs):
            # [start, end) — 단, 마지막 구간은 end 포함(끝 워드 누락 방지)
            last = i == len(segs) - 1
            if seg["start"] <= st < seg["end"] or (last and st >= seg["start"]):
                buckets[i].append(word)
                break
    for seg, words_in in zip(segs, buckets):
        seg["text"] = " ".join(words_in)
    return segs


_TAG_DEFAULTS = {"scene_desc": "", "shot_role": "기타", "is_key": False,
                 "action": None, "has_effect": False, "product_benefits": []}


def merge_frame_tags(segs, tags):
    """세그먼트(start/end/text)에 제미니 프레임 태그를 인덱스로 병합.

    tags[i]가 segs[i]에 붙는다. 태그가 모자라면(길이 불일치) 남는 세그먼트는 기본값
    (fail-open — 크래시·누락 금지). scene_desc·shot_role·is_key·product_benefits만 태그에서
    가져오고 나머지 세그먼트 필드(start/end/text)는 보존한다."""
    out = []
    tags = tags or []
    for i, seg in enumerate(segs):
        tag = tags[i] if i < len(tags) and isinstance(tags[i], dict) else {}
        merged = dict(seg)
        for k, default in _TAG_DEFAULTS.items():
            merged[k] = tag.get(k, default)
        # product_benefits 정규화(str도 리스트로)
        pb = merged.get("product_benefits")
        if isinstance(pb, str):
            merged["product_benefits"] = [pb] if pb.strip() else []
        elif not isinstance(pb, list):
            merged["product_benefits"] = []
        out.append(merged)
    return out


def full_text_of(segs):
    """세그먼트 text들을 발화 순서대로 이어 full_text 생성(대본 재료·표절검사용)."""
    return " ".join(s.get("text", "").strip() for s in (segs or []) if s.get("text", "").strip())


_EMPTY = {"segments": [], "full_text": "", "product_benefits": []}


# ── 2026-09-04 수리 상수 (설계: docs/superpowers/specs/2026-09-04-3단계매칭-파서재설계-design.md §9-5) ──
# ★컷당 프레임 수. 종전 1장(중간)은 한 컷 안의 변화를 놓쳤다(실측 s0 14.07~16.67 "바닐라·초코·말차
#   차례로" → 중간 한 장만 보고 "초코 쿠키" 하나로). 시작·중간·끝 3장이면 잡힌다.
FRAMES_PER_CUT = 3
# ★컷당 프레임 k장은 **띠 한 장**으로 합쳐 보낸다(구간당 이미지 1장). 띠의 세로 픽셀.
STRIP_HEIGHT = 360
# ★원테이크(컷 없음) 강제 분할 상한. 실측 s1: 컷 3개 → 51초짜리 세그 1개 = 한 줄 묘사로 51초를 덮어
#   중간 프레임이 다른 장면. 이보다 긴 구간은 균등 분할한다.
MAX_SPAN_SEC = 7.0
# ★태깅·판정에 쓰는 모델 순서. response_schema(enum) 강제 호출은 gemini-3.5-flash에서 120초를 넘겨
#   죽었다(2026-09-04 실측: 판정 4/4·태깅 1/1 DEADLINE_EXCEEDED). 같은 이미지 10장을 스키마 없이
#   부르면 lite 8초·3.5-flash 5초. 그래서 **스키마 없이** 부르고 값은 코드가 검증한다.
#   lite를 앞에 둔 이유: 25장까지 16초로 안정적이었고(4편 실측), 3.5-flash는 503 spike 이력이 있다.
TAG_MODELS = ("gemini-3.1-flash-lite", "gemini-3.5-flash")


def split_long_spans(bounds, max_span=MAX_SPAN_SEC):
    """max_span보다 긴 구간을 균등 분할한 경계 목록(순수 함수).

    [0, 51, 75]에 max_span=7 → 0~51은 8조각(6.4초씩), 51~75는 4조각(6초씩).
    경계가 2개 미만이면 그대로. 컷이 있는 영상은 대개 손대지 않는다(컷 간격 < 상한)."""
    ts = sorted({float(b) for b in (bounds or [])})
    if len(ts) < 2 or not max_span or max_span <= 0:
        return ts
    out = [ts[0]]
    for a, b in zip(ts, ts[1:]):
        n = int((b - a) // max_span) + (1 if (b - a) % max_span > 1e-6 else 0)
        n = max(1, n)
        step = (b - a) / n
        out.extend(round(a + step * k, 3) for k in range(1, n))
        out.append(b)
    return out


def frame_times(start, end, k=FRAMES_PER_CUT, margin=0.15):
    """한 구간에서 뽑을 프레임 시각 k개(순수 함수). 시작·끝은 전환 순간을 피해 margin만큼 안쪽.
    구간이 짧으면(margin*2보다 작으면) 중간 한 장만."""
    a, b = float(start), float(end)
    if k <= 1 or (b - a) <= margin * 2 + 0.2:
        return [(a + b) / 2.0]
    lo, hi = a + margin, b - margin
    if k == 2:
        return [lo, hi]
    step = (hi - lo) / (k - 1)
    return [round(lo + step * i, 3) for i in range(k)]


def make_strip(paths, out_path, height=STRIP_HEIGHT):
    """프레임 여러 장을 왼쪽부터 가로로 이어붙인 띠 한 장(JPEG). 실패·1장 이하면 None.
    구간당 이미지를 1장으로 유지해 모델의 '이미지↔구간' 짝이 못 어긋나게 한다(위 상수 주석)."""
    if not paths or len(paths) < 2:
        return None
    try:
        from PIL import Image
        ims = []
        for p in paths:
            im = Image.open(p).convert("RGB")
            w = max(1, int(im.width * height / max(1, im.height)))
            ims.append(im.resize((w, height)))
        gap = 4
        strip = Image.new("RGB", (sum(im.width for im in ims) + gap * (len(ims) - 1), height), "white")
        x = 0
        for im in ims:
            strip.paste(im, (x, 0))
            x += im.width + gap
        strip.save(out_path, "JPEG", quality=85)
        return out_path
    except Exception as e:  # noqa: BLE001 — 띠 실패는 중간 한 장으로 간다(fail-open)
        print(f"frame_script.make_strip: 실패(중간 한 장으로) — {e!r}", file=__import__("sys").stderr)
        return None


def _default_boundaries(video_path):
    """실 컷 경계 리스트 [0, cut1, ..., duration]. detect_cuts(내부 컷)+길이로 조립.
    감지 실패/짧으면 길이만 알면 통구간 1개([0,dur])라도 만든다(호출부 폴백 최소화).

    ★2026-09-04 수리: `detect_cuts`는 07-20부터 **(start_frame, end_frame) 튜플**을 돌려준다.
      종전 `float(c)`가 TypeError를 내고 except가 삼켜 **항상 [0, dur] 구간 1개**였다(실측 s0:
      컷 12개인데 B1 세그 1개). 프레임 번호를 fps로 초로 바꾼다. 옛 형식(초 float)도 받는다.
    ★긴 구간은 MAX_SPAN_SEC로 강제 분할(원테이크 대비)."""
    from shopping_shorts import scene_cut, frame_extract
    try:
        dur = float(frame_extract._probe_duration(video_path))
    except Exception:
        dur = 0.0
    if dur <= 0:
        return []
    cuts = set()
    try:
        raw = scene_cut.detect_cuts(video_path, threshold=0.3)
        fps = None
        for c in raw or []:
            if isinstance(c, (tuple, list)):
                if fps is None:
                    fps = float(scene_cut.video_fps(video_path))
                cuts.add(float(c[0]) / fps)
                cuts.add(float(c[1]) / fps)
            else:
                cuts.add(float(c))
    except Exception as e:  # noqa: BLE001 — 컷 검출 실패는 통구간으로 간다(종전 계약)
        print(f"frame_script._default_boundaries: 컷 검출 실패(통구간으로) — {e!r}",
              file=__import__("sys").stderr)
        cuts = set()
    bounds = sorted({0.0, dur} | {round(c, 3) for c in cuts if 0.0 < c < dur})
    return split_long_spans(bounds, MAX_SPAN_SEC)


def normalize_tags(tags, n_segs):
    """모델 응답 tags를 코드가 검증한다(순수 함수) — 스키마 강제 대신 이 자리에서 거른다.
    · dict 아닌 항목·seg_no 범위 밖은 버린다
    · seg_no(1부터)가 있으면 그 자리에, 없으면 순서대로 채운다(모델이 하나 빠뜨려도 뒤가 안 밀린다)
    · shot_role은 shot_roles.normalize(모르는 값 → '기타'), is_key는 bool, product_benefits는 list
    반환: 길이 n_segs, 빈 자리는 {}(merge_frame_tags가 기본값으로 채운다)."""
    out = [{} for _ in range(max(0, int(n_segs)))]
    seq = 0
    for t in (tags or []):
        if not isinstance(t, dict):
            continue
        no = t.get("seg_no", t.get("image_no"))
        try:
            idx = int(no) - 1 if no is not None and not isinstance(no, bool) else seq
        except (TypeError, ValueError):
            idx = seq
        seq = idx + 1
        if not (0 <= idx < len(out)):
            continue
        pb = t.get("product_benefits")
        if isinstance(pb, str):
            pb = [pb] if pb.strip() else []
        elif not isinstance(pb, list):
            pb = []
        out[idx] = {
            "scene_desc": str(t.get("scene_desc") or "").strip(),
            "shot_role": _shot_roles.normalize(t.get("shot_role")),
            "is_key": bool(t.get("is_key", False)),
            "product_benefits": [str(x) for x in pb if str(x).strip()],
        }
    return out


def _gemini_tag_frames(frame_groups, caption, segs):
    """구간별 프레임 묶음 → 제미니가 구간별 시각태그 배열 반환.
    영상 통째 대신 이미지 파트만 보낸다(업로드/PROCESSING 급감). 실패 시 [](호출부 fail-open).
    반환: [{scene_desc, shot_role, is_key, product_benefits}, ...] (구간 순서, 길이 = len(segs)).

    ★2026-09-04 수리 둘:
      · frame_groups는 구간별 **묶음**(list of list). 종전 평평한 목록은 "N장 = N구간"을 전제해
        컷당 여러 장을 못 실었다. 프롬프트에 "k번 장면 = 이미지 a~b번"을 명시한다.
      · response_schema를 **안 쓴다** — enum 스키마 강제 호출이 gemini-3.5-flash에서 120초 초과로
        죽어 태깅이 통째로 실패하고 옛 추출로 조용히 폴백했다. 값 검증은 normalize_tags가 한다.
        모델은 TAG_MODELS 순서로 시도한다."""
    import json
    from shopping_shorts import comment_gen
    try:
        from google.genai import types
    except Exception:
        return []
    key, idx = comment_gen._current_key_and_idx()
    if key is None:
        return []
    groups = [list(g or []) for g in (frame_groups or [])]
    # 옛 호출 규약(평평한 경로 목록)도 받는다 — 문자열이 섞여 있으면 한 장씩 묶음으로 본다.
    if any(isinstance(g, str) for g in (frame_groups or [])):
        groups = [[g] if isinstance(g, str) else list(g or []) for g in frame_groups]
    parts_img, seg_lines, n = [], [], 0
    for i, s in enumerate(segs):
        g = groups[i] if i < len(groups) else []
        loaded = []
        for fp in g:
            try:
                with open(fp, "rb") as fh:
                    loaded.append(types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg"))
            except Exception:
                continue
        a, b = n + 1, n + len(loaded)
        n += len(loaded)
        img_s = (f"이미지 {a}~{b}번(시작→끝 순)" if b > a else f"이미지 {a}번" if loaded else "이미지 없음")
        seg_lines.append(
            f"{i+1}번 장면({round(s.get('start',0),1)}~{round(s.get('end',0),1)}초) = {img_s} | "
            f"나레이션:{s.get('text','') or '(없음)'}")
        parts_img.extend(loaded)
    if not parts_img:
        return []
    prompt = (
        "아래는 한 영상을 장면전환마다 자른 구간들이다. **구간 하나 = 이미지 한 장**이고, 각 이미지는 "
        "그 구간의 시작·중간·끝 프레임을 **왼쪽부터 가로로 이어붙인 띠**다(왼쪽이 구간 시작, 오른쪽이 끝). "
        f"총 {len(parts_img)}장 = 구간 {len(segs)}개. 띠 안의 변화까지 보고 구간별 태그를 매겨라.\n"
        + "\n".join(seg_lines) + "\n\n"
        "각 구간마다: seg_no(구간 번호, 1부터), scene_desc(그 구간에서 화면에 무엇이 보이고 무엇이 "
        "바뀌나 짧게 — 주 대상 정확히, 프레임이 여러 장이면 변화까지), "
        + _shot_roles.prompt_line() + ", is_key(제품 기능·효과를 화면으로 "
        "실증하면 true, 도입·인사·CTA면 false), product_benefits(자막 없어도 화면으로 보이는 특장점 "
        "한국어 1~2문장, 없으면 빈 배열).\n"
        '출력은 JSON 객체 {"tags": [{"seg_no": 1, "scene_desc": "...", "shot_role": "...", '
        '"is_key": false, "product_benefits": []}, ...]} 만. 구간을 빠짐없이, 구간 순서대로.'
        f"\n캡션(참고):{caption or '(없음)'}")
    parts = [prompt] + parts_img
    client = comment_gen._client_for_key(key)
    for model in TAG_MODELS:
        try:
            resp = client.models.generate_content(
                model=model, contents=parts,
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            data = json.loads(resp.text or "")
            raw = data.get("tags") if isinstance(data, dict) else data
            tags = normalize_tags(raw, len(segs))
            if any(tags):
                return tags
            print(f"frame_script._gemini_tag_frames: {model} 응답에 쓸 태그 없음 → 다음 모델",
                  file=__import__('sys').stderr)
        except Exception as e:  # noqa: BLE001 — 다음 모델로
            print(f"frame_script._gemini_tag_frames: {model} 실패 — {e!r}", file=__import__('sys').stderr)
    return []


_TAGS_SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "object", "properties": {
        "scene_desc": {"type": "string"},
        # ★enum과 위 프롬프트 문구는 **같은 목록**(shot_roles.SHOT_ROLES)에서 나온다.
        # 따로 적으면 모델이 프롬프트대로 답했는데 스키마가 거절하는 일이 생긴다.
        "shot_role": {"type": "string", "enum": list(_shot_roles.SHOT_ROLES)},
        "is_key": {"type": "boolean"},
        "product_benefits": {"type": "array", "items": {"type": "string"}},
    }, "required": ["scene_desc", "shot_role"]}}},
    "required": ["tags"],
}


def extract_script_frames(video_path, video_id, caption="", *, _no_classic=False,
                          get_boundaries=None, extract_frame_at=None,
                          extract_audio=None, transcribe_words=None, tag_frames=None):
    """B1 조립기: 영상 통째 업로드 없이 {segments, full_text, product_benefits} 반환.
    출력 스키마는 script_extract.extract_script와 100% 동일(다운스트림 무변경).
    모든 I/O는 주입 가능(기본은 실제 구현) — 단위테스트가 목킹한다. 컷 못 만들면 빈 결과."""
    import tempfile
    from pathlib import Path
    from shopping_shorts import script_extract
    get_boundaries = get_boundaries or _default_boundaries
    if extract_frame_at is None:
        from shopping_shorts import frame_extract
        extract_frame_at = frame_extract.extract_frame_at
    if extract_audio is None:
        from shopping_shorts import scene_assets
        extract_audio = scene_assets.extract_audio
    if transcribe_words is None:
        from shopping_shorts import asr_check
        transcribe_words = asr_check.transcribe_words
    tag_frames = tag_frames or _gemini_tag_frames

    boundaries = get_boundaries(video_path)
    if len(boundaries or []) < 2:
        return dict(_EMPTY)

    # 오디오 전사(실패·키없음 → None, text 빈칸 fail-open)
    words = None
    try:
        work = Path(tempfile.mkdtemp(prefix="frame_asr_"))
        mp3 = extract_audio(video_path, str(work / "audio.mp3"))
        if mp3:
            words = transcribe_words(mp3)
    except Exception:
        words = None

    segs = segments_from_cuts_and_words(boundaries, words)
    if not segs:
        return dict(_EMPTY)

    # ★구간마다 프레임 k장(시작·중간·끝) — 파일명을 **구간·장마다 다르게** 준다(2026-09-04 수리).
    #   종전엔 파일명 없이 불러 기본값 `frame_hint.jpg`에 전부 덮어썼다 → frame_paths가 같은 경로
    #   N개 = 모든 컷이 **마지막 프레임 한 장**으로 태깅됐다(조용한 버그, 실측으로 확인).
    #   tag_frames엔 구간별 묶음(list of list)으로 넘긴다 — 묶음 수 = 구간 수.
    #   ★구간당 이미지는 **띠 한 장**으로 합쳐 보낸다(2026-09-04 2차 실측). 이미지 2~3장을 따로
    #     싣고 "k번 장면 = 이미지 a~b번"이라 적어 줘도 모델(lite)이 **이미지 1장 = 구간 1개**로 세어
    #     묘사가 2배로 압축돼 밀렸다(s3: 12.73초 재료표가 37.23초 칸에). 띠로 합치면 이미지 수 =
    #     구간 수라 짝이 구조적으로 못 어긋난다. 합치기 실패(PIL 없음 등)면 중간 한 장만 쓴다.
    frame_dir = tempfile.mkdtemp(prefix="frame_tag_")
    frame_groups = []
    for i, s in enumerate(segs):
        shots = []
        for j, t in enumerate(frame_times(s["start"], s["end"], FRAMES_PER_CUT)):
            try:
                fp = extract_frame_at(video_path, frame_dir, t, f"seg{i:03d}_{j}.jpg")
            except Exception:
                fp = None
            if fp:
                shots.append(fp)
        strip = make_strip(shots, os.path.join(frame_dir, f"seg{i:03d}_strip.jpg")) if len(shots) > 1 else None
        frame_groups.append([strip] if strip else ([shots[len(shots) // 2]] if shots else []))

    tags = tag_frames(frame_groups, caption, segs) or []
    # 태깅이 실패(빈 태그: 제미니 503 과부하 등)면 장면 설명이 전부 비어 매칭이 망가진다.
    # 이땐 검증된 기존 추출(extract_script, 503 폴백모델 내장)로 넘겨 품질을 지킨다(2026-07-29 실측:
    # gemini 503 spike 때 프레임태깅이 죄다 실패했다). _no_classic=True면 폴백 안 함(테스트/재귀방지).
    if not tags and not _no_classic:
        from shopping_shorts import script_extract
        return script_extract.extract_script(video_path, video_id, caption=caption)
    merged = merge_frame_tags(segs, tags)
    segments = script_extract._assign_seg_ids(video_id, merged)
    return {
        "segments": segments,
        "full_text": full_text_of(segments),
        "product_benefits": script_extract._collect_benefits(segments),
    }
