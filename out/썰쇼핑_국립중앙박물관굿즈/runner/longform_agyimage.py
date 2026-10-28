# -*- coding: utf-8 -*-
"""인물형 롱폼 그림 — 제작표 `media[id].generate` 를 학생 자기 agy 그림 도구(generate_image · Nano Banana 2)로 그린다 (2026-10-09).

■ 왜 (사장님 10-09 «모션 그래픽 각각은 하나도 겹치지 않게» · 설계 docs/2026-10-09_롱폼-그래픽-다양성/설계.md 0·1절)
    달빛부부 그래픽 다양성의 출처는 «장면마다 새로 그린 그림» 인데 학생에게는 그릴 도구가 없었다(안내문이 FlowKit·유료 Replicate 만
    적었다). 카드뉴스가 이미 쓰는 agy 그림 부품(`cardnews_agyimage.generate` — 지문 캐시·이 PC 공용 간격 줄·한도 거부 감지)을
    그대로 쓴다. 여기에는 일감 검사·동시 실행·결과 모으기만 있다.

■ 실행기 경계: 무엇을 그릴지(지시문·비율·참조)·모델·간격 표·동시 수는 **서버가 준다**(`prepare_agy_images` 일감 · 설계 3-2).
■ 경로 돌기(2026-10-17 사장님 «agy 한도로 못 그린 그림은 볼케이노킷 로테이션을 돌리면 된다»): 그림 하나는 서버가 준 경로 순서
    (routes · vox imgroute.ALL — flow → codex → gemini 웹 → aistudio → agy → antigravity)를 **한 바퀴만** 돈다. 경로 코드는 볼케이노킷 팩
    (route_pack · vox 원본 imgroute·flowmake·vkclient 사본 · SOURCE_COMMIT 도장)의 것을 그대로 쓰고, agy 경로만 이 실행기의 agy 그림 부품
    (cardnews_agyimage.generate — 지문 캐시·이 PC 공용 agy 그림 줄·거부 판정)으로 바꿔 끼운다. 플로우 간격은 vkclient 공용 줄(5초×5건→20초).
■ 거부: 그 경로만 끊는다 — 다른 경로는 계속. agy 거부의 종류는 피사체 판독과 같은 한 규칙(subject_agy_run.refusal_continues)으로 가른다:
    한도·속도·로그인이면 agy 경로만 이 실행에서 건너뛰고 조용히 다음 경로로, 그 밖(도구 거부 등 이 PC 설정을 고칠 것)도 agy 경로는 끊고
    결과 refused 에 남겨 서버가 알린다. 자동 재시도 없음(6-2). 모든 경로가 실패한 그림만 errors(all_routes_failed · 경로마다 까닭).
■ 6-00: 참조 그림 sha256 은 파일마다 한 번(같은 참조를 여러 일감이 써도) · 결과 그림은 한 번 읽어 sha256·크기·가로세로를 같이 잰다 ·
    잠금 대기는 상한이 있다(cardnews_agyimage.LOCK_WAIT_TURNS) · 다시 보내기 없음.
■ 실행 전체가 막히는 실패는 한 번만 기다린다(10-09 검토 MAJOR): 줄 잠금이 멈췄으면(AgyGateStuck) 남은 그림은 보내지 않는다 —
    그림마다 600초씩 다시 기다리면 남은 수 × 10분이다. 거부 아닌 같은 실패(예: AGY_TIMEOUT 900초)가 잇따라 REPEAT_STOP 번이면
    남은 그림도 같은 까닭으로 실패할 공산이 커서 보내지 않는다(전역 규칙 6-00 «쓸모없는 반복»). 둘 다 사람이 확인하고 다시 낸다.
■ 파일 이름은 서버가 준 name(=id 앞부분 + id 의 sha256 앞 8자)이다 — id 는 대소문자만 다를 수 있어('BG'·'bg') 대소문자를 가리지
    않는 파일 시스템(맥 APFS 기본·윈도우 NTFS)에서 같은 파일이 된다. id·name 은 casefold 로도 겹치면 반려한다.
"""

import io
import os
import re
import shutil
import sys
import threading

