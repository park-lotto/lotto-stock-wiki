# -*- coding: utf-8 -*-
"""카드 그림을 **agy 그림 도구(generate_image · Nano Banana 2)** 로 레퍼런스와 같은 디자인으로 만든다 (2026-10-08).

■ 왜 (쇼츠대폭발 10-08 결정 «agy 그림 도구로 — 레퍼런스와 완벽하게 똑같이 · 잡스러운 단계는 빼라»)
    레퍼런스 그림을 참조(ImagePaths)로 넘기면 바탕·글꼴 느낌·꾸밈까지 한 번에 따라 그린다. 대신 글자를 그림 모델이 그리므로
    **오탈자가 날 수 있다** — 그래서 만든 뒤 agy 가 «보이는 글자를 그대로 받아 적고» 프로그램이 기대 문구와 대조한다
    (전역 규칙 6-1 검수 방식). 틀리면 같은 레퍼런스로 **글자 없는 바탕**을 다시 그리고 글자는 잰 자리에 코드가 얹는다
    (`cardnews_render.render_card(layout=…)` — 오탈자 0 을 보증하는 길).

■ 실행기 경계: 지시문(무엇을 그릴지)·받아 적기 질문·모델은 **서버가 준다.** 여기에는 agy 부르기·파일 옮기기·글자 견주기만.
■ 거부(한도·로그인·속도)는 `agy_transport_client.invoke` 가 이 실행 전체를 멈추는 예외로 올린다 — 삼키지 않는다(6-2).
"""

import json
import os
import re
import shutil

from PIL import Image

#: 받아 적기 답 모양.
READ_SCHEMA = {"type": "object", "required": ["lines"],
               "properties": {"lines": {"type": "array", "items": {"type": "string"}}}}
READ_CARD_SCHEMA = {"type": "object", "required": ["lines", "clipped"],
                    "properties": {"lines": {"type": "array", "items": {"type": "string"}},
                                   "clipped": {"type": "array", "items": {"type": "string"}}}}


class AgyImageError(RuntimeError):
    """그림을 못 만듦. 사유는 사람이 읽을 말로.

    code: 실패의 갈래(전송 코드 AGY_TIMEOUT·AGY_ERROR … 또는 이 부품의 AGY_IMAGE_*). 부르는 쪽(롱폼 그림 10-09)이 «같은 실패가
      잇따르면 남은 그림을 보내지 않는다» 를 문구가 아니라 이 값으로 가른다(문구로 가르면 말이 바뀔 때 조용히 깨진다 · CLAUDE.md §4)."""

    def __init__(self, message, code="AGY_IMAGE_FAILED"):
        super().__init__(message)
        self.code = str(code or "AGY_IMAGE_FAILED")


class AgyGateStuck(AgyImageError):
    """이 PC 공용 agy 그림 줄의 잠금을 상한 안에 못 잡음(10-09). 그림 하나의 사정이 아니라 **줄 전체**가 멈춘 것이라
    한 장마다 또 상한만큼(600초) 기다리면 남은 그림 수 × 600초를 헛되이 쓴다 — 부르는 쪽이 실행 전체를 멈추라고 갈래를 둔다.
    AgyImageError 의 자식이라 카드뉴스(`make_cards` 등)의 «그 길만 탈락» 처리는 예전 그대로 맞는다."""


def _invoke(prompt, *, kind, files=(), schema=None, model=None, cwd=None, timeout_s=900, status_error=None):
    import agy_transport_client as AGY                              # noqa: PLC0415
    # status_error 는 부르는 쪽이 고를 때만 싣는다(롱폼 그림 10-09 'per_request_evidence') — 없으면 전송 기본값(카드뉴스 지금 그대로).
    extra = {"status_error": status_error} if status_error else {}
    return AGY.invoke(prompt, kind=kind, files=list(files), schema=schema, model=model, timeout_s=timeout_s, cwd=cwd, **extra)


#: IMAGE_PATH 줄의 경로 — 한 줄 안에서 확장자로 끝나는 가장 짧은 글자(2026-10-17 신고 #122: 예전 `\S+` 는 «C:\Users\Windows 10\…» 처럼
#: 공백이 든 윈도우 경로를 못 읽었다). 앞의 백틱·따옴표·꺾쇠는 건너뛰고, 뒤에 붙는 마침표·따옴표는 확장자에서 끊겨 안 들어간다.
_PATH = re.compile(r"IMAGE_PATH:[ \t]*[`'\"<]?([^\r\n]+?\.(?:png|jpe?g|webp))", re.I)
#: agy 가 답을 끝낸 뒤에야 하위 에이전트가 그림을 저장하는 일이 있다(신고 #122 · «몇 초 뒤 파일이 생김»). 답 뒤 이 시간 안에서만
#: POLL 간격으로 저장 자리를 다시 본다 — 상한 있는 한 번의 대기이고 agy 에 다시 보내지 않는다(6-00 · 6-2).
#: 크기가 두 번 잇따라 같아야 «저장 끝» 으로 친다(덜 쓴 파일을 깨진 그림으로 읽지 않게).
SAVE_WAIT_S, SAVE_POLL_S = 30.0, 0.5
#: agy 답 글에서 그림 도구의 한도·속도 거부를 알아보는 표시(10-08 실측 문구 — 429 · RESOURCE_EXHAUSTED · QUOTA_EXHAUSTED ·
#: «exhausted your capacity»). 실행기의 다른 agy 부품(`agy_google.search_one`)과 같은 낱말을 본다.
QUOTA_SIGNS = re.compile(r"\b429\b|RESOURCE_EXHAUSTED|QUOTA_EXHAUSTED|exhausted your capacity|rate limit", re.I)


