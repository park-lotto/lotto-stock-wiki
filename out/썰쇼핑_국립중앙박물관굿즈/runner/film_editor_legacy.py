"""A host-authored edit sheet compiled into a deterministic local movie.

The server supplies concrete layout/voice settings. The host chooses the story
and camera points from measured scene sheets; this module never chooses a face.
Only the explicitly requested timestamp TTS operation uses a paid service.
"""
from contextlib import contextmanager
from pathlib import Path
import base64
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unicodedata
import urllib.request
import urllib.parse
import wave
import runtime_metrics

ENGINE_VERSION = "film-editor-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


_ASSET_CACHE = {}
_ASSET_LOCK = threading.Lock()


def source_asset_identity(path_or_str, primary_source=None, primary_source_id=None):
    """Deterministic content identity for video/image assets, avoiding repeated hashing."""
    if not path_or_str:
        return None
    path = Path(path_or_str).expanduser().resolve()
    if not path.is_file():
        raise ValueError("Source asset does not exist: " + str(path))
    st = path.stat()
    stamp = (st.st_size, st.st_mtime_ns)
    with _ASSET_LOCK:
        key = (str(path), stamp)
        if key in _ASSET_CACHE:
            return _ASSET_CACHE[key]
        if primary_source is not None and primary_source_id is not None:
            if path == Path(primary_source).expanduser().resolve():
                _ASSET_CACHE[key] = primary_source_id
                return primary_source_id
        sha = file_digest(path)
        _ASSET_CACHE[key] = sha
        return sha


def render_contract_digest(timeline_id, camera, config, tl, source, identity=None):
    """Single deterministic render contract digest binding exact rendering semantics."""
    from film_continuity import picture_timeline

    fonts_contract = {}
    for k, v in sorted(config.get("fonts", {}).items()):
        fpath = Path(v["path"]).expanduser().resolve() if "path" in v else None
        fonts_contract[k] = {
            "name": v.get("name"),
            "family": v.get("family"),
            "sha256": file_digest(fpath) if fpath and fpath.is_file() else None,
        }

    geometry_style = {
        "width": config.get("width"),
        "height": config.get("height"),
        "fps": config.get("fps"),
        "BG": config.get("BG"),
        "title": config.get("title"),
        "caption": config.get("caption"),
        "dialogue": config.get("dialogue"),
        "effect": config.get("effect"),
        "credit": config.get("credit"),
        "video": config.get("video"),
        "chrome": [
            {"path": str(layer["path"]), "x": layer.get("x"), "y": layer.get("y"),
             "width": layer.get("width"), "height": layer.get("height"),
             "sha256": file_digest(Path(layer["path"]).expanduser()) if Path(layer["path"]).expanduser().is_file() else None}
            for layer in config.get("chrome", [])
        ] if config.get("chrome") else None,
        "review_layout": config.get("review_layout"),
        "editorial_version": config.get("editorial_version"),
    }

    primary_src_id = (identity or {}).get("source_id")
    clips = picture_timeline(tl)["clips"] if ("clips" in tl or "picture_clips" in tl) else tl.get("clips", [])
    source_assets = {}
    for c in clips:
        clip_src = c.get("source") or source
        if not clip_src:
            continue
        c_path = Path(clip_src).expanduser().resolve()
        c_key = str(c_path)
        if c_key not in source_assets:
            is_still = bool(c.get("is_still") or c_path.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp') or c.get("clip_kind") in ('image', 'photo', 'still'))
            source_assets[c_key] = {
                "sha256": source_asset_identity(c_path, primary_source=source, primary_source_id=primary_src_id),
                "is_still": is_still,
            }

    contract = {
        "timeline_id": timeline_id,
        "camera": camera,
        "fonts": fonts_contract,
        "style": geometry_style,
        "sources": source_assets,
    }
    return digest(contract)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_json(path, value):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2,
                                 allow_nan=False).encode("utf-8"))