VERSION = 1
#: agy generate_image 가 받는 비율(설계 3-1 · agy 실행파일 jsonschema_description 실측) — 서버 검사와 같은 7개.
ASPECTS = ("16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "1:1")
#: agy ImagePaths 상한(설계 3-1).
MAX_REFS = 3
#: 간격 표에 있어야 하는 칸 — `cardnews_agyimage.take_turn` 이 읽는 칸 그대로(없으면 보내기 전에 멈춘다).
PACING_KEYS = ("gap_s", "burst", "burst_gap_s", "idle_reset_s", "poll_s", "line")
#: 일감 id 는 파일 이름이 된다 — 경로 문자를 막는다(out_dir 밖으로 쓰지 않게).
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}")
#: 참조로 보낼 수 있는 그림 확장자 — agy generate_image 의 ImagePaths 는 그림만 받는다(영상을 보내면 agy 가 거부하거나 엉뚱하게
#: 읽는다 · 서버 static_check 와 같은 자). 보내기 전에 막는다.
REF_EXTS = (".png", ".jpg", ".jpeg", ".webp")
#: 거부 아닌 같은 갈래(code)의 실패가 이만큼 잇따르면 남은 그림을 보내지 않는다. 2 인 까닭: 한 번은 그 그림만의 사정일 수 있지만
#: (지시문이 걸림 등) 같은 갈래가 연달아 두 번이면 대개 실행 전체의 사정(agy 응답 없음·시간 초과)이다. 시간 초과는 한 장 900초라
#: 120장을 다 겪으면 30시간이다 — 세 번째를 기다릴 근거가 없다(6-00 «쓸모없는 반복 금지»). 그림이 하나 나오면 다시 0 부터 센다.
REPEAT_STOP = 2
#: PIL 형식 → 확장자(agy 가 그린 그림의 실제 바이트로 고른다 — 캐시 사본은 이름이 .png 라도 안은 jpg·webp 일 수 있다).
_EXT = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


#: 그림 경로 이름 — vox imgroute.ALL 과 같은 이름(서버 agy_images.ROUTES 가 순서를 준다). agy 는 이 실행기의 agy 그림 부품으로 돈다.
ROUTE_NAMES = ("flow", "codex", "gemini", "aistudio", "agy", "antigravity")
#: 볼케이노킷(크롬 확장 + 연결 프로그램)을 쓰는 경로 — vox flowmake.VK_ROUTES 와 같다(연결이 없으면 이 경로들만 뺀다).
VK_ROUTES = ("flow", "gemini", "aistudio")


class RouteSkip(RuntimeError):
    """그 경로를 이 실행에서 끊었다(거부·줄 멈춤·잇따른 실패) — 다음 경로로."""


class RouteFailed(RuntimeError):
    """그 경로가 이 그림 하나를 못 만들었다 — 다음 경로로(같은 경로에 다시 보내지 않는다)."""


