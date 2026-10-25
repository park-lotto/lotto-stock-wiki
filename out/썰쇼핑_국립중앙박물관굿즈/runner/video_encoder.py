"""Video encoder choice for server encode slots — one place per PC (2026-10-19).

The server sends one argv element `@VENC@{json}` (src/volcano_venc.py) carrying the
CPU arguments it used to hard-code, GPU alternatives in owner order (nvenc, amf, qsv,
videotoolbox, then CPU) and a one-second probe template.  This module:

* picks the first alternative whose probe encode succeeds on this PC, once, and
  remembers it in ~/.volcano/video_encoder.json keyed by the ffmpeg binary
  (resolved path, size, mtime, `-version` line) and the GPU driver string;
* expands the slot into that alternative's arguments (the runner never invents
  encoder arguments — they all come from the server);
* gives callers at most two attempts: the GPU choice, then the CPU arguments once.
  A GPU that failed during a real encode is not used again in this process.
"""
import contextlib
import functools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

TOKEN = "@VENC@"
ENC_SLOT = "@ENC@"
CACHE_VERSION = 1
PROBE_TIMEOUT = 30

_lock = threading.Lock()
_probe_lock = threading.Lock()   # one probe at a time — pool threads wait for the first
_memo = {}          # codec -> chosen alternative name (this process)
_broken = set()     # GPU names that failed during a real encode in this process
_identity = {}      # memo of the cache key parts (one lookup per process)
_hooks = {"run": None, "head": None, "log": None}
#: GPU encodes at once in this process. Consumer NVIDIA drivers allowed 3 sessions from 2020
#: (2 before); pool jobs beyond this wait instead of failing to open a session.
gpu_slots = threading.BoundedSemaphore(3)


def home_runner_dir():
    """실행기 밖에서 Claude 가 직접 치는 «안내형» 엔진 팩 도구가 이 모듈을 찾는 **오래 가는 설치 자리**(맥·윈도우 같은 자리
    `Path.home()`). 작업 폴더의 runner/ 는 작업 폴더와 함께 지워질 수 있어 가리키지 않는다 — 실행기가 돌 때 자기 파일을
    여기에 설치한다(volcano_drive.install_home_runner). 읽는 쪽 정본: volcano-mcp tools/venc_lookup.py `find_video_encoder`
    (자리를 같게 — tests/test_venc_lookup.py 가 대조)."""
    return Path.home() / ".volcano" / "runner"


def configure(run=None, head=None, log=None):
    """run(argv) -> CompletedProcess(text) · head('ffmpeg') -> resolved argv head · log(str)."""
    _hooks.update(run=run, head=head, log=log)


def _log(text):
    (_hooks["log"] or (lambda s: print(s, file=sys.stderr, flush=True)))(text)


def _run(argv):
    if _hooks["run"]:
        return _hooks["run"](argv)
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=PROBE_TIMEOUT)


def parse(item):
    if isinstance(item, str) and item.startswith(TOKEN):
        spec = json.loads(item[len(TOKEN):])
        if spec.get("v") != 1 or not spec.get("cpu") or not spec.get("alts"):
            raise ValueError("encoder slot has an unknown shape")
        return spec
    return None


def slots(argv):
    return [s for s in (parse(a) for a in argv or ()) if s]


def cache_path():
    return os.path.join(os.path.expanduser("~"), ".volcano", "video_encoder.json")


@functools.lru_cache(maxsize=1)
def _gpu_driver():
    """GPU driver string — part of the cache key (a driver update re-probes)."""
    try:
        if os.name == "nt":
            p = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + '|' + $_.DriverVersion }"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
            return " ; ".join(sorted(x.strip() for x in (p.stdout or "").splitlines() if x.strip()))
        if sys.platform == "darwin":
            return "macOS " + platform.mac_ver()[0] + " " + platform.machine()
        with open("/proc/driver/nvidia/version", encoding="utf-8") as f:
            return f.readline().strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""


