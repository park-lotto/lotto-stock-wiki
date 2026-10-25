#!/usr/bin/env python3
"""사진 앞단 거르기 — TypeSafe Jev 1.14(그림 입력)로 «확실히 못 쓸 사진»만 agy 판독 전에 뺀다.

■ 실행기 공용 부품 (2026-10-23 · 회원 기능 요청 «AGY 판독 앞에 Jev 이미지 1차 거름(선택 · TYPESAFE_API_KEY 있을 때만)» ·
  사장님 «회원 기능 요청 전부 수락»): 판정은 **이 파일 한 벌**이다. 예전에는 팟캐스트 팩 template/tools/jev_photo.py 에만
  있었다 — 팩은 이제 이 부품을 실행기 자리(VOLCANO_RUNNER_DIR · 없으면 ~/.volcano/runner — tools/venc_lookup.py 와 같은 길)에서
  읽는다. 다른 프리셋의 agy 사진 판독 앞에 붙일 때도 이 `prefilter` 를 부른다(복사 금지) — 단 그 단계의 정답지로
  먼저 잰 뒤에(전역 규칙 6-4 «잰 일은 이것 하나»: 아래 실측은 «주제 배경 사진 후보»). 부품이 없거나(옛 실행기) 열쇠가 없으면 거르지 않는다.

왜(2026-10-16 사장님 «podcast 에만 붙여» · 실측 /Volumes/Samsung_T5/jev results/image_1016/보고.md):
- agy 판독은 8장 묶음에 30~60초, Jev 는 장당 0.3초. 처음 보는 사진 555장(두 영상 · 정답 = 이 파일의 agy 판독 문구)에서
  점수 < 0.1 만 버리니 agy 로 넘긴 장수 76/206·198/349(10-16 bigtext 문구 바꾼 뒤), agy «예» 사진은 39/40 살렸다(버린 1장 = «도형 그래픽 일러스트»).
- 그래서 그림·도표·아이콘을 찾는 검색어는 거르지 않는다(Jev 가 그래픽을 로고·큰 글자로 본다) — 검색어 판정만 Jev 글 질문 1개.
- Jev 는 거르기만 한다. 최종 «쓸 만한가»는 언제나 agy(전역 규칙 6-1 «검수는 agy»).
- 실패하면 거르지 않는다: 키 없음·요청 실패·시간 초과·그림 규격 밖 → 그 사진은 그대로 agy 로 간다(작업은 멈추지 않는다).

키(볼케이노 규약 — 경로를 지어내지 않는다):
- 개발 PC(이 맥): volcano-mcp tools/devkeys.py 의 `key("typesafe")` 만(주인 확인된 키만 · 거부되면 Jev 없이 진행).
- 수강생 PC: 환경변수 TYPESAFE_API_KEY → 볼케이노 키 자리 ~/.volcano/keys/typesafe
  (volcano-mcp `volcano_spec.API_SERVICES["typesafe"]` 선언 · 실행기 `_service_key_value` 와 같은 순서·같은 인코딩 처리).
- 키 값은 어디에도 찍지 않는다(로그는 개수·초·사유만).

공식 숫자(출처를 그대로 옮김):
- 그림: 헤더 `TypeSafe-Danger-Zone-Images: true` · PNG/JPEG · 한 변 256~1568px · 파일 16MiB (docs.typesafe.ai/go/images)
- 동시: 공식 한도 초당 80요청(docs.typesafe.ai/models.md) — 여기선 실측 때와 같은 동시 4.
- 거부(429·529)면 그 실행의 Jev 요청을 전부 멈춘다(전역 규칙 6-2) · 재시도 없음.
"""
import base64
import io
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.14.0"            # 고정 판(공식 models.md «Aliases»: 문턱을 맞췄으면 판을 고정). 실측 판과 같다.
THRESHOLD = 0.1                 # 점수 < 0.1 이면 버린다 — 1차 32장에서 정하고 검증 555장에 한 번만 적용한 값
PAR = 4                         # 실측과 같은 동시 수(거부 0)
TIMEOUT = 20                    # 한 요청 상한(초) — 넘으면 그 사진은 agy 로
SIDE_MIN, SIDE_MAX = 256, 1568  # 공식 그림 규격
DEVKEYS = "/Volumes/Samsung_T5/volcano-mcp/tools/devkeys.py"   # 개발 PC 에만 있다(팟캐스트 팩 tools/voice_engines.py 와 같은 판별)
STUDENT_KEY = os.path.join("~", ".volcano", "keys", "typesafe")
ENV_VAR = "TYPESAFE_API_KEY"

# 실측(results/image_1016)과 글자 그대로 같은 질문 — 바꾸면 다시 잰다.
QUESTIONS = {
    "relevant": "Could `photo` naturally be used as a background or reference image in a video about the topic in `topic`? "
                "Showing only part of the topic (an object, place or person related to it) counts as yes.",
    "logo": "Is `photo` a logo, icon, or advertising banner rather than a photograph?",
    "screenshot": "Is `photo` a screenshot of an app, website, or software interface?",
    # 10-16 바꿈: 옛 문구(«large text … takes up a large part»)는 강연 사진 뒤 현수막 글자(agy 판독 넓이 16%)를 0.94 로 «큼» 판정해
    #   agy «예» 사진을 버렸다. 새 문구로 agy 정답 589장 재측정: 좋은 사진 43/44 그대로·이 사진 살림 0.05→0.82 · agy 로 넘김 늘어남(아래 머리말).
    "bigtext": "Does text cover more than about a quarter of the area of `photo`? Small or background text such as signs, banners, "
               "slides behind a speaker, labels or captions counts as no.",
    "watermark": "Does `photo` have a large or central watermark, or a stock-photo preview watermark (Shutterstock, Getty, iStock, "
                 "Adobe Stock, PREVIEW, SAMPLE, repeated translucent logos)? A small watermark in a corner does not count.",
}
REJECT = ("logo", "screenshot", "bigtext", "watermark")
GRAPHIC_Q = ("Does the search query in `query` ask for a non-photographic image: a graphic design, illustration, drawing, vector art, "
             "diagram, chart, graph, infographic, icon or logo? A query for a photo of a real scene counts as no, "
             "even if the scene contains screens, subtitles, text, timelines or devices.")