def _routes(item, timeout_s):
    """경로 돌기 부품 → (만드는 함수 {이름: f(job, out_dir) → 그림 경로}, 쓸 수 있나 f(이름, job), 경로 실패 예외 묶음).

    route_pack(볼케이노킷 팩 폴더 · vox 원본 imgroute·flowmake·vkclient 사본)이 없으면 agy 경로만 있다(옛 일감 그대로).
    거부(imgroute.RouteRefused)는 그 경로만 이 실행에서 끈다(imgroute._turn_off · 자동 재시도 없음). 플로우 간격은 vkclient 공용 줄."""
    pack, wanted = item.get("route_pack"), [r for r in item.get("routes") or ("agy",) if r != "agy"]
    if not pack or not wanted:
        return {}, (lambda name, job: False), (), (lambda jobs, out_dir: None)
    if not os.path.isfile(os.path.join(pack, "vkclient.py")):
        # ★그림 경로 팩(volcanokit_flow)이 이 작업 폴더에 아직 안 풀렸다(2026-10-17 신고 · 그 팩을 받기 전 assets 로 만든 작업 폴더) —
        #   `import vkclient` 로 죽어 «실행 환경 오류» 로 멈추지 않고 위 약속대로 agy 경로만 쓴다(다음 assets 가 팩을 푼다).
        print(f"그림 경로 팩이 없어({pack}) agy 경로로만 그립니다 — assets 단계를 다시 부르면 플로우·코덱스 경로도 쓸 수 있습니다",
              file=sys.stderr, flush=True)
        return {}, (lambda name, job: False), (), (lambda jobs, out_dir: None)
    if pack not in sys.path:
        sys.path.insert(0, pack)
    import vkclient, flowmake, imgroute                            # noqa: E401,PLC0415 — 팩 사본(SOURCE_COMMIT 도장)
    vkclient.EXTENSION_DIR = os.path.join(pack, "volcanokit", "extension")
    if any(r in VK_ROUTES for r in wanted):
        try:
            vkclient.start_agent(pack)
            vkclient.ensure_available()
        except vkclient.FlowBlocked:
            wanted = [r for r in wanted if r != "flow"]           # 플로우 거부 멈춤 중 — 플로우만 건너뛴다
        except (vkclient.FlowUnavailable, OSError) as error:      # 볼케이노킷 연결 없음 — 그 경로들만 뺀다
            print(f"볼케이노킷 연결 없음 — {'·'.join(r for r in wanted if r in VK_ROUTES)} 경로를 뺀다: {str(error).splitlines()[0]}",
                  file=sys.stderr, flush=True)
            wanted = [r for r in wanted if r not in VK_ROUTES]

    def req_of(job):
        return {"key": job["name"], "prompt": job["prompt"], "aspect": job["aspect"], "refs": [{"path": r} for r in job["refs"]]}

    pre = {}     # 묶음으로 미리 받은 플로우 결과 {그림 이름: flowmake 답 줄} — batch() 가 채우고 flow() 가 꺼낸다(한 그림에 한 번)

    def send(reqs, out_dir):
        """플로우 요청 → flowmake.run 한 길(2026-10-21 사장님 «플로우 에이전트로 10개씩 한 번에» — 묶음 크기·간격 줄은 flowmake 가 정한다).
        거부로 멈추면 그 요청들의 답이 없거나 refused 다 → 받은 답만 pre 에 남기고, 멈춤은 RouteSkip 으로 알린다."""
        results, stopped, _failed = flowmake.run(reqs, "flow_images", out_dir, ("flow",))
        pre.update(results)
        return stopped

    def batch(jobs, out_dir):
        """플로우가 첫 경로인 그림을 한 번에 보낸다(그림마다 따로 보내지 않는다). 화면 지시문이 같은 그림은 한 묶음에서 가를 수
        없어(flowmake.run 이 보내기 전에 멈춤) 묶음에 하나만 넣고, 나머지는 자기 차례에 flow() 가 따로 보낸다."""
        if "flow" not in makers or not jobs:
            return
        seen, reqs = set(), []
        for job in jobs:
            sp = vkclient.screen_prompt(job["prompt"])
            if sp not in seen and imgroute.usable("flow", req_of(job)):
                seen.add(sp)
                reqs.append(req_of(job))
        if reqs:
            stop["why"] = send(reqs, out_dir) or stop.get("why")

    stop = {}

    def flow(job, out_dir):
        got = pre.pop(job["name"], None)
        if got is None and not stop.get("why"):
            stop["why"] = send([req_of(job)], out_dir) or None
            got = pre.pop(job["name"], None)
        if got is None or got.get("status") == "refused":
            raise RouteSkip(f"플로우 거부 — 이 경로만 끊음: {str((got or {}).get('reason') or stop.get('why'))[:160]}")
        if got.get("status") != "done":
            raise vkclient.FlowFailed(f"플로우: {got.get('reason')}")
        return got["path"]

    def wrap(name, make):
        def run(job, out_dir):
            try:
                return make(job, out_dir) if name == "flow" else make(req_of(job), out_dir)
            except imgroute.RouteRefused as error:
                imgroute._turn_off(name, error)                    # 그 경로만 끊는다
                raise RouteSkip(f"거부 — 이 경로만 끊음: {str(error)[:160]}") from error
            except vkclient.FlowBlocked as error:                 # 플로우 거부 — vkclient 가 멈춤 파일을 남겼다(모든 세션이 같이 봄)
                raise RouteSkip(f"플로우 거부 — 이 경로만 끊음: {str(error)[:160]}") from error
        return run
    makers = {name: wrap(name, flow if name == "flow" else imgroute.MAKERS[name]) for name in wanted if name in ROUTE_NAMES}
    usable = lambda name, job: name in makers and imgroute.usable(name, req_of(job))   # noqa: E731
    return makers, usable, (vkclient.FlowUnavailable, vkclient.FlowFailed, OSError, ValueError), batch


