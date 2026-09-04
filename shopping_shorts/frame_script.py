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
                 "action": None, "has_effect": False, "product_benefits": [],
                 # ★2026-09-04: 통째 업로드 추출과 같은 필드를 낸다 — 3단계 인벤토리가 쓰임(label)·활용(use_point)·
                 #   변화(change)를 읽는데 B1은 종전에 이 셋을 아예 안 줬다(빈칸 = 매칭 재료 손실).
                 "label": "", "use_point": "", "change": ""}


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
# ★1차 브리프용 격자(컷 대표 프레임 전체를 한 장에). 셀 세로 픽셀·최대 장수.
GRID_HEIGHT = 180
GRID_MAX = 40
# ★2차 태깅 한 호출에 넣는 구간 수. 필드 8개 × 27구간을 한 번에 넣으면 lite가 504·JSON 깨짐(실측 80~90초).
TAG_BATCH = 12
# ★원테이크(컷 없음) 강제 분할 상한. 실측 s1: 컷 3개 → 51초짜리 세그 1개 = 한 줄 묘사로 51초를 덮어
#   중간 프레임이 다른 장면. 이보다 긴 구간은 균등 분할한다.
MAX_SPAN_SEC = 7.0
# ★태깅·판정에 쓰는 모델 순서. response_schema(enum) 강제 호출은 gemini-3.5-flash에서 120초를 넘겨
#   죽었다(2026-09-04 실측: 판정 4/4·태깅 1/1 DEADLINE_EXCEEDED). 같은 이미지 10장을 스키마 없이
#   부르면 lite 8초·3.5-flash 5초. 그래서 **스키마 없이** 부르고 값은 코드가 검증한다.
#   lite를 앞에 둔 이유: 25장까지 16초로 안정적이었고(4편 실측), 3.5-flash는 503 spike 이력이 있다.
TAG_MODELS = ("gemini-3.1-flash-lite", "gemini-3.5-flash")

# 2차 태깅 응답의 모양(문서 + 어휘 계약). ★response_schema로 **보내지 않는다**(위 TAG_MODELS 주석 —
# 스키마 강제 호출이 120초 초과로 죽었다). 값 검증은 normalize_tags → script_extract._assign_seg_ids가 한다.
# shot_role enum은 shot_roles.SHOT_ROLES 한 목록에서 나온다(test_shot_role_axis가 어휘 일치를 검사한다).
_TAGS_SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "object", "properties": {
        "seg_no": {"type": "integer"},
        "scene_desc": {"type": "string"},
        "label": {"type": "string"},
        "use_point": {"type": "string"},
        "action": {"type": "string"},
        "change": {"type": "string"},
        "has_effect": {"type": "boolean"},
        "is_key": {"type": "boolean"},
        "shot_role": {"type": "string", "enum": list(_shot_roles.SHOT_ROLES)},
        "product_benefits": {"type": "array", "items": {"type": "string"}},
    }, "required": ["seg_no", "scene_desc", "shot_role"]}}},
    "required": ["tags"],
}


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


def make_strip(paths, out_path, height=STRIP_HEIGHT, label=None):
    """프레임 여러 장을 왼쪽부터 가로로 이어붙인 띠 한 장(JPEG). 실패·1장 이하면 None.
    구간당 이미지를 1장으로 유지해 모델의 '이미지↔구간' 짝이 못 어긋나게 한다(위 상수 주석).
    ★label(예 "#12 47.0s")을 주면 띠 왼쪽 위에 **번호를 찍는다**(2026-09-05 실측): 25구간을 한 호출에 넣으면 모델이
      띠 하나를 건너뛰고 그 뒤 seg_no가 전부 한 칸씩 밀렸다(s3 10번~, s2 17번~ → 판정 44~46%). 번호가 그림에
      박혀 있으면 "몇 번째 이미지인가"를 세지 않고 읽는다."""
    if not paths or len(paths) < 2:
        return None
    try:
        from PIL import Image, ImageDraw
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
        if label:
            d = ImageDraw.Draw(strip)
            txt = str(label)
            d.rectangle((0, 0, 10 + 7 * len(txt), 18), fill="black")
            d.text((4, 3), txt, fill="white")
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
            "has_effect": bool(t.get("has_effect", False)),
            "product_benefits": [str(x) for x in pb if str(x).strip()],
            # 아래 넷은 원문 그대로 넘긴다 — script_extract._assign_seg_ids가 통째 업로드 추출과
            # **같은 정규화**(_norm_label·_norm_use_point·action 사전·change strip)를 건다(0순위-B).
            "label": t.get("label"),
            "use_point": t.get("use_point"),
            "action": t.get("action"),
            "change": t.get("change"),
        }
    return out