# 그림 검색어로 볼 문턱 — 10-16 검색어 29개를 두 번씩: 그래픽·도표·로고·일러스트 0.96~0.99 · 사진 검색어 0.08~0.66(흔들림 ±0.05).
#   0.8 이면 두 무리 사이가 넓어 같은 검색어가 실행마다 갈리지 않는다(옛 문구는 «영화 자막 화면» 0.42~0.50 으로 0.5 를 오갔다).
GRAPHIC_MIN = 0.8


def _read_text(path):
    """실행기 `_service_key_value` 와 같은 디코딩(윈도우 메모장 UTF-16·BOM)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig").strip()


def api_key():
    """(키, 출처) 또는 (None, 사유). 값은 돌려주기만 하고 찍지 않는다."""
    if os.path.isfile(DEVKEYS):
        sys.path.insert(0, os.path.dirname(DEVKEYS))
        try:
            import devkeys  # noqa: PLC0415
            val, _owner = devkeys.key("typesafe", quiet=True)
            return (val.reveal() if hasattr(val, "reveal") else str(val)), "devkeys"
        except Exception as e:                       # KeyRefused 등 — 개발 PC 규칙상 못 쓰면 Jev 없이 간다
            return None, f"devkeys 거부: {type(e).__name__}"
    v = (os.environ.get(ENV_VAR) or "").strip()
    if v:
        return v, "env"
    p = os.path.expanduser(STUDENT_KEY)
    try:
        v = _read_text(p)
    except FileNotFoundError:
        return None, "키 없음"
    except (OSError, UnicodeError) as e:
        return None, f"키 파일 읽기 실패: {type(e).__name__}"
    return (v, "file") if v else (None, "키 파일 비어 있음")


class Jev:
    def __init__(self, log):
        self.log = log
        self.key, self.src = api_key()
        self.stop = threading.Event()
        self.reason = None if self.key else self.src

    def _post(self, body, images):
        headers = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}
        if images:
            headers["TypeSafe-Danger-Zone-Images"] = "true"
        req = urllib.request.Request(URL, json.dumps(body).encode(), headers)
        try:
            return json.load(urllib.request.urlopen(req, timeout=TIMEOUT))["answers"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 529):
                self.stop.set()
                self.reason = f"Jev 거부 {e.code} → 이번 실행의 Jev 요청 전부 멈춤"
            return None
        except Exception:                             # 시간 초과·연결 실패·응답 모양 — 그 항목만 agy 로
            return None

    def graphic_query(self, query):
        """그림·도표 검색어면 True(거르지 않는다). 판정 못 하면 True(안전한 쪽 = 거르지 않음)."""
        a = self._post({"model": MODEL, "state": {"query": query},
                        "questions": {"graphic": {"type": "noul", "instructions": GRAPHIC_Q}}}, images=False)
        return True if a is None else a["graphic"]["noul"] >= GRAPHIC_MIN

    def score(self, path, topic):
        """점수(0~1) 또는 None(판정 못 함 → agy 로)."""
        if self.stop.is_set():
            return None
        try:
            from PIL import Image  # noqa: PLC0415  (팩 전용 가상환경 PIP_PACKAGES 에 pillow)
            im = Image.open(path).convert("RGB")
            im.thumbnail((SIDE_MAX, SIDE_MAX))
            if min(im.size) < SIDE_MIN:
                return None
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=90)
        except Exception:
            return None
        body = {"model": MODEL, "state": {"topic": topic, "photo": "img1"},
                "assets": {"img1": {"type": "image", "format": "jpg", "data_base64": base64.b64encode(buf.getvalue()).decode()}},
                "questions": {k: {"type": "noul", "instructions": v} for k, v in QUESTIONS.items()}}
        a = self._post(body, images=True)
        if a is None:
            return None
        p = {k: a[k]["noul"] for k in QUESTIONS}
        return p["relevant"] * (1 - max(p[k] for k in REJECT))


def prefilter(rows_by_query, log):
    """{검색어: [행(«file» 키)]} → 버릴 행을 뺀 같은 모양 + 통계. 행 순서는 그대로 둔다."""
    j = Jev(log)
    if not j.key:
        log(f"Jev 앞단 없음({j.reason}) — 전부 agy 판독")
        return rows_by_query, {"jev": "off", "why": j.reason}
    out, stats = {}, {"jev": MODEL, "key": j.src, "dropped": 0, "unjudged": 0, "graphic_queries": []}
    with ThreadPoolExecutor(PAR) as ex:
        graphic = dict(zip(rows_by_query, ex.map(j.graphic_query, rows_by_query)))
        for q, rows in rows_by_query.items():
            if graphic[q]:
                stats["graphic_queries"].append(q)
                out[q] = rows
                continue
            scores = list(ex.map(lambda r: j.score(r["file"], q), rows))
            keep = []
            for r, s in zip(rows, scores):
                if s is None:
                    stats["unjudged"] += 1
                    keep.append(r)
                elif s >= THRESHOLD:
                    keep.append(r)
                else:
                    stats["dropped"] += 1
            out[q] = keep
            log(f"Jev «{q}» {len(rows)}장 → agy 로 {len(keep)}장")
    if j.stop.is_set():
        stats["why"] = j.reason
        log(j.reason)
    return out, stats
