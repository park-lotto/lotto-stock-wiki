"""VMake(vmake.ai) 자막/화면텍스트 제거 어댑터 — 공식 SDK(vmake_sdk) 래퍼.

외부에는 remove_subtitles(video_path, api_key, out_path) 하나만 노출한다.
실제 서명(SDK-HMAC-SHA256)·OSS 업로드·비동기 job 폴링은 번들된 `vmake_sdk`
(공식 Vmake AI SDK를 vendoring, 내부 import만 상대경로로 변환)가 전부 처리한다.

키는 대시보드에 **'app_key:secret'**(= MT_AK:MT_SK) 형식으로 저장한다.
비디오 태스크명은 `videoscreenclear`(화면 텍스트/워터마크 제거, 비동기 spawn).
문서: vmake.ai/de/developers → Dok. / base=https://wapi-skill.vmake.ai
"""
import json
import os
import time
import urllib.request
from pathlib import Path

# 비디오 화면정리(하드섭·워터마크 제거) 프리셋명. 서버 config.INVOKE의 키와 일치해야 함.
_VIDEO_TASK = "videoscreenclear"
# 결과를 URL로 받는다(우리는 그 URL을 다운로드).
_DEFAULT_PARAMS = {"parameter": {"rsp_media_type": "url"}}

# ── 새 VMake API(2026-09-16) ────────────────────────────────────────────────
# 사장님 계정을 새 API로 전환하니 프리셋이 6개로 늘었다(SKM0001~0006). 우리가 쓰는 둘:
#     SKM0003 = Smart      (视频智能消除普通档位)  — 초당 2크레딧
#     SKM0005 = Smart Pro  (视频智能消除Pro档位)  — 초당 4크레딧, Pro 멤버십 전용
# ★왜 필요한가(2026-09-16 고객 이윤정 제보): 큰 흰박스 자막을 옛 경로(legacy
#   videoscreenclear)가 못 메워 **다른 장면 픽셀이 띠로 끌려왔다**. 같은 클립을
#   Smart Pro로 돌리니 깨끗하게 복원됐다(실측). 재시도로는 절대 안 고쳐진다 —
#   같은 입력에 같은 결과가 나온다(사장님 키로 재시도해 확인).
# ★버전 문자열이 갈림길이다. v1.x로 config을 받으면 옛 4개만 오고, v2.0.0으로
#   받아야 SKM*이 열린다. legacy 키로 v2를 부르면 [60007]이 떨어진다 — 그게
#   "이 키가 아직 안 옮겼다"는 **유일하게 확실한 판별법**이다(is_legacy_key).
NEW_API_VERSION = "v2.0.0"
TASK_SMART = "SKM0003"
TASK_SMART_PRO = "SKM0005"
# 등급 이름(화면·DB가 쓰는 값)의 정의처. 여기 한 곳에서만 정한다(0순위-B).
TIER_BASIC = "basic"
TIER_PRO = "pro"


def is_preprocess_fail(err) -> bool:
    """VMake가 **영상 파일을 준비하다** 멈췄나 — `[30029] 前置开放平台事件处理失败`.

    실측(2026-09-17, 영상 1556910737b6): 우리 조립본(mix_raw, concat -c copy)을 보내면
    사장님 키·고객 키 모두 이 오류로 실패했는데, 같은 영상을 **한 번 다시 인코딩**하거나
    조각내 보내면 성공했다. 실패 요청은 크레딧이 안 빠졌다(대시보드 잔액 대조).
    ★좁게 본다 — 코드 30029만. 다른 실패까지 재인코딩으로 돌리면 헛돈이 든다.
    """
    return "30029" in str(err or "")


def is_legacy_key(err) -> bool:
    """이 오류가 **'아직 legacy API에 묶인 키'**인가.

    실측 원문: "[60007] Your current Access Key only supports the legacy Skill.
                Switch to the new API in the dashboard and try again."
    ★is_no_credit과 같은 원칙으로 좁게 본다 — 넓게 잡으면 네트워크 오류까지
      "옛날 키"로 오해해 새 API를 쓸 수 있는 사람까지 옛 경로로 떨어뜨린다.
    """
    t = str(err or "")
    return "60007" in t or "legacy skill" in t.lower()