# ── 그림 캐시 (쇼츠대폭발 10-08 «반복 검증 낭비 금지» · 하루 그림 약 112장을 같은 계정 재그리기로 썼다) ─────────
#
# ■ 같은 지문(참조 그림 sha256 + 그림 지시문 + 비율 + 모델)이면 다시 그리지 않고 전에 그린 것을 쓴다.
#   지시문에 카드 글자가 들어가는 «글자까지 그린 카드» 는 글자가 바뀌면 지문이 바뀌어 새로 그리고, 글자가 안 들어가는
#   «사진만» 은 글자·배치가 바뀌어도 다시 쓴다. 수강생 PC 도 같다 — 다시 돌려도 한도를 다시 쓰지 않는다.
# ■ 자리: ~/.volcano/cardnews_agycache/<지문>.png (`CARDNEWS_AGY_CACHE` 로 바꿀 수 있다). 지우면 다시 그린다.
CACHE_STATS = {"hit": 0, "miss": 0}


def cache_dir():
    d = os.environ.get("CARDNEWS_AGY_CACHE") or os.path.join(os.path.expanduser("~"), ".volcano", "cardnews_agycache")
    os.makedirs(d, exist_ok=True)
    return d


def _file_sha(path):
    import hashlib                                                  # noqa: PLC0415
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def key_from_shas(ref_shas, image_prompt, aspect, model):
    """지문 — 참조 그림 sha256 목록(순서대로) + 지시문 + 비율 + 모델. 참조가 0·1장이면 예전 지문 모양 그대로(카드뉴스 캐시가
    그대로 맞는다 · 같은 요청이면 같은 지문). 2장 이상(롱폼 그림 10-09 · agy ImagePaths 최대 3)이면 순서까지 지문에 넣는다 —
    참조 순서가 바뀌면 agy 에 가는 요청도 바뀌기 때문이다."""
    import hashlib                                                  # noqa: PLC0415
    shas = list(ref_shas)
    head = {"ref": shas[0] if shas else None} if len(shas) <= 1 else {"refs": shas}
    body = json.dumps(dict(head, prompt=image_prompt, aspect=aspect, model=model), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def image_key(ref_path, image_prompt, aspect, model):
    """ref_path: 경로 하나(카드뉴스 — 없는 파일이면 참조 없음으로 친다, 예전 그대로) 또는 경로 목록(롱폼 그림 — 목록의 파일은
    있어야 한다 · 없으면 OSError 를 그대로 올린다 · 부르는 쪽이 보내기 전에 확인한다)."""
    if isinstance(ref_path, (list, tuple)):
        return key_from_shas([_file_sha(p) for p in ref_path], image_prompt, aspect, model)
    return key_from_shas([_file_sha(ref_path)] if ref_path and os.path.isfile(ref_path) else [], image_prompt, aspect, model)


# ── agy 그림 요청 줄 (쇼츠대폭발 10-08 «agy 그림에도 6-0 플로우 규칙과 같은 값 · 여러 세션이 함께 세게») ─────────────
#   플로우 공용 줄(~/.flowkit-gate · info3d flow_client._take_turn)과 같은 방식 — spacing.lock 파일 잠금 안에서 last-send 를
#   읽어 기다리고 «<보낸 시각> agy-image pid <pid> burst <n>» 를 적는다. 줄 이름만 agy 그림 전용(서버가 준다).
#   숫자(간격·묶음·쉼)는 전부 서버가 준다(`volcano_cardnews.agy_image_pacing` ← `volcano_image_engine.PACING`).
_PACING = {}
#: 줄 잠금을 기다리는 상한 = burst_gap_s × 이 수(10-09 · 전역 규칙 6-00 «무한 대기 금지»). 근거: 잠금을 쥔 쪽은 «기다릴 초»
#: (turn_wait — 최대 burst_gap_s) 만큼 자고 한 줄 적은 뒤 놓는다 → 한 차례가 쥐는 시간은 burst_gap_s 남짓. 이 PC 에서 함께 줄을 서는
#: 보내는 쪽은 카드뉴스 동시 4 · 롱폼 그림 동시 4 · 전자책 등을 다 합쳐도 16(agy 병렬 상한 · 전역 규칙 6-1)이라 최악 16 × 20초 = 320초.
#: 그 두 배 가까이(30 차례 · 6-0 값으로 600초)를 넘게 못 잡으면 정상 줄서기가 아니라 멈춘 쪽이 있는 것이다 — 기다리지 않고 알린다.
LOCK_WAIT_TURNS = 30


def set_pacing(p):
    _PACING.clear()
    _PACING.update(p or {})


class _FileLock:
    """파일 하나의 배타 잠금(맥 flock · 윈도우 msvcrt) — 플로우 줄 `flow_client._FileLock` 과 같은 동작."""

    def __init__(self, path):
        self.path, self.f = path, open(path, "a+b")

    def try_lock(self):
        try:
            if os.name == "nt":
                import msvcrt                                       # noqa: PLC0415
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl                                        # noqa: PLC0415
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, PermissionError):
            return False
        except OSError as e:
            if os.name == "nt" and getattr(e, "errno", None) in (13, 36):
                return False
            raise

    def lock(self, poll, max_wait_s):
        """잠금을 잡을 때까지 기다린다 — **max_wait_s 를 넘으면 멈춘다**(전역 규칙 6-00 «상한 없는 대기 금지» · 10-09).
        잡지 못하면 파일을 닫고 AgyImageError 로 올린다(그 그림은 보내지 않는다 · 자동으로 다시 기다리지 않는다)."""
        import time                                                 # noqa: PLC0415
        deadline = time.monotonic() + float(max_wait_s)
        while not self.try_lock():
            if time.monotonic() >= deadline:
                self.f.close()
                raise AgyGateStuck(f"agy 그림 요청 줄의 잠금을 {float(max_wait_s):.0f}초 동안 잡지 못했습니다 — 다른 작업이 줄을 "
                                    "오래 쥐고 있습니다. 이 그림은 보내지 않았습니다(자동으로 다시 기다리지 않음). "
                                    "다른 agy 그림 작업이 끝났는지 확인한 뒤 다시 실행하세요.", code="AGY_GATE_STUCK")
            time.sleep(poll)

    def unlock(self):
        try:
            if os.name == "nt":
                import msvcrt                                       # noqa: PLC0415
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl                                        # noqa: PLC0415
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        finally:
            self.f.close()