def _cache_hit(path):
    """캐시에 쓸 그림이 있나(요청 없이 꺼낸다) — 묶음에서 뺄 그림과 one() 이 꺼낼 그림을 같은 자로 가른다."""
    return os.path.isfile(path) and os.path.getsize(path) > 0


class LongformAgyImageError(ValueError):
    """일감이 규격에 안 맞음 — 아무것도 보내지 않았다. 사유는 사람이 읽을 말로."""


def _bad(msg):
    raise LongformAgyImageError("롱폼 그림 일감이 올바르지 않습니다: " + msg + " (아무 그림도 보내지 않았습니다)")


def check_item(item):
    """일감 모양 검사(보내기 전 · 한 번). 돌려주는 것: 일감 목록(그대로)."""
    if not isinstance(item, dict) or item.get("version") != VERSION:
        _bad(f"version 은 {VERSION} 이어야 합니다.")
    if not isinstance(item.get("contract_key"), str) or not re.fullmatch("[0-9a-f]{64}", item["contract_key"]):
        _bad("contract_key 가 sha256 글자(64자)가 아닙니다.")
    if not isinstance(item.get("model"), str) or not item["model"].strip():
        _bad("model 이 없습니다.")
    out_dir = item.get("out_dir")
    if not isinstance(out_dir, str) or not os.path.isabs(out_dir):
        _bad("out_dir 는 절대경로여야 합니다.")
    for k in ("timeout_s", "parallel"):
        v = item.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            _bad(f"{k} 는 1 이상의 정수여야 합니다.")
    pacing = item.get("pacing")
    if not isinstance(pacing, dict) or any(k not in pacing for k in PACING_KEYS):
        _bad("간격 표(pacing)에 " + ", ".join(PACING_KEYS) + " 가 다 있어야 합니다 — 간격 없이 보내지 않습니다.")
    routes = item.get("routes", ["agy"])
    if not isinstance(routes, list) or not routes or any(r not in ROUTE_NAMES for r in routes) or len(set(routes)) != len(routes):
        _bad("routes 는 " + "·".join(ROUTE_NAMES) + " 중에서 겹치지 않게 고른 목록이어야 합니다.")
    if item.get("route_pack") is not None and not (isinstance(item["route_pack"], str) and os.path.isabs(item["route_pack"])):
        _bad("route_pack 은 볼케이노킷 팩 폴더의 절대경로여야 합니다.")
    jobs = item.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        _bad("jobs 는 비어 있지 않은 목록이어야 합니다.")
    # 겹침은 casefold 로 본다 — 결과 파일이 대소문자를 가리지 않는 파일 시스템(APFS 기본·NTFS)에서 한 파일이 되면 뒤 그림이 앞
    # 그림을 덮는다(오류 없이). 집합 하나로 한 번 훑는다(쌍 비교 없음 · 6-00).
    ids, names = set(), set()
    for n, job in enumerate(jobs):
        where = f"jobs[{n}]"
        if not isinstance(job, dict):
            _bad(f"{where} 가 묶음이 아닙니다.")
        jid, name = job.get("id"), job.get("name")
        if not isinstance(jid, str) or not _ID.fullmatch(jid):
            _bad(f"{where}.id 는 영문·숫자·_.- 로 된 이름이어야 합니다(파일 이름이 됩니다).")
        if not isinstance(name, str) or not _ID.fullmatch(name):
            _bad(f"{where}.name 은 영문·숫자·_.- 로 된 이름이어야 합니다.")
        if jid.casefold() in ids or name.casefold() in names:
            _bad(f"{where} 의 id·name 이 다른 일감과 겹칩니다(대소문자만 달라도 같은 파일이 됩니다 · {jid} · {name}).")
        ids.add(jid.casefold())
        names.add(name.casefold())
        if not isinstance(job.get("prompt"), str) or not job["prompt"].strip():
            _bad(f"{where}.prompt 가 비었습니다.")
        if job.get("aspect") not in ASPECTS:
            _bad(f"{where}.aspect 는 {', '.join(ASPECTS)} 중 하나여야 합니다(받은 값 {job.get('aspect')!r}).")
        refs = job.get("refs")
        if not isinstance(refs, list) or len(refs) > MAX_REFS:
            _bad(f"{where}.refs 는 {MAX_REFS}장 이하의 목록이어야 합니다.")
        for r in refs:
            if not isinstance(r, str) or not os.path.isabs(r) or not os.path.isfile(r):
                _bad(f"{where}.refs 의 참조 그림이 없습니다(절대경로 파일이어야 합니다): {r!r}")
            if os.path.splitext(r)[1].lower() not in REF_EXTS:
                _bad(f"{where}.refs 의 {os.path.basename(r)!r} 는 그림 파일이 아닙니다 — 참조는 그림 파일만 됩니다"
                     f"({'·'.join(REF_EXTS)} · 영상이면 프레임을 뽑아 그림 media 로 등록하세요).")
    return jobs