@contextmanager
def file_lock(path):
    """Native advisory lock on a writable descriptor; no unlink-on-release race."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError("Another editor is using this work directory") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError("Another editor is using this work directory") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def process_cwd(root):
    # Python file I/O accepts extended-length paths. Windows npm internally
    # invokes cmd.exe, which misclassifies the extended local-drive spelling
    # as UNC and silently changes cwd to C:\Windows. Keep extended file args,
    # but hand child processes the equivalent ordinary local-drive directory.
    name=str(root)
    prefix=chr(92)*2+'?'+chr(92)
    if os.name=='nt' and name.startswith(prefix) and len(name)>5 and name[5]==':':
        return name[4:]
    return name


@contextmanager
def process_directory(root, *, force_alias=False):
    """Keep CreateProcess/CMD below MAX_PATH using a temporary local junction.

    force_alias also protects browser profiles that add their own nested paths.
    Files and receipts stay at their original extended paths. Only the child's
    current-directory spelling changes; removing the junction never removes
    its target. No shell interpolation or administrator privileges are used.
    """
    name = process_cwd(root)
    if os.name != 'nt' or (not force_alias and len(name.encode('utf-16-le')) // 2 < 248):
        yield name
        return
    import ctypes
    import struct
    from ctypes import wintypes
    target = str(Path(name).resolve())
    prefix = chr(92) * 2 + '?' + chr(92)
    if target.startswith(prefix):
        target = target[4:]
    if target.startswith(chr(92) * 2) or target.startswith('UNC' + chr(92)):
        raise ValueError('Long network work directories require a local work folder')
    # Prefer the selected volume, not the system disk, for the short alias.
    anchor = Path(target)
    while len(str(anchor).encode('utf-16-le')) // 2 > 120:
        anchor = anchor.parent
    scratch = Path(tempfile.mkdtemp(prefix='.volcano-cwd-', dir=anchor))
    link = scratch / 'work'
    link.mkdir()
    try:
        substitute = ('\\??\\' + target).encode('utf-16-le')
        display = target.encode('utf-16-le')
        paths = substitute + b'\0\0' + display + b'\0\0'
        payload = struct.pack('<HHHH', 0, len(substitute), len(substitute) + 2, len(display)) + paths
        data = struct.pack('<IHH', 0xA0000003, len(payload), 0) + payload
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.DeviceIoControl.argtypes = [wintypes.HANDLE,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        kernel.DeviceIoControl.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(link), 0x40000000, 0, None, 3, 0x02200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            returned = wintypes.DWORD()
            buffer = ctypes.create_string_buffer(data)
            if not kernel.DeviceIoControl(handle, 0x000900A4, buffer, len(data), None, 0, ctypes.byref(returned), None):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
        yield str(link)
    finally:
        # rmdir unlinks the junction itself; never recursively delete its target.
        link.rmdir()
        scratch.rmdir()


def command(root, args, label, timeout=300):
    started = time.monotonic()
    log = Path(root) / "logs"
    log.mkdir(exist_ok=True)
    try:
        with process_directory(root) as cwd:
            p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        atomic_bytes(log / (label + ".log"), exc.stderr or b"")
        atomic_bytes(log / (label + ".stdout.log"), exc.stdout or b"")
        with (log / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"label":label,"seconds":time.monotonic()-started,
                                     "exit":None,"timed_out":True})+"\n")
        raise ValueError(label+": local process exceeded its time limit; partial logs and paid receipts are preserved") from exc
    atomic_bytes(log / (label + ".log"), p.stderr)
    atomic_bytes(log / (label + ".stdout.log"), p.stdout)
    with (log / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"label": label, "seconds": time.monotonic() - started,
                                 "exit": p.returncode}, ensure_ascii=False) + "\n")
    if p.returncode:
        diagnostic = (p.stderr + b"\n" + p.stdout).decode("utf-8", "replace")
        raise ValueError(label + ": exit=" + str(p.returncode) + ": " + (diagnostic.strip()[-4000:] or "process produced no diagnostic output; see commands.jsonl"))
    return p.stdout


def probe(root, source):
    return json.loads(command(root, ["ffprobe", "-v", "error", "-show_streams",
                                   "-show_format", "-of", "json", source], "probe"))


def number(value, label, low=0, high=float("inf")):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Invalid " + label)
    return value


def load_value(value):
    return read_json(value) if isinstance(value, (str, Path)) else value


def validate_config(config):
    if config.get("engine_version") != ENGINE_VERSION:
        raise ValueError("Unsupported editor engine version; keep the job's installed runner version")
    for key in ("fps", "width", "height"):
        number(config.get(key), key, 1, 7680)
        if int(config[key]) != config[key]:
            raise ValueError(key + " must be an integer")
    video = config["video"]
    for key in ("x", "y", "width", "height"):
        number(video.get(key), "video." + key, 0, 7680)
        if int(video[key]) != video[key] or video[key] % 2:
            raise ValueError("Video rectangle must use even integer pixels")
    if min(video["width"], video["height"]) <= 0 or video["x"] + video["width"] > config["width"] or video["y"] + video["height"] > config["height"]:
        raise ValueError("Video rectangle lies outside canvas")
    sample_rate = config["audio"]["sample_rate"]
    if sample_rate % config["fps"]:
        raise ValueError("Audio sample rate must be divisible by fps")


def subtitle_rows(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    rows = []
    stamp = r"((?:\d{1,3}:)?\d{2}:\d{2}[,.]\d{3})"
    def seconds(value):
        parts = value.replace(",", ".").split(":")
        return sum(float(v) * 60 ** i for i, v in enumerate(reversed(parts)))
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = block.splitlines()
        if lines and (lines[0].startswith("NOTE") or lines[0] in ("STYLE", "REGION")):
            continue
        for i, line in enumerate(lines):
            match = re.match(stamp + r"\s*-->\s*" + stamp, line)
            if match:
                start, end = seconds(match[1]), seconds(match[2])
                if end > start:
                    content = html.unescape(re.sub(r"<[^>]*>", "", " ".join(lines[i + 1:]))).strip()
                    if content:
                        rows.append([start, end, content])
                break
    if not rows:
        raise ValueError("Selected subtitle contains no usable UTF-8 SRT/VTT cues")
    return rows


def discover_subtitles(source, language=None):
    """Match NFC/NFD equivalent basenames, never infer a different language."""
    stem = unicodedata.normalize("NFC", source.stem).casefold()
    aliases = {"kor": {"ko", "kor", "kokr", "korean"},
               "eng": {"en", "eng", "enus", "engb", "english"},
               "jpn": {"ja", "jpn", "japanese"},
               "zho": {"zh", "zho", "zhs", "zht", "zhcn", "zhtw", "chinese"}}
    wanted = str(language or "").casefold()
    accepted = next((a for k, a in aliases.items() if wanted == k or wanted in a), {wanted} if wanted else set())
    candidates, automatic = [], []
    for path in sorted(source.parent.iterdir()):
        if not path.is_file() or path.suffix.casefold() not in (".srt", ".vtt"):
            continue
        candidate = unicodedata.normalize("NFC", path.stem).casefold()
        if candidate == stem:
            candidates.append(path); automatic.append(path)
            continue
        if not candidate.startswith(stem) or candidate[len(stem):len(stem)+1] not in ". _-([":
            continue
        candidates.append(path)
        suffix = re.sub(r"[\s._()\[\]-]+", "", candidate[len(stem):])
        suffix = re.sub(r"(?:cc|sdh)$", "", suffix)
        if suffix in accepted:
            automatic.append(path)
    return candidates, automatic


def source_overview(root, source, duration, *, tile_width=320, max_frames=240):
    """설명자막 소재(인물형)용 **원본 훑어보기 시트** — 저자가 대본을 쓰기 전에 원본을 본다 (2026-09-16).

    ■ 왜
        인물형 새 경로는 원본 전사가 없다(창작 설명 자막). 그러면 저자가 장면을 고를 근거가
        «원본을 본 것» 뿐인데, 그 원본을 보여 주는 자리가 없었다 — 09-16 실기는 사람이 미리 잰
        시각(238~242초)을 프롬프트에 박아 넘겼다. 새 소재에서는 그 시각을 아무도 모른다.
    ■ 무엇
        일정 간격(기본 2초, 긴 원본은 최대 `max_frames` 장이 되게 늘림)으로 저해상도 프레임을 뽑아
        라벨(원본 초·mm:ss)을 붙인 접촉 시트로 묶는다. 저자는 시트를 Read 로 열고 라벨의 초를
        `source_in`/`source_out` 에 그대로 쓴다 — 시각을 추측하지 않는다.
    ★고르지 않는다. 장면 판단은 저자(현재 클라이언트 AI)의 일이다.
    """
    duration = float(duration or 0.0)
    step = 2.0
    if duration > step * max_frames:
        step = math.ceil(duration / max_frames * 2) / 2
    folder = root / "overview"; frames = folder / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for old in list(frames.glob("*.jpg")) + list(folder.glob("overview-*.jpg")):
        old.unlink()
    command(root, ["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0", "-an",
                   "-vf", f"fps=1/{step},scale={tile_width}:-2", "-q:v", "3", "-y",
                   frames / "%05d.jpg"], "overview")
    images = sorted(frames.glob("*.jpg"))
    if not images:
        raise ValueError("Source overview produced no frames; the video stream could not be decoded")
    entries = []
    for i, path in enumerate(images):
        at = i * step
        entries.append((path, f"{at:.1f}s ({int(at) // 60:02d}:{int(at) % 60:02d})"))
    sheets = contact_sheets(folder, entries, prefix="overview", columns=6, per_page=36)
    return {"overview_sheets": sheets, "overview_step_sec": step, "overview_frames": len(images)}


def ingest(root, source, item, identity):
    from local_paths import resolve_existing_input
    info = probe(root, source)
    videos = [s for s in info["streams"] if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise ValueError("Source must contain video stream")
    is_commentary_only = bool(
        item.get("no_asr") or item.get("caption_type") == "commentary"
        or item.get("config", {}).get("no_asr")
        or item.get("config", {}).get("caption", {}).get("subtitle_type") == "commentary"
        or item.get("config", {}).get("preset") in ("인물형",)
    )
    has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
    if not has_audio and not is_commentary_only:
        raise ValueError("Source must contain video and audio streams")
    silence_bed = None
    if not has_audio:
        silence_bed = root / "silence.m4a"
        if not silence_bed.is_file():
            command(root, ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                           "-t", str(info["format"]["duration"]), "-c:a", "aac", "-b:a", "192k",
                           "-ar", "48000", "-y", silence_bed], "silence-bed")
    selected = item.get("subtitle_path")
    if selected:
        selected = str(resolve_existing_input(selected))
    candidates, automatic = discover_subtitles(source, item.get("source_lang") or item.get("config", {}).get("tts", {}).get("language"))
    if not selected and len(automatic) == 1:
        selected = str(automatic[0])
    result = {"ok": True, "status": "ingested" if (selected or is_commentary_only) else "needs_subtitles",
              **identity, "source": str(source), "duration": float(info["format"]["duration"]),
              "source_width": videos[0]["width"], "source_height": videos[0]["height"],
              "subtitle_candidates": [str(p) for p in candidates]}
    if silence_bed:
        result["silence_bed_path"] = str(silence_bed)
        result["has_source_audio"] = False
    supplied = item.get("transcript") or item.get("words")
    if selected or supplied or is_commentary_only:
        if selected:
            rows = subtitle_rows(selected)
            result.update(subtitle_path=str(Path(selected).resolve()), subtitle_sha256=file_digest(selected))
        elif supplied:
            rows = []
            for word in supplied:
                a = number(word.get("start"), "transcript start", 0, result["duration"])
                b = number(word.get("end"), "transcript end", a, result["duration"])
                text = word.get("text", word.get("word"))
                if b > a and isinstance(text, str) and text.strip():
                    rows.append([a, b, text])
            if not rows:
                raise ValueError("Supplied transcription has no usable timestamped text")
            result.update(transcript_sha256=digest(rows), transcript_origin="provided_timestamps")
        else:
            rows = []
            result.update(transcript_sha256=digest(rows), transcript_origin="no_asr_commentary")
        result.update(status="ingested",
                      transcript_path=str(root / "transcript.json"), subtitle_cues=len(rows))
        atomic_json(root / "transcript.json", rows)
        atomic_bytes(root / "transcript.txt", "\n".join(f"{a:.3f}–{b:.3f} {t}" for a, b, t in rows).encode("utf-8"))
        if item.get("config", {}).get("editorial_version"):
            table = timing_table(root, source, item, identity, rows, selected)
            result.update(timing_table_path=str(root / "source-timing.json"), timing_kind=table["timing_kind"])

    else:
        result["instruction"] = "Select an exact source SRT/VTT in the intended language, or provide Speechmatics transcription. No local ASR fallback was run."
    if is_commentary_only:
        # 설명자막 경로는 저자가 원본을 **보고** 장면을 골라야 한다 — 훑어보기 시트를 같이 남긴다.
        result.update(source_overview(root, source, info["format"]["duration"]))
    atomic_json(root / "ingest.json", result)
    return result


class PaidUncertain(Exception):
    def __init__(self, request_id):
        self.request_id = request_id
        super().__init__("A paid request was submitted or reserved but its result is uncertain. Preserve the receipt; do not automatically resend.")


def typecast_key(headers):
    for name, value in (headers or {}).items():
        if name.lower() == "x-api-key" and value:
            return value
    if os.environ.get("TYPECAST_API_KEY"):
        return os.environ["TYPECAST_API_KEY"]
    path = Path.home() / ".volcano" / "keys" / "typecast"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    raise ValueError("Typecast API key is missing; configure it locally before preparing narration")


def typecast_body(text, settings):
    return {"text": text, "voice_id": settings["voice_id"], "model": settings["model"],
            "language": settings["language"], "seed": settings.get("seed", 42),
            "prompt": {"emotion_type": "preset", "emotion_preset": settings["emotion"], "emotion_intensity": 1},
            "output": {"volume": 100, "audio_pitch": 0, "audio_tempo": settings["tempo"], "audio_format": "wav"}}


def request_tts(root, text, config, headers):
    settings = config["tts"]
    if settings.get("provider") != "typecast":
        raise ValueError("This engine requires a timestamp-capable Typecast configuration")
    endpoint = settings.get("endpoint", "")
    parsed_endpoint = urllib.parse.urlsplit(endpoint)
    if parsed_endpoint.scheme != "https" or not parsed_endpoint.hostname or parsed_endpoint.username or parsed_endpoint.password or parsed_endpoint.fragment:
        raise ValueError("The configured timestamp TTS endpoint must be an HTTPS service URL")
    body = typecast_body(text, settings)
    body_id = digest(body)
    request_id = digest({"version": 2, "endpoint": endpoint, "body": body})
    # Serialize the whole paid ledger: a changed edit must not race another body
    # into a second paid request. Never move/delete legacy receipts during reuse.
    with file_lock(root / "paid" / "ledger.lock"):
        folder = root / "paid" / request_id
        legacy = root / "paid" / body_id
        records = [p for p in (root / "paid").iterdir() if p.is_dir() and
                   ((p / "receipt.json").exists() or (p / "response.json").exists())]
        if not any(p == folder for p in records):
            if legacy in records:
                previous = read_json(legacy / "receipt.json") if (legacy / "receipt.json").is_file() else {}
                pin = read_json(root / "identity.json") if (root / "identity.json").is_file() else {}
                bound = previous.get("endpoint") == endpoint or (
                    not previous.get("endpoint") and pin.get("config_id") == digest(config))
                if not bound or not previous or not (legacy / "response.json").is_file():
                    raise PaidUncertain(body_id)
                folder = legacy
            elif records:
                # No automatic narration regeneration within an existing job.
                # Source shots, cards and camera edits reuse the unchanged body.
                blocked = PaidUncertain(records[0].name)
                blocked.args = ("This job already has a paid narration record. Keep the exact narration text and voice settings when changing source shots, cards or camera. Automatic paid regeneration is blocked; preserve all receipts.",)
                raise blocked
        folder.mkdir(parents=True, exist_ok=True)
        request_id = folder.name
        receipt_path, response_path = folder / "receipt.json", folder / "response.json"
        if response_path.exists() and not receipt_path.is_file():
            raise PaidUncertain(folder.name)
        requested = False
        if not response_path.is_file():
            if receipt_path.exists():
                raise PaidUncertain(request_id)
            key = typecast_key(headers)
            atomic_json(receipt_path, {"request_id": request_id, "status": "reserved",
                                      "request_identity_version": 2, "endpoint": endpoint, "body_sha256": body_id,
                                      "characters": len(text), "request_characters": len(text),
                                      "provider": settings["provider"], "model": settings["model"],
                                      "language": settings["language"], "billing": {"actual_cost": None, "status": "unavailable"},
                                      "created_unix": time.time(), "requests": 1})
            request = urllib.request.Request(endpoint,
                                             data=json.dumps(body).encode("utf-8"),
                                             headers={"X-API-KEY": key, "Content-Type": "application/json"}, method="POST")
            started = time.monotonic()
            requested = True
            response, raw, parsed = None, None, None
            response_recorded = False
            with runtime_metrics.context(str(root)):
                runtime_metrics.event("tts", "submitted", request_id)
            try:
                with runtime_metrics.context(str(root)), runtime_metrics.span("api", "tts"):
                    with urllib.request.urlopen(request, timeout=180) as response:
                        raw = response.read()
                    # Save before parsing; malformed results never authorize a replay.
                    atomic_bytes(response_path, raw)
                    parsed = json.loads(raw)
                with runtime_metrics.context(str(root)):
                    runtime_metrics.provider_response("tts", request_id, response, parsed,
                        service=settings["provider"], model=settings["model"], json_received=True,
                        seconds=time.monotonic() - started, outcome="response_received")
                    response_recorded = True
                receipt = read_json(receipt_path)
                receipt.update(status="response_received", seconds=time.monotonic() - started,
                               response_sha256=hashlib.sha256(raw).hexdigest())
                atomic_json(receipt_path, receipt)
            except Exception as exc:
                with runtime_metrics.context(str(root)):
                    runtime_metrics.event("tts", "failed", request_id)
                    if not response_recorded:
                        runtime_metrics.provider_response("tts", request_id, response or exc, parsed,
                            service=settings["provider"], model=settings["model"], json_received=parsed is not None,
                            seconds=time.monotonic() - started,
                            outcome="http_error" if getattr(exc, "code", None) else
                                    "json_error" if raw is not None else
                                    "read_error" if response is not None else "transport_error")
                receipt = read_json(receipt_path)
                receipt.update(status="uncertain", error_type=type(exc).__name__, seconds=time.monotonic() - started)
                atomic_json(receipt_path, receipt)
                raise PaidUncertain(request_id) from exc
        saved_receipt = read_json(receipt_path)
        if saved_receipt.get("response_sha256") and file_digest(response_path) != saved_receipt["response_sha256"]:
            raise ValueError("Saved TTS response checksum differs; preserve paid receipt for recovery")
        data = read_json(response_path)
        if "characters" not in data or "audio" not in data:
            raise ValueError("Saved TTS response has no character timestamps/audio; preserve paid receipt for recovery")
        if "".join(x["text"] for x in data["characters"]) != text:
            raise ValueError("TTS transcript differs from requested text; preserve paid receipt")
        audio = folder / "narration.wav"
        decoded = base64.b64decode(data["audio"], validate=True)
        if not audio.is_file() or file_digest(audio) != hashlib.sha256(decoded).hexdigest():
            atomic_bytes(audio, decoded)
        with runtime_metrics.context(str(root)):
            runtime_metrics.event("tts", "succeeded" if requested else "reused", request_id)
        return data, audio, {**read_json(receipt_path), "reused": not requested}


def clean(text):
    return "".join(c for c in text if c.isalnum())


def validate_edit(edit, duration):
    if not isinstance(edit, dict) or not isinstance(edit.get("sequence"), list) or not edit["sequence"]:
        raise ValueError("An authored, nonempty edit.sequence is required")
    ids = set()
    for n in edit.get("narration", []):
        if not isinstance(n.get("id"), str) or n["id"] in ids or not clean(n.get("text", "")):
            raise ValueError("Narration needs unique IDs and spoken text")
        ids.add(n["id"])
        number(n.get("source"), "narration source", 0, duration)
        if not n.get("cards") or any(not isinstance(t, str) or not clean(t) for t in n["cards"]) or clean("".join(n["cards"])) != clean(n["text"]):
            raise ValueError("Narration cards must cover its exact spoken text")
    for c in edit["sequence"]:
        if "narration" in c:
            if c["narration"] not in ids:
                raise ValueError("Unknown narration ID")
        else:
            clip_src = c.get("source")
            # A clip with its own source (multi-source person cut) is bounded by that file's probe
            # later, not by the primary source duration. The old form referenced an undefined
            # name (`source`) that always resolved to "" — same behaviour, now stated plainly.
            clip_dur = float('inf') if clip_src else duration
            a = number(c.get("source_in"), "source_in", 0, clip_dur)
            b = number(c.get("source_out"), "source_out", 0, clip_dur)
            if b <= a:
                raise ValueError("Empty source interval")
            for row in c.get("captions", []):
                if isinstance(row, str):
                    if not clean(row):
                        raise ValueError("Caption phrase must contain spoken text")
                    continue
                if isinstance(row, dict):
                    if not isinstance(row.get("word_ids"), list) or not isinstance(row.get("text"), str):
                        raise ValueError("Caption card requires word_ids and text")
                    continue
                start, end, text = row
                number(start, "caption start", a, b)
                number(end, "caption end", start, b)
                if end <= start or not isinstance(text, str):
                    raise ValueError("Invalid caption")
    if not isinstance(edit.get("title"), list) or not all(isinstance(t, str) for t in edit["title"]):
        raise ValueError("edit.title must be a list of text lines")


def validate_source_order(edit):
    """Reject known replay/order conflicts before spending on unknown N lengths."""
    narration = {n["id"]: n for n in edit.get("narration", [])}
    lower = 0
    pending_source = 0
    for index, clip in enumerate(edit["sequence"]):
        reason = clip.get("intentional_jumpback_reason")
        if reason is not None:
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("Source jumpback requires an explicit authored reason")
            lower = 0
            pending_source = 0
        a = narration[clip["narration"]]["source"] if "narration" in clip else clip["source_in"]
        # Narration picture positions are requests, not fixed intervals. Once
        # voice lengths are known, the resolver can backfit them before the next
        # dialogue. Only a preceding fixed dialogue creates a known lower bound.
        if a < lower - 1e-8:
            raise ValueError(f"Source sequence[{index}] replays an already selected interval. Select a forward interval before requesting voice, or explicitly author an intentional flashback.")
        if "narration" in clip:
            pending_source = max(pending_source, a)
        else:
            if pending_source > a + 1e-8:
                raise ValueError(f"Source sequence[{index}] precedes the requested narration picture. Reorder the story or select an earlier narration source before requesting voice; do not silently move later events backwards.")
            lower = clip["source_out"]
            pending_source = 0


def narration_cards(narration, config):
    """Split display cards only; keep paid text and Unicode character offsets intact."""
    spec = config.get("caption", {})
    if not config.get("editorial_version") or not spec.get("fixed_size"):
        return narration["cards"]
    from PIL import ImageFont
    font = ImageFont.truetype(str(Path(config["fonts"]["body"]["path"]).expanduser()), spec["size"])
    maximum = spec["max_width"]
    preferred = min(maximum, spec.get("cadence_width", maximum))
    result = []
    for original in narration["cards"]:
        if "\n" not in original and "\r" not in original and font.getlength(original)*spec.get('metric_scale',.84) <= preferred:
            result.append(original)
            continue
        group = ""
        for word in original.split():
            if font.getlength(word)*spec.get('metric_scale',.84) > maximum:
                raise ValueError("Narration card contains an oversized word: " + word)
            joined = (group + " " + word).strip()
            if group and font.getlength(joined)*spec.get('metric_scale',.84) > preferred:
                result.append(group)
                group = word
            else:
                group = joined
        if group:
            result.append(group)
    return result


def compile_timeline(edit, tts, config):
    fps, cursor, narration = config["fps"], 0, {}
    chars = tts.get("characters", []) if tts else []
    for n in edit.get("narration", []):
        subset = chars[cursor:cursor + len(n["text"])]; cursor += len(n["text"]) + 1
        if len(subset) != len(n["text"]) or any(len(x["text"]) != 1 for x in subset):
            raise ValueError("TTS must return one timestamp per requested Unicode character")
        spoken = [x for x in subset if x["text"].isalnum()]
        for x in spoken:
            number(x["start"], "TTS start")
            number(x["end"], "TTS end", x["start"])
        a = max(0, spoken[0]["start"] - .065)
        b = min(float(tts["audio_duration"]), spoken[-1]["end"] + .09)
        frames = math.ceil((b - a) * fps)
        if frames <= 0:
            raise ValueError("Empty timestamp narration")
        offset, caps = 0, []
        for text in narration_cards(n, config):
            length = len(clean(text))
            caps.append([max(0, spoken[offset]["start"] - a),
                         min(frames / fps, spoken[offset + length - 1]["end"] - a + .07), text])
            offset += length
        narration[n["id"]] = {"kind": "N", "source_in": n["source"], "audio_in": a,
                               "frames": frames, "captions": caps}
    clips, total = [], 0
    for idx, item in enumerate(edit["sequence"]):
        if "narration" in item:
            c = dict(narration[item["narration"]])
        else:
            frames = round((item["source_out"] - item["source_in"]) * fps)
            is_comm = bool(
                item.get("caption_type") == "commentary" or item.get("is_dialogue") is False
                or config.get("caption", {}).get("subtitle_type") == "commentary"
                or config.get("dialogue", {}).get("subtitle_type") == "commentary"
                or edit.get("caption_type") == "commentary"
            )
            caps = []
            for row in item.get("captions", []):
                if isinstance(row, str):
                    # Commentary has no transcript to fit a phrase to: a bare string is the
                    # whole-clip caption. (A person run submitted this documented shape and the
                    # later triple unpack crashed with "too many values to unpack", 2026-09-16.)
                    caps.append([0.0, frames / fps, row] if is_comm else row)
                elif isinstance(row, dict):
                    if is_comm:
                        raise ValueError("Commentary captions are plain text or [start, end, text]; "
                                         "word-bound captions need a transcript")
                    caps.append(row)
                else:
                    caps.append([row[0] - item["source_in"], row[1] - item["source_in"], row[2]])
            c = {"kind": "D", "source_in": item["source_in"], "frames": frames,
                 "caption_type": "commentary" if is_comm else "dialogue",
                 "is_dialogue": not is_comm, "captions": caps}
            if "source" in item:
                c["source"] = item["source"]
            if "is_still" in item:
                c["is_still"] = item["is_still"]
            if "kind" in item:
                c["clip_kind"] = item["kind"]
        if c["frames"] < 1:
            raise ValueError("Clip must contain at least one output frame")
        if "speaker" in item:
            c["speaker"] = str(item["speaker"])
        if item.get("intentional_jumpback_reason"):
            c["intentional_jumpback_reason"] = item["intentional_jumpback_reason"]
        c.update(index=idx, duration=c["frames"] / fps, timeline_in=total / fps,
                 timeline_out=(total + c["frames"]) / fps, effect=item.get("effect"))
        total += c["frames"]; clips.append(c)
    from film_tracks import compile_tracks
    music = edit.get("music")
    if isinstance(music, str) and music.strip():
        music = {"path": music.strip()}
    extra = {"music": dict(music)} if isinstance(music, dict) and music.get("path") else {}
    return compile_tracks({"fps": fps, "frames": total, "duration": total / fps, "clips": clips, **extra,
            "title": edit["title"], "credit": edit.get("credit", "")}, edit)


def measure_content(root, source, info, clips):
    """Use the most common measured rectangle; send it to the host for review."""
    samples = []
    for c in clips[:8]:
        clip_src = c.get("source") or source
        ext = Path(clip_src).suffix.lower() if isinstance(clip_src, (str, Path)) else ""
        is_still = ext in ('.jpg', '.jpeg', '.png', '.webp') or c.get("is_still") or c.get("clip_kind") in ('image', 'photo', 'still')
        if is_still:
            command(root, ["ffmpeg", "-hide_banner", "-i", str(clip_src),
                           "-map", "0:v:0", "-an", "-t", "1", "-vf",
                           "cropdetect=24:2:0", "-f", "null", "-"], "content")
        else:
            command(root, ["ffmpeg", "-hide_banner", "-ss", str(c["source_in"]), "-i", str(clip_src),
                           "-map", "0:v:0", "-an", "-t", str(min(1, c["duration"])), "-vf",
                           "cropdetect=24:2:0", "-f", "null", "-"], "content")
        samples += [tuple(map(int, m)) for m in re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", (root / "logs/content.log").read_text(encoding="utf-8", errors="replace"))]
    sw, sh = info["source_width"], info["source_height"]
    valid = [s for s in samples if s[0] >= sw * .5 and s[1] >= sh * .5 and s[2] + s[0] <= sw and s[3] + s[1] <= sh]
    if not valid:
        return {"width": sw, "height": sh, "x": 0, "y": 0, "method": "full_frame_no_stable_crop"}
    w, h, x, y = max(set(valid), key=valid.count)
    return {"width": w, "height": h, "x": x, "y": y, "method": "cropdetect_mode"}


def source_grid_input(source, start_frame, fps):
    # Keep the preceding keyframe and its timestamps: fps rounding needs the
    # preceding decoded image, even when the requested cut lies between frames.
    return ["-copyts", "-start_at_zero", "-noaccurate_seek", "-ss",
            f"{max(0, start_frame / fps - .5):.12f}", "-i", source]


def source_grid_filter(start_frame, count, fps):
    return f"fps={fps}:round=near,trim=start_pts={start_frame}:end_pts={start_frame+count},setpts=PTS-STARTPTS"


def measure_source_catalog(root, source, intervals, config, duration, source_id):
    """Cache actual decoded handles, including gaps; never invent continuity."""
    from film_continuity import measurement_windows, build_source_shots
    fps = config['fps']
    windows = measurement_windows(intervals, fps, duration, config.get('source_handles_seconds', 2))
    key = digest({'source_id':source_id, 'fps':fps, 'threshold':config.get('scene_threshold',.15),
                  'measurement_version':4})
    folder = root / 'source-catalog'; folder.mkdir(exist_ok=True)
    path = folder / (key+'.json')
    saved = read_json(path) if path.exists() else {'windows':[], 'cut_frames':[]}
    if path.exists() and (saved.get('key') != key or saved.get('cache_sha256') !=
                         digest({k:v for k,v in saved.items() if k!='cache_sha256'})):
        raise ValueError('Source scene cache identity or evidence changed; preserve evidence')
    cuts = set(saved['cut_frames'])
    measured = list(saved['windows'])
    for a,b in windows:
        if any(left <= a and b <= right for left,right in measured):
            continue
        first, stop = round(a*fps), round(b*fps)
        # scene compares current AND previous mean absolute frame differences.
        # Two predecessors seed that state, matching a continuous decode and
        # avoiding a false cut created only by the measurement window boundary.
        decode_first = max(0,first-2)
        filt = source_grid_filter(decode_first,stop-decode_first,fps)
        filt += f",select='gt(scene,{config.get('scene_threshold',.15)})',showinfo"
        label = f'source-scenes-{first}-{stop}'
        command(root,['ffmpeg','-hide_banner',*source_grid_input(source,decode_first,fps),
                      '-map','0:v:0','-an','-vf',filt,'-f','null','-'],label)
        log=(root/'logs'/(label+'.log')).read_text(encoding='utf-8',errors='replace')
        cuts.update(frame for t in re.findall(r'pts_time:([\d.]+)',log)
                    if first <= (frame := decode_first+round(float(t)*fps)) < stop and frame>0)
        measured.append([a,b])
    merged=measurement_windows(measured,fps,duration,0)
    data={'key':key,'source_id':source_id,'windows':merged,'cut_frames':sorted(cuts),
          'cuts':[frame/fps for frame in sorted(cuts)],'source_duration':duration}
    data['shots']=build_source_shots(merged,data['cuts'],duration)
    data['cache_sha256']=digest(data)
    atomic_json(path,data)
    return data


def measure_source_shots(root, source, tl, config):
    """Measure each connected source window once, independent of caption cuts."""
    from film_continuity import build_source_shots, build_picture_fragments
    intervals = sorted((c.get("picture_in", c["source_in"]),
                        c.get("picture_in", c["source_in"]) + c["duration"]) for c in tl["clips"])
    windows = []
    for a, b in intervals:
        if windows and a <= windows[-1][1] + 1:
            windows[-1][1] = max(windows[-1][1], b)
        else:
            windows.append([a, b])
    cuts = []
    for index, (a, b) in enumerate(windows):
        count = round((b-a) * tl["fps"])
        first = round(a * tl["fps"])
        filt = source_grid_filter(first, count, tl["fps"]) + f",select='gt(scene,{config.get('scene_threshold', .15)})',showinfo"
        label = f"source-scenes-{index}"
        command(root, ["ffmpeg", "-hide_banner", *source_grid_input(source, first, tl["fps"]),
                       "-map", "0:v:0", "-an", "-vf", filt, "-f", "null", "-"], label)
        log = (root / "logs" / (label + ".log")).read_text(encoding="utf-8", errors="replace")
        cuts.extend(a + round(float(t)*tl["fps"])/tl["fps"]
                    for t in re.findall(r"pts_time:([\d.]+)", log) if 0 < float(t) < b-a)
    shots = build_source_shots(windows, cuts, max(b for _, b in windows))
    fragments = build_picture_fragments(tl, shots)
    data = {"shots": shots, "fragments": fragments, "windows": windows, "cuts": cuts}
    atomic_json(root / "source-shots.json", data)
    return data


def frame_select_expression(frames):
    # A flat sum exceeds FFmpeg's expression recursion limit on some builds.
    # A balanced tree selects exactly the same frames with logarithmic depth.
    terms = [f'eq(n,{frame})' for frame in frames]
    while len(terms) > 1:
        terms = ['(' + terms[i] + '+' + terms[i+1] + ')' if i+1 < len(terms) else terms[i]
                 for i in range(0, len(terms), 2)]
    return terms[0] if terms else '0'


def contact_sheets(folder, entries, *, prefix, columns, per_page, crop=None):
    """Pack all labelled evidence, without dropping similar/adjacent frames."""
    from PIL import Image, ImageDraw
    paths = []
    for offset in range(0, len(entries), per_page):
        group = entries[offset:offset + per_page]
        with Image.open(group[0][0]) as first:
            width, height = first.crop(crop).size if crop else first.size
        sheet = Image.new('RGB', (width * min(columns, len(group)),
            (height + 24) * math.ceil(len(group) / columns)), '#222222')
        draw = ImageDraw.Draw(sheet)
        for index, (path, label) in enumerate(group):
            x, y = index % columns * width, index // columns * (height + 24)
            with Image.open(path) as image:
                tile = image.crop(crop) if crop else image
                if tile.size != (width, height):
                    fitted = Image.new('RGB', (width, height), '#111111')
                    im_ratio = tile.width / tile.height
                    target_ratio = width / height
                    if im_ratio > target_ratio:
                        new_w = width
                        new_h = max(1, round(width / im_ratio))
                    else:
                        new_h = height
                        new_w = max(1, round(height * im_ratio))
                    resized = tile.resize((new_w, new_h), Image.Resampling.BILINEAR)
                    fitted.paste(resized, ((width - new_w) // 2, (height - new_h) // 2))
                    tile = fitted
                sheet.paste(tile, (x, y + 24))
            draw.text((x + 4, y + 4), label, fill='white')
        target = folder / f'{prefix}-{offset//per_page}.jpg'
        sheet.save(target, quality=93); paths.append(str(target))
    return paths


def window_box(config, image_width):
    scale = image_width / config['width']; video = config['video']
    return tuple(round(value * scale) for value in (video['x'], video['y'],
        video['x'] + video['width'], video['y'] + video['height']))


def scene_sheets(root, source, tl, config, canonical=None):
    from PIL import Image, ImageDraw
    folder = root / "samples"; folder.mkdir(exist_ok=True)
    template, sheets, measurements = {}, [], {}
    compact_entries = []
    if canonical is None and config.get("editorial_version"):
        canonical = measure_source_shots(root, source, tl, config)
    if canonical:
        atomic_json(root / 'source-shots.json', canonical)
    for c in tl["clips"]:
        idx, count = c["index"], c["frames"]
        picture_in = c.get("picture_in", c["source_in"])
        clip_src = c.get("source") or source
        ext = Path(clip_src).suffix.lower() if isinstance(clip_src, (str, Path)) else ""
        is_still = ext in ('.jpg', '.jpeg', '.png', '.webp') or c.get("is_still") or c.get("clip_kind") in ('image', 'photo', 'still')
        if canonical:
            cuts = [part["start"] for part in canonical["fragments"][str(idx)] if part["start"] > 0]
        elif is_still:
            cuts = []
        else:
            # Decode precisely the same fps grid used by picture_filter.
            filt = f"setpts=PTS-STARTPTS,fps={tl['fps']},trim=end_frame={count},select='gt(scene,{config.get('scene_threshold', .30)})',showinfo"
            command(root, ["ffmpeg", "-hide_banner", "-ss", str(picture_in), "-i", str(clip_src),
                           "-map", "0:v:0", "-an", "-t", str(c["duration"] + 1),
                           "-vf", filt, "-f", "null", "-"], f"scene-{idx}")
            log = (root / "logs" / f"scene-{idx}.log").read_text(encoding="utf-8", errors="replace")
            cuts = sorted({round(float(t) * tl["fps"]) for t in re.findall(r"pts_time:([\d.]+)", log) if 0 < round(float(t) * tl["fps"]) < count})
        starts = [0] + cuts
        frames = {0, count - 1}
        for a, b in zip(starts, starts[1:] + [count]):
            frames.update([a, (a + b - 1) // 2, b - 1])
            # Motion samples at most 0.5 seconds apart; avoids only start/end guesses.
            frames.update(range(a, b, max(1, tl["fps"] // 2)))
        for at in cuts:
            frames.update([at - 1, at])
        template[str(idx)] = {"shots": [{"start": n, "points": [[n, None]]} for n in starts]}
        measurements[str(idx)] = {"cuts": cuts, "frames": count}
        frames = sorted(frames)
        expression = frame_select_expression(frames)
        frame_dir = folder / str(idx); frame_dir.mkdir(exist_ok=True)
        if is_still:
            decode_input = ["-framerate", str(tl["fps"]), "-loop", "1", "-i", str(clip_src)]
            decode_filter = f"fps={tl['fps']},trim=end_frame={count}"
        elif canonical:
            decode_input = source_grid_input(str(clip_src), c["source_frame_in"], tl["fps"])
            decode_filter = source_grid_filter(c["source_frame_in"], count, tl["fps"])
        else:
            decode_input = ["-ss", str(picture_in), "-i", str(clip_src)]
            decode_filter = f"setpts=PTS-STARTPTS,fps={tl['fps']},trim=end_frame={count}"
        command(root, ["ffmpeg", "-v", "error", *decode_input,
                       "-map", "0:v:0", "-an", "-vf",
                       decode_filter + f",select='{expression}',scale=480:-2",
                       "-fps_mode", "vfr", "-q:v", "2", "-y", frame_dir / "%04d.jpg"], f"samples-{idx}")
        images = sorted(frame_dir.glob("*.jpg"))
        if len(images) != len(frames):
            raise ValueError("Source ended before requested clip frames")
        if config.get('review_layout') == 'film-window-v1':
            compact_entries.extend((path, f"clip {idx} f{frame} src {picture_in+frame/tl['fps']:.3f}s")
                for path, frame in zip(images, frames))
            continue
        for page in range(0, len(images), 12):
            group = images[page:page + 12]
            with Image.open(group[0]) as first:
                w, h = first.size
            sheet = Image.new("RGB", (w * 3, (h + 26) * math.ceil(len(group) / 3)), "#222222")
            draw = ImageDraw.Draw(sheet)
            for j, path in enumerate(group):
                x, y = j % 3 * w, j // 3 * (h + 26)
                with Image.open(path) as im:
                    sheet.paste(im, (x, y + 26))
                draw.text((x + 5, y + 5), f"clip {idx} f{frames[page+j]} src {picture_in+frames[page+j]/tl['fps']:.3f}s", fill="white")
            out = folder / f"clip-{idx}-page-{page//12}.jpg"; sheet.save(out, quality=90)
            sheets.append(str(out))
    if compact_entries:
        sheets = contact_sheets(folder, compact_entries, prefix='sheet', columns=4, per_page=20)
    if canonical:
        used_shots = {part["shot_id"] for parts in canonical["fragments"].values() for part in parts}
        template = {"source_shots": {shot["id"]: {
            "source_in": shot["source_in"], "source_out": shot["source_out"],
            "points": [[shot["source_in"], None]]} for shot in canonical["shots"] if shot["id"] in used_shots},
            "fragments": canonical["fragments"]}
        measurements["source_shots"] = canonical
    return template, sheets, measurements


class WordTimingPending(Exception):
    def __init__(self, cause):
        self.state_file = cause.state_file
        self.retry_after = cause.retry_after
        super().__init__(str(cause))


def timing_table(root, source, item, identity, rows, selected):
    """Keep readable subtitle cues separate from immutable measured word times."""
    from film_caption import canonical_table, completed_speechmatics_words
    path = root / "source-timing.json"
    if path.exists():
        table = read_json(path)
        if table.get("source_id") != identity["source_id"]:
            raise ValueError("Saved word timing belongs to a different movie")
        return table
    plan = item.get("asr_plan")
    table = None
    if plan:
        from volcano_run import _asr_request_id
        rid = _asr_request_id("speechmatics", plan["providers"]["speechmatics"])
        table = completed_speechmatics_words(source, identity["source_id"], rid)
    if table is None:
        supplied = item.get("words")
        # Only explicitly supplied word objects are word timing; generic transcript
        # and SRT rows never acquire fake word-level precision.
        if supplied and all(isinstance(w, dict) and "word" in w for w in supplied):
            table = canonical_table(supplied, source_id=identity["source_id"], timing_kind="word",
                provider="provided_word_timestamps", request_id=digest(supplied), receipt_sha256=digest(supplied))
        else:
            table = canonical_table(rows, source_id=identity["source_id"], timing_kind="cue")
    atomic_json(path, table)
    return table


def prepare_dialogue_cards(root, source, edit, config, item, identity, table, font):
    from film_caption import layout_captions, CaptionTimingError
    clips = [{"sequence_index": index, "source_in": c["source_in"], "duration": c["source_out"]-c["source_in"],
              "source_id": identity["source_id"], "captions": [row if isinstance(row, (dict, str)) else
              [row[0]-c["source_in"],row[1]-c["source_in"],row[2]] for row in c.get("captions", [])]}
             for index,c in enumerate(edit["sequence"]) if "narration" not in c]
    spec = config.get("dialogue", config["caption"])
    def layout(clip):
        return layout_captions(clip, table, lambda t: font.getlength(t)*spec.get('metric_scale',.84),
                               spec["max_width"], preferred_width=spec.get("cadence_width"))
    missing, timing_problems, repair_issues = [], [], []
    for clip in clips:
        try:
            layout(clip)
        except CaptionTimingError as exc:
            if exc.code != "word_timing_required": raise
            missing.append([clip["source_in"],clip["source_in"]+clip["duration"]])
            timing_problems.append(f"source {clip['source_in']:.3f}–{clip['source_in']+clip['duration']:.3f}s: {exc}")
            repair_issues.append({"sequence_index":clip["sequence_index"],
                "source_in":clip["source_in"], "source_out":clip["source_in"]+clip["duration"],
                "error":str(exc), "captions":clip["captions"],
                "measured_words":[word for word in table.get("words", [])
                    if word["end"]>clip["source_in"]-.15
                    and word["start"]<clip["source_in"]+clip["duration"]+.15]})
    if missing:
        if config.get('reuse_only_narration') or (root/'legacy-inventory.json').exists():
            raise ValueError('Migrated work requires its preserved word timing; no new transcription request was sent')
        plan = item.get("asr_plan")
        if table.get("timing_kind") == "word":
            from film_word_audio import selected_coverage, missing_ranges
            coverage = selected_coverage(root, identity["source_id"], plan) if plan else []
            # A full-source table has no selected-batch coverage. Partial tables
            # must distinguish unmeasured intervals from corrected existing words.
            uncovered = missing_ranges(missing, coverage) if coverage else []
            if not uncovered:
                report={"source_id":identity["source_id"],"edit_id":digest(edit),
                        "table_id":table.get("table_id"),"issues":repair_issues}
                report_path=root/("caption-repair-"+digest(report)[:16]+".json")
                atomic_json(report_path,report)
                raise ValueError("Caption wording differs from measured words; use source-timing.json word_ids with corrected text. No new transcription or voice request was sent. Read the small repair report with the affected measured word IDs: " + str(report_path) + "\n" + "\n".join(timing_problems))
        if not plan: raise ValueError("Selected dialogue needs word timing; provide the server Speechmatics plan before voice")
        from film_word_audio import selected_word_table
        from volcano_run import transcribe_words, TranscriptionPending
        try:
            table = selected_word_table(root, source, identity["source_id"], missing, plan,
                command=command, atomic_json=atomic_json, read_json=read_json,
                file_digest=file_digest, transcribe=transcribe_words)
        except TranscriptionPending as exc:
            raise WordTimingPending(exc) from exc
        atomic_json(root / "source-timing.json", table)
    return [layout(clip) for clip in clips]


def fixed_text_preflight(edit, config):
    """A paid voice cannot fix an oversized title or a narration card."""
    from PIL import ImageFont
    for spec, role, values, label in (
        (config["title"], "bold", edit["title"], "Title"),
        (config["caption"], "body", [card for n in edit.get("narration", []) for card in narration_cards(n, config)], "Narration card"),
    ):
        if not spec.get("fixed_size"):
            continue
        font = ImageFont.truetype(str(Path(config["fonts"][role]["path"]).expanduser()), spec["size"])
        width_limit = spec.get("max_width", config["width"] - 80)
        for text in values:
            if "\n" in text or "\r" in text or font.getlength(text) * spec.get('metric_scale',.84) > width_limit:
                raise ValueError(f"{label} exceeds one line at fixed size {spec['size']}; shorten the title or split narration cards at a meaning boundary before requesting voice: {text}")


def boundary_word_coverage(root, source, table, item, identity, duration):
    """Absence of words is evidence only in completed, source-bound coverage."""
    from film_word_audio import selected_coverage
    coverage = selected_coverage(root,identity['source_id'],item['asr_plan']) if item.get('asr_plan') else []
    provenance=table.get('provenance',{})
    if provenance.get('provider')=='speechmatics' and provenance.get('request_id'):
        from film_caption import completed_speechmatics_words
        complete=completed_speechmatics_words(source,identity['source_id'],provenance['request_id'])
        if complete and complete.get('table_id')==table.get('table_id'):
            coverage=[[0,duration]]
    return coverage


def dialogue_boundary_preflight(root, source, edit, cards, table, config, item, identity, duration):
    """Resolve source choices before reserving voice, with all conflicts in one report."""
    from copy import deepcopy
    from film_continuity import resolve_picture_intervals, clean_dialogue_boundaries, plan_picture_transitions
    fps=config['fps']; narrations={n['id']:n for n in edit.get('narration',[])}
    clips=[]; cursor=0
    for index,segment in enumerate(edit['sequence']):
        if 'narration' in segment:
            clip={'kind':'N','source_in':narrations[segment['narration']]['source'],'frames':1,'captions':[]}
        else:
            clip={'kind':'D','source_in':segment['source_in'],'authored_source_out':segment['source_out'],
                  'frames':round((segment['source_out']-segment['source_in'])*fps),'captions':cards[cursor]}
            cursor+=1
        clip['index']=index
        if segment.get('intentional_jumpback_reason'):
            clip['intentional_jumpback_reason']=segment['intentional_jumpback_reason']
        clips.append(clip)
    tl=resolve_picture_intervals({'fps':fps,'clips':clips},duration)
    catalog=measure_source_catalog(root,source,[(c['picture_in'],c['picture_out']) for c in tl['clips']],config,duration,identity['source_id'])
    coverage=boundary_word_coverage(root,source,table,item,identity,duration)
    planned=clean_dialogue_boundaries(tl,catalog['shots'],words=table.get('words',[]),coverage=coverage,
                                     min_frames=round(.5*fps),max_shift_frames=round(3*fps))
    visual=plan_picture_transitions(planned,catalog['shots'],max_partial_frames=round(.5*fps))
    effective=deepcopy(edit); adjusted_cards=[]
    for before,after in zip(tl['clips'],planned['clips']):
        if after['kind']=='D':
            if before['source_in']!=after['source_in'] or before['frames']!=after['frames']:
                segment=effective['sequence'][after['index']]
                segment['source_in']=after['source_in']
                segment['source_out']=after['source_in']+after['frames']/fps
            adjusted_cards.append(after['captions'])
    kinds={c['index']:c['kind'] for c in clips}
    audit=planned['boundary_audit']
    mapped=[]
    for issue in visual['picture_boundary_issues']:
        issue=dict(issue);issue['picture_index']=issue['clip_index']
        issue['clip_index']=visual['picture_clips'][issue['clip_index']]['origin_index']
        if 'next_clip_index' in issue:
            issue['next_clip_index']=visual['picture_clips'][issue['next_clip_index']]['origin_index']
        mapped.append(issue)
    mapped.extend(issue for issue in audit['issues'] if issue.get('reason')=='same_shot_audio_clock')
    audit['planned_picture_transitions']=visual['picture_transitions']
    audit['issues']=[issue for issue in mapped if kinds[issue['clip_index']]=='D'
                     and ('next_clip_index' not in issue or kinds[issue['next_clip_index']]=='D')]
    for issue in audit['issues']:
        c=planned['clips'][issue['clip_index']]
        a,b=c['picture_in']-2,c['picture_out']+2
        issue['nearby_words']=[w for w in table.get('words',[]) if w['end']>a and w['start']<b]
        issue['source_shots']=[s for s in catalog['shots'] if s['source_out']>a and s['source_in']<b]
    report={**identity,'edit_id':digest(edit),'coverage':coverage,'audit':audit,'effective_edit':effective,
            'instruction':'Keep narration text and paid receipts. Apply the safe effective_edit adjustments, then resolve all listed dialogue selections together using nearby words and measured source shots. Choose complete utterances and clean shot boundaries; never cut a spoken word or include an unrelated next line just to pad a shot. Same-shot source gaps require continuous footage or a different scene selection. Do not render or request replacement voice to repair picture boundaries.'}
    path=root/('boundary-preflight-'+digest(report)[:16]+'.json'); atomic_json(path,report)
    return effective,adjusted_cards,audit,path


def prepare(root, source, config, item, identity, headers=None):
    # Verify all local prerequisites before reserving any billable request.
    try:
        import numpy  # noqa: F401
        from PIL import ImageFont
    except ImportError as exc:
        raise ValueError("Install numpy and Pillow before preparing narration") from exc
    info = read_json(root / "ingest.json") if (root / "ingest.json").exists() else ingest(root, source, item, identity)
    edit = load_value(item.get("edit"))
    validate_edit(edit, info["duration"])
    if ((root/'legacy-inventory.json').is_file() or config.get('reuse_only_narration')) and edit.get('narration') and not edit.get('existing_narration'):
        raise ValueError('기존 작업의 음성·정렬 자료를 existing_narration으로 연결하세요. 새 음성 요청은 차단되어 있으며 기존 접수 기록과 결과는 보존했습니다.')
    from film_tracks import validate as validate_tracks
    validate_tracks(edit,config,info['duration'])
    if config.get("editorial_version"):
        validate_source_order(edit)
    low, high = 0.0, float('inf')
    limits = item.get("duration_limits")
    if limits:
        low = number(limits.get("min"), "minimum duration")
        high = number(limits.get("max"), "maximum duration", low)
    if len(edit["title"]) != len(config["title"]["positions"]):
        raise ValueError("Title line count must match configured positions")
    for spec in config["fonts"].values():
        if not Path(spec["path"]).expanduser().is_file():
            raise ValueError("Install the configured font before requesting paid narration: " + spec["path"])
        ImageFont.truetype(str(Path(spec["path"]).expanduser()), 20)
    for segment in edit["sequence"]:
        palette = config.get("dialogue", {}).get("speaker_colors")
        if "narration" not in segment and palette is not None and str(segment.get("speaker", "")) not in palette:
            raise ValueError("Speaker identity must be assigned before requesting paid narration")
        if segment.get("effect") and not config["effect"].get("enabled", True):
            raise ValueError("This profile does not use effect captions")
    prepare_chrome(root, config)
    fixed_text_preflight(edit, config)
    # Readability is a local prerequisite, before reserving paid narration.
    transcript = read_json(root / "transcript.json") if (root / "transcript.json").is_file() else []
    dialogue_spec = config.get("dialogue", config["caption"])
    dialogue_font = config["fonts"].get("dialogue", config["fonts"]["body"])
    caption_font = ImageFont.truetype(str(Path(dialogue_font["path"]).expanduser()), dialogue_spec["size"])
    canonical_cards = None
    if config.get("editorial_version"):
        table = timing_table(root, source, item, identity, transcript, info.get("subtitle_path"))
        canonical_cards = prepare_dialogue_cards(root, source, edit, config, item, identity, table, caption_font)
    else:
        for segment in edit["sequence"]:
            if "narration" not in segment:
                is_seg_comm = bool(
                    segment.get("caption_type") == "commentary" or segment.get("is_dialogue") is False
                    or dialogue_spec.get("subtitle_type") == "commentary"
                    or edit.get("caption_type") == "commentary"
                )
                if is_seg_comm:
                    commentary_layout({"source_in": segment["source_in"], "captions": [
                        [a-segment["source_in"], b-segment["source_in"], text]
                        for a, b, text in segment.get("captions", [])]}, dialogue_spec, caption_font)
                else:
                    dialogue_layout({"source_in": segment["source_in"], "captions": [
                        [a-segment["source_in"], b-segment["source_in"], text]
                        for a, b, text in segment.get("captions", [])]}, transcript, dialogue_spec, caption_font)
    filters = command(root, ["ffmpeg", "-hide_banner", "-filters"], "filter-prerequisites").decode("utf-8", "replace")
    encoders = command(root, ["ffmpeg", "-hide_banner", "-encoders"], "encoder-prerequisites").decode("utf-8", "replace")
    if not all(re.search(r"\s" + f + r"\s", filters) for f in ("ass", "loudnorm", "cropdetect")) or not re.search(r"\slibx264\s", encoders):
        raise ValueError("FFmpeg needs libass, loudnorm, cropdetect and libx264 before paid narration")
    effective_edit=edit; boundary_audit=None; boundary_path=None
    if config.get('editorial_version')=='story-cards-v1':
        # prepare_dialogue_cards may have completed selected word timing.
        table=read_json(root/'source-timing.json')
        effective_edit,canonical_cards,boundary_audit,boundary_path=dialogue_boundary_preflight(
            root,source,edit,canonical_cards,table,config,item,identity,info['duration'])
        if boundary_audit['issues']:
            return {'ok':True,'status':'edit_required',**identity,'reason':'source_cut_boundaries',
                    'boundary_report_path':str(boundary_path),'boundary_issues':boundary_audit['issues'],
                    'tts_requests_this_action':0,
                    'instruction':'Read the boundary report and revise all affected source selections together before camera work. No voice request or full render was made.'}
    text = "\n".join(n["text"] for n in edit.get("narration", []))
    if text and edit.get('existing_narration'):
        from film_tracks import existing_narration
        tts,audio,receipt=existing_narration(edit['existing_narration'],text,root)
    else:
        tts, audio, receipt = request_tts(root, text, config, headers) if text else (None, None, {"requests": 0})
    tl = compile_timeline(effective_edit, tts, config)
    if tl.get('music') and isinstance(item.get('music'), dict) and item['music'].get('path') == tl['music'].get('path'):
        # Server-verified measurement (lufs) rides with the job; the bed gain uses it instead of re-measuring.
        tl['music'] = {**tl['music'], **{k: v for k, v in item['music'].items() if k in ('lufs', 'gain_db')}}
    card_cursor = 0
    for clip in tl["clips"]:
        if clip["kind"] == "D":
            if clip.get("caption_type") == "commentary" or clip.get("is_dialogue") is False or dialogue_spec.get("subtitle_type") == "commentary":
                clip["captions"] = commentary_layout(clip, dialogue_spec, caption_font)
            else:
                clip["captions"] = canonical_cards[card_cursor] if canonical_cards is not None else dialogue_layout(clip, transcript, dialogue_spec, caption_font)
                card_cursor += 1
    timing = {"narration_seconds":sum(c["duration"] for c in tl["clips"] if c["kind"]=="N"),
              "dialogue_seconds":sum(c["duration"] for c in tl["clips"] if c["kind"]=="D" and c.get("caption_type")!="commentary")}
    comm_sec = sum(c["duration"] for c in tl["clips"] if c.get("caption_type")=="commentary")
    if comm_sec > 0 or any(c.get("caption_type") == "commentary" for c in tl["clips"]):
        timing["commentary_seconds"] = comm_sec
    if limits:
        if not low <= tl["duration"] <= high:
            result = {"ok":True,"status":"edit_required",**identity,"duration":tl["duration"],
                      "frames":tl["frames"],"timing":timing,"tts_receipt":receipt,
                      "audio_path":str(audio) if audio else None,
                      "tts_requests_this_action":int(bool(text) and not receipt.get("reused",False))}
            atomic_json(root / "duration-measurement.json",result)
            return result
    for c in tl["clips"]:
        if not config.get("editorial_version") and c["source_in"] + c["duration"] > info["duration"]:
            raise ValueError("Source is too short for narration; choose an earlier source interval")
    if config.get("editorial_version"):
        from film_continuity import resolve_picture_intervals, picture_timeline
        if 'picture_clips' in tl:
            visual=resolve_picture_intervals(picture_timeline(tl),info['duration'])
            tl['picture_clips']=visual['clips']
            tl['picture_adjustments']=visual['picture_adjustments']
        else:
            tl = resolve_picture_intervals(tl, info["duration"])
    canonical=None
    if config.get('editorial_version')=='story-cards-v1':
        from film_continuity import clean_narration_boundaries, build_picture_fragments, plan_picture_transitions, picture_timeline, same_shot_gaps
        speech_tl=tl if 'picture_clips' in tl else None
        if speech_tl is not None:
            tl={k:v for k,v in picture_timeline(tl).items() if k!='picture_clips'}
        canonical=measure_source_catalog(root,source,[(c['picture_in'],c['picture_out']) for c in tl['clips']],config,info['duration'],identity['source_id'])
        tl=clean_narration_boundaries(tl,canonical['shots'],min_frames=round(.5*config['fps']),max_shift_frames=round(2*config['fps']))
        tl['boundary_audit']['adjustments']=boundary_audit['adjustments']+tl['boundary_audit']['adjustments']
        tl=plan_picture_transitions(tl,canonical['shots'],max_partial_frames=round(.5*config['fps']))
        tl['boundary_audit']['issues']=tl['picture_boundary_issues']+[
            issue for issue in same_shot_gaps(tl,canonical['shots'],include_audio=True)
            if issue['reason']=='same_shot_audio_clock']
        tl['boundary_audit']['picture_transitions']=tl['picture_transitions']
        if tl['boundary_audit']['issues']:
            path=root/('boundary-picture-'+digest(tl)[:16]+'.json')
            atomic_json(path,{'timeline':tl,'source_shots':canonical['shots'],
                             'instruction':'Choose a different continuous picture interval within measured source shots. Preserve the existing narration text, audio and paid receipts.'})
            return {'ok':True,'status':'edit_required',**identity,'reason':'source_cut_boundaries',
                    'boundary_report_path':str(path),'boundary_issues':tl['boundary_audit']['issues'],
                    'tts_receipt':receipt,'audio_path':str(audio) if audio else None,
                    'tts_requests_this_action':int(bool(text) and not receipt.get('reused',False))}
        canonical['fragments']=build_picture_fragments(picture_timeline(tl),canonical['shots'])
        tl['source_catalog_id']=digest(canonical)
        if speech_tl is not None:
            tl={**speech_tl,'picture_clips':picture_timeline(tl)['clips'],
                **{k:tl[k] for k in ('boundary_audit','source_catalog_id','picture_adjustments')}}
    timeline_id = digest({**identity, "edit": edit, "timeline": tl})
    work = root / "edits" / timeline_id; work.mkdir(parents=True, exist_ok=True)
    saved = work / "prepared.json"
    if saved.exists():
        result = read_json(saved)
        result["tts_requests_this_action"] = 0
        atomic_json(root / "current.json", {"timeline_id": timeline_id})
        return result
    from film_continuity import picture_timeline
    visual=picture_timeline(tl)
    content = measure_content(work, source, info, visual["clips"])
    template, sheets, measurements = scene_sheets(work, source, visual, config, canonical=canonical)
    result = {"ok": True, "status": "camera_required", **identity, "timeline_id": timeline_id,
              "timeline_path": str(work / "timeline.json"), "edit_path": str(work / "edit.json"),
              "camera_template": {"timeline_id": timeline_id, **(template if config.get("editorial_version") else {"clips": template})},
              "sample_sheets": sheets, "content_rect": content,
              "duration":tl["duration"],"frames":tl["frames"],"timing":timing,
              "tts_receipt": receipt, "audio_path": str(audio) if audio else None,
              "tts_requests_this_action": int(bool(text) and not receipt.get("reused", False)),
              "boundary_audit":tl.get('boundary_audit'),
              "camera_preview_required":bool(config.get('camera_preview_required') or tl.get('picture_transitions')),
              "boundary_report_path":str(boundary_path) if boundary_audit is not None else None,
              "instruction": "Inspect every scene sheet. Fill normalized source-image horizontal subject coordinates (cx 0..1). Preserve measured source shot boundaries. Source boundaries are planned before camera/render; never mask a partial shot with frozen or cloned frames."}
    atomic_json(work / "timeline.json", tl); atomic_json(work / "edit.json", edit)
    atomic_json(work / 'effective-edit.json',effective_edit)
    atomic_json(work / "measurements.json", measurements); atomic_json(saved, result)
    atomic_json(root / "current.json", {"timeline_id": timeline_id})
    return result


def validate_camera(camera, tl, measurements):
    plans = camera.get("clips", {})
    if set(plans) != {str(c["index"]) for c in tl["clips"]}:
        raise ValueError("Camera plan must cover every clip exactly once")
    for c in tl["clips"]:
        idx, count = str(c["index"]), c["frames"]
        plan = plans[idx]
        a, b = plan.get("trim_start", 0), plan.get("trim_end", count)
        if not isinstance(a, int) or not isinstance(b, int) or not 0 <= a < b <= count or a > 2 or count - b > 2:
            raise ValueError("Only up to two edge flash frames may be trimmed")
        shots = plan.get("shots", [])
        starts = [s.get("start") for s in shots]
        if not starts or starts[0] != 0 or any(type(n) is not int or n < 0 or n >= count for n in starts) or starts != sorted(set(starts)):
            raise ValueError("Camera shots need sorted unique integer starts from frame 0")
        # Coordinates refer to the trimmed output grid, not the original sample grid.
        measured = {n - a for n in measurements[idx]["cuts"] if a < n < b}
        resolved = plan.get("false_positive_cuts", [])
        if any(type(n) is not int or n not in measured for n in resolved):
            raise ValueError("False-positive cut resolutions must name measured output frames")
        if resolved and not str(plan.get("cut_review", "")).strip():
            raise ValueError("Explain why measured cuts are false positives")
        if not measured - set(resolved) <= set(starts):
            raise ValueError("Camera plan misses measured cut frames; inspect scene sheets")
        if any(y - x == 1 for x, y in zip(starts, starts[1:] + [count])):
            raise ValueError("One-frame camera shot would flash; resolve or trim its actual edge")
        for j, s in enumerate(shots):
            if 'view_width' in s:
                number(s['view_width'], 'source shot view width', 1e-9, 1)
            end = starts[j + 1] if j + 1 < len(starts) else count
            points = s.get("points", [])
            frames = [p[0] for p in points if isinstance(p, list) and len(p) == 2]
            if len(frames) != len(points) or not frames or frames[0] != s["start"] or any(type(n) is not int or not s["start"] <= n < end for n in frames) or frames != sorted(set(frames)):
                raise ValueError("Camera points must be sorted within their own shot")
            for n, cx in points:
                number(cx, "camera subject cx", 0, 1)


def camera_expression(plan, sw, crop_width, content_x=0, content_width=None):
    content_width = content_width or sw
    def x(cx):
        return int(round(max(content_x, min(content_x + content_width - crop_width, cx * sw - crop_width / 2)) / 2) * 2)
    def shot(points):
        expr = str(x(points[-1][1]))
        for (a, ca), (b, cb) in reversed(list(zip(points, points[1:]))):
            expr = f"if(lt(n,{b}),{x(ca)}+({x(cb)-x(ca)})*clip((n-{a})/{b-a},0,1),{expr})"
        return expr
    result = shot(plan["shots"][0]["points"])
    for s in plan["shots"][1:]:
        result = f"if(gte(n,{s['start']}),{shot(s['points'])},{result})"
    return result


def picture_filter(plan, count, config, content, sw, source_frame_in=None):
    v, fps = config["video"], config["fps"]
    cw = min(content["width"], int(round(content["height"] * v["width"] / v["height"] / 2) * 2))
    ch = min(content["height"], int(round(cw * v["height"] / v["width"] / 2) * 2))
    y = int((content["y"] + (content["height"] - ch) / 2) // 2 * 2)
    start, end = plan.get("trim_start", 0), plan.get("trim_end", count)
    filters = ["setpts=PTS-STARTPTS", f"fps={fps}", f"trim=start_frame={start}:end_frame={end}", "setpts=PTS-STARTPTS"]
    if source_frame_in is not None:
        filters = [source_grid_filter(source_frame_in, count, fps)]
        if start or end != count:
            filters += [f"trim=start_frame={start}:end_frame={end}", "setpts=PTS-STARTPTS",
                        f"tpad=start_mode=clone:start={start}:stop_mode=clone:stop={count-end}"]
    elif count - (end - start):
        filters.append(f"tpad=stop_mode=clone:stop={count-(end-start)}")
    bg_pad = config.get("pad_color") or config.get("bg_color") or ("white" if config.get("preset") == "인물형" else "black")
    if any('view_width' in shot for shot in plan['shots']):
        # One width belongs to a measured source shot, not an audio block.
        # Split on the exact output-frame grid so width changes never interpolate
        # across cuts and multi-person shots retain their authored field of view.
        pieces = []
        labels = ''.join(f'[view{i}]' for i in range(len(plan['shots'])))
        prefix = ','.join(filters) + f",split={len(plan['shots'])}" + labels
        for i, shot in enumerate(plan['shots']):
            a = shot['start']; b = plan['shots'][i+1]['start'] if i+1<len(plan['shots']) else count
            width = min(content['width'], max(2, round(sw*shot.get('view_width',cw/sw)/2)*2))
            height = content['height'] if 'view_width' in shot else ch
            top = int((content['y']+(content['height']-height)/2)//2*2)
            local = {'shots':[{'start':0,'points':[[n-a,x] for n,x in shot['points']]}]}
            expression = camera_expression(local,sw,width,content['x'],content['width'])
            pieces.append(f"[view{i}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,"
                f"crop={width}:{height}:'{expression}':{top},"
                f"scale={v['width']}:{v['height']}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,"
                f"pad={v['width']}:{v['height']}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,"
                f"pad={config['width']}:{config['height']}:{v['x']}:{v['y']}:{bg_pad}[picture{i}]")
        return ';'.join([prefix,*pieces,''.join(f'[picture{i}]' for i in range(len(pieces)))+f'concat=n={len(pieces)}:v=1:a=0'])
    expression = camera_expression(plan, sw, cw, content["x"], content["width"])
    filters += [f"crop={cw}:{ch}:'{expression}':{y}", f"scale={v['width']}:{v['height']}:flags=lanczos", "setsar=1",
                f"pad={config['width']}:{config['height']}:{v['x']}:{v['y']}:{bg_pad}"]
    return ",".join(filters)


def ass_color(color):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Color must be #RRGGBB")
    return "&H00" + color[5:7] + color[3:5] + color[1:3]


def timestamp(value, fps=None):
    if fps is None:
        t = round(value * 100)
    else:
        # libass uses centiseconds. Choose the centisecond at/before the first
        # affected video frame, so an end boundary cannot leak into that frame
        # and a new card is not delayed by rounding up (e.g. frame 2 at 30 fps).
        frame = math.ceil(value * fps - 1e-7)
        t = math.floor(frame * 100 / fps + 1e-7)
    return f"{t//360000}:{t//6000%60:02d}:{t//100%60:02d}.{t%100:02d}"


def ass_text(text):
    # Host text is data, never libass override tags.
    return str(text).replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N").replace("\r", "")


def dialogue_layout(clip, transcript, spec, font):
    """Keep short cues; split long cues only at matching measured word starts.

    Whole-cue SRT timestamps or different text cannot authorize guessed word
    timing. Such cues retain their full interval and receive readable wrapping.
    """
    if "min_size" not in spec:
        return clip["captions"]
    nominal = spec["size"]
    minimum = int(number(spec["min_size"], "caption minimum size", 1, nominal))
    max_lines = int(number(spec["max_lines"], "caption maximum lines", 1))
    width = number(spec["max_width"], "caption maximum width", 1)
    def size_of(value):
        measured = max((font.getlength(line) for line in value.splitlines()), default=0)
        return min(nominal, math.floor(nominal * width / max(1, measured * spec.get('metric_scale',.84))))
    def fits(value, size):
        return font.getlength(value) * spec.get('metric_scale',.84) * size / nominal <= width
    def within_bounds(value):
        size = size_of(value)
        ascent, descent = font.getmetrics()
        height = (ascent + descent) * size / nominal * len(value.splitlines()) + 2 * spec.get("outline", 0)
        y = spec["position"][1]
        return (size >= minimum and len(value.splitlines()) <= max_lines
                and y-height/2 >= spec.get("safe_top", -float("inf"))
                and y+height/2 <= spec.get("safe_bottom", float("inf")))
    def wrap(value):
        if within_bounds(value):
            return value
        for size in range(int(nominal), minimum-1, -1):
            lines, line = [], ""
            for token in value.split():
                if line and not fits(line + token, size):
                    lines.append(line); line = ""
                # Long unspaced tokens can wrap visually without inventing time.
                for character in token:
                    if line and not fits(line + character, size):
                        lines.append(line); line = ""
                    line += character
                line += " "
            if line.strip(): lines.append(line.strip())
            rendered = "\n".join(part.strip() for part in lines)
            if within_bounds(rendered): return rendered
        raise ValueError("Dialogue caption is too long for readable lines. Keep its words and use existing timed subtitle cues or a shorter source interval; no narration was regenerated.")
    output = []
    for a, b, value in clip["captions"]:
        if within_bounds(value):
            output.append([a, b, value]); continue
        source = clip["source_in"]
        words = [row for row in transcript if len(row) == 3 and row[1] > source+a
                 and row[0] < source+b and isinstance(row[2], str) and clean(row[2])]
        matched = (len(words) > 1 and clean("".join(row[2] for row in words)) == clean(value)
                   and all(words[i][0] >= words[i-1][1] for i in range(1, len(words))))
        if not matched:
            output.append([a, b, wrap(value)]); continue
        positions = [i for i, character in enumerate(value) if character.isalnum()]
        offset, raw_start, groups, current, group_start = 0, 0, [], "", a
        for row in words:
            offset += len(clean(row[2]))
            raw_end = positions[offset] if offset < len(positions) else len(value)
            fragment = value[raw_start:raw_end].strip(); raw_start = raw_end
            joined = (current + " " + fragment).strip()
            boundary = row[0] - source
            if current and not fits(joined, nominal) and group_start < boundary < b:
                groups.append([group_start, boundary, wrap(current)])
                group_start, current = boundary, fragment
            else:
                current = joined
        groups.append([group_start, b, wrap(current)])
        output.extend(groups)
    return output


def commentary_layout(clip, spec, font):
    """Layout creative commentary captions with strict font measurement, line wrapping,
    and safe bounds checks, but without ASR/transcript word fitting.
    """
    if "min_size" not in spec:
        return clip["captions"]
    nominal = spec["size"]
    minimum = int(number(spec["min_size"], "caption minimum size", 1, nominal))
    max_lines = int(number(spec.get("max_lines", 2), "caption maximum lines", 1))
    width = number(spec["max_width"], "caption maximum width", 1)

    def size_of(value):
        measured = max((font.getlength(line) for line in value.splitlines()), default=0)
        return min(nominal, math.floor(nominal * width / max(1, measured * spec.get('metric_scale', .84))))

    def fits(value, size):
        return font.getlength(value) * spec.get('metric_scale', .84) * size / nominal <= width

    def within_bounds(value):
        size = size_of(value)
        ascent, descent = font.getmetrics()
        line_count = len(value.splitlines())
        height = (ascent + descent) * size / nominal * line_count + 2 * spec.get("outline", 0)
        y = spec["position"][1]
        if line_count > 1:
            single_h = (ascent + descent) * size / nominal
            top = y - single_h / 2
            bottom = top + height
            return (size >= minimum and line_count <= max_lines
                    and top >= spec.get("safe_top", -float("inf"))
                    and bottom <= spec.get("safe_bottom", float("inf")))
        return (size >= minimum and line_count <= max_lines
                and y - height / 2 >= spec.get("safe_top", -float("inf"))
                and y + height / 2 <= spec.get("safe_bottom", float("inf")))

    def wrap(value):
        if within_bounds(value):
            return value
        for size in range(int(nominal), minimum - 1, -1):
            lines, line = [], ""
            for token in value.split():
                if line and not fits(line + token, size):
                    lines.append(line); line = ""
                for character in token:
                    if line and not fits(line + character, size):
                        lines.append(line); line = ""
                    line += character
                line += " "
            if line.strip(): lines.append(line.strip())
            rendered = "\n".join(part.strip() for part in lines)
            if within_bounds(rendered): return rendered
        raise ValueError(f"Commentary caption is too long for readable lines or exceeds safe bounds. Text: '{value}'")

    output = []
    for a, b, value in clip["captions"]:
        if within_bounds(value):
            output.append([a, b, value])
        else:
            output.append([a, b, wrap(value)])
    return output


def write_ass(work, tl, config, transcript=()):
    from PIL import ImageFont
    fonts = work / "fonts"; fonts.mkdir(exist_ok=True)
    font_paths = {}
    for kind, spec in config["fonts"].items():
        path = Path(spec["path"]).expanduser().resolve()
        if not path.is_file():
            raise ValueError("Missing configured font: " + str(path))
        dst = fonts / (kind + path.suffix)
        if not dst.exists() or file_digest(dst) != file_digest(path):
            atomic_bytes(dst, path.read_bytes())
        if any(c in spec["name"] for c in ",\r\n"):
            raise ValueError("Invalid font family")
        font_paths[kind] = dst
    head, cap, effect, credit = (config[k] for k in ("title", "caption", "effect", "credit"))
    dlg = config.get("dialogue", cap)
    dialogue_font = "dialogue" if "dialogue" in config["fonts"] else "body"
    styles = [("Head", "bold", head["size"], head["colors"][0], head.get("outline", 0), 8),
              ("Narr", "body", cap["size"], cap["narration_color"], cap.get("outline", 0), 5),
              ("Dialogue", dialogue_font, dlg["size"], dlg["dialogue_color"], dlg.get("outline", 0), 5),
              ("Effect", "effect" if "effect" in config['fonts'] else "body", effect["size"], effect["color"], effect.get("outline", 4), 5),
              ("Credit", "bold", credit["size"], credit["color"], credit.get("outline", 0), 8)]
    text = f"[Script Info]\nScriptType: v4.00+\nPlayResX: {config['width']}\nPlayResY: {config['height']}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    for name, kind, size, color, outline, alignment in styles:
        text += f"Style: {name},{config['fonts'][kind]['name']},{size},{ass_color(color)},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{outline},0,{alignment},20,20,0,1\n"
    text += "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    def tags(value, spec, kind="body", position=None, is_comm=False):
        nominal = spec["size"]
        font = ImageFont.truetype(str(font_paths[kind]), nominal)
        width = max(font.getlength(line) for line in value.splitlines() or [""])
        if spec.get("fixed_size"):
            if not is_comm and ("\n" in value or "\r" in value or width * spec.get('metric_scale',.84) > spec.get("max_width", config["width"] - 80)):
                raise ValueError("Fixed-size one-line text failed preflight; preserve audio and correct the card")
            size = nominal
        else:
            size = min(nominal, math.floor(nominal * spec.get("max_width", config["width"] - 80) / max(1, width * spec.get('metric_scale',.84))))
        x, y = position or spec["position"]
        if is_comm and len(value.splitlines()) > 1:
            ascent, descent = font.getmetrics()
            single_h = (ascent + descent) * size / nominal
            height = single_h * len(value.splitlines())
            y = (y - single_h / 2) + height / 2
        return rf"\pos({x},{y})\fax{spec.get('slant', 0)}\fs{size}"
    def event(a, b, style, value, overrides):
        nonlocal text
        if b > a:
            fps = tl['fps'] if config.get('editorial_version') else None
            text += f"Dialogue: 1,{timestamp(a, fps)},{timestamp(b, fps)},{style},,0,0,0,,{{{overrides}}}{ass_text(value)}\n"
    # A one-line title (second line empty) sits at the profile's single-line block position when
    # the profile declares one; empty lines render nothing (2026-09-16, person title overlap).
    filled = [i for i, value in enumerate(tl["title"]) if str(value).strip()]
    single = head.get("positions_single") if len(filled) == 1 and head.get("positions_single") else None
    for i, value in enumerate(tl["title"]):
        if not str(value).strip():
            continue
        pos = single[0] if single else head["positions"][i]
        event(0, tl["duration"], "Head", value, tags(value, head, "bold", pos) + r"\c" + ass_color(head["colors"][i]) + "&")
    if credit.get("enabled", True):
        event(0, tl["duration"], "Credit", tl["credit"], tags(tl["credit"], credit, "bold"))
    for c in tl["clips"]:
        spec = dlg if c["kind"] == "D" else cap
        kind = dialogue_font if c["kind"] == "D" else "body"
        color_tag = ""
        if c["kind"] == "D" and "speaker_colors" in dlg:
            speaker = str(c.get("speaker", ""))
            if speaker not in dlg["speaker_colors"]:
                raise ValueError("Speaker identity is missing from the configured dialogue palette")
            color_tag = r"\c" + ass_color(dlg["speaker_colors"][speaker]) + "&"
        is_comm = bool(
            c.get("caption_type") == "commentary" or c.get("is_dialogue") is False
            or spec.get("subtitle_type") == "commentary"
        )
        if is_comm:
            captions = commentary_layout(c, spec, ImageFont.truetype(str(font_paths[kind]), spec["size"]))
        else:
            captions = (dialogue_layout(c, transcript, spec, ImageFont.truetype(str(font_paths[kind]), spec["size"]))
                        if c["kind"] == "D" and not spec.get("fixed_size") else c["captions"])
        for j, (a, b, value) in enumerate(captions):
            b = min(b, c["duration"])
            if c["kind"] == "N" and j + 1 < len(c["captions"]):
                b = min(b, c["captions"][j + 1][0])
            event(c["timeline_in"] + max(0, a), c["timeline_in"] + b,
                  "Narr" if c["kind"] == "N" else "Dialogue", value, tags(value, spec, kind, is_comm=is_comm) + color_tag)
        if c.get("effect") and effect.get("enabled", True):
            event(c["timeline_in"] + .1, c["timeline_out"] - .05, "Effect", c["effect"], tags(c["effect"], effect))
    for cue in tl.get('effects',[]):
        face='effect' if 'effect' in config['fonts'] else 'body'
        pos=cue.get('position',effect['position'])
        fw=ImageFont.truetype(str(font_paths[face]),effect['size']).getlength(cue['text'])*effect.get('metric_scale',.84)
        half=min(effect.get('max_width',config['width']-80),fw)/2+effect.get('outline',4)
        position=[max(half+20,min(config['width']-half-20,pos[0])),pos[1]]
        overrides=tags(cue['text'],effect,face,position)
        for key,tag in (('color',r'\c'),('outline_color',r'\3c')):
            if key in cue:overrides+=tag+ass_color(cue[key])+'&'
        event(cue['start_frame']/tl['fps'],cue['end_frame']/tl['fps'],'Effect',cue['text'],overrides)
    atomic_bytes(work / "captions.ass", text.encode("utf-8-sig"))


def build_audio(work, source, audio, tl, config):
    import numpy as np
    from film_tracks import bind_assets, mix_extra
    bind_assets(tl,config)
    rate, fps = config["audio"]["sample_rate"], tl["fps"]
    target = work / "audio.m4a"
    if target.exists() and (work / "audio.json").exists() and read_json(work / "audio.json")["sha256"] == file_digest(target):
        return target
    pcm = work / "master.wav"
    with wave.open(str(pcm), "wb") as out:
        out.setnchannels(2); out.setsampwidth(2); out.setframerate(rate)
        for index,c in enumerate(tl["clips"]):
            clip_src = c.get("source") or source
            ext = Path(clip_src).suffix.lower() if isinstance(clip_src, (str, Path)) else ""
            is_still = ext in ('.jpg', '.jpeg', '.png', '.webp') or c.get("is_still") or c.get("clip_kind") in ('image', 'photo', 'still')
            count = c["frames"] * (rate // fps)
            is_comm = (c.get("caption_type") == "commentary"
                       or config.get("preset") == "인물형"
                       or config.get("caption", {}).get("subtitle_type") == "commentary")
            is_secondary = (c.get("source") is not None and str(c["source"]) != str(source))
            if is_still:
                data = np.zeros((count, 2), dtype="<f4")
            elif is_comm and (is_secondary or (c.get("source_audio_gain_db") is None and not c.get("include_audio"))):
                data = np.zeros((count, 2), dtype="<f4")
            else:
                src, start = (audio, c["audio_in"]) if c["kind"] == "N" else (clip_src, c["source_in"])
                gain = 0 if c["kind"] == "N" else c.get('source_audio_gain_db',config["audio"]["dialogue_gain_db"])
                try:
                    raw = command(work, ["ffmpeg", "-v", "error", "-ss", str(start), "-i", str(src), "-map", "0:a:0",
                                          "-t", str(c["duration"]), "-af", f"volume={gain}dB", "-f", "f32le", "-ar", str(rate), "-ac", "2", "pipe:1"], f"audio-{c['index']}")
                    data = np.frombuffer(raw, dtype="<f4").reshape(-1, 2).copy()
                    if len(data) < count:
                        data = np.pad(data, ((0, count - len(data)), (0, 0)))
                    data = data[:count]
                except Exception:
                    data = np.zeros((count, 2), dtype="<f4")
            fade = min(round(rate * .005), len(data) // 2)
            if fade and np.any(data):
                def continuous(left,right):
                    return (left is not None and right is not None and left['kind']==right['kind']=='D'
                            and (left.get('source') or source) == (right.get('source') or source)
                            and round((left['source_in']+left['duration'])*rate)==round(right['source_in']*rate))
                previous=tl['clips'][index-1] if index else None
                following=tl['clips'][index+1] if index+1<len(tl['clips']) else None
                if not continuous(previous,c):
                    data[:fade] *= np.linspace(0, 1, fade)[:, None]
                if not continuous(c,following):
                    data[-fade:] *= np.linspace(1, 0, fade)[:, None]
            out.writeframes((np.clip(data, -1, 1) * 32767).astype("<i2").tobytes())
    if tl.get('sounds') or any(c.get('source_audio_gain_db') is not None and c['kind']=='N' for c in tl.get('picture_clips',tl['clips'])):
        mix_extra(work,source,tl,config,pcm)
    music_note = None
    if tl.get("music") and tl["music"].get("path"):
        music_note = mix_music_bed(work, pcm, tl["music"], config, tl)
    settings = config["audio"]
    norm = f"loudnorm=I={settings['lufs']}:TP={settings['true_peak']}:LRA={settings.get('lra', 11)}"
    command(work, ["ffmpeg", "-hide_banner", "-i", pcm, "-af", norm + ":print_format=json", "-f", "null", "-"], "loudness")
    stats = json.loads(re.findall(r"\{[^{}]+\}", (work / "logs/loudness.log").read_text(encoding="utf-8", errors="replace"))[-1])
    if all(math.isfinite(float(stats[k])) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")):
        norm += ":linear=true:" + ":".join(f"{k}={stats[v]}" for k, v in [("measured_I", "input_i"), ("measured_TP", "input_tp"), ("measured_LRA", "input_lra"), ("measured_thresh", "input_thresh"), ("offset", "target_offset")])
    else:
        norm = "anull"  # Digital silence has no finite loudness; do not invent a measurement.
    tmp = work / "audio.pending.m4a"
    command(work, ["ffmpeg", "-v", "error", "-i", pcm, "-af", norm, "-c:a", "aac", "-b:a", "192k", "-ar", rate, "-y", tmp], "audio-encode")
    os.replace(tmp, target)
    atomic_json(work / "audio.json", {"sha256": file_digest(target), "loudness_input": stats, "samples": tl["frames"] * rate // fps,
                                      **({"music": music_note} if music_note else {})})
    return target


def mix_music_bed(work, pcm, music, config, tl):
    """Continuous music bed under the (muted) commentary clips (person shorts, 2026-09-16).

    Gain: the bed is set to config['music']['lufs'] (spec MUSIC.lufs) from its measured integrated
    loudness (server-verified `lufs` when present, else measured here), then the master loudnorm
    runs as usual. The song is trimmed to the timeline; only a song shorter than the piece is looped,
    and that fact is recorded in audio.json (the channel uses one continuous track).
    """
    import numpy as np
    rate, fps = config["audio"]["sample_rate"], tl["fps"]
    total = tl["frames"] * (rate // fps)
    path = str(Path(music["path"]).expanduser())
    measured = music.get("lufs")
    if not isinstance(measured, (int, float)):
        command(work, ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=print_format=json",
                       "-f", "null", "-"], "music-loudness")
        stats = json.loads(re.findall(r"\{[^{}]+\}", (work / "logs/music-loudness.log").read_text(encoding="utf-8", errors="replace"))[-1])
        measured = float(stats["input_i"])
    if not math.isfinite(float(measured)):
        raise ValueError("Music file is digital silence; choose an audible track")
    target_lufs = float((config.get("music") or {}).get("lufs", config["audio"]["lufs"]))
    gain_db = target_lufs - float(measured) + float(music.get("gain_db", 0) or 0)
    song = command(work, ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], "music-probe")
    song_sec = float((song or b"0").decode("utf-8", "replace").strip() or 0)
    looped = song_sec + 0.05 < total / rate
    raw = command(work, ["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", path, "-map", "0:a:0",
                         "-t", f"{total / rate:.3f}", "-af", f"volume={gain_db:.3f}dB", "-f", "f32le",
                         "-ar", str(rate), "-ac", "2", "pipe:1"], "music-bed")
    bed = np.frombuffer(raw, dtype="<f4").reshape(-1, 2).copy()
    if len(bed) < total:
        bed = np.pad(bed, ((0, total - len(bed)), (0, 0)))
    bed = bed[:total]
    fade = min(round(rate * .5), len(bed) // 2)
    if fade:
        bed[-fade:] *= np.linspace(1, 0, fade)[:, None]
    with wave.open(str(pcm), "rb") as fh:
        data = np.frombuffer(fh.readframes(fh.getnframes()), dtype="<i2").reshape(-1, 2).astype(float) / 32767
    n = min(len(data), len(bed))
    data[:n] += bed[:n]
    peak = float(np.max(np.abs(data))) if data.size else 0
    headroom = min(1, .98 / peak) if peak else 1
    with wave.open(str(pcm), "wb") as fh:
        fh.setnchannels(2); fh.setsampwidth(2); fh.setframerate(rate)
        fh.writeframes((data * headroom * 32767).astype("<i2").tobytes())
    return {"path": path, "sha256": file_digest(path), "measured_lufs": float(measured), "target_lufs": target_lufs,
            "gain_db": round(gain_db, 3), "song_seconds": round(song_sec, 3), "looped": looped, "pre_master_gain": headroom}


def review_complete(receipt):
    frames, sheets = receipt.get("review_frames"), receipt.get("review_sheets")
    if not isinstance(frames, list) or not frames or not isinstance(sheets, list) or not sheets:
        return False
    if len(frames) != len(receipt.get("review_frame_numbers", [])):
        return False
    hashes = receipt.get("review_sha256", {})
    for name in frames + sheets:
        path = Path(name)
        if not path.is_file() or path.stat().st_size == 0:
            return False
        if hashes.get(name) and file_digest(path) != hashes[name]:
            return False
    return True


def review_frame_numbers(tl, camera):
    """Show every caption, and consecutive frames on both sides of every cut."""
    frames = {0, tl["frames"] - 1}
    fps = tl["fps"]
    from film_continuity import picture_timeline
    for clip in picture_timeline(tl)["clips"]:
        base = round(clip["timeline_in"] * fps)
        for shot in camera["clips"][str(clip["index"] )]["shots"]:
            n = base + shot["start"]
            radius=round(fps*.5) if tl.get('boundary_audit') and shot['start']==0 else 2
            frames.update(range(max(0, n - radius), min(tl["frames"], n + radius + 1)))
    for clip in tl['clips']:
        base=round(clip['timeline_in']*fps)
        for a, b, _ in clip.get("captions", []):
            start = max(0, math.ceil(a * fps - 1e-7))
            end = min(clip["frames"], math.ceil(b * fps - 1e-7))
            if end > start:
                frames.add(base + (start + end - 1) // 2)
    return sorted(frames)


def review_artifacts(work, output, render_id, tl, camera, config=None):
    """Restore evidence directly from the verified MP4, without paid or audio work."""
    from PIL import Image, ImageDraw
    frame_numbers = review_frame_numbers(tl, camera)
    review = work / ("review-" + render_id[:16]); review.mkdir(exist_ok=True)
    expression = frame_select_expression(frame_numbers)
    # A concatenated H.264 stream may change decoder properties between scenes.
    # Keep select's n on the full-output frame clock, instead of resetting it.
    command(work, ["ffmpeg", "-v", "error", "-reinit_filter", "0", "-i", output, "-vf", f"select='{expression}',scale=270:-2",
                   "-fps_mode", "vfr", "-q:v", "2", "-y", review / "%04d.jpg"], "review-frames")
    review_images = [review / f"{i+1:04d}.jpg" for i in range(len(frame_numbers))]
    if any(not path.is_file() or not path.stat().st_size for path in review_images):
        raise ValueError("Output review extraction did not produce every required frame")
    sheet_paths = []
    if config and config.get('review_layout') == 'film-window-v1':
        entries = [(path, f'output frame {frame}') for path, frame in zip(review_images, frame_numbers)]
        # Static titles/chrome are shown in full at the start and end. Every
        # sampled movie/caption/cut frame remains at its original 270px width.
        sheet_paths = contact_sheets(review, [entries[0], entries[-1]], prefix='layout', columns=2, per_page=2)
        sheet_paths += contact_sheets(review, entries, prefix='window', columns=4, per_page=24,
            crop=window_box(config, 270))
    else:
        sheet_paths = contact_sheets(review,
            [(path, f'output frame {frame}') for path, frame in zip(review_images, frame_numbers)],
            prefix='sheet', columns=4, per_page=12)
    frame_paths = [str(p) for p in review_images]
    return {"review_frames": frame_paths, "review_sheets": sheet_paths,
            "review_frame_numbers": frame_numbers,
            "review_sha256": {p: file_digest(p) for p in frame_paths + sheet_paths}}


def prepare_chrome(work, config):
    """Compose only configured matte regions; never obscure the movie window."""
    if not config.get("chrome"):
        return None
    from PIL import Image
    import io
    canvas = Image.new("RGBA", (config["width"], config["height"]), (0,0,0,0))
    video = config["video"]
    for layer in config["chrome"]:
        x,y,w,h = [layer[k] for k in ("x","y","width","height")]
        if any(type(v) is not int for v in (x,y,w,h)) or min(x,y)<0 or min(w,h)<1 or x+w>canvas.width or y+h>canvas.height:
            raise ValueError("Chrome rectangle lies outside canvas")
        if x < video["x"]+video["width"] and x+w > video["x"] and y < video["y"]+video["height"] and y+h > video["y"]:
            raise ValueError("Chrome must not cover the video window")
        with Image.open(Path(layer["path"]).expanduser()) as image:
            image = image.convert("RGBA").resize((w,h),Image.Resampling.LANCZOS)
            canvas.alpha_composite(image,(x,y))
    data = io.BytesIO(); canvas.save(data,format="PNG")
    path = work / "chrome.png"
    atomic_bytes(path,data.getvalue())
    return path


def final_visual_args(work, config, input_label="0:v"):
    """Use the same static composition for preview and final output."""
    chrome = prepare_chrome(work, config)
    # N/(fps*TB) can truncate an exact boundary to the preceding timestamp
    # (frame 510 at 30 fps became 16.999988s with a 90 kHz MP4 timebase).
    # Give ASS an integer frame clock before any overlay/filter rescaling.
    clock = f"settb=expr=1/{config['fps']},setpts=N"
    if chrome:
        return (["-loop", "1", "-framerate", config["fps"], "-i", chrome],
                f"[{input_label}]{clock}[movie];[movie][2:v]overlay=0:0:shortest=1,{clock},ass=captions.ass:fontsdir=fonts[visual]",
                "[visual]")
    return ([], f"[{input_label}]{clock},ass=captions.ass:fontsdir=fonts[visual]", "[visual]")


def render_context(root, source, config, item, identity):
    camera = load_value(item.get("camera"))
    if not isinstance(camera, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(camera.get("timeline_id", ""))):
        raise ValueError("A camera plan bound to prepare.timeline_id is required")
    timeline_id = camera["timeline_id"]
    if not (root / "current.json").exists() or read_json(root / "current.json")["timeline_id"] != timeline_id:
        raise ValueError("Stale camera plan: prepare the current edit and inspect its sheets")
    work = root / "edits" / timeline_id
    prepared = read_json(work / "prepared.json"); tl = read_json(work / "timeline.json")
    if any(prepared[k] != v for k, v in identity.items()):
        raise ValueError("Source/config changed since camera preparation")
    if item.get("edit") is not None and load_value(item["edit"]) != read_json(work / "edit.json"):
        raise ValueError("Edit changed since camera preparation")
    if digest({**identity, "edit": read_json(work / "edit.json"), "timeline": tl}) != timeline_id:
        raise ValueError("Prepared timeline identity differs from saved edit; preserve evidence and prepare again")
    authored_camera = camera
    measurements = read_json(work / "measurements.json")
    if config.get("editorial_version"):
        from film_continuity import project_camera, stabilize_picture_edges, picture_timeline
        camera = {"timeline_id": timeline_id, **project_camera(
            picture_timeline(tl), measurements["source_shots"]["fragments"], camera.get("source_shots", {}))}
        if config.get('editorial_version')=='story-cards-v1':
            if not tl.get('boundary_audit') or tl['boundary_audit'].get('issues'):
                raise ValueError('Prepare clean source boundaries before rendering; preserve all paid audio')
        else:
            camera = stabilize_picture_edges(tl, camera, config.get("edge_flash_max_frames", 0))
    if not config.get("editorial_version"):
        validate_camera(camera, tl, measurements)
    write_ass(work, tl, config)
    from film_tracks import bind_assets
    bind_assets(tl,config)
    saved_edit=read_json(work/'edit.json')
    if saved_edit.get('existing_narration'):
        from film_tracks import verify_existing
        verify_existing(saved_edit['existing_narration'])
    render_id = render_contract_digest(timeline_id, authored_camera, config, tl, source, identity)
    return work, prepared, tl, camera, render_id


def verify_preview(work, preview_id, confirmation):
    """Bind a host's visual check to the current camera and actual image bytes."""
    if not isinstance(confirmation, dict) or confirmation.get("preview_id") != preview_id or confirmation.get("visual_checked") is not True or confirmation.get("blockers") != []:
        raise ValueError("Inspect the current camera preview and correct blockers before full rendering")
    receipt = read_json(work / ("preview-" + preview_id + ".json"))
    if receipt.get("preview_id") != preview_id or not receipt.get("evidence_sha256"):
        raise ValueError("Current preview evidence is missing")
    for path, sha in receipt["evidence_sha256"].items():
        if file_digest(path) != sha:
            raise ValueError("Preview evidence changed; inspect the restored current preview")