def gate_dir():
    d = os.environ.get("CARDNEWS_AGY_IMAGE_GATE") or os.path.join(os.path.expanduser("~"), str(_PACING.get("line")))
    os.makedirs(d, exist_ok=True)
    return d


def turn_wait(now, last, burst, p):
    """(기다릴 초, 이번 순번). 앞 요청이 없거나 idle_reset_s 넘게 쉬었으면 새 묶음 1번째 · 묶음이 덜 찼으면 앞 요청 뒤 gap_s ·
    다 찼거나 순번을 모르면 앞 요청 뒤 burst_gap_s."""
    if not last:
        return 0.0, 1
    since = now - last
    if since >= float(p["idle_reset_s"]):
        return 0.0, 1
    if burst is not None and 1 <= burst < int(p["burst"]):
        return max(0.0, float(p["gap_s"]) - since), burst + 1
    return max(0.0, float(p["burst_gap_s"]) - since), 1


def take_turn():
    """그림 한 장 보내기 바로 앞 — 이 PC 의 agy 그림 줄에서 차례를 기다리고 적는다. 간격 표가 없으면 멈춘다(규칙 없이 보내지 않는다)."""
    import threading                                                # noqa: PLC0415
    import time                                                     # noqa: PLC0415
    p = _PACING
    if not all(k in p for k in ("gap_s", "burst", "burst_gap_s", "idle_reset_s", "poll_s", "line")):
        raise AgyImageError("그림 요청 간격 표가 응답에 없습니다 — 간격 없이 보내지 않습니다(images 단계를 다시 부르세요).")
    folder = gate_dir()
    lock = _FileLock(os.path.join(folder, "spacing.lock"))
    lock.lock(float(p["poll_s"]), float(p["burst_gap_s"]) * LOCK_WAIT_TURNS)
    try:
        try:
            with open(os.path.join(folder, "last-send"), encoding="utf-8") as f:
                words = f.read().split()
            last = float(words[0])
            burst = int(words[words.index("burst") + 1]) if "burst" in words else None
        except (OSError, ValueError, IndexError):
            last, burst = 0.0, None
        wait, turn = turn_wait(time.time(), last, burst, p)
        if wait > 0:
            time.sleep(wait)
        now = time.time()
        tmp = os.path.join(folder, f"last-send.{os.getpid()}.{threading.get_ident()}.part")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"{now!r} agy-image pid {os.getpid()} burst {turn}\n")
        os.replace(tmp, os.path.join(folder, "last-send"))
    finally:
        lock.unlock()
    return now, turn


def cached_path(key):
    """지문 → 캐시 그림 자리(있는지는 부르는 쪽이 본다). 이름은 언제나 .png 다 — agy 가 jpg·webp 로 그렸어도 바이트 그대로
    이 이름에 담는다(예전부터 · 확장자는 받는 쪽이 바이트로 가린다 — `longform_agyimage`)."""
    return os.path.join(cache_dir(), key + ".png")


