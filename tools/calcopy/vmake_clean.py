# -*- coding: utf-8 -*-
"""박힌 자막 지우기(VMake) — 해외원본형 원본의 덧씌운 글자를 지우고 원본은 `<이름>_orig.mp4` 로 보존 (관제 263 지시서 08 · 표준 §3-3 C2).

옛 자리: 세션 scratchpad `vmake.py`·`vfetch.sh`(10-22~24 잇템로그 v3 13편 — 쓰는 구간만 잘라 서버 VMake Pro → 원본 소리 붙임).
두 길(둘 다 돈이 든다 — VMake Pro 초당 4크레딧):
  · 우리 PC(사장님 키)  = `server_clean` — 파일을 서버로 보내 서버의 키(mix_pipeline._vmake_keys → keyroute)로 Pro. 40분 제한에 걸려 5400초(10-23 rc=124).
  · 회원 PC(회원 키)    = `member_clean` — 회원 VMake 키('app_key:secret', 환경변수 VMAKE_API_KEY)로 이 PC 에서 바로(vmake_client.remove_subtitles).
    ★10-25 사장님: 박힌 자막 = VMake 로 지운다(흐림 아님) · 회원 PC = 회원 본인 키(~/.shortem/keys/vmake). 키가 없으면 흐림 대체가 아니라 **멈춤**(why/fix).
    판단 주인 = 이 파일 ready()(판 칸 orig_text.mode + key_source)·clean_used() — runner_ops.c_clean_text 는 부르기만 한다.
  · SHORTEM_NO_PAID=1 이면 어느 길도 부르지 않는다(시험·개발 완주의 '돈 0' 스위치).
지운 결과: `<이름>.mp4` = 지운 영상 + 원본 소리(같은 이름이라 대본·재료의 src 가 그대로) · `<이름>_orig.mp4` = 원본 · 장부 `<폴더>/vmake_log.json`(호출마다 한 줄).

★10-26 사장님 "쓰는 구간만": 원본 통째(524초까지)를 보내지 않는다 — **확정 계획(계획_시간표.json)의 컷이 쓰는 구간만** 잘라 VMake →
  지운 조각을 원본 같은 시각에 덮어 같은 이름·같은 길이 파일로 끼운다(`clean_used`). 판단 주인 = 이 파일(구간 계산 used_spans · 자르기 cut_piece ·
  덮기 splice · 보낸 초 검사 sent_check). 회원 flow(runner_ops.c_clean_text)·우리 PC 손 제작(`used` 명령) 둘 다 이 함수를 부른다.
  같은 이름·같은 길이로 끼우는 이유: 재료 ss·장면 경계 캐시(_cutbounds)·관문(cut_content_gate·봉인)·샷 표가 파일 이름+원본 초를 그대로 쓴다 —
  조각 파일(새 이름)로 바꾸면 src·ss 를 다 고쳐야 하고 원본 목록·샷 표와 어긋난다.

    PYTHONUTF8=1 py tools/calcopy/vmake_clean.py used <판> <doc 폴더> [--shots 샷표.json] [--dry]   # ★손 제작 — render_bench --plan 뒤·렌더 전, 쓰는 구간만

    PYTHONUTF8=1 py tools/calcopy/vmake_clean.py fetch <폴더> <이름 …>          # 서버에 끝난 *_clean 만 받아 끼우기(40분 제한으로 끊겼을 때)
    PYTHONUTF8=1 py tools/calcopy/vmake_clean.py log <폴더>                     # 장부 보기
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SERVER_TIMEOUT = 5400      # 서버 한 번 호출 상한(초) — 40분 제한(rc=124)에 걸려 올림(10-23)
REMOTE_DIR = "/tmp/calcopy_vmake"
LEDGER = "vmake_log.json"
FPS = 30                   # 렌더 격자(render_bench.FPS 와 같은 값 — 컷 길이 = 프레임 수/FPS)
PAD = 0.2                  # 쓰는 구간 앞뒤 여유(초) — 30fps 반올림 ±1프레임 + 조각 첫 프레임 여유. 렌더 ss 는 같은 계획이라(경계 캐시 유지 → snap_ss 같은 답) 옮겨지지 않는다
JOIN_GAP = 1.0             # 같은 파일 이웃 구간 사이가 이보다 짧으면 한 조각으로(호출 수를 줄이고 돈은 사이 초만큼만 더)
MIN_PIECE = 1.0            # 조각 하한(초) — 아주 짧은 업로드 실패를 피함(VMake 짧은 영상 한계는 확인 안 함, 하한으로 더 드는 돈 1초 미만)
PIECE_TAG = "__vm_"        # 조각 파일 이름 <stem>__vm_<a>_<b>.mp4 — 장부에서 원본 이름을 되찾는 표식


def paid_off() -> bool:
    return os.environ.get("SHORTEM_NO_PAID") == "1"


MEMBER_KEY_FILE = Path.home() / ".shortem" / "keys" / "vmake"     # 회원 VMake 키 파일('app_key:secret' 한 줄) — 타입캐스트 키와 같은 방식(사장님 10-25)
NO_KEY_WHY = "원본에 박힌 자막을 지우려면 VMake 키가 필요합니다"
NO_KEY_FIX = "설정 화면 '소리' 칸 옆 VMake 키 칸에 본인 VMake 키를 넣고 다시 시작하세요"


def member_key() -> str:
    """회원 VMake 키 자리 한 곳 — 환경변수 VMAKE_API_KEY → ~/.shortem/keys/vmake. 값은 묻지도 출력하지도 않는다(사장님 10-25: 회원 PC = 회원 본인 키)."""
    v = (os.environ.get("VMAKE_API_KEY") or "").strip()
    if v:
        return v
    return MEMBER_KEY_FILE.read_text(encoding="utf-8").strip() if MEMBER_KEY_FILE.exists() else ""


def key_source() -> str:
    """'server' = 우리 PC(서버의 사장님 키 — 서버 접속 키 파일이 있는 PC) · 'member' = 회원 PC(회원 본인 키). CALCOPY_VMAKE_VIA 로 덮을 수 있다."""
    v = (os.environ.get("CALCOPY_VMAKE_VIA") or "").strip().lower()
    if v in ("server", "member"):
        return v
    from tools.calcopy.hybrid import server_ai
    return "server" if Path(server_ai.KEY).exists() else "member"


def style_mode(version: str | None) -> str:
    """판 칸 orig_text.mode — 'vmake'(지운다) | 'blur'(흐림). 판에 없으면 'vmake'(사장님 10-25: 박힌 자막 = VMake 로 지운다)."""
    if not version:
        return "vmake"
    from tools.calcopy.hybrid import styles
    return str(((styles.load(version).get("orig_text") or {}).get("mode")) or "vmake")


def will_erase(version: str | None) -> bool:
    """이 판의 박힌 글자를 렌더 전에 지우나(판단 주인) — 판 orig_text.mode 가 vmake 이고 돈 막힘(SHORTEM_NO_PAID)이 아니면 True.
    render_bench --plan 관문 ④ 가 True 일 때 글자 컷을 멈추지 않고 '지울 컷'(timeline.vmake_cuts)에 올린다(사장님 10-26 "글자가 많으면 자막을 지우면 되는 거고").
    키 없음(need_key)도 True — 지울 판이고, 키는 flow f_clean 이 렌더 전에 따로 멈춰 받는다."""
    return ready(style_mode(version))["mode"] != "blur"


def ready(mode: str = "vmake") -> dict:
    """돈 없이 '지울 수 있나'만 — {mode: vmake|blur|need_key, why, (fix), (via)}. flow 가 재료 단계에서 먼저 물어 키 없으면 일찍 멈춘다."""
    if mode == "blur" or paid_off():
        return {"mode": "blur", "why": "SHORTEM_NO_PAID — 돈 드는 호출 막음" if mode != "blur" else "판 orig_text.mode=blur"}
    if key_source() == "server":
        return {"mode": "vmake", "via": "server", "why": ""}
    if not member_key():
        return {"mode": "need_key", "why": NO_KEY_WHY, "fix": NO_KEY_FIX}
    return {"mode": "vmake", "via": "member", "why": ""}


# ── 쓰는 구간만(사장님 10-26) ─────────────────────────────────────────────
def _merge(iv: list, gap: float = 0.0) -> list:
    out = []
    for a, b in sorted([float(a), float(b)] for a, b in iv if b > a):
        if out and a - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _intersect(x: list, y: list) -> list:
    return _merge([[max(a, c), min(b, d)] for a, b in x for c, d in y if min(b, d) > max(a, c)])


def _subtract(x: list, y: list) -> list:
    out = []
    for a, b in x:
        cur = [[a, b]]
        for c, d in y:
            nxt = []
            for s0, s1 in cur:
                if d <= s0 or c >= s1:
                    nxt.append([s0, s1]); continue
                if c > s0:
                    nxt.append([s0, c])
                if d < s1:
                    nxt.append([d, s1])
            cur = [q for q in nxt if q[1] - q[0] > 1e-3]
        out += cur
    return out


def text_spans(shots_by_src: dict, names) -> dict:
    """샷 표에서 박힌 글자가 있는 샷 구간 {파일 이름: [[a,b]…]} — 글자 판독 주인은 샷 표(flow f_material_got), 여기는 구간만 모은다."""
    out = {}
    for stem, shots in (shots_by_src or {}).items():
        name = next((n for n in names if n.rsplit(".", 1)[0] == stem), None)
        iv = [[float(s["a"]), float(s["b"])] for s in shots or [] if s.get("text")]
        if name and iv:
            out[name] = _merge(iv)
    return out


def gate_text_cuts(T: dict, M: dict, style_name: str) -> set:
    """샷 표가 없는 길(손 제작·preset)의 컷별 '박힌 글자 있나' — 렌더 전 관문 ④ 판정 그대로(render_bench.cut_content_feats + foreign_text,
    TEXT_MIN_HITS, 렌더 조각과 같은 프레임 3장·같은 crop). 흐림 칸은 빼지 않고 잰다(지우면 흐림이 필요 없어지니까). 반환 = 글자 있는 컷 번호."""
    from tools.calcopy.hybrid import render_bench as RB, styles as STY
    st = STY.load(style_name)
    _, _, ww, wh = RB.frame_window(st["frame"])
    src_dir = Path(M["cand_dir"])
    out = set()
    for k, c in enumerate(T.get("cuts") or []):
        src = src_dir / str(c.get("src"))
        if c.get("ss") is None or src.suffix.lower() in RB.IMG_EXT or not src.exists():
            continue
        n = c.get("frames") or (round(c["t1"] * FPS) - round(c["t0"] * FPS))
        m = RB.cut_content_feats(src, c["ss"], n, RB.cut_crop(c, src, (ww, wh)), (ww, wh), None, ())
        if sum(1 for fr in m["text"] if any(RB.foreign_text(f) for f in fr)) >= RB.TEXT_MIN_HITS:
            out.add(k)
    return out


def used_spans(T: dict, durs: dict, text: dict | None = None, done: dict | None = None,
               pad: float = PAD, gap: float = JOIN_GAP, min_piece: float = MIN_PIECE, text_cuts: set | None = None) -> dict:
    """★VMake 규칙 하나(사장님 10-26 "어떤 영상이든 동일 — 장면 편집 후 자막 있는 컷만"): 확정 계획 T(계획_시간표.json timeline)의 컷 중
    **박힌 글자가 있는 컷**이 쓰는 원본 구간만 → VMake 로 보낼 구간 {파일 이름: [[a,b]…]}(원본 초). 글자 없는 컷 = 호출 0.
    컷별 글자 판정은 이미 있는 것만: text = 샷 표 글자 샷 구간(회원 flow, text_spans — 컷과 겹치는 곳만) · text_cuts = 관문 ④ 판정 컷 번호(gate_text_cuts).
    둘 다 None = 검사 기준(쓰는 구간 전체). durs = {이름: 원본 길이}(없는 src = 사진·재료 → 안 보냄) · done = 이미 지운 구간(빼고 보냄).
    T["vmake_cuts"] = 렌더 전 관문 ④ 가 '글자 있음'으로 잰 컷(render_bench --plan, 지우는 판) — 샷 표·text_cuts 와 상관없이 늘 보낸다(관문이 멈추지 않은 대신).
    컷 길이 = 원본에서 쓰는 초(render_bench.src_frames — fit_cut 이 늦춘 컷은 화면보다 짧다)."""
    from tools.calcopy.hybrid.render_bench import src_frames
    force = {int(k) for k in T.get("vmake_cuts") or [] if text is not None or text_cuts is not None}
    raw: dict = {}
    must: dict = {}
    for k, c in enumerate(T.get("cuts") or []):
        n, ss = c.get("src"), c.get("ss")
        if n not in durs or ss is None or (text_cuts is not None and k not in text_cuts and k not in force):
            continue
        sec = src_frames(c) / FPS
        span = [max(0.0, float(ss) - pad), min(float(durs[n]), float(ss) + sec + pad)]
        raw.setdefault(n, []).append(span)
        if k in force:
            must.setdefault(n, []).append(span)
    out = {}
    for n, iv in raw.items():
        iv = _merge(iv, gap)
        if text is not None:
            iv = _merge(_intersect(iv, [[a - pad, b + pad] for a, b in text.get(n) or []]) + must.get(n, []), gap)
        iv = _subtract(iv, (done or {}).get(n) or [])
        fixed = []
        for a, b in iv:
            if b - a < min_piece:
                m = (a + b) / 2
                a, b = max(0.0, m - min_piece / 2), min(float(durs[n]), m + min_piece / 2)
            fixed.append([round(a, 3), round(b, 3)])
        iv = _merge(fixed, gap)
        if iv:
            out[n] = iv
    return out


def span_sec(spans: dict) -> float:
    return round(sum(b - a for iv in spans.values() for a, b in iv), 3)


def sent_check(sent: dict, used: dict, tol: float = 0.5) -> list:
    """결과물 검사 — VMake 로 실제 넘긴 초(sent = {원본 이름: 초}, 장부 in_sec 합)가 쓰는 구간 합(used = used_spans(T, durs) — 글자 교차·뺄 것 없이)을
    넘으면 문제. 통째(524초 원본 전체)면 여기서 걸린다. 반환 = 문제 문장 목록(빈 목록 = 통과)."""
    bad = []
    for n, sec in sent.items():
        lim = sum(b - a for a, b in used.get(n) or [])
        if sec > lim + tol:
            bad.append(f"{n}: VMake 로 {sec:.1f}초 보냄 > 쓰는 구간 {lim:.1f}초(+{tol}) — 쓰지 않는 구간까지 보냈다")
    return bad


def sent_from_ledger(folder: Path, since: str = "") -> dict:
    """장부에서 돈 든 호출(server·member)이 넘긴 초를 원본 이름별로 — in_sec 이 없는 옛 줄(통째 시절)은 그 파일 길이로 센다."""
    p = Path(folder) / LEDGER
    out: dict = {}
    for r in (json.loads(p.read_text(encoding="utf-8")) if p.exists() else []):
        if r.get("mode") not in ("server", "member") or str(r.get("at") or "") < since:
            continue
        name = str(r.get("of") or r.get("file"))
        sec = r.get("in_sec")
        if sec is None:
            f = Path(folder) / name
            orig = f.with_name(f.stem + "_orig" + f.suffix)
            sec = _dur(orig if orig.exists() else f)
        out[name] = round(out.get(name, 0.0) + float(sec or 0), 3)
    return out


def _dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, stdin=subprocess.DEVNULL)
    try:
        return float(r.stdout.decode("utf-8", "replace").strip())
    except ValueError:
        return 0.0


def _wh(f: Path) -> tuple:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(f)],
                       capture_output=True, stdin=subprocess.DEVNULL)
    w, h = r.stdout.decode().strip().split(",")[:2]
    return int(w), int(h)


def _piece_name(f: Path, a: float, b: float) -> Path:
    return f.with_name(f"{f.stem}{PIECE_TAG}{a:.2f}_{b:.2f}{f.suffix}")


def of_piece(name: str) -> tuple:
    """조각 이름 → (원본 이름, [a,b]) · 조각이 아니면 (이름, None)."""
    m = re.match(r"(.+)" + re.escape(PIECE_TAG) + r"([\d.]+)_([\d.]+)(\.\w+)$", name)
    return (m.group(1) + m.group(4), [float(m.group(2)), float(m.group(3))]) if m else (name, None)


def cut_piece(f: Path, a: float, b: float) -> Path:
    """원본 [a,b] 를 소리 없이 다시 굽는다(정확한 시작 프레임 — 덮을 때 같은 시각에 맞추려고)."""
    out = _piece_name(f, a, b)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(f), "-t", f"{b - a:.3f}", "-an",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)], check=True, stdin=subprocess.DEVNULL)
    return out


def splice(f: Path, pieces: list) -> Path:
    """지운 조각들 [(조각 파일, a, b)] 을 원본 f 의 같은 시각에 덮어 같은 이름·같은 길이로 끼운다(원본 소리 그대로). 원본은 <이름>_orig 로(이미 있으면 안 덮음).
    장면 경계 캐시(_cutbounds_<stem>_*)는 그대로 쓴다 — 글자만 지웠고 시간축·편집점은 같다(다시 재면 524초 원본 몇 분 + snap_ss 가 흔들릴 수 있다)."""
    f = Path(f)
    keep = f.with_name(f.stem + "_orig" + f.suffix)
    w, h = _wh(f)
    args, chain, last = ["ffmpeg", "-v", "error", "-y", "-i", str(f)], [], "0:v"
    for i, (p, a, b) in enumerate(pieces, 1):
        args += ["-i", str(p)]
        chain.append(f"[{i}:v]scale={w}:{h},setsar=1,setpts=PTS-STARTPTS+{a:.3f}/TB[p{i}]")
        chain.append(f"[{last}][p{i}]overlay=eof_action=pass:enable='between(t,{a:.3f},{b:.3f})'[v{i}]")
        last = f"v{i}"
    tmp = f.with_name(f.stem + "_s" + f.suffix)
    subprocess.run(args + ["-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "0:a?", "-c:a", "copy",
                           "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(tmp)], check=True, stdin=subprocess.DEVNULL)
    caches = list(f.parent.glob(f"_cutbounds_{f.stem}_*.json"))
    if not keep.exists():
        f.replace(keep)
    tmp.replace(f)
    for c in caches:
        try:
            os.utime(c, None)
        except OSError:
            pass
    return f


def clean_used(src_dir: Path, spans: dict, mode: str = "vmake", log=print) -> dict:
    """쓰는 구간만 지우기(주인) — 구간마다 잘라 VMake(서버 키/회원 키 = ready 판정) → 지운 조각을 원본에 덮어 끼움.
    반환 {mode, via, done:{이름:[[a,b]…]}(지운 구간), cleaned:[이름], calls, sec(보낸 초), why, (fix)}. 구간이 없으면 호출 0."""
    src_dir = Path(src_dir)
    spans = {n: iv for n, iv in (spans or {}).items() if iv and (src_dir / n).exists()}
    if not spans:
        return {"mode": "none", "done": {}, "cleaned": [], "calls": 0, "sec": 0.0, "why": "쓰는 구간에 박힌 글자 없음"}
    rd = ready(mode)
    if rd["mode"] != "vmake":
        for n, iv in spans.items():
            log_entry(src_dir, {"file": n, "mode": rd["mode"], "ok": rd["mode"] == "blur", "calls": 0, "spans": iv, "why": rd["why"]})
        return {**rd, "done": {}, "cleaned": [], "calls": 0, "sec": 0.0}
    pieces = {n: [(cut_piece(src_dir / n, a, b), a, b) for a, b in iv] for n, iv in spans.items()}
    files = [p for ps in pieces.values() for p, _, _ in ps]
    r = server_clean(files, log=log) if rd["via"] == "server" else member_clean(files, member_key(), log=log)
    done, cleaned = {}, []
    for n, ps in pieces.items():
        ok = [(p, a, b) for p, a, b in ps if p.name in r["cleaned"]]
        if ok:
            splice(src_dir / n, ok)
            done[n] = [[a, b] for _, a, b in ok]
            cleaned.append(n)
        for p, _, _ in ps:
            for x in (p, p.with_name(p.stem + "_orig" + p.suffix)):
                try:
                    x.unlink()
                except OSError:
                    pass
    sec = span_sec(spans)
    log_entry(src_dir, {"file": ",".join(spans), "mode": "spans", "ok": not r["fail"], "calls": 0, "spans": spans, "sent_sec": sec, "done": done})
    return {"mode": "vmake", "via": rd["via"], "done": done, "cleaned": cleaned, "calls": r["calls"], "sec": sec,
            "why": "; ".join(f"{k}: {v}" for k, v in r["fail"].items())[:300]}


def plan_spans(doc: Path, shots: dict | None = None, done: dict | None = None, style_name: str | None = None) -> tuple:
    """doc/plan/계획_시간표.json(render_bench --plan 이 쓴다) + 재료.cand_dir → (원본 폴더, 보낼 구간, 쓰는 구간 전체(검사 기준)).
    컷별 글자 판정 = 샷 표(shots, 회원 flow) · 없으면 관문 ④(gate_text_cuts, style_name 필요) — 어느 쪽도 없으면 멈춤(통째·추측 금지)."""
    doc = Path(doc)
    T = json.loads((doc / "plan" / "계획_시간표.json").read_text(encoding="utf-8"))["timeline"]
    M = json.loads((doc / "재료.json").read_text(encoding="utf-8"))
    src = Path(M["cand_dir"]) if M.get("cand_dir") else doc.parent / "src"
    names = {c.get("src") for c in T.get("cuts") or [] if str(c.get("src") or "").lower().endswith((".mp4", ".mov", ".webm", ".mkv"))}
    durs = {n: _dur(src / n) for n in names if (src / n).exists()}
    if shots is not None:
        send = used_spans(T, durs, text_spans(shots, durs), done)
    elif style_name:
        send = used_spans(T, durs, None, done, text_cuts=gate_text_cuts(T, M, style_name))
    else:
        raise ValueError("컷별 박힌 글자 판정 없음 — shots 또는 style_name 이 필요하다")
    return src, send, used_spans(T, durs)


def log_entry(folder: Path, entry: dict) -> None:
    """장부 = <폴더>/vmake_log.json [{at, file, mode, ok, sec, calls, why}] — 호출 0 인 대체(흐림)도 한 줄 남긴다(돈 든 호출 수를 셀 수 있게)."""
    p = Path(folder) / LEDGER
    rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    rows.append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), **entry})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def _sent(f: Path) -> dict:
    """장부 칸 — 넘긴 파일 길이(in_sec)와 조각이면 원본 이름(of)·구간(span). 보낸 초 검사(sent_from_ledger)가 이걸 센다."""
    of, span = of_piece(Path(f).name)
    return {"in_sec": round(_dur(Path(f)), 3), **({"of": of, "span": span} if span else {})}


def swap_in(orig: Path, cleaned_video: Path) -> Path:
    """지운 영상(소리 없음일 수 있다) + 원본 소리 → <이름>.mp4, 원본은 <이름>_orig.mp4 로. 이미 _orig 가 있으면 원본을 덮지 않는다."""
    orig = Path(orig)
    keep = orig.with_name(orig.stem + "_orig" + orig.suffix)
    src_audio = keep if keep.exists() else orig
    tmp = orig.with_name(orig.stem + "_c" + orig.suffix)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(cleaned_video), "-i", str(src_audio), "-map", "0:v", "-map", "1:a?", "-c:v", "copy", "-shortest", str(tmp)],
                   check=True, stdin=subprocess.DEVNULL)
    if not keep.exists():
        orig.replace(keep)
    tmp.replace(orig)
    try:
        if Path(cleaned_video).resolve() != orig.resolve():
            Path(cleaned_video).unlink()
    except OSError:
        pass
    return orig


def member_clean(files: list, api_key: str, log=print, tier: str = "pro") -> dict:
    """회원 PC — 회원 키로 이 PC 에서 바로. 반환 {cleaned:[이름], calls:n, fail:{이름: 이유}}. 돈이 든다(호출부가 키·동의를 확인한 뒤에만)."""
    if paid_off():
        raise PermissionError("SHORTEM_NO_PAID=1 — VMake 호출 막음")
    from shopping_shorts import vmake_client as VC
    out = {"cleaned": [], "calls": 0, "fail": {}}
    for f in files:
        f = Path(f)
        t0 = time.time()
        tmp = f.with_name(f.stem + "_vclean" + f.suffix)
        out["calls"] += 1
        try:
            VC.remove_subtitles(str(f), api_key, str(tmp), tier=tier, resume_key=f"calcopy:{f.name}:{f.stat().st_size}")
            swap_in(f, tmp)
            out["cleaned"].append(f.name)
            log_entry(f.parent, {"file": f.name, "mode": "member", "ok": True, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f)})
        except Exception as e:  # noqa: BLE001 — 실패는 이유를 남기고 다음 파일(그 파일은 흐림으로)
            out["fail"][f.name] = f"{type(e).__name__}: {str(e)[:200]}"
            log_entry(f.parent, {"file": f.name, "mode": "member", "ok": False, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f), "why": out["fail"][f.name]})
            log(f"[vmake] {f.name} 실패: {out['fail'][f.name]}")
    return out


def server_clean(files: list, log=print, timeout: int = SERVER_TIMEOUT) -> dict:
    """우리 PC — 서버의 사장님 키로 Pro(scratchpad vmake.py 이식). 한 번에 여러 개 보내면 40분 제한에 걸리니 파일마다 따로 부른다."""
    if paid_off():
        raise PermissionError("SHORTEM_NO_PAID=1 — VMake 호출 막음")
    from tools.calcopy.hybrid import server_ai
    code = r'''
import json, sys
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline as mp
from shopping_shorts.vmake_client import TIER_PRO
a=json.loads(sys.stdin.read()); keys=mp._vmake_keys(Store(DB_PATH),0); out={}
for n in a['names']:
    try: mp._vmake_clean(f'/tmp/calcopy_vmake/{n}.mp4', keys, f'/tmp/calcopy_vmake/{n}_clean.mp4', tier=TIER_PRO); out[n]='ok'
    except Exception as e: out[n]=repr(e)[:300]
print('@@JSON@@'+json.dumps(out))
'''
    out = {"cleaned": [], "calls": 0, "fail": {}}
    subprocess.run(["ssh", "-i", server_ai.KEY, server_ai.HOST, f"mkdir -p {REMOTE_DIR}"], check=True, stdin=subprocess.DEVNULL)
    for f in files:
        f = Path(f)
        n = f.stem
        t0 = time.time()
        subprocess.run(["scp", "-q", "-i", server_ai.KEY, str(f), f"{server_ai.HOST}:{REMOTE_DIR}/{n}.mp4"], check=True, stdin=subprocess.DEVNULL)
        out["calls"] += 1
        try:
            res = server_ai._ssh_py(code, {"names": [n]}, timeout=timeout)
        except Exception as e:  # noqa: BLE001 — 시간 초과면 서버에서는 끝났을 수 있다 → fetch 로 받는다
            res = {n: f"{type(e).__name__}: {str(e)[:200]}"}
        if res.get(n) == "ok":
            fetch(f.parent, [n], log)
            out["cleaned"].append(f.name)
            log_entry(f.parent, {"file": f.name, "mode": "server", "ok": True, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f)})
        else:
            out["fail"][f.name] = str(res.get(n))[:300]
            log_entry(f.parent, {"file": f.name, "mode": "server", "ok": False, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f), "why": out["fail"][f.name]})
            log(f"[vmake] {f.name} 실패: {out['fail'][f.name]} — 서버에서 끝났으면 `vmake_clean.py fetch {f.parent} {n}`")
    return out


def fetch(folder: Path, names: list, log=print) -> list:
    """서버에 끝난 <이름>_clean.mp4 를 받아 원본 소리를 붙여 끼운다(scratchpad vfetch.sh 이식). 받은 이름 목록."""
    from tools.calcopy.hybrid import server_ai
    got = []
    for n in names:
        local = Path(folder) / f"{n}_v.mp4"
        r = subprocess.run(["scp", "-q", "-i", server_ai.KEY, f"{server_ai.HOST}:{REMOTE_DIR}/{n}_clean.mp4", str(local)], stdin=subprocess.DEVNULL)
        if r.returncode != 0 or not local.exists():
            log(f"[vmake] {n}: 서버에 끝난 파일 없음")
            continue
        swap_in(Path(folder) / f"{n}.mp4", local)
        got.append(n)
        log(f"[vmake] {n} 끼움(원본 = {n}_orig.mp4)")
    return got


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print(__doc__); return 2
    cmd = a.pop(0)
    if cmd in ("server", "clean"):   # 옛 통째 명령 — 사장님 10-26 '쓰는 구간·자막 있는 컷만' 규칙 하나로 닫음
        print("통째 보내기는 닫혔습니다 — `used <판> <doc>` (render_bench --plan 뒤, 자막 있는 컷 구간만)")
        return 2
    if cmd == "used":            # used <판> <doc> [--shots 샷표.json] [--dry] — 손 제작: render_bench --plan 뒤·렌더 전, 쓰는 구간만(주인 clean_used)
        dry = "--dry" in a
        a = [x for x in a if x != "--dry"]
        shots = None
        if "--shots" in a:
            i = a.index("--shots")
            shots = json.loads(Path(a[i + 1]).read_text(encoding="utf-8"))
            del a[i:i + 2]
        src, send, used = plan_spans(Path(a[1]), shots, style_name=a[0])
        print(json.dumps({"src": str(src), "send": send, "send_sec": span_sec(send), "used_sec": span_sec(used)}, ensure_ascii=False))
        if not dry:
            r = clean_used(src, send, style_mode(a[0]))
            print(json.dumps({**r, "check": sent_check(sent_from_ledger(src, r.get("at", "")), used)}, ensure_ascii=False))
        return 0
    if cmd == "fetch":
        print(fetch(Path(a[0]), a[1:]))
        return 0
    if cmd == "log":
        p = Path(a[0]) / LEDGER
        print(p.read_text(encoding="utf-8") if p.exists() else "[]")
        return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