# ── "이 키는 크레딧이 떨어졌다"의 판정 (2026-08-29) ───────────────────────────
# ★판정은 여기 한 곳에서만 한다(0순위-B). 쓰는 곳이 둘이다:
#     · mix_pipeline — 다음 키로 넘길지 결정
#     · app.clean_failure_kind — 고객에게 보여줄 문구 결정
#   두 곳이 각자 문자열을 검사하면 "화면은 소진이라는데 다음 키로는 안 넘어간다"처럼
#   서로 어긋난다. VMake 에러의 뜻을 아는 건 이 파일이므로 여기가 제자리다.
#   실측 원문: "[60002] You don't have enough credits for this API. Purchase a subscription..."
def is_no_credit(err) -> bool:
    """이 오류가 **그 키의 잔액 소진**인가. 다른 실패(네트워크·처리불가)는 False.

    ★좁게 본다 — 넓게 잡으면 멀쩡한 키를 죽은 것으로 보고 건너뛰다가 결국
      전부 못 쓰게 된다(2026-08 vmake_paused 사고의 계보).
    """
    t = str(err or "")
    return "60002" in t or "enough credits" in t.lower()


def _split_key(api_key):
    """대시보드 키 'app_key:secret' → (ak, sk). 콜론 없으면 둘 다 키 전체."""
    if ":" in api_key:
        ak, sk = api_key.split(":", 1)
        return ak.strip(), sk.strip()
    return api_key.strip(), api_key.strip()


_DL_TRIES = 4


def _download(url, dest):
    """결과 영상 다운로드 → dest 경로. **끊기면 다시 받는다**(2026-09-27).

    ★왜: 업체는 처리가 끝나면 이미 크레딧을 가져갔다. 여기서 한 번 끊기면(실측 WinError 10053)
      job이 failed가 되고, 고객이 다시 누르면 **같은 영상에 두 번 과금**된다.
    ★반쪽 파일을 결과로 두지 않는다 — .part에 받고 다 받은 뒤에만 이름을 바꾼다.
    """
    dest = Path(dest)
    tmp = dest.with_name(dest.name + ".part")
    last = None
    for i in range(_DL_TRIES):
        try:
            urllib.request.urlretrieve(url, str(tmp))
            if not tmp.exists() or tmp.stat().st_size <= 1024:
                raise RuntimeError("받은 결과 파일이 비었습니다")
            os.replace(str(tmp), str(dest))
            return str(dest)
        except Exception as e:                    # noqa: BLE001 — 몇 번 더 받아 본다
            last = e
            print("[vmake] 결과 받기 실패 %d/%d: %r" % (i + 1, _DL_TRIES, e), flush=True)
            if i < _DL_TRIES - 1:
                time.sleep(min(2 ** i, 8))
    try:
        tmp.unlink()
    except OSError:
        pass
    raise last


# ── 이어받기 장부 (2026-09-27 사장님 "고쳐야지") ─────────────────────────────
# 업체는 제출 직후 크레딧을 가져간다. 그 뒤 결과 받기가 끊기거나 워커가 재시작되면(09-17 수동 재시작이
# 청소 1건을 죽인 실사고) 결과는 업체에 있는데 우리 쪽만 실패다. 다시 누르면 새로 보내 **또 과금**된다.
# → 제출하자마자 작업 번호를 결과 폴더 옆 장부에 적어 두고, 같은 작업(resume_key)이 다시 오면
#   **업로드·과금 없이** 그 번호로 결과만 받아 온다(poll_task_status — 실측 2026-09-26 재과금 0으로 복구).
# ★같은 작업인지는 파일 내용으로 못 가린다 — 다시 조립하면 바이트가 달라진다(실측 sha1 c9c27e→0383b2).
#   그래서 호출부가 "무엇을 지우는 작업인가"(편성 서명·등급·고른 장면·증분 조각의 원본 구간)를 이름표로 준다.
# ★이어받은 결과는 길이가 보낸 영상과 맞는지 한 번 더 본다 — 어긋나면 버리고 새로 한다.
_PENDING_FILE = ".vmake_pending.json"
_PENDING_TTL = 24 * 3600


def _pending_path(out_path):
    return Path(out_path).parent / _PENDING_FILE