def generate(ref_path, image_prompt, aspect, name, out_path, model, workdir, status_error=None, key=None, timeout_s=900):
    """레퍼런스(있으면)를 참조로 agy generate_image 한 번 → out_path(그대로 복사). 돌려주는 것: out_path.
    같은 지문의 그림이 캐시에 있으면 그리지 않고 그것을 쓴다(`CACHE_STATS` 에 센다).

    ref_path: 경로 하나 또는 None(카드뉴스 · 예전 그대로) · 경로 목록(롱폼 그림 10-09 · 0~3장 · 순서대로 ImagePaths).
    status_error: None 이면 전송 기본값(카드뉴스 지금 그대로) · 롱폼 그림은 'per_request_evidence'(그 그림 하나만 실패 — 한도·속도·
      로그인의 증거가 있을 때만 전부 멈춤 · agy_transport_client.invoke).
    key: 부르는 쪽이 이미 잰 지문(image_key 와 같은 값) — 참조 그림 sha256 을 두 번 재지 않으려고(전역 규칙 6-00 «중복 지문 금지»).
      없으면 여기서 잰다.

    ★지시문(image_prompt)은 «한 글자도 바꾸지 말고» generate_image 의 Prompt 로 넘기라고 한다 — agy 가 고쳐 쓰면 서버가 잰
      자리·색이 흐려진다."""
    import glob                                                     # noqa: PLC0415
    import uuid                                                     # noqa: PLC0415
    os.makedirs(workdir, exist_ok=True)
    cached = cached_path(key or image_key(ref_path, image_prompt, aspect, model))
    if os.path.isfile(cached) and os.path.getsize(cached) > 0:
        CACHE_STATS["hit"] += 1
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        shutil.copyfile(cached, out_path)
        return out_path
    CACHE_STATS["miss"] += 1
    if isinstance(ref_path, (list, tuple)):
        refs = [os.path.abspath(r) for r in ref_path]
    else:
        refs = [os.path.abspath(ref_path)] if ref_path else []
    # ★그림 이름을 이 호출만의 이름으로 — agy 가 IMAGE_PATH 줄을 빠뜨려도(10-08 실측 1회) 그 이름으로 저장 자리를 찾는다.
    #   agy 는 그림을 ~/.gemini/antigravity-cli/brain/<대화>/<이름>_<시각>.<확장자> 에 둔다(맥 실측 · 윈도우도 같은 자리 —
    #   `agy_google.brain_dir`).
    # ★ImageName 은 영문·숫자·밑줄만(신고 #122: agy 는 하이픈을 밑줄로 바꿔 저장해 «이 이름으로 찾기» 가 빗나갔다). 찾는 열쇠는 이
    #   호출만의 꼬리(tag · 16진수 10자)다 — agy 가 앞부분을 또 바꾸어도 꼬리로 찾는다. 바깥 out_path·캐시 지문은 이름과 무관하다.
    tag = uuid.uuid4().hex[:10]
    name = re.sub(r"[^0-9A-Za-z_]", "_", str(name or "image")) + "_" + tag
    # ★도구는 generate_image 하나만 — 10-08 실측: agy 가 그림을 기다리며 하위 에이전트 기록·설정 파일을 열려다 거부당했고
    #   (read_file ~/.gemini/config/mcp_config.json 거부), 공용 전송 부품은 거부를 «이 실행 전부 멈춤» 으로 다룬다(6-2).
    #   그래서 확인·열람을 하지 말라고 못박는다(만든 그림의 확인은 우리가 받아 적기·비교로 따로 한다).
    lead = ("도구는 generate_image 하나만 쓴다 — view_file·list_dir·검색·RunCommand·셸·브라우저·URL 등 다른 도구는 한 번도 쓰지 마라"
            "(만든 그림을 열어 확인하지도 말고, 하위 에이전트 기록·설정 파일도 열지 마라 — 확인은 부른 쪽이 한다). "
            "generate_image 를 **한 번만** 불러라. 인자: "
            + json.dumps({"ImagePaths": refs, "AspectRatio": aspect, "ImageName": name}, ensure_ascii=False)
            + ", Prompt = 아래 «지시문» 을 한 글자도 바꾸지 않고 그대로. 그림이 저장되면 마지막 줄에 "
              "IMAGE_PATH: <저장된 그림의 절대경로> 만 적어라.\n\n«지시문»\n")
    take_turn()                    # ★보내기 바로 앞 — 이 PC 공용 agy 그림 줄(6-0 값)
    # status_error 는 고른 쪽만 싣는다 — 카드뉴스 호출은 예전 인자 그대로(_invoke 를 바꿔 끼우는 검사·도구도 그대로 맞는다).
    res = _invoke(lead + image_prompt, kind=None, files=refs, model=model, cwd=workdir, timeout_s=timeout_s,
                  **({"status_error": status_error} if status_error else {}))
    if not res.get("ok"):
        raise AgyImageError(f"agy 그림 실패({res.get('code')}): {str(res.get('message') or '')[:200]}", code=res.get("code"))
    said = res.get("text") or ""
    # ★그림 파일부터 찾는다(10-09 검토 MAJOR) — 예전에는 한도 표시를 답 **전체**에서 먼저 찾아, 그림 이름·경로에 «429» 가 든
    #   정상 답(media id 'scene-429' → IMAGE_PATH …/scene-429_….png)을 거부로 읽었다. 거부는 캐시에 남지 않으니 다시 돌릴 때마다
    #   같은 그림을 또 그려 한도를 거듭 썼다. 그림이 실제로 저장됐으면 거부가 아니다.
    brain = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity-cli", "brain")

    def saved():
        """저장된 그림 후보(IMAGE_PATH 가 가리키는 실제 파일 → 없으면 brain 아래 이 호출의 꼬리가 든 파일 · 오래된 것부터)."""
        found = [x.strip() for x in _PATH.findall(said)]
        found = [x for x in found if os.path.isfile(x)]
        return found or sorted((x for ext in ("png", "jpg", "jpeg", "webp")
                                for x in glob.glob(os.path.join(glob.escape(brain), "*", f"*{tag}*.{ext}"))), key=os.path.getmtime)

    m = saved()
    prose = "\n".join(line for line in said.splitlines() if "IMAGE_PATH" not in line.upper())   # 확장자 없는 경로 줄도 뺀다
    if not m and not QUOTA_SIGNS.search(prose):
        m = _wait_saved(saved)
    if not m:
        # ★그림 도구의 한도·속도 거부는 agy 답이 «SUCCESS» 인 채 **글로만** 알린다(10-08 실측: «429 RESOURCE_EXHAUSTED …
        #   QUOTA_EXHAUSTED · gemini-3.1-flash-image · reset after 1h37m»). 그림이 없을 때만, 그리고 IMAGE_PATH 줄(경로 글자)을 뺀
        #   나머지 글에서 그 표시를 찾는다 — 경로의 숫자를 거부로 읽지 않는다. 보이면 거부로 다룬다: 이 실행의 agy 요청을 전부
        #   멈추고(전역 규칙 6-2) 자동으로 다시 보내지 않는다. 다른 길(코드 길의 사진 그리기)도 같은 그림 도구라 넘어가지 않는다.
        if QUOTA_SIGNS.search(prose):
            import agy_transport_refusal as RUN_REFUSAL             # noqa: PLC0415
            RUN_REFUSAL.mark_refusal(kind="AGY_QUOTA")         # 한도 거부 — 거부 종류 표(GATE_REFUSAL_CODES)의 이름으로 남긴다
            failure = RUN_REFUSAL.RunServiceRefused()
            failure.provider_result = {"code": "AGY_IMAGE_QUOTA", "message": said[-400:]}
            raise failure
        raise AgyImageError("agy 가 그림을 저장하지 않았습니다(IMAGE_PATH 도 없고 그 이름의 파일도 없음) — 그 카드는 만들지 못했습니다.",
                            code="AGY_IMAGE_NOT_SAVED")
    # ★캐시에 넣기 전에 그림인지 끝까지 풀어 본다(10-09 검토 MAJOR) — 예전에는 받은 파일을 그대로 캐시에 넣어, 잘린·깨진 파일이
    #   한 번 들어가면 같은 지문의 다음 호출이 모두 그 파일을 «캐시 적중» 으로 받았다(지우기 전까지 영영). 바이트를 한 번 읽어
    #   그 바이트로 풀어 보고, 같은 바이트를 결과·캐시에 쓴다(파일을 두 번 읽지 않는다 · 6-00).
    with open(m[-1], "rb") as f:
        data = f.read()
    check_image_bytes(data)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)
    tmp = cached + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, cached)
    return out_path


