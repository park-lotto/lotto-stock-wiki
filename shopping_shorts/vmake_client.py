"""VMake(vmake.ai) 자막/화면텍스트 제거 어댑터 — 공식 SDK(vmake_sdk) 래퍼.

외부에는 remove_subtitles(video_path, api_key, out_path) 하나만 노출한다.
실제 서명(SDK-HMAC-SHA256)·OSS 업로드·비동기 job 폴링은 번들된 `vmake_sdk`
(공식 Vmake AI SDK를 vendoring, 내부 import만 상대경로로 변환)가 전부 처리한다.

키는 대시보드에 **'app_key:secret'**(= MT_AK:MT_SK) 형식으로 저장한다.
비디오 태스크명은 `videoscreenclear`(화면 텍스트/워터마크 제거, 비동기 spawn).
문서: vmake.ai/de/developers → Dok. / base=https://wapi-skill.vmake.ai
"""
import urllib.request

# 비디오 화면정리(하드섭·워터마크 제거) 프리셋명. 서버 config.INVOKE의 키와 일치해야 함.
_VIDEO_TASK = "videoscreenclear"
# 결과를 URL로 받는다(우리는 그 URL을 다운로드).
_DEFAULT_PARAMS = {"parameter": {"rsp_media_type": "url"}}


def _split_key(api_key):
    """대시보드 키 'app_key:secret' → (ak, sk). 콜론 없으면 둘 다 키 전체."""
    if ":" in api_key:
        ak, sk = api_key.split(":", 1)
        return ak.strip(), sk.strip()
    return api_key.strip(), api_key.strip()


def _download(url, dest):
    """결과 영상 다운로드 → dest 경로."""
    urllib.request.urlretrieve(url, dest)
    return str(dest)


def _client(ak, sk):
    """SkillClient 생성(지연 import — OSS 의존성은 실제 업로드 시점에만 필요)."""
    from shopping_shorts.vmake_sdk import SkillClient
    return SkillClient(ak=ak, sk=sk)


def remove_subtitles(video_path, api_key, out_path, poll_timeout=1200):
    """video_path의 하드섭/화면텍스트를 VMake로 제거 → out_path에 저장하고 경로 반환.

    흐름(SDK 내부): 로컬영상 OSS 업로드 → /skill/consume.json(크레딧) →
    알고리즘 job 제출 → 비동기 상태 폴링 → 결과 URL. 그 URL을 out_path로 내려받는다.

    api_key 없으면 ValueError. 처리 실패/타임아웃은 상위로 raise.
    poll_timeout은 하위호환용 인자 — 실제 폴링 예산은 SDK가 서버 config +
    MT_AI_POLL_* 환경변수로 관리한다(기본 최대 ~1h).
    """
    if not api_key:
        raise ValueError("VMake API 키가 등록되지 않았습니다")
    ak, sk = _split_key(api_key)
    client = _client(ak, sk)
    result = client.run_task(
        task_name=_VIDEO_TASK,
        image_path=video_path,
        params=_DEFAULT_PARAMS,
    )
    # 성공: dict에 output_urls. 실패: {"error":..., "skill_status":"failed", "detail":...}
    if isinstance(result, dict) and result.get("error"):
        detail = result.get("detail") or result.get("error")
        raise RuntimeError(f"VMake 자막제거 실패: {detail}")
    urls = (result or {}).get("output_urls") or []
    if not urls:
        raise RuntimeError(f"VMake 결과 URL이 비었습니다: {result}")
    return _download(urls[0], out_path)