def preview(root, source, config, item, identity):
    """Selected frames through the real crop, without TTS or video encoding."""
    from PIL import Image, ImageDraw
    from film_continuity import picture_timeline
    work, prepared, tl, camera, preview_id = render_context(root, source, config, item, identity)
    receipt_path = work / ("preview-" + preview_id + ".json")
    if receipt_path.is_file():
        try:
            verify_preview(work, preview_id, {"preview_id":preview_id,"visual_checked":True,"blockers":[]})
            return read_json(receipt_path)
        except (OSError, ValueError, KeyError):
            pass
    directory = work / ("preview-" + preview_id[:16]); directory.mkdir(exist_ok=True)
    info = read_json(root / "ingest.json")
    chrome = prepare_chrome(work, config)
    pairs, provenance = [], []
    for clip in picture_timeline(tl)["clips"]:
        plan = camera["clips"][str(clip["index"])]; count = clip["frames"]
        frames = {0, count-1}
        shots = plan["shots"]
        for index, shot in enumerate(shots):
            start = shot["start"]; end = shots[index+1]["start"] if index+1<len(shots) else count
            frames.update((start, (start+end-1)//2, end-1))
            frames.update(int(point[0]) for point in shot.get("points", []))
        frames = sorted(frame for frame in frames if 0<=frame<count)
        select = "select='"+frame_select_expression(frames)+"'"
        prefix = "c"+str(clip["index"])
        raw_pattern = directory/(prefix+"-source-%04d.jpg")
        crop_pattern = directory/(prefix+"-crop-%04d.jpg")
        clip_src = clip.get("source") or source
        ext = Path(clip_src).suffix.lower() if isinstance(clip_src, (str, Path)) else ""
        is_still = ext in ('.jpg', '.jpeg', '.png', '.webp') or clip.get("is_still") or clip.get("clip_kind") in ('image', 'photo', 'still')
        if clip_src != source and Path(clip_src).is_file():
            try:
                cp = probe(work, clip_src)
                cv = next((s for s in cp.get("streams", []) if s.get("codec_type") == "video"), None)
                clip_sw = cv["width"] if cv else info["source_width"]
                clip_sh = cv["height"] if cv else info["source_height"]
                clip_content = {"width": clip_sw, "height": clip_sh, "x": 0, "y": 0, "method": "clip_source"}
            except Exception:
                clip_sw, clip_sh, clip_content = info["source_width"], info["source_height"], prepared["content_rect"]
        else:
            clip_sw, clip_sh, clip_content = info["source_width"], info["source_height"], prepared["content_rect"]
        picture = picture_filter(plan, count, config, clip_content, clip_sw, clip.get("source_frame_in") if not is_still else None)
        if is_still:
            decode_input = ["-framerate", str(tl["fps"]), "-loop", "1", "-i", str(clip_src)]
            raw = f"fps={tl['fps']},trim=end_frame={count}"
        elif clip.get("source_frame_in") is not None:
            decode_input = source_grid_input(str(clip_src), clip["source_frame_in"], tl["fps"])
            raw = source_grid_filter(clip["source_frame_in"], count, tl["fps"])
        else:
            decode_input = ["-ss", str(clip.get("source_in", 0)), "-i", str(clip_src)]
            raw = f"setpts=PTS-STARTPTS,fps={tl['fps']},trim=end_frame={count}"
        graph = f"[0:v]split=2[full][crop];[full]{raw},{select},scale=540:304:force_original_aspect_ratio=decrease,pad=540:304:(ow-iw)/2:(oh-ih)/2[original];[crop]{picture}[picture];"
        inputs = []
        if chrome:
            inputs = ["-loop", "1", "-framerate", tl["fps"], "-i", chrome]
            graph += "[picture][1:v]overlay=0:0:shortest=1[decorated];"
        else:
            graph += "[picture]null[decorated];"
        graph += f"[decorated]settb=expr=1/{tl['fps']},setpts=N+{round(clip['timeline_in']*tl['fps'])},ass=captions.ass:fontsdir=fonts,setpts=PTS-STARTPTS,{select},scale=270:480[framed]"
        command(work, ["ffmpeg", "-v", "warning", "-threads", 2,
            *decode_input, *inputs,
            "-filter_complex_threads", 1, "-filter_complex", graph,
            "-map", "[original]", "-fps_mode", "vfr", "-frames:v", len(frames), "-q:v", 2, "-y", raw_pattern,
            "-map", "[framed]", "-fps_mode", "vfr", "-frames:v", len(frames), "-q:v", 2, "-y", crop_pattern], "camera-preview-" + prefix)
        for number, frame in enumerate(frames, 1):
            raw_path = directory / (prefix + f"-source-{number:04d}.jpg")
            crop_path = directory / (prefix + f"-crop-{number:04d}.jpg")
            pair = Image.new("RGB", (820, 520), (25, 25, 25)); draw = ImageDraw.Draw(pair)
            pair.paste(Image.open(raw_path).convert("RGB"), (0, 90))
            pair.paste(Image.open(crop_path).convert("RGB"), (550, 30))
            if clip.get("source_frame_in") is not None:
                source_seconds = (clip["source_frame_in"] + frame) / tl["fps"]
            else:
                source_seconds = clip.get("source_in", 0) + frame / tl["fps"]
            draw.text((8, 8), f"clip {clip['index']} | source {source_seconds:.3f}s | output frame {round(clip['timeline_in']*tl['fps'])+frame}", fill="white")
            draw.text((8, 45), "FULL SOURCE: locate speaker / action", fill="white")
            draw.text((552, 8), "ACTUAL CROP", fill="white")
            path = directory / (prefix + f"-pair-{number:04d}.jpg"); pair.save(path, quality=93)
            pairs.append(str(path)); provenance.append({'clip': clip['index'], 'frame': frame, 'source_seconds': source_seconds, 'pair': str(path)})
    compact = config.get('review_layout') == 'film-window-v1'
    sheets = contact_sheets(directory, [(pairs[0], 'FULL LAYOUT: first'), (pairs[-1], 'FULL LAYOUT: last')],
        prefix='layout', columns=1, per_page=2) if compact else []
    per_page, row_height = (6, 330) if compact else (4, 520)
    for offset in range(0,len(pairs),per_page):
        group=pairs[offset:offset+per_page];sheet=Image.new("RGB",(820,row_height*len(group)),(25,25,25))
        for i,path in enumerate(group):
            with Image.open(path) as image:
                if compact:
                    sheet.paste(image.crop((0, 0, 820, 26)), (0,i*row_height))
                    sheet.paste(image.crop((0,90,540,394)), (0,i*row_height+26))
                    box = window_box(config, 270)
                    sheet.paste(image.crop((550+box[0],30+box[1],550+box[2],30+box[3])),
                        (550,i*row_height+26))
                else:
                    sheet.paste(image,(0,i*row_height))
        path=directory/("sheet-"+str(offset//per_page)+".jpg");sheet.save(path,quality=93);sheets.append(str(path))
    receipt={"ok":True,"status":"previewed",**identity,"timeline_id":work.name,
        "preview_id":preview_id,"preview_sheets":sheets,"preview_pairs":provenance,
        "duration":tl["duration"],"evidence_sha256":{p:file_digest(p) for p in pairs+sheets},
        "camera_preview_required":bool(prepared.get('camera_preview_required')),
        "picture_transitions":tl.get('picture_transitions',[]),
        "tts_requests_this_action":0,"verification":"Host must inspect speaker and context. Preview is sampled, not proof of every video frame."}
    atomic_json(receipt_path,receipt)
    return receipt


def render(root, source, config, item, identity):
    from film_continuity import picture_timeline
    work, prepared, tl, camera, render_id = render_context(root, source, config, item, identity)
    timeline_id = work.name
    if config.get("camera_preview_required") or prepared.get('camera_preview_required'):
        verify_preview(work, render_id, item.get("preview_review"))
    output = work / ("final-" + render_id[:16] + ".mp4")
    receipt_path = work / ("render-" + render_id[:16] + ".json")
    if output.exists() and receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt["output_sha256"] == file_digest(output):
            if not review_complete(receipt):
                receipt.update(review_artifacts(work, output, render_id, tl, camera, config))
                receipt["evidence_restored"] = True
                atomic_json(receipt_path, receipt)
            return receipt
    info = read_json(root / "ingest.json")
    pictures = work / "picture"; pictures.mkdir(exist_ok=True)
    files = []
    started = time.monotonic()
    for c in picture_timeline(tl)["clips"]:
        plan = camera["clips"][str(c["index"])]; count = c["frames"]
        clip_src = c.get("source") or source
        ext = Path(clip_src).suffix.lower() if isinstance(clip_src, (str, Path)) else ""
        is_still = ext in ('.jpg', '.jpeg', '.png', '.webp') or c.get("is_still") or c.get("clip_kind") in ('image', 'photo', 'still')
        if clip_src != source and Path(clip_src).is_file():
            try:
                cp = probe(work, clip_src)
                cv = next((s for s in cp.get("streams", []) if s.get("codec_type") == "video"), None)
                clip_sw = cv["width"] if cv else info["source_width"]
                clip_sh = cv["height"] if cv else info["source_height"]
                clip_content = {"width": clip_sw, "height": clip_sh, "x": 0, "y": 0, "method": "clip_source"}
            except Exception:
                clip_sw, clip_sh, clip_content = info["source_width"], info["source_height"], prepared["content_rect"]
        else:
            clip_sw, clip_sh, clip_content = info["source_width"], info["source_height"], prepared["content_rect"]
        vf = picture_filter(plan, count, config, clip_content, clip_sw, c.get("source_frame_in") if not is_still else None)
        canon = "scale=in_range=auto:in_color_matrix=auto:out_range=tv:out_color_matrix=bt709,format=yuv420p"
        vf_canon = f"{vf},{canon}"
        key = digest({"identity": identity, "source_in": c.get("picture_in", c["source_in"]), "frames": count, "filter": vf_canon, "source": str(clip_src)})
        dest = pictures / (key + ".mp4"); marker = dest.with_suffix(".json")
        if not dest.exists() or not marker.exists() or read_json(marker)["sha256"] != file_digest(dest):
            tmp = pictures / (key + ".pending.mp4")
            if is_still:
                decode_input = ["-framerate", str(tl["fps"]), "-loop", "1", "-i", str(clip_src)]
            elif config.get("editorial_version"):
                decode_input = source_grid_input(str(clip_src), c["source_frame_in"], tl["fps"])
            else:
                decode_input = ["-ss", str(c["source_in"]), "-i", str(clip_src)]
            command(work, ["ffmpeg", "-v", "warning", "-threads", 2, *decode_input,
                           "-map", "0:v:0", "-an", "-vf", vf_canon, "-frames:v", count, "-c:v", "libx264",
                           "-preset", "veryfast", "-crf", 17, "-threads", 2, "-pix_fmt", "yuv420p",
                           "-color_range", "tv", "-colorspace", "bt709", "-color_trc", "bt709", "-color_primaries", "bt709",
                           "-video_track_timescale", 90000, "-y", tmp], f"picture-{c['index']}")
            os.replace(tmp, dest); atomic_json(marker, {"sha256": file_digest(dest)})
        files.append(f"file 'picture/{dest.name}'\nduration {c['duration']:.9f}\n")
    atomic_bytes(work / "concat.txt", "".join(files).encode("utf-8"))
    audio = build_audio(work, source, prepared["audio_path"], tl, config)
    tmp = work / ("pending-" + render_id[:16] + ".mp4")
    visual_inputs, visual_filter, visual_map = final_visual_args(work, config)
    command(work, ["ffmpeg", "-v", "warning", "-f", "concat", "-safe", 0, "-i", "concat.txt", "-i", audio,
                   *visual_inputs, "-filter_complex", visual_filter, "-map", visual_map, "-map", "1:a:0",
                   "-c:v", "libx264", "-preset", "fast", "-crf", 18, "-threads", 4, "-pix_fmt", "yuv420p",
                   "-c:a", "copy", "-t", tl["duration"], "-movflags", "+faststart", "-y", tmp], "final")
    command(work, ["ffmpeg", "-v", "error", "-i", tmp, "-f", "null", "-"], "decode-qc")
    result_probe = probe(work, tmp)
    video = next(s for s in result_probe["streams"] if s["codec_type"] == "video")
    sound = next(s for s in result_probe["streams"] if s["codec_type"] == "audio")
    if int(video.get("nb_frames", 0)) != tl["frames"] or abs(float(video.get("start_time", 0)) - float(sound.get("start_time", 0))) > 1 / tl["fps"]:
        raise ValueError("Rendered frame count or AV start time failed verification")
    os.replace(tmp, output)
    evidence = review_artifacts(work, output, render_id, tl, camera, config)
    receipt = {"ok": True, "status": "rendered", **identity, "timeline_id": timeline_id,
               "render_id": render_id, "output": str(output), "output_sha256": file_digest(output),
               "duration": tl["duration"], "frames": tl["frames"], "render_seconds": time.monotonic() - started,
               "audio_sha256": file_digest(audio), "tts_receipt": prepared["tts_receipt"],
               "tts_requests_this_action": 0,
               "boundary_audit":tl.get('boundary_audit'),
               "picture_transitions":tl.get('picture_transitions',[]),
               "camera_preview_required":bool(prepared.get('camera_preview_required')),
               **evidence, "decode_ok": True,
               "edge_picture_repairs": {key: value["edge_picture_repair"]
                   for key, value in camera["clips"].items() if "edge_picture_repair" in value},
               "verification": "Full decode, frame count and stream starts verified. Host must inspect output frames and assess content; no automated claim of human listening or complete visual fidelity.",
               "platform": {"os": os.name, "system": __import__("platform").system(), "machine": __import__("platform").machine()}}
    atomic_json(receipt_path, receipt)
    return receipt


def verify(root, config, item, identity):
    """Final local evidence check; no regeneration, mutation of media, or network."""
    state = item.get("state") or {}
    timeline_id, render_id = state.get("timeline_id"), state.get("render_id")
    if state.get("status") not in ("rendered", "verified") or not all(
            isinstance(x, str) and re.fullmatch(r"[a-f0-9]{64}", x) for x in (timeline_id, render_id)):
        raise ValueError("Final verification needs the previous rendered receipt")
    if any(state.get(k) != v for k, v in identity.items()):
        raise ValueError("Rendered receipt source, configuration or engine identity is stale")
    if not (root / "current.json").is_file() or read_json(root / "current.json").get("timeline_id") != timeline_id:
        raise ValueError("Rendered receipt does not match the current edit timeline")
    work = root / "edits" / timeline_id
    prepared = read_json(work / "prepared.json")
    tl, edit = read_json(work / "timeline.json"), read_json(work / "edit.json")
    if any(prepared.get(k) != v for k, v in identity.items()) or digest({**identity, "edit": edit, "timeline": tl}) != timeline_id:
        raise ValueError("Saved timeline no longer matches the pinned source/configuration")
    if item.get("edit") is not None and load_value(item["edit"]) != edit:
        raise ValueError("Authored edit changed after the reviewed render")
    from film_tracks import bind_assets
    bind_assets(tl,config)
    if edit.get('existing_narration'):
        from film_tracks import verify_existing
        verify_existing(edit['existing_narration'])
    if item.get("camera") is not None:
        camera = load_value(item["camera"])
        source = item.get("source") or (read_json(root / "ingest.json").get("source") if (root / "ingest.json").is_file() else None)
        expected = render_contract_digest(timeline_id, camera, config, tl, source, identity)
        if not isinstance(camera, dict) or camera.get("timeline_id") != timeline_id or expected != render_id:
            raise ValueError("Authored camera, font content or render contract changed after the reviewed render")
    receipt = read_json(work / ("render-" + render_id[:16] + ".json"))
    output = work / ("final-" + render_id[:16] + ".mp4")
    def native_path(value):
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError("Rendered evidence paths must be absolute native paths")
        # The server changes Windows backslashes to forward slashes. Compare
        # native file identities without weakening hashes or artifact ordering.
        return os.path.normcase(str(Path(value).resolve()))

    for key in (*identity, "timeline_id", "render_id", "output_sha256", "review_frame_numbers"):
        if state.get(key) != receipt.get(key):
            raise ValueError("Previous rendered state differs from local receipt: " + key)
    if native_path(state.get("output")) != native_path(receipt.get("output")):
        raise ValueError("Previous rendered state differs from local receipt: output")
    for key in ("review_frames", "review_sheets"):
        current_paths, saved_paths = state.get(key), receipt.get(key)
        if not isinstance(current_paths, list) or not isinstance(saved_paths, list) or (
                [native_path(p) for p in current_paths] != [native_path(p) for p in saved_paths]):
            raise ValueError("Previous rendered state differs from local receipt: " + key)
    if native_path(receipt.get("output")) != native_path(str(output)) or not output.is_file() or file_digest(output) != receipt.get("output_sha256"):
        raise ValueError("Final video is missing or its SHA256 changed; restore it with the free render action")
    if not review_complete(receipt):
        raise ValueError("Required review frames/sheets are missing or changed; restore evidence with the free render action")
    return {**receipt, "ok": True, "status": "verified", "tts_requests_this_action": 0,
            "verified_unix": time.time(), "verification": "Local final video SHA256, source/config/engine/timeline binding and required review artifacts verified. This does not claim human audio listening."}


def input_identity(item):
    """Bind failed attempts to actual authored/file content without secret fields."""
    value = {"action": item.get("action")}
    for key in ("edit", "camera", "transcript", "words"):
        original = item.get(key)
        if key in ("edit", "camera") and isinstance(original, (str, Path)):
            path = Path(original).expanduser()
            if path.is_file():
                try:
                    original = read_json(path)
                except (ValueError, OSError):
                    original = {"path": str(path), "sha256": file_digest(path)}
        value[key] = original
    selected = item.get("subtitle_path")
    if selected:
        path = Path(selected).expanduser()
        value["subtitle"] = {"path": unicodedata.normalize("NFC", str(path)),
                             "sha256": file_digest(path) if path.is_file() else None}
    else:
        value["subtitle"] = None
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def run(item, headers=None):
    """Run one local action; locally resolved Typecast X-API-KEY stays in memory."""
    started = time.monotonic()
    action = item.get("action")
    attempt = {"action": action}
    identity = {}
    try:
        attempt["input_id"] = input_identity(item)
        root = Path(item["workdir"]).expanduser().resolve(); root.mkdir(parents=True, exist_ok=True)
        from local_paths import resolve_existing_input
        source = resolve_existing_input(item["source"]).resolve()
        if not source.is_file():
            raise ValueError("Source file does not exist")
        config = item["config"]; validate_config(config)
        source_id = file_digest(source)
        st_src = source.stat()
        _ASSET_CACHE[(str(source), (st_src.st_size, st_src.st_mtime_ns))] = source_id
        identity = {"engine_version": ENGINE_VERSION, "engine_sha256": digest({name: file_digest(Path(__file__).with_name(name)) for name in ("film_editor.py", "film_caption.py", "film_continuity.py", "film_word_audio.py", "film_tracks.py")}) if config.get("editorial_version") else file_digest(__file__),
                    "source_id": source_id, "config_id": digest({**config, "chrome_sha256": [file_digest(Path(layer["path"]).expanduser()) for layer in config["chrome"]]}) if config.get("chrome") else digest(config)}
        with file_lock(root / "editor.lock"):
            pin = root / "identity.json"
            if pin.exists() and read_json(pin) != identity:
                previous = read_json(pin)
                compatible = (bool(config.get('editorial_version')) and
                              set(previous) == set(identity) and
                              all(previous[k] == v for k, v in identity.items() if k != 'engine_sha256'))
                if not compatible:
                    raise ValueError("Source or pinned configuration changed; use a new work directory and preserve existing receipts")
                # ENGINE_VERSION is the compatibility contract. A code-only
                # correction rebuilds derived artifacts under a new timeline ID,
                # while source, configuration, paid ledger and old output remain.
                if action not in ('ingest', 'prepare'):
                    return {'ok':False, 'status':'engine_update_required',
                            'error':'Compatible engine update requires preparation with retained audio and receipts',
                            **identity, **attempt}
                history = root / 'identity-history' / (digest(previous) + '.json')
                if not history.exists():
                    atomic_json(history, previous)
                elif read_json(history) != previous:
                    raise ValueError('Engine identity history conflicts; preserve evidence and inspect the record')
            atomic_json(pin, identity)
            if action == "ingest":
                result = ingest(root, source, item, identity)
            elif action == "prepare":
                result = prepare(root, source, config, item, identity, headers)
            elif action == "preview":
                result = preview(root, source, config, item, identity)
            elif action == "render":
                result = render(root, source, config, item, identity)
            elif action == "verify":
                result = verify(root, config, item, identity)
            else:
                raise ValueError("Unknown film editor action")
        result["action_seconds"] = time.monotonic() - started
        return {**result, **attempt}
    except WordTimingPending as exc:
        return {"ok": False, "status": "word_timing_pending", "error": str(exc),
                "state_file": exc.state_file, "retry_after": exc.retry_after, **identity, **attempt}
    except PaidUncertain as exc:
        return {"ok": False, "status": "paid_request_uncertain", "error": str(exc), "request_id": exc.request_id, **identity, **attempt}
    except (ValueError, KeyError, OSError, TypeError) as exc:
        return {"ok": False, "status": "invalid", "error": str(exc), "engine_version": ENGINE_VERSION, **identity, **attempt}