def _wait_saved(saved):
    """답 뒤 늦게 저장되는 그림을 SAVE_WAIT_S 안에서만 기다린다 — 후보 파일의 크기가 0 이 아니고 두 번 잇따라 같으면 그 목록.
    끝내 없으면 [] (부르는 쪽이 AGY_IMAGE_NOT_SAVED 로 그 그림 하나만 실패로 적는다). 다시 보내지 않는다."""
    import time                                                     # noqa: PLC0415
    deadline = time.monotonic() + SAVE_WAIT_S
    last = None
    while time.monotonic() < deadline:
        time.sleep(SAVE_POLL_S)
        found = saved()
        size = os.path.getsize(found[-1]) if found else 0
        now = (found[-1], size) if size else None
        if now and now == last:
            return found
        last = now
    return []


#: PIL 이 그림을 못 풀 때 내는 예외 — UnidentifiedImageError·잘린 파일(OSError) · 형식 오류(SyntaxError·ValueError) · 지나치게 큰
#: 그림(DecompressionBombError 는 Exception 의 직계라 따로 적는다). 이 밖의 예외는 잡지 않는다(삼키지 않음).
IMAGE_DECODE_ERRORS = (OSError, SyntaxError, ValueError, Image.DecompressionBombError)


def check_image_bytes(data):
    """그림 바이트를 **끝까지** 풀어 본다(헤더만 보면 잘린 PNG·JPEG 가 통과한다). 돌려주는 것: (형식, 가로, 세로).
    못 풀면 AgyImageError(code AGY_IMAGE_UNREADABLE) — 깨진 파일을 «됐다» 로 넘기지 않는다."""
    import io                                                       # noqa: PLC0415
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            return im.format, im.size[0], im.size[1]
    except IMAGE_DECODE_ERRORS as error:
        raise AgyImageError(f"agy 가 저장한 파일이 그림으로 읽히지 않습니다({len(data)}바이트 · {type(error).__name__}).",
                            code="AGY_IMAGE_UNREADABLE") from error


# ── 두 길 비교는 레퍼런스당 한 번 (쇼츠대폭발 10-08) ────────────────────────────────────────────────
#   같은 레퍼런스 그림(sha256)·같은 비교 질문이면 전에 이긴 길만 그린다. 기록: <캐시>/route_<지문>.json.
#   지우면 다음 한 벌에서 다시 두 길을 견준다.
def _route_path(ref_path, sim_question):
    import hashlib                                                  # noqa: PLC0415
    k = hashlib.sha256(json.dumps({"ref": _file_sha(ref_path), "q": sim_question}, ensure_ascii=False,
                                  sort_keys=True).encode("utf-8")).hexdigest()[:32]
    return os.path.join(cache_dir(), f"route_{k}.json")


def load_route(ref_path, sim_question):
    if not ref_path or not os.path.isfile(ref_path):
        return None
    p = _route_path(ref_path, sim_question)
    try:
        with open(p, encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError):
        return None
    return r if r.get("engine") in ("agy", "code") else None