def _measure(path, decoded):
    """결과 그림을 **한 번** 읽어 (sha256, 길이, 가로, 세로, 확장자). 같은 파일을 두 번 재지 않는다(6-00).

    decoded: 이 바이트를 이미 끝까지 풀어 본 적이 있는가 — 새로 그린 그림은 generate 가 캐시에 넣기 전에 풀어 봤으니(check_image_bytes)
      머리만 읽어 크기를 잰다. 캐시에서 꺼낸 그림은 이 판 전의 캐시(검사 없이 들어갔을 수 있음)일 수 있어 끝까지 풀어 본다.
    그림으로 안 읽히면 그 일감의 실패(AgyImageError)로 올린다 — 깨진 파일을 «됐다» 로 넘기지 않는다."""
    import hashlib                                                  # noqa: PLC0415
    from PIL import Image                                           # noqa: PLC0415
    import cardnews_agyimage as G                                   # noqa: PLC0415
    with open(path, "rb") as f:
        data = f.read()
    if decoded:
        try:
            with Image.open(io.BytesIO(data)) as im:
                fmt, (w, h) = im.format, im.size
        except G.IMAGE_DECODE_ERRORS as error:
            raise G.AgyImageError(f"agy 가 저장한 파일이 그림으로 읽히지 않습니다({len(data)}바이트).",
                                  code="AGY_IMAGE_UNREADABLE") from error
    else:
        fmt, w, h = G.check_image_bytes(data)
    ext = _EXT.get(str(fmt or "").upper())
    if not ext:
        raise G.AgyImageError(f"agy 가 그린 그림의 형식({fmt})을 쓸 수 없습니다(png·jpg·webp 만).", code="AGY_IMAGE_FORMAT")
    return hashlib.sha256(data).hexdigest(), len(data), w, h, ext