def _pending_all(out_path):
    try:
        d = json.loads(_pending_path(out_path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:                             # noqa: BLE001 — 장부가 없거나 깨졌으면 빈 장부
        return {}


def _pending_write(out_path, d):
    try:
        p = _pending_path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(p))
    except Exception as e:                        # noqa: BLE001 — 장부 실패가 청소를 막으면 안 된다
        print("[vmake] 이어받기 장부 쓰기 실패(무해): %r" % (e,), flush=True)


def _pending_get(out_path, key):
    ent = _pending_all(out_path).get(key) if key else None
    if not ent or time.time() - float(ent.get("ts") or 0) > _PENDING_TTL:
        return None
    return ent


def _pending_put(out_path, key, task_id, seconds, consumed=False):
    """작업 번호를 적는다. consumed=True면 **번호 없이** '돈 나감' 표식만 남긴다(과금 직후·제출 전).
    번호가 오면 같은 키를 덮어쓴다."""
    if not key or not (task_id or consumed):
        return
    d = {k: v for k, v in _pending_all(out_path).items()
         if time.time() - float((v or {}).get("ts") or 0) <= _PENDING_TTL}
    d[key] = {"task_id": (str(task_id) if task_id else None), "ts": time.time(), "seconds": seconds,
              "consumed": True}
    _pending_write(out_path, d)


def _orphan_charge_alert(key, ent):
    """번호 없는 과금 표식이 남은 채 다시 왔다 = 지난 시도가 과금 직후·번호 받기 전에 죽었다(업체 SDK 틈).
    막을 수는 없고 **모르고 넘어가지 않게** 관리자에게 올린다(2026-09-27 사장님). 경보 실패는 무해."""
    try:
        from shopping_shorts import ops_alert
        ops_alert.raise_alert(
            "vmake_orphan_charge", "자막제거 과금됐는데 결과 없음(이전 시도 중단) — 업체 사용내역 확인",
            "key=%s ts=%s seconds=%s — 이번 클릭은 새로 보냈다(2번째 과금 가능)" % (key, ent.get("ts"), ent.get("seconds")),
            grade=ops_alert.GRADE_OPS, signature=key)
    except Exception as e:                        # noqa: BLE001
        print("[vmake] 번호 없는 과금 경보 실패(무해): %r" % (e,), flush=True)


def _pending_drop(out_path, key):
    if not key:
        return
    d = _pending_all(out_path)
    if key in d:
        d.pop(key)
        _pending_write(out_path, d)


def _seconds(path):
    """영상 길이(초). 못 재면 None — 이어받기 검사는 그때 건너뛴다(막지 않는다)."""
    try:
        import subprocess
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:                             # noqa: BLE001
        return None


def _fetch_by_task(client, task_id, out_path, want_sec):
    """작업 번호로 결과 주소를 새로 받아 내려받는다(업로드·과금 없음). 길이가 어긋나면 예외."""
    r = client.poll_task_status(task_id)
    urls = (r or {}).get("output_urls") or []
    if not urls:
        raise RuntimeError("이어받을 결과가 없습니다: %s" % ((r or {}).get("error") or r))
    got = _download(urls[0], out_path)
    have = _seconds(got)
    if want_sec and have and abs(have - want_sec) > 0.5:
        raise RuntimeError("이어받은 결과 길이가 다릅니다(%.2f != %.2f초)" % (have, want_sec))
    return got


def _client(ak, sk):
    """SkillClient 생성(지연 import — OSS 의존성은 실제 업로드 시점에만 필요)."""
    from shopping_shorts.vmake_sdk import SkillClient
    return SkillClient(ak=ak, sk=sk)


def _new_api_client(ak, sk):
    """새 API(SKM*)를 쓸 수 있는 client. 못 쓰는 키면 legacy 오류를 그대로 올린다.

    ★fetch_config(version='v2.0.0')이 관문이다 — 이게 통과해야 config.INVOKE에
      SKM0003/SKM0005가 채워진다. legacy 키면 여기서 [60007]이 난다.
    """
    client = _client(ak, sk)
    client.fetch_config(version=NEW_API_VERSION)
    return client


# ── 이 키로 고급을 쓸 수 있나 (2026-09-16) ─────────────────────────────────
# 사장님 제보: 이미 새 API로 옮겨 고급이 **되는** 계정인데도 화면이 늘 "Pro 쓰려면 키를
# 다시 등록하라"고 띄웠다. 화면이 판단 근거 없이 경고를 박아 뒀기 때문이다.
# ★판정은 remove_subtitles와 **같은 관문**(fetch_config v2.0.0)으로 한다 — 다른 방법으로
#   재면 "화면은 된다는데 실제로는 안 된다"가 난다(0순위-B).
# ★config 조회만 한다 — 크레딧이 나가지 않는다(실측: legacy 호출도 Free Usage 0).
_PRO_READY_CACHE = {}          # 키 해시 → (시각, True/False)
_PRO_READY_TTL = 3600


def key_supports_new_api(api_key):
    """True=새 API 키(고급 가능) / False=옛 키 / None=모르겠음(네트워크 등 — 화면은 경고 유지)."""
    import hashlib
    import time
    if not api_key:
        return None
    h = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    hit = _PRO_READY_CACHE.get(h)
    if hit and time.time() - hit[0] < _PRO_READY_TTL:
        return hit[1]
    try:
        ak, sk = _split_key(api_key)
        _new_api_client(ak, sk)
        ok = True
    except Exception as exc:                      # noqa: BLE001 — 판정만 한다
        if not is_legacy_key(exc):
            return None                           # 모르는 실패는 캐시하지 않는다
        ok = False
    _PRO_READY_CACHE[h] = (time.time(), ok)
    return ok


def remove_subtitles(video_path, api_key, out_path, poll_timeout=1200, tier=TIER_BASIC, resume_key=None):
    """video_path의 하드섭/화면텍스트를 VMake로 제거 → out_path에 저장하고 경로 반환.

    흐름(SDK 내부): 로컬영상 OSS 업로드 → /skill/consume.json(크레딧) →
    알고리즘 job 제출 → 비동기 상태 폴링 → 결과 URL. 그 URL을 out_path로 내려받는다.

    tier: 'basic'(기본) | 'pro'(Smart Pro). **경로를 고르는 유일한 자리**다(0순위-B).
      · 새 API 키  → basic=SKM0003, pro=SKM0005
      · legacy 키  → basic이면 옛 videoscreenclear로 **조용히 내려간다**(지금까지와 동일).
                     pro면 못 하므로 무엇이 필요한지 말하고 막는다 — 조용히 기본으로
                     떨어뜨리면 고객은 고급을 골랐는데 기본 결과를 받고 "왜 그대로냐"가 된다
                     (조용한 폴백은 이 저장소가 여러 번 데인 함정이다).

    resume_key: "무엇을 지우는 작업인가" 이름표(호출부가 준다). 주면 제출 직후 작업 번호를 장부에 적고,
      같은 이름표로 다시 오면 업로드·과금 없이 그 결과를 받아 온다(위 이어받기 장부 참조).
      None이면 종전과 같다(다운로드 재시도만 더해졌다).

    api_key 없으면 ValueError. 처리 실패/타임아웃은 상위로 raise.
    poll_timeout은 하위호환용 인자 — 실제 폴링 예산은 SDK가 서버 config +
    MT_AI_POLL_* 환경변수로 관리한다(기본 최대 ~1h).
    """
    if not api_key:
        raise ValueError("AI 자막 제거 API 키가 등록되지 않았습니다")
    ak, sk = _split_key(api_key)
    want_pro = (tier == TIER_PRO)
    try:
        client = _new_api_client(ak, sk)
        task, params = (TASK_SMART_PRO, None) if want_pro else (TASK_SMART, _DEFAULT_PARAMS)
    except Exception as exc:                      # noqa: BLE001 — legacy인지 진짜 오류인지 가른다
        # AttributeError = 이 SDK에 fetch_config이 없다(번들 SDK를 되돌렸거나 옛 버전).
        # ★그때도 **기본 자막제거는 살아 있어야 한다** — 새 기능 때문에 되던 게 죽으면
        #   고객 전체가 멈춘다. 고급만 막고 기본은 옛 경로로 간다.
        if not (is_legacy_key(exc) or isinstance(exc, AttributeError)):
            raise
        if want_pro:
            raise RuntimeError(
                "고급 자막제거(Smart Pro)는 VMake 새 API 키가 필요합니다. "
                "VMake 대시보드에서 'Switch to New API'로 전환한 뒤 다시 시도해 주세요."
            ) from exc
        client, task, params = _client(ak, sk), _VIDEO_TASK, _DEFAULT_PARAMS
    key = ("%s|%s|%s" % (resume_key, tier, task)) if resume_key else None
    want_sec = _seconds(video_path) if key else None
    ent = _pending_get(out_path, key)
    if ent and not ent.get("task_id"):
        # 돈은 나갔는데 번호가 없다 — 이어받을 길이 없으니 새로 보내되, 관리자에게 알린다
        print("[vmake] 지난 시도가 과금 직후 끊겼다(번호 없음) → 경보 후 새로 맡긴다", flush=True)
        _orphan_charge_alert(key, ent)
        _pending_drop(out_path, key)
        ent = None
    if ent:
        print("[vmake] 이미 맡긴 작업이 있다 — 업로드·과금 없이 이어받는다: task_id=%s" % ent["task_id"], flush=True)
        try:
            got = _fetch_by_task(client, ent["task_id"], out_path, want_sec)
            _pending_drop(out_path, key)
            return got
        except Exception as e:                    # noqa: BLE001 — 못 이으면 종전처럼 새로 맡긴다
            print("[vmake] 이어받기 실패 → 새로 맡긴다: %r" % (e,), flush=True)
            _pending_drop(out_path, key)
    if key:
        # ★과금(consume) 직후·제출 전에 '돈 나감' 표식을 먼저 적는다 — 그 사이에 죽으면 다음 클릭이 안다
        _orig_consume = client._consume_permission

        def _consume_marked(url, task_name):
            r = _orig_consume(url, task_name)
            _pending_put(out_path, key, None, want_sec, consumed=True)
            return r
        client._consume_permission = _consume_marked
        result = client.run_task(task_name=task, image_path=video_path, params=params,
                                 on_async_submitted=lambda tid: _pending_put(out_path, key, tid, want_sec))
    else:
        result = client.run_task(task_name=task, image_path=video_path, params=params)
    # 성공: dict에 output_urls. 실패: {"error":..., "skill_status":"failed", "detail":...}
    if isinstance(result, dict) and result.get("error"):
        detail = result.get("detail") or result.get("error")
        if result.get("error") == "poll_aborted":
            # ★진행 조회가 끊긴 것이지 업체가 실패한 게 아니다(SDK _poll_aborted_payload). 작업은 업체에서 계속
            #   돌고 크레딧은 이미 나갔다 — 장부를 **남겨** 다시 누르면 작업 번호로 이어받는다(2026-09-27).
            raise RuntimeError("AI 자막 제거 진행 조회가 중단되었습니다 — 다시 누르면 추가 비용 없이 "
                               "이어받습니다 (task_id=%s): %s" % (result.get("task_id"), detail))
        _pending_drop(out_path, key)              # 업체가 실패로 끝냈다 — 이어받을 결과가 없다
        raise RuntimeError(f"AI 자막 제거 실패: {detail}")
    urls = (result or {}).get("output_urls") or []
    if not urls:
        _pending_drop(out_path, key)
        raise RuntimeError(f"AI 자막 제거 결과가 비었습니다: {result}")
    # ★결과를 받자마자, **내려받기 전에** 작업 번호를 장부에 쓴다(2026-09-27 실측 사고).
    #   업체가 동기 시간 안에 끝내면(짧은 장면 = 골라 지우기가 딱 그 경우) SDK는 on_async_submitted를
    #   **안 부르고** 결과를 바로 돌려준다(api.py: status==9일 때만 콜백). 그러면 장부가 비어 내려받기가
    #   끊긴 뒤 다시 누르면 새로 보내 **재과금**됐다(03:40·03:54 추적: put 0회, B2 MISS). 비동기면 콜백이
    #   이미 썼으니 같은 번호를 다시 쓰는 것뿐(무해).
    if key and (result or {}).get("task_id"):
        _pending_put(out_path, key, result["task_id"], want_sec)
    try:
        got = _download(urls[0], out_path)
    except Exception as e:                        # noqa: BLE001
        # 주소가 만료됐을 수 있다 — 작업 번호로 새 주소를 받아 한 번 더(과금 없음)
        tid = (result or {}).get("task_id")
        try:
            if not tid:
                raise
            got = _fetch_by_task(client, tid, out_path, None)
        except Exception:                         # noqa: BLE001
            # 장부는 남긴다 — 고객이 다시 누르면 과금 없이 이어받는다
            raise RuntimeError("AI 자막 제거 결과 받기가 중단되었습니다 — 다시 누르면 추가 비용 없이 "
                               "이어받습니다 (task_id=%s): %s" % (tid, e)) from e
    _pending_drop(out_path, key)
    return got