def make_grid(paths, out_path, times=None, cols=4, height=GRID_HEIGHT, max_n=GRID_MAX):
    """컷 대표 프레임들을 격자 한 장으로(1차 브리프용 — 영상 전체를 한눈에). 실패면 None.
    times(초 목록)를 주면 칸 왼쪽 위에 그 컷의 시각을 찍는다 — 없으면 모델이 flow의 초를 지어낸다
    (실측: 78초 영상에 "0~4초 → 12~15초")."""
    pairs = [(p, (times[i] if times and i < len(times) else None))
             for i, p in enumerate(paths or []) if p][:max_n]
    if not pairs:
        return None
    try:
        from PIL import Image, ImageDraw
        ims = []
        for p, t in pairs:
            im = Image.open(p).convert("RGB")
            w = max(1, int(im.width * height / max(1, im.height)))
            im = im.resize((w, height))
            if t is not None:
                d = ImageDraw.Draw(im)
                label = f"{float(t):.1f}s"
                d.rectangle((0, 0, 8 + 7 * len(label), 16), fill="black")
                d.text((3, 2), label, fill="white")
            ims.append(im)
        cell_w = max(im.width for im in ims)
        rows = (len(ims) + cols - 1) // cols
        grid = Image.new("RGB", (cell_w * cols, height * rows), "white")
        for k, im in enumerate(ims):
            grid.paste(im, ((k % cols) * cell_w, (k // cols) * height))
        grid.save(out_path, "JPEG", quality=85)
        return out_path
    except Exception as e:  # noqa: BLE001
        print(f"frame_script.make_grid: 실패 — {e!r}", file=__import__("sys").stderr)
        return None


def brief_block(brief):
    """브리프 dict → 2차 태깅 프롬프트에 넣을 '큰 그림' 문단(순수 함수). 비면 ""."""
    b = brief or {}
    if not any(b.get(k) for k in ("product", "flow", "summary", "core")):
        return ""
    lines = ["[이 영상의 큰 그림 — 1차로 전체를 보고 정리한 것. 구간 묘사·역할(label)은 이 흐름 안에서 정한다]"]
    for k, name in (("product", "제품"), ("role", "영상의 몫"), ("core", "요지"),
                    ("flow", "시간 흐름"), ("summary", "요약"), ("confidence", "스토리 확신도")):
        if b.get(k):
            lines.append(f"- {name}: {b[k]}")
    if (b.get("confidence") or "") == "불명":
        lines.append("★스토리가 불명이다 — 역할(label)은 화면에 보이는 것만으로 보수적으로, 안 보이는 전개를 지어내지 마라.")
    return "\n".join(lines)


def is_foreign_text(text):
    """전사가 한국어가 아닌가(순수 함수). 글자 중 한글 비율이 30% 미만이면 외국어로 본다.
    글자가 없으면(무자막) False — 번역할 게 없다."""
    letters = [c for c in (text or "") if c.isalpha()]
    if len(letters) < 4:
        return False
    hangul = sum(1 for c in letters if "가" <= c <= "힣")
    return hangul / len(letters) < 0.3


def _gemini_translate(texts):
    """구간별 원문 목록 → 같은 길이의 한국어 번역 목록(빈 원문은 ""). 실패는 [](fail-open).
    텍스트만 보내는 한 호출. 번역은 **자연스러운 구어체 한국어**로, 숫자·제품명은 보존."""
    import json
    from shopping_shorts import comment_gen
    try:
        from google.genai import types
    except Exception:
        return []
    key, _ = comment_gen._current_key_and_idx()
    if key is None:
        return []
    items = [{"no": i + 1, "text": (t or "").strip()} for i, t in enumerate(texts or [])]
    if not any(x["text"] for x in items):
        return []
    prompt = (
        "아래는 숏폼 영상의 구간별 나레이션·자막 원문이다(영어·중국어 등). 각 항목을 **자연스러운 구어체 한국어**로 "
        "번역해라. 숫자·단위·제품명·브랜드는 그대로 보존하고, 빈 원문은 빈 문자열로.\n"
        + json.dumps(items, ensure_ascii=False)
        + '\n\n출력은 JSON 객체 {"items": [{"no": 1, "ko": "..."}, ...]} 만. 항목을 빠짐없이.')
    client = comment_gen._client_for_key(key)
    for model in TAG_MODELS:
        try:
            resp = client.models.generate_content(
                model=model, contents=[prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            data = loads_lenient(resp.text)
            raw = data.get("items") if isinstance(data, dict) else data
            out = [""] * len(items)
            for r in raw or []:
                try:
                    k = int(r.get("no")) - 1
                except (TypeError, ValueError, AttributeError):
                    continue
                if 0 <= k < len(out):
                    out[k] = str(r.get("ko") or "").strip()
            if any(out):
                return out
        except Exception as e:  # noqa: BLE001
            print(f"frame_script._gemini_translate: {model} 실패 — {e!r}", file=__import__("sys").stderr)
    return []


def _gemini_story_brief(grid_path, caption, transcript):
    """1차 — 컷 대표 프레임 격자 한 장 + 캡션 + 전사로 영상 전체의 스토리 브리프를 뽑는다.
    실패는 {}(fail-open — 2차 태깅은 브리프 없이 종전대로 돈다).

    ★왜 두 번 보나(2026-09-04 사장님 "대사 없는 외국 영상, 컷만 따로 보면 나중에 못 쓰지 않나"):
      컷을 하나씩 떼어 보면 '먼지 낀 방충망'이 before인지 그냥 방충망인지 모른다. 전체 흐름을
      먼저 잡고(1차), 그 흐름을 알려준 채 컷을 보게(2차) 해야 역할이 맞는다."""
    import json
    from shopping_shorts import comment_gen, script_extract
    try:
        from google.genai import types
    except Exception:
        return {}
    key, _ = comment_gen._current_key_and_idx()
    if key is None or not grid_path:
        return {}
    try:
        with open(grid_path, "rb") as fh:
            img = types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg")
    except Exception:
        return {}
    prompt = (
        "아래 이미지는 한 영상을 장면전환마다 자른 대표 프레임을 **왼쪽→오른쪽, 위→아래 시간순**으로 격자에 "
        "모은 것이다. **각 칸 왼쪽 위의 숫자(예 12.7s)가 그 컷의 실제 시각(초)**이다 — flow의 초는 이 숫자로 적어라. "
        "영상 전체를 먼저 파악해 source_brief를 정리해라.\n\n"
        + script_extract._BRIEF_GUIDE
        + f"\n\n캡션(참고용, 화면이 우선): {caption or '(없음)'}"
        + f"\n들리는 말/자막(참고용, 없으면 화면만으로): {(transcript or '').strip()[:1500] or '(없음)'}"
        + '\n\n출력은 JSON 객체 {"source_brief": {"product": "...", "role": "...", "core": "...", "summary": "...", '
          '"flow": "...", "confidence": "높음|낮음|불명"}} 만.')
    client = comment_gen._client_for_key(key)
    for model in TAG_MODELS:
        try:
            resp = client.models.generate_content(
                model=model, contents=[prompt, img],
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            data = loads_lenient(resp.text)
            raw = data.get("source_brief") if isinstance(data, dict) and "source_brief" in data else data
            brief = script_extract._norm_brief(raw)
            if brief:
                return brief
        except Exception as e:  # noqa: BLE001
            print(f"frame_script._gemini_story_brief: {model} 실패 — {e!r}", file=__import__("sys").stderr)
    return {}


def loads_lenient(text):
    """JSON 앞부분만 읽는다 — 모델이 객체 뒤에 쓰레기를 붙여도(실측 "Extra data: line 17") 버리지 않는다."""
    import json
    t = (text or "").strip()
    if not t:
        raise ValueError("빈 응답")
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:] if t[:4].lower() == "json" else t
    i = min([k for k in (t.find("{"), t.find("[")) if k >= 0] or [0])
    obj, _ = json.JSONDecoder().raw_decode(t[i:])
    return obj


def _gemini_tag_frames(frame_groups, caption, segs, brief=None):
    """구간별 프레임 묶음(+1차 브리프) → 제미니가 구간별 시각태그 배열 반환.
    영상 통째 대신 이미지 파트만 보낸다(업로드/PROCESSING 급감). 실패 시 [](호출부 fail-open).
    반환: 길이 = len(segs)의 태그 배열(빈 자리는 {}).

    ★2026-09-04 수리:
      · frame_groups는 구간별 **묶음**(list of list, 보통 띠 1장). 옛 평평한 목록도 받는다.
      · response_schema를 **안 쓴다** — enum 스키마 강제 호출이 gemini-3.5-flash에서 120초 초과로
        죽어 태깅이 통째로 실패하고 옛 추출로 조용히 폴백했다. 값 검증은 normalize_tags가 한다.
      · **TAG_BATCH 구간씩 나눠 부른다** — 필드가 8개라 27구간을 한 호출에 넣으면 응답이 길어져 lite가
        504·JSON 깨짐으로 상위 모델에 떨어지고 80~90초가 걸렸다(실측). 12구간이면 한 호출 15초 안팎.
      · 필드 정의는 script_extract._SEG_FIELD_GUIDE 한 곳(0순위-B). 브리프가 있으면 그 큰 그림 안에서 정한다."""
    from shopping_shorts import comment_gen, script_extract
    try:
        from google.genai import types
    except Exception:
        return []
    key, idx = comment_gen._current_key_and_idx()
    if key is None:
        return []
    groups = [list(g or []) for g in (frame_groups or [])]
    if any(isinstance(g, str) for g in (frame_groups or [])):
        groups = [[g] if isinstance(g, str) else list(g or []) for g in frame_groups]
    _bb = brief_block(brief)
    _guide = script_extract._SEG_FIELD_GUIDE.format(_SHOT_ROLE_GUIDE=_shot_roles.guide_block())
    client = comment_gen._client_for_key(key)
    out = [{} for _ in segs]
    n_segs = len(segs)
    for b0 in range(0, n_segs, TAG_BATCH):
        b1 = min(n_segs, b0 + TAG_BATCH)
        parts_img, seg_lines = [], []
        for i in range(b0, b1):
            s = segs[i]
            g = groups[i] if i < len(groups) else []
            loaded = []
            for fp in g:
                try:
                    with open(fp, "rb") as fh:
                        loaded.append(types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg"))
                except Exception:
                    continue
            seg_lines.append(
                f"#{i + 1} ({round(s.get('start', 0), 1)}~{round(s.get('end', 0), 1)}초) "
                f"= {'이미지 ' + str(len(parts_img) + 1) + '번째, 띠 왼쪽 위에 #' + str(i + 1) if loaded else '이미지 없음'} | "
                f"나레이션:{s.get('text', '') or '(없음)'}")
            parts_img.extend(loaded[:1])          # 구간당 이미지 1장(띠)
        if not parts_img:
            continue
        prompt = (
            "아래는 한 영상을 장면전환마다 자른 구간들이다. **구간 하나 = 이미지 한 장**이고, 각 이미지는 "
            "그 구간의 시작·중간·끝 프레임을 **왼쪽부터 가로로 이어붙인 띠**다(왼쪽이 구간 시작, 오른쪽이 끝). "
            f"이번 묶음은 {len(parts_img)}장 = 구간 {b1 - b0}개(영상 전체 {n_segs}구간 중 {b0 + 1}~{b1}번째). "
            "띠 안의 변화까지 보고 구간별 태그를 매겨라.\n"
            + (_bb + "\n\n" if _bb else "")
            + "\n".join(seg_lines) + "\n\n"
            "각 구간마다 seg_no와 아래 필드를 적어라. ★seg_no는 **띠 왼쪽 위에 찍힌 # 번호**다(세지 말고 읽어라 — "
            "이미지 순서로 세면 하나만 건너뛰어도 뒤가 전부 밀린다). scene_desc는 띠 안에서 무엇이 보이고 무엇이 "
            "바뀌나까지(프레임이 여러 장이면 변화 순서대로).\n"
            + _guide + "\n\n"
            '출력은 JSON 객체 {"tags": [{"seg_no": 1, "scene_desc": "...", "label": "...", "use_point": "...", '
            '"action": "...", "change": "...", "has_effect": false, "is_key": false, "shot_role": "...", '
            '"product_benefits": []}, ...]} 만. 구간을 빠짐없이, 구간 순서대로. JSON 뒤에 다른 글을 붙이지 마라.'
            f"\n캡션(참고):{caption or '(없음)'}")
        parts = [prompt] + parts_img
        got = None
        # ★묶음마다 키를 새로 고른다(2026-09-05) — _current_key_and_idx는 라운드로빈이라 부를 때마다 다음 키.
        #   종전엔 함수 시작에 한 번만 골라 한 영상의 모든 묶음이 같은 키를 때렸다(분당 한도·503 스파이크에 취약,
        #   실측 s3 133~280초 흔들림). 503/429면 같은 모델을 다른 키로 한 번 더 시도한 뒤 다음 모델로.
        for model in TAG_MODELS:
            for attempt in range(2):
                _k2, _ = comment_gen._current_key_and_idx()
                client = comment_gen._client_for_key(_k2 or key)
                try:
                    resp = client.models.generate_content(
                        model=model, contents=parts,
                        config=types.GenerateContentConfig(response_mime_type="application/json"))
                    data = loads_lenient(resp.text)
                    raw = data.get("tags") if isinstance(data, dict) else data
                    # seg_no는 띠에 찍힌 전체 번호(#1부터) → 이번 묶음 기준으로 되돌린다. 묶음 밖 번호는 버려진다.
                    fixed = []
                    for t in (raw or []):
                        if isinstance(t, dict) and t.get("seg_no") is not None:
                            try:
                                t = dict(t, seg_no=int(t["seg_no"]) - b0)
                            except (TypeError, ValueError):
                                pass
                        fixed.append(t)
                    tags = normalize_tags(fixed, b1 - b0)
                    if any(tags):
                        got = tags
                    else:
                        print(f"frame_script._gemini_tag_frames: {model} 응답에 쓸 태그 없음 → 다음 모델",
                              file=__import__('sys').stderr)
                    break
                except Exception as e:  # noqa: BLE001
                    msg = repr(e)
                    transient = any(c in msg for c in ("429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded"))
                    print(f"frame_script._gemini_tag_frames: {model} 실패({'다른 키로 재시도' if transient and attempt == 0 else '다음 모델'}) — {msg[:120]}",
                          file=__import__('sys').stderr)
                    if not (transient and attempt == 0):
                        break
            if got:
                break
        if got:
            out[b0:b1] = got
    return out if any(out) else []


def extract_script_frames(video_path, video_id, caption="", *, _no_classic=False,
                          get_boundaries=None, extract_frame_at=None,
                          extract_audio=None, transcribe_words=None, tag_frames=None,
                          story_brief=None, translate=None):
    """B1 조립기: 영상 통째 업로드 없이 {segments, full_text, product_benefits, source_brief} 반환.
    출력 스키마는 script_extract.extract_script와 100% 동일(다운스트림 무변경).
    모든 I/O는 주입 가능(기본은 실제 구현) — 단위테스트가 목킹한다. 컷 못 만들면 빈 결과.

    ★두 번 본다(2026-09-04): 1차 story_brief(격자 한 장으로 전체 흐름) → 2차 tag_frames(구간 띠, 브리프를
      알려준 채). tag_frames는 (frame_groups, caption, segs, brief) 4인자. 브리프 실패는 {}(2차는 종전대로)."""
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
        # ★언어 자동 감지(2026-09-04) — 소스는 외국 영상이 많다. "ko" 고정이면 중국어·영어를 한국어로
        #   엉터리 받아쓴다. 원문 언어로 받아쓰고 아래 translate가 한국어(text_ko)를 붙인다.
        transcribe_words = lambda mp3: asr_check.transcribe_words(mp3, language=None)  # noqa: E731
    tag_frames = tag_frames or _gemini_tag_frames
    story_brief = story_brief or _gemini_story_brief
    translate = translate or _gemini_translate

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

    # ★외국어 전사면 한국어 번역(text_ko)을 붙인다(2026-09-04). 원문(text)은 그대로 둔다 —
    #   인벤토리·2단계 장면 목록은 text_ko를 '말:'로 쓰고, 대본 재료는 full_text_ko를 쓴다.
    if is_foreign_text(full_text_of(segs)):
        try:
            ko = translate([s.get("text", "") for s in segs]) or []
        except Exception as e:  # noqa: BLE001 — 번역 실패는 원문만으로 간다(fail-open)
            print(f"frame_script: 번역 실패(무해) — {e!r}", file=__import__("sys").stderr)
            ko = []
        for s, t in zip(segs, ko):
            if t:
                s["text_ko"] = t

    # ★구간마다 프레임 k장(시작·중간·끝) — 파일명을 **구간·장마다 다르게** 준다(2026-09-04 수리).
    #   종전엔 파일명 없이 불러 기본값 `frame_hint.jpg`에 전부 덮어썼다 → frame_paths가 같은 경로
    #   N개 = 모든 컷이 **마지막 프레임 한 장**으로 태깅됐다(조용한 버그, 실측으로 확인).
    #   tag_frames엔 구간별 묶음(list of list)으로 넘긴다 — 묶음 수 = 구간 수.
    #   ★구간당 이미지는 **띠 한 장**으로 합쳐 보낸다(2026-09-04 2차 실측). 이미지 2~3장을 따로
    #     싣고 "k번 장면 = 이미지 a~b번"이라 적어 줘도 모델(lite)이 **이미지 1장 = 구간 1개**로 세어
    #     묘사가 2배로 압축돼 밀렸다(s3: 12.73초 재료표가 37.23초 칸에). 띠로 합치면 이미지 수 =
    #     구간 수라 짝이 구조적으로 못 어긋난다. 합치기 실패(PIL 없음 등)면 중간 한 장만 쓴다.
    frame_dir = tempfile.mkdtemp(prefix="frame_tag_")
    frame_groups, mids, mid_times = [], [], []
    for i, s in enumerate(segs):
        shots = []
        for j, t in enumerate(frame_times(s["start"], s["end"], FRAMES_PER_CUT)):
            try:
                fp = extract_frame_at(video_path, frame_dir, t, f"seg{i:03d}_{j}.jpg")
            except Exception:
                fp = None
            if fp:
                shots.append(fp)
        strip = (make_strip(shots, os.path.join(frame_dir, f"seg{i:03d}_strip.jpg"),
                            label=f"#{i + 1} {float(s['start']):.1f}s")
                 if len(shots) > 1 else None)
        frame_groups.append([strip] if strip else ([shots[len(shots) // 2]] if shots else []))
        if shots:
            mids.append(shots[len(shots) // 2])
            mid_times.append((float(s["start"]) + float(s["end"])) / 2.0)

    # 1차 — 영상 전체의 스토리 브리프(격자 한 장, 칸마다 실제 초). 실패는 {}로 2차가 종전대로 돈다(fail-open).
    brief = {}
    try:
        grid = make_grid(mids, os.path.join(frame_dir, "grid.jpg"), times=mid_times)
        brief = story_brief(grid, caption, full_text_of(segs)) or {}
    except Exception as e:  # noqa: BLE001
        print(f"frame_script: 1차 브리프 실패(무해) — {e!r}", file=__import__("sys").stderr)
        brief = {}

    tags = tag_frames(frame_groups, caption, segs, brief) or []
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
        "source_brief": brief,       # 1차 브리프(product·role·core·summary·flow·confidence), 없으면 {}
        # 외국 소스의 한국어 전사 전문(대본 재료용). 한국어 소스는 빈칸 → 호출부가 full_text로 폴백.
        "full_text_ko": " ".join((s.get("text_ko") or "").strip() for s in segments
                                 if (s.get("text_ko") or "").strip()),
    }
