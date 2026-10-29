# -*- coding: utf-8 -*-
"""볼케이노 구동기 — 서버가 시키는 순서를 **그대로 따라가는 루프**.

■ 왜 이 파일이 필요한가
    `volcano_run.py` 는 "받은 것을 실행하는 함수 모음"이고, 그것을 **순서대로 부르는
    코드**는 없었다. 그러면 수강생마다 Claude Code 가 매번 새로 짜게 되고,
    그 순간 결과가 갈린다 — 실행기를 배급한 이유가 사라진다.

■ 이 파일에도 채널 규격이 없다. 일부러 없다.
    여기 있는 건 **응답의 문법**뿐이다:
      do[].cmd/argv     실행하라
      do[].fetch_asset  받아서 sha 확인하고 풀어라
      jobs + retry      TTS/이미지 요청을 던지고 후처리 단계를 돌려라
      *_ass / *_txt     {path, content} 를 그 경로에 그대로 써라
      argv              실행하라
      verify            실행해서 expect 와 같은지 보라
      measure           **무엇을 재서 어느 payload 칸에 넣을지** (서버가 데이터로 준다)
      next_step         다음은 이것
    무엇을 만들지·어떤 값인지는 하나도 모른다.

■ 사람(모델)이 해야 하는 자리에서는 멈춘다
    status="need_input" 이면 대본·제목 같은 창작이 필요하다는 뜻이다. 구동기는 거기서
    멈추고 무엇이 필요한지 알려준다. 그것까지 자동으로 지어내면 채널이 아니게 된다.

    ★기계 일을 **하고 나서** 멈춰야 하는 자리도 있다 — 이미지를 다 굽고 나서 컷마다
      감정을 골라야 하고, 컷 조각을 다 굽고 나서 프레임을 보고 적어야 한다.
      그런 자리는 status 가 "execute" 라 예전 구동기는 그대로 다음 단계로 넘어가
      **거기서 죽었다.** 지금은 서버가 `author` 로 알려준다:
          author = {"for": 다음단계, "keys": [없는 값…], "why": 왜 사람이 만들어야 하나}
      구동기는 jobs 를 **먼저 다 하고** 그 다음에 멈춘다(한 일을 버리지 않는다).

■ ★★**"볼케이노 토큰" 을 사람에게 묻지 마라** (2026-08-17, 실물 여러 명이 여기서 멈췄다)
    이 루프(`drive`)는 서버를 직접 부르므로 Bearer 토큰이 필요하다. 그런데 **정상
    경로에는 토큰이 필요 없다** — Claude Code 가 MCP 도구 `volcano_video` 를 부를 때
    인증은 이미 되어 있고, 자산 URL 에는 열쇠가 **URL 안에** 들어 있다(`?k=…`).
    토큰이 없으면 이 루프를 쓰지 말고 `volcano_run` 의 **함수만** 가져다 써라
    (`README.md` 의 '정상 경로'). 수강생에게 토큰을 요구하면 그 사람은 **없는 것을
    찾다가 막힌다.** 이 독스트링의 옛 예제가 정확히 그 오해를 만들었다.
    토큰이 이미 있는 사람만 아래처럼 쓴다(받는 곳: `<서버>/login` — 본인이 직접).

    쓰는 법: (★토큰을 **이미 손에 든 사람만**. 없으면 위의 정상 경로로 하라)
        from volcano_run import Client
        from volcano_drive import drive
        c = Client(URL, MY_TOKEN, preset="어랍숏")
        state = drive(c, "start",
                      source={"kind": "youtube", "url": "https://youtu.be/…"},
                      headers={"X-API-KEY": MY_KEY})

    ★★`source` 는 **키워드로** 준다. 세 번째 **위치**인자는 `payload` 다 —
      `drive(c, "start", {"source": {...}})` 라고 쓰면 소재가 payload 안으로 들어가고
      `Client.step` 은 그것을 최상위 `source` 로 올려주지 않는다. 서버는 소재를 못 보고
      `source.kind 는 [...] 중 하나여야 합니다` 로 반려한다.
      **이 독스트링이 실제로 그 틀린 호출을 가르치고 있었다**(2026-08-16 발견) —
      바로 옆 `README.md` 는 `source=` 로 올바르게 적혀 있어서 두 배급물이 어긋났고,
      틀린 쪽이 모델이 import 하는 모듈 안에 있었다. `start` 반려 9건/5명 중
      실행기 3건이 이 경로였다.
      (지금은 서버가 payload 안의 소재도 되살려 주지만, **그건 구제책이고 규격이
       아니다** — 서버가 "다음부터는 최상위로 보내라" 고 말한다.)

■ ★★**어느 도구를 모는가** — `volcano_video` 만이 아니다 (2026-09-04)
    `Client.step` 이 JSON-RPC 본문에 도구 이름 `"volcano_video"` 를 **박아** 보내고
    있었다. 그래서 이 팩에 조교 계측 손(`ref_*`) 20개가 들어 있는데도 `volcano_ref`
    체인을 **시킬 문이 없었고**, 그 15단계는 사람이 손으로 이어 부르는 길 하나뿐이었다.
        python volcano_drive.py --workdir <폴더> --tool volcano_ref --key-file <출입증>
    ★기본값은 그대로 `volcano_video` 다 — 안 주면 예전 요청과 **바이트가 같다**.
    ★★그런데 이 루프는 payload 를 **누적한다**(`payload.update(...)`). 곁 도구는 계약이
      `then_call_with` **하나**인데 여기서는 앞 단계의 값이 그대로 남아 다음 단계에
      실려 간다 — 즉 **서버가 `then_call_with` 에 안 실은 칸도 이 경로에서는 우연히
      채워져 보인다.** 사람이 손으로 이어 부르면 그 자리에서 반려된다.
      **계약 결손은 서버에서 고쳐야 하고, 이 루프로 「돌더라」를 근거 삼으면 안 된다.**
"""

import contextlib
import copy
import hashlib
import json
import os
import sys
import time
import shutil
import subprocess
import tarfile
import traceback
import tempfile
import stat
import unicodedata

# ★실행기 곁 모듈(volcano_run·runner_files·runtime_metrics …)은 **이 파일과 같은 폴더**의 것만 쓴다(2026-10-23).
#   파이썬은 보통 스크립트 폴더를 sys.path 맨 앞에 넣지만, 격리 모드(-I·-P · 윈도우 임베디드 파이썬의 ._pth — 공식 문서
#   «When the file exists … isolated mode is enabled»)에서는 넣지 않는다. 그러면 곁 모듈을 sys.path 의 다른 실행기 폴더에서
#   읽어, 새 판으로 다시 뜬 실행기가 옛 폴더의 식별값을 알리고 서버가 같은 갱신을 또 요구해 멈췄다(신고 10-14·10-18·10-20·10-23:
#   두 번째 요청의 from 이 설치한 판이 아니었다 — 같은 대상 판 · 같은 Worker 판). 한 팩의 파일을 섞어 도는 경우는 없다.
_HERE = os.path.dirname(os.path.abspath(__file__))
if not sys.path or os.path.normcase(os.path.abspath(sys.path[0] or os.curdir)) != os.path.normcase(_HERE):
    sys.path.insert(0, _HERE)
import runtime_metrics  # noqa: E402

from volcano_run import disk_full_note as _vr_disk_full_note  # noqa: E402
from volcano_run import (TEXT_PIPE, Client, RejectedError, _have,  # noqa: F401
                         _progress, _spawn, _is_ytdlp, _photo_write_state, _service_key_value,
                         StepError, StepBack, ProviderRefusalError, TranscriptionPending, ASRSetupRequired, CustomMediaChanged, ClientReviewPending, ClientReviewInputError, ask_text, ask_video, bake_frames,
                         download, download_seen, asset_mismatch_facts, err_gist, failure_text, fetch_font, fold_payload, unfold_payload, hardsub_probe, missing_inputs,
                         # ★쇼핑 측정단위(lufs·seconds_by_frames)가 쓴다 — 병합(08-23)
                         #   때 놓치면 호출 때만 죽는다(컴파일이 못 잡는다 · AST 로 잡았다).
                         frame_seconds, lufs_of,
                         scene_cuts,
                         fetch_images,
                         image_qc,
                         generate_images, http_headers, is_drawn, check_photo, measure_audio,
                         cut_signature, cut_signatures,
                         search_images, search_videos, recover_photos,
                         fact_check,
                         measure_frame,
                         # 조교 채널 계측 — 손 (2026-09-03 · volcano_ref)
                         ref_probe,
                         # ★그림 크기·피사체 중심 — 정의는 예전부터 있었는데
                         #   **부르는 곳이 0곳**이었다 (2026-08-26 배선).
                         image_facts,
                         measure_sfx,
                         measure_lufs, measure_lufs_spread,
                         measure_loudnorm, measure_peak, rise_edges, run_argv, source_mp4,
                         run_argv_pool, run_vmake_job, synthesize,
                         # ★군림보 마스터 오디오(2026-08-24) — 침대·드라이브·고역·
                         #   오프닝 목소리. 값·문턱은 전부 서버 params 로 온다.
                         master_drive, measure_hf, measure_openvoice,
                         render_sfx_bed,
                         # ★군림보 소리 뒷단(2026-08-25 · 끝판 검증이 잡은 구멍) —
                         #   조각 파생 사본(shape/lvl). 표·문턱 전부 서버 params.
                         piece_shape,
                         # ★군림보 그림 축(2026-08-25) — 색인 프로브·일러 놓기.
                         #   경로·실측값 전부 서버 params 로 온다(러너에 채널 값 0).
                         iras_probe, place_illust, probe_custom_media, prepare_custom_media, verify_custom_media,
                         transcribe_words, wav_seconds)


def _write(spec, what):
    """{path, content} 를 그대로 쓴다. 서버가 만든 본문을 **한 글자도 고치지 않는다.**

    ★`encoding: "base64"` 면 **바이트 파일**이다(프리미어 `.prproj` 은 gzip 이다).
      어떻게 쓸지는 **서버가 선언한다** — 실행기가 확장자를 보고 추측하면
      한쪽만 바뀌었을 때 조용히 깨진다.

    ★★**텍스트 모드로 열지 않는다** (2026-08-12, 윈도우 실물이 잡았다).
      `open(p, "w")` 는 플랫폼마다 줄바꿈을 바꾼다 — 윈도우가 `\\n` 을 `\\r\\n` 으로
      쓰면 서버가 준 본문과 **바이트가 달라지고** 바로 다음 줄의 sha256 대조가
      반드시 깨진다 — 자막 파일은 **줄 수만큼** 바이트가 늘어난다.
      윈도우 수강생의 뇌전구가 **여기서 전부 멈췄다.**
      ★수치를 여기 적지 마라. 이 파일은 수강생에게 배급되므로, 명세 값과 우연히
        겹치는 숫자 하나가 검사 [20](명세 잎값 유출)에 걸린다 — 실제로 걸렸다.
      `newline=""` 를 붙이면 고쳐지지만 그건 **누가 지워도 아무도 모르는 플래그**다.
      그래서 아예 **바이트로 쓴다** — 인코딩 지점을 한 곳으로 모으면 플랫폼이
      끼어들 자리가 없어진다. 두 갈래가 같은 `"wb"` 를 쓰는 것도 그 이유다.
    """
    if spec.get('cmd') == 'write_focus_receipt':
        from focus_receipt import write_focus_receipt
        result=write_focus_receipt(spec)
        _progress(f"  [{what}] {result['path']} ({result['bytes']}B, focus receipt)")
        return
    p = spec["path"]
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    if spec.get("encoding") == "base64":
        import base64                                             # noqa: PLC0415
        raw, kind = base64.b64decode(spec["content"]), "이진"
    elif spec.get("encoding") == "deflate64":
        # ★deflate64 = zlib 압축본의 base64 (2026-08-25 — 큰 기록 파일의 전송량).
        #   sha256 은 **디스크에 앉는(압축 푼) 바이트**의 것이다 — 이 갈래를 모르는
        #   옛 실행기는 base64 글을 그대로 파일로 써서 바로 아래 sha 대조가 **크게**
        #   멈춘다(깨진 기록이 조용히 남지 않는다).
        import base64                                             # noqa: PLC0415
        import zlib                                               # noqa: PLC0415
        raw, kind = zlib.decompress(base64.b64decode(spec["content"])), "deflate64"
    else:
        raw, kind = spec["content"].encode("utf-8"), "utf-8"
    with open(p, "wb") as fh:
        fh.write(raw)
    _progress(f"  [{what}] {p} ({len(raw)}B, {kind})")


def _pack_members(t):
    """배급 팩 계약: 일반 파일/폴더만. 구형 Python에서도 같은 경계를 지킨다."""
    names, prefixes, members = {}, {}, t.getmembers()
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update("%s%d" % (prefix, n) for prefix in ("COM", "LPT") for n in range(1, 10))
    for member in members:
        name = member.name
        parts = [p for p in name.split("/") if p not in ("", ".")]
        if (not (member.isfile() or member.isdir()) or name.startswith("/")
                or "\\" in name or any(p == ".." for p in parts)
                or any(":" in p or p.endswith((".", " ")) or any(ord(c) < 32 for c in p)
                       or p.split(".", 1)[0].upper() in reserved for p in parts)
                or (not parts and not member.isdir())):
            raise StepError("안전하지 않은 자산 항목: %r" % name)
        canonical = unicodedata.normalize("NFC", "/".join(parts)).casefold()
        for end in range(1, len(parts) + 1):
            spelling = "/".join(parts[:end])
            key = unicodedata.normalize("NFC", spelling).casefold()
            if key in prefixes and prefixes[key] != spelling:
                raise StepError("대소문자/정규화 폴더 이름이 충돌하는 자산 항목: %r" % name)
            prefixes[key] = spelling
        if canonical in names and not (member.isdir() and names[canonical] == (name, True)):
            raise StepError("대소문자/정규화/중복 이름이 충돌하는 자산 항목: %r" % name)
        names[canonical] = (name, member.isdir())
    return members


def _pack_junction(path):
    return (getattr(os.lstat(path), "st_reparse_tag", 0)
            == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1))


def _pack_link(path):
    return os.path.islink(path) or _pack_junction(path)


def _pack_copy_tree(source, target, active=None):
    """기존 공용 자산의 스냅샷. 링크 referent를 바꾸거나 따라 쓰지 않는다."""
    active = set() if active is None else active
    real = os.path.normcase(os.path.realpath(source))
    if real in active:
        raise StepError("공용 자산의 junction/디렉터리가 순환합니다: " + source)
    active.add(real)
    try:
        os.mkdir(target)
        with os.scandir(source) as entries:
            for item in entries:
                src, dst = item.path, os.path.join(target, item.name)
                if item.is_symlink():
                    link = os.readlink(src)
                    if not os.path.isabs(link):
                        link = os.path.join(os.path.realpath(os.path.dirname(src)), link)
                    attrs = getattr(item.stat(follow_symlinks=False), "st_file_attributes", 0)
                    is_dir = bool(attrs & getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0))
                    os.symlink(link, dst, target_is_directory=is_dir)
                elif _pack_junction(src) or item.is_dir(follow_symlinks=False):
                    _pack_copy_tree(src, dst, active)
                elif item.is_file(follow_symlinks=False):
                    shutil.copy2(src, dst)
                else:
                    raise StepError("공용 자산의 특수 파일을 보존할 수 없습니다: " + src)
    finally:
        active.remove(real)


# ★같은 작업 폴더에 팩 여러 개를 **동시에** 푼다(서버 `fetch_parallel`). 두 스레드가 같은 공용 연결을
#   동시에 떼면 한쪽이 다른 쪽의 복사본을 옮겨 버린다 — 떼기는 한 번에 하나, 잠금 안에서 다시 확인한다.
#   실행기 설치기의 공용 연결 COW(`install_runner_files`)도 같은 잠금을 잡는다. 그 안에서 복사본의 하위 연결을
#   `extract_pack` 이 다시 떼므로(같은 스레드) 재진입 가능해야 한다 — 보통 Lock 이면 영원히 멈춘다(검사 실측).
import threading as _threading                                   # noqa: E402


#: 윈도우 App Execution Alias 의 재분석 태그(IO_REPARSE_TAG_APPEXECLINK · winnt.h) · 조회 코드(FSCTL_GET_REPARSE_POINT).
_APPEXECLINK_TAG = 0x8000001B
_FSCTL_GET_REPARSE_POINT = 0x000900A8
#: 파이썬이 안 깔린 윈도우에서 `python.exe`·`python3.exe` 별칭이 가리키는 «스토어에서 설치하라» 안내 프로그램.
#: 돌리면 "Python was not found; run without arguments to install from the Microsoft Store" 만 찍고 끝난다.
_STORE_STUB_TARGET = "appinstallerpythonredirector.exe"


def _spawn_failed(e):
    """파이썬 후보를 돌리다 난 예외 한 줄 — «무엇이» 를 남긴다(2026-10-20 정치롱 윈도우 신고).
    str(TimeoutExpired) 는 argv(측정 글 전체)로 시작해 앞 60자로 자르면 «Command '['C:\\…» 만 남고 시간 초과라는 사실이 잘렸다."""
    if isinstance(e, subprocess.TimeoutExpired):
        return f"TimeoutExpired: {e.timeout}초 안에 끝나지 않음"
    return f"{type(e).__name__}: {e}"[:120]


def _windows_store_python_stub(path):
    """`path` 가 윈도우 «스토어 설치 안내» 파이썬 별칭(App Execution Alias)인가 — **실행하지 않고** 별칭이 가리키는
    대상을 읽어 판정한다(uv 의 is_windows_store_shim 과 같은 방법).

    ★크기·폴더(WindowsApps)만 보면 안 된다 — 스토어에서 **정말 설치한** 파이썬도 같은 폴더의 0바이트 별칭이다.
      가르는 것은 별칭의 대상이 AppInstallerPythonRedirector.exe 인가 하나다.
    맥·리눅스는 늘 False. 읽지 못하면 False(지금까지처럼 존재로 판정 — 막지 않는다)."""
    if os.name != "nt" or not path:
        return False
    import ctypes
    try:
        if not getattr(os.lstat(path), "st_reparse_tag", 0) == _APPEXECLINK_TAG:
            return False
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        k32.DeviceIoControl.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        FILE_FLAG_OPEN_REPARSE_POINT, FILE_FLAG_BACKUP_SEMANTICS, OPEN_EXISTING = 0x00200000, 0x02000000, 3
        h = k32.CreateFileW(str(path), 0, 0x7, None, OPEN_EXISTING,
                            FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, None)
        if h in (None, wintypes.HANDLE(-1).value):
            return False
        try:
            buf = ctypes.create_string_buffer(16 * 1024)          # MAXIMUM_REPARSE_DATA_BUFFER_SIZE
            got = wintypes.DWORD(0)
            if not k32.DeviceIoControl(h, _FSCTL_GET_REPARSE_POINT, None, 0, buf, len(buf), ctypes.byref(got), None):
                return False
            raw = buf.raw[:got.value]
        finally:
            k32.CloseHandle(h)
        return _appexeclink_is_store_stub(raw)
    except (OSError, AttributeError, ValueError, TypeError, ctypes.ArgumentError):
        return False


def _appexeclink_is_store_stub(raw):
    """REPARSE_DATA_BUFFER(태그 4 · 길이 2 · 예약 2 · 판 4 · 넓은 문자열들) → 대상이 스토어 안내 프로그램인가."""
    if len(raw) < 12 or int.from_bytes(raw[:4], "little") != _APPEXECLINK_TAG:
        return False
    parts = raw[12:].decode("utf-16-le", "replace").split("\0")
    return any(p.strip().lower().endswith(_STORE_STUB_TARGET) for p in parts)
_PACK_DETACH_LOCK = _threading.RLock()


def _pack_detach(path):
    """공용 디렉터리는 복사 후 연결만 교체한다. 교체 실패 시 원래 연결 복구.

    ★**설치 대상(작업 폴더) 자신이나 그 위 폴더에는 부르지 않는다** (2026-10-05 · 누락 점검 M8).
      학생들이 긴 한글 경로를 피하려고 작업 폴더 자체를 짧은 정션·심링크(`C:\\vw\\…`·`D:\\vxw\\…`·맥 `~/c/…`)로
      가리킨다. 예전 `extract_pack` 은 대상 자신이 링크면 이 함수로 **작업 폴더 통째**를 복사·교체하려 했고
      5일 13건이 멈췄다 — 긴 경로(WinError 206) · 병렬로 받는 다른 팩이 쓰는 중인 파일(WinError 3) ·
      실행기·cwd 가 열려 있는 폴더 교체(WinError 5) · 맥 FileNotFound. 이 함수는 대상 **안의** 공용 연결
      (runner/·fonts/·sfx_norm/ 따위)만 맡는다. 그 판정은 부르는 쪽(`extract_pack.local_dir`)이 한다.
    """
    with _PACK_DETACH_LOCK:
        # 다른 스레드가 방금 떼었으면 이미 일반 폴더다 — 다시 떼지 않는다.
        if not (os.path.lexists(path) and _pack_link(path)):
            return
        _pack_detach_locked(path)


def _pack_detach_locked(path):
    parent = os.path.dirname(path)
    _progress("  [자산] 공용 연결을 작업용 폴더로 복사 중: " + os.path.basename(path))
    temp = tempfile.mkdtemp(prefix=".volcano-cow-", dir=parent)
    copied, backup = os.path.join(temp, "copy"), os.path.join(temp, "original")
    try:
        _pack_copy_tree(path, copied)
        os.replace(path, backup)
        try:
            os.replace(copied, path)
        except Exception:
            os.replace(backup, path)
            raise
        # junction은 unlink 대신 rmdir로 연결 자체만 지운다. 대상은 읽기만 했다.
        if _pack_junction(backup):
            os.rmdir(backup)
        else:
            os.unlink(backup)
    except Exception as error:
        if os.path.lexists(backup):
            # 복구 rename도 불가능하면 원래 연결과 복사본을 지우지 않고 위치를 알린다.
            raise StepError("자산 연결 복구/정리 실패; 원래 연결 보존: %s (%s)" % (backup, error)) from error
        raise StepError("공용 자산 복사/교체 실패; 공용 원본은 변경하지 않았습니다: %s" % error) from error
    finally:
        if not os.path.lexists(backup):
            shutil.rmtree(temp)


def _pack_same(source, target):
    if not os.path.isfile(target) or os.path.getsize(source) != os.path.getsize(target):
        return False
    with open(source, "rb") as first, open(target, "rb") as second:
        while True:
            block = first.read(1024 * 1024)
            if block != second.read(len(block)):
                return False
            if not block:
                return True


def extract_pack(t, dest):
    """깨끗한 임시폴더에 안전 해제 후, 동일 파일 재사용/변경 파일만 로컬 설치.

    기존 dest 안의 symlink/junction 때문에 data filter가 정상 팩도 거부했던
    문제를 푼다. 필터를 없애거나 공용 대상에 덮어쓰지 않는다. filter 없는
    Python 3.9.6도 일반 파일/상대 경로 사전 검사를 반드시 거친다.
    """
    members = _pack_members(t)
    base = os.path.abspath(dest)
    # ★다 쓴 임시 폴더를 지우다 실패해도(맥 exFAT 외장에 시스템이 «._*» 를 덧붙여 «Directory not empty» · 2026-10-17 인스타형
    #   예능 assets 1건) 이미 설치한 팩을 실패로 돌리지 않는다 — 남은 임시 폴더는 무해하다(3.10+ 의 공식 인자 · 3.9 는 그대로).
    with tempfile.TemporaryDirectory(prefix="volcano-pack-",
                                     **({"ignore_cleanup_errors": True} if sys.version_info >= (3, 10) else {})) as staging:
        if hasattr(tarfile, "data_filter"):
            t.extractall(staging, members=members, filter="data")
        else:
            # 3.9.6에는 data_filter가 없다. 검사된 일반 파일/폴더만 새 임시폴더로
            # 풀고 소유권·특수 권한을 적용하지 않는다. 폴더 탐색 권한도 보장한다.
            import copy                                          # noqa: PLC0415
            safe_members = []
            for member in members:
                safe = copy.copy(member)
                safe.uid = safe.gid = -1
                safe.uname = safe.gname = None
                safe.mode = 0o700 if safe.isdir() else (safe.mode & 0o755) | 0o600
                if safe.isfile() and not safe.mode & 0o100:
                    safe.mode &= ~0o111
                safe_members.append(safe)
            t.extractall(staging, members=safe_members)
        dirs, files = [], []
        for here, subdirs, names in os.walk(staging):
            relative = os.path.relpath(here, staging)
            target_dir = base if relative == "." else os.path.join(base, relative)
            dirs.append(target_dir)
            for name in names:
                files.append((os.path.join(here, name), os.path.join(target_dir, name)))
        # 종류 충돌은 기존 파일을 하나라도 바꾸기 전에 확인한다.
        for path in dirs:
            if os.path.lexists(path) and not os.path.isdir(path):
                raise StepError("자산 폴더 자리에 폴더가 아닌 항목이 있습니다: " + path)
        for _, path in files:
            if os.path.isdir(path):
                raise StepError("자산 파일 자리에 기존 폴더가 있습니다: " + path)

        def local_dir(path):
            if path != base:
                local_dir(os.path.dirname(path))
            elif not os.path.isdir(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path), exist_ok=True)
            # ★대상 자신(base)은 떼지 않는다 — 대상이 링크·정션이면 그것은 호출자가 고른 **작업 폴더 그 자체**다
            #   (짧은 경로 별칭). 그 안에 쓰는 것이 맞다(§_pack_detach 머리말 · M8). 떼는 것은 대상 **안**의 연결뿐.
            if path != base and os.path.lexists(path) and _pack_link(path):
                _pack_detach(path)
            else:
                os.makedirs(path, exist_ok=True)

        for path in dirs:
            if not os.path.isdir(path):
                local_dir(path)
        def under_inner_link(path):
            # 대상 안의 공용 연결 아래인가 — 그 자리의 캐시는 공용이라 손대지 않는다.
            here = os.path.dirname(path)
            while here != base and here.startswith(base):
                if os.path.lexists(here) and _pack_link(here):
                    return True
                here = os.path.dirname(here)
            return False

        reused = 0
        for source, target in files:
            if _pack_same(source, target):
                reused += 1
                # ★같은 바이트로 재사용한 .py 도 옛 .pyc 를 지운다(W2-09) — 앞선 실행기가 시각 고정 팩을 풀면서
                #   다른 내용의 캐시를 이미 남겼을 수 있다(크기·시각이 같으면 파이썬이 그 캐시를 쓴다).
                if target.endswith('.py') and not under_inner_link(target):
                    _purge_stale_pyc(target)
                continue
            local_dir(os.path.dirname(target))
            # 다른 파일시스템의 staging에서 직접 rename하지 않는다. 기존 hardlink도
            # 열어서 덮어쓰지 않고 해당 디렉터리 항목만 원자적으로 교체한다.
            fd, temp = tempfile.mkstemp(prefix=".volcano-file-", dir=os.path.dirname(target))
            os.close(fd)
            try:
                shutil.copy2(source, temp)
                os.replace(temp, target)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
            # ★팩의 수정 시각이 고정이라(재현 가능한 tar) 크기가 같은 옛 .pyc 가 새 원본의 캐시로 채택된다 —
            #   «Local computation implementation mismatch» 2명(W2-09). 설치한 .py 의 옛 캐시를 지운다.
            if target.endswith('.py'):
                _purge_stale_pyc(target)
        _progress("  [자산] 동일 파일 %d개 재사용 · %d개 설치" % (reused, len(files) - reused))


# ★윈도우에서 동기화 앱·백신·편집기가 파일을 잠깐 쥐면 교체가 거부된다(WinError 5·32·33). 짧게만 다시 한다.
#   값은 서버가 옛 실행기에게 내려주는 파일 단위 설치기와 같은 값이다(src/volcano_runner_migration.py `_replace_shared`)
#   — 두 설치기가 같은 자를 쓴다. 이것은 로컬 파일 교체만이다(서비스·단계 요청에는 쓰지 않는다).
_REPLACE_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)
# 실행기 본체 셋은 맨 마지막에 바꾼다 — 도중에 끊겨도 옛 본체가 새 부품을 부르는 반쪽 상태가 덜 생긴다
# (서버 설치기의 CORE 순서와 같다).
_RUNNER_CORE = ('runner_files.py', 'volcano_run.py', 'volcano_drive.py')


def _replace_retry(temp, target):
    for attempt in range(len(_REPLACE_RETRY_DELAYS) + 1):
        try:
            os.replace(temp, target)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) in (5, 32, 33) and attempt < len(_REPLACE_RETRY_DELAYS):
                time.sleep(_REPLACE_RETRY_DELAYS[attempt])
                continue
            raise


def _unlink_retry(path):
    """지우면 True · 다른 프로세스가 끝내 쥐고 있으면 False(같은 간격으로만 다시 해 본다)."""
    for attempt in range(len(_REPLACE_RETRY_DELAYS) + 1):
        try:
            os.unlink(path)
            return True
        except FileNotFoundError:
            return True
        except OSError as error:
            if getattr(error, 'winerror', None) in (5, 32, 33) and attempt < len(_REPLACE_RETRY_DELAYS):
                time.sleep(_REPLACE_RETRY_DELAYS[attempt])
                continue
            return False



def _read_state_retry(path):
    """진행 기록(process.json)을 읽는다 — 윈도우에서 자식이 같은 파일을 교체(`_photo_write_state` · os.replace)하는 그 순간에 열면
    «삭제 대기» 상태라 PermissionError(WinError 5·32·33)가 난다(10-22 win-main 실측: 빨리 끝난 일은 running → exited 를 연달아
    교체해 부모의 첫 읽기와 겹쳤다). 교체가 쓰는 같은 자(`_REPLACE_RETRY_DELAYS`)로만 다시 읽는다 — 끝내 안 되면 그 오류를 그대로 올린다."""
    for attempt in range(len(_REPLACE_RETRY_DELAYS) + 1):
        try:
            with open(path, encoding='utf-8') as fh:
                return json.load(fh)
        except OSError as error:
            if getattr(error, 'winerror', None) in (5, 32, 33) and attempt < len(_REPLACE_RETRY_DELAYS):
                time.sleep(_REPLACE_RETRY_DELAYS[attempt])
                continue
            raise

def _purge_stale_pyc(source):
    """`source`(.py)의 옛 바이트코드를 지운다 — 배급 팩은 수정 시각이 고정이라(재현 가능한 tar) 크기가 같은
    옛 .pyc 가 새 원본의 캐시로 채택된다(맥·win-01 실측 «Local computation implementation mismatch» · W2-09).
    못 지운 것은 원본의 수정 시각을 바꿔 무효로 만든다(캐시는 원본의 시각·크기가 같을 때만 쓰인다)."""
    from pathlib import Path
    source = Path(source)
    cache = source.parent / '__pycache__'
    stale = [source.with_suffix('.pyc')]
    if cache.is_dir() and not _pack_link(str(cache)):
        stale.extend(cache.glob(source.stem + '.*.pyc'))
    held = False
    for path in stale:
        if (path.is_file() or path.is_symlink()) and not _unlink_retry(str(path)):
            held = True
    # ★원본이 공용 파일로의 연결이면 시각을 바꾸지 않는다 — os.utime 은 링크를 따라가 공용 원본을 바꾼다(COW 약속 ·
    #   2026-10-05 B 최종 검토). 공용 폴더 연결 아래의 원본은 부르는 쪽이 아예 부르지 않는다(§_runner_owned).
    if held and source.is_file() and not _pack_link(str(source)):
        now = time.time()
        if int(now) == int(os.stat(str(source)).st_mtime):
            now += 2
        os.utime(str(source), (now, now))


def _runner_identity(directory):
    """그 폴더의 실행기 식별값(실행기가 UA 에 싣는 값) — 그 폴더의 runner_files.py 로 잰다(판마다 파일 목록이
    다르다). 못 재면 None 과 사유."""
    import importlib.util
    path = os.path.join(str(directory), 'runner_files.py')
    if not os.path.isfile(path):
        return None, 'runner_files.py 없음'
    spec = importlib.util.spec_from_file_location('volcano_staged_runner_files', path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module.identity(str(directory)), None
    except (OSError, ImportError, SyntaxError, AttributeError, TypeError, ValueError) as error:
        # 무엇이 없었는지까지 말한다(2026-10-17 어랍숏 assets «식별값(FileNotFoundError)» — 어느 파일인지 한 글자도 없었다).
        missing = getattr(error, 'filename', None)
        return None, type(error).__name__ + (f": {os.path.basename(str(missing))}" if missing else "")


def _runner_local_dir(here, directory):
    """runner/ 안의 하위 폴더를 쓸 수 있게 만든다 — 그 사이의 공용 연결은 떼고(COW) 없는 폴더는 만든다."""
    relative = os.path.relpath(directory, here)
    path = here
    for part in ([] if relative == os.curdir else relative.split(os.sep)):
        path = os.path.join(path, part)
        if os.path.lexists(path) and _pack_link(path):
            _pack_detach(path)
        elif not os.path.isdir(path):
            os.mkdir(path)


def _install_runner_in_place(stage, here, names):
    """일반 폴더 runner/ — **파일마다** 같은 폴더의 임시 파일 → os.replace 로 바꾼다(폴더 이름을 바꾸지 않는다).

    ★왜 (원장 W2-10 · win-01 실측): 부모 프로세스·편집기·탐색기가 runner/ 안에 있으면 윈도우는 그 폴더의
      이름 바꾸기를 거부한다(WinError 32). 같은 조건에서 파일 단위 교체는 5/5 성공했다. 예전 설치기는 폴더를
      통째로 바꿔(`os.replace(here, backup)`) 실행 중인 실행기 자신이 자기 갱신을 막았다.
    · 모든 새 파일을 임시 이름으로 먼저 다 쓰고(실패하면 아무것도 안 바뀐다) → 바꿀 원본을 보관하고 → 교체한다.
    · 바꾼 원본은 `<작업 폴더>/.volcano-runner-update/replaced/<설치 전 식별값>/` 에 처음 것만 남긴다
      (서버 설치기와 같은 자리 — 되돌릴 근거).
    · 링크 파일은 그 항목만 바꾼다(링크 대상은 공용이라 건드리지 않는다).
    """
    parent = os.path.dirname(here)
    os.makedirs(here, exist_ok=True)
    changed = []
    for name in names:
        source = os.path.join(stage, *name.split('/'))
        target = os.path.join(here, *name.split('/'))
        if os.path.islink(target) or not _pack_same(source, target):
            changed.append(name)
    if not changed:
        return []
    ordered = sorted(changed, key=lambda n: (n in _RUNNER_CORE, _RUNNER_CORE.index(n) if n in _RUNNER_CORE else -1, n))
    key, _why = _runner_identity(here)
    old = {}
    # 교체 도중 실패하면 되돌릴 원래 모습 — 일반 파일은 바이트와 권한, 링크 파일은 링크 대상(실행기 파일은 수백 KB 라 메모리에 둔다).
    before = {}
    for name in ordered:
        target = os.path.join(here, *name.split('/'))
        if os.path.islink(target):
            before[name] = ('link', os.readlink(target), None)
        elif os.path.isfile(target):
            with open(target, 'rb') as body:
                data = body.read()
            old[name] = hashlib.sha256(data).hexdigest()
            before[name] = ('file', data, stat.S_IMODE(os.stat(target).st_mode))
    if key is None:
        mark = hashlib.sha256()
        for name in sorted(old):
            mark.update(name.encode('utf-8') + b'\0' + old[name].encode('ascii'))
        key = 'x' + mark.hexdigest()[:11]
    backup = os.path.join(parent, '.volcano-runner-update', 'replaced', key)
    temps = {}
    done = []
    try:
        name = None
        try:
            for name in ordered:
                target = os.path.join(here, *name.split('/'))
                _runner_local_dir(here, os.path.dirname(target))
                fd, temps[name] = tempfile.mkstemp(prefix='.volcano-file-', dir=os.path.dirname(target))
                os.close(fd)
                shutil.copy2(os.path.join(stage, *name.split('/')), temps[name])
        except OSError as error:
            raise StepError('새 실행기 파일 runner/%s 을(를) 준비하지 못했습니다(%s: %s). 아직 아무 파일도 바꾸지 않았습니다 — '
                            '디스크 공간·쓰기 권한을 확인한 뒤 같은 명령을 다시 실행하세요.'
                            % (name, type(error).__name__, str(error)[:120])) from error
        name = None
        try:
            for name in ordered:
                if name not in old:
                    continue
                copy = os.path.join(backup, *name.split('/'))
                if os.path.lexists(copy):
                    continue   # 처음 보관한 원본은 덮지 않는다
                os.makedirs(os.path.dirname(copy), exist_ok=True)
                fd, temp = tempfile.mkstemp(prefix='.volcano-file-', dir=os.path.dirname(copy))
                os.close(fd)
                try:
                    shutil.copy2(os.path.join(here, *name.split('/')), temp)
                    os.replace(temp, copy)
                finally:
                    if os.path.exists(temp):
                        os.unlink(temp)
        except OSError as error:
            raise StepError('바꾸기 전 원본 runner/%s 을(를) %s 에 보관하지 못했습니다(%s: %s). 아직 아무 파일도 바꾸지 '
                            '않았습니다 — 디스크 공간·쓰기 권한을 확인한 뒤 같은 명령을 다시 실행하세요.'
                            % (name, _plain_path(backup), type(error).__name__, str(error)[:120])) from error
        for name in ordered:
            target = os.path.join(here, *name.split('/'))
            try:
                if os.name == 'nt' and os.path.isfile(target) and not os.access(target, os.W_OK):
                    # 읽기 전용 속성이 붙은 파일은 윈도우가 교체를 거부한다(WinError 5) — 속성만 푼다.
                    os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
                _replace_retry(temps[name], target)
            except OSError as error:
                # ★이미 바꾼 파일을 원래대로 되돌린다(2026-10-06 B 최종 검토 4회차) — 되돌리지 않으면 새 volcano_run 과
                #   옛 volcano_drive 처럼 판이 섞인 runner/ 가 남아, 그 폴더로 다시 뜬 실행기가 어느 판도 아닌 채로 돈다.
                #   예전 폴더째 교체 설치기도 실패하면 원래 폴더로 돌아갔다(tests/test_runner_update_cwd ③). 되돌리기마저
                #   막히면(같은 프로그램이 쥐고 있다) 그 사실과 «같은 명령으로 이어서 설치» 를 말한다.
                stuck = _runner_rollback(here, done, before)
                if stuck:
                    raise StepError('runner/%s 을(를) 바꾸지 못했고(%s: %s), 이미 바꾼 파일 %d개 중 %s 은(는) 원래대로 '
                                    '되돌리지도 못했습니다 — runner/ 에 새 판과 옛 판 파일이 섞여 있습니다. 바꾸기 전 원본은 %s '
                                    '에 있습니다. 그 파일을 쥔 프로그램(동기화 앱·백신·편집기)을 끝낸 뒤 같은 명령을 다시 '
                                    '실행하면 이어서 설치합니다.'
                                    % (name, type(error).__name__, str(error)[:120], len(done), ', '.join(stuck),
                                       _plain_path(backup))) from error
                raise StepError('runner/%s 을(를) 바꾸지 못했습니다(%s: %s). 먼저 바꾼 파일 %d개는 원래대로 되돌렸습니다 — '
                                'runner/ 는 설치 전 그대로입니다. 다른 프로그램(동기화 앱·백신·편집기)이 그 파일을 쥐고 '
                                '있거나 쓰기 권한이 없습니다 — 그것을 끝낸 뒤 같은 명령을 다시 실행하세요.'
                                % (name, type(error).__name__, str(error)[:120], len(done))) from error
            del temps[name]
            done.append(name)
    finally:
        for temp in temps.values():
            if os.path.exists(temp):
                os.unlink(temp)
    return changed


def _runner_rollback(here, done, before):
    """`_install_runner_in_place` 의 교체 도중 실패 — 이미 바꾼 `done` 을 거꾸로 원래 모습(`before`)으로 되돌린다.
    원래 없던 파일은 지운다. 못 되돌린 이름 목록을 돌려준다(빈 목록이면 runner/ 는 설치 전 그대로다)."""
    stuck = []
    for name in reversed(done):
        target = os.path.join(here, *name.split('/'))
        kind, value, mode = before.get(name, (None, None, None))
        try:
            if kind is None:
                if not _unlink_retry(target):
                    stuck.append(name)
                continue
            fd, temp = tempfile.mkstemp(prefix='.volcano-file-', dir=os.path.dirname(target))
            os.close(fd)
            try:
                if kind == 'link':
                    os.unlink(temp)
                    os.symlink(value, temp)
                else:
                    with open(temp, 'wb') as body:
                        body.write(value)
                    # ★권한도 설치 전 그대로(2026-10-06 B 최종 검토 4회차 minor) — mkstemp 임시 파일은 0600 이라 바이트만 쓰고
                    #   바꾸면 되돌린 파일이 0600 이 됐다. 수정 시각은 일부러 되돌리지 않는다: 지금 시각이면 옛 .pyc 가 크기·시각
                    #   대조에서 반드시 빗나가 원본에서 다시 컴파일된다(고정 시각 팩의 «같은 크기·시각 다른 내용» 캐시 사고 W2-09).
                    if mode is not None:
                        os.chmod(temp, mode)
                _replace_retry(temp, target)
            finally:
                if os.path.lexists(temp):
                    if os.name == 'nt' and not os.path.islink(temp):
                        # 읽기 전용으로 되돌린 임시 파일은 윈도우가 지우기를 거부한다 — 속성만 풀고 지운다.
                        os.chmod(temp, stat.S_IWRITE | stat.S_IREAD)
                    os.unlink(temp)
        except OSError:
            stuck.append(name)
    return stuck


def _plain_path(path):
    """윈도우 확장 경로(`\\\\?\\…`)를 사람이 읽는 일반 경로로 — 안내문·현재 폴더 비교용(입출력은 확장 경로로 한다)."""
    path = os.fspath(path)
    if path.startswith('\\\\?\\UNC\\'):
        return '\\\\' + path[8:]
    if path.startswith('\\\\?\\'):
        return path[4:]
    return path


def _runner_owned(here, name):
    """runner/<name> 이 이번 설치가 **소유한** 자리인가 — runner/ 자신과 그 아래 폴더·파일 어느 것도 공용 연결(심링크·정션)이
    아니어야 한다(2026-10-05 B 최종 검토 major). 연결된 자리의 캐시·원본은 공용이라 «읽기만» 한다(COW 약속) — 예전에는
    바뀐 파일이 없을 때도 옛 바이트코드 정리가 링크를 따라 공용 `__pycache__` 를 지우고 공용 원본의 수정 시각을 바꿨다
    (tests/test_runner_install_shared_untouched). 바뀐 파일이 있으면 그 자리는 이미 떼어 새 폴더가 됐다(COW) → 소유."""
    path = here
    for part in [''] + name.split('/'):
        if part:
            path = os.path.join(path, part)
        if os.path.lexists(path) and _pack_link(path):
            return False
    return True


def install_runner_files(tar, runner_dir, *, expect_id=None):
    """실행기 팩을 `runner_dir` 에 설치하는 **한 자리** — self_update·assets(runner 팩)·FP2 자동 갱신이 쓴다.

    · 팩은 runner/ 아래 일반 파일만(검사 실패면 아무것도 안 바꾼다) · 깨끗한 임시 폴더에 안전 해제해 대조한다.
    · `expect_id`(서버가 선언한 runner_id)가 있으면 **설치 전** 새 팩의 식별값을 대조하고(다르면 안 바꾼다)
      **설치 뒤** 그 폴더의 식별값을 다시 잰다(다르면 멈춘다 — 옛 .pyc·다른 프로세스의 동시 교체 등).
    · 일반 폴더는 파일 단위 원자 교체(`_install_runner_in_place`) · 공용 연결은 연결만 바꾸는 COW(`_install_runner_linked`).
    · 설치·재사용한 .py 의 옛 바이트코드를 지운다(W2-09) — 이번 설치가 소유한 자리에서만(공용 연결은 읽기만 · §_runner_owned).
    돌려주는 것: 바꾼 파일 이름(runner/ 기준 상대경로) 목록. 같으면 [].
    """
    members = _pack_members(tar)
    files = [m for m in members if m.isfile()]
    if not files or any(m.name.rstrip("/") != "runner" and
                        not m.name.startswith("runner/") for m in members):
        raise StepError("실행기 팩에는 runner/ 아래 일반 파일만 있어야 합니다. 바꾸지 않았습니다.")
    # ★모든 파일 입출력은 확장 경로로 한다(윈도우 MAX_PATH · 2026-10-05 B 최종 검토 major). 원본 보관 자리
    #   <작업 폴더>/.volcano-runner-update/replaced/<12자>/<이름> 은 runner/<이름> 보다 38자 길어, 실행기가 멀쩡히 도는
    #   폴더(win-01 실측: 작업 폴더 196자 · 실행기 파일 232자)에서도 보관본이 270자가 돼 날 FileNotFoundError 로 죽었다.
    #   FP1 서버 설치기(src/volcano_runner_migration.py io_target·backups)와 같은 계약 — `_review_receipt_io_path`.
    from volcano_run import _review_receipt_io_path
    here = _review_receipt_io_path(os.path.abspath(runner_dir))
    if os.path.lexists(here) and not os.path.isdir(here):
        raise StepError("실행기 설치 자리에 폴더가 아닌 항목이 있습니다. 바꾸지 않았습니다.")
    names = sorted({"/".join(p for p in m.name.split("/")[1:] if p not in ("", ".")) for m in files})
    with tempfile.TemporaryDirectory(prefix="volcano-runner-check-") as checked:
        extract_pack(tar, checked)
        stage = _review_receipt_io_path(os.path.join(checked, "runner"))
        if expect_id is not None:
            staged, why = _runner_identity(stage)
            if staged != expect_id:
                raise StepError("새 실행기 팩의 식별값(%s)이 서버 선언(%s)과 다릅니다. 바꾸지 않았습니다."
                                % (staged or why, expect_id))
        # ★공용 연결 판정과 폴더째 교체(COW)는 떼기 잠금 **안에서** 한다(2026-10-05 B 최종 검토 3회차). assets 는 팩을
        #   동시에 받는다 — 조교 손 팩(runner/ref_*.py)이 `extract_pack` 으로 같은 runner/ 의 연결을 떼고 파일을 쓰는
        #   사이에 이 설치기가 «옛 연결» 이라 여긴 그 폴더를 통째로 치우면 손 팩 파일이 오류 없이 사라졌다. 잠금 안에서
        #   다시 보고, 누가 먼저 뗐으면(이제 보통 폴더) 파일 단위 설치로 간다 — 파일 단위는 남의 파일을 안 지운다.
        # changed 는 두 갈래 중 하나에서 정해진다 — 연결이면 잠금 안 연결 설치, 아니면 잠금 밖 파일 단위 설치(2026-10-06 통합:
        #   경계 검사 «조건부 미정의 변수 0건» 이 이 구조를 증명하지 못했다 · 동작은 그대로).
        changed = None
        with _PACK_DETACH_LOCK:
            linked = os.path.lexists(here) and _pack_link(here)
            if linked:
                changed = _install_runner_linked(tar, here)
        if not linked:
            changed = _install_runner_in_place(stage, here, names)
    for name in names:
        if name.endswith('.py') and _runner_owned(here, name):
            _purge_stale_pyc(os.path.join(here, *name.split('/')))
    if expect_id is not None:
        after, why = _runner_identity(here)
        if after != expect_id:
            raise StepError("설치 뒤 실행기 식별값(%s)이 서버 선언(%s)과 다릅니다. 같은 명령을 다시 실행하면 이어서 "
                            "설치합니다(바꾸기 전 원본은 작업 폴더의 .volcano-runner-update/replaced/ 에 있습니다)."
                            % (after or why, expect_id))
    if not changed:
        _progress("  [실행기] 같은 파일 %d개를 재사용합니다" % len(files))
    return sorted(changed)


def install_runner_pack(t, runner_dir):
    """옛 이름 — 서버 설치기(옛 실행기 자동 갱신 · src/volcano_runner_migration.py)가 새 팩의 이 이름을 부른다.
    서명·반환을 그대로 두고 `install_runner_files` 한 자리로 간다."""
    return install_runner_files(t, runner_dir)


def install_home_runner(workdir, runner_id):
    """작업 폴더의 실행기가 돌 때 자기 배급 파일(runner_files.STUDENT_FILES)을 오래 가는 자리
    (video_encoder.home_runner_dir — ~/.volcano/runner)에 설치한다. 실행기 밖에서 Claude 가 직접 치는 «안내형» 엔진 팩 도구가
    그 자리에서 영상 인코더 판정 모듈을 찾는다(정본 tools/venc_lookup.py).

    · 설치된 실행기만 한다 — 그 사실은 실행기 자신의 설치 자리(`volcano_run._self_update_dir(workdir)` = <작업 폴더>/runner,
      self_update·FP2 가 설치하는 바로 그 자리)와 이 모듈의 폴더가 같은가다. 저장소 원본을 다른 작업 폴더로 돌린 실행(개발·시험)은
      설치된 실행기가 아니라 하지 않는다.
    · 가리킴(다른 폴더 이름)을 적지 않고 **파일을 설치**한다 — 작업 폴더가 지워져도 이 자리는 남는다(10-19 가리킴 판은 시험·작업
      폴더를 가리킨 채 그 폴더가 지워져 안내형 단계가 조용히 CPU 로 떨어졌다).
    · 그 자리의 식별값이 이미 같으면 아무것도 안 한다. 설치는 실행기 설치기 한 자리(`install_runner_files` · 파일 단위 원자 교체 ·
      옛 .pyc 정리 · 설치 뒤 식별값 대조)로 한다. 못 하면 실행기는 멈추지 않고 사유를 진행 줄에 남긴다 — 그때 안내형 도구는
      «모듈 없음» 을 보여 주고 멈춘다(조용히 CPU 로 가지 않는다). 돌려주는 값: 바꾼 파일 이름 목록(같으면 [] · 안 하면 None)."""
    import io                                                         # noqa: PLC0415
    import video_encoder                                              # noqa: PLC0415
    from runner_files import STUDENT_FILES                            # noqa: PLC0415
    from volcano_run import _self_update_dir                          # noqa: PLC0415
    here = os.path.dirname(os.path.abspath(__file__))
    home = str(video_encoder.home_runner_dir())
    try:
        installed = os.path.samefile(here, _self_update_dir(os.path.abspath(workdir)))
        if os.path.isdir(home) and os.path.samefile(here, home):
            return None                                               # 오래 가는 자리에서 직접 돈다
    except OSError:
        installed = False
    if not installed or runner_id == "unknown":
        return None
    if _runner_identity(home)[0] == runner_id:
        return []
    try:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name in sorted(STUDENT_FILES):
                tar.add(os.path.join(here, name), arcname="runner/" + name, recursive=False)
        buf.seek(0)
        with tarfile.open(fileobj=buf) as tar:
            return install_runner_files(tar, home, expect_id=runner_id)
    except (OSError, StepError, tarfile.TarError) as error:
        _progress(f"  ⚠ 실행기를 {home} 에 설치하지 못했습니다 — 실행기 밖 엔진 팩 도구가 영상 인코더 모듈을 못 찾습니다. "
                  f"사유: {error}", flush=True)
        return None


def _install_runner_linked(t, runner_dir):
    """runner/ 가 **공용 연결(심링크·정션)** 일 때만 — 연결 대상(공용 원본)은 읽기만 하고, 그 내용을 형제 임시
    폴더에 복사해 새 파일을 얹은 뒤 **연결만** 새 폴더로 바꾼다(COW). 바꾸는 것은 작업 폴더의 연결 항목이지
    남이 쥔 폴더가 아니다. 새 팩 검사/복사 중 실패하면 옛 연결이 그대로 남고, 마지막 교체가 실패하면 연결을
    복구한다. 공용 연결이 아닌 runner/ 는 `install_runner_files` 가 파일 단위로 바꾼다.
    """
    members = _pack_members(t)
    files = [m for m in members if m.isfile()]
    if not files or any(m.name.rstrip("/") != "runner" and
                        not m.name.startswith("runner/") for m in members):
        raise StepError("실행기 팩에는 runner/ 아래 일반 파일만 있어야 합니다. 바꾸지 않았습니다.")
    here = os.path.abspath(runner_dir)
    parent = os.path.dirname(here)
    if os.path.lexists(here) and not os.path.isdir(here):
        raise StepError("실행기 설치 자리에 폴더가 아닌 항목이 있습니다. 바꾸지 않았습니다.")
    with tempfile.TemporaryDirectory(prefix="volcano-runner-check-") as checked:
        extract_pack(t, checked)
        changed = [os.path.relpath(m.name, "runner") for m in files
                   if not _pack_same(os.path.join(checked, m.name),
                                     os.path.join(here, os.path.relpath(m.name, "runner")))]
        if not changed:
            _progress("  [실행기] 같은 파일 %d개를 재사용합니다" % len(files))
            return []
        os.makedirs(parent, exist_ok=True)
        temp = tempfile.mkdtemp(prefix=".volcano-runner-install-", dir=parent)
        copied, backup = os.path.join(temp, "runner"), os.path.join(temp, "original")
        try:
            if os.path.isdir(here):
                _progress("  [실행기] 기존 파일을 보존하며 새 설치를 준비합니다", flush=True)
                _pack_copy_tree(here, copied)
            else:
                os.mkdir(copied)
            # 같은 사전 검사·COW·파일 원자 교체를 마지막 설치 준비에도 적용한다.
            # copied는 소유한 새 폴더다. 내부 링크도 extract_pack이 분리한다.
            extract_pack(t, temp)
            # Reproducible archives share mtimes. An older same-size .pyc can
            # therefore look valid after replacement. Remove only cache files
            # belonging to the Python sources this pack actually installs.
            from pathlib import Path
            for member in files:
                source = Path(temp, member.name)
                if source.suffix == '.py':
                    cached = [source.with_suffix('.pyc')]
                    cached.extend((source.parent / '__pycache__').glob(source.stem + '.*.pyc'))
                    for path in cached:
                        if path.is_file() or path.is_symlink():
                            path.unlink()
            # Windows holds a directory handle for the process cwd. Release
            # our own handle only for cutover, then restore the same relative
            # location in the installed (or rolled-back) tree. Updates run before
            # recipe worker pools start; no child or external lock is bypassed.
            cwd = os.getcwd()
            # 현재 폴더 비교는 일반 경로끼리(입출력 경로는 확장 경로일 수 있다 — install_runner_files).
            shown = _plain_path(here)
            try:
                inside = os.path.commonpath([os.path.normcase(_plain_path(cwd)), os.path.normcase(shown)]) == os.path.normcase(shown)
            except ValueError:  # Windows paths on different drives.
                inside = False
            relative = os.path.relpath(_plain_path(cwd), shown) if inside else None
            if inside:
                os.chdir(_plain_path(parent))
            try:
                if os.path.lexists(here):
                    os.replace(here, backup)
                try:
                    os.replace(copied, here)
                except Exception:
                    if os.path.lexists(backup):
                        os.replace(backup, here)
                    raise
            finally:
                if inside:
                    restored = os.path.join(shown if os.path.isdir(here) else _plain_path(backup), relative)
                    if os.path.isdir(restored):
                        os.chdir(restored)
        except Exception as error:
            if os.path.lexists(backup):
                raise StepError("실행기 설치/복구 실패; 이전 파일의 백업 위치: %s (%s)" % (_plain_path(backup), error)) from error
            raise StepError("실행기 설치 실패; 공용 원본은 변경하지 않았습니다: %s" % error) from error
        else:
            # Cutover has succeeded. A locked old backup does not undo the new
            # installation and must not trigger the updater again.
            try:
                if os.path.lexists(backup):
                    if _pack_junction(backup):
                        os.rmdir(backup)
                    elif os.path.islink(backup):
                        os.unlink(backup)
                    else:
                        shutil.rmtree(backup)
            except OSError as error:
                _progress("  [실행기] 새 설치 완료 · 이전 파일 정리 보류: %s (%s)" % (_plain_path(backup), error), flush=True)
        finally:
            if not os.path.lexists(backup):
                try:
                    shutil.rmtree(temp)
                except OSError as error:
                    _progress("  [실행기] 임시 폴더 정리 보류: %s (%s)" % (_plain_path(temp), error), flush=True)

    return sorted(changed)


def _measure_frame_row(item):
    """One cut's server-facing measurement.

    `measure_frame` also returns `sample_paths` — the content-addressed sample
    PNGs it wrote so `review_film_frames` can attach the very same files. Here
    they live in a temporary folder and paths carry the student's home folder,
    so they are not part of the payload.
    """
    row = measure_frame(item)
    row.pop('sample_paths', None)
    return row


def _fetch_asset(item, c):
    """자산을 받아 SHA와 실제 파일 수를 확인한 뒤에만 푼다.

    ★서버가 주는 url 은 **상대경로**다(`/asset/…`). 서버 주소와 이어 붙여야 한다.
    ★열쇠는 **URL 안에** 들어 있다(`?k=…`). 그래서 토큰이 없어도 받아진다 —
      OAuth 로 등록한 수강생은 토큰을 손에 쥘 수 없기 때문이다(macOS 는 키체인).
      토큰이 있으면 함께 실어 보낸다. 옛 서버(열쇠 없는 URL)와도 그대로 맞물린다.
    ★파일 이름은 **경로에서만** 딴다. 쿼리를 그대로 두면 `sfx?k=….tar.gz` 가 된다.
    """
    # ★굽기 직전 확보(서버 `_attach_render_packs` · 2026-10-17) — 그 단계가 읽을 팩 파일이 **다 있으면** 지문도 재지 않고 지나간다.
    #   하나라도 없을 때만 아래 검증·확보 길을 탄다(빠진 밈·글꼴을 그 자리에서 되살린다 · 평소에는 os.path.exists 만).
    need = item.get("only_if_missing")
    if isinstance(need, list) and need and all(isinstance(p, str) and os.path.exists(p) for p in need):
        return
    if isinstance(need, list) and need:
        gone = [p for p in need if not (isinstance(p, str) and os.path.exists(p))]
        _progress(f"  [자산] 작업 폴더에 없는 팩 파일 {len(gone)}개 — 팩을 다시 확보합니다: " + " · ".join(map(str, gone[:3]))
                  + (f" 외 {len(gone) - 3}개" if len(gone) > 3 else ""), flush=True)
    baseline_repair = item.get("politics_baseline_repair")
    if baseline_repair is not None:
        import politics_legacy_upgrade
        if politics_legacy_upgrade.ready(item.get("extract_to") or ".", baseline_repair):
            return
    url = item["url"]
    if url.startswith("/"):
        url = c.url.rstrip("/") + url
    label = item["url"].split("?", 1)[0]
    reuse = item.get("reuse_verified") is True
    dest = os.path.abspath(item.get("extract_to") or ".")
    receipt_dir = os.path.join(dest, ".volcano-asset-receipts")

    def sha256(body):
        digest = hashlib.sha256()
        for block in iter(lambda: body.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()

    def valid_sha(value):
        return (isinstance(value, str) and len(value) == 64
                and all(c in "0123456789abcdef" for c in value))

    def first_mismatch(files):
        """기록(팩 파일 목록)과 실물이 다른 첫 파일 «이름 · 어떻게 다른지» — 다 맞으면 None.
        ★어느 파일이 어떻게 다른지를 돌려준다(2026-10-22 뇌전구 신고 · 윈도우 6건 · 10-13 까지 3D쇼츠 187건): 예전엔 참/거짓만이라
          «설치한 자산이 검증된 팩과 다릅니다» 에 파일 이름이 없어 풀자마자 사라졌는지(백신 격리 등)·바뀌었는지(다른 프로그램이
          같은 자리에 씀)를 가를 수 없었다. 판정은 그대로다(첫 어긋남에서 멈춘다 · 파일마다 한 번만 잰다)."""
        for entry in files:
            path = os.path.join(dest, *entry["name"].split("/"))
            if not os.path.isfile(path):
                return entry["name"] + " · 풀었는데 없음", entry
            size = os.path.getsize(path)
            if size != entry["size"]:
                return "%s · 크기 %d (팩 %d)" % (entry["name"], size, entry["size"]), entry
            with open(path, "rb") as body:
                if sha256(body) != entry["sha256"]:
                    return entry["name"] + " · 크기는 같고 내용이 다름", entry
        return None

    def written_by_whom(entry, packed):
        """풀자마자 다른 파일의 사실 — 누가 썼는지 가를 재료(2026-10-23 우팔롬아 신고 2명 · ytclip.py 34785 · newjob.py 18028:
        우리 판 어디에도 없는 크기이고 받은 팩 sha 는 맞았다 → 회원 PC 의 무언가가 풀린 직후 그 자리에 썼다. 그것이 무엇인지
        (링크로 다른 곳을 가리킴 · 하드링크 · 방금 쓰임 · 무엇을 바꿨나)를 다음 신고가 말하게 한다). 판정은 바꾸지 않는다."""
        path = os.path.join(dest, *entry["name"].split("/"))
        facts = []
        try:
            real = os.path.realpath(path)
            if os.path.normcase(real) != os.path.normcase(os.path.abspath(path)):
                facts.append("실제 자리 " + real)
            st = os.lstat(path)
            facts.append("쓴 지 %.1f초 전" % (time.time() - st.st_mtime))
            if st.st_nlink > 1:
                facts.append("하드링크 %d개" % st.st_nlink)
            with open(path, "rb") as body:
                disk = body.read(4 * 1024 * 1024)
        except OSError as error:
            return " · 사실 못 잼(%s)" % type(error).__name__
        old_lines, new_lines = packed.splitlines(), disk.splitlines()
        for number, (a, b) in enumerate(zip(old_lines, new_lines), 1):
            if a != b:
                facts.append("처음 다른 줄 %d: %r" % (number, b[:160].decode("utf-8", "replace")))
                break
        else:
            facts.append("앞 %d줄은 같고 뒤가 %s" % (min(len(old_lines), len(new_lines)),
                                                "늘었음" if len(new_lines) > len(old_lines) else "줄었음"))
        return " · " + " · ".join(facts)

    def local_receipt_dir():
        if os.path.lexists(receipt_dir) and (_pack_link(receipt_dir)
                                            or not os.path.isdir(receipt_dir)):
            raise StepError("자산 검증 기록 폴더가 일반 폴더가 아닙니다: " + receipt_dir)

    if reuse:
        from types import SimpleNamespace

        if not valid_sha(item.get("sha256")):
            raise StepError("자산 재사용에는 유효한 sha256 선언이 필요합니다: " + label)
        try:
            expected_files = int(item["n_files"])
        except (KeyError, TypeError, ValueError) as error:
            raise StepError("자산 파일 수 선언이 없습니다: " + label) from error
        receipt = os.path.join(receipt_dir, item["sha256"] + ".json")
        local_receipt_dir()
        try:
            # 기록 파일 자체가 링크면(공용 기록) 재사용하지 않는다. ★대상(작업 폴더) 자신이 정션·심링크인 것은
            #   막지 않는다 — 그것은 작업 폴더의 짧은 별칭이고(M8), 재사용 판정은 아래 first_mismatch 가 실물
            #   파일마다 sha·크기를 다시 재서 한다(기록은 «어느 파일을 잴지» 목록일 뿐이다).
            if (os.path.isfile(receipt)
                    and not _pack_link(receipt)):
                with open(receipt, encoding="utf-8") as body:
                    state = json.load(body)
                files = state["files"]
                if (state.get("version") != 1 or state.get("pack_sha256") != item["sha256"]
                        or not isinstance(files, list) or len(files) != expected_files):
                    raise ValueError("다른 팩 기록")
                members = []
                for entry in files:
                    name = entry["name"]
                    if (not isinstance(name, str) or not name
                            or name != "/".join(p for p in name.split("/") if p and p != ".")
                            or name.split("/")[0].casefold() == ".volcano-asset-receipts"
                            or not valid_sha(entry["sha256"])
                            or type(entry["size"]) is not int or entry["size"] < 0):
                        raise ValueError("잘못된 파일 기록")
                    members.append(tarfile.TarInfo(name))
                # 팩과 기록에 같은 경로/중복/Windows 이름 검증을 적용한다.
                _pack_members(SimpleNamespace(getmembers=lambda: members))
                if first_mismatch(files) is None:
                    _progress(f"  [자산] {label} 실물 sha·파일수 OK ({len(files)}) · 다운로드 재사용")
                    return
        except (OSError, ValueError, KeyError, TypeError, AttributeError, StepError):
            pass  # 손상/누락된 기록은 검증된 팩을 다시 받아 복구한다.
    with tempfile.TemporaryDirectory(prefix="volcano-download-") as temp:
        out = os.path.join(temp, "asset.tar.gz")
        # ★우리 서버의 자산 팩 — 중간에 끊기면 받은 데부터 이어받는다(2026-09-25 B11-코드 SR-19 ② · 209MB 참조 팩 끊김 17회·14명).
        with download_seen() as seen:
            n = download(url, out,
                         headers={"Authorization": f"Bearer {c.token}"} if c.token else None,
                         resume=True)
        with open(out, "rb") as body:
            got = sha256(body)
        if got != item["sha256"]:
            # ★응답 머리를 싣는다(2026-10-23): 새 판 주소(v=새 sha)에 바로 앞 판 바이트가 온 신고 15건(10-11~10-22) — 서버 경로로는 못 나온다.
            #   어느 Worker 판·어느 R2 키·Cloudflare 캐시·중간 프록시가 답했는지가 신고에 있어야 가린다(판정은 그대로).
            raise StepError(f"자산 sha256 불일치: {label} ({n}B)\n"
                            f"  받은 것 {got}\n  기대값  {item['sha256']}\n"
                            + asset_mismatch_facts(seen, n, got, fetcher=download))
        if baseline_repair is not None:
            politics_legacy_upgrade.install(dest, out, baseline_repair)
            return
        with tarfile.open(out) as t:
            try:
                expected_files = int(item["n_files"])
            except (KeyError, TypeError, ValueError) as error:
                raise StepError(f"자산 파일 수 선언이 없습니다: {label}") from error
            actual_files = sum(1 for member in t.getmembers() if member.isfile())
            if actual_files != expected_files:
                raise StepError(f"자산 파일 수 불일치: {label}\n"
                                f"  받은 것 {actual_files}\n  기대값  {expected_files}")
            if reuse:
                files, packed_member = [], {}
                for member in _pack_members(t):
                    name = "/".join(p for p in member.name.split("/") if p and p != ".")
                    if name.split("/")[0].casefold() == ".volcano-asset-receipts":
                        raise StepError("자산 팩은 검증 기록 폴더를 설치할 수 없습니다")
                    if member.isfile():
                        packed_member[name] = member
                        with t.extractfile(member) as body:
                            files.append({"name": name, "size": member.size, "sha256": sha256(body)})
                extract_pack(t, dest)
                # 팩의 내용과 최종 실물을 대조한 뒤에만 완료 기록을 남긴다.
                mismatch = first_mismatch(files)
                if mismatch is not None:
                    try:
                        with t.extractfile(packed_member[mismatch[1]["name"]]) as body:
                            packed = body.read(4 * 1024 * 1024)
                    except (KeyError, OSError, tarfile.TarError):
                        packed = b""
                    raise StepError("설치한 자산이 검증된 팩과 다릅니다: " + label + " — " + mismatch[0]
                                    + written_by_whom(mismatch[1], packed)
                                    # ★풀자마자(같은 실행 안 · 몇 ms) 다르면 이 실행 밖의 프로그램이 같은 파일에 쓴 것이다 — 신고 10-22 우팔롬아:
                                    #   같은 회원이 작업 셋을 한꺼번에 시작했고 `~/가라사대` 공용 이음이 작업마다 바뀌어 그 이음으로 고친 파일이
                                    #   다른 작업 폴더에 떨어졌다(우리 판 어디에도 없는 크기). 원인과 할 일을 함께 말한다.
                                    + " · 풀자마자 달라졌습니다 — 같은 폴더를 쓰는 다른 프로그램(동시에 돌리는 다른 작업이 공용 이음으로 연 파일·편집기·동기화)이"
                                      " 이 파일을 고쳤습니다. 팩 안 파일은 고치지 말고, 동시에 돌던 작업이 끝난 뒤 같은 명령을 다시 실행하면 팩을 다시 받아 풉니다")
                # ★대상 자신을 떼지 않는다(예전 `if _pack_link(dest): _pack_detach(dest)` — 작업 폴더 통째 복사·교체로
                #   윈도우 WinError 5 가 났다 · M8). 기록은 대상 안의 일반 폴더에 쓴다.
                local_receipt_dir()
                os.makedirs(receipt_dir, exist_ok=True)
                try:
                    from volcano_run import _asr_save
                    receipt = os.path.join(receipt_dir, item["sha256"] + ".json")
                    _asr_save(receipt, {"version": 1, "pack_sha256": item["sha256"], "files": files})
                except TranscriptionPending as error:
                    raise StepError("자산 검증 기록 저장 실패 — 저장 공간/권한을 확인하세요") from error
            elif item.get("pack") == "runner":
                # ★실행기 팩은 실행기 설치기 한 자리로 간다(W2-09·W2-10) — 파일 단위 교체 · 옛 .pyc 정리 ·
                #   서버가 runner_id 를 실었으면 설치 전·후 식별값 대조(예전에는 일반 자산처럼 풀고 확인하지 않아
                #   옛 캐시를 쓴 실행기가 «implementation mismatch» 로 멈췄다).
                rid = item.get("runner_id")
                install_runner_files(t, os.path.join(dest, "runner"),
                                     expect_id=rid if isinstance(rid, str) and rid else None)
            else:
                extract_pack(t, dest)
    _progress(f"  [자산] {label} {n:,}B sha·파일수 OK ({actual_files})")


def _ink_box(png):
    """그림에서 잉크 크기를 잰다. 픽셀을 재는 것은 실행기의 일반 기술이다."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert("L"))
    c = np.where(a.max(axis=0) > 60)[0]
    r = np.where(a.max(axis=1) > 60)[0]
    return (int(c.max() - c.min()), int(r.max() - r.min())) if len(c) else None


def _editor_font_metadata(font):
    """Read OpenType identity and libass' unscaled REAL_DIM metrics.

    libass ass_font.c:set_font_metrics uses signed OS/2 Windows metrics first.
    Otherwise FreeType's SFNT metrics (typo flag, hhea, typo) are retained;
    libass finally falls back to typo metrics without gap, then the font bbox.
    See libass 0.17.3 ass_font.c and FreeType sfnt/sfobjs.c (SFNT metrics).
    """
    os2=font.get('OS/2');head=font['head'];hhea=font.get('hhea')
    signed=lambda value:(int(value)+32768)%65536-32768
    win_a=signed(os2.usWinAscent) if os2 else 0
    win_d=signed(os2.usWinDescent) if os2 else 0
    if win_a+win_d:
        asc,desc,height,source=win_a,-win_d,win_a+win_d,'OS/2.usWinAscent/Descent'
    else:
        if os2 and os2.fsSelection&128:
            asc,desc,gap,source=os2.sTypoAscender,os2.sTypoDescender,os2.sTypoLineGap,'OS/2.USE_TYPO_METRICS'
        else:
            asc,desc,gap,source=(hhea.ascent,hhea.descent,hhea.lineGap,'hhea') if hhea else (0,0,0,'hhea-missing')
            if not (asc or desc) and os2:
                if os2.sTypoAscender or os2.sTypoDescender:
                    asc,desc,gap,source=os2.sTypoAscender,os2.sTypoDescender,os2.sTypoLineGap,'OS/2.sTypoAscender/Descender'
                else:asc,desc,gap,source=win_a,-win_d,0,'OS/2.usWinAscent/Descent'
        height=asc-desc+gap
        if asc-desc==0 or height==0:
            if os2 and os2.sTypoAscender-os2.sTypoDescender:
                asc,desc,source=os2.sTypoAscender,os2.sTypoDescender,'OS/2.sTypoAscender/Descender-fallback'
            else:asc,desc,source=head.yMax,head.yMin,'head.bbox-fallback'
            height=asc-desc
    name=font['name'].getDebugName(6)
    if not name or head.unitsPerEm<=0 or asc-desc<=0:
        raise ValueError('PostScript 이름 또는 실제 글꼴 높이를 확인할 수 없습니다.')
    return dict(font_postscript_name=name,font_units_per_em=int(head.unitsPerEm),
        font_ass_height=int(asc-desc),font_ascender=int(asc),font_descender=int(desc),
        font_line_height=int(height),font_metrics_source=source,
        font_bbox=[int(head.xMin),int(head.yMin),int(head.xMax),int(head.yMax)])


def measure_custom_text(item):
    """Inspect the actual font, then execute server-authored libass probes."""
    from pathlib import Path
    import shutil
    import numpy as np
    from PIL import Image
    from fontTools.ttLib import TTFont
    directory=Path(item['dir']);directory.mkdir(parents=True,exist_ok=True)
    fonts={};measurements={};catalog={}
    def inspect(path):
        try:
            with TTFont(path) as font:
                names={n.toUnicode() for n in font['name'].names if n.nameID in (1,4,6,16)}
                family=font['name'].getDebugName(1)
                cmap=set((font.getBestCmap() or {}).keys())
                metadata=_editor_font_metadata(font)
            return family,names,cmap,metadata
        except Exception as exc:
            raise StepError(f'사용자 글꼴 파일을 읽지 못했습니다: {path} ({type(exc).__name__})') from exc
    def resolve(pr):
        key=(pr.get('font_file'),pr['font'])
        if key not in fonts:
            source=Path(pr['font_file']) if pr.get('font_file') else None
            if source is None:
                # Only exact name-table matches are candidates; no fc-match fallback.
                roots=[directory,Path.home()/'Library/Fonts',Path('/Library/Fonts'),Path('/System/Library/Fonts/Supplemental'),
                    Path('/usr/share/fonts'),Path('/usr/local/share/fonts'),Path.home()/'.local/share/fonts',Path.home()/'.fonts']
                if os.environ.get('WINDIR'):roots.append(Path(os.environ['WINDIR'])/'Fonts')
                if os.environ.get('LOCALAPPDATA'):roots.append(Path(os.environ['LOCALAPPDATA'])/'Microsoft/Windows/Fonts')
                candidates=[]
                for root in roots:
                    if not root.is_dir():continue
                    for path in sorted(root.rglob('*')):
                        if path.suffix.lower() not in ('.ttf','.otf') or not path.is_file():continue
                        try:family,names,cmap,metadata=inspect(path)
                        except StepError:continue
                        if pr['font'] in names:candidates.append(path)
                    # Preserve root precedence without rereading every installed
                    # system font after an exact match in the supplied pack.
                    if candidates:break
                if not candidates:raise StepError(f"사용자 글꼴을 찾을 수 없습니다: {pr['font']}. font_file에 실제 TTF/OTF 절대경로를 지정하세요.")
                source=candidates[0]
            if not source.is_file():raise StepError(f'사용자 글꼴 파일이 없습니다: {source}')
            family,names,cmap,metadata=inspect(source)
            if pr.get('font_explicit') and pr['font'] not in names:
                raise StepError(f"사용자 font와 font_file의 이름이 다릅니다: {pr['font']} / {family}")
            name=pr['font'] if pr['font'] in names else family
            if not name or any(c in name for c in ',\\{}\n'):
                raise StepError('사용자 글꼴의 family 이름을 ASS에 사용할 수 없습니다.')
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            target=directory/('custom-'+digest+source.suffix.lower())
            if source.resolve()!=target.resolve():
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                    raise StepError(f'동일 지문 글꼴 사본의 내용이 바뀌었습니다: {target}')
                if not target.exists():shutil.copyfile(source,target)
            fonts[key]=(name,target,digest,cmap,metadata)
        name,target,digest,cmap,metadata=fonts[key]
        if name in catalog and catalog[name]['sha256']!=digest:
            raise StepError(f'동일 글꼴 이름에 서로 다른 파일이 지정됐습니다: {name}. 이름이 다른 실제 글꼴을 사용하세요.')
        catalog[name]=dict(font=name,font_file=str(target),sha256=digest,**metadata)
        return fonts[key]
    for pr in item['probes']:
        name,target,digest,cmap,metadata=resolve(pr)
        missing=sorted({ord(c) for c in pr['text'] if not c.isspace() and ord(c) not in cmap})
        if missing:raise StepError(f"{pr['id']}: 사용자 글꼴에 없는 글자 {''.join(chr(c) for c in missing[:12])}. 다른 글꼴로 자동 대체하지 않습니다.")
        write=dict(pr['write']);write['content']=write['content'].replace('@FONT@',name)
        _write(write,'사용자 글꼴프로브')
        rendered=run_argv(pr['argv'])
        if not _font_selected(dict(name=name,font_file=str(target)),rendered.stderr):
            raise StepError(f"{pr['id']}: libass가 실제 사용자 글꼴을 선택하지 못했습니다: {name}")
        pixels=np.asarray(Image.open(pr['out']).convert('L'))
        yy,xx=np.where(pixels>60)
        if not len(xx):raise StepError(f"{pr['id']}: 글꼴을 렌더했지만 글자 잉크가 없습니다.")
        if xx.min()<2 or yy.min()<2 or xx.max()>=pixels.shape[1]-2 or yy.max()>=pixels.shape[0]-2:
            raise StepError(f"{pr['id']}: 문구가 측정 화면을 넘습니다. font_size 또는 줄바꿈을 수정하세요.")
        measurements[pr['id']]=dict(font=name,font_file=str(target),sha256=digest,**metadata,
            width=int(xx.max()-xx.min()+1),height=int(yy.max()-yy.min()+1),
            left=float(xx.min()-pr['origin'][0]),top=float(yy.min()-pr['origin'][1]))
    for name in item.get('editor_fonts') or []:
        resolve(dict(font=name,font_explicit=True))
    return dict(key=item['key'],lines=measurements,editor_fonts=catalog,
                font_metrics_version=item.get('font_metrics_version'))


def _font_selected(probe, stderr):
    """서버가 지정한 파일과 libass가 실제 선택한 얼굴을 대조한다.

    잉크 크기만 같아도 정상 글꼴이 기본 fallback일 수 있다. 글꼴 이름을
    추측하지 않고 OpenType nameID6와 libass fontselect 진단을 대조한다.
    """
    try:
        from fontTools.ttLib import TTFont
        with TTFont(probe["font_file"], lazy=True) as font:
            expected = font["name"].getDebugName(6)
    except Exception as error:
        # 깨진 name 테이블도 성공으로 취급하지 않는다. 키/사용자 경로는 싣지 않는다.
        raise StepError(f"libass 글꼴 확인용 파일을 읽지 못했다: {probe['name']} "
                        f"({type(error).__name__}). env 검사와 글꼴 자산 단계를 다시 실행하라.") from error
    import re
    selected = []
    for line in (stderr or "").splitlines():
        match = re.search(r"fontselect: \((.*), -?\d+, -?\d+\) -> .*, -?\d+, ([^,]+)$", line)
        if match:
            selected.append((match.group(1), match.group(2).strip()))
    return bool(expected and selected and all(
        name == probe["name"] and face == expected for name, face in selected))


# 조교 채널 계측 — 손 팩 2·3판 (2026-09-03 · volcano_ref). 각 모듈은 volcano_run 의 StepError·_fill 만 가져온다.
#
# ■ ★★**이 모듈들은 조교 팩(`runner_ref`)에만 있다** (2026-09-05, 유출 차단)
#     `ref_*` 는 «채널을 통째로 뜯어 규격을 뽑는» 계측기다. 그것을 수강생 480명에게
#     배급하면 안 된다 — 그런데 팩 빌더가 **확장자만** 보고 담아서, 2026-09-04 12:34 부터
#     `runner` 팩에 22개가 통째로 실려 나갔다(실측: 159명이 받아갔고 94명은 실행기가
#     자동으로 풀었다). 지금은 팩을 둘로 갈랐다.
#
# ■ 그래서 **없어도 죽지 않아야 한다**
#     최상위 `from ref_meta import ...` 로 두면 파일이 없는 수강생 실행기가 **첫 줄에서
#     통째로 죽는다** — 즉 「팩에서 빼기」만 하면 전원이 막힌다. 쓰는 자리는 전부
#     `if cmd == "ref_*"` 갈래 안이고 그 명령은 **조교 도구만** 보낸다(서버 `volcano_ref_gate`).
#     그러니 없으면 **부를 때** 사람 말로 멈추면 된다 — 부르지 않으면 아무 일도 없다.
#   ★이름을 `globals()` 로 심지 말 것 — `tools/check_names.py` 가 「정의되지 않은 이름」으로
#     본다. 갈래마다 **눈에 보이게** 이름을 만든다.
try:
    from ref_meta import ref_meta                               # S0 채널 전수 메타
    from ref_frames import ref_frames                           # S5 프레임 세기
    from ref_ocr import ref_ocr                                 # S6 Vision OCR + 색 샘플
    from ref_geom import ref_geom                               # S7 행 프로필·컷
    from ref_stems import ref_stems                             # S8 demucs 2스템
    from ref_captions import ref_captions                       # S9 자막 이벤트 병합
    from ref_tikitaka import ref_tikitaka                       # S10 보컬 엔벨로프
    from ref_fonts import ref_glyph_iou, ref_corepixels         # S11 낱자 IoU · 코어픽셀
    from ref_bundle import ref_sheet, ref_bundle_collect        # §5 컨택트시트 · 번들 수집
    from ref_advtable import ref_advtable                       # 4판 preset — 글자 전진폭 표
    from ref_analyze import ref_analyze_collect                 # 4판 analyze — 읽을 것 모으기
    REF_HANDS_ERR = ""
except ImportError as _rh_e:        # 조교 팩이 없는 수강생 실행기 — 정상이다
    REF_HANDS_ERR = repr(_rh_e)

    def _ref_absent(*_a, **_k):
        """조교 손이 없을 때 **부르면** 멈춘다. 수강생에게는 이 명령이 오지 않는다."""
        raise StepError(
            "조교 계측 손(runner_ref 팩)이 이 기계에 없습니다.\n"
            "  · 조교라면 `assets` 단계를 다시 부르세요 — 조교 계정에는 `runner_ref` 팩이 함께 옵니다.\n"
            "  · 수강생이라면 이 명령이 올 자리가 아닙니다(영상 제작에는 쓰이지 않습니다).\n"
            f"  (사유: {REF_HANDS_ERR})")

    ref_meta = ref_frames = ref_ocr = ref_geom = _ref_absent
    ref_stems = ref_captions = ref_tikitaka = _ref_absent
    ref_glyph_iou = ref_corepixels = _ref_absent
    ref_sheet = ref_bundle_collect = _ref_absent
    ref_advtable = ref_analyze_collect = _ref_absent

# ── axes 묶음 손(3판 2물결 · 73개) — 모듈마다 `ref_<줄기>` 함수들을 **이름으로** 모은다.
#   묶음 하나가 import 에서 죽어도 나머지는 산다 — 사유는 `_REF_AXES_ERRORS` 에 남고, 그 cmd 가 오면 말한다.
_REF_AXES, _REF_AXES_ERRORS = {}, {}
#   ★`siglip` 은 `ref_axes_*` 가 아니라 **자기 파일**이다 — `m_imgkind`·`m_imgmatch`·
#     `m_consist` 가 전부 그 한 자리를 쓰기 때문이다(정본 `m_pepe._siglip`). 묶음 이름이
#     아니라 **모듈 이름**으로 등록한다.
for _b, _mod in [(_x, f"ref_axes_{_x}") for _x in
                 ("a1", "a2", "b", "c1", "c2", "d", "e1", "e2", "f")] + [
                     ("g", "ref_siglip"), ("lf", "ref_lf_gemini")]:
    try:
        _m = __import__(_mod)
    except Exception as _e:
        _REF_AXES_ERRORS[_b] = repr(_e)
        continue
    for _n in dir(_m):
        if _n.startswith("ref_") and callable(getattr(_m, _n)):
            _REF_AXES[_n] = getattr(_m, _n)


def _keep(outs, cmd, value):
    """구조화 명령의 결과를 **명령 이름 그대로** `outs` 에도 남긴다.

    ■ 왜 있나 (2026-08-16)
        `execute()` 안에 결과 통이 둘이었다 — 구조화 핸들러는 `got`(=payload 조각),
        argv 명령은 `outs`(=명령 이름별 출력). 그런데 서버의 `measure` 규칙
        `{"from": "cmds:<이름>"}` 은 **`outs` 만** 본다. 그래서 서버가 구조화 명령에
        규칙을 적는 순간 "재기는 성공하고 다음 줄에서 죽는" 상태가 됐다.
        `measure_sfx`·`cut_sigs`·`factcheck` 셋이 그렇게 나흘간 92건·48명을 죽였다.
    ★고치는 자리는 규칙(서버)과 이 등록(실행기) **둘 다**다. 규칙만 지우면 다음
      사람이 또 적고, 여기만 고치면 이미 나간 옛 팩이 안 낫는다.
    ★매핑일 때만 남긴다 — `cmds:` 는 `dict(vals)` 로 쓰므로 목록·스칼라를 넣으면
      그 자리에서 다른 오류가 난다. 넣을 수 없는 것을 조용히 넣지 않는다.
    """
    #   ★★**빈 묶음도 남긴다**(2026-09-04). 전에는 `and value` 라 `{}` 를 버렸는데,
    #     `{}` 는 «못 쟀다» 가 아니라 **«재 보니 없더라»** 인 정상 측정값이다 — 어랍숏에는
    #     오프닝 카드가 없어 `ref_card_pass2` 가 `{}` 를 내는 것이 맞는 답인데, 그것이
    #     버려져 서버가 «하나도 재지 않았다» 로 죽였다(로컬 완주로 잡았다).
    #     §"빈 목록이 통과한다" 의 **거울상** — 여기서는 빈 것이 정답인데 없는 것으로 셌다.
    #   ★★**목록도 남긴다**(2026-09-04). 옛 이유는 «`cmds:` 가 `dict(vals)` 로 쓴다» 였는데,
    #     그 강제 변환 자체가 결함이었다 — 손이 **목록을 돌려주는 축**이 실제로 있다
    #     (`ref_capwidth` → `[{ratio}|{error}, …]`). 그래서 `_measure` 가 형을 **그대로** 쓰게
    #     고쳤고(아래), 여기서도 목록을 버리지 않는다. 스칼라는 여전히 안 남긴다 —
    #     그건 «명령 이름별 결과» 라는 이 통의 뜻과 맞지 않는다(그 자리는 `capture` 몫이다).
    if cmd and isinstance(value, (dict, list)):
        outs[cmd] = value


def _pick_from(got, rules):
    """`{"as": …, "pick": "words.SRC"}` — **이미 잰 값**을 서버가 읽는 이름으로 옮긴다.

    ■ 왜 (2026-08-22, 진단 저장소 304건·66명)
        전사 갈래는 `got["words"] = {"SRC": […]}` 로 담는데 서버는
        `payload.src_words` 를 읽는다. 그 변환을 **산문으로만** 시켰다:
            `"payload.src_words = words['SRC'] + payload.src_voiced = voiced['SRC']"`
        배급 실행기를 안 쓰는 클라(모델 클라이언트)가 그것을 못 지켜 값이 통째로
        안 왔고, `stitch_script` 가 「원본 측정값이 비어 있습니다」로 막았다.
        §"무엇을 재라를 산문으로 주면 된다 → **안 된다.** `measure` 로 데이터로 준다"
        (2026-08-18 에 같은 부류를 고쳤는데 `transcribe` 갈래는 안 봤다).

    ★**없으면 조용히 건너뛴다.** 이 규칙은 「이미 있으면 옮겨라」이지 「재라」가 아니다 —
      그 갈래를 안 탄 단계에서 죽으면 안 된다.
    ★점(`.`)으로 파고든다. 중간이 묶음이 아니면 그 규칙만 건너뛴다.
    """
    out = {}
    for r in (rules or []):
        path = r.get("pick")
        if not path:
            continue
        cur = got
        for part in str(path).split("."):
            if not isinstance(cur, dict) or part not in cur:
                cur = None
                break
            cur = cur[part]
        if cur is not None:
            out[r["as"]] = cur
            n = len(cur) if hasattr(cur, "__len__") else cur
            _progress(f"  [측정] {r['as']} ← {path} ({n}건)")
    return out


def _measure(res, rules, outs=None):
    """서버가 시킨 대로 재서 payload 조각을 만든다.

    ★무엇을 잴지 **구동기가 정하지 않는다.** 규칙이 없으면 아무것도 재지 않는다.
      규칙의 종류는 두 가지다:
        {"as","of":"jobs","index_by","file","unit":"seconds"}  파일 길이를 잰다
        {"as","from":"cmd:<이름>","unit":"json_stdout"}         그 명령의 출력을 넣는다
        {"as","from":"cmd:<이름>","unit":"json_stderr"}         같되 **stderr** 를 읽는다
        {"as","from":"cmd:<이름>","unit":"lufs_tp","stage":"…"}  `I:`·`Peak:` → {I,TP}

    ★★`cmds:<이름>` 의 `<이름>` 은 **`do[].cmd` 그 이름**이고, 찾는 자리는 `outs`
      하나다. 구조화 핸들러가 결과를 `got` 에만 넣으면 여기서는 영영 안 보인다 —
      2026-08-16 에 그것 때문에 `measure_sfx`·`cut_sigs`·`factcheck` 셋이
      나흘간 92건·48명을 죽였다(재기는 성공하고 **그 다음 줄**에서 죽는다).
      그래서 지금은 핸들러가 `outs[cmd]` 에도 등록한다(§execute ⑤).
    """
    import json as _json
    out = {}
    for r in rules or []:
        # ★`pick` 규칙은 **`_pick_from` 이 이미 처리했다** — 여기서 보면
        #   `r["of"]` 에서 `KeyError` 로 죽는다(재기는 성공하고 다음 줄에서 죽는 부류).
        if r.get("pick"):
            continue
        if str(r.get("from", "")).startswith("cmds:"):
            name = r["from"].split(":", 1)[1]
            vals = (outs or {}).get(name)
            # ★★`optional` — **못 재는 것이 정상인 측정**이 있다 (2026-08-16).
            #   `measure_lufs_spread` 는 짧은 소리에서 표본이 모자라면 `None` 을
            #   돌려준다(그게 옳다 — 못 잰 것은 0 이 아니다). 그러면 `outs` 에
            #   그 이름이 아예 안 생기고, 규칙이 **정상 실행을 죽였다**
            #   (`redub_source` 2건, 실측). 서버는 그 값을 경고에만 쓰는데도.
            #   → "이 측정은 있으면 좋고 없어도 된다" 를 **계약이 말하게** 한다.
            #   ★기본은 여전히 **필수**다. 선언한 것만 넘어간다 — 안 그러면
            #     진짜로 필요한 측정이 빠져도 조용히 지나간다(§유령 게이트).
            #   ★★**«키가 있느냐»로 판정한다**(2026-09-04). `if not vals` 는 빈 묶음 `{}` 를
            #     «안 쟀다» 로 셌다 — 그런데 `{}` 는 «재 보니 없더라» 인 **정상 측정값**이다.
            #     어랍숏에는 오프닝 카드가 없어 `ref_card_pass2` 가 `{}` 를 내는 것이 맞는 답인데
            #     여기서 죽었다(로컬 완주 31단계째에서 잡았다).
            #     CLAUDE.md §"측정값이 `is None` 이 아니면 통과 → 값이 아니라 **키가 있느냐**를 봐라"
            #     의 **거울상**이다 — 그쪽은 빈 것이 통과해서 문제였고 이쪽은 빈 것이 정답인데 막았다.
            _absent = name not in (outs or {})
            if _absent and r.get("optional"):
                _progress(f"  [측정] {r['as']} — 못 쟀다(선택 측정이라 넘어간다)")
                continue
            if _absent:
                # ★**무엇이 있었는지 말한다.** "하나도 재지 않았다" 만 주면 사람이
                #   "실행기가 안 쟀다" 로 읽는데, 실제로는 잰 값이 다른 이름에 있는
                #   경우가 있었다(위 사고). 이름이 어긋난 것을 즉시 보게 한다.
                have = ", ".join(sorted(outs or {})) or "(아무것도 없다)"
                raise StepError(
                    f"'{name}' 을 하나도 재지 않았다 — 이 응답의 measure 규칙이 "
                    f"`cmds:{name}` 을 요구하는데 그 이름으로 잰 것이 없다.\n"
                    f"  잰 이름: {have}\n"
                    f"  do 에 있던 명령: "
                    f"{', '.join(str(d.get('cmd')) for d in (res.get('do') or [])) or '(없음)'}\n"
                    f"  → 규칙의 이름이 명령 이름과 다르거나, 그 값이 payload 로 "
                    f"이미 흐르고 있어 규칙이 필요 없는 경우다. 서버 쪽 문제다.")
            #   ★★**형을 그대로 쓴다**(2026-09-04). `dict(vals)` 는 목록을 돌려주는 손을
            #     그 자리에서 죽였다(`ref_capwidth`). 복사만 하고 형은 손이 정한 대로 둔다 —
            #     서버가 그 형을 알고 규칙을 적었기 때문이다(§손이 정한 모양을 서버가 바꾸지 않는다).
            out[r["as"]] = dict(vals) if isinstance(vals, dict) else list(vals)
            _progress(f"  [측정] {r['as']} ← {name} {len(vals)}건")
            continue
        if str(r.get("from", "")).startswith("cmd:"):
            name = r["from"].split(":", 1)[1]
            raw = (outs or {}).get(name)
            if raw is None:
                raise StepError(f"'{name}' 의 출력이 없다 — 그 명령이 돌지 않았다")
            # ★★`cmd:`(단수)는 **글자**를 기대하는데 묶음이 올 수 있다 (2026-08-19).
            #   이름 있는 핸들러가 `_keep()` 으로 `outs[cmd]` 에 **묶음**을 넣기
            #   때문이다(`measure_loudnorm`·`measure_peak`). 그러면 바로 아래에서
            #   `raw.strip()` 이 `'dict' object has no attribute 'strip'` 로,
            #   `re.findall(..., raw)` 가 `TypeError` 로 죽었다 — 재기는 성공하고
            #   **그 다음 줄에서** 죽는 부류다. 실측(2026-08-19): 린박스·명화관
            #   마스터에서 91건·11명이 **영상을 다 굽고 난 뒤** 그렇게 멎었다.
            #   ★핸들러가 이미 **같은 값을 계산해 놓은 것**이므로 그대로 쓴다.
            #     서버 쪽도 핸들러 없는 이름을 보내도록 고쳤지만, 여기까지 막아야
            #     다음 사람이 `cmd:` 규칙을 새로 적었을 때 또 죽지 않는다
            #     (§`_keep` 독스트링: "고치는 자리는 규칙과 이 등록 **둘 다**다").
            if isinstance(raw, dict):
                if r.get("unit") == "lufs_tp":
                    stg = str(r.get("stage") or "master")
                    v = raw.get(stg) if isinstance(raw.get(stg), dict) else raw
                    if not isinstance(v, dict) or v.get("I") is None or v.get("TP") is None:
                        raise StepError(
                            f"'{name}' 이 낸 묶음에 `I`·`TP` 가 없다: "
                            f"{sorted(raw)[:6]}")
                    out.setdefault(r["as"], {})[stg] = {
                        "I": float(v["I"]), "TP": float(v["TP"])}
                    _progress(f"  [측정] {r['as']}[{stg}] "
                          f"I={v['I']} TP={v['TP']} (핸들러가 이미 잰 값)")
                else:
                    out[r["as"]] = raw
                    _progress(f"  [측정] {r['as']} ← {name} (핸들러가 이미 잰 값)")
                continue
            if r.get("unit") == "lufs_tp":
                # ★ffmpeg `ebur128` 요약의 `I:` 와 `Peak:` 두 숫자.
                #   서버가 `stage` 로 어느 칸에 넣을지 말한다 — 이름을 여기서
                #   지어내면 서버가 읽는 자리와 어긋난다(§`auth` 와 같은 규율).
                import re as _re
                _i = _re.findall(r"^\s*I:\s*(-?\d+\.?\d*)\s*LUFS",
                                 raw, _re.M)
                _pk = _re.findall(r"^\s*Peak:\s*(-?\d+\.?\d*)\s*dBFS",
                                  raw, _re.M)
                if not _i or not _pk:
                    raise StepError(
                        f"'{name}' 출력에서 `I:`·`Peak:` 를 못 읽었다 — "
                        f"argv 에 `-v error` 가 붙으면 요약이 사라진다. "
                        f"(받은 것 {len(raw)}자)")
                out.setdefault(r["as"], {})[str(r.get("stage") or "master")] = {
                    "I": float(_i[-1]), "TP": float(_pk[-1])}
                _progress(f"  [측정] {r['as']}[{r.get('stage')}] "
                      f"I={_i[-1]} TP={_pk[-1]}")
                continue
            if r.get("unit") == "pts_times":
                # ★★장면 전환 시각 — ffmpeg `showinfo` 가 **stderr** 에 찍는
                #   `pts_time:12.345` 를 전부 모아 정렬한다 (2026-08-19).
                #
                #   왜 단위를 만들었나: 서버가 `do:[{cmd:"scene_cuts"}]` 로 재라고만
                #   시키고 **`measure` 규칙을 안 줬다.** 그 이름을 아는 것은 배급
                #   실행기뿐이라, 모델 클라이언트는 무엇을 어디에 넣을지 몰라 같은
                #   값을 되보냈고 서버는 같은 단계를 다시 시켰다 — 한 명이 138회,
                #   47명이 530회를 그렇게 돌았다.
                #   §"무엇을 재라를 산문으로 주면 된다 → **안 된다.** `measure` 로
                #     **데이터로** 준다(실측 40회 순환)" — 그 규칙을 또 어겼다.
                #   ★`-v error` 가 붙으면 `showinfo` 줄이 통째로 사라진다. 그때는
                #     **0개**가 되는데, 그건 「장면 전환이 없다」와 구분되지 않는다 —
                #     그래서 서버가 0개를 어떻게 다룰지 따로 정한다(되묻지 않는다).
                import re as _re2
                out[r["as"]] = sorted({round(float(m.group(1)), 3) for m in
                                       _re2.finditer(r"pts_time:([0-9.]+)", raw)})
                _progress(f"  [측정] {r['as']} ← {name} 출력 {len(out[r['as']])}곳")
                continue
            if r.get("unit") in ("json_stdout", "json_stderr"):
                # ★출력 **전체**를 파싱한다. 한 줄이라 가정하면 안 된다 —
                #   ffprobe -of json 은 여러 줄로 예쁘게 찍는다(실측에서 여기서 깨졌다).
                txt = raw.strip()
                try:
                    out[r["as"]] = _json.loads(txt)
                except Exception:                                 # noqa: BLE001
                    # ★앞의 잡음은 건너뛰되 **객체 하나만** 읽는다 (2026-10-17 · 신고 #137). 예전에는 첫 '{' 부터 마지막 '}'
                    #   까지를 통째로 읽어, 자식이 결과를 둘 이상 이어 붙여 낸 판(쇼핑 수급 — 일꾼 스레드의 emit)에서
                    #   «Extra data» 로 죽었다. 결과가 둘이면 어느 쪽이 맞는지 여기서 고를 수 없다 — 그 사실을 말한다.
                    i = txt.find("{")
                    if i < 0:
                        raise StepError(f"'{name}' 이 JSON 을 내놓지 않았다: {txt[:160]!r}")
                    try:
                        obj, end = _json.JSONDecoder().raw_decode(txt, i)
                    except ValueError as exc:
                        raise StepError(f"'{name}' 의 JSON 출력을 읽지 못했다({exc}): {txt[i:i + 160]!r}") from exc
                    # ★«둘째 결과» 는 뒤가 **실제로 JSON 객체로 읽힐 때만**이다 (2026-10-17). ffmpeg stderr 는 결과 JSON 뒤에
                    #   `[out#0/null @ …]` 같은 로그 줄이 늘 이어지는데, 첫 글자 '[' 만 보고 둘째 결과로 쳐서 loudnorm 측정
                    #   (json_stderr)이 전 채널에서 죽었다(경계검사 test_master_audio_converges 가 잡았다).
                    _rest = txt[end:].lstrip()
                    try:
                        _second = _json.JSONDecoder().raw_decode(_rest)[0] if _rest[:1] == "{" else None
                    except ValueError:
                        _second = None
                    if isinstance(_second, dict):
                        raise StepError(f"'{name}' 이 결과를 둘 이상 냈다(한 번만 내야 한다 — 자식 스크립트 결함): "
                                        f"{txt[i:i + 120]!r} … 뒤 {txt[end:end + 120].strip()!r}")
                    out[r["as"]] = obj
            else:
                out[r["as"]] = raw.strip()
            _progress(f"  [측정] {r['as']} ← {name} 출력")
            continue
        src = res.get(r["of"]) or []
        vals = {}
        for it in src:
            path = it.get(r["file"])
            if not path or not os.path.exists(path):
                raise StepError(f"재야 할 파일이 없다: {path}")
            if r.get("unit") == "seconds":
                try:
                    vals[str(it[r["index_by"]])] = wav_seconds(path)
                except StepError as error:
                    error.audio_duration_failure = True
                    error.execution_partial = dict(out, **{r['as']: vals})
                    raise
            elif r.get("unit") == "lufs":
                # ★★파일 간 **크기 맞추기**에 쓴다 — TTS 는 문장마다 크기가 제각각이다
                #   (실측: 같은 편에서 −16.0 ~ −25.9 LUFS). 서버가 이 값으로 게인을 정한다.
                # ★★재는 **명령은 서버가 준다.** 없으면 멈춘다 — 여기서 지어내면
                #   서버가 자를 고쳐도 이 팩이 안 따라간다(§실행기 규율).
                tpl = r.get("argv")
                if not tpl:
                    raise StepError("라우드니스 argv 를 서버가 안 줬다 — 여기서 짓지 않는다")
                slot = r.get("argv_in") or "@IN@"
                vals[str(it[r["index_by"]])] = lufs_of(
                    [path if a == slot else a for a in tpl])
            elif r.get("unit") == "seconds_by_frames":
                # ★자를 **서버가 정한다** — 컨테이너 duration 과 프레임 수는 다를 수
                #   있고, 이어붙인 길이를 정하는 것은 프레임이다(실측 2026-08-18).
                vals[str(it[r["index_by"]])] = frame_seconds(path)
            else:
                raise StepError(f"모르는 단위: {r.get('unit')}")
        out[r["as"]] = vals
        _progress(f"  [측정] {r['as']} {len(vals)}개")
    return out


def auth_headers(res, headers=None):
    """서버가 `auth` 로 알려준 자리에서 **본인 키**를 읽어 헤더를 만든다.

    ★어디서 읽고 어느 헤더에 싣는지는 **서버가 정한다.** 여기서 파일 이름이나
      헤더 이름을 지어내면, 서버가 확인한 자리와 여기가 읽는 자리가 어긋나
      `env` 게이트가 통과시켜 놓고 실행이 죽는다 — 오류가 늦게 나는 그 결함이
      정확히 그렇게 생긴다.
    ★호출자가 직접 넘긴 headers 가 있으면 그것을 **덮어쓰지 않는다**(수동 지정 우선).
    """
    # ★★★**헤더가 아닌 것을 헤더로 내보내지 않는다** (2026-08-26 · 35명·69건).
    #   이 통은 「키 운반 통」으로 겸용돼 왔다 — 서버가 산문으로
    #   `headers['asr_keys'] = {제공자: 키}`(**묶음**)를 시켰기 때문이다.
    #   그런데 여기서 그 항목을 그대로 복사해 HTTP 헤더로 내보내는 바람에,
    #   그 세션의 **다른 모든 API 호출**이 `TypeError: expected string or
    #   bytes-like object, got 'dict'` 로 죽었다(현 배포본 4.6시간에도 8회·6명).
    #   ★전사 갈래는 **원본 headers 를 그대로** 보므로 `asr_keys` 는 계속 동작한다.
    #   ★뿌리는 따로 고쳤다 — 서버가 키 **자리**를 데이터로 주고(`key_file`·
    #     `env_var`) 실행기가 거기서 직접 읽는다. 이 줄은 그 뒤에도 남는 안전줄이다.
    out = {k: v for k, v in (headers or {}).items()
           if isinstance(v, (str, bytes))}
    spec = res.get("auth")
    for a in ([spec] if isinstance(spec, dict) else (spec or [])):
        if not isinstance(a, dict) or not a.get("header"):
            continue
        if out.get(a["header"]):
            continue
        try:
            val, key_source = _service_key_value(a)
        except (OSError, UnicodeError):
            raise StepError("키 파일을 읽지 못했습니다. env 단계에서 파일 가져오기를 다시 확인하세요.") from None
        if not val:
            raise StepError(
                f"{a.get('label') or a.get('service')} 키를 찾지 못했습니다 — "
                f"{a.get('key_file')} 또는 환경변수 {a.get('env_var')}. "
                "env 단계를 다시 실행하면 넣는 법을 알려줍니다.")
        # ★**어느 키를 쓰는지 말한다** (2026-08-16 사고).
        #   한 기계에 여러 세션이 살면 `~/.volcano/keys/<서비스>` 를 **전부 공유**한다.
        #   그래서 남의 키로 크레딧을 쓰고도 **아무도 몰랐다** — 주인이 "누가 내
        #   크레딧을 쓴다" 며 키를 지우고 나서야 알았다.
        #   ★키는 **절대 안 찍는다.** 지문(sha256 앞 12자)과 **어디서 읽었는지**만 찍는다.
        #     지문만으로는 키를 되돌릴 수 없고, "이게 내 키가 맞나" 는 대조할 수 있다.
        _src = ("환경변수 " + str(a.get("env_var"))
                if key_source == "env" else str(a.get("key_file")))
        _progress(f"  [키] {a.get('label') or a.get('service')} · "
              f"지문 {hashlib.sha256(val.encode()).hexdigest()[:12]} · {_src}", flush=True)
        out[a["header"]] = (a.get("scheme") or "") + val
    return out


def photo_headers(res, service, headers=None):
    """Resolve only the declared QC service, and only when API fallback is used."""
    def resolve():
        auth = res.get("auth") or []
        auth = [auth] if isinstance(auth, dict) else auth
        selected = [a for a in auth if isinstance(a, dict) and a.get("service") == service]
        try:
            return auth_headers({"auth": selected}, headers)
        except StepError:
            return {}  # image_qc records unchecked; CLI/cache never requires API keys
    return resolve


def _declared_outs(res):
    """서버가 **선언한** 출력 경로 전부. 한 곳에서 모은다 — 자리마다 세면 하나가 빠진다.

    ★argv 를 뜯어 추측하지 않는다(채널마다 갈린다). 서버가 `out`/`out_path` 로
      **선언한 값**만 본다. 선언에 없는 출력은 서버가 말하지 않은 것이고,
      말하지 않은 것을 실행기가 짐작하면 그때부터 결과가 갈린다.
    """
    outs = [res.get("out_path")]
    for coll in ("do", "steps", "jobs", "write_files"):
        for item in res.get(coll) or []:
            if not isinstance(item, dict):
                continue
            outs.append(item.get("out"))
            outs.append(item.get("path"))
            # 일감 안에 다시 단계가 들어 있다(이미지 job 의 copy/normalize).
            for sub in item.get("steps") or []:
                if isinstance(sub, dict):
                    outs.append(sub.get("out"))
    return [p for p in outs if isinstance(p, str) and p]


def _ensure_declared_dirs(res):
    """선언된 출력의 **부모 폴더**를 미리 만든다. ffmpeg 은 폴더를 만들어 주지 않는다.

    ★뇌전구 최종 렌더가 실제로 이것 때문에 죽는다 — 서버는 `out_path` 로
      `<workdir>/out/<slug>_v001.mp4` 를 선언하는데 그 부모를 **아무도 만들지 않아서**,
      처음 돌리는 사람은 프레임을 다 굽고 나서 "No such file or directory" 를 본다.
      서버 전체에서 `out/` 을 만드는 코드가 한 줄도 없다(2026-08-13 전건 확인).
    ★단계마다 `makedirs` 를 흩어 놓지 않는다 — 그렇게 두면 새 단계가 생길 때 빠지고,
      빠진 자리는 **가장 늦게**(다 굽고 난 뒤) 드러난다. 그래서 ①보다 먼저 한 번에 한다.
    """
    seen = []
    for p in _declared_outs(res):
        d = os.path.dirname(p)
        if d and d not in seen:
            os.makedirs(d, exist_ok=True)
            seen.append(d)
    if seen:
        _progress(f"  [출력자리] {len(seen)}곳 준비")


def _carry_into(res, dst, fresh=()):
    """서버가 "이건 그대로 돌려줘라" 고 지정한 값을 옮긴다. 산문으로 말하면 클라가 빠뜨린다.

    ★`need_input` 자리에서도 해야 한다. 거기서 멈춘다고 carry 가 사라지는 게 아니다 —
      그 응답에도 다음 단계가 **대조하는** 값이 실려 있다(뇌전구 `script` 의
      `image_slots`, 어랍숏 `redub_source` 의 `utterances`). 예전에는 `execute()` 안에만
      있었고 `drive` 는 need_input 이면 `execute` 를 타지 않아서, 구동기만 쓰면
      `prompts` 가 "payload.image_slots 가 필요합니다" 로 **반드시** 죽었다(실측).
    ★그래서 두 자리가 같은 함수를 부른다. 코드를 두 벌 두면 언젠가 한쪽만 고쳐진다.
    """
    for key in res.get('payload_discard') or []:
        dst.pop(key, None)
    for k in res.get("carry") or []:
        values = res if k in res else (res.get("next_payload") or {})
        if not isinstance(values, dict) or k not in values:
            raise StepError(f"carry 로 지정된 '{k}' 가 응답에 없다")
        # ★★**방금 잰 값을 덮지 않는다** (2026-08-19).
        #
        #   `carry`("옛 값을 그대로 돌려줘라")와 `measure`("새 값을 만들어라")가
        #   **같은 칸**을 가리키면 그 지시는 자기모순이다. 예전에는 이 줄이
        #   `dst[k] = values[k]` 라서 **옛 값이 이겼고**, A버킷 마스터가 그것 하나로
        #   끝나지 않았다 — 서버가 `peaks['out']` 을 기다리는데 잰 값이 매번
        #   `peaks={'master':…}` 로 덮여 사라졌다(한 명이 12분에 56회, 40회
        #   상한에 닿은 것만 20건·10명).
        #   ★순서를 뒤집어 고칠 수는 없다 — `_carry_into` 는 `need_input` 자리에서도
        #     돌아야 하고(거기선 잰 값이 없다), 측정은 `execute()` 안에만 있다.
        #     그래서 **누가 이기는지를 여기서 못박는다: 방금 잰 값이 이긴다.**
        #   ★둘 다 묶음이면 **합친다** — 그래야 `peaks` 의 `master`(옛)와
        #     `out`(방금 잰 것)이 함께 산다. 어느 한쪽을 버리면 서버가 다른 칸을
        #     못 찾아 또 순환한다.
        #   ★서버도 같은 자리를 고쳤다(모순된 지시를 아예 안 만든다). 여기까지
        #     막는 이유는 **이미 배급된 팩**과 앞으로 생길 다른 자리 때문이다
        #     (§`_keep` 독스트링: "고치는 자리는 규칙과 이 등록 **둘 다**다").
        if k in fresh:
            if isinstance(values[k], dict) and isinstance(dst.get(k), dict):
                merged = dict(values[k])
                merged.update(dst[k])          # 잰 값이 이긴다
                dst[k] = merged
            continue
        dst[k] = values[k]
    return dst


def _carry_after_failure(res, dst, error, fresh=()):
    """Preserve available evidence without turning a failed contract into success.

    Legacy saved replies may declare future outputs that never existed. Record
    that defect on the original exception; only materialized values are saved.
    Normal execution still uses the strict _carry_into contract.

    ★이 왕복이 재라고 한(`measure`) 값을 다 못 잰 채 멈췄으면 응답의 carry 를 옮기지 않는다(2026-10-22 · 군림보 voice
      3건). 응답의 carry 는 «이 왕복을 다 하고 잰 값과 함께 다음 호출에 실을 것» 이다 — 합성 왕복의 `voice_state`
      (stage=rate · «잰 말소리 길이를 볼 차례») 가 그렇다. Typecast 502 로 합성이 멈췄는데 그 값을 옮겨 두니, 다시
      실행할 때 잰 값(voiced_secs) 없이 «잴 차례» 만 가서 서버가 «실행기가 measure 를 싣지 못했다» 로 막았다.
      옮기지 않으면 다음 실행은 이 왕복 전의 payload 로 서버에 새로 묻고(§_release_failed_response), 서버는 같은
      왕복을 다시 낸다(받은 소리는 요청 본문 캐시라 다시 사지 않는다). 사람 차례 멈춤(검수·전사 대기·ASR 준비·
      앞 단계로 돌아가기)은 같은 왕복을 그 자리에서 잇는 것이라 예전대로 옮긴다.
    """
    if not isinstance(error, (ClientReviewPending, TranscriptionPending, ASRSetupRequired, StepBack)):
        have = set(fresh) | set(getattr(error, 'execution_partial', None) or {})
        unmeasured = [r['as'] for r in (res.get('measure') or [])
                      if isinstance(r, dict) and r.get('as') and r['as'] not in have]
        if unmeasured:
            error.round_unmeasured = unmeasured
            return dst
    available, missing = [], []
    for key in res.get('carry') or []:
        values = res if key in res else (res.get('next_payload') or {})
        (available if isinstance(values, dict) and key in values else missing).append(key)
    if missing:
        error.contract_error = "carry 응답 누락: " + ', '.join(str(key) for key in missing)
    _carry_into(dict(res, carry=available), dst, fresh=fresh)
    return dst


def _preserve_execution_failure(c, step, res, payload, source, error):
    partial = getattr(error, 'execution_partial', None)
    _carry_after_failure(res, payload, error)
    if isinstance(partial, dict):
        payload.update(partial)
    recovery = getattr(error, 'execution_recovery', None)
    if isinstance(recovery, dict):
        payload.update(recovery)
    _checkpoint(c, step, payload, source)


def _release_failed_response(c, step, payload, source):
    """실행하다 멈춘 응답의 영수증을 소비한다 — 다음 실행은 같은 단계를 서버에 새로 묻는다(§_drive_loop 실패 갈래 · 2026-10-21).
    받은 응답이 없으면(서버 단계 자체가 실패) 아무것도 하지 않는다. 상태를 먼저 적고(인계 표식 포함) 소비한다."""
    if getattr(c, '_receipt_returned', None) is None:
        return
    try:
        _checkpoint(c, step, payload, source, 'active', response_consumed=True)
        c.acknowledge_response()
    except (OSError, StepError) as error:
        # 소비를 못 적어도 **원래 오류는 그대로 사람에게 간다**(부르는 쪽이 다시 던진다) — 잃는 것은 «다음 실행이 새로 묻기» 뿐이다
        #   (volcano_run `_finish_step` 오류 응답 소비와 같은 약속).
        _progress(f"  [영수증] 멈춘 응답의 영수증을 닫지 못했다({type(error).__name__}) — 같은 명령을 다시 돌리면 이 답이 "
                  "한 번 더 나올 수 있다", flush=True)
    else:
        # 같은 오류가 되풀이돼 보여도 다음 실행은 옛 답을 다시 쓰지 않는다는 것을 사람·작성 AI 가 알게 한다.
        _progress(f"  [영수증] [{step}] 받은 응답으로 끝내지 못해 그 영수증을 닫았다 — 다음 실행은 서버에 새로 묻는다", flush=True)


def _as_of(res, cmd, default):
    """이 명령의 결과를 **서버가 무슨 이름으로 받겠다고 했나**.

    ★응답의 `measure` 에 `{"as": …, "from": "cmd:<이름>"}` 이 있으면 그것을 쓴다.
      없으면 옛 이름으로 물러난다 — 옛 서버와도 돈다.
    ★실행기가 이름을 박으면 **서버가 값을 바꿔도 안 따라온다.** 같은 명령을
      다른 뜻으로 쓰는 단계가 생기는 순간 이름이 갈린다(2026-08-22 실측:
      `shop_cuts` 는 구운 조각, `shop_shots` 는 샷 대표 화면 — 뒤엣것이 앞엣것을 덮었다).
    """
    for r in (res.get("measure") or []):
        if str(r.get("from") or "") == f"cmd:{cmd}" and r.get("as"):
            return str(r["as"])
    return default


def _wav_stamp(path):
    """소리 파일의 **내용 도장** — 같은 소리면 같은 값 (tikitaka m_contts._소리도장).
    sha1 은 보안이 아니라 내용 식별이다(같은 저장소 프레임4 규칙과 같은 자)."""
    h = hashlib.sha1()                                             # noqa: S324
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return {"sha1": h.hexdigest(), "bytes": os.path.getsize(path)}


def _transcribe_cache_load(j):
    """전사 캐시 적중이면 단어열, 아니면 None. **서버가 cache 를 줄 때만** 본다.

    캐시 파일은 두 꼴을 받는다 — ① 이 실행기가 저장한 {provider, words} 묶음
    ② 제공자 원 응답(json-v2 등 · 보존 굽기의 캐시를 그대로 쓸 수 있어야 한다).
    ②는 아는 읽기(_WORD_READER)를 차례로 대 보고 단어가 나오는 것을 쓴다 —
    실행기가 판단하는 것은 「이 응답 꼴을 읽을 수 있는가」뿐이다.
    """
    spec = j.get("cache")
    if not isinstance(spec, dict) or not spec.get("path") or not spec.get("stamp"):
        return None
    if not (os.path.exists(spec["path"]) and os.path.exists(spec["stamp"])
            and os.path.exists(j.get("path") or "")):
        return None
    try:
        with open(spec["stamp"], encoding="utf-8") as fh:
            old = json.load(fh)
    except Exception:                                              # noqa: BLE001
        return None
    if old != _wav_stamp(j["path"]):
        _progress(f"    [전사] {j.get('key')} — 묵은 캐시를 버린다(소리가 바뀌었다)",
              flush=True)
        return None
    try:
        with open(spec["path"], encoding="utf-8") as fh:
            tr = json.load(fh)
    except Exception:                                              # noqa: BLE001
        return None
    if isinstance(tr, dict) and isinstance(tr.get("words"), list) \
            and tr.get("_volcano_cache"):
        return tr["words"]
    from volcano_run import _WORD_READER                           # noqa: PLC0415
    if isinstance(tr, dict):
        for name in _WORD_READER:
            try:
                w = _WORD_READER[name](tr)
            except Exception:                                      # noqa: BLE001
                continue
            if w:
                return w
    return None


def _transcribe_cache_save(j, words, provider):
    """전사 결과를 내용도장과 함께 남긴다 — 같은 소리 재굽기에 유료 전사가
    다시 나가지 않게. 실패해도 조용히 지나간다(캐시는 있으면 좋은 것이다)."""
    spec = j.get("cache")
    if not isinstance(spec, dict) or not spec.get("path") or not spec.get("stamp"):
        return
    try:
        os.makedirs(os.path.dirname(spec["path"]) or ".", exist_ok=True)
        # ★바이트로 쓴다 — 텍스트 모드는 플랫폼이 줄바꿈에 끼어든다(§_write 규율).
        with open(spec["path"], "wb") as fh:
            fh.write(json.dumps({"_volcano_cache": 1, "provider": provider,
                                 "words": words},
                                ensure_ascii=False).encode("utf-8"))
        with open(spec["stamp"], "wb") as fh:
            fh.write(json.dumps(_wav_stamp(j["path"]),
                                ensure_ascii=False).encode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        _progress(f"    [전사] 캐시 저장 실패({type(e).__name__}) — 계속 간다", flush=True)


def _rms_wins(item, path):
    """20ms 창 RMS 레벨(dBFS) — tikitaka `m_pausespec._wins` 의 그 자.

    디코드 argv·표본율·창 크기 전부 **서버 params** 다(실행기가 자를 정하면
    서버가 자를 고쳐도 이 팩이 안 따라온다 — §실행기 규율). numpy 가 없으면
    None — 부르는 쪽이 「못 쟀다」로 다룬다(0 이 아니다).
    """
    try:
        import numpy as np                                         # noqa: PLC0415
    except ImportError:
        return None, None, None
    r = _spawn([path if a == "@IN@" else a for a in item["decode_argv"]],
                       capture_output=True)
    if r.returncode != 0:
        raise StepError(f"소리 되읽기 실패: {path}\n{err_gist(r.stderr, 300)}")
    a = np.frombuffer(r.stdout, np.float32)
    W = int(item["win"])
    n = a.size // W
    if n < 8:
        return None, None, np
    lv = 20 * np.log10(np.sqrt((a[:n * W].reshape(n, W) ** 2).mean(1)) + 1e-12)
    return lv, W / float(item["sr"]), np


def _silence_runs(lv, wsec, thr, min_run):
    """문턱 아래로 이어지는 구간 [(시작초, 길이초)…] — m_gapshape.runs 그대로."""
    out, c = [], 0
    for k, x in enumerate(lv < thr):
        if x:
            c += 1
        elif c:
            out.append(((k - c) * wsec, c * wsec))
            c = 0
    if c:
        out.append(((len(lv) - c) * wsec, c * wsec))
    return [r for r in out if r[1] >= float(min_run)]


def _execution_error_wire(error):
    """Only known control-flow types cross the interpreter boundary."""
    if isinstance(error, ProviderRefusalError):
        return {'type':'ProviderRefusalError', 'origin':error.origin,
                'reason_code':error.reason_code, 'reason':error.reason,
                **({'todo':error.todo} if getattr(error, 'todo', None) is not None else {}),
                **({'code':error.code} if getattr(error, 'code', None) else {}),
                **({'replayed':True} if getattr(error, 'replayed', False) else {}),
                'execution_partial':getattr(error, 'execution_partial', {})}
    if isinstance(error, ClientReviewPending):
        return {'type':'ClientReviewInputError' if isinstance(error, ClientReviewInputError) else 'ClientReviewPending',
                'request':error.request, 'message':str(error),
                'requests':getattr(error, 'requests', [error.request]),
                'execution_partial':getattr(error, 'execution_partial', {})}
    if isinstance(error, ASRSetupRequired):
        return {'type': 'ASRSetupRequired', 'execution_partial': getattr(error, 'execution_partial', {})}
    if isinstance(error, StepBack):
        # «앞 단계로 돌아가기» 는 구동기(부모)가 한다 — 고른 파이썬(자식)에서 난 것도 단계·표지를 실어 넘긴다(없으면 일반 멈춤이 된다).
        return {'type': 'StepBack', 'message': str(error), 'back_to': error.back_to, 'mark': error.mark,
                'payload_add': getattr(error, 'payload_add', None) or {},
                'execution_partial': getattr(error, 'execution_partial', {})}
    if isinstance(error, TranscriptionPending):
        return {"type": "TranscriptionPending", "provider": error.provider,
                "reason": error.reason, "retry_after": error.retry_after, "state_file": error.state_file,
                "execution_partial": getattr(error, 'execution_partial', {})}
    kind = "RejectedError" if isinstance(error, RejectedError) else "StepError" if isinstance(error, StepError) else type(error).__name__
    child_trace = _diagnostic_head_tail("".join(traceback.format_exception(type(error), error, error.__traceback__)), 4000, 2000)
    return {"type": kind, "message": str(error), "traceback": child_trace,
            **{k: getattr(error, k) for k in ("contract", "contract_error", "execution_recovery", "execution_next_step", "execution_partial", "recovery_path", "audio_duration_failure", "input_check_failure", "code", "review_stopped", "resume_lines", "replayed", "errno", "strerror", "filename", "filename2", "winerror", "name", "path")
               if getattr(error, k, None) is not None}}


def _frozen(value):
    """JSON 을 건너온 표지(리스트)를 다시 해시 가능한 튜플로 — 같은 표지 한 번만(StepBack) 을 집합으로 센다."""
    return tuple(_frozen(v) for v in value) if isinstance(value, (list, tuple)) else value


def _raise_execution_error(value):
    if value.get('type') == 'StepBack':
        error = StepBack(value.get('message') or '', value.get('back_to'), _frozen(value.get('mark')))
        error.payload_add = value.get('payload_add') if isinstance(value.get('payload_add'), dict) else {}
        error.execution_partial = value.get('execution_partial') or {}
        raise error
    if value.get('type') == 'ProviderRefusalError':
        error = ProviderRefusalError(value['origin'], value['reason_code'], value['reason'], todo=value.get('todo'))
        if value.get('code'):
            error.code = value['code']
        if value.get('replayed'):
            error.replayed = True
        error.execution_partial = value.get('execution_partial') or {}
        raise error
    if value.get('type') in ('ClientReviewPending', 'ClientReviewInputError'):
        error = (ClientReviewInputError(value['request'], value.get('message') or '검수 답을 수정하세요.')
                 if value['type'] == 'ClientReviewInputError' else ClientReviewPending(value['request']))
        error.requests = value.get('requests') or [error.request]
        error.execution_partial = value.get('execution_partial') or {}
        raise error
    if value.get('type') == 'ASRSetupRequired':
        error = ASRSetupRequired()
        error.execution_partial = value.get('execution_partial') or {}
        raise error
    if value.get("type") == "TranscriptionPending":
        error = TranscriptionPending(value.get("provider"), value.get("reason"),
                                     value.get("retry_after", 0), value.get("state_file"))
        error.execution_partial = value.get('execution_partial') or {}
        raise error
    classes = {"StepError": StepError, "RejectedError": RejectedError,
               "FileNotFoundError": FileNotFoundError, "PermissionError": PermissionError,
               "ModuleNotFoundError": ModuleNotFoundError, "ValueError": ValueError,
               "RuntimeError": RuntimeError}
    cls = classes.get(value.get("type"), RuntimeError)
    message = value.get("message") or "child execution failed"
    if value.get("type") not in classes:
        message = str(value.get("type") or "Exception") + ": " + message
    if issubclass(cls, OSError) and value.get("errno") is not None:
        error = cls(value["errno"], value.get("strerror"), value.get("filename"), value.get("winerror"), value.get("filename2"))
    else:
        error = cls(message)
    error.child_error_type = value.get("type")
    error.child_traceback = value.get("traceback") or ""
    for key in ("contract", "contract_error", "execution_recovery", "execution_next_step", "execution_partial", "recovery_path", "audio_duration_failure", "input_check_failure", "code", "review_stopped", "resume_lines", "replayed", "name", "path"):
        if key in value:
            setattr(error, key, value[key])
    raise error


def _execution_worker():
    """Read one private stdin request; keep progress off the JSON reply stream."""
    import contextlib
    value = json.load(sys.stdin)
    try:
        with contextlib.redirect_stdout(sys.stderr), runtime_metrics.context(value.get('metrics_workdir')), \
                runtime_metrics.stage(value.get('metrics_stage')):
            client = Client(**value['client']) if value.get('client') else None
            result = _execute_current(value['response'], value.get('headers'), client)
        reply = {'ok': True, 'result': result}
        stopped = None
    except BaseException as error:
        # SystemExit·KeyboardInterrupt 도 답을 남긴다 — 답 없이 끝나면 부모는 «종료 코드 1 · N초 뒤» 만 알고
        # 자식 트레이스백(콘솔 stderr)은 자동 신고에 안 실린다(10-23 뇌전구 render_plan 713초 rc1 신고).
        reply = {'ok': False, 'error': _execution_error_wire(error)}
        stopped = None if isinstance(error, Exception) else error
    channel = value.get('reply_channel')

    def publish(answer):
        if channel is None:
            # Legacy direct-worker callers; selected-interpreter execution always
            # supplies a separate channel before importing this module.
            print(json.dumps(answer, ensure_ascii=False))
        else:
            _photo_write_state(channel['path'], dict(
                version=1, identity=channel['identity'], request_sha256=channel['request_sha256'], reply=answer))
    try:
        publish(reply)
    except (TypeError, ValueError) as error:
        # 답을 JSON 으로 못 옮기면(값 종류) 그 사실을 답으로 남긴다 — 일은 끝났으니 부모가 다시 돌리지 않게 «불확실» 로 멈춘다.
        failure = StepError(f"실행 결과를 기록하지 못했습니다({type(error).__name__}: {error}) — 결과 값에 JSON 으로 못 옮기는 값이 있다.")
        failure.__traceback__ = error.__traceback__
        publish({'ok': False, 'error': _execution_error_wire(failure)})
    if stopped is not None:
        raise stopped


def _execute_selected_python(selected, res, headers, c):
    # The executable is the one readiness actually inspected. Do not use realpath:
    # virtual environments often point to the same binary but import different modules.
    if not os.path.isabs(selected) or not os.path.isfile(selected):
        raise StepError("검증된 Python 실행 파일을 찾지 못했습니다. env 단계를 다시 실행하세요: " + selected)
    client = None
    if c is not None and getattr(c, "url", None):
        client = {k: getattr(c, k) for k in ("url", "token", "preset", "timeout", "tool") if hasattr(c, k)}
    wire = {"response": res, "headers": headers, "client": client,
            "metrics_workdir": runtime_metrics.current(), "metrics_stage": runtime_metrics.current_stage()}
    # Native libraries and interpreter startup can write fd 1 despite Python's
    # redirect_stdout. Never parse that diagnostic stream as execution data.
    # Each invocation owns a fresh private directory; a failed/unknown outcome
    # retains its reply (including paid receipts) and must not rerun the work.
    from longform_state import native_path
    import secrets
    raw = json.dumps(wire, ensure_ascii=False,
                     default=lambda v: v.decode('utf-8') if isinstance(v, bytes) else (_ for _ in ()).throw(TypeError(type(v).__name__)))
    directory = native_path(tempfile.mkdtemp(prefix='volcano-execution-'))
    path = directory / 'reply.json'
    channel = {'path': str(path), 'identity': secrets.token_hex(32),
               'request_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest()}
    wire['reply_channel'] = channel
    raw = json.dumps(wire, ensure_ascii=False,
                     default=lambda v: v.decode('utf-8') if isinstance(v, bytes) else (_ for _ in ()).throw(TypeError(type(v).__name__)))
    script = "import sys;sys.path.insert(0,sys.argv[1]);import volcano_drive as d;d._execution_worker()"
    def unknown(reason):
        error = StepError(reason + " 완료 여부가 불확실하여 자동 재실행하지 않았습니다. "
                          "기존 접수 기록과 결과를 확인하세요. 실행 결과 보존 폴더: " + str(directory))
        error.execution_result_path = str(path)
        return error
    started = time.monotonic()
    try:
        process = _spawn([selected, "-c", script, os.path.dirname(os.path.abspath(__file__))],
                         input=raw, stdout=subprocess.DEVNULL,
                         env=dict(os.environ, PYTHONIOENCODING='utf-8'), **TEXT_PIPE)
    except Exception as error:
        raise unknown("검증된 Python의 실행 종료를 확인하지 못했습니다.") from error
    try:
        with path.open('r', encoding='utf-8') as stream:
            envelope = json.load(stream)
        if (not isinstance(envelope, dict) or envelope.get('version') != 1
                or envelope.get('identity') != channel['identity']
                or envelope.get('request_sha256') != channel['request_sha256']):
            raise ValueError('execution reply identity')
        reply = envelope.get('reply')
        if not isinstance(reply, dict) or type(reply.get('ok')) is not bool:
            raise ValueError('execution reply shape')
        if reply['ok'] and not isinstance(reply.get('result'), dict):
            raise ValueError('execution result shape')
        if not reply['ok'] and not isinstance(reply.get('error'), dict):
            raise ValueError('execution error shape')
    except (OSError, TypeError, ValueError) as error:
        # 종료 코드의 뜻(윈도우 0xC000013A = 콘솔 닫힘·Ctrl+C 등)과 걸린 시간을 함께 말한다 — 출력 없이 끝난 자식의 남은 증거다(10-20 뇌전구 render_plan).
        from volcano_run import _rc_text
        raise unknown(f"검증된 Python의 실행 결과를 확인하지 못했습니다(종료 코드 {_rc_text(process.returncode)} · "
                      f"시작 {round(time.monotonic() - started, 1)}초 뒤 끝남).") from error
    # Even if teardown failed after publication, the completed response is
    # authoritative. Do not discard it and invite a second paid submission.
    # Keep the original file through return/error propagation: a parent crash
    # between this boundary and its checkpoint must not erase the only copy.
    if not reply['ok']:
        try:
            _raise_execution_error(reply.get('error') or {})
        except Exception as error:
            error.execution_result_path = str(path)
            raise
    if not isinstance(reply.get('result'), dict):
        raise StepError("검증된 Python이 측정 결과 묶음을 반환하지 않았습니다.")
    return reply['result']


def execute(res, headers=None, c=None):
    """Observe native execution, including exceptions and selected-Python work."""
    with runtime_metrics.context(res.get('workdir') or (res.get('next_payload') or {}).get('workdir')):
        try:
            with runtime_metrics.span('execute'):
                return _execute_plan(res, headers, c)
        finally:
            runtime_metrics.export()


def _execute_plan(res, headers=None, c=None):
    """Run the issued plan in its verified environment and preserve failure state."""
    try:
        selected = res.get('python')
        if (isinstance(selected, str) and selected
                and os.path.normcase(os.path.abspath(selected)) != os.path.normcase(os.path.abspath(sys.executable))):
            result = _execute_selected_python(selected, res, headers, c)
        else:
            result = _execute_current(res, headers, c)
        recovery = res.get('execution_recovery') or {}
        field = {'film_frame_state': 'film_probe_frames', 'film_recovery_state': 'film_recovery_frames',
                 'film_semantic_state': 'film_semantic_frames', 'focus_state': 'focus_frames',
                 'photo_text_state': 'photo_text_results'}.get(recovery.get('state'))
        measured = result.get(field) if field else None
        if isinstance(measured, dict):
            failures = {k: v.get('_error') for k, v in measured.items() if isinstance(v, dict) and v.get('_error')}
            if measured.get('_error'):
                failures['_error'] = measured['_error']
            if failures:
                error = StepError('화면 측정 실행 실패: ' + '; '.join(str(k) + ': ' + str(v) for k, v in failures.items()))
                error.execution_partial = {field: {k: v for k, v in measured.items()
                    if k != '_error' and isinstance(v, dict) and not v.get('_error')}}
                raise error
        return result
    except (RejectedError, ProviderRefusalError, TranscriptionPending, ASRSetupRequired, ClientReviewPending):
        raise  # A quality refusal or pending paid request never authorizes another measurement.
    except Exception as error:
        if getattr(error, 'review_stopped', False):
            raise  # An explicit review stop is not a failed measurement to recover.
        # A failed import needs the existing environment probe before another
        # measurement. Do not classify a quality refusal or missing result this way.
        missing = []
        if isinstance(error, ModuleNotFoundError):
            missing = [getattr(error, 'name', None)]
        if isinstance(error, ModuleNotFoundError) or str(error).startswith('화면 측정 실행 실패:'):
            import re
            missing += re.findall(r"No module named ['\"]([A-Za-z_][A-Za-z0-9_.]*)['\"]", str(error))
        missing = sorted({name.split('.')[0] for name in missing if isinstance(name, str) and name})
        if missing:
            error.execution_recovery = dict(getattr(error, 'execution_recovery', None) or {},
                execution_environment_error={'modules': missing, 'driver_python': sys.executable})
        recovery = res.get('execution_recovery') or {}
        state_name = recovery.get('state')
        state = (res.get(state_name) or (res.get('next_payload') or {}).get(state_name)) if isinstance(state_name, str) else None
        if (state_name in ('film_frame_state', 'film_recovery_state', 'film_semantic_state', 'focus_state', 'photo_text_state')
                and isinstance(state, dict) and state.get('key') == recovery.get('key')):
            error.execution_recovery = {
                **(getattr(error, 'execution_partial', None) or {}),
                state_name: dict(state, execution_failed=True),
                **(getattr(error, 'execution_recovery', None) or {})}
        raise


#: 검수 답의 두 칸 이름 — 서버 `volcano_review_policy.REPLY_FIELDS`·`ACTIVE_FIELD` 와 같은 낱말이다.
_REVIEW_REPLY_FIELDS = ('focus_review_replies', 'review_replies')


def _review_reply_field(payload):
    """사람(모델)에게 «여기에 답하라» 고 말할 칸 — payload 의 정본 칸 표식(`review_reply_field` · 서버가 carry)을 따른다.

    ★왜 (2026-10-05 · 원장 W2-14 · 23건·8명): 예전 정지문은 언제나 `review_replies` 를 시켰다. 서버는 답을 정본 칸
      (`focus_review_replies` 일 때가 있다)에 모아 두므로, 호스트가 이미 답한 요청에 **다른 칸**으로 또 답해 같은 SHA 에
      두 답이 생겼고 서버·실행기가 «서로 다른 답» 으로 막혔다. 정본 칸에 쓰면 같은 칸의 같은 SHA 를 고쳐 쓰는 것이라
      충돌이 생기지 않는다. 표식이 없으면(옛 서버) 예전처럼 review_replies."""
    field = (payload or {}).get('review_reply_field')
    return field if field in _REVIEW_REPLY_FIELDS else 'review_replies'


def _execute_current(res, headers=None, c=None):
    """Bind the public review selection inside either Python interpreter.

    ★검수 답의 권위는 서버가 모은 답 지도(`res['review']['replies']` · `volcano_review_policy.attach_response`)다
      (2026-10-05 검토 2회차 · 원장 «두 벌 금지»). 서버가 두 칸(focus_review_replies·review_replies)의 충돌을 정해진
      순서(거절된 답 제외 → 요청 형식 → 나중 답 → 예비)로 이미 풀어 그 지도와 정본 칸에 실었다 — 실행기가 같은 규칙의
      둘째 판을 갖고 따로 고르면 서버와 다른 답을 고를 수 있다. 그래서
        · 서버 지도가 있으면: 응답 뿌리의 두 칸에서는 **지도에 없는 SHA 의 답만** 보탠다. 지도와 다른 답은 버리고 알린다.
        · 서버 지도가 없으면(옛 응답·로컬 인계): 예전 그대로 — 두 칸이 다르면 고치라고 멈춘다(실행기가 고르지 않는다).
    """
    from volcano_run import review_context, resolve_review_replies, _close_google
    config = res.get('review') or {}
    authority = config.get('replies') if isinstance(config.get('replies'), dict) else None
    try:
        replies = {}
        ignored = 0
        for field in ('review_replies', 'focus_review_replies'):
            value = res.get(field)
            if value is None:
                continue
            if not isinstance(value, dict):
                raise StepError('검수 답은 요청 SHA별 객체여야 합니다.')
            for key, answer in value.items():
                if authority is not None and key in authority:
                    if authority[key] != answer:
                        ignored += 1
                    continue
                if key in replies and replies[key] != answer:
                    raise StepError('같은 검수 요청 SHA에 서로 다른 답이 있습니다. 응답의 답을 일치시켜 주세요.')
                replies[key] = answer
        if ignored:
            _progress('  [검수 답] 서버가 고른 답과 다른 답 ' + str(ignored) + '건은 쓰지 않았습니다 — 서버가 두 칸의 충돌을 '
                      '규칙으로 풀어 고른 답(review.replies)을 씁니다.', flush=True)
        with review_context(policy=config.get('policy'), client=config.get('client'),
                            replies=config.get('replies'), budget=config.get('budget')):
            # Older/local response handoffs carry answers at the response root.
            # Merge evidence without changing the authoritative client/policy.
            with review_context(replies=resolve_review_replies(replies)):
                return _execute_source_checked(res, headers, c)
    finally:
        # Share one browser across this response's search jobs, then release it
        # on success, error, interruption and review handoff alike.
        _close_google()


def _execute_source_checked(res, headers=None, c=None):
    if res.get('local_source_plan'):
        from local_source_plan import verify_inputs
        local_sources=verify_inputs(res['local_source_plan'],res.get('local_source_inputs') or {})
        res=dict(res,source_checks=[*(res.get('source_checks') or []),*local_sources])
    """Bind every selected geometry to the current source bytes during execution."""
    from volcano_run import _ArgvInputDigests
    if res.get('longform_source_check'):
        from longform_source_revision import check as check_longform_sources
        res = dict(res, source_checks=[*(res.get('source_checks') or []), *check_longform_sources(res)])
    if res.get('local_shop_plan'):
        from local_shop_plan import verify_proof, delivery_files
        res = dict(res, source_checks=[*(res.get('source_checks') or []), *verify_proof(res['local_shop_plan'])])
        if res.get('local_shop_delivery'):
            res = dict(res,write_files=[*(res.get('write_files') or []),*delivery_files(res['local_shop_delivery'])])
    if res.get('local_person_plan'):
        from local_person_plan import expand_response
        res=expand_response(res)
    if res.get('local_redub_plan'):
        from local_redub_plan import verify_proof
        res = dict(res, source_checks=[*(res.get('source_checks') or []), *verify_proof(res['local_redub_plan'])])
    if res.get('local_render_plan'):
        from local_render_plan import verify_render_plan
        local_sources = verify_render_plan(res['local_render_plan'])
        res = dict(res, source_checks=[*(res.get('source_checks') or []), *local_sources])
    checks = res.get('source_checks') or []
    runtime_checks = res.get('focus_runtime_checks') or []
    input_checks = res.get('input_checks') or []
    if not checks and not runtime_checks and not input_checks:
        return _execute_unchecked(res, headers, c)
    def check_sources(sources):
        try:
            for item in input_checks:
                if sources.digest(item['path']) != item['sha256']:
                    raise StepError('측정 이후 입력 파일이 바뀌었습니다: ' + item['path'])
        except (OSError, StepError) as error:
            recovery = res.get('input_check_recovery') or {}
            error.execution_recovery = dict(recovery.get('payload') or {})
            error.input_check_failure = True
            raise
        try:
            if runtime_checks:
                import subject_focus
                for runtime in runtime_checks:
                    current = subject_focus._detector_identity(runtime['root'])
                    identity = hashlib.sha256(json.dumps(current, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                    if identity != runtime['identity'] or runtime['algorithm'] != subject_focus.ALGORITHM_VERSION:
                        raise StepError('피사체 선택 뒤 검출 모델·환경이 바뀌었습니다. 현재 단계로 재개하면 새 환경에서 재확인합니다.')
            for item in checks:
                if sources.digest(item['path']) != item['sha256']:
                    raise StepError('피사체를 선택한 뒤 원본 파일이 바뀌었습니다: ' + item['path']
                                    + '. 현재 단계로 재개하면 현재 원본을 다시 확인합니다.')
        except (OSError, StepError) as error:
            # The caller checkpoints this before surfacing the failure. Completed
            # paid work remains in the selector's content-addressed disk cache.
            error.execution_recovery = dict(focus_measurements={}, focus_frames={},
                                            focus_state={}, frames={}, person_frame_key='',
                                            focus_render_key='')
            raise
    with _ArgvInputDigests() as sources:
        check_sources(sources)
        result = _execute_unchecked(res, headers, c)
        check_sources(sources)
        return result


def _execute_unchecked(res, headers=None, c=None):
    """Keep completed measurements when a model review interrupts a recipe."""
    got, outs = {}, {}
    try:
        return _execute_instructions(res, headers, c, got, outs)
    except Exception as error:
        # Capture every completed output, including a strict carry failure after
        # successful measurements. Pending/refused work must never be repeated.
        measured = [rule for rule in res.get('measure') or []
                    if str(rule.get('from') or '').split(':', 1)[0] in ('cmd', 'cmds')
                    and str(rule.get('from')).split(':', 1)[1] in outs]
        try:
            got.update(_measure(res, measured, outs))
        except Exception as measurement_error:
            error.partial_measurement_error = str(measurement_error)
        _carry_after_failure(res, got, error, fresh=set(got))
        error.execution_partial = dict(got, **getattr(error, 'execution_partial', {}))
        raise


def _child_review_control(stdout):
    """A child review may wait or stop; neither is successful command output."""
    try:
        value = json.loads(stdout)
    except (ValueError, TypeError):
        return
    if not isinstance(value, dict):
        return
    if value.get('status') == 'review_stopped':
        if value.get('code') == 'provider_refused' and all(
                isinstance(value.get(key), str) and value[key] for key in ('origin', 'reason_code', 'reason')):
            _raise_execution_error(dict(value, type='ProviderRefusalError'))
        error = StepError(str(value.get('why') or '검수가 중단되었습니다. 같은 단계의 중단 원인을 확인하세요.'))
        error.code = value.get('code') or 'review_failed'
        error.review_stopped = True
        raise error
    if value.get('status') != 'client_review_pending':
        return
    requests = value.get('review_requests')
    if not isinstance(requests, list) or not requests or any(
            not isinstance(item, dict) or not item.get('request_sha256') for item in requests):
        raise StepError('자식 검수 대기 응답에 요청 SHA와 실제 자료가 없습니다.')
    problem = requests[0].get('reply_error') or {}
    error = (ClientReviewInputError(requests[0], problem.get('message') or '검수 답을 수정하세요.')
             if problem.get('code') == 'client_review_reply_invalid' else ClientReviewPending(requests[0]))
    error.requests = requests
    raise error


def _ver_tuple(v):
    """yt-dlp 판 글자(2026.10.10 · 야간판 2026.10.10.233141) → 앞 세 칸 숫자. 못 읽으면 None."""
    try:
        parts = [int(x) for x in str(v).strip().split(".")[:3]]
        return tuple(parts) if len(parts) == 3 else None
    except ValueError:
        return None


def _ytdlp_latest_version():
    """공식 최신 판(GitHub releases/latest 의 tag_name) — 실패할 때 **한 번만** 묻는다. 못 물으면 None(모른다)."""
    import urllib.request
    try:
        req = urllib.request.Request("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
                                     headers={"User-Agent": "volcano-runner", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return str(json.loads(r.read().decode("utf-8")).get("tag_name") or "").strip() or None
    except Exception:                                              # noqa: BLE001
        return None


def _tool_failure_hint(tool, stderr):
    """yt-dlp 가 실패했을 때 **왜**를 — stderr 가 실제로 말한 것만 갈라 맞는 처방을 붙인다.

    ★예전에는 403 이면 늘 «판이 오래됐다 · 갱신하라» 하나였다(2026-09-17 win-01 실측: 2026.03.17 판 403 ·
      2026.08.19 판 정상). 그런데 최신 판(2026.10.10)에서도 403 이 났고, 갱신해도 못 빠져나갔다(신고 #52 · 9명).
      원인이 여럿이라 한 원인으로 단정하면 사람에게 헛일을 시킨다 → 갈래마다 그 말이 있을 때만 말한다.
      · JS 실행기 없음 — 2025-11 부터 yt-dlp 가 유튜브 JS 풀이에 외부 JS 실행기(deno 권장)를 요구한다
        (공식 https://github.com/yt-dlp/yt-dlp/wiki/EJS · 경고 «No supported JavaScript runtime could be found»)
      · 풀이 스크립트(yt-dlp-ejs) 없음 — «challenge solver script … skipped» · «n challenge solving failed»
      · 봇 확인 «Sign in to confirm» — 브라우저 쿠키 · PO 토큰 — 공식 PO-Token-Guide
      · 판 — 403 이고 위 갈래가 없을 때, 설치된 판이 공식 최신보다 낮을 때만 «갱신». 최신이면 갱신을 말하지 않는다.
    """
    base = os.path.basename(str(tool)).lower()
    if not base.startswith("yt-dlp"):
        return ""
    low = (stderr or "").lower()
    js_missing = "no supported javascript runtime" in low
    solver = ("challenge solver script" in low or "remote component" in low
              or "challenge solving failed" in low or "signature extraction failed" in low)
    bot = "sign in to confirm" in low
    pot = "po token" in low or "po_token" in low
    blocked = "http error 403" in low or "unable to download video data" in low
    # ★«Unsupported URL» = 주소 모양이 영상 페이지가 아니다(2026-10-23 린박스 신고: 회원이 `https://youtu.be/--` 를 넣어
    #   yt-dlp 가 일반 추출기로 넘긴 뒤 이 말로 끝났다 — 무엇을 고쳐야 하는지 말하지 않았다). 판·쿠키 문제가 아니라 주소 문제다.
    import re                                                     # noqa: PLC0415
    unsupported = re.search(r"unsupported url:\s*(\S+)", stderr or "", re.IGNORECASE)
    if not (js_missing or solver or bot or pot or blocked or unsupported):
        return ""
    nt = os.name == "nt"
    cfg = r"%APPDATA%\yt-dlp\config" if nt else "~/.config/yt-dlp/config"
    out = []
    if unsupported:
        out.append("yt-dlp 가 이 주소를 영상 페이지로 알아보지 못했습니다(" + unsupported.group(1) + ") — 판·쿠키 문제가 아니라 주소 문제입니다. "
                   "유튜브면 영상 ID(11자)가 든 주소 전체(youtube.com/watch?v=11자 · youtu.be/11자 · youtube.com/shorts/11자)를 "
                   "브라우저 주소창이나 «공유 → 링크 복사» 에서 그대로 옮겨 source.url 에 넣고 start 부터 다시 부르세요.")
    if js_missing:
        out.append("JS 실행기가 없습니다 — yt-dlp 는 유튜브 영상을 받을 때 JS 실행기(deno 권장)가 필요합니다. "
                   + ("winget install DenoLand.Deno" if nt else "brew install deno")
                   + " 로 깔고 새 창에서 같은 단계를 다시 부르세요(공식 안내 https://github.com/yt-dlp/yt-dlp/wiki/EJS).")
    if solver:
        out.append("유튜브 JS 풀이에 실패했습니다(풀이 스크립트 yt-dlp-ejs 가 없거나 JS 실행기가 없음) — yt-dlp 공식 실행 파일에는 "
                   "풀이 스크립트가 들어 있습니다. pip 로 깔았으면 pip install -U \"yt-dlp[default]\" · 그 밖이면 yt-dlp 설정 파일("
                   + cfg + ")에 «--remote-components ejs:github» 한 줄(공식 안내 https://github.com/yt-dlp/yt-dlp/wiki/EJS).")
    if bot:
        out.append("유튜브가 봇 확인(로그인)을 요구합니다 — 판 갱신으로는 안 풀립니다. 유튜브에 로그인된 브라우저의 쿠키를 쓰게 "
                   "yt-dlp 설정 파일(" + cfg + ")에 «--cookies-from-browser chrome»(엣지면 edge) 한 줄을 넣고 다시 부르세요.")
    if pot:
        out.append("유튜브가 PO 토큰을 요구합니다 — 공식 안내 https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide")
    if blocked and not (js_missing or solver or bot or pot):
        ver = ""
        try:
            v = run_argv([tool, "--version"], capture=True)
            ver = ((v.stdout or "").strip().splitlines() or [""])[0][:24]
        except Exception:                                              # noqa: BLE001
            ver = ""
        latest = _ytdlp_latest_version()
        have, top = _ver_tuple(ver), _ver_tuple(latest)
        upd = ("winget upgrade yt-dlp.yt-dlp" if nt else "brew upgrade yt-dlp") + " (또는 yt-dlp -U)"
        if have and top and have >= top:
            out.append(f"설치된 yt-dlp({ver})는 이미 공식 최신 판({latest})입니다 — 판 문제가 아닙니다. 위 오류 바로 앞의 "
                       "WARNING 줄(JS 실행기 · 풀이 · 봇 확인 · PO 토큰)을 보세요. 아무 경고가 없으면 deno 를 깔고("
                       + ("winget install DenoLand.Deno" if nt else "brew install deno")
                       + ") 다시 부르세요(공식 안내 https://github.com/yt-dlp/yt-dlp/wiki/EJS).")
        elif have and top:
            out.append(f"설치된 yt-dlp({ver})가 공식 최신 판({latest})보다 오래됐습니다 — 유튜브가 옛 판을 403 으로 막습니다. "
                       f"갱신하세요: {upd} · 갱신한 뒤 같은 단계를 다시 부르면 됩니다.")
        else:
            out.append("HTTP 403 — 최신 판을 확인하지 못했습니다"
                       + (f"(설치된 판: {ver})" if ver else "")
                       + f". 판이 오래됐으면 갱신하세요: {upd}. 이미 최신이면 deno 를 깔고("
                       + ("winget install DenoLand.Deno" if nt else "brew install deno")
                       + ") 다시 부르세요(공식 안내 https://github.com/yt-dlp/yt-dlp/wiki/EJS).")
    return "".join("\n  ★" + x for x in out)


class CaptionInputsChanged(StepBack):
    """측정한 사용자 자막·글꼴이 굽기 전에 없거나 바뀌었다 — 구동기가 subtitle 단계로 돌아가 다시 만든다(신고 #32)."""

    def __init__(self, message, path, sha):
        super().__init__(message, 'subtitle', (path, sha))
        self.path, self.sha = path, sha


def _execute_instructions(res, headers, c, got, outs):
    """응답 하나가 시키는 **기계적인 일**을 전부 하고, 측정 결과를 돌려준다.

    ★순서가 규격이다 — 명령이 쓸 **입력을 먼저 만든다.**
      ① 검사(check_photo)   돈·시간 쓰기 전에 막는다
      ② 파일 쓰기            ffmpeg 이 읽을 concat/자막을 먼저 만든다
      ③ 프레임 굽기          concat 이 가리키는 그림을 만든다
      ④ 일감(jobs)          TTS·이미지·블록 인코드
      ⑤ 명령(do 의 argv)     위 결과를 소비한다
      ⑥ concat/최종 argv → 확인 → 측정
      실제로 ⑤를 ②③보다 먼저 돌렸다가 "vconcat.txt 가 없다" 로 죽었다.
    """
    # ⓪ 출력 자리 — **아무것도 만들기 전에.** 다 굽고 나서 폴더가 없어 죽는 것을 막는다
    # ★★실행기용 출입증 (2026-09-02) — 서버가 `assets` 응답에 실어 준다. 여기서 저장해 두면
    #   `python volcano_drive.py --workdir …` 한 줄이 서버를 직접 부르며 끝까지 돈다.
    _rk = res.get("runner_key")
    if isinstance(_rk, dict) and _rk.get("token"):
        _wd = res.get('workdir')
        if _wd is not None:
            if not isinstance(_wd, str) or not os.path.isabs(_wd):
                raise StepError('실행기 출입증을 저장할 workdir 는 절대경로여야 합니다.')
        else:
            _wd = next((i.get("extract_to") for i in (res.get("do") or [])
                        if isinstance(i, dict) and i.get("cmd") == "fetch_asset" and i.get("extract_to")
                        and i.get("extract_to") != "."), None) or os.getcwd()
        save_runner_key(_rk, _wd)

    _ensure_declared_dirs(res)

    # User media identity is checked before any paid work or rendering.
    for item in res.get("do") or []:
        if item.get("cmd") == "verify_custom_media":
            verify_custom_media(item)
        elif item.get("cmd") == "prepare_custom_media":
            got["custom_media_receipts"] = prepare_custom_media(item)
            _keep(outs, "prepare_custom_media", got["custom_media_receipts"])
        elif item.get("cmd") == "probe_custom_media":
            got["customization_media_probe"] = probe_custom_media(item)
            _keep(outs, "probe_custom_media", got["customization_media_probe"])

    # ① 검사
    # ★사진 중복 방지 집합 — **payload 에 넣지 않는다**(set 은 JSON 이 아니고,
    #   이 통은 그대로 서버로 나간다). 이 실행 안에서만 산다.
    _photo_seen = set()
    # ★굽기가 읽는 팩(only_if_missing · 서버 `_attach_render_packs`)은 검사(글꼴 확인)보다 **먼저** 확보한다 — 글꼴 확인이 «글꼴 폴더에
    #   번들 글꼴이 없다» 로 멈추기 전에 빠진 글꼴을 되살린다. 다 있으면 os.path.exists 만 하고 지나간다(⑤ 의 같은 항목도 마찬가지).
    for item in res.get("do") or []:
        if item.get("cmd") == "fetch_asset" and isinstance(item.get("only_if_missing"), list):
            _fetch_asset(item, c)
    for item in res.get("do") or []:
        if item.get('cmd') == 'check_custom_fonts':
            for font in item['fonts']:
                try:
                    with open(font['font_file'],'rb') as body:actual=hashlib.sha256(body.read()).hexdigest()
                except OSError as exc:raise StepError(f"사용자 글꼴 파일이 없습니다: {font['font_file']}") from exc
                if actual!=font['sha256']:
                    why = '사용자 글꼴이 측정 뒤 바뀌었습니다. subtitle을 다시 실행하세요.'
                    # sub.ass 를 함께 대조하는 검사(공통 subtitle 단계가 만든 것)만 실행기가 그 단계로 되돌린다 — 다른 채널 검사는 예전대로.
                    raise CaptionInputsChanged(why, font['font_file'], actual) if item.get('subtitle') else StepError(why)
            subtitle = item.get('subtitle')
            if subtitle:
                try:
                    with open(subtitle['path'], 'rb') as body:
                        actual = hashlib.sha256(body.read()).hexdigest()
                except OSError as exc:
                    raise CaptionInputsChanged('측정한 사용자 자막 파일이 없습니다. subtitle을 다시 실행하세요.',
                                               subtitle['path'], None) from exc
                if actual != subtitle['sha256']:
                    raise CaptionInputsChanged('현재 문구·스타일·실측값과 sub.ass가 다릅니다. subtitle을 다시 실행하세요.',
                                               subtitle['path'], actual)
        if item.get("cmd") == "check_fonts":
            # ★명령은 서버가 지었다. 실행기는 돌리고 **잉크를 재서 비교**만 한다.
            for w in item.get("write") or []:
                _write(w, "글꼴프로브")
            # ★이름 조회 **전에** 파일이 있는지 본다. macOS 의 libass 는 CoreText 로
            #   찾아서 `fontsdir` 이 격리가 아니라 **추가**다 — 기계에 그 글꼴이 깔려
            #   있으면 **빈 폴더로도 조회가 통과한다.** 그러면 팩이 안 풀린 것을
            #   못 보고 "글꼴 확인 통과" 라는 거짓 안심만 남는다.
            fdir = item.get("dir")
            want_files = item.get("files") or []
            if fdir and want_files:
                have = set(os.listdir(fdir)) if os.path.isdir(fdir) else set()
                missing = [f for f in want_files if f not in have]
                if missing:
                    raise StepError(
                        f"글꼴 폴더에 번들 글꼴이 없다: {missing}\n"
                        f"  폴더: {fdir} (파일 {len(have)}개)\n"
                        f"  {item.get('files_note') or ''}\n"
                        "  ★이름 조회만으로는 못 잡는다 — macOS 는 기계에 깔린 글꼴로 "
                        "답해서 **빈 폴더도 통과**한다.")
                _progress(f"  [글꼴파일] 번들 {len(want_files)}개 확인")
            inks, checked, bad = {}, set(), []
            for pr in item.get("probes") or []:
                rendered = run_argv(pr["argv"])
                inks[pr["name"]] = _ink_box(pr["out"])
                if pr.get("font_file"):
                    checked.add(pr["name"])
                    if not inks[pr["name"]] or not _font_selected(pr, rendered.stderr):
                        bad.append(pr["name"])
            sent = inks.get(item["sentinel"])
            bad.extend(n for n, v in inks.items()
                       if n != item["sentinel"] and n not in checked and (v is None or v == sent))
            if bad:
                raise StepError(
                    f"글꼴을 libass 가 못 찾는다: {bad}\n"
                    f"  (요청한 글꼴과 실제 선택이 다르거나 확인할 수 없다)\n"
                    f"  {item.get('note') or ''}\n"
                    "  ★이대로 렌더하면 **오류 없이 다른 글꼴로** 그려진다.")
            if inks:
                _progress(f"  [글꼴확인] {len(inks) - 1}종 전부 잡힌다")
        if item.get("cmd") == "check_photo":
            review_headers = photo_headers(res, (item.get("photo_review") or {}).get("service"), headers)
            recovery_auth = (item.get("recovery") or {}).get("auth")
            # A client review may pass without any key. Only an actual repair
            # resolves the generator's independently declared credential.
            generation_headers = review_headers  # older issued recipes
            if recovery_auth:
                generation_headers = lambda auth=recovery_auth: auth_headers({"auth": auth}, headers)
            got["photo_check"] = check_photo(item, review_headers, generation_headers=generation_headers)
            _progress(f"  [사진확인] {got['photo_check']['checked']}장 통과"
                  f" · 재검수 {len(got['photo_check']['reviewed'])}"
                  f" · 해당 슬롯 복구 {len(got['photo_check']['repaired'])}")

    # Old issued plans contain an unsafe, unjournaled client. Obtain the current
    # same-step plan before executing; never silently repeat its paid POSTs.
    for item in list(res.get("do") or []) + list(res.get("jobs") or []):
        if item.get("cmd") == "vmake_clear" and not all(item.get(k) for k in ("receipt", "script", "out")):
            raise StepError("이 Vmake 계획에는 접수 기록 계약이 없습니다. 같은 source 단계에서 새 계획을 받아 실행하세요. 기존 파일은 보존했습니다.")

    # Preserve evidence of a pre-receipt Vmake attempt before replacing its script.
    # Without input/output provenance, an old result stays unclaimed and no new POST is sent.
    for item in list(res.get("do") or []) + list(res.get("jobs") or []):
        if item.get("cmd") == "vmake_clear" and item.get("receipt") and item.get("script"):
            script = item["script"]
            if os.path.isfile(script):
                with open(script, "rb") as old:
                    durable = b"RECEIPT_VERSION = 1\n" in old.read()
                if not durable:
                    marker = item["receipt"] + ".legacy"
                    os.makedirs(os.path.dirname(marker) or ".", exist_ok=True)
                    with open(marker, "ab") as fh:
                        fh.write(b"pre-receipt script present\n")
                        fh.flush()
                        os.fsync(fh.fileno())

    # ② 파일
    for w in res.get("write_files") or []:
        _write(w, "파일")
        if w.get("sha256"):
            with open(w["path"], "rb") as written:
                got_h = hashlib.sha256(written.read()).hexdigest()
            if got_h != w["sha256"]:
                raise StepError(f"쓴 파일의 sha256 이 다르다: {w['path']}\n"
                                f"  쓴 것 {got_h}\n  기대  {w['sha256']}")

    # ③ 프레임 — 검증한 로컬 계획 또는 기존 서버 계획을 그대로 적용한다.
    # ★★`frames_file` — 프레임 지시서를 **파일로** 받는 길 (2026-09-01 수강생 신고:
    #   render_plan 응답이 5만자를 넘어 MCP 토큰 한도에 잘렸다). 서버가
    #   `payload.compact_plan` 요청을 받으면 지시서를 write_files 로 내리고 이
    #   칸에 경로만 싣는다 — 위 `_write` 가 이미 그 파일을 썼다.
    _frames = res.get("frames")
    if not _frames and res.get("frames_file"):
        with open(res["frames_file"], encoding="utf-8") as _ff:
            _frames = json.load(_ff)
        _progress(f"  [프레임] 지시서 파일에서 {len(_frames)}건 읽음")
    if _frames:
        # ★run 서술자가 섞이면 낱장 수는 전개 뒤에야 안다 — bake_frames 가 말한다.
        _progress(f"  [프레임] 항목 {len(_frames)}건 굽는다")
        # ★폭은 **서버가 준다**(`bake_parallel`). 없으면 직렬이다 — 여기서 정하지 않는다.
        bake_frames(_frames, parallel=res.get("bake_parallel"))

    # ④ 일감
    if res.get("jobs"):
        j0 = res["jobs"][0]
        # ★종류는 **서버가 선언한다.** 모양을 보고 추측하면 키가 하나 늘어나는 순간
        #   조용히 다른 처리기로 샌다(실제로 이미지 job 에 steps 가 생기자 그렇게 됐다).
        #   선언이 없으면 옛 서버다 — 모양으로 떨어지되 그 사실을 **말한다.**
        kind = res.get("jobs_kind")
        if not kind:
            _progress("  ⚠ 서버가 jobs_kind 를 안 줬다 — 옛 배포본이다. 모양으로 추측한다")
            kind = ("transcribe" if "transcribe" in j0 else
                    "fetch_images" if "queries" in j0 else
                    "generate_images" if "poll" in res else
                    "synthesize" if "steps" in j0 else
                    "argv" if all("argv" in j for j in res["jobs"]) else None)
        if kind == "transcribe":
            # 자막을 소리에 맞추기 위한 측정 — **재기만** 한다. 판정은 서버가 한다.
            # ★파형(rise_edges)은 가벼운 로컬 ffmpeg 라 전사(whisper)가 도는 동안
            #   **겹쳐** 돌린다 (2026-08-24). 폭은 서버가 준다(`edge_parallel`) —
            #   없으면 지금까지처럼 순차다(옛 서버 응답 그대로 동작).
            #   전사 자체는 직렬을 유지한다 — whisper 는 프로세스마다 모델을 통째로
            #   올려 폭 2면 RAM 이 2배다. 수강생 기계 사양을 모르면서 넓히지 않는다.
            w_out, e_out = {}, {}
            _asr_skipped = []          # 전사·선택 파형을 못 잰 사유(서버에 그대로 올린다)
            try:
                _ew = int(res.get("edge_parallel") or 0)
            except (TypeError, ValueError):
                _ew = 0
            _efut, _pool = {}, None
            if _ew > 1 and any(j.get("edges") for j in res["jobs"]):
                from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
                _pool = ThreadPoolExecutor(max_workers=_ew)
                for j in res["jobs"]:
                    if j.get("edges"):
                        _efut[j["key"]] = _pool.submit(
                            rise_edges, j["path"], res["edge_params"])
            for j in res["jobs"]:
                if j.get("transcribe"):
                    # ★전사 캐시 — **내용도장(sha1)** 이 같을 때만 재사용한다
                    #   (2026-08-25 · 군림보 연속 나레). 파일 이름·mtime 으로는
                    #   안 된다: 이름만 보면 어제 소리의 낱말 시각을 돌려주고
                    #   (자막이 말과 어긋난다), mtime 은 같은 소리를 다시 구워도
                    #   바뀌어 **유료 전사가 또 나간다**. 서버가 `cache` 로
                    #   경로+도장 자리를 줄 때만 돈다 — 옛 서버 응답에는 이 키가
                    #   없어 신구 혼재가 무해하다.
                    cw = _transcribe_cache_load(j)
                    if cw is not None:
                        _progress(f"    [전사] {j['key']} — 캐시 적중(내용도장 동일 · "
                              f"단어 {len(cw)}개 · 유료 호출 0)", flush=True)
                        w_out[j["key"]] = cw
                    else:
                        # ★★`optional` 전사 — **열쇠가 없는 것이 정상인 자리**가 있다
                        #   (2026-09-04 · 조교 계측). 조교 MCP 의 말속도·대본 축은
                        #   낱말 시각이 «있으면 켜지는» 축이라, 열쇠가 없다고 체인이
                        #   멎으면 나머지 62축이 통째로 선다. do 항목의 `optional`
                        #   (:332·:1709)과 **같은 규약**을 전사 일감에도 준다.
                        #   ★선택이 아닌 자리(자막 정렬)는 그대로 던진다 — 대조군이다.
                        try:
                            w_out[j["key"]], _p = transcribe_words(
                                j["path"], res["asr"],
                                (headers or {}).get("asr_keys") or {})
                            _transcribe_cache_save(j, w_out[j["key"]], _p)
                        except ASRSetupRequired as setup:
                            if j.get('optional'):
                                w_out[j['key']] = []
                                _asr_skipped.append(f"{j['key']}: ASRSetupRequired: {setup}")
                                _progress(f"    [전사] {j['key']} — 건너뜀(선택): {setup}", flush=True)
                            else:
                                got['words'] = dict(w_out)
                                got['edges'] = {key: value.get('edges') or [] for key, value in e_out.items()}
                                got['voiced'] = {key: value.get('voiced') or [] for key, value in e_out.items()}
                                if _pool is not None:
                                    _pool.shutdown(wait=False, cancel_futures=True)
                                raise
                        except TranscriptionPending:
                            if _pool is not None:
                                _pool.shutdown(wait=False, cancel_futures=True)
                            raise               # 선택 전사도 대기를 '말 없음'으로 바꾸지 않는다.
                        except Exception as _e:            # noqa: BLE001
                            if not j.get("optional"):
                                raise
                            #   ★삼키는 게 아니다 — 빈 값을 넣고 **왜 비었는지 말한다.**
                            #     서버는 빈 값을 보고 «못 잼 + 사유» 로 적는다.
                            w_out[j["key"]] = []
                            _asr_skipped.append(f"{j['key']}: {type(_e).__name__}: {_e}")
                            _progress(f"    [전사] {j['key']} — 건너뜀(선택): {_e}", flush=True)
                if j.get("edges"):
                    m = (_efut[j["key"]].result() if j["key"] in _efut
                         else rise_edges(j["path"], res["edge_params"]))
                    e_out[j["key"]] = m
                    if m.get("unavailable"):
                        reason = {"numpy_missing": "numpy가 없습니다",
                                  "audio_too_short": "음성이 너무 짧아 파형을 비교할 수 없습니다"}.get(
                                      m["unavailable"], m["unavailable"])
                        note = f"{j['key']}: 파형 측정 불가 ({m['unavailable']}) — {reason}. 낱말 시각은 보존합니다."
                        _asr_skipped.append(note)
                        _progress("    [파형] " + note, flush=True)
                    else:
                        _progress(f"    [파형] {j['key']} 상승엣지 {len(m.get('edges') or [])}개 · "
                              f"소리구간 {len(m.get('voiced') or [])}개", flush=True)
            if _pool is not None:
                _pool.shutdown(wait=False)
            got["words"] = w_out
            if _asr_skipped:
                #   ★«못 쟀다» 를 조용히 넘기지 않는다 — 사유를 서버까지 올린다.
                got["asr_skipped"] = _asr_skipped
            got["edges"] = {k: v.get("edges") or [] for k, v in e_out.items()}
            got["voiced"] = {k: v.get("voiced") or [] for k, v in e_out.items()}
        elif kind == "ask_video":
            # ★소재를 **통째로** 모델에 보여 초안 대본·임팩트 구간을 받는다.
            #   무엇을 묻는지·어디로 보내는지·어떻게 줄일지 전부 서버가 준다.
            # ★★`auth_headers` 는 **응답 전체**를 받는 자다 — 알맹이(res["auth"])를
            #   넘기면 안에서 .get("auth") 가 None 이 되어 빈 헤더가 나가고,
            #   EvoLink 키가 정상인데도 「모델 키가 없다」로 죽었다
            #   (2026-09-01 수강생 제보 · L 번호까지 짚어 줬다 — 형제 호출
            #   image_qc/synthesize/generate_images 는 전부 (res, headers) 였다).
            for j in res["jobs"]:
                got[j.get("key") or "draft"] = ask_video(
                    j, lambda: auth_headers(res, headers))
                _progress(f"    [모델] 초안 받음 — 카드 "
                      f"{len((got.get(j.get('key') or 'draft') or {}).get('cards') or [])}장 · "
                      f"임팩트 {len((got.get(j.get('key') or 'draft') or {}).get('impact') or [])}구간",
                      flush=True)
        elif kind == "fetch_images":
            # 그림 조달 — 받은 검색어·소스로 받아 저장만 한다. 크기는 서버가 판정한다.
            # ★`synthesize`·`generate_images` 와 **같은 모양**으로 넘긴다.
            #   전에는 인증·재시도 정책이 이미지 경로에만 안 걸려 있었다 —
            #   429·403 에 되풀이하지 않는 규칙(2026-08-15 사고)이 여기만 비어 있었다.
            candidate_bag = {} if res.get('collect_candidates') else None
            got["image_sizes"] = fetch_images(res["jobs"], res["retry"], res["min_bytes"],
                                              res.get("pace_sec", 0.0),
                                              res.get("backoff_sec") or (),
                                              auth_headers(res, headers),
                                              res.get("retry_policy"),
                                              **({'candidates_out':candidate_bag} if candidate_bag is not None else {}))
            if candidate_bag is not None:
                got['candidates'] = candidate_bag
        elif kind == "image_qc":
            # ★그림 검수 — 후보를 **한 번에 비교**해 고른다.
            #   키가 없으면 건너뛰되 **「검수 못 했다」를 남긴다** — 「통과」로 읽히면 안 된다.
            got["image_qc"] = image_qc(res["jobs"], lambda: auth_headers(res, headers),
                                       res.get("retry", 3),
                                       res.get("retry_policy"),
                                       # ★폭·클로드 설정은 서버가 준다(없으면 옛 그대로: 직렬·제미나이)
                                       parallel=res.get("parallel"),
                                       claude=res.get("claude"))
        elif kind == "synthesize":
            # ★재시도 정책은 **서버가 준다**. 없으면 실행기가 fail-closed 로 멈춘다 —
            #   옛 기본값(모두 재시도)으로 떨어지면 2026-08-15 사고가 되살아난다.
            synthesize(res["jobs"], auth_headers(res, headers), res["retry"],
                       res["min_bytes"], res.get("parallel"),
                       res.get("retry_policy"))
        elif kind == "generate_images":
            # ★결과 URL 을 payload 로 올린다 (2026-08-25) — 서버의 일관성 배선
            #   (참조 생성 body.image_urls)이 앞 칸 그림의 URL 을 쓴다. 옛 서버는
            #   measure(pick) 선언이 없어 이 값을 안 읽는다 — 신구 혼재 무해.
            got["gen_urls"] = generate_images(
                res["jobs"], res["poll"], auth_headers(res, headers),
                res["retry"], res["min_bytes"],
                res.get("parallel"), res.get("stagger_sec") or 0.0,
                res.get("retry_policy")) or {}
        elif kind == "argv":
            # ★서버가 준 폭으로 **동시에** 돈다. 폭이 없으면 1(직렬)이다.
            #   실측(28컷): 직렬 19.25초 → 폭8 11.14초. 바이트는 1,540파일 전수 동일.
            #   ★`-threads` 를 argv 에 넣지 마라 — 넣는 순간 산출물 바이트가 달라진다
            #     (x264 가 스레드 수를 파일에 박는다). 줄일 것은 스레드가 아니라 폭이다.
            # ★출력 폴더는 ⓪에서 **한 번에** 만들었다. 여기서 또 만들지 않는다 —
            #   두 벌이면 언젠가 한쪽만 고쳐지고, 안 고쳐진 쪽이 조용히 남는다.
            # ★★이름을 `outs` 로 쓰면 **명령 출력을 모으는 dict 를 덮어쓴다**
            #   (2026-08-14 재현). ⑤에서 `outs["bake_bgm"] = …` 를 하는 순간
            #   `TypeError: list indices must be integers` 로 죽는다 —
            #   `person_deliver` 가 정확히 그 모양이다(jobs_kind=argv + do 의 argv).
            #   측정값도 같이 사라진다. 그래서 **다른 이름**을 쓴다.
            job_outs = [j.get("out") for j in res["jobs"] if j.get("out")]
            if len(set(job_outs)) != len(job_outs):
                # ★두 잡이 같은 파일을 쓰면 결과가 재현되지 않는다(실측: 6회 중 5종의 md5).
                #   게다가 길이만 보는 검사는 그걸 통과시킨다 — 큰 소리로 멈춘다.
                raise StepError("두 일감이 같은 출력 경로를 쓴다 — 동시에 굽면 결과가 깨진다.")
            completed_jobs = run_argv_pool(res["jobs"], res.get("parallel"))
            # No payload update happens until every job has returned verified
            # completion. On pending, successful files/receipts survive on disk.
            handoff = {}
            for result in (completed_jobs or {}).values():
                handoff.update(result.get("handoff") or {})
            got.update(_pick_from({"vmake_done": handoff}, res.get("measure")))
        else:
            # ★모르는 모양을 **조용히 넘기지 않는다.** 건너뛰면 결과가 조용히 비어 버린다
            raise StepError(f"모르는 job 종류다 — {kind!r}, 키 {sorted(j0)}. 여기서 멈춘다.")

    # ⑤ 명령
    # ★자산 팩은 서로 독립이라 **동시에** 받는다 (2026-08-24). 폭은 서버가 준다
    #   (`fetch_parallel`) — 없으면 지금까지처럼 아래 루프에서 하나씩 받는다.
    #   콜드스타트(약 9%) 재시도 대기가 팩 수만큼 직렬로 쌓이던 자리다.
    _fa_done = False
    try:
        _fa_w = int(res.get("fetch_parallel") or 0)
    except (TypeError, ValueError):
        _fa_w = 0
    _fa_items = [i for i in (res.get("do") or []) if i.get("cmd") == "fetch_asset"]
    if _fa_w > 1 and len(_fa_items) > 1:
        if c is None:
            raise StepError("자산을 받으려면 Client 가 필요하다 — execute(..., c=클라이언트)")
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
        _progress(f"  [자산] {len(_fa_items)}팩을 폭 {min(_fa_w, len(_fa_items))} 로 동시에 받는다",
              flush=True)
        with ThreadPoolExecutor(max_workers=min(_fa_w, len(_fa_items))) as _ex:
            # ★list() 로 결과를 소진해야 예외가 여기서 난다 — 삼키면 §조용한 실패다
            list(_ex.map(lambda it: _fetch_asset(it, c), _fa_items))
        _fa_done = True
    # ★구글 사진(agy) 미리 찾기 (2026-09-28 사장님 결정 «네이버는 기존대로, 구글만 agy로»).
    #   컷 순서대로 가면 agy 한 번(검색 30~40초)이 컷마다 줄을 선다. 그래서 이 응답의 사진 검색 컷 중
    #   **앞 출처(네이버)로 모자랄 컷**의 첫 검색어만 모아 동시에 먼저 찾아 영수증으로 남긴다.
    #   못 한 것은 아래 컷 순서에서 그 자리에서 다시 찾고, 이유는 거기서도 사람 말로 찍힌다.
    #   이미 기록이 있는 컷(옛 판 영수증 포함)은 미리 찾지 않는다 — 이어 하기는 그 기록을 쓴다(`photo_search_started`).
    _agy_items = [i for i in (res.get("do") or []) if i.get("cmd") == "search_images"
                  and any(str(s.get("kind") or "").lower() == "agy_google" for s in (i.get("sources") or []))]
    if _agy_items:
        from volcano_run import PhotoSourceError, agy_google_plan_prefetch, photo_search_started  # noqa: PLC0415
        _agy_items = [i for i in _agy_items if not photo_search_started(i)]
    if _agy_items:
        try:
            agy_google_plan_prefetch(_agy_items)
        except PhotoSourceError as _agy_e:
            _progress(f"  [구글 사진·agy] 미리 찾기를 못 했다 — 컷마다 다시 시도한다: {_agy_e}")
    for item in res.get("do") or []:
        cmd = item.get("cmd")
        if cmd in ("check_photo", "probe_custom_media", "prepare_custom_media", "verify_custom_media", "check_custom_fonts"):
            continue
        if cmd == "fetch_font":
            # ★auto_download 글꼴 — 서버가 준 주소·zip 안 이름·자리로 **자동으로** 받는다
            fetch_font(item)
            continue
        if cmd == "write_manifest":
            from pathlib import Path
            m_path = Path(item["path"])
            m_path.parent.mkdir(parents=True, exist_ok=True)
            m_path.write_text(json.dumps(item["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")
            got["source_manifest"] = item["manifest"]
            _progress(f"  [소재 기록] {item['manifest'].get('title')} ({item['manifest'].get('license')})")
            continue
        if cmd in ("acquire_source", "source_acquisition"):
            from pathlib import Path
            expected_url = (item.get("url") or (item.get("provenance") or {}).get("source_url") or "").strip()
            # Defensive check 1: Reject missing URL or local video before any mutation.
            # acquire_source is strictly for remote URL downloads; local video is a read-only original.
            if not expected_url or item.get("kind") == "local_video":
                raise StepError(f"acquire_source는 원격 URL 다운로드 전용이며 로컬 원본을 변조할 수 없습니다: URL 누락 ({item.get('target_path')})")

            target_path = Path(item["target_path"])
            receipt_path = Path(item["receipt_path"])
            manifest_path = Path(item.get("manifest_path") or (target_path.parent / "source_manifest.json"))

            # Defensive check 2: Target must be an explicit runner-owned path inside workdir.
            # The work folder comes with the job (server) or from the receipt path; a response never
            # carries `payload` (reserved-word check [81] caught the stray read, 2026-09-16).
            workdir_raw = item.get("workdir") or getattr(c, "workdir", None) or str(receipt_path.parent)
            workdir_path = Path(workdir_raw).resolve()
            try:
                target_path.resolve().relative_to(workdir_path)
            except ValueError:
                raise StepError(f"소재 다운로드 대상({target_path})이 작업 폴더({workdir_path}) 외부에 있어 안전을 위해 거부되었습니다.")

            target_path.parent.mkdir(parents=True, exist_ok=True)

            def _file_sha256(p):
                import hashlib
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        h.update(chunk)
                return h.hexdigest()

            def _safe_recover_existing(p):
                if not p.is_file():
                    return
                base_name = p.stem
                stamp = int(time.time())
                idx = 0
                while True:
                    suffix_tag = f".recovered_{stamp}" if idx == 0 else f".recovered_{stamp}_{idx}"
                    candidate = p.with_name(f"{base_name}{suffix_tag}{p.suffix}")
                    if candidate.exists():
                        idx += 1
                        continue
                    try:
                        os.rename(str(p), str(candidate))
                        _progress(f"  [소재 보존] 미검증/불완전 기존 파일을 보존했습니다: {candidate.name}")
                        break
                    except FileExistsError:
                        idx += 1
                        continue
                    except OSError:
                        try:
                            os.replace(str(p), str(candidate))
                            _progress(f"  [소재 보존] 미검증/불완전 기존 파일을 보존했습니다: {candidate.name}")
                            break
                        except OSError:
                            pass
                        break

            def _atomic_write_receipt(r_path, m_path, data):
                serialized = json.dumps(data, ensure_ascii=False, indent=2)
                for dst in (r_path, m_path):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dst.with_name(f"{dst.stem}.tmp_{os.getpid()}_{time.time_ns()}{dst.suffix}")
                    try:
                        tmp.write_text(serialized, encoding="utf-8")
                        os.replace(str(tmp), str(dst))
                    except OSError:
                        try:
                            tmp.unlink(missing_ok=True)
                        except OSError:
                            pass

            is_valid_cache = False
            cached_receipt = None
            if receipt_path.is_file() and target_path.is_file():
                try:
                    loaded = json.loads(receipt_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        is_complete = loaded.get("completion_state") == "complete"
                        url_matches = bool(expected_url and loaded.get("source_url") == expected_url)
                        st = target_path.stat()
                        size_matches = (st.st_size == loaded.get("file_size", -1)
                                        and st.st_size > 0)
                        identity_matches = True
                        if is_complete and url_matches and size_matches:
                            rec_sha = loaded.get("file_sha256")
                            rec_mtime_ns = loaded.get("file_mtime_ns")
                            current_mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))
                            if rec_sha:
                                if _file_sha256(target_path) != rec_sha:
                                    identity_matches = False
                            elif rec_mtime_ns is not None:
                                if current_mtime_ns != rec_mtime_ns:
                                    identity_matches = False

                        if is_complete and url_matches and size_matches and identity_matches:
                            probe_argv = item.get("probe_argv") or ["ffprobe", "-v", "error", "-select_streams", "v:0",
                                                                   "-show_entries", "stream=width,height,r_frame_rate,duration",
                                                                   "-of", "json", str(target_path)]
                            p_val = run_argv(probe_argv, capture=True)
                            if p_val.returncode == 0:
                                parsed = json.loads(p_val.stdout or "{}")
                                if parsed.get("streams"):
                                    is_valid_cache = True
                                    cached_receipt = loaded
                                    cached_receipt["cache_status"] = "hit"
                                    cached_receipt["probe"] = parsed
                                    cached_receipt["probe_stdout"] = p_val.stdout
                except Exception:
                    is_valid_cache = False

            if is_valid_cache and cached_receipt:
                _atomic_write_receipt(receipt_path, manifest_path, cached_receipt)
                got["source_manifest"] = cached_receipt
                outs["probe"] = cached_receipt.get("probe_stdout")
                outs[cmd] = cached_receipt
                _keep(outs, "probe", outs["probe"])
                _keep(outs, cmd, cached_receipt)
                _progress(f"  [소재 캐시] 검증 완료 소재를 확인했습니다 ({cached_receipt.get('file_size')}B): {target_path.name}")
                continue

            if target_path.is_file():
                _safe_recover_existing(target_path)

            dl_argv = item.get("download_argv") or []
            if dl_argv:
                _progress(f"  [소재 다운로드] {dl_argv[0]} …")
                p_dl = run_argv(dl_argv, capture=True)
                if p_dl.returncode != 0:
                    _miss = missing_inputs(dl_argv)
                    raise StepError(f"소재 다운로드 실패: {dl_argv[0]}\n{failure_text(p_dl)}"
                                    + (("\n  ★입력 파일이 없습니다: " + " · ".join(_miss)) if _miss else ""))
                if item.get("source_mp4"):
                    source_mp4(item["source_mp4"])

            if not target_path.is_file() or target_path.stat().st_size == 0:
                raise StepError(f"소재 다운로드 후 파일이 생성되지 않았거나 0바이트입니다: {target_path}")

            probe_argv = item.get("probe_argv") or ["ffprobe", "-v", "error", "-select_streams", "v:0",
                                                   "-show_entries", "stream=width,height,r_frame_rate,duration",
                                                   "-of", "json", str(target_path)]
            _progress(f"  [소재 검증] {probe_argv[0]} …")
            p_pr = run_argv(probe_argv, capture=True)
            if p_pr.returncode != 0:
                raise StepError(f"소재 ffprobe 검증 실패: {probe_argv[0]}\n{failure_text(p_pr)}")

            try:
                probe_data = json.loads(p_pr.stdout or "{}")
                if not probe_data.get("streams"):
                    raise ValueError("유효한 비디오 스트림이 없습니다.")
            except Exception as pe:
                raise StepError(f"소재 메타데이터 분석 실패: {pe}")

            prov = item.get("provenance") or {}
            st_now = target_path.stat()
            receipt = {
                "subject": prov.get("subject", ""),
                "source_url": expected_url,
                "title": prov.get("title", ""),
                "source": prov.get("source", ""),
                "license": prov.get("license", ""),
                "terms": prov.get("terms", ""),
                "url_hash": item.get("url_hash", ""),
                "target_path": str(target_path).replace("\\", "/"),
                "file_size": st_now.st_size,
                "file_mtime_ns": getattr(st_now, "st_mtime_ns", int(st_now.st_mtime * 1e9)),
                "file_sha256": _file_sha256(target_path),
                "completion_state": "complete",
                "cache_status": "fresh",
                "verified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "probe": probe_data,
                "probe_stdout": p_pr.stdout,
            }
            _atomic_write_receipt(receipt_path, manifest_path, receipt)
            got["source_manifest"] = receipt
            outs["probe"] = p_pr.stdout
            outs[cmd] = receipt
            _keep(outs, "probe", outs["probe"])
            _keep(outs, cmd, receipt)
            _progress(f"  [소재 확보 완료] {receipt['title']} ({receipt['file_size']}B, 검증 완료)")
            continue
        if cmd == "scene_cuts":
            # 장면 전환 시각. **판정은 서버가 한다** — 여기는 읽기만.
            got["scene_cuts"] = scene_cuts(item)
            _progress(f"  [장면전환] {len(got['scene_cuts'])}곳")
            continue
        if cmd == 'film_editor_migrate':
            import film_tracks
            got['editor_migration']=film_tracks.migrate(item)
            _keep(outs,cmd,got['editor_migration'])
            _progress('  [영상 편집] 기존 파일 목록과 접수 기록을 보존했습니다. 새 유료 요청 없음')
            continue
        if cmd == 'film_editor':
            import film_editor
            previous = item.get('state') or {}
            result = film_editor.run(item, headers=auth_headers(res, headers) if item.get('action') == 'prepare' else None)
            result['contract_input_id'] = item.get('contract_input_id')
            result['action'] = item.get('action')
            if result.get('ok') and item.get('action') in ('prepare', 'preview', 'render'):
                result[item['action'] + '_input_id'] = item.get('contract_input_id')
            result['history'] = list(previous.get('history') or []) + [{
                key: result.get(key) for key in ('action','status','error','action_seconds','tts_requests_this_action','input_id','render_id')}]
            got['rinbox'] = {**previous, **result}
            if result.get('ok'):
                got['rinbox'].pop('error', None)
                if item.get('action') == 'verify':
                    got['rinbox'].pop('verify_repair_input_id', None)
            _keep(outs, cmd, got['rinbox'])
            _progress('  [영상 편집] ' + str(result.get('status', 'unknown')))
            continue
        if cmd == "hardsub_probe":
            # 박힌 자막 띠·레터박스 알맹이 — **판정은 서버가 한다** (2026-09-02 명화관·린박스 제보).
            #   ★옛 팩은 이 이름을 몰라 «건너뜀» 으로 지나간다(argv 가 없다) — 서버는 값이 없으면 말하지 않는다.
            got["src_hardsub"] = hardsub_probe(item)
            _hs = got["src_hardsub"] or {}
            _progress(f"  [하드섭] 표본 {_hs.get('with_text')}/{_hs.get('frames')} 프레임에 박힌 자막 · 띠 {_hs.get('band')} · 알맹이 {_hs.get('content')}")
            _keep(outs, cmd, got["src_hardsub"])
            continue
        if cmd == "ref_probe":
            # 조교 채널 계측 S1 — tikitaka grb/s1_probe.py + m_fps.py 이관 (2026-09-03).
            #   ids·폴더·오디오 규격·자릿수·확장자 전부 서버 params. 판정(해상도 경고·분포)은
            #   서버 volcano_ref_steps 가 한다. ★`_keep` 으로 outs 에도 남긴다 — 서버 규칙이
            #   `cmds:ref_probe` 로 읽는다(§_keep: 규칙과 등록 **둘 다**).
            got["probe"] = ref_probe(item)
            _keep(outs, cmd, got["probe"])
            _progress(f"  [계측 probe] {len(got['probe'])}편")
            continue
        # ── 조교 채널 계측 2·3판 (2026-09-03). 규칙 이름 == 디스패치 이름 == 함수 이름(§_keep). ──
        #   문턱·규격은 전부 서버 params. `as` 가 오면 그 이름으로 got 에 담는다(frames·geom 이 두 왕복).
        if cmd == "ref_meta":
            got["meta"] = ref_meta(item)
            _keep(outs, cmd, got["meta"])
            _progress(f"  [계측 meta] {item.get('mode')}")
            continue
        if cmd == "ref_frames":
            key = item.get("as") or "frames"
            got[key] = ref_frames(item)
            _keep(outs, cmd, got[key])
            _progress(f"  [계측 {key}] {len(got[key])}편")
            continue
        if cmd == "ref_ocr":
            got["ocr"] = ref_ocr(item)
            _keep(outs, cmd, got["ocr"])
            _progress(f"  [계측 ocr] {len(got['ocr'])}편")
            continue
        if cmd == "ref_geom":
            key = item.get("as") or "geom"
            got[key] = ref_geom(item)
            _keep(outs, cmd, got[key])
            _progress(f"  [계측 {key}] {len(got[key])}편")
            continue
        if cmd == "ref_stems":
            got["stems"] = ref_stems(item)
            _keep(outs, cmd, got["stems"])
            _progress(f"  [계측 stems] {len(got['stems'])}편")
            continue
        if cmd == "ref_captions":
            got["captions"] = ref_captions(item)
            _keep(outs, cmd, got["captions"])
            _progress(f"  [계측 captions] {len(got['captions'])}편")
            continue
        if cmd == "ref_tikitaka":
            got["tikitaka"] = ref_tikitaka(item)
            _keep(outs, cmd, got["tikitaka"])
            _progress(f"  [계측 tikitaka] {len(got['tikitaka'])}편")
            continue
        if cmd == "ref_glyph_iou":
            got["glyph"] = ref_glyph_iou(item)
            _keep(outs, cmd, got["glyph"])
            _progress(f"  [계측 glyph] 표본 {len(got['glyph'].get('targets') or [])}")
            continue
        if cmd == "ref_corepixels":
            got["core"] = ref_corepixels(item)
            _keep(outs, cmd, got["core"])
            _progress(f"  [계측 core] 이벤트 {len(got['core'].get('events') or [])}")
            continue
        if cmd == "ref_sheet":
            got["sheets"] = ref_sheet(item)
            _keep(outs, cmd, got["sheets"])
            _progress(f"  [계측 sheets] {len(got['sheets'])}편")
            continue
        if cmd == "ref_bundle_collect":
            got["collected"] = ref_bundle_collect(item)
            _keep(outs, cmd, got["collected"])
            _progress(f"  [계측 bundle] 파일 {len(got['collected'])}개")
            continue
        if cmd == "ref_advtable":
            got["advtable"] = ref_advtable(item)
            _keep(outs, cmd, got["advtable"])
            _progress(f"  [계측 advtable] {len(got['advtable'])}개 계열")
            continue
        if cmd == "ref_analyze_collect":
            got["collected"] = ref_analyze_collect(item)
            _keep(outs, cmd, got["collected"])
            _progress(f"  [계측 analyze] 파일 {len(got['collected'])}개")
            continue
        if cmd in _REF_AXES:
            # axes 하위 단계 손 — 서버 measure 규칙이 `cmds:<cmd>` 로 읽는다(§_keep). got 키는 `as` 또는 줄기 이름.
            key = item.get("as") or cmd[len("ref_"):]
            got[key] = _REF_AXES[cmd](item)
            #   ★★같은 `cmd` 로 **여러 do 항목**이 오면 `as` 로 **묶어서** 남긴다(2026-09-04).
            #     `openzoom` 은 편마다 do 항목을 내고(`"as": vid`) 서버는 `{편id: 결과}` 를 기대하는데
            #     (그 응답이 스스로 «각 do 항목의 vid 로 결과를 묶어» 라고 적어 뒀다), 전에는
            #     `outs[cmd]` 를 **덮어써** 마지막 편만 남았다 → 서버가 `raw.items()` 에서
            #     `AttributeError: 'list' object has no attribute 'items'` 로 죽었다(완주 60단계째).
            #   ★한 항목뿐이면 예전처럼 **그대로** 남긴다 — `card_pass2` 처럼 서버가 날 값을
            #     통째로 기대하는 자리가 그 모양이다(묶으면 그쪽이 깨진다).
            #   ★★**개수로 추측하지 않는다 — 서버가 말하는 칸(`vid`)을 본다** (2026-09-04 2차).
            #     처음엔 «같은 cmd 가 두 번 이상이면 묶는다» 로 썼는데, **1편만 재면 항목이
            #     하나라서 묶이지 않아** 서버가 `raw.items()` 에서 죽었다(완주 52걸음째,
            #     `openzoom`). 즉 **편 수에 따라 값의 모양이 달라지고 있었다.**
            #   ★`as` 로 가를 수도 없다 — `as` 는 **두 뜻**이다(편 id 3곳 · 잰 이름 10곳,
            #     §「SRC 가 세 뜻으로 겹친다」). 편별 손은 전부 `vid` 를 함께 싣는다
            #     (`{"cmd": …, "vid": v, "as": v, …}`) → 그 칸이 «편별로 묶어라» 는 선언이다.
            if item.get("vid"):
                outs.setdefault(cmd, {})
                if isinstance(outs[cmd], dict):
                    outs[cmd][item["vid"]] = got[key]
            else:
                _keep(outs, cmd, got[key])
            _progress(f"  [계측 axes·{key}] 완료")
            continue
        # ★`cmd` 는 **None 일 수 있다** — 아래 «cmd 도 argv 도 없다» 가드가
        #   존재하는 이유가 바로 그 경우다(2026-08-17 사진 지시 20건). 09-04 에
        #   넣은 이 조교 갈래가 가드보다 **앞에서** 벗겨 AttributeError 로 죽었다
        #   — 사람이 읽을 사유가 통째로 사라진다.
        if cmd and cmd.startswith("ref_") and _REF_AXES_ERRORS:
            raise StepError(f"'{cmd}' 손 모듈을 열지 못했습니다 — 묶음 import 오류: {_REF_AXES_ERRORS}")
        if cmd == "measure_lufs":
            v = measure_lufs(item["argv"])
            outs.setdefault("measure_lufs", {})[item.get("stage") or "?"] = v
            # ★같은 stderr 에서 **단기 라우드니스 폭**도 뽑는다 — 완성본이 실물보다
            #   평평한지(소재가 균일한지)를 **돈 쓰기 전에** 알려주기 위해서다.
            #   따로 돌리면 같은 파일을 두 번 굽는다.
            sp = measure_lufs_spread(item["argv"])
            if sp is not None:
                outs.setdefault("lufs_spread", {})[item.get("stage") or "?"] = sp
            _progress(f"  [라우드니스] {item.get('stage')} = {v}")
            continue
        if cmd == "measure_loudnorm":
            # 마스터 2패스용 1패스 측정 — **값만** 돌려준다. 판정·게인은 서버가 한다.
            got["ln_probe"] = measure_loudnorm(item)
            _keep(outs, cmd, got["ln_probe"])
            _progress(f"  [라우드니스 1패스] I {got['ln_probe'].get('input_i')} / "
                  f"TP {got['ln_probe'].get('input_tp')}")
            continue
        if cmd == "measure_peak":
            # 구운 것을 **게이트와 같은 자**로 다시 잰다(ebur128 peak=true).
            v = measure_peak(item)
            got.setdefault("peaks", {})[item.get("stage") or "?"] = v
            _keep(outs, cmd, got["peaks"])
            _progress(f"  [피크] {item.get('stage')} = I {v.get('I')} / TP {v.get('TP')}")
            continue
        if cmd == "measure_images":
            # ★그림 크기·피사체 중심 — **서버가 파일 목록을 준다.** 판정(구도·크롭)은
            #   서버가 한다. 이 자리는 재기만 한다.
            # ★★왜 생겼나 (2026-08-26): `image_facts` 는 예전부터 있었는데
            #   **부르는 곳이 0곳**이었고, 서버는 같은 일을 산문 한 줄로 시켰다
            #   (*"얼굴 검출 우선, 없으면 엣지 무게중심"*). 그러면 클라마다 다르게
            #   짜서 **구도가 갈린다** — 7일 87명이 그 자리에서 막혔다.
            _base = item.get("dir") or ""
            _rel = list(item.get("paths") or [])
            _abs = [(p_ if os.path.isabs(p_) else os.path.join(_base, p_)) for p_ in _rel]
            _facts = image_facts(_abs)
            # ★열쇠는 **서버가 준 이름 그대로** 돌려준다 — 절대경로로 돌려주면
            #   서버가 여는 이름(`img43/01.png`)과 안 맞아 조용히 빗나간다.
            _by = {}
            for _r, _a2 in zip(_rel, _abs):
                _v = _facts.get(_a2) or _facts.get(os.path.basename(_a2))
                if _v is None:
                    for _k2, _v2 in _facts.items():
                        if str(_k2).endswith(os.path.basename(_a2)):
                            _v = _v2
                            break
                if _v is not None:
                    _by[_r] = _v
            got["images"] = _by
            _keep(outs, cmd, _by)
            _progress(f"  [그림] {len(_by)}장을 쟀다 (크기·피사체 중심)")
            continue
        if cmd == "measure_sfx":
            # 내가 넣은 효과음 — 서버가 준 자로 재서 그대로 돌려준다. **판정은 서버가 한다.**
            got["available_info"] = measure_sfx(item)
            _keep(outs, cmd, got["available_info"])
            _progress(f"  [내효과음] {len(got['available_info'])}개를 쟀다")
            continue
        if cmd == 'measure_custom_text':
            got['custom_text_metrics']=measure_custom_text(item)
            _keep(outs,cmd,got['custom_text_metrics'])
            _progress(f"  [사용자 글꼴] {len(got['custom_text_metrics']['lines'])}줄 실측")
            continue
        if cmd == "measure_card_ink":
            # 카드 글 잉크폭 — 서버가 지은 프로브를 그 글꼴로 굽고 **기둥 폭만** 잰다.
            #   판정(글자를 줄일지·아이콘 자리)은 서버가 한다. 프로브 본문·argv·
            #   문턱까지 전부 서버가 준다 — 실행기가 자를 스스로 정하면 서버가
            #   값을 바꿔도 안 따라온다.
            # ★서버가 열쇠(이 명령)를 줄 때만 돈다 — 옛 서버 응답에는 이 명령이
            #   없어 신구 혼재가 무해하다.
            # ★`known` — 앞 왕복에서 이미 잰 값. 합쳐서 올려야 두 번째 측정에서
            #   앞 값이 payload 에서 증발하지 않는다(칸 증발 사고 부류).
            import numpy as np                                    # noqa: PLC0415
            for w in item.get("write") or []:
                _write(w, "카드프로브")
            vals = {}
            for pr in item.get("probes") or []:
                run_argv(pr["argv"])
                pw, ph, th = int(pr["w"]), int(pr["h"]), int(pr["thresh"])
                a = np.fromfile(pr["out"], dtype=np.uint8)
                if a.size < pw * ph:
                    raise StepError(f"카드 프로브 프레임이 짧다: {pr['out']} "
                                    f"({a.size}B < {pw * ph}B)")
                m = a[:pw * ph].reshape(ph, pw) > th
                xs = np.nonzero(m.any(0))[0]
                vals[pr["name"]] = float(xs.max() - xs.min() + 1) if xs.size else 0.0
            got["card_ink"] = dict(item.get("known") or {}, **vals)
            _keep(outs, cmd, got["card_ink"])
            _progress("  [카드잉크] " + " · ".join(f"{k} {v:g}px"
                                              for k, v in sorted(vals.items())))
            continue
        if cmd == "measure_pieces":
            # 나레 조각 — 서버가 준 후보 차례(candidates)에서 **있는 첫 파일**을 골라
            #   길이·표본율을 재고, 갭 없는 이어붙임의 조용몫을 서버가 준 자
            #   (quiet 의 창·문턱·argv 전부)로 잰다 (2026-08-24 · 군림보 이식).
            # ★고르는 차례도, 재는 자도 **전부 서버 데이터다** — 실행기가 차례나
            #   문턱을 스스로 정하면 서버가 고쳐도 이 팩이 안 따라온다(§실행기 규율).
            #   고른 결과(picks)를 그대로 되올린다 — 서버가 같은 목록으로 aconcat 을
            #   잇는다(재는 쪽과 굽는 쪽이 같은 파일을 보게 하는 그 자리다).
            # ★서버가 이 명령을 줄 때만 돈다 — 옛 서버 응답과 혼재 무해.
            import numpy as np                                    # noqa: PLC0415
            base = item["base"]
            picks, secs, srates = {}, {}, {}
            for k in sorted(item["candidates"], key=lambda x: int(x)):
                names = item["candidates"][k]
                chosen = next((n for n in names
                               if os.path.exists(os.path.join(base, n))), None)
                if chosen is None:
                    raise StepError(f"나레 조각 {k} 이 없다 — 찾아본 자리: {names} "
                                    f"(기준 {base})")
                p = os.path.join(base, chosen)
                picks[k] = chosen
                secs[k] = wav_seconds(p)
                pr = run_argv([p if a == "@IN@" else a
                               for a in item["srate_argv"]], capture=True)
                try:
                    srates[k] = int((pr.stdout or "").strip().splitlines()[0])
                except (ValueError, IndexError):
                    raise StepError(f"표본율을 못 읽었다: {p} ← "
                                    f"{(pr.stdout or '')[:80]!r}")
            quiet = None
            q = item.get("quiet")
            if q:
                lines = "\n".join(f"file '{os.path.join(base, picks[k])}'"
                                  for k in sorted(picks, key=int))
                os.makedirs(os.path.dirname(q["list_path"]) or ".", exist_ok=True)
                # ★바이트로 쓴다 — 윈도우 줄바꿈 변환을 막는 `_write` 와 같은 이유
                with open(q["list_path"], "wb") as fh:
                    fh.write((lines + "\n").encode("utf-8"))
                run_argv([q["list_path"] if a == "@LIST@"
                          else q["wav_path"] if a == "@OUT@" else a
                          for a in q["concat_argv"]])
                r = _spawn([q["wav_path"] if a == "@IN@" else a
                                    for a in q["decode_argv"]], capture_output=True)
                if r.returncode != 0:
                    raise StepError(f"나레 되읽기 실패: {err_gist(r.stderr, 300)}")
                a = np.frombuffer(r.stdout, np.float32)
                W = int(q["win"])
                wsec = W / float(q["sr"])
                n = a.size // W
                if n >= 8:
                    lv = 20 * np.log10(
                        np.sqrt((a[:n * W].reshape(n, W) ** 2).mean(1)) + 1e-12)
                    thr = float(np.percentile(lv, 90)) - float(q["drop_db"])
                    runs, c = [], 0
                    for x in (lv < thr):
                        if x:
                            c += 1
                        elif c:
                            runs.append(c * wsec)
                            c = 0
                    if c:
                        runs.append(c * wsec)
                    runs = [x for x in runs if x >= float(q["min_run"])]
                    # ★쉼이 min_pauses 미만이면 「못 잼」(None)이다 — 0 이 아니다.
                    #   판정(넣을지 말지)은 서버가 한다. 여기는 재기만.
                    if len(runs) >= int(q["min_pauses"]):
                        quiet = {"sec": round(n * wsec, 1),
                                 "quiet": round(float((lv < thr).mean()), 4),
                                 "pauses": len(runs)}
            got["piece_stat"] = {"picks": picks, "secs": secs,
                                 "srates": srates, "quiet": quiet}
            _keep(outs, cmd, got["piece_stat"])
            _progress(f"  [나레조각] {len(picks)}개 (파생 사본 "
                  f"{sum(1 for v in picks.values() if v.count('.') > 1)}개) · "
                  f"표본율 {sorted(set(srates.values()))}Hz · "
                  + (f"조용몫 {quiet['quiet']:.4f} ({quiet['pauses']}쉼)"
                     if quiet else "조용몫 못 잼(쉼이 모자라다)"))
            continue
        if cmd == "measure_voiced":
            # 말한 시간(초) — 서버가 준 자(20ms 창 RMS · p90−drop_db)로 재기만.
            #   판정(말속도·tempo)은 서버가 한다. tikitaka `m_speed._voiced` 의
            #   그 자다 — 자가 갈리면 수렴점이 실물과 어긋난다 (2026-08-25 이식).
            # ★서버가 이 명령을 줄 때만 돈다 — 옛 서버 응답과 혼재 무해.
            vals = {}
            for f in item["files"]:
                lv, wsec, np_ = _rms_wins(item, f["path"])
                if lv is None:
                    vals[f["key"]] = None      # 못 잼 — 0 이 아니다
                    continue
                thr = float(np_.percentile(lv, 90)) - float(item["drop_db"])
                q = float((lv < thr).mean())
                v = lv.size * wsec * (1.0 - q)
                # ★「못 잼」 문턱도 서버 params — 여기 숫자를 박으면 명세가 샌다
                vals[f["key"]] = (None if v <= float(item["min_voiced"])
                                  else round(v, 3))
            got["voiced_secs"] = vals
            _keep(outs, cmd, vals)
            _progress("  [말시간] " + " · ".join(
                f"{k} {v if v is not None else '못잼'}"
                for k, v in sorted(vals.items())))
            continue
        if cmd == "gap_shape":
            # 무음 꼴 손질 — tikitaka `m_gapshape.다듬기` 이관 (2026-08-25).
            #   낱말 **안** 무음과 낱말 **사이** 무음을 갈래마다 제 분위수 표로,
            #   **한 지나감**에 맞춘다(나눠 하면 찌꺼기가 되살아난다). 표·문턱·
            #   자(decode·창·min_run)·개수 목표 전부 **서버 params** — 이 팩에는
            #   채널 값이 0개다. 판정(표를 쓸지·재전사할지)은 서버가 한다.
            # ★늘릴 땐 그 구간을 되풀이해 채우고(디지털 0 은 바닥이 뚝 떨어진다)
            #   줄일 땐 **가운데**를 잘라낸다(말이 잦아드는 양 끝을 남긴다).
            # ★서버가 이 명령을 줄 때만 돈다 — 옛 서버 응답과 혼재 무해.
            import wave                                            # noqa: PLC0415
            src, dst = item["src"], item["dst"]
            w_in = item.get("words")
            if w_in is None and item.get("words_from"):
                w_in = (got.get("words") or {}).get(item["words_from"])
            words = [{"orig": w,
                      "t0": round(float(w.get("start") if w.get("start") is not None
                                        else w.get("t0") or 0.0), 3),
                      "t1": round(float(w.get("end") if w.get("end") is not None
                                        else w.get("t1") or 0.0), 3)}
                     for w in (w_in or [])]
            stat = {"shaped": False}
            lv, wsec, np_ = _rms_wins(item, src)
            rs, dur = None, 0.0
            if lv is not None:
                thr = float(np_.percentile(lv, 90)) - float(item["drop_db"])
                rs = _silence_runs(lv, wsec, thr, item["min_run"])
                dur = lv.size * wsec
            if rs:
                # ★여백·문턱 전부 서버 params — 숫자를 박으면 명세가 새고,
                #   서버가 자를 고쳐도 이 팩이 안 따라온다(검사 [20]이 잡는다).
                margin = float(item["margin"])
                span_min = float(item["min_word_span"])

                def _inside_word(s_, d_):
                    for w in words:
                        a_, b_ = w["t0"] + margin, w["t1"] - margin
                        if b_ - a_ > span_min and s_ >= a_ and s_ + d_ <= b_:
                            return True
                    return False

                inside = [_inside_word(s_, d_) for s_, d_ in rs]
                kill = set()
                rate = item.get("rate")
                if rate and dur > 1.0:
                    want_n = int(round(float(rate) * dur / 60.0))
                    if 0 <= want_n < len(rs):
                        for i_ in sorted(range(len(rs)),
                                         key=lambda i2: rs[i2][1])[:len(rs) - want_n]:
                            kill.add(i_)
                tbl = item.get("table") or {}
                t_in, t_bt = tbl.get("inside"), tbl.get("between")

                def _rank_fit(mine, tb):
                    # 등수 그대로 실물 분위수 표로 — 어디서 쉬는지는 안 바뀐다
                    n_ = len(mine)
                    if n_ == 0 or not tb:
                        return list(mine)
                    order = sorted(range(n_), key=lambda i2: mine[i2])
                    o_ = [0.0] * n_
                    for rank, i2 in enumerate(order):
                        q_ = (rank / (n_ - 1)) if n_ > 1 else 0.5
                        o_[i2] = float(np_.interp(
                            q_, np_.linspace(0, 1, len(tb)), tb))
                    return o_

                # ★두 표가 같으면 **한 자루**로 등수를 매긴다 — 갈래마다 따로
                #   매기면 위쪽 꼬리가 두 벌 생긴다(m_gapshape 실측 그대로).
                if (t_in == t_bt) or not t_in:
                    _all = _rank_fit([d_ for _s, d_ in rs], t_bt)
                    m_in = [v for v, i2 in zip(_all, inside) if i2]
                    m_bt = [v for v, i2 in zip(_all, inside) if not i2]
                else:
                    m_in = _rank_fit([d_ for (s_, d_), i2 in zip(rs, inside)
                                      if i2], t_in or t_bt)
                    m_bt = _rank_fit([d_ for (s_, d_), i2 in zip(rs, inside)
                                      if not i2], t_bt)
                want, ki, kb = [], 0, 0
                for i_, ins in enumerate(inside):
                    v = (m_in[ki] if m_in else 0.0) if ins else \
                        (m_bt[kb] if m_bt else 0.0)
                    if ins:
                        ki += 1
                    else:
                        kb += 1
                    want.append(0.0 if i_ in kill else v)
                with wave.open(src, "rb") as w_:
                    nch, sw, sr_n, n_fr = (w_.getnchannels(), w_.getsampwidth(),
                                           w_.getframerate(), w_.getnframes())
                    pcm = w_.readframes(n_fr)
                fr = nch * sw
                # ★긴 것(≥big_floor)이 실물보다 많으면 가장 짧은 것부터 big_to 로
                rate2 = item.get("rate2")
                if rate2 and dur > 1.0:
                    _n2 = int(round(float(rate2) * dur / 60.0))
                    _big = sorted([i2 for i2, g_ in enumerate(want)
                                   if g_ >= float(item["big_floor"])],
                                  key=lambda i2: want[i2])
                    for i2 in _big[:max(0, len(_big) - _n2)]:
                        want[i2] = float(item["big_to"])
                buf, cur, shift = bytearray(), 0, []
                for (s_, d_), g_ in zip(rs, want):
                    a_ = max(0, min(n_fr, int(round(s_ * sr_n))))
                    b_ = max(0, min(n_fr, int(round((s_ + d_) * sr_n))))
                    if a_ < cur:
                        continue
                    buf += pcm[cur * fr:a_ * fr]
                    need = int(round(g_ * sr_n))
                    seg = pcm[a_ * fr:b_ * fr]
                    if seg and need > 0:
                        if need <= (b_ - a_):
                            h_ = need // 2
                            buf += seg[:h_ * fr] + seg[(b_ - a_ - (need - h_)) * fr:]
                        else:
                            buf += seg
                            rep = need - (b_ - a_)
                            while rep > 0:
                                take = min(rep, b_ - a_)
                                buf += seg[:take * fr]
                                rep -= take
                    shift.append((s_, s_ + d_, d_ - need / float(sr_n),
                                  need / float(sr_n), (need // 2) / float(sr_n)))
                    cur = b_
                buf += pcm[cur * fr:]
                with wave.open(dst, "wb") as w_:
                    w_.setnchannels(nch)
                    w_.setsampwidth(sw)
                    w_.setframerate(sr_n)
                    w_.writeframes(bytes(buf))

                def _sh(t):
                    # 무음 **안**에 든 시각도 따라간다 — 앞쪽 남김 안이면 그대로,
                    #   뒤쪽 남김 안이면 이 무음의 없앤 길이까지, 잘린 가운데면
                    #   남긴 앞쪽 끝으로 (m_gapshape._sh 그대로).
                    off = 0.0
                    for s0, e0, c_, g_, h_ in shift:
                        if t >= e0:
                            off += c_
                            continue
                        if t <= s0:
                            break
                        if t - s0 <= h_:
                            return round(t - off, 3)
                        if e0 - t <= (g_ - h_):
                            return round(t - off - c_, 3)
                        return round(s0 - off + h_, 3)
                    return round(t - off, 3)

                n_out = len(buf) // fr
                lv2, wsec2, _ = _rms_wins(item, dst)
                rs2 = (_silence_runs(
                    lv2, wsec2,
                    float(np_.percentile(lv2, 90)) - float(item["drop_db"]),
                    item["min_run"]) if lv2 is not None else [])
                stat = {
                    "shaped": True, "sr": sr_n, "frames": n_out,
                    "n_before": len(rs), "sum_before": round(sum(d_ for _s, d_ in rs), 2),
                    "dur_before": round(dur, 2),
                    "n_after": len(rs2), "sum_after": round(sum(d_ for _s, d_ in rs2), 2),
                    "dur_after": round(n_out / float(sr_n), 2),
                    "n_inside": sum(1 for x in inside if x),
                    "n_killed": len(kill),
                    # 재전사를 못 했을 때의 폴백 — 옮겨 쓴 낱말 시각
                    "words": [dict(w["orig"],
                                   **({"start": _sh(w["t0"]), "end": _sh(w["t1"])}
                                      if "start" in w["orig"] or "end" in w["orig"]
                                      else {"t0": _sh(w["t0"]), "t1": _sh(w["t1"])}))
                              for w in words],
                }
            got["gap_stat"] = stat
            _keep(outs, cmd, stat)
            _progress("  [무음꼴] " + (
                f"{stat['n_before']}개 {stat['sum_before']}초 → "
                f"{stat['n_after']}개 {stat['sum_after']}초 · 길이 "
                f"{stat['dur_before']} → {stat['dur_after']}초 · "
                f"낱말 안 {stat['n_inside']} · 없앤 것 {stat['n_killed']}"
                if stat.get("shaped") else "손질 안 함(무음이 없거나 numpy 가 없다)"))
            continue
        # ── 군림보 마스터 오디오 4종 (2026-08-24) — 자·값 전부 서버 데이터.
        #    서버가 이 명령을 줄 때만 돈다(옛 서버 응답과 혼재 무해). 결과는
        #    `_keep` 으로 outs 에도 올린다 — `cmds:` measure 규칙이 읽는 자리다
        #    (안 올리면 재기는 성공하고 다음 줄에서 죽는 그 부류 · §_keep).
        if cmd == "piece_shape":
            # 나레 조각 파생 사본(shape/lvl) — 표·문턱·차례 전부 서버 params.
            #   조각(jobs④ 자르기)이 먼저다 — do⑤ 라 순서가 계약으로 잡혀 있다.
            #   서버가 이 명령을 줄 때만 돈다(연속 나레 채널) — 혼재 무해.
            got["piece_shape_stat"] = piece_shape(item)
            _keep(outs, cmd, got["piece_shape_stat"])
            _ps = got["piece_shape_stat"]
            _progress(f"  [조각손질] 기울기 {_ps['n_shape']}줄"
                  + (f" · 6dB 넘어 안 건드림 {_ps['big']}" if _ps["big"] else "")
                  + (f" · 좁히기 {_ps['n_lvl']}줄" if _ps["n_lvl"] else
                     (f" · 흩어짐 {_ps['spread']}dB(실물보다 좁다 — 안 좁힘)"
                      if _ps["spread"] is not None else ""))
                  + (f" · 오프닝 {_ps['open_gain']:+.2f}dB"
                     if _ps["open_gain"] is not None else ""))
            continue
        if cmd == "render_sfx_bed":
            # 효과음 침대 — 자리·크기·창 전부 서버 params. 나레(narr.wav)가 먼저다.
            got["sfx_bed_stat"] = render_sfx_bed(item)
            _keep(outs, cmd, got["sfx_bed_stat"])
            _st = got["sfx_bed_stat"]
            _progress(f"  [효과음침대] {_st['n']}발 · {len(_st['files'])}종 · "
                  f"{_st['bytes']:,}B"
                  + (f" · 자리 밖 {len(_st['dropped'])}발" if _st["dropped"] else ""))
            continue
        if cmd == "master_drive":
            # 마스터 드라이브 이분법 — 한 왕복 안에서 순차 bake·측정(12회 자).
            got["master_probe"] = master_drive(item)
            _keep(outs, cmd, got["master_probe"])
            _mp = got["master_probe"]
            _progress(f"  [마스터] 드라이브 {_mp['drive']:+.2f}dB → I {_mp['I']:.2f} · "
                  f"TP {_mp['TP']:.2f} · LRA {_mp['LRA']:.2f} · bake {_mp['n_bakes']}회"
                  + (f" · AAC 상승 {_mp['rise']:+.2f}dB" if _mp.get("rise") else ""))
            continue
        if cmd == "measure_hf":
            got["hf_probe"] = measure_hf(item)
            _keep(outs, cmd, got["hf_probe"])
            _progress(f"  [고역] 8k~16k {got['hf_probe']['hf']:.2f}dBFS")
            continue
        if cmd == "measure_openvoice":
            got["ov_probe"] = measure_openvoice(item)
            _keep(outs, cmd, got["ov_probe"])
            _ov = got["ov_probe"]
            _progress("  [오프닝 목소리] "
                  + (f"바닥위 {_ov['open']:.2f}dB · 본문 {_ov['body']:.2f}dB"
                     if _ov.get("ok") else "못 쟀다(구간이 너무 짧다)"))
            continue
        if cmd == "iras_probe":
            # ★이라스토야 색인 프로브 (2026-08-25) — 로컬 조회(네트워크·키 0).
            #   경로·질의·후보 수 전부 서버가 준다. **판정은 서버가 한다.**
            got["iras_probe"] = iras_probe(item)
            _keep(outs, cmd, got["iras_probe"])
            _sc = [v.get("score") for v in got["iras_probe"].values()
                   if v.get("score") is not None]
            _progress(f"  [이라스토야] {len(got['iras_probe'])}칸 조회 — 점수 있는 칸 "
                  f"{len(_sc)}", flush=True)
            continue
        if cmd == "place_illust":
            # ★이라스토야 실물 놓기 (2026-08-25) — 흰 판(슬롯)에 실측 비율로.
            #   fit/band/slot 전부 서버 params — 러너에 채널 값 0.
            _pi = place_illust(item)
            _keep(outs, cmd, _pi)
            _progress(f"  [일러놓기] {os.path.basename(str(item.get('out')))} — "
                  f"잉크 {_pi.get('ink_w')}x{_pi.get('ink_h')} / 판 "
                  f"{_pi.get('w')}x{_pi.get('h')}", flush=True)
            continue
        if cmd == "ask_text":
            # ★★**글만** 보내고 답을 받는다 (2026-08-23) — 첨부가 없다.
            #   인물형 대본은 **글(원문)에서** 나오므로 `ask_video` 로는 못 돕는다
            #   (그쪽은 소재 영상이 반드시 있어야 한다).
            #   ★선택이다 — 열쇠가 없으면 빈 묶음이 오고 그냥 지나간다.
            _k = item.get("key") or "draft"
            # ★`else` 갈래도 **걸러진 헤더**를 쓴다 — 원본 headers 를 그대로 쓰면
            #   `asr_keys` 같은 묶음이 HTTP 헤더로 나가 TypeError 로 죽는다
            #   (§`auth_headers` 주석 · 2026-08-26).
            got[_k] = ask_text(item, lambda: auth_headers(
                {"auth": {"service": item.get("service")}} if item.get("service") else {},
                headers))
            _keep(outs, cmd, got[_k])
            _n = len(((got.get(_k) or {}).get("cards")) or [])
            _progress(f"  [모델] 초안 {'받음 — 카드 %d장' % _n if _n else '없음(열쇠가 없거나 못 받았다) — 직접 쓰면 된다'}",
                  flush=True)
            continue
        if cmd == "fact_check":
            # 현재 검수 정책으로 실행한다. 미완료는 대기하며 지적은 서버가 경고로 해석한다.
            got["factcheck"] = fact_check(item, lambda: auth_headers({"auth": {
                "service": item.get("service")}}, headers) if item.get("service") else None)
            _keep(outs, cmd, got["factcheck"])
            _progress("  [팩트체크] " + ("지적 "
                  + str(len((got["factcheck"] or {}).get("items") or [])) + "건"
                  if got["factcheck"] else "건너뜀(키 없음)"))
            continue
        if cmd == "prepare_local_shop_plan":
            from local_shop_plan import prepare
            from volcano_run import resolve_review_policy
            selection=item['selection'];review=selection.get('video_review') or {}
            review_headers=(photo_headers(res,review.get('service'),headers)
                if resolve_review_policy(selection.get('review_policy'))['provider']=='evolink' else None)
            key=item.get('as') or 'local_render_plan_result'
            got[key]=prepare(item,headers=review_headers)
            _keep(outs,cmd,got[key])
            continue
        if cmd == "prepare_local_person_plan":
            from local_person_plan import prepare as prepare_person
            from volcano_run import resolve_review_policy
            selection=item['selection'];review=selection.get('video_review') or {}
            review_headers=(photo_headers(res,review.get('service'),headers)
                if resolve_review_policy(selection.get('review_policy'))['provider']=='evolink' else None)
            key=item.get('as') or 'local_render_plan_result'
            got[key]=prepare_person(item,headers=review_headers)
            _keep(outs,cmd,got[key])
            continue
        if cmd == "prepare_local_person_delivery":
            from local_person_plan import prepare_delivery
            key=item.get('as') or 'local_person_delivery_result'
            got[key]=prepare_delivery(item)
            _keep(outs,cmd,got[key])
            continue
        if cmd == "deliver_local_source":
            from local_source_plan import export_files
            execute({'write_files':export_files(item)})
            continue
        if cmd == "prepare_local_source_plan":
            from local_source_plan import prepare
            from volcano_run import resolve_review_policy
            review=item['selection'].get('video_review') or {}
            review_headers=photo_headers(res,review.get('service'),headers) if resolve_review_policy(item['selection'].get('review_policy'))['provider']=='evolink' else None
            got[item.get('as') or 'local_render_plan_result']=prepare(item,headers=review_headers)
            continue
        if cmd == "execute_local_source_plan":
            from local_source_plan import verify_proof,checked_execution
            got.update(execute(checked_execution(verify_proof(item['proof']))))
            continue
        if cmd == "deliver_local_redub":
            from local_redub_delivery import prepare_execution
            try:got.update(execute(prepare_execution(item)))
            except StepError as exc:
                if getattr(exc,'execution_next_step',None)=='redub_master':exc.execution_next_step='deliver'
                raise
            continue
        if cmd == "prepare_local_redub_plan":
            from local_redub_plan import prepare as prepare_redub
            from volcano_run import resolve_review_policy
            selection=item['selection'];review=selection.get('video_review') or {}
            review_headers=(photo_headers(res,review.get('service'),headers)
                if resolve_review_policy(selection.get('review_policy'))['provider']=='evolink' else None)
            try:got[item.get('as') or 'local_render_plan_result']=prepare_redub(item,headers=review_headers)
            except StepError as exc:
                if res.get('next_step')=='deliver' and getattr(exc,'execution_next_step',None)=='redub_master':exc.execution_next_step='deliver'
                raise
            _keep(outs,cmd,got[item.get('as') or 'local_render_plan_result'])
            continue
        if cmd == "prepare_local_render_plan":
            from local_render_plan import prepare_local_render_plan
            from volcano_run import resolve_review_policy
            selection = item['selection']
            review = selection.get('photo_review') or {}
            review_headers = (photo_headers(res, review.get('service'), headers)
                              if resolve_review_policy(selection.get('review_policy'))['provider'] == 'evolink' else None)
            key = item.get('as') or 'local_render_plan_result'
            got[key] = prepare_local_render_plan(item, headers=review_headers)
            _keep(outs, cmd, got[key])
            continue
        if cmd == "agy_preflight":
            # 인물형 롱폼 env 단계의 이른 AGY 관문(2026-10-05 · 영상 없이 설치·로그인·한도만). 판정은 서버가 한다.
            from subject_agy_run import agy_preflight, SubjectAgyError
            key = item.get('as') or 'agy_preflight'
            try:
                got[key] = agy_preflight(item)
            except SubjectAgyError as error:
                raise StepError(str(error)) from error
            _keep(outs, cmd, got[key])
            continue
        if cmd == "prepare_agy_focus":
            # 인물형 롱폼 피사체(2026-10-05 · AGY 필수 · 로컬 추론 0). 결과 모양은 prepare_local_focus 와 같다.
            from subject_agy_run import prepare_agy_focus, SubjectAgyError
            key = item.get('as') or 'local_focus_result'
            try:
                got[key] = prepare_agy_focus(item)
            except SubjectAgyError as error:
                raise StepError(str(error)) from error
            _keep(outs, cmd, got[key])
            continue
        if cmd == "prepare_agy_images":
            # 인물형 롱폼 그림(2026-10-09 · 설계 docs/2026-10-09_롱폼-그래픽-다양성 3-2) — 제작표 media.generate 를 학생 agy 그림 도구로.
            # 거부(한도·속도·로그인)는 longform_agyimage 안에서 refused 칸이 있는 «막힘» 결과로 바뀐다(prepare_agy_focus 와 같은 관례 —
            # 서버가 그 결과를 보여 주고 사람이 다시 내기 전에는 다시 보내지 않는다). 일감 규격 오류만 여기서 StepError 로 멈춘다.
            from longform_agyimage import prepare_agy_images, LongformAgyImageError
            key = item.get('as') or 'longform_images'
            try:
                got[key] = prepare_agy_images(item)
            except LongformAgyImageError as error:
                raise StepError(str(error)) from error
            _keep(outs, cmd, got[key])
            continue
        if cmd == "prepare_cutouts":
            # 인물형 롱폼 누끼(2026-10-17 · 신고 #121) — 제작표 media.cutout 을 실행기 공용 nukki.py 로(본인 Cloudflare 0순위 · 아니면 Replicate).
            # 거부·엔진 없음은 longform_cutout 안에서 refused 칸이 있는 «막힘» 결과가 된다(prepare_agy_images 와 같은 관례).
            from longform_cutout import prepare_cutouts, LongformCutoutError
            key = item.get('as') or 'longform_cutouts'
            try:
                got[key] = prepare_cutouts(item)
            except LongformCutoutError as error:
                raise StepError(str(error)) from error
            _keep(outs, cmd, got[key])
            continue
        if cmd == "prepare_local_focus":
            from local_focus import prepare_local_focus
            from volcano_run import resolve_review_policy
            selection = item['selection']
            review = selection.get('video_review') or selection.get('photo_review') or {}
            review_headers = (photo_headers(res, review.get('service'), headers)
                              if resolve_review_policy(selection.get('review_policy'))['provider'] == 'evolink' else None)
            key = item.get('as') or 'local_focus_result'
            got[key] = prepare_local_focus(item, headers=review_headers)
            _keep(outs, cmd, got[key])
            continue
        if cmd == "select_subjects":
            from subject_focus import select_subjects
            from volcano_run import resolve_review_policy
            review = item.get("video_review") or item.get("photo_review") or {}
            key = item.get("as") or "subject_focus"
            review_headers = (photo_headers(res, review.get("service"), headers)
                              if resolve_review_policy(item.get('review_policy'))['provider'] == 'evolink' else None)
            got[key] = select_subjects(item, headers=review_headers)
            _keep(outs, cmd, got[key])
            continue
        if cmd == "measure_source_motion":
            from subject_focus import measure_source_motions
            key = item.get('as') or 'source_motion_results'
            got[key] = measure_source_motions(item)
            _keep(outs, cmd, got[key])
            continue
        if cmd == "review_film_frames":
            from volcano_run import review_film_frames, resolve_review_policy
            review = item.get("photo_review") or {}
            key = item.get("as") or "film_semantic_frames"
            review_headers = (photo_headers(res, review.get("service"), headers)
                              if resolve_review_policy(item.get('review_policy'))['provider'] == 'evolink' else None)
            got[key] = review_film_frames(item, headers=review_headers)
            _keep(outs, cmd, got[key])
            continue
        if cmd == "recover_photos":
            _review = next((j.get('photo_review') for j in item.get('jobs') or []
                            if j.get('photo_review')), {})
            _hdr = photo_headers(res, _review.get('service'), headers)
            got['photo_recovery'] = recover_photos(item, headers=_hdr)
            _keep(outs, cmd, got['photo_recovery'])
            continue
        if cmd == "search_videos":
            # 인물형 소재 탐색 (2026-09-16) — 서버가 준 소스·검색어 사다리로 **동영상 후보**를
            # 찾아 목록으로 돌려준다. 고르지 않는다(판정은 서버 `rank_source_candidates`·저자).
            # ★`source_candidates` 는 «찾아 봤다» 의 증거다 — 0건이어도 키를 넣는다(§«안 쟀다»
            #   와 «재 봤더니 0개» 는 다른 말). 못 부른 소스는 `source_search_errors` 로 같이 간다.
            found = search_videos(item)
            got["source_candidates"] = list(found.get("candidates") or [])
            got["source_search_errors"] = list(found.get("errors") or [])
            _keep(outs, cmd, {"count": len(got["source_candidates"]), "errors": len(got["source_search_errors"]),
                              "from_cache": bool(found.get("from_cache"))})
            _progress(f"  [소재 탐색] 후보 {len(got['source_candidates'])}건"
                      + (f" · 실패한 소스 {len(got['source_search_errors'])}" if got["source_search_errors"] else "")
                      + (" (캐시)" if found.get("from_cache") else ""))
            continue
        if cmd == "search_images":
            # 서버가 시킨 검색어·API·읽을 자리로 **사진을 받아온다.** 판정은 서버가 한다.
            # ★못 찾은 컷은 **비워서** 돌려준다 — 아무 그림이나 채우면 자막과 무관한
            #   화면이 오류 없이 완성본까지 간다(이 채널이 반려당한 그 사고다).
            # ★같은 그림이 두 컷에 들어가면 **컷 튐 게이트가 반려한다** —
            #   사다리 마지막 칸이 인물명이라 실제로 그렇게 겹쳤다(실측 컷 1·3 동일).
            #   집합 하나를 컷마다 이어 쓴다.
            _review = item.get('photo_review') or {}
            _hdr = photo_headers(res, _review.get('service'), headers)
            found = search_images(item, seen=_photo_seen, headers=_hdr)
            bag = got.setdefault("photos", {})
            bag[str(item["card"])] = found
            _keep(outs, cmd, bag)
            _progress(f"  [사진] 컷 {item['card']} — {len(found)}장"
                  + (f" ({found[0]['w']}x{found[0]['h']} {found[0]['provider']})"
                     if found else " ★못 찾았다 — 사람이 채운다"))
            continue
        if cmd == "cut_signature":
            # 구운 조각의 화면 서명. **판정은 서버가 한다** — 여기는 재고 접기만.
            # ★서버가 `correlate` 로 **무엇을 견줄지** 선언하면 상관 스칼라만 올린다.
            #   예전에는 벡터를 통째로 보내 한 호출이 3.76MB 였고 워커가 메모리로
            #   죽었다(2026-08-17 · 하루 553건). 자는 그대로고 오가는 양만 줄었다.
            sigs = cut_signatures(item)
            # ★접힌 샷 행렬(corr64)은 `shot_scan` 칸이다 (2026-08-24) — `cut_sigs`
            #   에 넣으면 뒤 단계(audit_jump)가 컷 지도로 오독한다. 모양으로 가른다
            #   — 채널 이름을 알 필요가 없다(구동기는 채널을 모른다).
            if isinstance(sigs, dict) and sigs.get("_fold") == "corr64":
                got["shot_scan"] = sigs
                _progress(f"  [샷 서명] {len(sigs.get('ids') or [])}샷 → 상관 행렬")
            else:
                got["cut_sigs"] = sigs
                _progress(f"  [컷 서명] {len(sigs)}컷")
            _keep(outs, cmd, sigs)
            continue
        if cmd == "resolve_files":
            from volcano_run import resolve_files
            got[item["as"]] = resolve_files(item)
            _keep(outs, cmd, got[item["as"]])
            _progress(f"  [파일 조회] {len(got[item['as']])}개 실물 경로 확인")
            continue
        if cmd == "measure_frame":
            # 컷마다 알맹이 사각형·얼굴·움직임을 잰다. **판정은 서버가 한다** — 여기는 읽기만.
            # ★컷끼리 독립(로컬 ffmpeg+OpenCV)이라 서버가 준 폭으로 **동시에** 잰다
            #   (2026-08-24). 폭이 없으면 지금까지처럼 순차다. 임시폴더는 컷마다
            #   가른다 — 한 폴더를 동시에 쓰면 프레임 파일이 충돌한다.
            import tempfile
            frames = dict(item.get("base") or {})
            _cuts = item["cuts"]
            try:
                _mw = int(item.get("parallel") or 1)
            except (TypeError, ValueError):
                _mw = 1
            _mw = max(1, min(_mw, len(_cuts) or 1))
            with tempfile.TemporaryDirectory() as _td:
                if _mw > 1:
                    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

                    def _mf_one(pair):
                        _i, _it = pair
                        _sub = os.path.join(_td, f"c{_i:03d}")
                        os.makedirs(_sub, exist_ok=True)
                        return str(_it["card"]), _measure_frame_row(dict(_it, tmp=_sub))

                    with ThreadPoolExecutor(max_workers=_mw) as _ex:
                        for _k, _v in _ex.map(_mf_one, list(enumerate(_cuts))):
                            frames[_k] = _v
                else:
                    for it in _cuts:
                        frames[str(it["card"])] = _measure_frame_row(dict(it, tmp=_td))
            got[item.get("as") or "frames"] = frames
            _keep(outs, cmd, frames)
            _nf = sum(1 for v in frames.values() if v["by"] == "face")
            _progress(f"  [컷 프레임] {len(frames)}컷 · 얼굴로 잡은 것 {_nf}")
            continue
        if cmd == "measure_audio":
            m = measure_audio(item)
            outs["measure_audio"] = json.dumps(m, ensure_ascii=False)
            _progress(f"  [음악] {os.path.basename(item.get('path') or '')} "
                  f"{m['lufs']:.1f} LUFS · 음색 {m['brightness_hz']:.0f}Hz · "
                  f"온셋 {m['onset_per_s']:.2f}/s · 강약 {m['dyn_db']:.1f}dB")
            continue
        if cmd == "upgrade_politics_baseline":
            if c is None:
                raise StepError("기존 작업을 보존하여 갱신하려면 인증된 Client가 필요합니다")
            from ta_upgrade_local import Transport, upgrade, native, safe
            original = json.loads(safe(native(item["workdir"]), ".ta-job-receipt.json").read_bytes())
            if (item.get("action") != "upgrade-preserving-work" or original.get("job_id") != item.get("job_id")
                    or original.get("pins", {}).get("pipeline", {}).get("sha256") != item.get("old_sha256")):
                raise StepError("서버 이행 명령과 원래 작업 영수증이 다릅니다. 기존 기록을 보존했습니다")
            result = upgrade(Transport(c.url, c.token, client=c), item["workdir"], item["target_manifest_sha256"], approved=True)
            got.update({k:result[k] for k in ("ta_job_id", "ta_upgrade_id")})
            got["resume"] = item.get("resume") is True
            continue
        if cmd == "fetch_asset":
            if _fa_done:
                continue                       # ★위에서 동시에 이미 받았다
            if c is None:
                raise StepError("자산을 받으려면 Client 가 필요하다 — execute(..., c=클라이언트)")
            _fetch_asset(item, c)
            continue
        if cmd == "survey":
            from volcano_run import current_review_context, _photo_write_state
            argv = [a.replace("@@PY@@", sys.executable).replace(
                    "@@RUNNER@@", os.path.dirname(os.path.abspath(__file__))) for a in item["argv"]]
            context = current_review_context()
            work = argv[argv.index('--work')+1] if '--work' in argv else os.path.dirname(os.path.abspath(argv[2]))
            context['budget'] = context.get('budget') or os.path.join(work, 'review-budget.sqlite3')
            # A file avoids Windows argv limits as completed window replies accumulate.
            settings_key = hashlib.sha256(json.dumps(context,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            settings = os.path.join(work, '_survey_review', 'execution-'+settings_key+'.json')
            os.makedirs(os.path.dirname(settings),exist_ok=True)
            _photo_write_state(settings, context)
            if '--review-json' in argv:
                pos = argv.index('--review-json');del argv[pos:pos+2]
            if '--review-file' in argv:
                pos = argv.index('--review-file');del argv[pos:pos+2]
            argv.extend(['--review-file',settings])
            child_env = dict(os.environ)
            if context['policy']['provider'] == 'evolink':
                auth = item.get('auth')
                if auth:
                    argv.extend(['--auth-json',json.dumps(auth,ensure_ascii=False)])
                    # Only an explicitly supplied header is transported here. The
                    # child resolves declared key files after checking its receipt.
                    value = (headers or {}).get(auth['header'])
                    if value:
                        if isinstance(value,bytes): value = value.decode('utf-8')
                        scheme = auth.get('scheme') or ''
                        if not value.startswith(scheme): raise StepError('훑기 인증 헤더가 서버의 인증 규약과 다릅니다')
                        child_env[auth['env_var']] = value[len(scheme):]
            else:
                child_env.pop('EVOLINK_API_KEY',None)
                child_env.pop('GOOGLE_GEMINI_API_KEY',None)
            p = run_argv(argv, capture=True, env=child_env)
            _child_review_control(p.stdout)
            if p.returncode:
                raise StepError("긴 소재 훑기 실패:\n" + err_gist(p.stderr or p.stdout, 1200))
            try:
                picks = json.loads(p.stdout)
                if not isinstance(picks, list) or not all(isinstance(v, dict) for v in picks):
                    raise ValueError("picks")
            except (TypeError, ValueError) as exc:
                raise StepError("훑기 결과를 대목 목록으로 읽지 못했습니다") from exc
            outs[cmd] = p.stdout
            import survey
            survey.report(picks)
            continue
        # ★서버가 후보를 여럿 주면 **되는 것을 고른다.** 판단이 아니라 존재 확인이다 —
        #   무엇을 시도할지는 서버가 정했고, 여기는 이 기계에 있는 것을 집을 뿐이다.
        #   예전에는 서버가 `/usr/bin/env` 하나만 줘서 **윈도우에서 통째로 막혔다.**
        if item.get("argv_candidates"):
            # ★**존재가 아니라 성공으로** 고른다. 있는 것과 도는 것은 다르다 —
            #   윈도우 PATH 앞자리의 0바이트 `python3.exe` 스텁이 실제로 그렇다
            #   (`shutil.which` 는 찾지만 돌리면 "Python was not found" 만 찍는다).
            #   서버가 `pick_by` 로 무엇을 성공으로 볼지 말해 준다(판단은 서버에 남는다).
            want = item.get("pick_by") or {}
            from volcano_run import _rc_text                       # noqa: PLC0415
            # started = 있는 파이썬을 실제로 띄웠는데 기대한 답이 아니었던 후보 — «설치하라» 와 «설치는 됐는데 못 돈다» 를 가르는 사실.
            picked, tried, started = None, [], []
            for cand in item["argv_candidates"]:
                t = cand[0]
                found = t if (os.path.isabs(t) and os.path.exists(t)) else shutil.which(t)
                if not found:
                    tried.append(f"{t}: 없음")
                    continue
                if _windows_store_python_stub(found):
                    # 있어도 돌지 않는 것은 «없음» 이다 — pick_by 가 없는 단계도 같은 판정(신고 #45).
                    tried.append(f"{t}: Microsoft Store 설치 안내 스텁({found}) — 파이썬이 아니다")
                    continue
                if not want:                       # 기대치가 없으면 존재로 만족한다
                    picked = cand
                    break
                try:
                    r = _spawn(cand, capture_output=True, timeout=180, **TEXT_PIPE)
                except Exception as e:             # noqa: BLE001
                    tried.append(f"{t}: {_spawn_failed(e)}")
                    continue
                if cmd == "runner_install":
                    moved = _installer_moved(r)
                    if moved is not None:
                        raise moved
                ok = r.returncode == want.get("rc", 0)
                if ok and want.get("stdout") == "json":
                    ln = [x for x in (r.stdout or "").strip().splitlines()
                          if x.strip().startswith("{")]
                    try:
                        json.loads(ln[-1]) if ln else None
                        ok = bool(ln)
                    except Exception:              # noqa: BLE001
                        ok = False
                if ok:
                    picked = cand
                    break
                started.append(t)
                tried.append(f"{t}: rc={_rc_text(r.returncode)} "
                             f"{((r.stderr or r.stdout) or '').strip()[:60]}")
            if picked is None:
                # ★이 실행기 자신이 지금 도는 파이썬이다(sys.executable) — 후보가 전부 없거나(윈도우 PATH 의 0바이트 스토어 스텁
                #   «Python was not found» rc=9009 포함) 못 돌면 같은 인자로 이 파이썬을 시도한다(2026-10-17 · 쇼핑 env 2건).
                for cand in item["argv_candidates"]:
                    rest = _python_launcher_rest(cand)
                    if rest is None or not sys.executable:
                        continue
                    alt = [sys.executable] + rest
                    try:
                        r = _spawn(alt, capture_output=True, timeout=180, **TEXT_PIPE) if want else None
                    except Exception as e:             # noqa: BLE001
                        tried.append(f"{sys.executable}: {_spawn_failed(e)}")
                        continue
                    if r is None or r.returncode == want.get("rc", 0):
                        picked = alt
                        break
                    started.append(sys.executable)
                    tried.append(f"{sys.executable}: rc={_rc_text(r.returncode)}")
            if picked is None:
                # ★10-23 신고(뇌전구 env · 윈도우): 설치된 파이썬(venv·이 실행기 자신 포함)이 전부 0xC0000142 로 시작조차 못 했는데
                #   «파이썬을 설치하라» 고 안내했다 — 이미 있는 것을 다시 깔게 하는 틀린 처방이다. 띄워 본 후보가 있으면 설치가 아니라
                #   그 종료 코드(뜻은 각 줄)가 원인이라고 말한다.
                advice = ("  위 파이썬은 설치돼 있고 띄워졌지만 기대한 답 없이 끝났다 — 다시 설치할 문제가 아니라 각 줄의 종료 코드가 원인이다"
                          "(0xC0000142·0x40010004 처럼 출력 없이 끝났으면 윈도우나 보안 프로그램이 시작을 막은 것 — PC 를 다시 켠 뒤 같은 명령)."
                          if started else
                          "  파이썬 3.9 이상을 설치하고 PATH 에 있는지 확인하라 "
                          "(윈도우: winget install Python.Python.3.12).")
                raise StepError(
                    "파이썬을 실행할 방법을 못 찾았다.\n  " + "\n  ".join(tried) + "\n" + advice)
            item = dict(item, argv=picked)
        if cmd == "vmake_clear":
            done = run_vmake_job(item, run_argv)
            got.update(_pick_from({"vmake_done": done}, res.get("measure")))
            continue
        if cmd == "source_mp4":
            source_mp4(item)
            continue
        if cmd == "probe" and outs.get("probe"):
            continue
        if item.get("argv"):
            if item.get('resolve_inputs'):
                from local_paths import resolve_declared_inputs
                try:
                    item, resolved = resolve_declared_inputs(item)
                except (OSError, ValueError) as error:
                    raise StepError(str(error)) from error
                # These are local observations, so stale server carry values
                # cannot overwrite the actual filesystem spelling below.
                got.update(resolved)
            tool = item["argv"][0]
            # ★도구가 없으면 트레이스백 대신 사람이 읽을 말로 멈춘다.
            #   선택 명령(optional)이면 건너뛴다 — 원문을 이미 갖고 있는 경우가 그렇다.
            #   yt-dlp 는 PATH 에 없어도 실행기가 자기 파이썬에 공식 판을 올려 부른다(volcano_run._spawn · 신고 #211).
            if not (os.path.isabs(tool) or shutil.which(tool) or (_is_ytdlp(tool) and not item.get("optional"))):
                if item.get("optional"):
                    _progress(f"  [건너뜀] '{tool}' 이 없다 — 선택 명령이다. {item.get('why') or ''}")
                    continue
                raise StepError(
                    f"'{tool}' 이 설치돼 있지 않다. 이 단계에 필요한 도구다.\n"
                    f"  {item.get('note') or ''}\n"
                    f"  env 단계가 무엇이 없는지 알려준다 — 설치한 뒤 다시 하라.")
            # ★★유료 일감의 건너뛰기 계약 (2026-09-01 실측 — 하드섭 제거가
            #   재실행마다 같은 원본을 또 지워 **또 과금**되다 크레딧 벽에 닿았다).
            #   서버가 skip_if(키-인-파일명)를 실어 주면 그 규칙으로만 건너뛴다 —
            #   실행기 자기 기준(파일 존재)으로 건너뛰면 §옛 음성 사고가 된다.
            _si = item.get("skip_if")
            if _si and _have(_si):
                _progress(f"  [건너뜀] {cmd or tool} — 이미 있다: {_si['path']}")
                continue
            _progress(f"  [{cmd or 'run'}] {tool} …")
            p = run_argv(item["argv"], capture=True)
            if p.returncode != 0 and item.get("allow_fail"):
                #   ★★**실패해도 넘어가라고 서버가 선언한 명령** (2026-09-04).
                #     `optional` 은 «그 도구가 **없을 때** 건너뛴다» 는 뜻이라, 도구는 있는데
                #     명령이 실패하는 경우(인터넷 막힌 기계의 `pip install`)를 못 덮는다.
                #     자동 설치는 «되면 그 축이 켜지고, 안 되면 그 축만 못 잰다» 이므로
                #     여기서 체인을 죽이면 안 된다 — 끄기로 했으면 **받는 쪽이 그것을 알아야 한다**.
                _progress(f"  [넘어감] {cmd or tool} 이 실패했다(rc={p.returncode}) — "
                      f"서버가 «실패해도 된다» 고 선언한 명령이다. "
                      f"{item.get('why') or ''}")
                _progress(f"    {err_gist(p.stderr or p.stdout, 300)}")
                continue
            if p.returncode != 0 and cmd == "runner_install":
                # 설치기가 새 실행기를 설치했고 이 프로세스만 옛 코드다(종료 4 + restart_required) — 같은 단계를 새 실행기로 다시 띄운다.
                #   후보 고르기의 첫 실행은 설치기의 «확인» 이라 대개 여기서 처음 설치된다(설치기 .probed 표식).
                moved = _installer_moved(p)
                if moved is not None:
                    raise moved
            if p.returncode != 0:
                _miss = missing_inputs(item["argv"])
                raise StepError(f"실행 실패: {tool}\n{failure_text(p)}"
                                + (("\n  ★입력 파일이 없습니다: " + " · ".join(_miss)
                                    + " (윈도우 ffmpeg 는 이것을 «Illegal byte sequence» 라고 "
                                      "말합니다 — 파일이 없다는 뜻입니다)") if _miss else "")
                                + _tool_failure_hint(tool, p.stderr or ""))
            # ★★어느 통에서 읽을지 **서버가 말한다**. ffmpeg 의 `loudnorm`·
            #   `ebur128` 은 측정값을 **stderr** 로 낸다 — stdout 만 담으면
            #   빈 문자열이 되고, 그 뒤 `_measure` 가 "출력이 없다" 로 죽는다.
            #   실측(2026-08-18): 마스터 오디오 측정에서 32명이 그렇게 막혔다.
            #   ★기본은 stdout 이다 — 지금까지 쓰던 명령들이 그렇다.
            _child_review_control(p.stdout)
            captured = p.stderr if item.get("capture") == "stderr" else p.stdout
            if not (captured or "").strip() and any(
                    isinstance(r, dict) and r.get("from") == f"cmd:{cmd}" and str(r.get("unit") or "").startswith("json_")
                    for r in (res.get("measure") or [])):
                # ★10-22 회원 신고(영화 롱폼 longmovie_status · 윈도우): 결과 JSON 을 내야 하는 명령이 종료 코드 0 인데 출력이 비었다.
                #   예전에는 여기서 그대로 넘겨 _measure 가 «JSON 을 내놓지 않았다: ''» 만 말했다 — 종료 코드·걸린 시간·오류 출력(stderr)을
                #   버려 무엇이 왜 조용히 끝났는지 남지 않았다. 실패한 명령과 같은 증거(failure_text)를 싣는다.
                raise StepError(f"'{cmd}' 이 결과 JSON 을 내지 않고 끝났다: {tool}\n{failure_text(p)}")
            outs[cmd or tool] = captured
        elif cmd:
            _progress(f"  [건너뜀] '{cmd}' 는 실행할 argv 가 없다 — 사람이 할 일이다")
        else:
            # ★★`cmd` 도 `argv` 도 없는 지시는 **아무 말도 없이 지나갔다** (2026-08-17).
            #   서버가 `cmd` 칸을 빼먹었을 때 정확히 여기로 떨어져, 사진 검색 지시
            #   20건이 오류 0줄로 통째로 사라졌다(받은 사진 0장). 그 뒤 단계는 "왜
            #   비었지" 를 알 방법이 없다.
            #   §"모르는 모양을 조용히 넘기지 않는다" 는 `jobs` 에만 적혀 있었고
            #   `do` 에는 이 구멍이 남아 있었다.
            raise StepError(
                f"서버 지시에 `cmd` 도 `argv` 도 없다 — 키 {sorted(item)}.\n"
                "  이건 수강생이 고칠 수 있는 것이 아니다(서버 쪽 누락이다). "
                "여기서 멈춘다 — 조용히 넘기면 그 일이 통째로 빠진 채 완성된다.")

    # ⑥
    if res.get("concat_argv"):
        run_argv(res["concat_argv"])
    if res.get("argv"):
        _progress(f"  [렌더] {res['argv'][0]} …")
        run_argv(res["argv"])

    for note in res.get("verify_note") or []:
        _progress(f"  [확인할 것] {note}")
    # ★★`verify` 는 **묶음일 수도 목록일 수도** 있다 (2026-09-01 수강생 신고 —
    #   쇼핑 `shop_render` 는 `[{"path": …, "min_bytes": …}]` 목록을 주는데 여기가
    #   dict 만 가정해 **마스터를 다 굽고 나서** AttributeError 로 죽었다).
    #   목록 원소는 두 꼴: {argv, expect…}(명령 확인) · {path, min_bytes}(산출물 크기).
    for v in ([res["verify"]] if isinstance(res.get("verify"), dict)
              else (res.get("verify") or [])):
        if not isinstance(v, dict):
            continue
        if v.get("argv"):
            p = _spawn(v["argv"], capture_output=True, **TEXT_PIPE)
            got_s = (p.stdout or "").strip()
            if v.get("expect") is not None and got_s != str(v["expect"]):
                raise StepError(f"확인 실패({v.get('cmd')}): {got_s!r} ≠ {v['expect']!r}\n"
                                f"  {v.get('note') or ''}")
            _progress(f"  [확인] {v.get('cmd')} = {got_s}")
        elif v.get("path"):
            _sz = os.path.getsize(v["path"]) if os.path.exists(v["path"]) else -1
            _mb = int(v.get("min_bytes") or 1)
            if _sz < _mb:
                raise StepError(
                    f"확인 실패: {v['path']} 크기 {_sz}B < 최소 {_mb}B — "
                    "산출물이 비었거나 안 만들어졌습니다.")
            _progress(f"  [확인] {v['path']} = {_sz}B (최소 {_mb}B)")

    # ★★`got` 에 이미 담긴 값을 **서버가 읽는 이름으로** 옮긴다 (2026-08-22).
    #   전사 갈래는 `got["words"]["SRC"]` 로 담는데 서버는 `payload.src_words` 를
    #   읽는다. 그 변환을 **산문으로만** 시켰더니(`"payload.src_words = words['SRC']"`)
    #   배급 실행기를 안 쓰는 클라가 못 지켜 값이 통째로 안 왔다 — 304건·66명.
    #   §"무엇을 재라를 산문으로 주면 안 된다 — `measure` 로 **데이터로** 준다".
    #   ★`_measure` 보다 **먼저** 돌린다 — 같은 이름을 `_measure` 가 덮을 수 있고,
    #     그때는 새로 잰 값이 이겨야 한다.
    _p = _pick_from(got, res.get("measure"))
    got.update(_p)
    _m = _measure(res, res.get("measure"), outs)
    got.update(_m)
    # ★방금 잰 이름을 알려 준다 — 그 칸은 `carry` 가 덮지 못한다(위 설명).
    # ★★pick 산출도 «방금 잰 값»이다 (2026-08-24 실물: shop_align 이 words 를
    #   pick 으로 선언했는데 fresh 에 안 들어가 carry 에코된 **옛 대본의 전사가
    #   방금 전사를 도로 덮었다** — 수강생이 거짓 「whisper 고장」 진단에 갇혔다).
    # got starts empty; command outputs are fresh too. Server echoes enter only
    # here, so an echoed value alone never becomes a fresh measurement.
    _carry_into(res, got, fresh=set(got))
    return got


def _machine_work(res):
    """`need_input` 인데 **기계가 할 일**이 실려 있으면 무엇이 실렸는지 (2026-09-04).

    ■ 왜 이것을 말하나
        need_input에 실행 가능한 일을 잘못 실으면 구동기는 실행 전에 멈춘다.
        과거 probed의 survey가 이 상태였고 2026-09-07 서버에서 execute로 연결했다.
        지금은 훑기 실행 뒤 author가 소재 선택을 기다린다. 조교 체인의 setup/start도
        execute로 연결되어 있다. 새 단계가 같은 실수를 하면 이 경보가 알려 준다.
    ★★세는 것은 **실행기가 실제로 돌릴 수 있는 것**뿐이다. `do` 에는 `{"cmd":"transcript",
      "hint":…}` 처럼 argv 가 없는 «사람이 할 일» 도 들어온다(실행기 자신이 그렇게 말하고
      건너뛴다) — 그것까지 세면 정상 응답마다 경고가 떠서 아무도 안 읽게 된다.
    """
    out = []
    runnable = [d for d in (res.get("do") or [])
                if isinstance(d, dict) and (d.get("argv") or d.get("argv_candidates")
                                            or d.get("cmd") == "fetch_asset")]
    if runnable:
        out.append("do " + "·".join(str(d.get("cmd") or d.get("run") or "?")
                                    for d in runnable[:3]))
    for k in ("jobs", "write_files", "measure", "verify"):
        v = res.get(k)
        if isinstance(v, (list, tuple)) and v:
            out.append(f"{k} {len(v)}개")
        elif isinstance(v, dict) and v:
            out.append(f"{k} {len(v)}칸")
    return out


def _then_lines(res):
    """`then_call_with` 를 사람이 읽을 줄들로 (2026-09-04).

    ★모양이 **둘**이다 — 영상 체인은 글자 목록(`["preset 에 …", …]`)이고 조교 계측
      체인(`volcano_ref`)은 **묶음**(`{"step":…, "payload":{…}}`)이다. 예전 코드는
      `for t in then_call_with` 로 돌아서 묶음이 오면 **열쇠 이름만**(`step`·`payload`)
      찍었다 — 멈춰 세워 놓고 «무엇을 채우라» 는 정작 한 글자도 안 보였다.
      곁 도구는 `then_call_with` 가 **유일한 계약**이라 그 자리가 그대로 사고가 된다.
    ★모르는 모양은 있는 그대로 한 줄로 찍는다(삼키지 않는다).
    """
    t = res.get("then_call_with")
    if not t:
        return []
    if isinstance(t, dict):
        out = []
        for k in sorted(t, key=lambda x: (x != "step", x)):
            v = t[k]
            out.append(f"{k}: " + (v if isinstance(v, str)
                                   else json.dumps(v, ensure_ascii=False)))
        return out
    if isinstance(t, (list, tuple)):
        return [x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in t]
    return [str(t)]


def _feedback(c, payload):
    """보고(`feedback`)를 **그 단계를 가진 도구**로 보낸다 (2026-09-04).

    ★`feedback` 은 `volcano_video` 의 단계다 — 곁 도구(`volcano_ref`·`volcano_cardnews`)의
      STEPS 에는 그 이름이 **없다**. 그래서 조교가 `--tool volcano_ref` 로 돌리면
      완주·중단 보고가 서버에서 «알 수 없는 step: feedback» 으로 튕겨 **한 줄도 안 남는다**
      (§"로그 사각지대 — 실패는 세는데 성공을 못 셌다" 가 그대로 재발한다). 주소를 바로 쓴다.
    ★수강생 경로(도구가 `volcano_video`)에서는 **예전과 똑같이** 부른다 — `tool=` 을
      아예 안 넘긴다. `Client` 를 상속해 옛 `step(self, name, payload, source)` 시그니처를
      들고 있는 클라이언트도 그대로 돈다(새 키워드에 `TypeError` 로 죽지 않는다).
    """
    tool = getattr(c, "tool", None) or "volcano_video"
    if tool == "volcano_video":
        return c.step("feedback", payload=payload)
    return c.step("feedback", payload=payload, tool="volcano_video")


def _report_done(c, step, res, started):
    """**끝까지 갔다는 것을 서버에 한 줄 알린다.**

    ■ 왜 필요한가 (2026-08-22 실측)
        서버는 「지시를 줬다」까지만 안다. 실제 렌더는 그 뒤 이 기계에서 나고,
        **완성본이 나왔는지 0명분도 모른다** — 3일 실측으로 `render_mix` 성공
        2,475회·175명 · `stitch_master` 11,017회·129명인데 완주 기록은 **0건**이다.
        실패는 `_report_failure` 가 알리는데 **성공은 알리는 쪽이 없었다.**
        그래서 「막힌 사람」은 세어도 「해낸 사람」은 못 세고, 그러면
        **반려를 고친 것이 실제로 도움이 됐는지**를 값으로 말할 수 없다.

    ■ ★비밀도 개인 정보도 싣지 않는다
        보내는 것은 **마지막 단계 이름 · 걸린 시간(초) · 만든 파일이 있는지**뿐이다.
        경로·문구·프롬프트는 안 보낸다(경로에는 사람 이름이 들어간다).

    ★**끝을 막지 않는다.** 알리다 실패해도 조용히 넘어간다 — 다 만들어 놓고
      알림 때문에 죽으면 그게 더 나쁘다(`_report_failure` 와 같은 판단).
    ★`kind="done"` — 서버가 `bug`·`rejected` 와 **가려서** 셀 수 있어야 한다.
      한 통에 담으면 §"집계표의 이름을 믿는다" 사고가 그대로 재발한다.
    """
    try:
        secs = None
        try:
            secs = round(time.time() - float(started), 1)
        except Exception:                                          # noqa: BLE001
            secs = None
        # ★「무엇이 나왔나」는 **서버가 선언한 산출물**로만 본다. 우리가 경로를
        #   짐작해 뒤지지 않는다(짐작하면 채널마다 갈린다).
        res = res or {}
        paths = list(res.get("output_files") or []) if isinstance(res.get("output_files"), list) else []
        for k in ("out", "out_path", "master", "mp4"):
            v = (res or {}).get(k)
            if isinstance(v, str) and v:
                paths.append(v)
        # 카드뉴스의 files는 PNG 경로 목록이다. 디렉터리와 파일이 섞인 dict는
        # 추측하지 않고 전용 output_files 선언을 기다린다.
        if isinstance(res.get("files"), list):
            paths.extend(v for v in res["files"] if isinstance(v, str))
        paths = sorted({os.path.normcase(os.path.abspath(v)) for v in paths
                        if isinstance(v, str) and v})
        outs = []
        for path in paths:
            try:
                outs.append(os.path.isfile(path) and os.path.getsize(path) > 0)
            except OSError:
                outs.append(False)
        made = (sum(1 for x in outs if x), len(outs))
        nxt = res.get("next_step")
        terminal = (not nxt or (isinstance(nxt, str) and nxt.startswith("(")))
        completion = {"version": 1, "terminal": bool(terminal), "execution_ok": True,
                      "artifacts_expected": made[1], "artifacts_verified": made[0]}
        txt = f"[실행 종료] 마지막 단계 {step}"
        if secs is not None:
            txt += f" · 이번 실행 {secs}초 (재개 전 작업 제외)"
        if made[1]:
            txt += f" · 산출물 {made[0]}/{made[1]}개 확인"
        _feedback(c, {"kind": "done", "step": step, "text": txt,
                      "completion": completion})
        _progress("  [알림] 실행 종료와 파일 확인 개수를 서버에 남겼다")
    except Exception:                                              # noqa: BLE001
        # ★조용히 넘어간다 — 다 만들고 나서 알림 때문에 죽으면 안 된다.
        pass


def _diagnostic_head_tail(text, limit, head_chars):
    """긴 진단의 시작과 실제 원인이 있는 끝을 정해진 글자 수 안에 보존한다."""
    text = str(text)
    if len(text) <= limit:
        return text
    marker = "\n... [중간 진단 생략] ...\n"
    if limit <= len(marker):
        return text[-limit:] if limit > 0 else ""
    head_chars = max(0, min(int(head_chars), limit - len(marker)))
    tail_chars = limit - len(marker) - head_chars
    return text[:head_chars] + marker + (text[-tail_chars:] if tail_chars else "")


def _report_failure(c, step, err):
    """여기서 죽었다는 것을 **서버에 한 줄 알린다.**

    ■ 왜 필요했나 (2026-08-13)
        파이프라인의 돈과 시간은 거의 다 **이 기계**에서 나가는데, 여기서 죽으면
        서버 쪽에는 흔적이 0이었다. 서버가 아는 것은 "지시를 줬다" 까지고,
        수강생이 말해 주지 않는 한 무엇이 몇 명에게서 깨지는지 영원히 모른다.
        실제로 `render_mix` 를 성공한 33명 중 **몇 명이 mp4 를 얻었는지 0명분도**
        알 수 없었다. `feedback` 단계는 받을 준비가 돼 있었고 보내는 쪽만 없었다.

    ★**원래 오류를 삼키지 않는다.** 알리는 데 실패해도 부르는 쪽이 그대로 던진다 —
      알림이 사람에게 보일 오류를 가리면 그게 더 나쁘다.
    ★비밀은 싣지 않는다. 열쇠는 헤더로만 다니고 메시지에 들어오지 않지만,
      길이를 잘라 보내는 양 자체를 묶는다.
    """
    if getattr(err, 'replayed', False):
        # ★앞 실행에서 이미 받아 알린 응답을 다시 보여 주는 것이다(W2-04) — 다시 알리면 서버에는 한 번 반려가
        #   재실행마다 한 줄씩 쌓인다(10-04 강석주 render_mix: 반려 1건 뒤 43초에 feedback 20건). 처음 받았을 때 알렸다.
        _progress("  [알림] 앞 실행에서 이미 알린 응답이라 다시 남기지 않았다")
        return
    try:
        # StepError 자체에 subprocess stderr/원격 traceback 이 들어올 수 있다. 앞만
        # 자르면 실제 최종 errno 가 사라지므로 호출 문맥과 오류 꼬리를 함께 남긴다.
        txt = _diagnostic_head_tail(" ".join(str(err).split()), 400, 200)
        # ★★**트레이스백을 같이 보낸다** (2026-08-15 지시).
        #   예전에는 `str(err)` 한 줄만 보냈다. 실제로 서버에 쌓인 것이 이랬다:
        #       text 31자 | [실행기 중단] 단계가 2번을 넘었다 — 순환일 수 있다
        #   **어느 줄에서 죽었는지가 없다.** 그래서 같은 오류가 며칠씩 반복돼도
        #   원인을 좁힐 수가 없었다 — 그게 "sentry 급이 아니다" 의 실체다.
        #   서버는 최대 2,000자를 받는다(`write_feedback`). 그 안에서 최대한 싣는다.
        tb = ""
        try:
            tb = getattr(err, "child_traceback", None) or traceback.format_exc()
        except Exception:  # noqa: BLE001
            tb = ""
        # ★★**서버 반려와 실행기 오류를 가른다** (2026-08-16).
        #   예전에는 전부 `kind="bug"` 였다. 그래서 **서버가 답을 하고 반려한 것**이
        #   '오작동' 으로 쌓였고(전수 1,518건 중 58.5%), 일일 리포트가 그것을
        #   "크래시" 로, 아침 알림이 *"서버가 답을 못 준 것"* 으로 보고했다.
        #   실제로 그날 서버 예외는 0건이었다.
        #   ★가르는 것은 문자열이 아니라 **타입**이다 — 반려문에 무슨 말이 들어올지
        #     우리가 정하지 못한다. 어디서 났는지는 타입만이 안다.
        rejected = isinstance(err, RejectedError)
        head = "[서버 반려로 멈춤]" if rejected else "[실행기 중단]"
        # 긴 예외 문자열에서는 traceback 마지막 줄의 클래스 이름도 중간에 밀릴 수
        # 있다. 실행기 오류만 타입을 앞에 고정해 원인의 종류까지 항상 남긴다.
        error_type = "" if rejected else (getattr(err, "child_error_type", None) or type(err).__name__) + ": "
        # 작업 폴더가 사라진 정지는 실행기 결함이 아니다 — 신고를 읽는 쪽이 원인을 바로 가르게 앞에 적는다(#224).
        gone = None if rejected else _vanished_workdir(getattr(c, "_last_workdir", None))
        body = f"{head} {error_type}" + (f"[작업 폴더 안 보임: {gone}] " if gone else "") + txt
        # 반려에는 트레이스백을 싣지 않는다 — 우리 코드가 죽은 것이 아니라서
        # 아무것도 안 가리키고, 2,000자 한도만 먹는다.
        if not rejected and tb and tb.strip() and "NoneType: None" not in tb:
            label = "\n--- 트레이스백 ---\n"
            remaining = 1900 - len(body) - len(label)
            body += label + _diagnostic_head_tail(tb.strip(), remaining,
                                                   min(450, remaining // 3))
        _feedback(c, {"kind": "rejected" if rejected else "bug",
                      "step": step, "text": body})
        _progress("  [알림] " + ("서버가 반려한 자리를 남겼다"
                            if rejected else "어디서 멈췄는지 서버에 남겼다 (트레이스백 포함)"))
    except Exception as failure:  # noqa: BLE001
        relocated = getattr(sys.modules.get("volcano_run"), "RunnerRelocated", None)
        if isinstance(relocated, type) and isinstance(failure, relocated):
            # ★보고는 서버에 닿았고, 그 응답이 실은 새 실행기를 이 작업 폴더의 runner/ 에 설치했다 — 이 프로세스는 다른
            #   폴더(작업 폴더 밖 공용 runner 등)의 코드라 새 코드로 이어 가지 못한다(`volcano_run.self_update`). 그 사실과
            #   «다시 띄울 명령» 을 보여 준다. 삼키면 «서버에 남기지 못했다» 라는 틀린 말만 남고 사람은 다음에도 같은 공용
            #   폴더로 띄운다(2026-10-06 · Z 검토 3회차 minor 수리 중 실측 — 실패 보고 응답 갱신은 이 자리에서만 닿는다).
            #   원래 오류는 그대로 부르는 쪽이 올린다. 옛 volcano_run(이 이름이 없는 판)과 짝이어도 죽지 않게 이름으로 찾는다.
            _progress("  [알림] 어디서 멈췄는지 서버에 남겼다")
            _progress("  ★ " + str(failure), flush=True)
            return
        # ★알림이 죽어도 조용히 넘어간다. 여기서 던지면 **진짜 오류가 가려진다.**
        _progress("  [알림] 서버에 남기지 못했다 (원래 오류를 그대로 올린다)")


RUNNER_KEY_FILE = ".volcano_runner_key.json"


def _owner_only(path):
    """`path` 를 본인만 읽고 쓰게 좁힌다 → (됐나, 못 했으면 이유).

    POSIX 는 0600. ★윈도우(NTFS)는 권한 비트가 아니라 ACL 이 정한다 — `os.chmod(…, 0o600)` 은 읽기 전용 깃발만 건드려 아무것도
    좁히지 않는다. 작업 폴더가 사용자 폴더 밖(E:\\ 등)이면 상위 폴더에서 상속된 다른 계정 권한이 출입증에 그대로 남는다(2026-10-22
    win-main · test_boundary «0600 으로 저장한다» 가 윈도우에서만 실패). 상속을 끊고 지금 사용자에게만 전체 권한을 준다(icacls ·
    윈도우 기본 도구)."""
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
            return True, ""
        except OSError as e:
            return False, str(e)
    # 사람 이름(USERDOMAIN\\USERNAME)이 아니라 보안 식별자(SID)로 준다 — ssh 접속 등에서 USERDOMAIN 이 «WORKGROUP» 이면
    #   icacls 가 «계정 이름과 보안 식별자 간의 매핑이 이루어지지 않았습니다» 로 실패했다(2026-10-22 win-main 실측).
    # ★whoami·icacls 는 윈도우 시스템 폴더(System32)의 것을 정확한 경로로 부른다 — 이름으로 부르면 PATH 앞자리의 Git for Windows
    #   `usr\bin\whoami.exe`(유닉스판 · «extra operand '/user'» rc 1 · 출력 없음)가 잡혀 SID 를 못 얻었다(2026-10-23 win-main 실측:
    #   shutil.which("whoami") = E:\tools\git\usr\bin\whoami.EXE · test_boundary «본인 전용 ACL» 이 윈도우에서만 실패). 규칙은 실행기 한 자리
    #   agy_transport_proc.windows_system_tool(tools/lib/platform.mjs windowsSystemTool 과 같은 규칙).
    import re
    import agy_transport_proc as _proc                            # noqa: PLC0415
    try:
        w = _spawn([_proc.windows_system_tool("whoami"), "/user", "/fo", "csv", "/nh"], capture_output=True, timeout=30)
        sid = re.search(r"S-1-[0-9-]+", w.stdout.decode("ascii", "ignore"))
        if not sid:
            return False, "whoami 가 SID 를 주지 않았다"
        r = _spawn([_proc.windows_system_tool("icacls"), str(path), "/inheritance:r", "/grant:r", f"*{sid.group(0)}:F"],
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError, StepError) as e:   # 도구 문(_spawn)이 못 찾으면 StepError
        return False, str(e)
    return r.returncode == 0, (r.stderr or r.stdout or b"").decode("oem", "replace").strip()[:120]


def save_runner_key(rk, workdir):
    """서버가 준 실행기용 출입증을 작업 폴더에 남긴다(본인만 읽게 0600). 값은 찍지 않는다."""
    path = os.path.join(str(workdir), RUNNER_KEY_FILE)
    temp = None
    try:
        # ★바이트로 쓴다 — 텍스트 모드는 플랫폼이 줄바꿈에 끼어든다(구동기 규율)
        # ★임시 파일 → 원자 교체 (2026-10-05 · 원장 W2-07). 돌고 있는 실행기·재개 래퍼·다른 단계가 같은 파일을
        #   읽는 사이에 제자리 덮어쓰기를 하면 반쪽 JSON 을 읽어 «출입증을 못 읽었다» 로 멈춘다. 권한(0600)도
        #   교체 **전에** 임시 파일에 건다 — 교체된 순간부터 남이 못 읽는다.
        fd, temp = tempfile.mkstemp(prefix=".volcano-key-", dir=str(workdir))
        with os.fdopen(fd, "wb") as fh:
            fh.write(json.dumps({"token": rk["token"], "url": rk.get("url") or "",
                                 "expires": rk.get("expires") or "", "preset": rk.get("preset") or ""},
                                ensure_ascii=False).encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        _ok, _why = _owner_only(temp)          # 교체 전에 임시 파일에(교체는 보안 설명자를 그대로 옮긴다)
        if not _ok:
            _progress(f"  [출입증] 본인 전용 권한을 못 걸었다({_why}) — 파일은 저장한다", flush=True)
        _replace_retry(temp, path)
        temp = None
        _progress(f"  [출입증] 실행기용 출입증을 저장했다 → {path} (만료 {rk.get('expires')}) — "
              f"이제 `python runner/volcano_drive.py --workdir {workdir}` 한 줄로 끝까지 돈다", flush=True)
    except OSError as e:
        _progress(f"  [출입증] 저장 실패({e}) — 도구를 단계마다 직접 부르는 길로 간다", flush=True)
    finally:
        if temp is not None and os.path.exists(temp):
            os.unlink(temp)
    return path


def load_runner_key(workdir, path=None):
    """작업 폴더의 출입증 — 없거나 만료면 (None, 이유).

    ★`path` 로 **다른 파일**을 줄 수 있다 (2026-09-04). 조교 계측 도구(`volcano_ref`)에는
      출입증을 발급하는 단계가 없다 — `assets` 는 영상 체인의 단계다. 그래서 조교는
      자기 토큰으로 같은 모양의 파일(`{"token":…, "url":…}`)을 손으로 만들어 가리킨다.
      ★**토큰 자체를 argv 로 받지 않는다** — `ps` 는 남의 명령줄까지 보여준다(§4).
    """
    path = str(path or os.path.join(str(workdir), RUNNER_KEY_FILE))
    if not os.path.exists(path):
        return None, f"{path} 가 없다 — 먼저 클로드 코드로 step='assets' 를 한 번 부르면 서버가 준다"
    try:
        with open(path, encoding="utf-8") as fh:
            rk = json.load(fh)
    except (OSError, ValueError) as e:
        return None, f"{path} 를 못 읽었다: {e}"
    exp = str(rk.get("expires") or "")
    if exp and exp < time.strftime("%Y-%m-%d"):
        return None, f"출입증이 {exp} 에 만료됐다 — 클로드 코드로 step='assets' 를 다시 부르면 새로 나온다"
    if not (rk.get("token") and rk.get("url")):
        return None, f"{path} 에 token/url 이 없다"
    return rk, None


DRIVE_STATE_FILE = '.volcano_drive_state.json'


def _relay_side_payload(c, res, payload, step):
    """Use the server side-tool contract; keep the local checkpoint directory."""
    if getattr(c, "tool", None) and c.tool != "volcano_video":
        # then_call_with 는 모양이 둘이다(_then_lines) — 묶음({"step","payload"})만 칸 계약이고, 글자 목록(안내 줄)은 칸 계약이 없다
        #   (2026-10-23 인물형 start 3건 «'list' object has no attribute 'get'» — 안내 줄 목록을 묶음으로 읽었다).
        _then = res.get("then_call_with")
        _tp = _then.get("payload") if isinstance(_then, dict) else None
        if isinstance(_tp, dict):
            #   ★★**교체한다 — 누적하지 않는다** (2026-09-04 완주 7차가 잡았다).
            #     이 루프는 payload 를 누적하는데(위 `payload.update`), 곁 도구는
            #     `then_call_with` 가 **유일한 계약**이라 누적이 두 가지를 한꺼번에 망친다:
            #     ①**계약 결손이 안 보인다** — 서버가 안 실은 칸도 옛 값으로 우연히 채워져
            #       「돌더라」가 나온다. 실제 조교(모델 클라)는 계약대로만 보내므로 죽는다.
            #       이 파일 머리말이 그 위험을 이미 적어 뒀는데 곁 도구 갈래에는 안 적용돼 있었다.
            #     ②**크기가 폭발한다** — 손이 잰 raw 가 64축 내내 쌓여 완주 7차에서 인계가
            #       113KB → **9,718,048바이트**가 됐다(서버가 «ids 를 나눠 도세요» 로 반려).
            #       서버 `_relay` 는 `_floor` 로 자기가 바닥을 깔아 주므로 누적할 이유가 없다.
            #   ★버린 칸은 **말한다** — 조용히 버리면 계약 결손인지 정상인지 아무도 모른다.
            _new = {}
            for _k, _v in _tp.items():
                if isinstance(_v, str) and _v.startswith("<") and _v.endswith(">"):
                    if _k in payload:
                        _new[_k] = payload[_k]   # 방금 잰 값(measure 가 넣었다)
                    continue          # 실행기가 채우는 칸 — measure 가 넣는다
                #   ★★**덮는다**(2026-09-04 완주에서 잡았다). 처음엔 `setdefault` 로 썼는데
                #     그러면 **앞 단계의 덜 찬 값이 뒤의 완성된 값을 막는다** — `geom` 이 두
                #     국면으로 돌며 첫 국면의 `geom_cuts`(cuts_per_min 없음)가 눌러앉아
                #     `tikitaka` 가 «cuts_per_min 이 없는 편이 2개» 로 멎었다.
                #   ★서버가 «다음엔 이걸로 부르라» 고 적은 것이 **계약**이므로 그것이 이긴다.
                #     방금 잰 값은 위 `payload.update(execute(...))` 로 **먼저** 들어가고,
                #     서버는 그 자리를 자리표시자로 두므로(바로 위 `continue`) 안 덮인다.
                _new[_k] = _v
            #   ★같은 (단계, 칸) 조합은 **한 번만** 찍는다 — axes 는 64왕복을 도는데
            #     매번 같은 줄을 찍으면 **새 결손이 묻힌다**(실측: `geom_cuts_raw` 한 줄이
            #     210번 찍혀서 그것이 진짜 순환 원인인 줄 내가 못 알아봤다, 2026-09-04).
            #     §"자가 시끄러우면 아무도 안 본다" 와 같은 부류다.
            if "workdir" not in _new and payload.get("workdir"):
                _new["workdir"] = payload["workdir"]
            _drop = sorted(set(payload) - set(_new))
            _seen = globals().setdefault("_SIDE_DROP_SEEN", set())
            _fresh = [k for k in _drop if (step, k) not in _seen]
            _seen.update((step, k) for k in _drop)
            if _fresh:
                _progress("  [계약] then_call_with 에 없어 안 나른 칸: " + ", ".join(_fresh[:12])
                      + (f" 외 {len(_fresh) - 12}개" if len(_fresh) > 12 else ""))
            payload = _new
    return payload


def _input_destination(res, current):
    author = res.get('author') or {}
    then = res.get('then_call_with') or {}
    for value in (res.get('next_step'), author.get('for'), then.get('step') if isinstance(then, dict) else None):
        if isinstance(value, str) and value.strip() and not value.startswith('('):
            return value
    return current


def _input_wait(c, step, res, payload, source, executed=False):
    if not executed:
        payload = _relay_side_payload(c, res, _carry_into(res, payload), step)
    target = _input_destination(res, step)
    # Public authoring guidance is not payload: relay only the declared fields
    # to the server, but preserve the response for the Claude Code author.
    # Otherwise caption budgets, tone and rules vanish at the CLI boundary.
    wd = payload.get('workdir')
    if isinstance(wd, str) and os.path.isabs(wd) and os.path.isdir(wd):
        brief = os.path.join(wd, 'input_brief.json')
        _photo_write_state(brief, {'version': 1, 'step': target, 'response': res['author_view'] if isinstance(res.get('author_view'), dict) else res})
        _progress(f"  [작성 안내] {brief} — 응답의 예산·말투·규칙을 읽고 작성하세요. "
                  "안내 조회를 위해 이전 MCP 단계를 다시 호출할 필요가 없습니다.", flush=True)
    if step == 'start' and target != 'start':
        source = None
    return {'step': target, 'res': res, 'payload': payload, 'source': source}


def _drive_script_path(wd):
    """재개 명령이 가리킬 구동기 — **이 작업 폴더의 runner/volcano_drive.py** (2026-10-05 · 원장 W2-13).

    예전에는 `os.path.abspath(__file__)` 였다. runner/ 가 공용 폴더로 이어진 링크면 파이썬이 스크립트 폴더의 링크를
    풀어 모듈을 읽으므로 `__file__` 이 **공용 원본 경로**가 되고, 재개 명령이 이 작업 폴더가 아닌 공용 실행기를
    띄웠다(맥 실측 — FP1 보고). 작업 폴더에 실행기가 없을 때만(다른 폴더의 실행기로 돌린 경우) 지금 파일을 쓴다."""
    local = os.path.join(str(wd), 'runner', 'volcano_drive.py')
    return local if os.path.isfile(local) else os.path.abspath(__file__)


def _quote_command(argv):
    if os.name == 'nt':
        return "PowerShell: & " + " ".join("'" + value.replace("'", "''") + "'" for value in argv)
    import shlex
    return shlex.join(argv)


def _resume_command(wd, st, payload_path, tool, key_file=None, max_steps=40):
    argv = [sys.executable, _drive_script_path(wd), '--workdir', wd,
            '--step', st['step'], '--payload', payload_path, '--tool', tool,
            '--max-steps', str(max_steps)]
    if key_file:
        argv += ['--key-file', os.path.abspath(key_file)]
    if st.get('source') is not None:
        source_path = os.path.join(wd, 'next_source.json')
        _photo_write_state(source_path, st['source'])
        argv += ['--source', source_path]
    return _quote_command(argv)


def _plain_resume_command(wd, tool, key_file=None, max_steps=40):
    """저장 상태에서 그대로 잇는 명령(`--step`·`--payload` 없음) — 실행기가 예외로 멈출 때 보여 준다(W2-12 ④)."""
    argv = [sys.executable, _drive_script_path(wd), '--workdir', wd]
    if tool != Client.tool:
        argv += ['--tool', tool]
    argv += ['--max-steps', str(max_steps)]
    if key_file:
        argv += ['--key-file', os.path.abspath(key_file)]
    return _quote_command(argv)


def _checkpoint(c, step, payload, source, status='active', *, publish_payload=False, response_consumed=False,
                rejected=False):
    """Save completed measurements before another operation can reject or fail.

    Migration wrappers already own an atomic state file; keep using their hook.
    Native callers get the same tool/args envelope in their existing workdir.
    Credentials on Client are never serialized. A failed write stops further work.

    `rejected=True` — 서버가 **이 payload 를 반려**한 자리(반려 계약을 나른 뒤)에서만 준다. 그 판에만
    `payload_rejected` 표식을 단다 — `--step` 재개가 그 판을 통째로 되살리면 «서버가 빼라고 한 칸» 이 다시 나가기
    때문이다(§_resume_with_saved_state · 2026-10-05 검토 2회차).
    ★표식은 **반려한 판에만** 단다 — 평소 판(보내기 직전 등)의 봉투는 `{version,status,tool,args}` 그대로다. 서버가
      학생 PC 로 보내는 새 프로젝트 확인 스크립트(`ta_local_bootstrap.LOCAL_SCRIPT` · `preflight_adoption`)가 assets
      단계 봉투를 **정확히 이 네 칸**으로 대조하고, 이미 배포된 판들이 학생 PC 에서 그렇게 돈다. 평소 판에 칸을 하나
      더하면 조교 프리셋 새 작업 폴더가 전부 «옛 폴더(legacy)» 로 판정된다(검토 3회차 · test_bootstrap_v2 가 잡았다).
    """
    from volcano_run import _review_receipt_io_path
    if response_consumed:
        import response_receipts
        c._runner_response_handoff = response_receipts.handoff(c, step, payload, source)
    callback = getattr(c, '_runner_checkpoint', None)
    if callable(callback):
        callback(step, payload, source)
        return
    wd = payload.get('workdir')
    if not isinstance(wd, str) or not os.path.isabs(wd) or not os.path.isdir(_review_receipt_io_path(wd)):
        return
    args = {'preset': getattr(c, 'preset', None), 'step': step,
            'payload': fold_payload(payload)}
    if source is not None:
        args['source'] = source
    path = _review_receipt_io_path(os.path.join(wd, DRIVE_STATE_FILE))
    if status == 'waiting' or publish_payload:
        # Both implicit resume and explicit --step must see the server's latest
        # repair contract. Publish the projection before the selecting state.
        _photo_write_state(_review_receipt_io_path(os.path.join(wd, 'next_payload.json')), args['payload'])
    state = {'version': 1, 'status': status,
             'tool': getattr(c, 'tool', None) or 'volcano_video', 'args': args}
    if rejected:
        state['payload_rejected'] = True
    marker = getattr(c, '_runner_response_handoff', None)
    if marker is not None:
        state['response_handoff'] = marker
    _keep_previous_state(path, state)
    _photo_write_state(path, state)


def _keep_previous_state(path, state):
    """새 체크포인트가 앞 판의 칸을 잃으면 앞 판을 `<상태 파일>.prev` 로 남긴다 (W2-12 ②).

    예전에는 `--step` + 몇 칸짜리 payload 로 이으면 그 몇 칸이 저장 상태를 통째로 덮어 source·image_slots 같은
    체인 상태가 되살릴 길 없이 사라졌다. 칸을 지어 합치지는 않는다(다른 자리의 측정을 되살리면 옛 값이 이긴다) —
    잃기 전 판을 보존해 복구할 근거를 남긴다. 같은 칸이거나 늘기만 하면 아무것도 하지 않는다."""
    try:
        with open(path, encoding='utf-8') as fh:
            old = json.load(fh)
        old_keys = set((old.get('args') or {}).get('payload') or {})
    except (OSError, ValueError, AttributeError, TypeError):
        return
    lost = old_keys - set(state['args']['payload'])
    # ★`assets` 판은 보존하지 않는다(2026-10-05 B 최종 검토 minor). 영상 체인의 첫 단계라 그 payload 는 시작 입력뿐이고
    #   측정·진행이 없다. 그리고 assets 까지만 돈 폴더는 서버의 새 프로젝트 확인 스크립트(ta_local_bootstrap.LOCAL_SCRIPT ·
    #   preflight_adoption.preflight_only)가 **정확한 파일 세 개**로 «새 폴더» 를 판정한다 — `.prev` 하나가 생기면
    #   조교 프리셋 새 작업 폴더가 «옛 폴더(legacy)» 로 판정된다(tests/test_drive_prev_preflight).
    if lost and old.get('tool') == state.get('tool') and (old.get('args') or {}).get('step') != 'assets':
        # 정상 흐름(서버의 payload_discard)에서도 칸이 빠지므로 출력은 하지 않는다 — 보존본만 남긴다.
        _photo_write_state(path + '.prev', old)


def _resume_state(wd, tool, preset, suffix=''):
    """저장 상태를 읽는다 — `suffix='.prev'` 면 칸을 잃기 전 보존본(`_keep_previous_state`)을 같은 검증으로 읽는다."""
    from volcano_run import _review_receipt_io_path
    path = _review_receipt_io_path(os.path.join(wd, DRIVE_STATE_FILE)) + suffix
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            state = json.load(fh)
        args = state['args']
        pl = args['payload']
        if (state.get('version') != 1 or state.get('status') not in ('active', 'waiting', 'done')
                or state.get('tool') != tool or args.get('preset') != preset
                or not isinstance(pl, dict) or not isinstance(args.get('step'), str)
                or not args['step'] or not isinstance(pl.get('workdir'), str)
                or os.path.normcase(os.path.realpath(pl['workdir'])) != os.path.normcase(os.path.realpath(wd))):
            raise ValueError('state identity or shape differs')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise StepError('저장한 재개 상태를 확인할 수 없습니다: ' + path
                        + ' — 처음부터 자동 실행하지 않습니다. 상태를 복구하거나 '
                        '--step과 --payload로 확인한 입력을 명시하세요.') from exc
    return state


def _save_review_handoff(wd, st, payload_path):
    """Expose response-only model work without copying credentials or whole args."""
    artifacts = []
    # 실행기 검수 정지는 정본 칸을 따른다(§_review_reply_field · W2-14) — 그 밖(서버가 준 focus 요청)은 예전 이름.
    active = (st.get('res') or {}).get('review_reply_field')
    review_field = active if active in _REVIEW_REPLY_FIELDS else 'review_replies'
    for field, reply_field in (('review_requests', review_field),
                               ('focus_review_requests', 'focus_review_replies')):
        requests = (st.get('res') or {}).get(field)
        if not requests:
            continue
        if not isinstance(requests,list) or any(not isinstance(request,dict) for request in requests):
            raise StepError('검수 요청 목록의 형식이 잘못되어 클라이언트 인계를 저장하지 못했습니다.')
        path = os.path.join(wd,field + '.json')
        _photo_write_state(path,{'version':1,'step':st['step'],field:requests,
            'payload_file':payload_path,'reply_field':reply_field})
        artifacts.append((path, reply_field))
    return artifacts


def _detach_options(platform=None):
    # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP; CREATE_NO_WINDOW alone still
    # belongs to the caller's console. POSIX gets its own session/process group.
    return ({'creationflags': 0x00000008 | 0x00000200}
            if (platform or os.name) == 'nt' else {'start_new_session': True})


class _LoggedRestart(BaseException):
    def __init__(self, argv, flags=(), module_dir=None):
        self.argv = argv
        self.flags = list(flags)    # 다시 띄울 파이썬의 실행 옵션(FP2 재시작 · -X utf8 등)
        # 다시 띄운 진행 기록 프로세스가 `import volcano_drive`·`volcano_run` 을 읽을 폴더. None 이면 지금 모듈의 폴더
        # (환경 준비가 다른 파이썬을 고른 재시작 — 같은 실행기 코드를 다른 파이썬으로 띄운다).
        self.module_dir = module_dir


def _restart_logged_python(python, script, arguments, *, flags=(), module_dir=None):
    """진행 기록 모드(`--background`)의 재시작 — 잠금을 놓고 새 프로세스를 띄운다.

    `module_dir` 은 새 프로세스가 실행기 모듈을 읽을 폴더다. 같은 실행기를 다른 파이썬으로 다시 띄울 때(환경 준비)는
    비워 둔다(지금 모듈의 폴더). FP2 처럼 **다른 폴더에 설치한 새 실행기**로 갈아탈 때는 반드시 그 폴더를 준다 —
    안 주면 새 프로세스가 옛 폴더의 `volcano_run` 을 먼저 읽어 옛 판을 알리고, 서버가 같은 갱신을 또 요구해 «명세·팩
    어긋남» 으로 멈춘다(2026-10-05 B 최종 검토 3회차: 연결된 runner/·작업 폴더 밖 실행기에서 실측)."""
    argv = [python, '-u', script] + list(arguments)
    if globals().get('_LOGGED_STATE'):
        # Release this worker's lock before the replacement acquires its own.
        # No pipeline work can run in the replacement before it owns the lock.
        raise _LoggedRestart(argv, flags, module_dir)
    # 직접 실행의 작업 폴더 잠금을 놓고 바꾼다 — 윈도우 execv 는 새 프로세스를 먼저 띄우고 이 프로세스를 끝내 잠금이 겹친다.
    _release_direct_run_lock()
    os.execv(python, [python, *flags] + argv[1:])


def _logged_bootstrap(argv, status_path, log_path, wd, module_dir):
    return ('import sys;sys.path.insert(0,' + repr(module_dir) + ');'
            'import volcano_drive as D;D._logged_child(' +
            ','.join(repr(x) for x in (argv, status_path, log_path, wd)) + ')')


def _logged_child(argv, status_path, log_path, wd):
    """The actual Python worker holds the lock, including all pipeline work."""
    import runpy
    from volcano_run import _asr_lock
    state = {'version': 1, 'pid': os.getpid(), 'status_path': status_path,
             'log_path': log_path, 'started_at': time.time(), 'status': 'running'}
    try:
        with _asr_lock(os.path.join(wd, '.volcano-drive.lock')):
            # Publish before starting work: a failed state write cannot orphan a
            # separately spawned pipeline. There is no supervisor/worker split.
            _photo_write_state(status_path, state)
            _claim_drive_owner(wd, dict(state, mode='background'))
            globals()['_LOGGED_STATE'] = state
            arguments = list(argv[1:])
            if arguments and arguments[0] == '-u':
                arguments.pop(0)
            original_argv = sys.argv
            try:
                if arguments and arguments[0] == '-c' and len(arguments) >= 2:
                    sys.argv = ['-c'] + arguments[2:]
                    exec(compile(arguments[1], '<string>', 'exec'), {'__name__': '__main__'})
                elif arguments and os.path.isabs(arguments[0]):
                    sys.argv = arguments
                    runpy.run_path(arguments[0], run_name='__main__')
                else:
                    raise ValueError('logged worker requires a Python script or -c')
                code = 0
            except SystemExit as stopped:
                code = stopped.code if isinstance(stopped.code, int) else (0 if stopped.code is None else 1)
                if stopped.code is not None and not isinstance(stopped.code, int):
                    print(stopped.code, file=sys.stderr, flush=True)
            except _LoggedRestart:
                raise
            except BaseException:
                traceback.print_exc()
                code = 1
            finally:
                sys.argv = original_argv
                globals().pop('_LOGGED_STATE', None)
            state.update(status='exited', returncode=code, ended_at=time.time())
            _photo_write_state(status_path, state)
    except _LoggedRestart as restart:
        # Environment preflight selected another Python. That process owns its
        # own lock while doing work; killing this waiting parent cannot release it.
        code = _logged_bootstrap(restart.argv, status_path, log_path, wd,
                                 os.path.abspath(getattr(restart, 'module_dir', None)
                                                 or os.path.dirname(os.path.abspath(__file__))))
        _spawn([restart.argv[0], *getattr(restart, 'flags', []), '-u', '-c', code],
                       stdin=subprocess.DEVNULL, close_fds=True, check=True)
    except BaseException:
        # Never serialize argv, Client, credential values or raw exception text.
        state.update(status='launch_error', ended_at=time.time())
        _photo_write_state(status_path, state)
        print('실행기를 시작하지 못했습니다. 같은 작업 폴더의 실행 여부와 파일 권한을 확인하세요.', flush=True)
        raise SystemExit(1)


def _resume_logged_entry(script, wd):
    """A handoff resume command uses the same detached logging/locking path."""
    if globals().get('_LOGGED_STATE'):
        return
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--key-file')
    options = ap.parse_args()
    key, why = load_runner_key(wd, options.key_file)
    if not key:
        print('작업 재개용 출입증을 읽지 못했습니다. ' + str(why), file=sys.stderr, flush=True)
        raise SystemExit(2)
    directory = tempfile.mkdtemp(prefix='run-', dir=os.path.dirname(script))
    print('진행 로그: ' + os.path.join(directory, 'progress.log'), file=sys.stderr, flush=True)
    state = _launch_logged([sys.executable, '-u', script] + sys.argv[1:], directory, wd, wait=True)
    if state.get('returncode'):
        raise SystemExit(state['returncode'])
    with open(os.path.join(os.path.dirname(script), 'result.json'), encoding='utf-8') as result:
        print(result.read(), flush=True)
    raise SystemExit(0)


def _launch_logged(argv, state_dir, wd, *, wait=False, runner_dir=None):
    """Persist both streams independently of the caller; optionally tail to stderr.

    A running receipt acknowledges startup, not completion. The OS lock prevents
    concurrent supervised launches. Abrupt OS termination may leave a stale
    running receipt; only an exited receipt proves completion.
    """
    state_dir, wd = os.path.abspath(state_dir), os.path.realpath(wd)
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    # Each launch has a fresh directory: an old success can never acknowledge it.
    log_path = os.path.join(state_dir, 'progress.log')
    status_path = os.path.join(state_dir, 'process.json')
    if os.path.exists(status_path):
        raise StepError('이미 실행 기록이 있는 폴더입니다: ' + status_path)
    module_dir = os.path.abspath(runner_dir or os.path.dirname(__file__))
    code = _logged_bootstrap(argv, status_path, log_path, wd, module_dir)
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as log:
        # 처음 파이썬 옵션(-X utf8 등)을 진행 기록 모드의 실제 실행기에도 싣는다(검토 2회차).
        process = _spawn([sys.executable, *_interpreter_flags(), '-u', '-c', code], popen=True,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            close_fds=True, **_detach_options())
    deadline = time.monotonic() + 10
    while not os.path.exists(status_path):
        if process.poll() is not None or time.monotonic() >= deadline:
            raise StepError('실행 시작을 확인하지 못했습니다. 다시 실행하기 전에 로그와 PID '
                            + str(process.pid) + '를 확인하세요: ' + log_path)
        time.sleep(.025)
    state = _read_state_retry(status_path)
    if state['status'] == 'launch_error':
        process.wait()
        raise StepError('같은 작업 폴더에서 이미 실행 중이거나 실행을 시작하지 못했습니다: ' + log_path)
    if wait:
        # Tail a regular file; losing this reader cannot close the child's logs.
        with open(log_path, encoding='utf-8', errors='replace') as log:
            while True:
                chunk = log.read()
                if chunk:
                    try:
                        sys.stderr.write(chunk); sys.stderr.flush()
                    except (OSError, ValueError):
                        pass
                if process.poll() is not None:
                    tail = log.read()
                    if tail:
                        try:
                            sys.stderr.write(tail); sys.stderr.flush()
                        except (OSError, ValueError):
                            pass
                    break
                time.sleep(.1)
        state = _read_state_retry(status_path)
        if state.get('status') != 'exited':
            raise StepError('실행 종료 결과가 없습니다. 완료로 처리하지 않습니다: ' + status_path)
    else:
        # Keep child handles alive and reap completed ones on a later launch.
        children = globals().setdefault('_BACKGROUND_PROCESSES', [])
        children[:] = [child for child in children if child.poll() is None]
        children.append(process)
    return state


SERVER_NEXT_PAYLOAD_FILE = 'next_payload.server.json'


def _edit_revision(value):
    """편집표의 판 지문 — 서버 `volcano_rinbox.edit_revision` 과 같은 글자로 잰다(patch 의 base_id 와 견준다)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _save_server_next_payload(wd, step, res):
    """사람(모델) 차례로 멈출 때 서버가 준 next_payload 원본을 따로 남긴다(W2-12 ③).

    ★되살리는 데 쓰지 않는다(2026-10-05 최종 검토 blocker) — 서버는 «빼라» 를 산문으로도 말해서, 모델이 시킨 대로
      지운 칸을 이 원본에서 되살리면 같은 정지·반려가 영원히 되풀이된다. 같은 단계로 이을 때 «원본에 있는데 이번에
    안 보내는 칸» 을 알리는 **기준**으로만 쓴다. 반려를 받으면 그 반려가 게시한 판으로 바꾼다(_drive_loop).
    원본이 없으면(서버가 안 실었다) 남기지 않는다 — 지어내지 않는다."""
    from volcano_run import _review_receipt_io_path
    pl = (res or {}).get('next_payload')
    if not (isinstance(wd, str) and os.path.isabs(wd) and os.path.isdir(wd)):
        return
    path = _review_receipt_io_path(os.path.join(wd, SERVER_NEXT_PAYLOAD_FILE))
    if not isinstance(pl, dict):
        if os.path.exists(path):
            os.unlink(path)      # 앞 정지의 원본이 이번 단계의 것으로 오해되지 않게
        return
    discard = [k for k in ((res or {}).get('payload_discard') or []) if isinstance(k, str)]
    _photo_write_state(path, {'version': 1, 'step': step, 'payload': fold_payload(pl), 'payload_discard': discard})


#: 수정 명령(`--step customize --payload <바꿀 항목 파일>`)이 싣는 칸 — 저장 상태가 이것뿐이면 제작 상태가 아니다.
_CUSTOMIZE_COMMAND_FIELDS = frozenset(('workdir', 'customization_patch', 'customization_help'))


def _customize_over_saved(wd, tool, preset, state, explicit_payload):
    """`--step customize --payload <바꿀 항목 파일>` — 저장된 **제작 상태** 위에 그 항목만 얹는다 (2026-10-19).

    customize 는 파이프라인 밖 단계다: 서버(무상태)가 받은 payload 를 «이미 만든 제작» 으로 보고 고친 항목의 단계부터
    다시 짓는다(`volcano_customization.revision`). 그런데 일반 재개 규칙은 저장된 단계와 다른 단계를 지정하면 합치지 않고,
    완료(done)·입력 대기 판도 되살리지 않는다 → 항목 한 칸만 나가 서버가 빈 제작을 고쳐 «대본(script)부터» 로 보내고
    script 가 «title·groups·region 이 필요합니다» 로 반려했다. 서버 안내(«저장된 작업 상태 위에 그 값만 덮습니다»)와
    실행기가 어긋난 자리다.
    · 기준 판: 입력 대기·반려 판이면 서버가 그 정지에서 준 next_payload(빼라고 한 칸은 이미 뺀 것), 없으면 저장된 payload.
      진행·완료 판은 저장된 payload 그대로(완료 판 = 마지막 단계에 보낸 제작 전체).
    · 명시 값이 이긴다(바꿀 항목 · workdir) · 명시 null 은 그 칸을 지운다(일반 재개와 같은 뜻).
    · 이 판 전의 실행기는 같은 명령에서 항목 한 칸짜리 payload 를 «customize 단계» 로 체크포인트해 제작 상태를 덮었다
      (`_keep_previous_state` 가 덮이기 전 판을 `.prev` 로 남겼다). 저장 상태가 customize 이고 수정 명령의 칸뿐이면
      제작 상태가 아니다 → 그 `.prev`(customize 가 아닌 판)를 기준으로 삼는다. 없으면 있는 그대로 보내고 서버가 말한다.
    돌려주는 것: ('customize', payload, 저장된 source, None) — 입력 대기 정체성은 잇지 않는다(새 요청이다)."""
    if state['args']['step'] == 'customize' and set(state['args']['payload']) <= _CUSTOMIZE_COMMAND_FIELDS:
        try:
            prev = _resume_state(wd, tool, preset, '.prev')
        except StepError:
            prev = None
        if prev and prev['args']['step'] != 'customize':
            _progress('  [수정] 저장 상태가 지난 수정 명령의 항목뿐이라(옛 실행기가 덮음) 덮이기 전 판(.prev · «'
                      + prev['args']['step'] + '» 단계)을 제작 상태로 씁니다.', flush=True)
            state = prev
    saved = unfold_payload(dict(state['args']['payload']))
    if state['status'] == 'waiting' or state.get('payload_rejected') is True:
        base = _load_server_next_payload(wd, state['args']['step']) or saved
    else:
        base = saved
    explicit = dict(explicit_payload)
    merged = dict(base)
    merged.update(explicit)
    for key in [k for k, v in explicit.items() if v is None]:
        merged.pop(key, None)
    merged['workdir'] = explicit.get('workdir') or merged.get('workdir') or wd
    _progress('  [수정] 저장된 작업(«' + state['args']['step'] + '» 단계 · ' + state['status'] + ') 위에 바꿀 항목('
              'customization_patch)만 얹어 customize 로 보냅니다 — 저장된 칸 ' + str(len(base)) + '개를 그대로 씁니다.',
              flush=True)
    return 'customize', merged, state['args'].get('source'), None


def _load_server_next_payload(wd, step):
    from volcano_run import _review_receipt_io_path
    path = _review_receipt_io_path(os.path.join(wd, SERVER_NEXT_PAYLOAD_FILE))
    try:
        with open(path, encoding='utf-8') as fh:
            saved = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(saved, dict) or saved.get('version') != 1 or saved.get('step') != step:
        return {}
    pl = saved.get('payload')
    if not isinstance(pl, dict):
        return {}
    pl = unfold_payload(dict(pl))
    # 서버가 그 정지에서 «빼라» 고 한 칸(payload_discard)은 원본에 있더라도 되살리지 않는다.
    for key in saved.get('payload_discard') or []:
        pl.pop(key, None)
    return pl


def _import_wrapper_state(wd, tool, preset):
    """10-04 재개 래퍼가 갈라 놓은 진도를 한 번 가져온다 (2026-10-05 · 원장 W2-11).

    10-04 의 옛 실행기 갱신은 «설치 도우미 + 재개 래퍼» 를 손으로 돌리게 했고, 래퍼는 자기 옆 state.json
    (`<작업 폴더>/.volcano-runner-resume-<nonce>/state.json`)에만 진도를 적었다(`_checkpoint` 가 콜백이 있으면 원래
    파일을 안 쓴다). 그 뒤 학생이 평소 명령으로 돌아오면 원래 상태 파일은 옛 단계 그대로라 이미 한 단계를 다시
    보냈다(재현 run_sim2 · 잠재 338건). 래퍼 상태가 원래 상태 파일보다 **새것**이면 그것을 원래 파일로 옮긴다
    (래퍼가 끝냈으면 «완료»로). 옮긴 뒤에는 원래 파일이 더 새것이라 다시 가져오지 않는다. 래퍼 파일은 그대로 둔다."""
    from volcano_run import _review_receipt_io_path
    target = _review_receipt_io_path(os.path.join(wd, DRIVE_STATE_FILE))
    try:
        floor = os.stat(target).st_mtime
    except OSError:
        floor = None
    best = None
    try:
        entries = list(os.scandir(_review_receipt_io_path(wd)))
    except OSError:
        return None
    for entry in entries:
        if not (entry.name.startswith('.volcano-runner-resume-') and entry.is_dir(follow_symlinks=False)):
            continue
        path = os.path.join(entry.path, 'state.json')
        try:
            mtime = os.stat(path).st_mtime
            if floor is not None and mtime <= floor:
                continue
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            args = data['args']
            pl = args['payload']
            if (data.get('tool') != tool or args.get('preset') != preset or not isinstance(pl, dict)
                    or not isinstance(args.get('step'), str) or not args['step']
                    or not isinstance(pl.get('workdir'), str)
                    or os.path.normcase(os.path.realpath(pl['workdir'])) != os.path.normcase(os.path.realpath(wd))):
                continue
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if best is None or mtime > best[0]:
            best = (mtime, entry.name, data)
    if best is None:
        return None
    _, name, data = best
    args = {'preset': data['args']['preset'], 'step': data['args']['step'], 'payload': data['args']['payload']}
    if data['args'].get('source') is not None:
        args['source'] = data['args']['source']
    state = {'version': 1, 'status': 'done' if data.get('_runner_completed') is True else 'active',
             'tool': tool, 'args': args}
    if data.get('response_handoff') is not None:
        state['response_handoff'] = data['response_handoff']
    _keep_previous_state(target, state)
    _photo_write_state(target, state)
    _progress('  [재개] 재개 래퍼(' + name + ')가 더 나중 진도를 적어 두었습니다 — «' + args['step'] + '» 단계'
              + (' (완료)' if state['status'] == 'done' else '') + '를 이 실행기의 저장 상태로 가져왔습니다. '
              '앞 단계를 다시 보내지 않습니다.', flush=True)
    return state


def _resume_with_saved_state(wd, tool, preset, explicit_step, explicit_payload, explicit_source):
    """`--step`/`--payload` 로 이을 때도 저장 상태를 버리지 않는다 — 단, **서버가 빼라고 한 칸은 되살리지 않는다**
    (2026-10-05 · 원장 W2-12 · 검토 2회차 정정).

    ■ 왜 — 서버 반려 사슬(②④⑤⑥⑦⑧ · 수십 명)
        1101·영수증 잠금·need_input 뒤에 학생의 모델이 `--step X --payload <손으로 쓴 몇 칸>` 으로 이었다. 예전 main 은
        그때 저장 상태를 아예 읽지 않고 그 몇 칸으로 체크포인트까지 덮었다 → source·rinbox 가 사라져 뒤 단계가
        반려했다(반려 원문 26건 전부 source 없음 · 지어낸 client_retry 칸).
    ■ 그런데 «빠진 칸» 은 두 뜻이다 (검토 2회차 · 재현 repro_drop_key)
        서버는 «sfx_plan 칸을 빼고 다시 부르면 다시 계획합니다»(render_plan) · «ref_hand_script 칸을 빼고 같은 단계를
        다시»(ref_hand) · «repair·fresh 칸을 빼고»(ref_geom) 처럼 **칸을 빼라고** 시킨다. 모델이 시킨 대로 뺀 칸을
        저장 상태에서 되살리면 반려된 값이 그대로 다시 나가 빠져나갈 수 없다(carry·최상위 에코·next_payload 에 이은
        넷째 «옛 값이 이긴다» 길 — CLAUDE.md). 빠진 것만 보고는 «깜빡» 과 «시켜서 뺐다» 를 가를 수 없다 →
        **서버가 그 payload 를 어떻게 판정했는지**로 가른다.
    ■ 규칙 (같은 작업 폴더·도구·프리셋이고 **이으려는 단계가 저장된 단계와 같을 때만** — 다른 단계는 합치지 않는다)
        · 입력 대기(waiting): **아무 payload 칸도 되살리지 않는다** — 사람(모델)이 준 payload 가 전부다(2026-10-05 최종
          검토 blocker). 입력 대기는 서버가 이미 판정한 자리이고, 서버는 «빼라» 를 payload_discard 로만이 아니라 산문으로도
          말한다(쇼핑 shop_footage «이전 hunted를 빼고 같은 단계로» 인데 carry:[hunted] · render_plan «sfx_plan 칸을 빼고
          다시» 반려). 예전(검토 2회차 판)에는 그 정지의 서버 원본(`next_payload.server.json`)을 깔아 모델이 시킨 대로 지운
          칸을 되살렸고, 서버가 같은 정지를 돌려줘 빠져나갈 수 없었다(tests/test_drive_waiting_resume_drop). 서버 원본은
          **알림의 기준**으로만 쓴다 — 원본에 있는데 이번에 안 보내는 칸을 이름으로 알리고 어디서 되찾는지 말한다.
          상태가 빠진 재개는 서버가 유도한다(1차 b derive-state 9e7aa109 — image_slots·sfx_plan·글꼴 측정·린박스 source).
        · 진행(active) 이고 반려 표식이 없는 판(서버가 이 payload 를 반려한 적 없음 — 1101·전송 실패·로컬 실패 뒤):
          체크포인트를 통째로 깔고 명시 값을 덮는다. 서버가 판정하지 않은 payload 이니 «빼라» 는 지시가 있을 수 없다.
        · 진행이지만 반려 뒤(`payload_rejected` 표식): payload 칸은 되살리지 않는다 — 반려 계약(payload_discard·안내)이
          기준이다. ★표식은 반려한 판에만 있다(평소 봉투는 서버 확인 스크립트가 네 칸으로 대조한다 — §_checkpoint).
          그래서 옛 실행기가 반려 뒤에 쓴 판(재개 래퍼가 쓴 판을 가져온 것 포함 — 래퍼의 저장 갈고리는 반려 여부를 받지 않는다)은 «받은 판» 처럼 보인다. 옛→새로 넘어가는 사이에 실행기를 한 번도 안 돌린
          채 `--step` 으로 이을 때만 생기고, 그때 되살린 칸이 다시 반려되면 이 실행기가 표식을 달아 다음 재개부터는 안
          되살린다(빠져나갈 수 없는 고리가 아니다).
        · 어느 경우든 최상위 소재 인자(source)는 되살린다(payload 칸이 아니라 «빼라» 대상이 될 수 없다).
        · 명시 값의 `null` 은 «이 칸을 보내지 마라» 다 — 되살리지 않고 칸을 지운다.
        · `rinbox_edit_patch` 만 주고 `rinbox_edit` 를 안 줬으면, 저장본 편집표 중 판 지문이 patch.base_id 와 같은 것만
          되살린다(그 patch 가 가리키는 바로 그 판 · 서버 계약). 판이 다르면 되살리지 않는다 — 서버의 고치기 안내가 간다.
        · `--payload` 만 주고 `--step` 을 안 주면 저장된 단계로 잇는다 · `--source`(새 작업)는 합치지 않는다.
        · 되살린 칸과, 저장돼 있지만 보내지 않은 칸을 출력한다(조용히 바꾸지 않는다).
    돌려주는 것: (단계, payload, source, 합친 저장 상태 또는 None)
    """
    from volcano_run import _review_receipt_io_path
    if explicit_source is not None:
        return explicit_step, explicit_payload, explicit_source, None
    try:
        state = _resume_state(wd, tool, preset)
    except StepError as error:
        _progress('  [재개] 저장 상태를 읽지 못해 명시한 값만으로 잇습니다: ' + str(error)[:200], flush=True)
        return explicit_step, explicit_payload, explicit_source, None
    if (explicit_step == 'customize' and 'customization_patch' in (explicit_payload or {})
            and state and state.get('status') in ('active', 'waiting', 'done')):
        return _customize_over_saved(wd, tool, preset, state, explicit_payload)
    if not state or state.get('status') not in ('active', 'waiting'):
        return explicit_step, explicit_payload, explicit_source, None
    saved_step = state['args']['step']
    target = explicit_step or saved_step
    if target != saved_step:
        _progress('  [재개] 저장된 진행은 «' + saved_step + '» 단계입니다. 다른 단계(«' + target + '»)를 지정해 저장 상태를 '
                  '합치지 않았습니다 — 다른 자리의 측정값을 되살리면 옛 값이 새 값을 이깁니다. '
                  + ('지정한 payload 그대로 «' + target + '» 단계를 잇습니다.' if explicit_payload else
                     '저장된 단계에서 이으려면 --step·--payload 없이 같은 명령을 실행하세요.'), flush=True)
        return explicit_step, explicit_payload, explicit_source, None
    saved = unfold_payload(dict(state['args']['payload']))
    if state['status'] == 'waiting':
        # 입력 대기 = 서버가 이미 판정한 자리. 사람(모델)이 준 payload 가 전부다 — 되살리지 않는다(최종 검토 blocker).
        # 알림의 기준만 서버가 그 정지(또는 그 뒤 반려)에서 준 원본이다(payload_discard 로 뺀 칸은 기준에서도 뺐다).
        base = {}
        reference = _load_server_next_payload(wd, target) or saved
    elif state.get('payload_rejected') is True:
        base = {}
        reference = saved
    else:
        base = dict(saved)
        reference = saved
    explicit = dict(explicit_payload or {})
    dropped = sorted(k for k, v in explicit.items() if v is None)
    merged = dict(base)
    merged.update(explicit)
    for key in dropped:
        merged.pop(key, None)
    merged['workdir'] = explicit.get('workdir') or merged.get('workdir') or wd
    patch = explicit.get('rinbox_edit_patch')
    if isinstance(patch, dict) and 'rinbox_edit' not in explicit:
        held = merged.get('rinbox_edit') if isinstance(merged.get('rinbox_edit'), dict) else saved.get('rinbox_edit')
        if isinstance(held, dict) and patch.get('base_id') == _edit_revision(held):
            merged['rinbox_edit'] = held
        else:
            merged.pop('rinbox_edit', None)
            if isinstance(held, dict):
                _progress('  [재개] 저장된 편집표(rinbox_edit)의 판이 patch 의 base_id 와 달라 되살리지 않았습니다 — 서버가 '
                          '지금 판의 base_id 를 알려 주면 그것으로 patch 를 다시 만드세요.', flush=True)
    restored = sorted(k for k in merged if k not in explicit and k != 'workdir')
    if restored:
        _progress('  [재개] 저장 상태에서 되살린 칸(' + str(len(restored)) + '): ' + ', '.join(restored[:20])
                  + (' 외 %d개' % (len(restored) - 20) if len(restored) > 20 else ''), flush=True)
    left = sorted(k for k in reference if k not in merged and k != 'workdir')
    if left:
        if state['status'] == 'waiting':
            where = (SERVER_NEXT_PAYLOAD_FILE if os.path.isfile(_review_receipt_io_path(os.path.join(wd, SERVER_NEXT_PAYLOAD_FILE)))
                     else DRIVE_STATE_FILE)
            _progress('  [재개] 서버가 이 단계에서 준 원본(' + where + ')에는 있지만 이번에 보내지 않은 칸(' + str(len(left))
                      + '): ' + ', '.join(left[:20]) + (' 외 %d개' % (len(left) - 20) if len(left) > 20 else '')
                      + ' — 입력 대기에서는 사람(모델)이 고친 payload 를 그대로 보냅니다(서버가 빼라고 한 칸일 수 있어 되살리지 '
                      '않습니다). 실수로 지웠다면 그 파일에서 그 칸을 next_payload.json 에 다시 넣고 같은 명령을 실행하세요.',
                      flush=True)
        else:
            _progress('  [재개] 저장 상태에는 있지만 보내지 않은 칸(' + str(len(left)) + '): ' + ', '.join(left[:20])
                      + (' 외 %d개' % (len(left) - 20) if len(left) > 20 else '') + ' — 지난번 이 단계의 payload 를 서버가 '
                      '반려한 판이라 되살리지 않았습니다(서버가 빼라고 한 칸일 수 있습니다). 반려 안내대로 고친 칸만 명시하세요.',
                      flush=True)
    source = state['args'].get('source')
    return target, merged, source, state


def _cow_leftover_notice(wd):
    """옛 실행기의 «작업 폴더 자신 떼기»(M8)가 남긴 흔적을 찾아 알린다 (2026-10-05 · 검토 2회차 누락 ⑦).

    옛 `extract_pack` 은 작업 폴더 자신이 정션·심링크면 그 폴더를 통째로 복사·교체하려 했다(`_pack_detach`). 그때
    상위 폴더에 `.volcano-cow-<임의>/original`(원래 연결)이 남은 사람이 있다(진단 원문 · 가린 사본 m8_masked):
      ㉠ 교체도 복구도 실패 — 작업 폴더 경로가 **없어지고** 원래 연결이 `original` 에 남았다(정치 기록).
      ㉡ 교체는 됐고 원래 연결 지우기만 실패 — 작업 폴더가 원래 폴더의 **복사본**으로 갈라졌다(3D쇼츠 기록).
    새 코드는 더 만들지 않지만 이미 그렇게 된 사람은 그대로다. 여기서는 **알리기만** 한다 — 상위 폴더에 같은 흔적이
    여럿이면 어느 작업 폴더의 것인지 실행기가 확정할 수 없고(흔적에 원래 이름이 적혀 있지 않다), ㉡ 은 복사본에 쌓인
    진행을 덮을 수 있어 사람이 고른다. 되돌리는 명령은 옛 코드가 하려던 바로 그 한 줄(os.replace)이다."""
    parent = os.path.dirname(os.path.abspath(wd))
    try:
        entries = [e for e in os.scandir(parent)
                   if e.name.startswith('.volcano-cow-') and e.is_dir(follow_symlinks=False)]
    except OSError:
        return []
    found = []
    for entry in entries:
        original = os.path.join(entry.path, 'original')
        try:
            if not (os.path.lexists(original) and _pack_link(original)):
                continue
            target = os.path.realpath(original)
        except OSError:
            continue
        found.append((original, target))
    if not found:
        return []
    missing = not os.path.lexists(wd)
    lines = ['  ⚠ [작업 폴더 연결] 옛 실행기가 작업 폴더 연결을 떼다 멈춘 흔적이 상위 폴더에 ' + str(len(found)) + '개 있습니다'
             ' (이 작업 폴더 또는 같은 상위 폴더의 다른 작업 폴더의 것일 수 있습니다). 자동으로 바꾸지 않았습니다.']
    for original, target in found:
        lines.append('     · 원래 연결: ' + original + '  →  원래 가리키던 폴더: ' + target)
    if missing:
        original = found[0][0]
        lines.append('     이 작업 폴더(' + wd + ')가 없습니다 — 연결이 위 «원래 연결» 자리로 옮겨진 채 멈춘 것입니다. '
                     '원래 이름으로 되돌리려면(가리키던 폴더는 손대지 않았습니다):')
        lines.append('       ' + _quote_command([sys.executable, '-c', 'import os,sys; os.replace(sys.argv[1], sys.argv[2])',
                                                 original, wd]))
        if len(found) > 1:
            lines.append('     ★흔적이 여럿이면 «원래 가리키던 폴더» 를 보고 이 작업 폴더의 것을 고르세요.')
    else:
        lines.append('     이 작업 폴더가 연결이 아니라 일반 폴더라면, 옛 실행기가 원래 폴더를 복사해 갈아 끼운 것입니다 — 그 뒤 진행은 '
                     '이 폴더(복사본)에 쌓였고 «원래 가리키던 폴더» 에는 그 전 진행만 있습니다. 어느 쪽을 쓸지 정한 뒤 '
                     '쓰지 않을 쪽과 위 흔적 폴더를 정리하세요.')
    for line in lines:
        _progress(line, flush=True)
    return found


def _vanished_workdir(wd):
    r"""작업 폴더가 **지금 안 보이면** 처음으로 안 보이는 자리(드라이브 뿌리·외장 볼륨·옮긴 폴더), 보이면 None (2026-10-19 #224).

    ■ 왜 — 윈도우 신고 «[WinError 3] … '\\?\D:\'» 5명(D: 4 · G: 1 — 경로 «내 드라이브» 라 구글 드라이브로 보임)은 `\\?\` 머리 탓이 아니었다.
      win-01 실측: 프로세스가 그 폴더를 쓰던 중 드라이브가 빠지면(가상 디스크 분리로 재현) Delivery 의
      `os.makedirs(\\?\…\.volcano-responses\<sha>)` 가 조상마다 «없음» 을 보고 드라이브 뿌리까지 올라가 WinError 3 '\\?\G:\'
      로 죽는다(신고와 makedirs 5겹까지 같다). 머리 없는 `G:\…` 도 'G:\' 로 똑같이 죽는다. 드라이브가 붙어 있는 동안은
      NTFS·exFAT·FAT32·subst·UNC 에서 Python 3.11·3.14 모두 머리 경로가 정상이었다. 신고 트레이스백에 실행기 줄 원문이
      비어 있는 것(그 순간 D: 의 runner 파일도 못 읽음)도 같은 사정이다.
    ■ 실행기가 드라이브를 되살릴 수는 없다 — «무엇이 사라졌나» 를 그 자리 이름으로 말한다. 조상을 한 번 거슬러 오를 뿐
      (경로 깊이만큼)이고 기다리거나 다시 시도하지 않는다.
    """
    if not isinstance(wd, str) or not os.path.isabs(wd):
        return None
    from volcano_run import _review_receipt_io_path
    here = os.path.abspath(wd)
    if os.path.isdir(_review_receipt_io_path(here)):
        return None
    while True:
        parent = os.path.dirname(here)
        if parent == here or os.path.exists(_review_receipt_io_path(parent)):
            return here
        here = parent


def _vanished_note(wd):
    """사람에게 보일 한 줄 — 작업 폴더가 보이면 빈 글자."""
    gone = _vanished_workdir(wd)
    if gone is None:
        return ''
    return ('작업 폴더 ' + wd + ' 가 지금 보이지 않습니다(처음 안 보이는 자리: ' + gone + ') — 외장 드라이브가 빠졌거나 잠들었거나 '
            '동기화 드라이브(구글 드라이브 등)의 연결이 끊긴 것입니다. 실행기가 고칠 수 없는 바깥 사정입니다. 드라이브를 다시 연결해 '
            '그 폴더가 보이면(옮겼다면 원래 자리로) 같은 명령으로 이으세요 — 받은 결과·영수증은 그 폴더에 그대로 있습니다. ')


def _report_resume_after_failure(wd, tool, preset, key_file, max_steps, error=None, *, rejection_saved=False):
    """예외로 멈출 때 잇는 길을 남긴다(W2-12 ④) — **서버 반려와 그 밖의 실패를 가른다** (2026-10-05 최종 검토).

    · 서버가 판정하지 않은 실패(1101·전송 끊김·로컬 실패): 저장된 판을 그대로 다시 보내면 된다 → `--step` 없는 명령.
    · 서버 반려(RejectedError): 같은 판을 그대로 다시 보내면 같은 반려다. 예전에는 여기서도 «--step·payload 를 손으로
      고치지 마라 · 이 명령 그대로» 를 내서 ① 다른 단계로 보내는 반려(계약 next_step — 3D쇼츠 `_tool_error(…, next_step=)`)
      는 반려된 단계를 되풀이했고 ② 사람이 고칠 반려는 next_payload.json 에 고친 값이 무시됐다(평소 재개는 진행 판의
      체크포인트를 보낸다). 이제 저장 단계(계약 next_step 이 있으면 그 단계 — _drive_loop 가 그것을 저장한다)와
      «next_payload.json 을 고친 뒤 `--step <그 단계> --payload next_payload.json`» 을 낸다. 그 파일은 반려 계약이 게시한
      판이다(payload_discard 를 뺐다) — 고칠 것이 없으면 그대로 실행해도 된다(바깥 원인을 고친 경우).
    · `rejection_saved` — 이 실행이 방금 보낸 판을 반려 판으로 저장했는가. 저장된 판이 **예전** 반려 판인데(표식 있음)
      이번 실행은 그 판을 다시 저장하기 전에 멈췄다면 next_payload.json 은 반려가 게시한 판이고 사람이 고쳤을 수 있다 —
      덮지 않는다(예전에는 체크포인트로 덮어 고친 값을 지웠다 · 2026-10-05 B 최종 검토 3회차). 평소 재개도 그 파일을
      보낸다(§main).
    """
    note = _vanished_note(wd)
    if note:
        # 저장 상태를 읽을 수 없다(그 폴더 안에 있다) — 무엇이 사라졌는지와 잇는 법만 말한다(#224).
        _progress('\n  ⏸ ' + note, flush=True)
        return
    try:
        state = _resume_state(wd, tool, preset)
    except StepError:
        state = None
    if not state or state.get('status') not in ('active', 'waiting'):
        return
    from volcano_run import _review_receipt_io_path
    out = os.path.join(wd, 'next_payload.json')
    held_edit = (state['status'] == 'active' and state.get('payload_rejected') is True and not rejection_saved
                 and os.path.exists(_review_receipt_io_path(out)))
    if state['status'] == 'active' and not held_edit:
        # 사람이 고칠 대기 파일(waiting)과 예전 반려가 게시한 파일(held_edit)은 건드리지 않는다. 기계 진행만 서버 계약의
        # 모양으로 다시 내보인다.
        _photo_write_state(_review_receipt_io_path(out), state['args']['payload'])
    step = state['args']['step']
    own = getattr(error, 'resume_lines', None)
    if isinstance(own, list) and own:
        # ★잇는 길을 스스로 실은 정지(사진 실사 검수 · volcano_run.check_photo) — «같은 명령 그대로» 는 같은 정지로 돌아온다
        #   (검수 답이 그림 파일마다 저장돼 있다). 그 정지가 준 한 줄을 가리킨다(Q 묶음 · 2026-10-06).
        _progress("\n  ⏸ 실행기가 «" + step + "» 단계에서 사람의 선택을 기다리며 멈췄습니다. 같은 명령을 다시 실행하지 마세요 — "
                  "저장된 판정으로 같은 정지가 납니다. 위 판정 근거를 보고 칸마다 고른 뒤 그 길의 한 줄로 이으세요:\n"
                  + "\n".join("     " + str(line) for line in own), flush=True)
        return
    if isinstance(error, RejectedError):
        contract = getattr(error, 'contract', None)
        # 서버는 반려된 단계와 다를 때만 계약에 next_step 을 싣는다(volcano_tools._rejection_contract) → 저장 단계와 같으면 옮긴 것.
        moved = isinstance(contract, dict) and contract.get('next_step') == step
        _progress("\n  ⏸ 서버가 반려했습니다(사유는 위 반려문). 저장 상태는 «" + step + "» 단계"
                  + (" — 반려 계약이 다음 단계로 지정한 단계입니다" if moved else "") + " · 고칠 payload: " + out + "\n"
                  "     반려 안내대로 그 파일을 고친 뒤(빼라는 칸은 빼고 · 고칠 것이 없으면 그대로) 이 명령으로 이으세요:\n"
                  "     " + _resume_command(wd, {'step': step}, out, tool, key_file, max_steps) + "\n"
                  "     (--step 없이 늘 쓰던 같은 명령을 실행해도 이 파일을 보냅니다.)", flush=True)
        return
    if held_edit:
        _progress("\n  ⏸ 실행기가 «" + step + "» 단계에서 멈췄습니다. 저장된 판은 지난번 서버가 반려한 판이라 다음 실행은 "
                  + out + " 를 보냅니다(고친 값 그대로 · 이 파일은 덮지 않았습니다).\n"
                  "     원인을 해결한 뒤 이 명령으로 이으세요:\n"
                  "     " + _plain_resume_command(wd, tool, key_file, max_steps), flush=True)
        return
    _progress("\n  ⏸ 실행기가 «" + step + "» 단계에서 멈췄습니다. 완료한 작업과 측정값은 저장돼 있습니다.\n"
              "     원인을 해결한 뒤 이 명령 그대로 이으세요(--step·payload 를 손으로 고쳐 쓰지 마세요 — 저장 상태가 이어 갑니다):\n"
              "     " + _plain_resume_command(wd, tool, key_file, max_steps), flush=True)


def main(argv=None):
    """`python volcano_drive.py --workdir <작업폴더> [--step env] [--payload next_payload.json]`

    ★출입증(`assets` 응답)으로 서버를 직접 부르며 끝까지 돈다. 사람이 채울 자리(need_input)
      에서 멈추고 `next_payload.json` 을 남긴다 — 채운 뒤 안내한 다음 단계로 이어간다.
    돌려주는 값: 0 끝 · 2 출입증 없음 · 3 사람 입력 또는 접수 결과 대기.

    ■ ★`--tool` — 어느 MCP 도구를 몰 것인가 (2026-09-04 신설)
        기본은 `volcano_video`(수강생 전원의 경로 — 안 주면 예전과 한 글자도 안 다르다).
        조교 계측 체인은 `--tool volcano_ref` 로 돈다. 도구 이름이 맞는지는 **서버가**
        판정한다 — 여기에 아는 도구 목록을 적지 않는다(적으면 도구가 늘 때 낡는다).
        · 첫 단계 기본값도 도구를 따라간다: `volcano_video` 는 `env`(자산을 이미 받은
          자리), 그 밖은 `setup`(곁 도구의 첫 단계).
        · 출입증: 곁 도구에는 그것을 **발급하는 단계가 없다**(`assets` 는 영상 단계다) —
          `--key-file` 로 같은 모양의 파일(`{"token":…, "url":…}`, 0600)을 가리킨다.
    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=os.getcwd())
    ap.add_argument("--step", default=None,
                    help="시작 단계(기본: volcano_video 는 env · 그 밖의 도구는 setup)")
    ap.add_argument("--payload", default=None,
                    help="payload JSON 파일(기본: <workdir>/next_payload.json 이 있으면 그것)")
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--background", action="store_true",
                    help="독립 프로세스로 실행하고 PID·진행 로그·종료 상태 경로를 남깁니다")
    ap.add_argument("--tool", default=None,
                    help="부를 MCP 도구 이름(기본 volcano_video · 조교 계측은 volcano_ref)")
    ap.add_argument("--key-file", default=None,
                    help=f"출입증 JSON 경로(기본 <workdir>/{RUNNER_KEY_FILE}). "
                         "★토큰 값을 인자로 주지 마라 — ps 로 남에게 보인다")
    ap.add_argument("--source", default=None,
                    help='소재 JSON — --step 이 없으면 `start` 부터 돈다. 예: {"kind":"youtube","url":"…"} · {"kind":"local_video","path":"/abs/a.mp4"}')
    a = ap.parse_args(argv)
    wd = os.path.abspath(a.workdir)
    delegated = _run_workdir_runner(wd, sys.argv[1:] if argv is None else list(argv))
    if delegated is not None:
        return delegated
    _cow_leftover_notice(wd)
    # 실행기 밖에서 Claude 가 직접 치는 엔진 팩 도구(안내형 단계)가 영상 인코더 판정을 찾는 오래 가는 자리 — 돌 때마다 한 번 대조
    from volcano_run import RUNNER_ID                                # noqa: PLC0415
    install_home_runner(wd, RUNNER_ID)
    tool = (a.tool or "").strip() or Client.tool
    rk, why = load_runner_key(wd, a.key_file)
    if not rk:
        _progress("  ✗ " + why, flush=True)
        if tool != Client.tool:
            _progress(f"     ★`--tool {tool}` 에는 출입증을 발급하는 단계가 없다 — 본인 토큰으로 "
                  f'{{"token":"…","url":"…"}} 파일을 만들고 `--key-file <경로>` 로 가리켜라'
                  " (chmod 600).", flush=True)
        return 2
    if a.background:
        child_argv = [sys.executable, '-u', os.path.abspath(__file__),
                      '--workdir', wd, '--tool', tool, '--max-steps', str(a.max_steps)]
        for option, value in (('--step', a.step), ('--payload', a.payload),
                              ('--key-file', a.key_file), ('--source', a.source)):
            if value is not None:
                if option in ('--payload', '--key-file') or (option == '--source' and not value.strip().startswith('{')):
                    value = os.path.abspath(value)
                child_argv += [option, value]
        state_dir = tempfile.mkdtemp(prefix='.volcano-background-', dir=wd)
        state = _launch_logged(child_argv, state_dir, wd)
        _progress('  실행 접수 (완료 여부는 종료 상태로 확인): PID ' + str(state['pid'])
                  + '\n  진행 로그: ' + state['log_path'] + '\n  종료 상태: ' + state['status_path'])
        return state.get('returncode', 0)
    with _workdir_run_lock(wd) as owner:
        if owner is not None:
            _progress(_workdir_busy_text(wd, owner), flush=True)
            return 3
        return _drive_main(a, wd, tool, rk)


#: 이 프로세스가 쥔 «작업 폴더 실행 잠금»(직접 실행) — 판 갱신으로 다시 띄우기 직전에 놓는다(_restart_after_update).
_DIRECT_RUN_LOCK = []


def _drive_owner_path(wd):
    return os.path.join(os.path.realpath(wd), '.volcano-drive.owner.json')


def _claim_drive_owner(wd, state):
    """잠금을 얻은 뒤 «누가 쥐었나» 를 적는다 — 판정은 OS 잠금이 하고(주인이 죽으면 OS 가 푼다) 이 기록은 알려 주기만 한다."""
    try:
        _photo_write_state(_drive_owner_path(wd), state)
    except (OSError, ValueError, StepError):
        pass  # 알림용 기록이다 — 못 써도 잠금(판정)은 그대로 선다.


@contextlib.contextmanager
def _workdir_run_lock(wd):
    """한 작업 폴더에는 실행기 하나만 — 직접 실행도 진행 기록 실행(_logged_child)과 **같은 잠금**을 쥔다.

    예전에는 `--background` 진행 기록 실행만 이 잠금을 쥐어, 직접 실행 둘(또는 진행 기록 실행 + 직접 실행)이 같은 폴더에서
    함께 돌다가 render_plan 검수 잠금에서 부딪혀 «다른 실행기가 같은 검수 요청을 처리 중» 으로 멈췄다(10-21 인물형 롱폼
    5db32e: 작업 폴더 6개에서 1분 동안 45번). 잠겨 있으면 owner(기록) 를 내주고 아무 일도 하지 않는다 — 주인이 살아 있다는
    증거는 OS 잠금 자체다(주인 프로세스가 죽으면 OS 가 푼다 · 낡은 잠금이 없다)."""
    if globals().get('_LOGGED_STATE'):
        yield None          # 진행 기록 실행은 _logged_child 가 이미 이 잠금을 쥐고 있다.
        return
    from volcano_run import _asr_lock
    held = contextlib.ExitStack()
    try:
        held.enter_context(_asr_lock(os.path.join(os.path.realpath(wd), '.volcano-drive.lock')))
    except TranscriptionPending:
        try:
            with open(_drive_owner_path(wd), encoding='utf-8') as fh:
                owner = json.load(fh)
        except (OSError, ValueError):
            owner = {}
        yield owner if isinstance(owner, dict) else {}
        return
    _DIRECT_RUN_LOCK.append(held)
    try:
        _claim_drive_owner(wd, {'version': 1, 'pid': os.getpid(), 'started_at': time.time(), 'mode': 'direct'})
        yield None
    finally:
        if held in _DIRECT_RUN_LOCK:
            _DIRECT_RUN_LOCK.remove(held)
        held.close()


def _release_direct_run_lock():
    while _DIRECT_RUN_LOCK:
        _DIRECT_RUN_LOCK.pop().close()


def _workdir_busy_text(wd, owner):
    who = []
    if isinstance(owner.get('pid'), int):
        who.append('PID ' + str(owner['pid']))
    if isinstance(owner.get('started_at'), (int, float)):
        who.append('시작 ' + time.strftime('%H:%M:%S', time.localtime(owner['started_at'])))
    if isinstance(owner.get('log_path'), str):
        who.append('진행 로그 ' + owner['log_path'])
    return ('\n  ⏸ 이 작업 폴더에서 다른 실행기가 아직 돌고 있습니다' + (' (' + ' · '.join(who) + ')' if who else '')
            + ' — 아무것도 하지 않고 끝냈습니다.\n'
            '     같은 폴더에서 실행기를 동시에 둘 돌리지 마세요. 그 실행이 끝난 뒤(진행 로그·종료 상태 확인) 같은 명령을 다시 실행하면 '
            '이어서 진행합니다(새 유료 요청 없음).\n     작업 폴더: ' + wd)


def _drive_main(a, wd, tool, rk):
    c = Client(rk["url"], rk["token"], preset=rk.get("preset") or "뇌전구", tool=tool)
    if not a.source:
        _import_wrapper_state(wd, tool, c.preset)
    saved = None if (a.step or a.payload or a.source) else _resume_state(wd, tool, c.preset)
    pl_path = a.payload or os.path.join(wd, "next_payload.json")
    payload = {"workdir": wd}
    if not saved and os.path.exists(pl_path):
        with open(pl_path, encoding="utf-8") as fh:
            # ★저장 파일은 접힌 채다 — 읽는 순간 펼친다(§unfold_payload). 접힌 채 두면 뒤의 carry 가
            #   focus_measurements 를 바꾸는 순간 참조가 낡아 서버가 «측정 참조가 올바르지 않습니다» 로 반려한다.
            payload = unfold_payload(dict(json.load(fh)))
        payload.setdefault("workdir", wd)
    src = None
    # ★첫 단계 기본값은 **도구마다 다르다.** 영상은 `env`(자산을 이미 받은 자리)이고
    #   곁 도구는 `setup` 이다 — 영상의 `env` 를 곁 도구에 보내면 «알 수 없는 step» 이다.
    step = a.step or ("env" if tool == Client.tool else "setup")
    if a.source:
        src = json.loads(a.source) if str(a.source).strip().startswith("{") else json.load(open(a.source, encoding="utf-8"))
        if not a.step:
            step = 'start'      # An explicit resume step keeps unconsumed source without restarting.
    merged_state = None
    if not saved and (a.step or a.payload) and not a.source:
        # ★명시 재개도 저장 상태를 깔고 그 위에 명시 값을 덮는다(W2-12 · §_resume_with_saved_state).
        _step, payload, _src, merged_state = _resume_with_saved_state(wd, tool, c.preset, a.step, payload, None)
        if merged_state is not None:
            step, src = _step, _src
    if saved:
        if saved['status'] == 'done':
            _progress('  ✅ 저장된 작업은 완료 상태입니다. 새 작업은 --step 또는 --source로 시작하세요.')
            return 0
        args = saved['args']
        step, payload, src = args['step'], unfold_payload(args['payload']), args.get('source')
        # ★서버가 반려한 진행 판(`payload_rejected`)도 입력 대기처럼 next_payload.json 을 보낸다(2026-10-05 B 최종 검토
        #   3회차). 반려 정지는 «그 파일을 고친 뒤 --step <단계> --payload …» 를 안내하지만, 사람이 늘 쓰던 같은 명령을
        #   치면 예전에는 반려된 체크포인트를 그대로 다시 보내 고친 값이 무시되고 같은 반려를 한 번 더 받았다. 반려 판의
        #   next_payload.json 은 반려가 게시한 바로 그 판이라(고친 것이 없으면 체크포인트와 같다) 그것을 보내는 것이
        #   안내한 명령과 같은 일이다. 파일이 없으면(게시 전에 끊김) 체크포인트를 보낸다.
        rejected = saved['status'] == 'active' and saved.get('payload_rejected') is True
        if saved['status'] == 'waiting' or (rejected and os.path.exists(pl_path)):
            try:
                with open(pl_path, encoding='utf-8') as fh:
                    edited = json.load(fh)
                if not isinstance(edited, dict):
                    raise ValueError('payload must be an object')
                edited.setdefault('workdir', wd)
                if os.path.normcase(os.path.realpath(str(edited['workdir']))) != os.path.normcase(os.path.realpath(wd)):
                    raise ValueError('workdir differs')
            except (OSError, ValueError, TypeError) as error:
                raise StepError(('반려된 payload 파일' if rejected else '입력 대기 파일')
                                + '을 확인할 수 없습니다. 파일을 고친 뒤 다시 실행하세요: ' + pl_path) from error
            # 사람(모델)이 고친 next_payload.json 이 전부다 — 서버 원본에 있는데 빠진 칸은 알리기만 한다(최종 검토 blocker).
            _, payload, _, _ = _resume_with_saved_state(wd, tool, c.preset, step, unfold_payload(edited), None)
            if rejected:
                _progress('  [재개] 지난번 서버가 반려한 판입니다 — ' + pl_path + ' 의 payload 를 보냅니다(고친 값 포함).',
                          flush=True)
        _progress('  ↻ 저장된 단계에서 재개합니다: ' + step)
    # A rejected human edit remains editable; failed machine work still uses only
    # its authoritative active checkpoint. Explicit commands emitted below retain
    # the same waiting identity without weakening explicit override behavior.
    input_state = saved or merged_state
    if input_state is None and a.step:
        try:
            candidate = _resume_state(wd, tool, c.preset)
        except StepError:
            candidate = None
        if (candidate and candidate['status'] == 'waiting'
                and candidate['args']['step'] == step
                and os.path.normcase(os.path.realpath(pl_path)) == os.path.normcase(os.path.realpath(os.path.join(wd, 'next_payload.json')))):
            input_state = candidate
    if input_state and input_state['status'] == 'waiting':
        c._runner_input_step = step
    # FP2 자동 갱신이 같은 명령으로 다시 띄울 때 쓸 값(출입증 경로만 · 토큰 값은 싣지 않는다).
    c._runner_restart = {'key_file': a.key_file}
    try:
        st = drive(c, step, payload, source=src, max_steps=a.max_steps)
    except Exception as error:
        # ★예외로 멈출 때도 잇는 길을 남긴다(W2-12 ④). 예전에는 트레이스백으로만 끝나 학생의 모델이
        #   `--step` + 손으로 쓴 몇 칸으로 우회했고, 그 몇 칸이 저장 상태를 덮었다(반려 사슬의 시작).
        #   체크포인트는 그 단계를 시작할 때 이미 저장했다 — 잇는 명령을 보여 주고 원래 예외를 올린다.
        #   서버 반려면 고칠 파일과 계약 단계를 말한다(§_report_resume_after_failure).
        _report_resume_after_failure(wd, tool, c.preset, a.key_file, a.max_steps, error,
                                     rejection_saved=getattr(c, '_runner_rejection_saved', False))
        raise
    if st.get('restart'):
        # FP2 — drive() 가 계측 구간을 닫고 기록을 낸 뒤에 다시 띄운다(§_runner_update_restart ④).
        return _restart_after_update(st['restart'])
    res = st.get("res") or {}
    if res.get("status") == "pending":
        out = os.path.join(wd, "next_payload.json")
        _photo_write_state(out, fold_payload(st.get("payload") or {}))
        command = _resume_command(wd, st, out, tool, a.key_file, a.max_steps)
        limited = res.get('reason') == 'step_limit'
        title = '단계 상한에 따라 일시정지' if limited else '처리 결과 대기'
        resume = '이어서 실행' if limited else f"{res.get('retry_after', 0)}초 이상 기다린 뒤 재개"
        _progress(f"\n  ⏸ {title} — 단계 {st.get('step')} · payload 는 {out} 에 남겼다.\n"
              f"     {res.get('message', '')}\n"
              f"     {resume}: {command}", flush=True)
        return 3
    if res.get("status") == "need_input" or (res.get("author") or {}).get("keys"):
        out = os.path.join(wd, "next_payload.json")
        _photo_write_state(out, fold_payload(st.get("payload") or {}))
        _save_server_next_payload(wd, st.get("step"), res)
        command = _resume_command(wd, st, out, tool, a.key_file, a.max_steps)
        for review_path, reply_field in _save_review_handoff(wd, st, out):
            _progress(f"  [검수 자료·응답 형식] {review_path}\n"
                  "     현재 연결된 클라이언트가 요청의 모든 실제 이미지와 필수 영상·음성을 읽고 검토하세요.\n"
                  f"     {out} 의 {reply_field} 객체에 요청 SHA를 키로 답을 저장하세요.\n"
                  "     값은 reply_schema의 확인 ID/SHA를 포함하고, answer는 prompt가 요구한 판정 JSON이어야 합니다.\n"
                  "     reply_error가 있으면 같은 자료를 기준으로 해당 답을 수정하세요. 읽지 못한 자료는 완료로 답하지 마세요.", flush=True)
        _progress(f"\n  ⏸ 사람(모델)이 채울 차례 — 단계 {st.get('step')} · payload 는 {out} 에 남겼다.\n"
              f"     채운 뒤: {command}", flush=True)
        return 3
    return 0


def drive(c, step, payload=None, headers=None, source=None, max_steps=40):
    """Keep local observations across native pauses and restarts."""
    with runtime_metrics.context((payload or {}).get('workdir')):
        try:
            with runtime_metrics.span('drive', step):
                return _drive_observed(c, step, payload, headers, source, max_steps)
        finally:
            observed = runtime_metrics.export()
            if observed:
                active = observed.get('active_seconds')
                label = f"{active:.1f}초" if isinstance(active,(int,float)) else '미확정'
                complete = '' if observed.get('measurement_complete') else ' · 일부 기록 불완전'
                _progress(f"  [실행 기록] 이 작업 폴더의 관측된 누적 실행 {label}{complete} · 실제 청구액 미측정 · runtime-report.json")


def _drive_observed(c, step, payload=None, headers=None, source=None, max_steps=40):
    """`next_step` 을 따라가며 기계적인 일을 한다. 사람이 필요한 자리에서 멈춘다.

    돌려주는 것: {"step": 멈춘 단계, "res": 그 응답, "payload": 지금까지 쌓인 payload}

    ★여기서 죽으면 **서버에 알리고** 그대로 다시 던진다(§_report_failure).
    """
    payload = dict(payload or {})
    import ta_upgrade_local
    payload = ta_upgrade_local.attach_context(payload, c.preset, client=c)
    reader = getattr(c, '_runner_checkpoint_reader', None)
    c._receipt_durable_owner = not callable(getattr(c, '_runner_checkpoint', None)) or callable(reader)
    if c._receipt_durable_owner and isinstance(payload.get('workdir'), str):
        import response_receipts
        from volcano_run import _review_receipt_io_path
        if callable(reader):
            state = reader()
        elif os.path.isdir(_review_receipt_io_path(os.path.join(payload['workdir'], '.volcano-responses'))):
            state = _resume_state(payload['workdir'], c.tool, c.preset)
        else:
            state = None
        response_receipts.restore_handoff(c, state, step, payload, source,
            save=_photo_write_state, io_path=_review_receipt_io_path)
        c._runner_response_handoff = (state or {}).get('response_handoff')
    # ★**어느 단계에서 죽었는지**를 알려야 한다. `step` 은 루프 안에서 바뀌므로
    #   시작 단계를 그대로 쓰면 늘 'start' 로 보고된다 — 아무 쓸모가 없다.
    at = {"step": step}
    try:
        st = _drive_loop(c, at, payload, headers, source, max_steps)
        if st.get('restart'):
            return st       # FP2 — 같은 단계를 «진행» 으로 이미 저장했다(완료로 덮으면 새 실행기가 멈춘다)
        res = st.get('res') or {}
        human = res.get('status') == 'need_input' or bool((res.get('author') or {}).get('keys'))
        status = 'waiting' if human else 'active' if res.get('status') == 'pending' else 'done'
        # ★사람 차례로 멈출 때도 받은 응답을 **소비**한다 (2026-10-17 · 뇌전구 images flow_resume 신고).
        #   소비하지 않으면 영수증이 «ready» 로 남아, 사람이 나중에 같은 명령(같은 payload)을 다시 돌릴 때 서버에 묻지 않고
        #   **디스크의 옛 답**을 그대로 내준다 — «4분 50초 남았습니다» 가 107초·335초 뒤에도 같은 글자로 나왔고 서버에는
        #   그 두 요청이 한 줄도 오지 않았다(진단 저장소). 기다림·파일 넣기처럼 **바깥 사정**을 묻는 멈춤은 다시 물어야 맞다.
        #   상태(waiting)를 먼저 저장한 뒤 소비한다 — 단계를 넘어갈 때와 같은 순서(_checkpoint → acknowledge_response).
        consumed = human and getattr(c, '_receipt_returned', None) is not None
        _checkpoint(c, st['step'], st['payload'], st.get('source'), status, response_consumed=consumed)
        if consumed:
            c.acknowledge_response()
        return st
    except Exception as e:  # noqa: BLE001
        # 디스크 가득 참은 어느 자리에서 났든 같은 말로(판별 한 곳 volcano_run.disk_full_note · 10-24 voice «OSError: [Errno 28]» 날것)
        _disk = None if isinstance(e, StepError) else _vr_disk_full_note(e, getattr(c, "_last_workdir", None))
        if _disk:
            full = StepError(f"[{at['step']}] {_disk}")
            _report_failure(c, at["step"], full)
            raise full from e
        _report_failure(c, at["step"], e)
        raise


_REEXEC_FLAG = 'VOLCANO_RUNNER_REEXEC'


def _file_sha_or_none(path):
    try:
        with open(path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _custom_media_repatch(payload, source):
    """바뀐 원본을 가리키는 customization 칸(images·memes)을 그대로 담은 patch — 없으면 None."""
    custom = payload.get('customization') if isinstance(payload, dict) else None
    if not isinstance(custom, dict):
        return None
    want = os.path.normcase(os.path.abspath(str(source)))
    patch = {}
    for field in ('images', 'memes'):
        rows = custom.get(field)
        if not isinstance(rows, dict):
            continue
        for key, row in rows.items():
            if (isinstance(row, dict) and isinstance(row.get('path'), str)
                    and os.path.normcase(os.path.abspath(row['path'])) == want):
                patch.setdefault(field, {})[key] = copy.deepcopy(row)
    return patch or None


def _python_launcher_rest(argv):
    """파이썬을 띄우는 명령이면 머리(launcher)를 뗀 나머지 인자 — 아니면 None.
    python·python3·py(-3 등 판 고르기 인자 포함)·`/usr/bin/env python3` 모양을 안다."""
    if not argv:
        return None
    head = os.path.basename(str(argv[0])).lower()
    for ext in (".exe", ".cmd", ".bat"):
        if head.endswith(ext):
            head = head[:-len(ext)]
    rest = [str(a) for a in argv[1:]]
    if head == "env" and rest and os.path.basename(rest[0]).lower().startswith("python"):
        return rest[1:]
    if head == "py":
        return rest[1:] if rest and rest[0].startswith("-") and rest[0][1:2].isdigit() else rest
    if head in ("python", "python3") or (head.startswith("python3.") and head[8:].isdigit()):
        return rest
    return None


class InstalledRunnerRestart(Exception):
    """FP1 설치기(서버가 내려 준 install.py)가 이 작업 폴더 runner/ 에 새 실행기를 설치했고, 이 요청을 보낸 프로세스만 옛 코드다.

    ■ 왜 (2026-10-23): 설치기는 그때 종료 코드 4 와 «다음부터 이 명령으로 실행하세요» 로 멈췄고 사람이 같은 명령을 다시 쳐야
      했다 — 1주 69건·17명(린박스·뇌전구·쇼핑·3D · 윈도우 `py` 런처·공용 폴더). 실행기는 자기를 다시 띄우는 문
      (`_restart_after_update` · FP2 와 같은 한 곳)을 이미 갖고 있다 — 설치기가 표준 출력에 남긴 한 줄(`restart_required`)을
      읽고 같은 단계를 새 실행기로 스스로 다시 띄운다. 상한: 다시 뜬 프로세스(`_REEXEC_FLAG` = 같은 판)는 또 띄우지 않는다."""

    def __init__(self, script, target):
        super().__init__(script)
        self.script, self.target = script, target


def _installer_moved(result):
    """설치기 결과가 «새 실행기 설치됨 · 이 프로세스는 옛 코드» 이고 그 폴더가 정말 그 판이면 `InstalledRunnerRestart` — 아니면 None.

    판정은 설치기의 말만 믿지 않는다: 그 폴더의 식별값을 그 폴더의 runner_files.py 로 다시 잰다(`_runner_identity`). 이미 그 판으로
    다시 뜬 프로세스면 None(고리 없음) — 그때는 설치기의 멈춤 글이 그대로 사람에게 간다."""
    lines = [x for x in (getattr(result, 'stdout', '') or '').strip().splitlines() if x.strip().startswith('{')]
    try:
        info = json.loads(lines[-1]).get('restart_required') if lines else None
    except (ValueError, AttributeError):
        return None
    if not isinstance(info, dict):
        return None
    script, target = info.get('script'), info.get('installed')
    if not (isinstance(script, str) and os.path.isabs(script) and os.path.isfile(script)
            and isinstance(target, str) and len(target) == 12 and os.environ.get(_REEXEC_FLAG) != target):
        return None
    if _runner_identity(os.path.dirname(script))[0] != target:
        return None
    return InstalledRunnerRestart(script, target)


class RunnerPackMismatch(StepError):
    """받은 실행기 팩 바이트가 서버 선언 sha256 과 다르다 — 배포 창(팩을 R2 에 올린 뒤 Worker 전파가 끝나기 전)의 일시 어긋남.

    2026-10-17 실행기 중단 보고 26건·2명(05:5x·08:3x·15:00 — 그날 배포 시각과 겹친다). 예전에는 «같은 명령을 다시 실행하라» 로
    멈췄다 — 그 재실행이 하는 일(서버에 같은 단계를 다시 묻기)을 `_drive_loop` 가 상한 안에서 스스로 한다(`_PACK_MISMATCH_WAITS`)."""


#: 팩 어긋남 뒤 서버에 같은 단계를 다시 묻기까지 기다리는 초 — 배포 전파 실측 8~14초 · 팩 올림→배포 창 약 45초(CLAUDE.md §3).
#: 우리 서버 배포 창이라 외부 서비스 공식 숫자와 무관하다. 합 90초가 지나도 어긋나면 사람에게 말한다(무한 대기 금지).
_PACK_MISMATCH_WAITS = (15, 30, 45)


def _runner_update_restart(c, step, res, payload, source, steps_left):
    """FP2 — 실행기가 스스로 새 판을 설치하고 같은 명령으로 다시 뜬다 (2026-10-05 · 원장 W2-08).

    ■ 왜: 판이 바뀔 때마다 옛 실행기는 «설치 → 같은 단계에서 멈춤 → 사람이 같은 명령을 다시 실행»(FP1)을 거쳤다.
      10-03 하루 646명이 2,804번 갈아탔다. 이 판부터 실행기가 `cow-v3` 를 알리면 서버는 정지 대신 새 팩 항목만 준다.
    ■ 순서 (어디서 끊겨도 다시 실행하면 이어진다)
      ① 현재 단계·payload 를 저장(active) — 새 프로세스가 같은 단계부터 잇는다.
      ② 이 응답의 영수증을 **받기 전에** 소비한다 — 받기가 실패한 실행의 재실행이 이 응답(6시간짜리 열쇠 주소)을
         재생해 영원히 되풀이하지 않게(서버 설치기 FP1 과 같은 판단). 소비 뒤 재실행은 서버에 새로 묻는다.
      ③ 곁 팩(조교 손) → 실행기 팩 순으로 받아 sha256·파일 수 대조 → `install_runner_files`(실행기 팩은 runner_id 대조).
      ④ 같은 인자·같은 파이썬 옵션으로 다시 띄운다 — 이 함수는 설치까지만 하고 «다시 띄울 명령» 을 돌려준다. 계측
         구간(drive)을 닫은 뒤 `main` 이 `_restart_after_update` 로 띄운다: POSIX 는 `os.execv`, 윈도우는 표준입출력을
         물려받은 하위 프로세스의 종료 코드, 진행 기록 모드(`--background`)는 잠금을 놓고 새 프로세스를 띄우는
         기존 길(`_restart_logged_python`).
      ⑤ 새 프로세스에 대상 판을 환경변수로 넘긴다 — 같은 대상 판의 갱신을 또 받으면 루프 대신 멈춘다(명세·팩 어긋남).
    """
    info = res.get('runner_update')
    item = info.get('item') if isinstance(info, dict) else None
    target = info.get('to') if isinstance(info, dict) else None
    if (not isinstance(item, dict) or not isinstance(target, str) or len(target) != 12
            or any(ch not in '0123456789abcdef' for ch in target)
            or not isinstance(item.get('url'), str) or not isinstance(item.get('sha256'), str)):
        raise StepError('서버의 실행기 갱신 응답 모양이 잘못됐습니다. 아무것도 바꾸지 않았습니다 — 관리자에게 알려 주세요.')
    if os.environ.get(_REEXEC_FLAG) == target:
        # 무엇을 알렸고 그 폴더가 무엇인지 사실을 싣는다(10-23 신고엔 판 이름뿐이라 «옛 폴더 모듈을 읽음» 과 «명세·팩 어긋남» 을 못 갈랐다).
        import volcano_run                                           # noqa: PLC0415
        mine = os.path.dirname(os.path.abspath(volcano_run.__file__))
        raise StepError('새 실행기(' + target + ')로 다시 시작했는데도 서버가 같은 갱신을 또 요구합니다 — 서버 명세와 배급 팩이 '
                        '어긋난 것입니다. 같은 명령을 되풀이하지 말고 관리자에게 알려 주세요(작업 상태는 저장돼 있습니다). '
                        '[알린 판 %s · 모듈 폴더 %s · 그 폴더 식별값 %s · 실행 파일 폴더 %s]'
                        % (volcano_run.RUNNER_ID, mine, _runner_identity(mine)[0] or '?', _HERE))
    wd = payload.get('workdir')
    if not (isinstance(wd, str) and os.path.isabs(wd)):
        raise StepError('실행기를 갱신할 작업 폴더(payload.workdir 절대경로)가 payload 에 없습니다. 아무것도 바꾸지 않았습니다.')
    # 10-23 신고(longform_deliver · 'D:/…' 절대경로가 실려 있었다): 폴더 판정이 _checkpoint 와 다른 자(머리 없는 isdir)였고,
    # 안 보일 때 «절대경로를 확인하지 못했다» 한 줄뿐이라 «빠진 드라이브» 와 «값 없음» 이 갈리지 않았다 → 같은 자(_review_receipt_io_path)
    # 로 보고, 안 보이면 #224 의 사실 한 줄(_vanished_note — 처음 안 보이는 자리)을 싣는다.
    from volcano_run import _review_receipt_io_path                 # noqa: PLC0415
    if not os.path.isdir(_review_receipt_io_path(wd)):
        raise StepError((_vanished_note(wd) or ('작업 폴더 ' + wd + ' 가 폴더로 보이지 않습니다. '))
                        + '실행기를 갱신하지 않았습니다(아무것도 바꾸지 않음).')
    _checkpoint(c, step, payload, source, 'active',
                response_consumed=getattr(c, '_receipt_returned', None) is not None)
    if getattr(c, '_receipt_returned', None) is not None:
        c.acknowledge_response()
    runner_dir = os.path.join(wd, 'runner')
    packs = [p for p in (info.get('packs') or []) if isinstance(p, dict)] + [item]
    changed = []
    with tempfile.TemporaryDirectory(prefix='volcano-runner-update-') as temp:
        for index, pack in enumerate(packs):
            url = str(pack.get('url') or '')
            if url.startswith('/'):
                url = c.url.rstrip('/') + url
            out = os.path.join(temp, 'pack%d.tar.gz' % index)
            with download_seen() as seen:
                download(url, out, headers=({'Authorization': 'Bearer ' + c.token} if getattr(c, 'token', None) else None),
                         resume=True)
            with open(out, 'rb') as body:
                got = hashlib.sha256(body.read()).hexdigest()
            if got != pack.get('sha256'):
                # 신고 #311(10-17~18 · 7명 · 같은 사람이 몇 시간 동안 되풀이): 키가 sha 주소라 저장소 바이트는 선언과 같아야 하는데
                # 어긋났다 — 어느 팩·몇 바이트·받은 지문인지가 신고에 없어 원인을 못 가렸다 → 사실을 싣는다(판정은 바꾸지 않는다).
                raise RunnerPackMismatch('받은 실행기 팩의 sha256 이 선언과 다릅니다(배포 중 어긋남일 수 있습니다). 바꾸지 않았습니다 — '
                                         '같은 명령을 다시 실행하면 서버가 새 주소를 줍니다. [팩 %s/%s · 선언 %s · 받음 %s · %d바이트]'
                                         % (pack.get('preset') or '?', pack.get('pack') or '?', str(pack.get('sha256'))[:12], got[:12],
                                            os.path.getsize(out))
                                         + '\n' + asset_mismatch_facts(seen, os.path.getsize(out), got, fetcher=download))
            with tarfile.open(out) as archive:
                count = sum(1 for m in archive.getmembers() if m.isfile())
                if pack.get('n_files') is not None and count != pack.get('n_files'):
                    raise StepError('받은 실행기 팩의 파일 수(%d)가 선언(%s)과 다릅니다. 바꾸지 않았습니다.' % (count, pack.get('n_files')))
                changed += install_runner_files(archive, runner_dir,
                                                expect_id=target if pack is item else None)
    _progress('  ★ 실행기를 새 판(' + target + ')으로 설치했습니다(' + str(len(changed)) + '개 파일) — 같은 단계(' + step
              + ')부터 새 실행기로 다시 시작합니다.', flush=True)
    script = os.path.join(runner_dir, 'volcano_drive.py')
    plan = _relaunch_plan(c, wd, script, target, steps_left)
    if plan is None:
        # 함수로 부른 실행기(모델이 짠 스크립트 등)는 자기를 다시 띄울 명령을 모른다 — 같은 명령을 다시 실행하게 멈춘다.
        why = ('새 실행기(' + target + ')를 이 작업 폴더의 runner/ 에 설치했습니다. 지금 프로세스는 옛 코드라 여기서 멈춥니다. '
               '같은 명령을 다시 실행하면 새 실행기가 같은 단계부터 잇습니다: ' + str(info.get('restart_command') or ''))
        return {'step': step, 'payload': payload, 'source': source,
                'res': {'status': 'need_input', 'done': False, 'next_step': step, 'message': why,
                        'author': {'for': step, 'keys': ['같은 명령 다시 실행'], 'why': why}}}
    # ★여기서 다시 띄우지 않는다(2026-10-05 검토 2회차). 이 함수는 `drive()` 의 계측 구간(span 'drive') 안이다 —
    #   POSIX execv 는 그 구간을 «끝나지 않음» 으로 영원히 남겨 이 작업 폴더의 실행 기록을 불완전하게 만들고, 윈도우
    #   하위 프로세스는 자식의 시간 전체를 부모 구간에 겹쳐 센다. 설치까지만 하고 «다시 띄울 명령» 을 돌려준다 —
    #   구간을 닫은 뒤 `main` 이 `_restart_after_update` 로 띄운다.
    return {'step': step, 'payload': payload, 'source': source, 'restart': plan,
            'res': {'status': 'runner_restart', 'done': False, 'next_step': step}}


def _relaunch_plan(c, wd, script, target, steps_left):
    """새 실행기(`script`)를 같은 인자로 다시 띄울 계획 — FP2 자동 갱신과 FP1 설치기 뒤 다시 띄우기(InstalledRunnerRestart)가 쓰는 한 자리.
    함수로 부른 실행기(자기를 다시 띄울 명령을 모름)거나 그 파일이 없으면 None."""
    launch = getattr(c, '_runner_restart', None)
    if not isinstance(launch, dict) or not os.path.isfile(script):
        return None
    arguments = ['--workdir', wd]
    if (getattr(c, 'tool', None) or Client.tool) != Client.tool:
        arguments += ['--tool', c.tool]
    arguments += ['--max-steps', str(steps_left)]
    if launch.get('key_file'):
        arguments += ['--key-file', os.path.abspath(launch['key_file'])]
    return {'script': script, 'arguments': arguments, 'target': target}


def _interpreter_flags():
    """지금 파이썬의 실행 옵션(-X utf8 · -B · -E · -W … ) — 다시 띄운 실행기도 같은 옵션으로 돈다.

    예전 재시작 argv 는 `[python, script, …]` 라 학생이 붙인 `-X utf8`(윈도우 콘솔 한글) 같은 옵션이 사라졌다
    (검토 2회차). 표준 라이브러리 `subprocess` 가 multiprocessing 자식에게 쓰는 그 함수다."""
    helper = getattr(subprocess, '_args_from_interpreter_flags', None)
    try:
        return list(helper()) if callable(helper) else []
    except Exception as error:  # noqa: BLE001 — 옵션을 못 읽어도 재시작은 같은 파이썬으로 한다(알린다)
        _progress('  [갱신] 지금 파이썬의 실행 옵션을 읽지 못해 옵션 없이 다시 띄웁니다: ' + type(error).__name__, flush=True)
        return []


def _run_workdir_runner(wd, arguments):
    """작업 폴더 밖 사본으로 띄웠는데 그 작업 폴더의 runner/ 에 **다른 판**이 설치돼 있으면 그 실행기로 같은 인자를 넘긴다.
    돌려주는 값: 넘겼으면 그 종료 코드(윈도우 · POSIX 는 execv 로 돌아오지 않는다) · 아니면 None(이 실행기가 그대로 돈다).

    ■ 왜 (2026-10-22 뇌전구 신고 전수 · diag): 갱신(FP2)은 늘 «작업 폴더의 runner/» 에 설치하고 그 자리에서 다시 뜬다
      (`_self_update_dir` ① — 공용 사본을 제자리에서 바꾸지 않는다). 그런데 다음 호출을 다시 작업 폴더 **밖** 공용 사본으로 띄우는
      회원이 있어, 그 사본은 영영 옛 판이라 **단계마다** 같은 갱신을 받았다 — 한 사람이 작업 폴더 33곳에서 107번(b6a65ba4a88a) ·
      같은 낯선 판(d12fc3463f09)이 작업 폴더 두 곳에서 32번 · 갱신마다 받기·설치·재시작 15~30초. 같은 판 아이디가 여러 작업
      폴더에 걸쳐 그대로인 것은 작업 폴더 밖 한 사본이라는 뜻이다(작업 폴더 runner/ 였다면 첫 갱신으로 바뀌었다).
    ■ 그래서 작업 폴더의 runner/ 가 이 작업의 실행기다(갱신이 설치하는 바로 그 자리) — 거기 다른 판이 있으면 그 판으로 돈다.
      그 판이 서버 판과 다르면 서버가 작업 폴더 runner/ 에 한 번 갱신하고(지금과 같은 길), 그 뒤로는 같은 갱신이 되풀이되지 않는다.
    · 같은 실체(작업 폴더 runner/ 에서 띄움)·없는 runner/·판을 못 잼·같은 판이면 넘기지 않는다. 넘겨받은 프로세스는 다시 넘기지
      않는다(_REEXEC_FLAG · 고리 없음). 띄우는 문은 갱신 재시작 한 곳(_restart_after_update)이다."""
    if os.environ.get(_REEXEC_FLAG):
        return None                     # 갱신·넘김으로 다시 뜬 프로세스 — 또 넘기지 않는다(고리 없음)
    from volcano_run import RUNNER_ID, _self_update_dir              # noqa: PLC0415
    here = os.path.dirname(os.path.abspath(__file__))
    target = _self_update_dir(wd)
    script = os.path.join(target, 'volcano_drive.py')
    if not os.path.isfile(script):
        return None
    try:
        if os.path.samefile(here, target):
            return None
    except OSError:
        return None
    target_id, _why = _runner_identity(target)
    if target_id is None or target_id == RUNNER_ID:
        return None
    _progress(f"  [실행기] 작업 폴더 밖 실행기({RUNNER_ID} · {here})로 띄웠습니다 — 이 작업 폴더의 실행기({target_id})로 넘깁니다. "
              f"다음부터는 {script} 로 실행하세요.", flush=True)
    # 띄우는 문은 갱신 재시작 한 곳(_restart_after_update — 윈도우 표준입출력 계약 · 다시 뜬 프로세스 표식)을 그대로 쓴다.
    return _restart_after_update({'script': script, 'arguments': list(arguments), 'target': target_id})


def _restart_after_update(restart):
    """FP2 ④ — 설치를 마친 뒤(계측 구간을 닫은 뒤) 새 실행기를 같은 인자로 띄운다.

    POSIX 는 `os.execv`(돌아오지 않는다). 윈도우의 `os.execv` 는 «새 프로세스 + 자신 종료» 라 호출한 셸이 끝난 줄
    알므로 표준입출력을 물려받은 하위 프로세스를 띄우고 그 종료 코드를 돌려준다. 진행 기록 모드(`--background`)는
    잠금을 놓고 새 프로세스를 띄우는 기존 길(`_restart_logged_python`). 새 프로세스에 대상 판을 환경변수로 넘긴다
    (같은 대상 판의 갱신을 또 받으면 루프 대신 멈춘다 — `_runner_update_restart` ⑤)."""
    flags = _interpreter_flags()
    os.environ[_REEXEC_FLAG] = restart['target']
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except (OSError, ValueError):
        pass
    if globals().get('_LOGGED_STATE'):
        # 새 실행기는 <작업 폴더>/runner 에 설치됐다 — 새 프로세스가 그 폴더의 모듈을 읽게 한다. 옛 프로세스의 폴더
        # (`__file__`)는 연결된 runner/(POSIX 는 원본 폴더로 풀린다)나 작업 폴더 밖 실행기면 새 판이 없는 곳이다.
        _restart_logged_python(sys.executable, restart['script'], restart['arguments'], flags=flags,
                               module_dir=os.path.dirname(restart['script']))
    argv = [sys.executable, *flags, restart['script'], *restart['arguments']]
    # 직접 실행이 쥔 작업 폴더 잠금을 놓고 새 판을 띄운다 — 쥔 채 띄우면 새 판이 «다른 실행기가 돌고 있다» 로 멈춘다.
    _release_direct_run_lock()
    if os.name == 'nt':
        # ★여기만 일부러 `_spawn` 을 안 지난다(tests/test_runner_win.py 가 이 한 줄의 모양을 못박는다). 재시작 자식은
        #   캡처 파이프가 아니라 부모의 표준입출력을 이어 쓰는 «같은 명령» 이다 — `_spawn` 은 윈도우에서 UTF-8 환경을
        #   강제하므로(캡처 전용 계약) 그 길로 띄우면 다시 뜬 실행기만 기본 인코딩이 바뀐다. 도구 문(`.cmd` 감싸기)도
        #   sys.executable(절대 경로)엔 할 일이 없다. 환경은 그대로, 종료 코드는 그대로 돌려준다.
        return subprocess.call(argv)
    os.execv(sys.executable, argv)


def _drive_loop(c, at, payload, headers, source, max_steps):
    # ★완주에 걸린 시간을 재려면 시작 시각이 필요하다. 루프 앞에서 한 번만 잡는다.
    _t0 = time.time()
    step = at["step"]
    environment_recovery_attempted = False
    source_revisions_seen = set()
    _pack_mismatch_tries = 0
    for _i in range(max_steps):
        at["step"] = step
        _progress(f"[{step}]")
        # 이행 wrapper는 다음 호출 전에 완료한 계측값을 보존한다. 저장 실패를
        # 삼키면 다시 시작할 때 모델을 재호출하므로 작업보다 먼저 멈춘다.
        editing = getattr(c, '_runner_input_step', None) == step
        _checkpoint(c, step, payload, source, 'waiting' if editing else 'active')
        # ★소재는 `start` 가 읽는다. **첫 걸음이 무엇이든 소진하면 안 된다** —
        #   예전에는 무조건 첫 호출에만 싣고 `source = None` 으로 지웠다. 주석은
        #   "source 는 start 에서만 쓴다" 인데 코드는 **첫 단계가 무엇이든** 지웠다.
        #   그래서 `drive(c, "setup", source=…)` 로 시작하면 `setup` 이 읽지도 않는
        #   소재를 받아 먹고, 정작 `start` 에는 `source=None` 이 가서 반려됐다
        #   (2026-08-16 실측: 오늘 그 경로로 3명이 막혔다).
        try:
            with runtime_metrics.span('mcp', step):
                res = c.step(step, payload=payload or None,
                             source=(source if step == "start" else None))
        except RejectedError as error:
            contract = getattr(error, 'contract', None)
            if isinstance(contract, dict):
                _carry_into(contract, payload)
            # ★반려 계약이 다른 단계를 가리키면(`next_step` — 3D쇼츠 `_tool_error(…, next_step=)` 등) 그 단계를 저장한다
            #   (2026-10-05 최종 검토). 예전에는 반려된 단계를 저장해 평소 재개가 같은 단계를 되풀이했다.
            redirect = contract.get('next_step') if isinstance(contract, dict) else None
            after = redirect if isinstance(redirect, str) and redirect else step
            # 반려 판은 계약이 없어도 언제나 next_payload.json 으로 게시한다(상태보다 먼저 — §_checkpoint) — 반려 판의 그
            # 파일이 사람이 고칠 자리이고, 평소 재개가 그 파일을 보낸다(§main · 2026-10-05 B 최종 검토 3회차). 예전에는
            # 계약 없는 반려를 main 의 정지 안내만 게시해, 함수로 부른 실행기·중간에 끊긴 실행에서는 낡은 파일이 남았다.
            _checkpoint(c, after, payload, source, 'waiting' if editing else 'active',
                        publish_payload=True, rejected=True)
            # 이 실행이 방금 보낸 판을 반려 판으로 저장했다 — 정지 안내가 next_payload.json 을 이 판으로 게시해도 된다.
            c._runner_rejection_saved = True
            # 알림의 기준(서버 원본)도 이 반려가 게시한 판으로 바꾼다 — 낡은 정지 원본이면 «빼라고 한 칸» 을 «빠졌다» 고
            # 잘못 알린다. 계약이 없는 반려면 원본이 없으므로 지운다(_save_server_next_payload 가 next_payload 없음 → 삭제).
            _save_server_next_payload(payload.get('workdir'), after,
                                      {'next_payload': dict(payload),
                                       'payload_discard': contract.get('payload_discard') or []}
                                      if isinstance(contract, dict) else {})
            raise
        # ★★서버가 **같은 `start` 를 다시** 부르라고 하면 그때도 소재를 실어야 한다
        #   (2026-09-04). 곁 도구(`volcano_ref`)의 `start` 는 소재 폴더를 프로브로
        #   확인하고 **자기를 다시** 부르게 하는 모양이라, 소진해 버리면 두 번째 호출이
        #   «소재가 없다» 로 반려된다(실측: 재진입 호출에 source 가 안 실렸다).
        #   ★영상 체인은 `start` 를 되풀이하지 않으므로 예전과 동작이 같다 — 그리고
        #     되풀이하더라도 같은 소재를 다시 싣는 것은 첫 호출과 같은 값이다.
        if res.get("message"):
            _progress(f"  {res['message']}")
        for w in res.get("warnings") or []:
            _progress(f"  ⚠ {w}")
        if res.get("status") == "runner_update":
            # ★FP2 — 서버가 새 실행기를 준다. 저장·설치·재시작을 여기서 끝낸다(§_runner_update_restart).
            #   재시작에 성공하면 돌아오지 않는다. 함수로 부른 실행기면 같은 명령을 다시 실행하라고 멈춘다.
            try:
                return _runner_update_restart(c, step, res, payload, source, max(1, max_steps - _i))
            except RunnerPackMismatch:
                # 배포 창의 일시 어긋남 — 상한 안에서 기다렸다 같은 단계를 서버에 다시 묻는다(영수증은 받기 전에 소비했다 · ②).
                if _pack_mismatch_tries >= len(_PACK_MISMATCH_WAITS):
                    raise
                _wait = _PACK_MISMATCH_WAITS[_pack_mismatch_tries]
                _pack_mismatch_tries += 1
                _progress(f"  ⚠ 받은 실행기 팩이 서버 선언과 다릅니다(배포 중일 수 있음) — {_wait}초 뒤 서버에 다시 묻습니다"
                          f"({_pack_mismatch_tries}/{len(_PACK_MISMATCH_WAITS)}).", flush=True)
                time.sleep(_wait)
                continue
        if res.get("status") == "need_input":
            _mw = _machine_work(res)
            if _mw:
                # ★삼키지 않는다 — 왜 실행기가 아무것도 안 하고 섰는지 말한다(§_machine_work)
                _progress("  ⚠ 이 응답은 status='need_input'(사람 차례) 인데 **기계가 할 일**이 "
                      f"실려 있다: {' · '.join(_mw)}.\n"
                      "     실행기는 need_input 에서 실행하지 않고 멈춘다 — 그 일을 실행기가 "
                      "하게 하려면 서버가 그 단계를 status='execute' 로 주고 "
                      "next_step 으로 자기를 다시 부르게 해야 한다. (지금은 사람이 한다)")
            _progress("  ⏸ 여기서 멈춘다 — 사람(모델)이 채워야 한다:")
            for t in _then_lines(res):
                _progress(f"     · {t}")
            # ★멈추기 전에 carry 를 나른다 — 사람이 채우는 것과 서버가 돌려준 것은 다르다
            return _input_wait(c, step, res, payload, source)
        if editing:
            c._runner_input_step = None
            _checkpoint(c, step, payload, source)
        # A revision must remove invalid measurements from accumulated state,
        # even though execute returns only newly produced/carry values.
        for key in res.get('payload_discard') or []:
            payload.pop(key, None)
        try:
            with runtime_metrics.stage(step):
                payload.update(execute(res, headers, c))
            # ★답한 검수 요청을 여기서 빼지 않는다(2026-10-05 검토 2회차) — 영상·음성 요청은 서버가 «이미 받은 자료의 답»
            #   임을 그 요청 기록으로 확인한다(`volcano_review_policy._settled`·`new_av_work`). 빼면 재개 때 같은 일이
            #   «새 영상·음성 일» 로 보여 검수 경로 선택에서 막힌다. 그 밖의 답한 요청은 서버 `attach_response` 가 뺀다.
        except InstalledRunnerRestart as moved:
            # FP1 설치기가 새 실행기를 설치했다 — 같은 단계를 새 실행기로 다시 띄운다(사람 재실행 없음 · 다시 뜬 프로세스는 또 안 띄움).
            plan = _relaunch_plan(c, payload.get('workdir') or '', moved.script, moved.target, max(1, max_steps - _i))
            if plan is None or not os.path.isabs(str(payload.get('workdir') or '')):
                raise StepError('새 실행기(' + moved.target + ')를 ' + os.path.dirname(moved.script) + ' 에 설치했습니다. 지금 '
                                '프로세스는 옛 코드라 여기서 멈춥니다 — 이 명령으로 실행하면 같은 단계부터 잇습니다: '
                                + subprocess.list2cmdline([sys.executable, moved.script, '--workdir',
                                                           str(payload.get('workdir') or '')])) from None
            _checkpoint(c, step, payload, source, 'active')
            _progress('  ★ 새 실행기(' + moved.target + ')가 설치됐습니다 — 같은 단계(' + step + ')부터 새 실행기로 다시 시작합니다.',
                      flush=True)
            return {'step': step, 'payload': payload, 'source': source, 'restart': plan,
                    'res': {'status': 'runner_restart', 'done': False, 'next_step': step}}
        except StepBack as back:
            # 처방이 «앞 단계 다시» 하나뿐인 멈춤 — 사람에게 시키지 않고 실행기가 그 단계로 돌아간다(신고 #32 자막 → subtitle ·
            #   빠진 그림 칸 → images). 같은 단계·같은 표지에 한 번만(상한) — 다시 만든 뒤에도 또 같으면 사람에게 말한다.
            seen = getattr(c, '_stepped_back', set())
            mark = (back.back_to, _frozen(back.mark))
            if mark in seen:
                raise
            c._stepped_back = seen | {mark}
            for key, values in (getattr(back, 'payload_add', None) or {}).items():
                # 돌아갈 단계가 읽을 목록 칸(사진 실사 검수 → images 의 flow_redo) — 이미 있는 값과 합친다(같은 칸 두 번 없음).
                had = payload.get(key) if isinstance(payload.get(key), list) else []
                payload[key] = sorted({int(x) for x in [*had, *values]})
            _progress(f'  ↻ [{step}] ' + str(back).split('\n')[0] + f' → {back.back_to} 단계로 돌아가 다시 만듭니다', flush=True)
            step = back.back_to
            continue
        except CustomMediaChanged as changed:
            # 회원이 원본 그림을 바꿨다 — 그 칸을 같은 path 로 customize 에 다시 보내면 서버가 로컬 확인 뒤 그 칸의 변환·측정만
            # 다시 만든다(정지 글이 사람에게 시키던 일 그대로). 같은 원본·같은 바이트에 한 번만(상한) — 두 번째면 사람에게 말한다.
            patch, seen = _custom_media_repatch(payload, changed.source), getattr(c, '_custom_media_repatched', set())
            mark = (changed.source, _file_sha_or_none(changed.source))
            if not patch or mark in seen:
                raise
            c._custom_media_repatched = seen | {mark}
            _progress('  ↻ [사용자 소재] 원본 그림이 바뀌어 그 칸을 다시 확인합니다(customize · 같은 path): ' + str(changed.source),
                      flush=True)
            payload['customization_patch'] = patch
            step = 'customize'
            continue
        except ASRSetupRequired as setup:
            guidance = res.get('asr_setup')
            if not isinstance(guidance, dict) or guidance.get('status') != 'need_input':
                raise  # Older server: preserve the explicit exception instead of inventing policy.
            _preserve_execution_failure(c, step, res, payload, source, setup)
            waiting = dict(guidance, next_step=step)
            _progress('  ⏸ ' + waiting.get('message', str(setup)), flush=True)
            return _input_wait(c, step, waiting, payload, source, executed=True)
        except ClientReviewPending as pending:
            _preserve_execution_failure(c, step, res, payload, source, pending)
            requests = getattr(pending, 'requests', None) or [pending.request]
            payload['review_requests'] = requests
            field = _review_reply_field(payload)
            _progress('  ⏸ 현재 AI가 보존된 검수 자료를 읽고 답할 차례입니다. 유료 검수를 자동 호출하지 않았습니다.')
            return {'step':step, 'payload':payload, 'source':source,
                    'res':{'status':'need_input', 'done':False, 'next_step':step,
                        'message':'현재 연결된 AI가 review_requests의 실제 자료를 검토하고 '
                                  'reply_schema대로 ' + field + '에 답을 넣어 같은 단계를 재개하세요. '
                                  '자료를 읽지 못하면 통과 답을 만들지 마세요. 사용자 승인 질문은 필요하지 않습니다.',
                        'review_requests':requests,
                        'review_reply_field':field,
                        'author':{'for':step, 'keys':[field],
                                  'why':'이미 보존한 실제 검수 자료에 대한 현재 AI의 답이 필요합니다.'}}}
        except TranscriptionPending as pending:
            _preserve_execution_failure(c, step, res, payload, source, pending)
            _progress("  ⏸ " + str(pending), flush=True)
            return {"step": step, "payload": payload, "source": source,
                    "res": {"status": "pending", "done": False, "next_step": step,
                            "message": str(pending), "retry_after": pending.retry_after}}
        except Exception as error:
            try:
                recovery = getattr(error, 'execution_recovery', None)
                partial = getattr(error, 'execution_partial', None)
                if isinstance(recovery, dict) or isinstance(partial, dict):
                    _preserve_execution_failure(c, step, res, payload, source, error)
                    if getattr(error, 'contract_error', None):
                        raise  # Invalid saved replies cannot authorize automatic work.
                    if (getattr(error, 'code', None) == 'local_source_changed'
                            and getattr(error, 'execution_next_step', None) in ('render_plan','redub_master','shop_cuts','stitch_blocks','person_frame')
                            and isinstance(recovery,dict)
                            and isinstance(recovery.get('local_source_versions'),dict)):
                        revision = json.dumps(recovery['local_source_versions'], sort_keys=True)
                        if revision in source_revisions_seen:
                            raise  # A repeated unchanged recovery is not progress.
                        source_revisions_seen.add(revision)
                        step = error.execution_next_step
                        _checkpoint(c, step, payload, source)
                        _progress('  [원본 변경] 기존 음성·접수 기록을 보존하고 새 원본의 로컬 계획을 준비합니다.')
                        continue
                    # ★굽기 증명이 작업 폴더의 계획 기록보다 옛것(local_render_plan._proof_stale · 2026-10-22) — 옛 결과를 payload 에서 뺐으니
                    #   (recovery) render_plan 로컬 계획부터 한 번 다시 간다. 같은 옛 증명이 또 오면 진전이 아니므로 멈춘다.
                    #   검출 환경이 바뀐 증명(local_render_plan._runtime_changed)도 같은 길이다 — render_plan 이 바뀐 컷만 지금 환경에서 다시 고른다.
                    if ((getattr(error, 'code', None) == 'local_plan_proof_stale'
                             and getattr(error, 'execution_next_step', None) == 'render_plan'
                             or getattr(error, 'code', None) == 'local_plan_runtime_changed'
                             and getattr(error, 'execution_next_step', None) in ('render_plan', 'shop_cuts', 'redub_master'))
                            and isinstance(recovery, dict) and recovery.get('local_render_plan_result', 0) is None):
                        revision = error.code + ':' + str(getattr(error, 'stale_proof', ''))
                        if revision in source_revisions_seen:
                            raise
                        source_revisions_seen.add(revision)
                        step = error.execution_next_step
                        _checkpoint(c, step, payload, source)
                        _progress('  [계획 기록] ' + str(error))
                        continue
                    if (getattr(error, 'code', None) == 'longform_source_changed'
                            and getattr(error, 'execution_next_step', None) == 'longform_seed'
                            and isinstance(recovery,dict)
                            and isinstance(recovery.get('longform_project'),dict)):
                        revision = 'longform:'+hashlib.sha256(json.dumps(recovery['longform_project'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                        if revision in source_revisions_seen:raise
                        source_revisions_seen.add(revision)
                        step = 'longform_seed'
                        _checkpoint(c,step,payload,source)
                        _progress('  [원본 변경] 기존 음성·검수 기록을 보존하고 교체 소재의 피사체 검수를 연결합니다.')
                        continue
                    input_recovery = res.get('input_check_recovery') or {}
                    input_target = input_recovery.get('next_step')
                    if (getattr(error, 'input_check_failure', False)
                            and isinstance(input_target, str) and input_target):
                        _progress('  [입력 변경] 저장된 음성은 보존하고 현재 파일의 측정부터 갱신합니다.')
                        step = input_target
                        _checkpoint(c, step, payload, source)
                        continue
                    audio_recovery = res.get('audio_measurement_recovery') or {}
                    target = audio_recovery.get('next_step')
                    if (getattr(error, 'audio_duration_failure', False)
                            and isinstance(target, str) and target and target != step):
                        _progress('  [음성 길이] 완료한 측정은 보존했습니다. 현재 원시 음성으로 로컬 복구합니다.')
                        step = target
                        _checkpoint(c, step, payload, source)
                        continue
                    if (not environment_recovery_attempted and isinstance(recovery, dict)
                            and recovery.get('execution_environment_error')):
                        environment_recovery_attempted = True
                        _progress('  [실행 환경] 모듈 누락을 기록했습니다. 같은 단계의 환경부터 다시 확인합니다.')
                        continue
                raise
            except Exception:
                # ★받은 응답을 이 PC 에서 실행하다 멈췄다 — 그 응답을 소비(ACK)해 다음 실행이 서버에 **새로** 묻게 한다
                #   (2026-10-21 · 인물형 롱폼 신고: 서버가 그림 묶음 기한을 고쳐 배포한 뒤에도 한 사람의 작업 폴더 7개가 서버에
                #   한 번도 묻지 않고 디스크의 옛 답(옛 팩 지문 · 6시간짜리 받기 열쇠)을 되풀이해 같은 «timeout_s 가 짧다» 로
                #   멈췄다 · 군림보 render_mix 40회도 같은 재생). 영수증은 «응답을 잃지 않는다»(응답을 받기 전·받고 상태를 적기
                #   전의 끊김)를 지키는 장치다 — 받은 응답을 실행해 실패한 것을 사람이 다시 돌리면 그 사이 고쳐진 서버의 답을
                #   받아야 한다. 사람 차례 멈춤(10-17)·실행기 갱신(FP2)과 같은 순서: 같은 단계를 «진행» 으로 적은 뒤 소비.
                #   유료 일은 실행기 쪽 접수 기록(그림·음성·플로우 장부)이 막는다 — 서버에 다시 묻는 것은 계획을 다시 받는 것이다.
                _release_failed_response(c, step, payload, source)
                raise

        if step == "start" and str(res.get("next_step") or "") != "start":
            source = None             # 실행 완료 전의 대기는 같은 소재로 재개해야 한다.
        #   ── ★★곁 도구는 `then_call_with` 가 **유일한 계약**이다 (2026-09-04) ──────────
        #     이 루프는 payload 를 **누적**하고 `then_call_with.payload` 를 **한 번도 안 읽었다.**
        #     `volcano_video` 는 서버가 `next_payload` 를 조립해 주니 괜찮은데, 곁 도구
        #     (`volcano_ref`·`volcano_cardnews`)는 그 기전을 **한 줄도 안 탄다**
        #     (`volcano_tools:16875 if is_side: return res`). 그래서 서버가 «다음엔 이걸로
        #     부르라» 고 적어 준 칸(`ids`·`src_dir` …)이 **영원히 안 흘렀다** — 로컬 완주에서
        #     `frames` 가 «payload.src_dir 은 절대경로여야 합니다 — 받은 것: ''» 로 멎었다.
        #   ★자리표시자(`"<ref_probe 결과 그대로>"`)는 **건너뛴다** — 그것은 «실행기가 채울 칸»
        #     이라는 표시이고, 그대로 넣으면 글자가 값이 된다(§유령 값). `measure` 가 채운다.
        #   ★`volcano_video` 경로는 **손대지 않는다**(기본 도구일 때 이 갈래를 안 탄다) —
        #     수강생 480명 요청이 한 글자도 안 바뀌어야 한다.
        payload = _relay_side_payload(c, res, payload, step)
        # ★기계 일을 **먼저 다 하고** 멈춘다. 앞에서 멈추면 이미 지시받은 작업(=돈이
        #   나가는 이미지 생성·TTS)을 버리게 되고, 다시 하면 두 번 나간다.
        au = res.get("author")
        if au and au.get("keys"):
            _progress(f"  ⏸ 여기서 멈춘다 — '{au.get('for')}' 단계가 사람 손을 기다린다:")
            _progress(f"     · 없는 값: {', '.join(au['keys'])}")
            _progress(f"     · {au.get('why') or ''}")
            for t in _then_lines(res):
                _progress(f"     · {t}")
            return _input_wait(c, step, res, payload, source, executed=True)
        # ★★실행기가 이 걸음에서 **자기를 갱신했으면** 다음 단계는 새 코드가 돈다 (2026-09-02).
        #   `importlib.reload` 는 같은 모듈 객체 안의 이름을 바꾸므로 여기서 부르는
        #   `_drive_loop` 는 이미 **새 함수**다. 남은 걸음 수를 넘겨 이어간다.
        if getattr(c, "updated", False):
            c.updated = False
            _nx = res.get("next_step")
            if _nx and not str(_nx).startswith("("):
                import volcano_run as _vr  # noqa: PLC0415
                # ★같은 객체를 **새 클래스로** 갈아끼운다 — 주소·토큰·회수 등 상태는 그대로다.
                #   (수강생이 Client 를 상속했으면 그 클래스는 두고 옛 step 으로 간다 —
                #    서버 계약은 같으므로 돈다.)
                if type(c).__name__ == "Client" and type(c) is not _vr.Client:
                    try:
                        c.__class__ = _vr.Client
                    except TypeError:
                        pass
                _progress("  ↻ 새 실행기 코드로 다음 단계를 이어갑니다", flush=True)
                if getattr(c, '_receipt_returned', None) is not None:
                    _checkpoint(c, _nx, payload, source, response_consumed=True)
                    c.acknowledge_response()
                at["step"] = _nx
                return _drive_loop(c, at, payload, headers, source, max(0, max_steps - _i - 1))
        nxt = res.get("next_step")
        # ★서버는 끝을 `next_step: None` + `done: True` 로 말한다. 옛 서버는 `"(완료)"`
        #   처럼 **괄호 낱말**을 넣었다 — 그것도 그대로 받는다(하위호환).
        #   ★그 괄호 낱말이 사고를 냈다: 모델 클라가 그것을 **단계 이름으로 불렀다**
        #     (`알 수 없는 step: (완료)` 7건·4명). 구동기는 안 불렀지만 사람은 부른다.
        if not nxt or nxt.startswith("("):
            _progress("  ✅ 끝 — " + str(res.get("done_note") or nxt or "더 부를 단계가 없다"))
            # ★★**끝까지 갔다는 것을 서버에 알린다** (2026-08-22).
            #   실패만 알리고 성공은 안 알려서, 서버가 「해낸 사람」을 0명분도
            #   모르고 있었다(§`_report_done`).
            _report_done(c, step, res, _t0)
            return {"step": step, "res": res, "payload": payload, "source": source}
        if getattr(c, '_receipt_returned', None) is not None:
            _checkpoint(c, nxt, payload, source, response_consumed=True)
            c.acknowledge_response()
        step = nxt
    # The caller's budget is an expected pause. drive persists this exact next
    # stage as active; main emits the existing resume command and exit 3.
    return {'step':step,'payload':payload,'source':source,
            'res':{'status':'pending','reason':'step_limit','done':False,'next_step':step,
                   'message':f'단계 상한(max_steps={max_steps})에 따라 멈췄습니다. '
                             '완료한 작업과 측정값을 보존했으며 다음 단계부터 재개합니다.'}}


if __name__ == "__main__":
    # self_update reloads volcano_drive. Run the loop in that same module,
    # otherwise __main__ retains old exception classes and drops new contracts.
    import volcano_drive as _driver
    sys.exit(_driver.main())