def _key(program):
    """Cache key — `program` is the probe's own program name (the server sends the probe argv)."""
    with _lock:
        if "key" in _identity:
            return _identity["key"]
    head = (_hooks["head"] or (lambda name: [name]))(program) or [program]
    exe = head[-1]
    if not os.path.isabs(exe):
        exe = shutil.which(exe) or exe          # same PATH rule as the spawn that will run it
    try:
        st = os.stat(exe)
        stamp = f"{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        stamp = ""
    try:
        version = ((_run([*head, "-hide_banner", "-version"]).stdout or "").splitlines() or [""])[0]
    except (OSError, subprocess.SubprocessError):
        version = ""
    key = json.dumps([CACHE_VERSION, os.path.realpath(exe) if os.path.isabs(exe) else exe,
                      stamp, version, _gpu_driver()], ensure_ascii=False)
    with _lock:
        _identity["key"] = key
    return key


def _load():
    try:
        with open(cache_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    path = cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError as e:                      # the choice still holds for this process
        _log(f"  ⚠ 인코더 판정 기록을 못 남겼습니다({e}) — 다음 실행에서 다시 1초 시험합니다")


def _probe(spec, name, args):
    argv = []
    for a in spec["probe"]:
        argv.extend(args if a == ENC_SLOT else [a])
    t0 = time.monotonic()
    try:
        p = _run(argv)
        ok, why = p.returncode == 0, (p.stderr or "").strip().splitlines()[-1:] or [""]
    except (OSError, subprocess.SubprocessError) as e:
        ok, why = False, [str(e)]
    return {"ok": ok, "why": why[0][-300:], "sec": round(time.monotonic() - t0, 2)}


def _pick(spec, codec, names, cpu):
    key = _key(spec["probe"][0])
    data = _load()
    hit = ((data.get(key) or {}).get(codec) or {}).get("chosen")
    if hit not in names:
        hit, tried = cpu, {}
        for name, args in spec["alts"][:-1]:
            tried[name] = _probe(spec, name, args)
            if tried[name]["ok"]:
                hit = name
                break
        data = _load()
        data.setdefault(key, {})[codec] = {"chosen": hit, "tried": tried, "at": int(time.time())}
        _save(data)
        _log(f"  [인코더] {codec}: {hit} 로 굽습니다(1초 시험 " +
             (", ".join(f"{n} {'성공' if r['ok'] else '실패'}" for n, r in tried.items()) or "GPU 후보 없음") + ")")
    with _lock:
        _memo[codec] = hit
    return hit


def choose(spec):
    """Name of the alternative this PC uses for `spec['codec']` (probes once per key)."""
    codec = spec["codec"]
    names = [n for n, _ in spec["alts"]]
    cpu = names[-1]
    with _lock:
        hit = _memo.get(codec)
    if hit not in names:
        with _probe_lock:
            with _lock:
                hit = _memo.get(codec)
            if hit not in names:
                hit = _pick(spec, codec, names, cpu)
    # A GPU that failed during a real encode stays off for the rest of this process only.
    return cpu if hit in _broken else hit


def expand(argv, choice=None):
    """argv with every slot filled — `choice` None = this PC's pick, 'cpu' = server CPU args."""
    out, used = [], None
    for a in argv:
        spec = parse(a)
        if spec is None:
            out.append(a)
            continue
        name = spec["alts"][-1][0] if choice == "cpu" else choose(spec)
        args = dict((n, x) for n, x in spec["alts"])[name]
        if name != spec["alts"][-1][0]:
            used = name
        out.extend(args)
    return out, used


def failed(name, reason):
    """A GPU encoder failed during a real encode — CPU for the rest of this process."""
    with _lock:
        _broken.add(name)
    _log(f"  ⚠ GPU 인코더 {name} 가 굽는 도중 실패했습니다 — 이번 한 번만 CPU 로 다시 굽습니다. 사유: "
         + " ".join(str(reason or "").split())[-400:])


def fell_back():
    """GPU names that failed during a real encode in this process (empty = none).

    Pieces joined with `-c copy` must come from one encoder: if this is not empty after the pieces
    were made, re-encode the pieces that used the GPU (`chosen_name` at the time) on CPU first."""
    with _lock:
        return set(_broken)


def attempts(argv):
    """[(gpu_name_or_None, argv)] — the GPU try, then the CPU retry (at most two)."""
    first, used = expand(argv)
    if used is None:
        return [(None, first)]
    return [(used, first), (None, expand(argv, "cpu")[0])]


def chosen_name(argv):
    """Encoder name this PC would use for argv's first slot (None when argv has no slot)."""
    found = slots(argv)
    return choose(found[0]) if found else None


def cpu_name(argv):
    found = slots(argv)
    return found[0]["alts"][-1][0] if found else None


def run_with_fallback(argv, run):
    """For server scripts the runner launches (they see VOLCANO_RUNNER_DIR): run(argv) -> (rc, err).

    Same contract as the runner's own spawn — the GPU try, then the CPU arguments once."""
    rc, err = 1, ""
    for gpu, cmd in attempts(argv):
        rc, err = run(cmd)
        if rc == 0 or gpu is None:
            return rc, err
        failed(gpu, err)
    return rc, err


def _text(x):
    return x.decode("utf-8", "replace") if isinstance(x, bytes) else (x or "")


def subprocess_run(argv, **kw):
    """Drop-in for `subprocess.run(argv, **kw)` when argv carries a slot — the GPU try, then CPU once.

    Same keywords and return value as subprocess.run (check= raises after the CPU try failed too).
    If the caller did not capture stderr it is captured to read the failure reason and then written
    through to this process's stderr, so nothing the caller used to see goes missing.
    A timeout (TimeoutExpired) is not retried — that is a time limit, not an encoder failure."""
    check = kw.pop("check", False)
    passthrough = not kw.get("capture_output") and kw.get("stderr") is None
    if passthrough:
        kw["stderr"] = subprocess.PIPE
    p = None
    for gpu, cmd in attempts(argv):
        with gpu_slots if gpu else contextlib.nullcontext():
            p = subprocess.run(cmd, **kw)
        reason = p.stderr if p.stderr is not None else p.stdout
        if passthrough and p.stderr:
            sys.stderr.write(_text(p.stderr))
            sys.stderr.flush()
            p.stderr = None
        if p.returncode == 0 or gpu is None:
            break
        failed(gpu, _text(reason))
    if check and p.returncode:
        raise subprocess.CalledProcessError(p.returncode, p.args, p.stdout, p.stderr)
    return p


# ── 현지에서 argv 를 짓는 곳(범용 엔진 film_editor · 프리셋 엔진 팩)이 쓰는 자리 짓기 ─────────────────────────────
# 표(BPP)는 서버 src/volcano_venc.py 와 같아야 한다 — tests/test_video_encoder.py 가 두 곳을 값으로 대조한다.
# 엔진 팩이 이 모듈을 찾는 길: 실행기(volcano_run)가 자식 프로세스에 VOLCANO_RUNNER_DIR 를 넘긴다.
#   이 값이 없으면(실행기 밖에서 팩만 따로 돌림) 팩은 예전 libx264 인자를 그대로 쓴다 — 판정 없음.
#   값이 있는데 import 가 안 되면 오류다(삼키지 않는다).
# 한 줄 사용법(자세히: docs/2026-10-19_GPU-인코딩-공통모듈.md):
#   enc = video_encoder.x264("medium", 18, W, H, FPS, program=ffmpeg)      # '-c:v libx264 -preset medium -crf 18' 를 대신하는 목록
#   video_encoder.subprocess_run([ffmpeg, ..., *enc, "-pix_fmt", "yuv420p", out], check=True)   # subprocess.run 대신
#   비트레이트로 굽던 곳:  video_encoder.slot(["-c:v", "libx264", "-b:v", "6M"], 6_000_000, program=ffmpeg)
#   파이프로 프레임을 넣는 곳:  for gpu, cmd in video_encoder.attempts(argv): ...(성공 break · 실패 failed(gpu, 사유))
BPP = {"veryfast17": 0.06655, "medium18": 0.06693, "medium19": 0.06047, "slow18": 0.06404, "fast14": 0.10559,
       "fast16": 0.08551, "fast17": 0.07719, "fast18": 0.06983, "fast19": 0.06323,
       "medium14": 0.1019, "medium15": 0.09144, "medium16": 0.08226, "medium17": 0.07417,
       "veryfast12": 0.12715, "veryfast16": 0.07526, "veryfast18": 0.05909, "veryfast20": 0.04681,
       "medium23": 0.03991}
_COLOR = ["-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
# 고르는 규칙 두 칸 — 서버 src/volcano_venc.py 의 AMF_QUALITY·CPU_ONLY 와 같아야 한다(검사가 대조 · 근거는 그쪽 주석과 문서 §4-1).
AMF_QUALITY = "balanced"
CPU_ONLY = ("veryfast",)


def probe_argv(program):
    return [program, "-hide_banner", "-nostdin", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=1",
            ENC_SLOT, "-pix_fmt", "yuv420p", "-f", "null", "-"]


def slot(cpu, bitrate, *, program, codec="h264", color=True):
    """서버 `volcano_venc.slot` 과 같은 자리. `program` = 이 자리를 돌릴 ffmpeg(시험 굽기도 같은 것으로)."""
    cpu = [str(x) for x in cpu]
    if codec not in ("h264", "hevc") or not cpu or cpu[0] != "-c:v" or int(bitrate) <= 0:
        raise ValueError("encoder slot: codec h264|hevc · cpu starts with -c:v · bitrate > 0")
    b, top = str(int(bitrate)), str(2 * int(bitrate))
    rc = ["-b:v", b, "-maxrate", top, "-bufsize", top]
    prof = ["-profile:v", "high"] if codec == "h264" else ["-profile:v", "main", "-tag:v", "hvc1"]
    alts = [[f"{codec}_nvenc", ["-c:v", f"{codec}_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr"] + rc + prof],
            [f"{codec}_amf", ["-c:v", f"{codec}_amf", "-usage", "transcoding", "-quality", AMF_QUALITY, "-rc", "vbr_peak"] + rc + prof],
            [f"{codec}_qsv", ["-c:v", f"{codec}_qsv", "-preset", "medium"] + rc + prof],
            [f"{codec}_videotoolbox", ["-c:v", f"{codec}_videotoolbox", "-b:v", b] + prof]]
    alts = [[n, a + (_COLOR if color else [])] for n, a in alts] + [[cpu[1], cpu]]
    return TOKEN + json.dumps({"v": 1, "codec": codec, "cpu": cpu, "alts": alts, "probe": probe_argv(program)},
                              ensure_ascii=False, separators=(",", ":"))


def bitrate(preset, crf, width, height, fps):
    """libx264 `preset`+`crf` 와 같은 용량이 되는 초당 비트. preset None = libx264 기본(medium)."""
    key = f"{preset or 'medium'}{int(crf)}"
    if key not in BPP:
        raise KeyError(f"{key}: no measured bits-per-pixel — measure with tools/measure_venc.py bpp "
                       "and add it to both tables (src/volcano_venc.py · runner/video_encoder.py)")
    return max(1, int(round(BPP[key] * int(width) * int(height) * float(fps))))


# ── 완성본(회원이 올릴 마지막 굽기) 비트레이트 바닥 ─────────────────────────────────────────────────────────────
# 왜(2026-10-23 회원 신고 · VOX): BPP 표(libx264 «같은 용량»)로 GPU 완성본을 구우면 1080p30 medium18 이 약 4.2Mbps —
#   유튜브 권장 업로드 비트(1080p30 8Mbps)보다 낮아 업로드 뒤 재압축에서 화질을 잃는다(회원 실측 4.3Mbps → 16Mbps 다시 굽기, GPU 라 시간 차이 거의 없음).
#   그래서 `x264(..., final=True)` 로 부르는 마지막 굽기만 GPU 비트를 max(BPP 값, 유튜브 권장값)으로 올린다. 중간 재료는 그대로.
#   CPU(libx264 -crf)는 화질 기준(CRF)이라 비트를 정하지 않는다 — 그대로 둔다.
# 출처: support.google.com/youtube/answer/1722171 «Recommended video bitrates for SDR uploads»(2026-10-23 원문 확인) —
#   (짧은 변, 보통 fps 24·25·30 Mbps, 높은 fps 48·50·60 Mbps). 4K·8K 는 표의 범위 중 아래 끝.
YT_SDR_MBPS = ((4320, 80, 120), (2160, 35, 53), (1440, 16, 24), (1080, 8, 12), (720, 5, 7.5), (480, 2.5, 4), (360, 1, 1.5))
#: 회원이 완성본 비트를 정하는 자리(환경 변수 · 예 «16M» «12000k» «16000000») — 있으면 그 값이 바닥 계산을 대신한다.
FINAL_BITRATE_ENV = "VOLCANO_FINAL_BITRATE"


def youtube_floor(width, height, fps):
    """유튜브 권장 업로드 비트(초당 비트) — 짧은 변으로 줄을 고른다(세로 1080x1920 도 1080p 줄)."""
    short, high = min(int(width), int(height)), float(fps) >= 48
    row = next((r for r in YT_SDR_MBPS if short >= r[0]), YT_SDR_MBPS[-1])
    return int(round((row[2] if high else row[1]) * 1_000_000))


def _bits(text):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([kKmM]?)\s*", str(text))
    if not m or float(m.group(1)) <= 0:
        raise ValueError(f"{FINAL_BITRATE_ENV}={text!r}: 초당 비트를 숫자로(예 16M · 12000k · 16000000)")
    return int(round(float(m.group(1)) * {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2).lower()]))


def final_bitrate(preset, crf, width, height, fps):
    """완성본 GPU 비트 — 회원 지정(FINAL_BITRATE_ENV)이 있으면 그 값, 없으면 max(같은 용량 BPP, 유튜브 권장)."""
    own = (os.environ.get(FINAL_BITRATE_ENV) or "").strip()
    if own:
        return _bits(own)
    return max(bitrate(preset, crf, width, height, fps), youtube_floor(width, height, fps))


def x264(preset, crf, width, height, fps, *, program, extra=(), color=True, final=False):
    """`-c:v libx264 [-preset P] -crf C [extra]` 를 대신하는 argv 조각(**목록** — `*x264(...)` 로 펼친다).
    GPU 를 쓰는 preset 은 자리 하나 `[slot]`(CPU 는 그 인자 그대로, GPU 는 같은 용량 비트레이트(BPP)),
    CPU_ONLY preset 은 예전 libx264 인자 그대로(자리 없음).
    final=True = 회원이 올릴 마지막 굽기 — GPU 비트를 `final_bitrate`(유튜브 권장 바닥 · 회원 지정)로.
    preset None = 원래 argv 에 -preset 이 없던 곳(CPU 인자에 넣지 않는다 · 용량은 기본 medium 으로)."""
    cpu = ["-c:v", "libx264", *(["-preset", str(preset)] if preset else []), "-crf", str(crf),
           *[str(x) for x in extra]]
    if preset and str(preset) in CPU_ONLY:
        return cpu
    rate = (final_bitrate if final else bitrate)(preset, crf, width, height, fps)
    return [slot(cpu, rate, program=program, color=color)]