def save_route(ref_path, sim_question, verdict, note=None):
    if not ref_path or not os.path.isfile(ref_path):
        return
    rec = {"engine": verdict.get("engine"), "score": verdict.get("score"), "codeScore": verdict.get("codeScore")}
    if note:
        rec["note"] = note
    p = _route_path(ref_path, sim_question)
    with open(p + ".part", "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    os.replace(p + ".part", p)


def fetch_ref(fetch, workdir, timeout=120):
    """배급된 레퍼런스 표지 한 장을 받는다 — 서버가 준 서명 주소(refFetch.url)·대조값(sha256)으로. 받은 경로를 돌려준다.

    ★받은 바이트의 sha256 이 다르면 쓰지 않는다(지운다). 이미 같은 파일이 있으면 다시 받지 않는다.
    ★실행기 UA 를 싣는다 — 파이썬 기본 UA 는 Cloudflare 가 1010/403 으로 막는다(CLAUDE.md §4).
    ★4xx 에 되풀이하지 않는다(만료 주소면 images 단계를 다시 불러 새 주소를 받는다)."""
    import hashlib                                                  # noqa: PLC0415
    import urllib.request                                           # noqa: PLC0415
    if not fetch or not fetch.get("url") or not fetch.get("sha256"):
        raise AgyImageError("레퍼런스 표지 배급 주소가 없습니다.")
    os.makedirs(workdir, exist_ok=True)
    out = os.path.join(workdir, os.path.basename(str(fetch.get("name") or "ref.jpg")))
    if os.path.exists(out):
        with open(out, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == fetch["sha256"]:
                return out
    req = urllib.request.Request(fetch["url"], headers={"User-Agent": "volcano-runner/1.0 (cardnews-ref)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if hashlib.sha256(raw).hexdigest() != fetch["sha256"]:
        raise AgyImageError("받은 레퍼런스 표지의 sha256 이 서버 값과 다릅니다 — 쓰지 않습니다.")
    tmp = out + ".part"
    with open(tmp, "wb") as f:
        f.write(raw)
    os.replace(tmp, out)
    return out


def read_text(path, question, model, with_clip=False):
    """agy 가 그림의 글자를 줄마다 보이는 그대로 받아 적는다(질문은 서버가 준다).
    with_clip=True 면 같은 한 번의 호출에서 «가장자리에서 잘린 줄» 도 받아 (줄 목록, 잘린 줄 목록) 을 돌려준다."""
    schema = READ_CARD_SCHEMA if with_clip else READ_SCHEMA
    res = _invoke(question, kind="view", files=[os.path.abspath(path)], schema=schema, model=model,
                  cwd=os.path.dirname(os.path.abspath(path)), timeout_s=300)
    if not res.get("ok"):
        raise AgyImageError(f"agy 받아 적기 실패({res.get('code')}): {str(res.get('message') or '')[:200]}")
    lines = parse_lines(res.get("json"))
    if not with_clip:
        return lines
    got = res.get("json")
    if isinstance(got, str):
        try:
            got = json.loads(got.strip().strip("`").removeprefix("json").strip())
        except ValueError:
            got = {}
    clipped = [str(x) for x in ((got or {}).get("clipped") or []) if str(x).strip()] if isinstance(got, dict) else []
    return lines, clipped


def parse_lines(got):
    """agy 받아 적기 답 → 줄 목록. 모양만 푼다(글자는 고치지 않는다)."""
    # ★agy 가 구조화 답을 **JSON 글자열**로 줄 때가 있다(10-08 실측 — 같은 질문이 한 번은 묶음, 한 번은 글자열).
    #   글자열이면 풀어 읽는다. 풀리지 않으면 받아 적기 실패로 올린다(맞다고 치지 않는다).
    if isinstance(got, str):
        g = got.strip()
        if g.startswith("```"):                                     # 코드 울타리만 벗긴다(아래 줄 묶음과 같은 이유)
            g = g.strip("`").strip()
            g = g[4:].strip() if g.lower().startswith("json") else g
        try:
            got = json.loads(g)
        except ValueError:
            raise AgyImageError("agy 받아 적기 답을 읽지 못했습니다.") from None
    lines = (got or {}).get("lines") if isinstance(got, dict) else None
    if not isinstance(lines, list):
        raise AgyImageError("agy 받아 적기 답에 lines 가 없습니다.")
    # ★답 묶음 안에 JSON 글자가 **통째로 또는 줄마다 쪼개져** 들어올 때가 있다(10-08 실측: lines = ['{', '  "lines": [', …]).
    #   이어 붙여 JSON 으로 풀리면 그 안의 lines 를 쓴다 — 글자 내용은 고치지 않는다(모양만 푼다).
    joined = "\n".join(str(x) for x in lines).strip()
    # ★코드 울타리(```json … ```)로 감싼 JSON 도 같은 답이다(10-08 실측: 글자 없는 사진의 답이 «```json {"lines": []} ```» 한 줄로
    #   와서 «사진에 글자가 있다» 로 잘못 읽었다). 울타리만 벗긴다.
    if joined.startswith("```"):
        joined = joined.strip("`").strip()
        if joined.lower().startswith("json"):
            joined = joined[4:].strip()
    if joined.startswith("{"):
        try:
            inner = json.loads(joined)
            if isinstance(inner, dict) and isinstance(inner.get("lines"), list):
                lines = inner["lines"]
        except ValueError:
            pass
    return [str(x) for x in lines]


def _norm(t):
    """견줄 때 빼는 것은 **빈칸·줄 바꿈뿐**이다. 같은 기호의 다른 모양(… ↔ ..., “” ↔ \", ‘’ ↔ ')만 하나로 맞춘다.

    ★10-08 실측: 지시문이 글자를 «» 로 감쌌더니 그림 모델이 «» 까지 그렸고(@anavocado12345 3번 카드), 첫 판 대조는 «» 를
      빼고 견줘서 그것을 «일치» 로 넘겼다(독립 검증의 받아 적기는 << >> 로 읽어 잡았다). 기호도 글자다 — 빼지 않는다."""
    s = str(t or "").replace("…", "...").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", "", s)


def text_matches(expected, seen):
    """기대 문구가 받아 적은 글자에 **그대로**(빈칸·줄 바꿈 무시) 들어 있고, 받아 적은 글자에 기대 밖 글자가 없는가."""
    exp = _norm("".join(expected))
    got = _norm("".join(seen))
    # ★기대 문구 자체에 이스케이프 흔적(역슬래시)·제어 문자가 있으면 실패 — 같은 오류끼리 맞춰 «맞다» 고 하지 않는다
    #   (10-08 실측 @anavocado12345: 기대 문구에도 «\n» 글자가 있어 카드에 찍힌 «\n» 과 맞았다).
    bad = any("\\" in str(e) or "₩n" in str(e) or any(ord(ch) < 32 and ch != "\n" for ch in str(e)) for e in expected)
    #   받아 적은 글자에 «\n»·«₩n» 흔적이 보이면(카드에 찍혔다) 기대와 상관없이 실패
    bad = bad or "\\n" in got or "₩n" in got
    return (exp == got) and not bad, {"expected": exp, "seen": got}


def fit_card(src, out, width, height):
    """만든 그림을 카드 크기로 — 비율이 다르면 가운데를 잘라 맞춘다(cover). 같은 비율이면 크기만."""
    im = Image.open(src).convert("RGB")
    k = max(width / im.width, height / im.height)
    im = im.resize((max(width, round(im.width * k)), max(height, round(im.height * k))), Image.LANCZOS)
    x = (im.width - width) // 2
    y = (im.height - height) // 2
    im.crop((x, y, x + width, y + height)).save(out)
    return out


def design_score(ref_path, card_path, question, schema, model, workdir):
    """레퍼런스와 우리 카드를 나란히 붙여 agy 가 디자인 닮음 점수(0~10)를 매긴다(질문·답 모양은 서버)."""
    a = Image.open(ref_path).convert("RGB")
    b = Image.open(card_path).convert("RGB")
    h = 1200
    a = a.resize((round(a.width * h / a.height), h), Image.LANCZOS)
    b = b.resize((round(b.width * h / b.height), h), Image.LANCZOS)
    pair = Image.new("RGB", (a.width + b.width + 24, h), (255, 255, 255))
    pair.paste(a, (0, 0))
    pair.paste(b, (a.width + 24, 0))
    path = os.path.join(workdir, "pair_" + os.path.basename(card_path).rsplit(".", 1)[0] + ".jpg")
    pair.save(path, quality=92)
    res = _invoke(question, kind="view", files=[path], schema=schema, model=model, cwd=workdir, timeout_s=300)
    if not res.get("ok"):
        raise AgyImageError(f"agy 비교 실패({res.get('code')}): {str(res.get('message') or '')[:200]}")
    got = res.get("json")
    if isinstance(got, str):
        got = json.loads(got)
    return got


def _code_card(job, model, workdir, ref, render_fallback, notes):
    """잰 배치를 코드로 — 사진(그림)만 agy 가 레퍼런스 느낌으로 그린다(단색 바탕이면 사진 없이)."""
    idx = int(job["index"])
    photo = None
    if job.get("promptScene"):
        # ★사진이 안 나오면(agy 가 그림을 저장하지 않음) 그 카드는 사진 없이 색면 바탕 — 한 벌 전체를 죽이지 않는다
        #   (10-08 실측 @whynotmag_: 코드 길 사진 한 장이 안 나와 계정 전체가 멈췄다). 거부(RunServiceRefused)는 잡지 않는다(6-2).
        try:
            photo = generate(ref, job["promptScene"], job["aspect"], f"scene_{idx:02d}",
                             os.path.join(workdir, f"scene_{idx:02d}.png"), model, workdir)
        except AgyImageError as e:
            notes.append(f"{idx}번 카드: 사진이 안 나와({str(e)[:60]}) 사진 없이 색면 바탕으로 그립니다.")
            render_fallback(job, None).save(job["out"])
            return {"index": idx, "path": job["out"], "how": "code", "seen": None, "notes": notes}
        # ★사진에도 글자가 없어야 한다 — 받아 적어 보고, 글자가 있으면 그 사진은 쓰지 않는다(바탕은 딥톤 색면 갈래).
        #   다시 그리지 않는다(같은 지시로 또 그리면 또 그릴 수 있고, 그 판단은 사람 몫이다 — 사유를 남긴다).
        seen = read_text(photo, job["readQuestion"], model)
        if any(str(x).strip() for x in seen):
            notes.append(f"{idx}번 카드: agy 가 그린 사진에 글자가 보여({' '.join(seen)[:40]}) 사진 없이 색면 바탕으로 그립니다.")
            photo = None
    render_fallback(job, photo).save(job["out"])
    return {"index": idx, "path": job["out"], "how": "code", "seen": None, "notes": notes}


def _agy_card(job, model, workdir, ref):
    """agy 가 글자까지 그린 카드 + 받아 적기 대조. 돌려주는 것: (맞음?, 원본 경로, 읽힌 줄, 비교)."""
    idx = int(job["index"])
    raw = generate(ref, job["prompt"], job["aspect"], f"card_{idx:02d}", os.path.join(workdir, f"agy_{idx:02d}.png"),
                   model, workdir)
    # ★받아 적기는 **카드 크기로 자른 뒤**의 그림으로 한다 — 그림 도구 비율(3:4)을 카드(4:5)로 자르면 위아래 끝 글자가 잘릴 수 있는데,
    #   자르기 전 그림을 읽으면 잘린 카드를 «맞다» 로 넘긴다(10-08 실측 @unni_secret_note 3번 카드 맨 아래 줄).
    fitted = os.path.join(workdir, f"agy_{idx:02d}_fit.png")
    fit_card(raw, fitted, job["width"], job["height"])
    raw = fitted
    q = job.get("readCardQuestion")
    if q:
        seen, clipped = read_text(raw, q, model, with_clip=True)
    else:
        seen, clipped = read_text(raw, job["readQuestion"], model), []
    ok, cmp_ = text_matches(job["expect"], seen)
    if clipped:
        # 글자가 카드 끝에서 잘렸으면 맞아도 쓰지 않는다(코드 길로 — 잰 자리에 글자를 얹는다)
        ok = False
        cmp_ = dict(cmp_, seen="(가장자리에서 잘림: " + " / ".join(clipped)[:40] + ") " + cmp_["seen"])
    return ok, raw, seen, cmp_


def make_cards(agy, ref, workdir, render_fallback, say=None):
    """한 벌 — 표지를 **두 길로** 만들어 같은 자(agy 나란히 비교)로 재고 더 닮은 길로 한 벌을 간다.

    ① agy 길: agy 가 레퍼런스를 참조로 글자까지 그린다 → 받아 적기 대조(틀리면 이 길은 탈락)
    ② 코드 길: 잰 배치를 코드로 그리고 사진만 agy 가 레퍼런스 느낌으로(사진에 글자가 보이면 사진 없이)
    ③ 레퍼런스 그림이 있으면 두 표지를 각각 레퍼런스와 나란히 놓고 agy 디자인 점수 → 높은 길(같으면 agy 길).
       레퍼런스 그림이 없으면 글자가 맞는 agy 길. (점수는 검증 표에 남긴다 — minDesign 아래면 그 사실을 알린다.)
    ④ 나머지 카드는 고른 길로(agy 길이면 카드마다 글자 대조 — 틀린 카드만 코드 길). 한 벌 안에서 길이 섞이는 것은 그때뿐이다.

    ★10-08 실측: 같은 표지라도 길마다 잘 맞는 계정이 다르다(@whynotmag_ agy 길 8 · 코드 길 10 / @ho1y_time agy 길 손글씨를
      둥근고딕으로 그림). 한 길만 믿지 않고 같은 자로 재서 고른다.
    agy = images 응답의 agyImage 묶음(지시문·질문·모델·문턱·동시 수는 전부 서버).
    render_fallback(job, 사진경로|None) → PIL 그림. 돌려주는 것: {"cards": [...], "cover": 판정}."""
    from concurrent.futures import ThreadPoolExecutor              # noqa: PLC0415
    os.makedirs(workdir, exist_ok=True)
    set_pacing(agy.get("pacing"))
    model = agy["model"]
    jobs = sorted(agy["jobs"], key=lambda j: int(j["index"]))
    par = max(1, int(agy.get("parallel") or 1))
    log = say or (lambda m: None)
    cover = jobs[0]
    agy_out = cover["out"].rsplit(".", 1)[0] + "_agy.png"
    code_out = cover["out"].rsplit(".", 1)[0] + "_code.png"

    def agy_path_cover():
        # agy 그림이 안 나오면(AgyImageError) 그 길만 탈락 — 거부(RunServiceRefused)는 잡지 않고 올린다(전부 멈춤 · 6-2)
        try:
            ok, raw, seen, cmp_ = _agy_card(cover, model, workdir, ref)
        except AgyImageError as e:
            return False, [], {"seen": f"(agy 그림 실패: {e})"[:60], "expected": ""}
        if ok:
            fit_card(raw, agy_out, cover["width"], cover["height"])
        return ok, seen, cmp_

    def code_path_cover():
        return _code_card(dict(cover, out=code_out), model, workdir, ref, render_fallback, [])
    route = load_route(ref, agy["simQuestion"]) if ref else None
    if route:
        # ★이 레퍼런스는 전에 두 길을 견줬다 — 이긴 길만 그린다(그림 한도 아끼기 · 쇼츠대폭발 10-08). agy 길인데 글자가 틀리면
        #   그 표지만 코드 길로 간다(오탈자 0 이 먼저).
        verdict = {"route": "remembered", "score": route.get("score"), "codeScore": route.get("codeScore")}
        a_ok, a_seen, a_cmp, code_res = False, [], {"seen": "", "expected": ""}, None
        if route["engine"] == "agy":
            a_ok, a_seen, a_cmp = agy_path_cover()
        if not a_ok:
            code_res = code_path_cover()
        verdict.update(text_ok=a_ok, seen=a_seen)
        use_agy = a_ok
        log(f"표지: 전에 견준 결과대로 {route['engine']} 길만 그립니다(agy {route.get('score')} · 코드 {route.get('codeScore')})")
    else:
        with ThreadPoolExecutor(2) as ex:
            fa, fc = ex.submit(agy_path_cover), ex.submit(code_path_cover)
            (a_ok, a_seen, a_cmp), code_res = fa.result(), fc.result()
        verdict = {"text_ok": a_ok, "seen": a_seen}
        if ref:
            def score(path):
                sc = design_score(ref, path, agy["simQuestion"], agy["simSchema"], model, workdir)
                return sc.get("overall") if isinstance(sc.get("overall"), (int, float)) else -1, sc
            with ThreadPoolExecutor(2) as ex:
                fs_a = ex.submit(score, agy_out) if a_ok else None
                fs_c = ex.submit(score, code_out)
                sa, sca = fs_a.result() if fs_a else (-1, None)
                sc_, scc = fs_c.result()
            verdict.update(score=sa, scores=sca, codeScore=sc_, codeScores=scc)
            # 같은 자로 잰 두 점수 중 높은 길(같으면 agy 길). ★문턱(minDesign)으로 agy 길을 먼저 떨어뜨리면 더 나쁜 코드 길이
            #   뽑힐 수 있다(10-08 실측 @hottopic_lab agy 8 · 코드 6 인데 코드 길을 골랐다) — 비교만으로 고른다.
            use_agy = a_ok and sa >= sc_
        else:
            use_agy = a_ok
    verdict["engine"] = "agy" if use_agy else "code"
    if ref and not route and (verdict.get("score") is not None):
        save_route(ref, agy["simQuestion"], verdict)
    best = max(verdict.get("score") or -1, verdict.get("codeScore") or -1)
    if ref and not route and best < float(agy.get("minDesign") or 0):
        log(f"★표지 디자인 점수가 두 길 모두 기준({agy.get('minDesign')}) 아래입니다(최고 {best}) — 이 레퍼런스는 잘 옮겨지지 않습니다.")
        verdict["belowMin"] = True
    out = []
    if use_agy:
        os.replace(agy_out, cover["out"])
        log(f"표지: agy 길(글자 일치 · 디자인 {verdict.get('score')} · 코드 길 {verdict.get('codeScore')})")
        out.append({"index": cover["index"], "path": cover["out"], "how": "agy", "seen": a_seen, "notes": []})

        def rest(job):
            try:
                ok2, raw2, seen2, cmp2 = _agy_card(job, model, workdir, ref)
            except AgyImageError as e:
                return _code_card(job, model, workdir, ref, render_fallback,
                                  [f"{job['index']}번 카드: agy 그림이 안 나와({str(e)[:60]}) 잰 배치를 코드로 그립니다."])
            if ok2:
                fit_card(raw2, job["out"], job["width"], job["height"])
                return {"index": job["index"], "path": job["out"], "how": "agy", "seen": seen2, "notes": []}
            note = (f"{job['index']}번 카드: 그림 속 글자가 기대와 달라(읽힘 «{cmp2['seen'][:40]}» · 기대 «{cmp2['expected'][:40]}») "
                    "잰 배치를 코드로 그립니다.")
            return _code_card(job, model, workdir, ref, render_fallback, [note])
        with ThreadPoolExecutor(par) as ex:
            out += list(ex.map(rest, jobs[1:]))
    else:
        os.replace(code_out, cover["out"])
        why = ("agy 길 글자가 기대와 다름 «" + a_cmp["seen"][:40] + "»" if not a_ok
               else f"디자인 agy 길 {verdict.get('score')} · 코드 길 {verdict.get('codeScore')}")
        log(f"표지: 코드 길({why}) — 이 한 벌은 잰 배치를 코드로 그립니다(사진만 agy).")
        out.append(dict(code_res, path=cover["out"]))
        with ThreadPoolExecutor(par) as ex:
            out += list(ex.map(lambda j: _code_card(j, model, workdir, ref, render_fallback, []), jobs[1:]))
    for p_ in (agy_out, code_out):
        if os.path.exists(p_):
            os.remove(p_)
    out.sort(key=lambda r: int(r["index"]))
    verdict["cache"] = dict(CACHE_STATS)
    return {"cards": out, "cover": verdict}