def prepare_agy_images(item):
    """서버 일감 `prepare_agy_images`(설계 3-2) → {version, contract_key, status, images, errors, refused}.

    · 같은 지문(참조 sha256 순서·지시문·비율·모델)의 그림이 캐시에 있으면 다시 그리지 않는다(cache_hit — 보내기 전에 캐시 자리로 판정;
      CACHE_STATS 의 차이는 여러 스레드가 함께 세서 그 일감의 것인지 모른다).
    · 그림마다 routes 를 한 바퀴만 돈다(머리말 «경로 돌기»). 거부는 그 경로만 끊고 agy 거부는 refused 에 남는다(종류 kind 포함).
    · 모든 경로가 실패한 그림만 errors(all_routes_failed · tried 에 경로마다 까닭) · 그때만 status blocked.
    · 캐시에서 꺼낸 그림이 안 풀리면 그 캐시 파일을 지운다 — 사람이 다시 내면 새로 그린다(자동으로 다시 그리지 않는다).
    · 그 밖의 예외는 삼키지 않고 올린다.
    · 캐시에서 꺼내는 일감은 요청이 아니므로 거부 뒤에도 끝낸다(이미 그린 그림을 버리지 않는다)."""
    from concurrent.futures import ThreadPoolExecutor              # noqa: PLC0415
    import cardnews_agyimage as G                                   # noqa: PLC0415
    import agy_transport_refusal as RUN_REFUSAL                     # noqa: PLC0415
    jobs = check_item(item)
    G.set_pacing(item["pacing"])
    model, out_dir, timeout_s = item["model"], item["out_dir"], int(item["timeout_s"])
    os.makedirs(out_dir, exist_ok=True)
    # 참조 그림 지문은 파일마다 한 번 — 여러 일감이 같은 참조를 써도 다시 재지 않는다(6-00 «중복 지문 금지»).
    ref_sha = {}
    for job in jobs:
        for r in job["refs"]:
            if r not in ref_sha:
                ref_sha[r] = G._file_sha(r)
    keys, seen = {}, set()
    for job in jobs:
        k = G.key_from_shas([ref_sha[r] for r in job["refs"]], job["prompt"], job["aspect"], model)
        if k in seen:
            # 같은 요청 둘 = 같은 그림 둘(돈·한도 두 번) — 서버가 지시문 중복을 막는데도 왔으면 보내지 않고 알린다.
            _bad(f"{job['id']} 가 다른 일감과 같은 그림 요청입니다(참조·지시문·비율이 같음).")
        seen.add(k)
        keys[job["id"]] = k
    out = {"version": VERSION, "contract_key": item["contract_key"], "status": "complete",
           "images": {}, "errors": {}, "refused": None}
    lock = threading.Lock()
    makers, usable, route_errors, flow_batch = _routes(item, timeout_s)
    routes = [r for r in item.get("routes") or ("agy",) if r in makers or r == "agy"]
    agy = {"off": None, "last_code": None, "streak": 0}     # agy 경로 상태(이 실행) — lock 안에서만 읽고 쓴다
    from subject_agy_run import refusal_continues              # noqa: PLC0415 — 거부 종류 한 규칙(피사체 판독과 같다)

    def agy_off(why):
        if agy["off"] is None:
            agy["off"] = why

    def agy_route(job, part):
        """agy 경로 한 번(이 실행기의 부품 — 지문 캐시·공용 agy 그림 줄·거부 판정). 끊긴 경로면 RouteSkip."""
        with lock:
            if agy["off"]:
                raise RouteSkip(agy["off"])
        try:
            G.generate(list(job["refs"]), job["prompt"], job["aspect"], job["name"], part, model, out_dir,
                       status_error="per_request_evidence", key=keys[job["id"]], timeout_s=timeout_s)
        except RUN_REFUSAL.RunServiceRefused as error:
            pr = getattr(error, "provider_result", None) or {}
            kind = RUN_REFUSAL.refusal_kind() or str(pr.get("code") or getattr(error, "code", "RUN_SERVICE_REFUSED"))
            with lock:
                if out["refused"] is None:
                    out["refused"] = {"code": str(pr.get("code") or getattr(error, "code", "RUN_SERVICE_REFUSED")),
                                      "message": str(pr.get("message") or error)[:400], "kind": kind}
                agy_off(("한도·속도·로그인 거부" if refusal_continues(kind) else "거부") + f"({kind}) — agy 경로만 건너뜀")
            raise RouteSkip(agy["off"]) from error
        except G.AgyGateStuck as error:
            with lock:
                agy_off(f"이 PC 의 agy 그림 줄이 멈춤 — agy 경로만 건너뜀({str(error)[:160]})")
            raise RouteSkip(agy["off"]) from error
        except G.AgyImageError as error:
            with lock:
                same = agy["last_code"] == error.code
                agy["last_code"], agy["streak"] = error.code, (agy["streak"] + 1 if same else 1)
                if agy["streak"] >= REPEAT_STOP:
                    agy_off(f"같은 실패({error.code})가 {REPEAT_STOP}번 잇따름 — agy 경로만 건너뜀")
            raise RouteFailed(f"{error.code}: {str(error)[:200]}") from error
        with lock:
            agy["last_code"], agy["streak"] = None, 0
        return part

    def one(job):
        jid, name = job["id"], job["name"]
        cached = G.cached_path(keys[jid])
        hit = _cache_hit(cached)
        part = os.path.join(out_dir, name + ".agy-part")
        tried, got, via = {}, None, None
        for route in (["agy"] if hit else routes):             # 캐시에 있으면 요청 없이 꺼낸다 · 아니면 경로를 한 바퀴만
            if route != "agy" and not usable(route, job):
                tried[route] = "못 쓰는 상태(거부·멈춤·참고 그림·연결 없음)"
                continue
            try:
                got = agy_route(job, part) if route == "agy" else makers[route](job, out_dir)
                via = route
                break
            except RouteSkip as error:
                tried[route] = f"건너뜀: {error}"
            except RouteFailed as error:
                tried[route] = f"실패: {error}"
            except route_errors as error:                       # 볼케이노킷 경로의 거부·실패 — 그 경로 코드가 이미 끊었다(imgroute._turn_off)
                tried[route] = f"{type(error).__name__}: {str(error)[:200]}"
        if got is None:
            with lock:
                out["errors"][jid] = {"code": "all_routes_failed", "tried": tried,
                                      "message": "모든 그림 경로가 실패: " + " · ".join(f"{k}: {v}" for k, v in tried.items())[:600]}
            return
        if got != part:
            shutil.copyfile(got, part)                          # 다른 경로의 결과(그 경로 폴더) → 이 그림 자리
        try:
            sha, size, w, h, ext = _measure(part, decoded=(via == "agy" and not hit))
        except G.AgyImageError as error:
            if via == "agy":
                # 쓸 수 없는 그림이 캐시에 있다 — 지워야 사람이 다시 낼 때 새로 그린다(자동으로 다시 그리지 않는다).
                os.remove(cached)
            os.remove(part)
            with lock:
                out["errors"][jid] = {"code": "agy_image_unreadable", "message": f"{via}: {str(error)[:300]}"}
            return
        final = os.path.join(out_dir, f"{name}.{ext}")
        try:
            # 윈도우 백신·색인기가 막 쓴 파일을 잠깐 쥐면 os.replace 가 WinError 5 로 실행 전체를 멈췄다(2026-10-17 신고 #131) —
            # 상한 있는 같은 지연(longform_state.replace · 한 자리)으로 다시 해 보고, 그래도 잠겨 있으면 이 그림 하나의 실패로 남긴다.
            from longform_state import replace as replace_file      # noqa: PLC0415 — 그림이 나온 뒤에만 무거운 모듈을 읽는다
            replace_file(part, final)
        except PermissionError as error:
            with lock:
                out["errors"][jid] = {"code": "agy_image_locked", "message":
                                      f"다른 프로그램(백신·검색 색인 등)이 그린 그림 파일을 쥐고 있어 이름을 바꾸지 못했습니다({os.path.basename(final)} · "
                                      f"{error}). 그림은 이 PC 캐시에 있어 다시 내면 새로 그리지 않습니다."}
            return
        with lock:
            out["images"][jid] = {"path": final, "sha256": sha, "bytes": size, "width": w, "height": h,
                                  "cache_hit": hit, "via": via}

    try:
        RUN_REFUSAL.assert_allowed()              # 이미 거부 표식이 걸린 실행이면 agy 경로는 처음부터 건너뛴다(캐시는 쓴다)
    except RUN_REFUSAL.RunServiceRefused as error:
        kind = RUN_REFUSAL.refusal_kind() or getattr(error, "code", "RUN_SERVICE_REFUSED")
        out["refused"] = {"code": getattr(error, "code", "RUN_SERVICE_REFUSED"), "message": str(error)[:400], "kind": kind}
        agy_off(f"이 실행에 이미 거부 표식({kind}) — agy 경로만 건너뜀")
    if routes and routes[0] == "flow":            # 플로우가 첫 경로면 캐시에 없는 그림을 한 번에 보낸다(실패한 것만 다음 경로로 · 아래 one)
        flow_batch([j for j in jobs if not _cache_hit(G.cached_path(keys[j["id"]]))], out_dir)
    with ThreadPoolExecutor(max_workers=min(int(item["parallel"]), len(jobs))) as ex:
        for fut in [ex.submit(one, job) for job in jobs]:
            fut.result()                          # 경로 실패 밖의 예외는 삼키지 않고 올린다
    if out["errors"]:
        out["status"] = "blocked"
    return out
