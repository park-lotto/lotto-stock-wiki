import os
import re
import json
import time
import hashlib
from pathlib import Path
from google import genai
from google.genai import types

_GEMINI_MODEL = "gemini-3.1-flash-lite"


def _load_gemini_keys() -> list[str]:
    """인제스트용 Gemini 키. 전용키(_3)가 있으면 그것만 사용해 대화형 리서치/이미지 키(_1·_2)와
    쿼터를 분리한다(대화형이 백그라운드 인제스트에 안 막히게). 없으면 _1·_2 폴백."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    env_vals: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_vals[k.strip()] = v.strip()

    def _v(name: str) -> str:
        return os.environ.get(name) or env_vals.get(name, "")

    # 인제스트 전용 키 우선 → 소진 시 API 키로 폴백 (전체 4개 rotation)
    ingest = [k for k in (_v("GEMINI_INGEST_KEY"), _v("GEMINI_INGEST_KEY_2"),
                          _v("GEMINI_INGEST_KEY_3"), _v("GEMINI_INGEST_KEY_4"),
                          _v("GEMINI_INGEST_KEY_5")) if k]
    api = [k for k in (_v("GEMINI_API_KEY"), _v("GEMINI_API_KEY_2"),
                       _v("GEMINI_API_KEY_3")) if k]
    return ingest + [k for k in api if k not in ingest]


def _load_gemini_key() -> str:
    keys = _load_gemini_keys()
    return keys[0] if keys else ""


_GEMINI_KEYS = _load_gemini_keys()
_key_idx = 0
_client_cache: dict[str, genai.Client] = {}  # 키별 클라이언트 캐시 (GC 방지)


def _get_client() -> genai.Client:
    """현재 활성 키로 클라이언트 반환. 키당 1개 인스턴스를 캐시해 GC로 인한 커넥션 닫힘 방지."""
    key = _GEMINI_KEYS[_key_idx] if _GEMINI_KEYS else ""
    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def _rotate_key() -> bool:
    """다음 키로 교체. 교체 성공 시 True, 더 이상 키 없으면 False."""
    global _key_idx
    old = _key_idx + 1
    if _key_idx + 1 < len(_GEMINI_KEYS):
        _key_idx += 1
        print(f"  [KEY] Gemini 키 #{_key_idx + 1}로 교체")
        _tg_alert(f"⚠️ <b>[인제스트] Gemini 키 #{old} 일일 한도 소진</b>\n→ #{_key_idx + 1}번 키로 교체 (잔여 {len(_GEMINI_KEYS) - _key_idx}개)")
        return True
    _tg_alert(f"🚨 <b>[인제스트] Gemini 키 전체 소진</b>\n총 {len(_GEMINI_KEYS)}개 모두 일일 한도 초과 — 인제스트 중단됨")
    return False


def _reset_key_idx():
    """인제스트 세션 시작 시 키 인덱스 초기화."""
    global _key_idx
    _key_idx = 0


def _tg_alert(text: str) -> None:
    """API 에러·키 소진 등을 텔레그램으로 즉시 발송. 실패해도 인제스트 중단 없음."""
    import urllib.request, urllib.parse as _up
    env_path = Path(__file__).parent.parent.parent / ".env"
    ev: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                ev[k.strip()] = v.strip()
    token = os.environ.get("BOT_TOKEN") or ev.get("BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID") or ev.get("CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _up.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

_PROMPT = """다음 텍스트를 주식 시장 정보 '원자' 단위로 분해하라.

원자 정의: 하나의 명확한 주제(자산/이벤트)에 대한 최소 의미 단위. 3~7문장.
핵심 규칙: 원문을 요약하지 마라. 원문의 해당 부분을 그대로 담아라.

각 원자에 아래 메타데이터를 부여하라:
- sector: 반도체/조선/로봇/방산/바이오/전력/2차전지/자동차/통신/AI소프트웨어/우주/소비내수/기타
- asset: 종목명 또는 섹터명 또는 지표명
- asset_level: stock/sector/market/macro/theme
- signal: bullish/bearish/neutral/risk/catalyst/conflict/data
- event_type: earnings/policy/supply/demand/consensus/momentum/macro/news/report/event
- magnitude: major/minor
- content_type: fact/data/analysis/opinion
- content: (필수) 이 원자의 본문. 원문 해당 부분을 3~7문장 그대로 담아라. 요약·생략 금지. 비어 있으면 안 된다.
- validity_type: permanent/date/event
- validity_until: 만료일 YYYY-MM-DD 형식 또는 null

JSON 배열만 반환하라. 다른 텍스트 없이.

텍스트:
{text}"""


def _sanitize(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def atomize_text(
    text: str,
    source_type: str,
    source_name: str,
    source_trust: str,
    raw_file: str,
    date: str,
    layer: str = "L5",
) -> list[dict]:
    text = _sanitize(text)
    raw_atoms = None
    for _attempt in range(6):
        try:
            response = _get_client().models.generate_content(
                model=_GEMINI_MODEL,
                contents=_PROMPT.format(text=text),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            raw_atoms = json.loads(response.text)
            break
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Gemini returned invalid JSON: {e}\nResponse: {getattr(response, 'text', 'no response')[:200]}")
        except Exception as e:
            _m = str(e)
            if any(c in _m for c in ("429", "RESOURCE_EXHAUSTED")):
                if "PerDay" in _m or "limit: 500" in _m:
                    # 일일 한도 초과 → 다른 프로젝트 키로 rotation
                    if _rotate_key():
                        continue
                else:
                    # 분당 한도(15건/분) → 62초 대기 (같은 프로젝트 키 교체 무의미)
                    time.sleep(62)
                    continue
            if _attempt < 5 and any(c in _m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((_attempt + 1) * 5)
                continue
            _tg_alert(f"❌ <b>[인제스트] Gemini API 에러</b>\n소스: {source_name}\n에러: {_m[:200]}")
            raise RuntimeError(f"Gemini API call failed: {e}")

    atoms = []
    for i, a in enumerate(raw_atoms):
        content = a.get("content", "")
        if not content:
            continue
        atoms.append(
            {
                "id": _make_id(date, source_name, i),
                "date": date,
                "source_type": source_type,
                "source_name": source_name,
                "source_trust": source_trust,
                "raw_file": raw_file,
                "layer": layer,
                "sector": a.get("sector", "기타"),
                "asset": a.get("asset", ""),
                "asset_level": a.get("asset_level", "sector"),
                "signal": a.get("signal", "neutral"),
                "event_type": a.get("event_type", "news"),
                "magnitude": a.get("magnitude", "minor"),
                "content_type": a.get("content_type", "fact"),
                "strength_score": _calc_strength(a, source_trust),
                "validity_type": a.get("validity_type", "permanent"),
                "validity_until": a.get("validity_until"),
                "is_active": 1,
                "content": content,
                "relations": [],
            }
        )
    return atoms


_YT_PROMPT = """아래 유튜브 발언 목록을 JSON 배열로 분류하라. content는 원문 그대로.

각 항목 필드:
- speaker: 화자 이름 (원문 그대로)
- timestamp: mm:ss 형식
- sector: 반도체/조선/로봇/방산/바이오/전력/2차전지/자동차/통신/AI소프트웨어/우주/소비내수/시장/기타
- asset: 언급 종목명 또는 섹터명 또는 지표명
- asset_level: stock/sector/market/macro
- signal: bullish/bearish/neutral/risk/catalyst/data
- stance: bullish/bearish/neutral (화자의 입장)
- content_type: fact/opinion/data
- content: 발언 원문 그대로 (요약·각색 금지)

JSON 배열만 반환. 다른 텍스트 없이.

발언 목록:
{highlights}"""


def _ts_to_seconds(ts: str) -> int:
    parts = ts.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        pass
    return 0


def atomize_youtube_highlights(
    highlights: list[str],
    video_url: str,
    source_name: str,
    source_trust: str,
    raw_file: str,
    date: str,
) -> list[dict]:
    """유튜브 ## 주요 발언 리스트 → 원자 (speaker·timestamp·deeplink 포함)."""
    if not highlights:
        return []

    highlights_text = "\n".join(f"- {h}" for h in highlights)
    raw_atoms = None
    for attempt in range(6):
        try:
            response = _get_client().models.generate_content(
                model=_GEMINI_MODEL,
                contents=_YT_PROMPT.format(highlights=highlights_text),
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            raw_atoms = json.loads(response.text)
            break
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Gemini returned invalid JSON: {e}")
        except Exception as e:
            _m = str(e)
            if any(c in _m for c in ("429", "RESOURCE_EXHAUSTED")):
                if _rotate_key():
                    continue
            if attempt < 5 and any(c in _m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            _tg_alert(f"❌ <b>[인제스트] Gemini API 에러 (YT)</b>\n소스: {source_name}\n에러: {_m[:200]}")
            raise RuntimeError(f"Gemini API call failed: {e}")

    atoms = []
    for i, a in enumerate(raw_atoms):
        content = a.get("content", "")
        if not content:
            continue
        ts = a.get("timestamp", "")
        secs = _ts_to_seconds(ts)
        deeplink = f"{video_url}&t={secs}" if secs > 0 else video_url
        atoms.append({
            "id": _make_id(date, source_name, f"yt_{i}"),
            "date": date,
            "source_type": "youtube",
            "source_name": source_name,
            "source_trust": source_trust,
            "raw_file": raw_file,
            "layer": "L5",
            "sector": a.get("sector", "기타"),
            "asset": a.get("asset", ""),
            "asset_level": a.get("asset_level", "market"),
            "signal": a.get("signal", "neutral"),
            "event_type": "news",
            "magnitude": "minor",
            "content_type": a.get("content_type", "opinion"),
            "strength_score": _calc_strength(a, source_trust),
            "validity_type": "date",
            "validity_until": None,
            "is_active": 1,
            "content": content,
            "relations": [],
            "speaker": a.get("speaker", ""),
            "yt_timestamp": ts,
            "deeplink": deeplink,
            "stance_key": a.get("stance", "neutral"),
        })
    return atoms


def _make_id(date: str, source_name: str, index) -> str:
    raw = f"{date}_{source_name}_{index}"
    return "atom_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def parse_yt_highlights(highlights: list[str]) -> list[dict]:
    """[mm:ss] 화자: 발언 형식에서 구조 파싱."""
    parsed = []
    pat = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:]+):\s*(.+)$")
    for h in highlights:
        m = pat.match(h.strip())
        if m:
            parsed.append({"timestamp": m.group(1), "speaker": m.group(2).strip(), "text": m.group(3).strip()})
        else:
            parsed.append({"timestamp": "", "speaker": "", "text": h.strip()})
    return parsed


def _calc_strength(atom: dict, source_trust: str) -> int:
    score = 1
    score += {"A": 2, "B": 1}.get(source_trust, 0)
    if atom.get("magnitude") == "major":
        score += 1
    return min(score, 5)
