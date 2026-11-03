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
    PYTHONUTF8=1 py tools/calcopy/vmake_clean.py compare <지운 원본.mp4> <결과 폴더> <a-b> [<a-b> …] [--tier basic] [--dry]   # 같은 구간을 다른 등급으로 지워 원본·지금 결과와 나란히 그림(돈 든다, --dry = 호출 없이 그림 틀만)
"""
from __future__ import annotations

import json
import os
import re
import shutil
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
TIER = "pro"               # 지우기 등급 한 곳 — pro(4크레딧/초, 서버 로그 처리 중앙 256초) · basic(2크레딧/초, 중앙 38초). 품질 비교 = `compare` 명령


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
    try:
        from tools.calcopy.hybrid import server_ai     # 서버 전용(회원 엔진 묶음엔 없다 — engine_bundle HAND_SERVER_ONLY)
    except ImportError:                                 # 회원 PC = 회원 본인 키(10-29 회원 샥템·숏템리폿: 준비 점검이 ImportError 로 1/13 멈춤)
        return "member"
    return "server" if Path(server_ai.KEY).exists() else "member"


def style_mode(version: str | None) -> str:
    """박힌 글자 처리 방식 — 'vmake'(장면마다 골라 지운다) | 'blur'(흐림). 사장님 10-30 "VMake 가 있으면 고급형으로 장면마다 골라서 지우고 없으면 흐림 ·
    사용자가 바꿀 수 있게 · 이 채널(썰템쇼)은 흐림": 회원 설정(text.orig_text — 실행기가 SHORTEM_TEXT_MODE 로) > 판 칸 orig_text.mode > 'vmake'(키 없으면 ready 가 흐림)."""
    m = (os.environ.get("SHORTEM_TEXT_MODE") or "").strip().lower()
    if m in ("vmake", "blur"):
        return m
    if not version:
        return "vmake"
    from tools.calcopy.hybrid import styles
    return str(((styles.load(version).get("orig_text") or {}).get("mode")) or "vmake")


def will_erase(version: str | None) -> bool:
    """이 판의 박힌 글자를 렌더 전에 지우나(판단 주인) — 판 orig_text.mode 가 vmake 이고 돈 막힘(SHORTEM_NO_PAID)이 아니면 True.
    render_bench --plan 관문 ④ 가 True 일 때 글자 컷을 멈추지 않고 '지울 컷'(timeline.vmake_cuts)에 올린다(사장님 10-26 "글자가 많으면 자막을 지우면 되는 거고").
    키 없음(need_key)도 True — 지울 판이고, 키는 flow f_clean 이 렌더 전에 따로 멈춰 받는다.
    ★그 판 형식 단계에 지우기(f_clean)가 없으면 False(10-30 설치본 시험: 쇼핑형 썰템쇼는 지우기 단계가 없는데 True 라 관문이 흐림을 안 넣고
      고치기 질문도 '흐림 넣지 마라' → 남의 로고·자막이 남아 1초 시트에서 4번 걸림). 형식 판단 주인 = flow.erases_text."""
    if not _flow_erases(version):
        return False
    return ready(style_mode(version))["mode"] != "blur"


def _flow_erases(version: str | None) -> bool:
    e = os.environ.get("CALCOPY_ERASE")          # 회원 PC = 지시서가 계획·렌더 명령에 실어 보낸 값(runner_ops 가 그 일 동안만 둔다 — 회원 엔진엔 flow.py 가 없다)
    if e in ("0", "1"):
        return e == "1"
    if not version:
        return True
    try:
        from tools.calcopy.hybrid import flow as F
        return F.erases_text(version)
    except Exception as e:  # noqa: BLE001 — 지시서가 없는 판(우리 PC 옛 길)은 판 칸 그대로
        sys.stderr.write(f"[vmake_clean] 형식 확인 못 함({version}): {type(e).__name__} — 판 칸 그대로" + chr(10))
        return True


def free_ok() -> bool:
    """무료 엔진(회원 GPU, tools/free_subclean)이 이 PC 에 깔렸나."""
    try:
        from tools.free_subclean import engine as FE
    except ImportError:          # 옛 묶음 회원 PC — 엔진 파일이 없으면 기존 길 그대로
        return False
    return FE.installed()


def erase_engine() -> str:
    """지우는 엔진 고르기(판단 주인) — 회원 설정 SHORTEM_ERASE_ENGINE(free|vmake) > 키 있으면 VMake(기존 그대로) > 무료 엔진이 깔렸으면 무료 > ''."""
    e = (os.environ.get("SHORTEM_ERASE_ENGINE") or "").strip().lower()
    if e == "free":
        return "free" if free_ok() else ""
    if e == "vmake" or key_source() == "server" or member_key():
        return "vmake"
    return "free" if free_ok() else ""


# VMake 확정 실패(다시 보내도 같다) — 판단 주인 hard_fail. 시간 초과·일시 실패는 여기 없다(다시 보내면 지워질 수 있다)
HARD_FAILS = (("new_api", r"Switch to New API|새 API 키"), ("not_pro", r"ConsumeDeniedError|60001"), ("sign", r"10021|sign not equals"))
HARD_FIX = {"new_api": "VMake 새 API 키를 넣으면 다음 편부터 지워요", "not_pro": "VMake Pro 요금제에서 지워져요",
            "sign": "VMake 키를 다시 확인해 주세요"}


def hard_fail(text: str) -> str:
    """실패 글 → 확정 실패 종류('new_api'·'not_pro'·'sign') 또는 ''."""
    import re
    return next((k for k, rx in HARD_FAILS if re.search(rx, str(text or ""), re.I)), "")


def ready(mode: str = "vmake") -> dict:
    """돈 없이 '지울 수 있나'만 — {mode: vmake|blur|need_key, why, (fix), (via)}. flow 가 재료 단계에서 먼저 물어 키 없으면 일찍 멈춘다."""
    if mode != "blur" and erase_engine() == "free":   # 돈이 안 드니 SHORTEM_NO_PAID 도 막지 않는다
        return {"mode": "vmake", "via": "free", "why": ""}
    if mode == "blur" or paid_off():
        return {"mode": "blur", "why": "SHORTEM_NO_PAID — 돈 드는 호출 막음" if mode != "blur" else "판 orig_text.mode=blur"}
    if key_source() == "server":
        return {"mode": "vmake", "via": "server", "why": ""}
    if not member_key():                   # 키 없음 = 흐림(사장님 10-30 — 멈추고 키를 묻지 않는다)
        return {"mode": "blur", "why": "VMake 키 없음 — 흐림으로 가린다", "fix": NO_KEY_FIX}
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


def cut_piece(f: Path, a: float, b: float, where: Path | None = None) -> Path:
    """원본 [a,b] 를 소리 없이 다시 굽는다(정확한 시작 프레임 — 덮을 때 같은 시각에 맞추려고). where = 조각을 둘 폴더(뒤에서 지울 때)."""
    out = _piece_name(f, a, b)
    if where:
        out = Path(where) / out.name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(f), "-t", f"{b - a:.3f}", "-an",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)], check=True, stdin=subprocess.DEVNULL)
    return out


def splice_tag(f: Path) -> Path:
    """덮은 구간 표식 — 파일 전체 정체는 바뀌어도 그 구간 밖 그림은 같다는 기록(render_bench.cut_src_id 가 읽는다: 구간 밖 컷을 다시 굽지 않게)."""
    f = Path(f)
    return f.with_name(f.stem + "_spliced.json")


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
    tag = splice_tag(f)
    rec = json.loads(tag.read_text(encoding="utf-8")) if tag.exists() else None
    was = [f.stat().st_size, f.stat().st_mtime_ns]
    if rec is None or rec.get("file") != was:      # 첫 덮기 — 이 파일 정체가 기준
        rec = {"base": was, "spans": []}
    if not keep.exists():
        f.replace(keep)
    tmp.replace(f)
    rec["spans"] += [[a, b, Path(p).stat().st_size] for p, a, b in pieces]
    rec["file"] = [f.stat().st_size, f.stat().st_mtime_ns]
    tag.write_text(json.dumps(rec), encoding="utf-8")
    for c in caches:
        try:
            os.utime(c, None)
        except OSError:
            pass
    return f


def _frames(f: Path) -> int:
    """영상 프레임 수(실제로 세어 본 값)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                          "-of", "csv=p=0", str(f)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return int(out.stdout.strip().split(",")[0])


def _rate(f: Path) -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(f)],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()


def _ledger_pieces(j: Path, fs: list) -> None:
    """합본 호출 줄을 조각별 줄로 바꾼다 — 보낸 초 검사(sent_from_ledger)는 원본 이름·구간으로 센다."""
    p = j.parent / LEDGER
    rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    out = []
    for r in rows:
        if r.get("file") != j.name:
            out.append(r)
            continue
        out.append({**r, "mode": "joined_call", "pieces": len(fs)})
        out += [{**r, "file": f.name, "calls": 0, "joined": j.name, **_sent(f)} for f in fs]
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def send_joined(files: list, send, log=print) -> dict:
    """(주인: VMake 호출 수) 조각을 크기가 같은 것끼리 이어 붙여 1회로 보내고, 지운 결과를 프레임 단위로 다시 조각 자리에 돌려준다.
    숏템메이커 _clean_joined 와 같은 방식(11-01 실측: 호출마다 대기가 복불복이라 13회 = 느린 1건에 걸릴 확률 13배).
    프레임 수가 안 맞으면 그 묶음은 실패로 돌려준다(어긋난 그림을 끼우지 않는다). send(파일 목록) = server_clean·member_clean."""
    import hashlib
    groups: dict = {}
    for f in map(Path, files):
        groups.setdefault((*_wh(f), _rate(f)), []).append(f)
    out = {"cleaned": [], "fail": {}, "calls": 0}
    jobs = {}
    for size, fs in groups.items():
        if len(fs) == 1:
            jobs[fs[0]] = None
            continue
        tag = hashlib.sha1("|".join(f"{f.name}:{f.stat().st_size}" for f in fs).encode()).hexdigest()[:10]
        j = fs[0].with_name(f"joined_{tag}.mp4")
        args = ["ffmpeg", "-v", "error", "-y"]
        for f in fs:
            args += ["-i", str(f)]
        chain = "".join(f"[{i}:v]setsar=1,setpts=PTS-STARTPTS[v{i}];" for i in range(len(fs))) + "".join(f"[v{i}]" for i in range(len(fs))) + f"concat=n={len(fs)}:v=1:a=0[o]"
        subprocess.run(args + ["-filter_complex", chain, "-map", "[o]", "-an", "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(j)],
                       check=True, stdin=subprocess.DEVNULL)
        jobs[j] = fs
    log(f"[vmake] 조각 {len(files)}개 → 호출 {len(jobs)}회로 묶음")
    r = send(list(jobs))
    out["calls"] = r.get("calls", 0)
    out["fail"].update(r.get("fail") or {})
    for j, fs in jobs.items():
        if j.name not in r.get("cleaned", []):
            if fs:
                for f in fs:
                    out["fail"].setdefault(f.name, str((r.get("fail") or {}).get(j.name) or "묶음 실패"))
            continue
        if fs is None:
            out["cleaned"].append(j.name)
            continue
        counts = [_frames(f) for f in fs]      # 같은 fps 끼리만 묶으니 프레임 수 그대로 이어진다
        have = _frames(j)
        if have != sum(counts):
            for f in fs:
                out["fail"][f.name] = f"합본 프레임 불일치 {have} != {sum(counts)}"
            log(f"[vmake] 합본 프레임 불일치 {have} != {sum(counts)} — 끼우지 않는다")
            continue
        at = 0
        for f, n in zip(fs, counts):
            tmp = f.with_name(f.stem + "_vclean" + f.suffix)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(j), "-vf", f"trim=start_frame={at}:end_frame={at + n},setpts=PTS-STARTPTS", "-an",
                            "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(tmp)], check=True, stdin=subprocess.DEVNULL)
            swap_in(f, tmp)
            out["cleaned"].append(f.name)
            at += n
    for j, fs in jobs.items():
        if fs:
            _ledger_pieces(j, fs)
            for x in (j, j.with_name(j.stem + "_orig" + j.suffix)):
                try:
                    x.unlink()
                except OSError:
                    pass
    return out


def clean_used(src_dir: Path, spans: dict, mode: str = "vmake", log=print, spots: dict | None = None) -> dict:
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
    pieces, r = _cut_send(src_dir, spans, rd, spots, log)
    return _put_back(src_dir, spans, pieces, r, rd)


def _cut_send(src_dir: Path, spans: dict, rd: dict, spots: dict | None, log=print, where: Path | None = None) -> tuple:
    """구간마다 잘라 보낸다 — ({이름: [(조각,a,b)…]}, {cleaned, fail, calls}). 돈이 드는 곳은 여기 한 곳(앞에서 기다리는 길·뒤에서 도는 길이 같이 부른다). 원본은 건드리지 않는다."""
    pieces = {n: [(cut_piece(src_dir / n, a, b, where), a, b) for a, b in iv] for n, iv in spans.items()}
    files = [p for ps in pieces.values() for p, _, _ in ps]
    if rd["via"] == "free":
        return pieces, free_clean(files, spots or {}, log=log)
    send = (lambda fs: server_clean(fs, log=log)) if rd["via"] == "server" else (lambda fs: member_clean(fs, member_key(), log=log))
    return pieces, send_joined(files, send, log=log)


def _put_back(src_dir: Path, spans: dict, pieces: dict, r: dict, rd: dict) -> dict:
    """지운 조각을 원본에 덮는다(같은 이름·같은 길이) — 렌더가 원본을 읽지 않는 때에만 부른다."""
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


# ── 뒤에서 지우기(관제 304, 사장님 11-02 '렌더 두 번 금지') ──────────────────────────────────────────
# 장면이 정해지면 지울 구간을 보내고 기다리지 않는다 — 렌더는 임시 흐림으로 끝내고, 결과가 오면 render() 의 구간 교체로 그 구간만 바꾼다. 늦거나 실패하면 흐림 판으로 완성.
# 호출은 앞 길과 같은 함수·같은 구간 한 번(_cut_send) — 다시 보내지 않는다. 뒤 프로세스는 원본을 건드리지 않고 조각만 만든다(렌더가 원본을 읽는 중일 수 있다) — 덮기는 bg_take 가 렌더 사이에.
# 판단 주인: 뒤로 보내도 되나 = bg_start · 끝났나·받기 = bg_take. 회원 PC 는 runner_ops.c_clean_text·c_clean_take 를 지나간다.
BG_DIR = "_vm_bg"          # 원본 폴더 안 — 조각·job.json·result.json
BG_MAX = 1800              # 이보다 오래 답이 없으면 끝난 것으로 치지 않는다(앞 길의 실행기 예산과 같다)


def _spawn_bg(d: Path) -> int:
    """실행기가 끝나도 살아 있는 프로세스로(실행기는 일감마다 뜨고 끝난다)."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "bg_run", str(d)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags).pid


def bg_start(src_dir: Path, spans: dict, mode: str = "vmake", spots: dict | None = None) -> dict | None:
    """(판단 주인 — 뒤로 보내도 되나) 돈 드는 길(VMake)이고 지울 구간이 있으면 뒤 프로세스를 띄운다. None = 앞에서 기다리는 옛 길로(무료 엔진은 이 PC 그래픽카드를 렌더와 나눠 쓰니 뒤로 안 보낸다)."""
    src_dir = Path(src_dir)
    spans = {n: iv for n, iv in (spans or {}).items() if iv and (src_dir / n).exists()}
    rd = ready(mode)
    if not spans or rd["mode"] != "vmake" or rd.get("via") == "free":
        return None
    d = src_dir / BG_DIR
    if bg_busy(src_dir):
        raise RuntimeError("뒤에서 지우는 일이 이미 돈다")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    (d / "job.json").write_text(json.dumps({"src": str(src_dir), "spans": spans, "rd": rd, "spots": spots or {}, "at": time.time()}, ensure_ascii=False), encoding="utf-8")
    _spawn_bg(d)
    return {"mode": "bg", "via": rd.get("via"), "sec": span_sec(spans)}


def bg_run(d: Path) -> None:
    """뒤 프로세스 본체 — 조각을 보내고 결과를 result.json 에(원자적으로). 실패도 결과다."""
    d = Path(d)
    job = json.loads((d / "job.json").read_text(encoding="utf-8"))
    src = Path(job["src"])
    try:
        pieces, r = _cut_send(src, job["spans"], job["rd"], job.get("spots"), log=lambda s: None, where=d)
        out = {"pieces": {n: [[str(p), a, b] for p, a, b in ps] for n, ps in pieces.items()}, **r}
    except Exception as e:  # noqa: BLE001 — 뒤 프로세스 실패는 result 로 알린다(조용히 죽지 않는다)
        out = {"error": f"{type(e).__name__}: {str(e)[:300]}", "calls": 0, "cleaned": [], "fail": {}}
    led = d / LEDGER
    if led.exists():                  # 장부는 원본 폴더 한 곳 — 늦어서 안 쓴 호출도 센다
        rows = json.loads((src / LEDGER).read_text(encoding="utf-8")) if (src / LEDGER).exists() else []
        (src / LEDGER).write_text(json.dumps(rows + json.loads(led.read_text(encoding="utf-8")), ensure_ascii=False, indent=1), encoding="utf-8")
    tmp = d / "result.tmp"
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "result.json")


def bg_busy(src_dir: Path) -> bool:
    d = Path(src_dir) / BG_DIR
    if not (d / "job.json").exists() or (d / "result.json").exists():
        return False
    return time.time() - json.loads((d / "job.json").read_text(encoding="utf-8")).get("at", 0) < BG_MAX


def bg_take(src_dir: Path, wait: float = 0, tick=None) -> dict:
    """(판단 주인 — 뒤 결과 받기) 최대 wait 초 기다려 끝났으면 지운 조각을 원본에 덮고(같은 이름·같은 길이) clean_used 와 같은 꼴로. state = none|running|late|done."""
    src_dir = Path(src_dir)
    d = src_dir / BG_DIR
    if not (d / "job.json").exists():
        return {"state": "none", "done": {}, "cleaned": [], "calls": 0}
    t0 = time.time()
    while not (d / "result.json").exists():
        if not bg_busy(src_dir):
            return {"state": "late", "done": {}, "cleaned": [], "calls": 0, "why": "답이 오지 않음"}
        if time.time() - t0 >= wait:
            return {"state": "running", "done": {}, "cleaned": [], "calls": 0}
        if tick:
            tick()
        time.sleep(min(2.0, max(0.05, wait / 50)))
    job = json.loads((d / "job.json").read_text(encoding="utf-8"))
    r = json.loads((d / "result.json").read_text(encoding="utf-8"))
    if r.get("error"):
        res = {"mode": "error", "done": {}, "cleaned": [], "calls": r.get("calls", 0), "why": r["error"], "error": r["error"]}
    else:
        pieces = {n: [(Path(p), a, b) for p, a, b in ps] for n, ps in r["pieces"].items()}
        res = _put_back(src_dir, job["spans"], pieces, r, job["rd"])
    shutil.rmtree(d, ignore_errors=True)
    return {**res, "state": "done"}


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


def member_clean(files: list, api_key: str, log=print, tier: str = TIER) -> dict:
    """회원 PC — 회원 키로 이 PC 에서 바로. 반환 {cleaned:[이름], calls:n, fail:{이름: 이유}}. 돈이 든다(호출부가 키·동의를 확인한 뒤에만)."""
    if paid_off():
        raise PermissionError("SHORTEM_NO_PAID=1 — VMake 호출 막음")
    from shopping_shorts import vmake_client as VC
    import threading
    from concurrent.futures import ThreadPoolExecutor
    out = {"cleaned": [], "calls": 0, "fail": {}}
    lock = threading.Lock()

    def one(f):
        f = Path(f)
        t0 = time.time()
        tmp = f.with_name(f.stem + "_vclean" + f.suffix)
        with lock:
            out["calls"] += 1
        try:
            VC.remove_subtitles(str(f), api_key, str(tmp), tier=tier, resume_key=f"calcopy:{f.name}:{f.stat().st_size}")
            swap_in(f, tmp)
            with lock:
                out["cleaned"].append(f.name)
                log_entry(f.parent, {"file": f.name, "mode": "member", "ok": True, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f)})
        except Exception as e:  # noqa: BLE001 — 실패는 이유를 남기고 다음 파일(그 파일은 흐림으로)
            with lock:
                out["fail"][f.name] = f"{type(e).__name__}: {str(e)[:200]}"
                log_entry(f.parent, {"file": f.name, "mode": "member", "ok": False, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f), "why": out["fail"][f.name]})
            log(f"[vmake] {f.name} 실패: {out['fail'][f.name]}")

    with ThreadPoolExecutor(SERVER_PAR) as ex:      # 조각마다 7분 안팎 — 서버 길과 같게 동시에(10-26)
        list(ex.map(one, files))
    return out


def free_clean(files: list, spots: dict, log=print) -> dict:
    """회원 GPU 로 지운다(돈 0) — spots = {원본 이름: 자리}(회원 Claude 지정, flow f_spots). 자리 없는 조각은 안 지우고 실패로(흐림이 덮는다)."""
    from tools.free_subclean import engine as FE
    out = {"cleaned": [], "calls": 0, "fail": {}}
    for f in files:                                  # GPU 하나라 차례로
        f = Path(f)
        spot = spots.get(of_piece(f.name)[0])
        if not spot or not (spot.get("bands") or spot.get("emoji")):
            out["fail"][f.name] = "자막 자리 지정 없음"
            continue
        t0 = time.time()
        tmp = f.with_name(f.stem + "_fclean" + f.suffix)
        try:
            res = FE.clean_file(f, tmp, spot)
            swap_in(f, tmp)
            out["cleaned"].append(f.name)
            log_entry(f.parent, {"file": f.name, "mode": "free", "ok": True, "sec": round(time.time() - t0, 1), "calls": 0, **_sent(f), **res})
        except Exception as e:  # noqa: BLE001 — 실패는 이유를 남기고 다음 조각
            out["fail"][f.name] = f"{type(e).__name__}: {str(e)[:200]}"
            log_entry(f.parent, {"file": f.name, "mode": "free", "ok": False, "calls": 0, "why": out["fail"][f.name]})
            log(f"[free] {f.name} 실패: {out['fail'][f.name]}")
    return out


SERVER_PAR = 4      # 서버 VMake 동시 조각 수(조각마다 다른 ssh·다른 파일)


def server_clean(files: list, log=print, timeout: int = SERVER_TIMEOUT, tier: str = TIER) -> dict:
    """우리 PC — 서버의 사장님 키로 지운다(등급 = tier, scratchpad vmake.py 이식). 한 번에 여러 개 보내면 40분 제한에 걸리니 파일마다 따로 부른다.
    resume_key = 끊긴 뒤 같은 조각을 다시 보낼 때 새 과금 없이 이어받는 이름표(member_clean 과 같은 꼴)."""
    if paid_off():
        raise PermissionError("SHORTEM_NO_PAID=1 — VMake 호출 막음")
    from tools.calcopy.hybrid import server_ai
    code = r'''
import json, sys
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline as mp
a=json.loads(sys.stdin.read()); keys=mp._vmake_keys(Store(DB_PATH),0); out={}
for n in a['names']:
    try: mp._vmake_clean(f'/tmp/calcopy_vmake/{n}.mp4', keys, f'/tmp/calcopy_vmake/{n}_clean.mp4', tier=a['tier'], resume_key=a['resume']); out[n]='ok'
    except Exception as e: out[n]=repr(e)[:300]
print('@@JSON@@'+json.dumps(out))
'''
    out = {"cleaned": [], "calls": 0, "fail": {}}
    subprocess.run(["ssh", "-i", server_ai.KEY, server_ai.HOST, f"mkdir -p {REMOTE_DIR}"], check=True, stdin=subprocess.DEVNULL)
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock = threading.Lock()

    def one(f):
        f = Path(f)
        n = f.stem
        t0 = time.time()
        subprocess.run(["scp", "-q", "-i", server_ai.KEY, str(f), f"{server_ai.HOST}:{REMOTE_DIR}/{n}.mp4"], check=True, stdin=subprocess.DEVNULL)
        with lock:
            out["calls"] += 1
        try:
            res = server_ai._ssh_py(code, {"names": [n], "tier": tier, "resume": f"calcopy:{f.name}:{f.stat().st_size}"}, timeout=timeout)
        except Exception as e:  # noqa: BLE001 — 시간 초과면 서버에서는 끝났을 수 있다 → fetch 로 받는다
            res = {n: f"{type(e).__name__}: {str(e)[:200]}"}
        if res.get(n) == "ok":
            fetch(f.parent, [n], log)
            with lock:
                out["cleaned"].append(f.name)
                log_entry(f.parent, {"file": f.name, "mode": "server", "ok": True, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f)})
        else:
            with lock:
                out["fail"][f.name] = str(res.get(n))[:300]
                log_entry(f.parent, {"file": f.name, "mode": "server", "ok": False, "sec": round(time.time() - t0, 1), "calls": 1, **_sent(f), "why": out["fail"][f.name]})
            log(f"[vmake] {f.name} 실패: {out['fail'][f.name]} — 서버에서 끝났으면 `vmake_clean.py fetch {f.parent} {n}`")

    with ThreadPoolExecutor(SERVER_PAR) as ex:      # 조각마다 7분 안팎(10-26 1초 조각 422초) — 차례로 보내면 실행기 예산(15분)을 넘겨 흐림으로 렌더됐다 → 동시에
        list(ex.map(one, files))
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


def compare(src: Path, out: Path, spans: list, tier: str = "basic", dry: bool = False) -> dict:
    """같은 구간을 tier 로 새로 지워 [원본 | 지금 결과 | tier 결과] 를 구간마다 3칸씩 나란히 그린다 — 작업 폴더는 안 건드린다(복사본·결과 폴더에서만).
    src = 이미 지운 <이름>.mp4(옆에 <이름>_orig.mp4). 반환 {sheet, tier, sent_sec, rows:[{span, sec}]}. sec = 장부의 올리기~받기 시간. dry = VMake 없이 원본 칸으로 그림만."""
    src, out = Path(src), Path(out)
    orig = src.with_name(src.stem + "_orig" + src.suffix)
    out.mkdir(parents=True, exist_ok=True)
    base = out / src.name
    if not base.exists():
        shutil.copy2(orig, base)
    pieces = [cut_piece(base, a, b) for a, b in spans]
    r = {"fail": {}} if dry else server_clean(pieces, tier=tier)
    rows, inputs, chain = [], [], []

    def frame(f, at, label):
        inputs.extend(["-ss", f"{at:.3f}", "-i", str(f)])
        i = len(inputs) // 4 - 1
        chain.append(f"[{i}:v]scale=360:-2,trim=end_frame=1,setpts=PTS-STARTPTS[{label}]")

    for k, ((a, b), p) in enumerate(zip(spans, pieces)):
        for j, part in enumerate((0.2, 0.5, 0.8)):
            at = (b - a) * part
            frame(orig, a + at, f"o{k}{j}")
            frame(src, a + at, f"c{k}{j}")
            frame(p, at, f"n{k}{j}")
        rows.append({"span": [a, b], "ok": p.name not in r["fail"], "why": r["fail"].get(p.name, "")})
    n = len(spans) * 3
    for i in range(n):
        k, j = divmod(i, 3)
        chain.append(f"[o{k}{j}][c{k}{j}][n{k}{j}]hstack=3[r{i}]")
    chain.append("".join(f"[r{i}]" for i in range(n)) + f"vstack={n}[v]" if n > 1 else "[r0]copy[v]")
    sheet = out / f"비교_{tier}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", "[v]", "-frames:v", "1", "-q:v", "3", str(sheet)],
                   check=True, stdin=subprocess.DEVNULL)
    led = out / LEDGER
    for row, p in zip(rows, pieces):
        hit = [e for e in (json.loads(led.read_text(encoding="utf-8")) if led.exists() else []) if e.get("file") == p.name]
        row["sec"] = hit[-1].get("sec") if hit else None
    return {"sheet": str(sheet), "tier": tier, "sent_sec": round(sum(b - a for a, b in spans), 3), "rows": rows}


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
    if cmd == "bg_run":          # 뒤 프로세스 — bg_start 가 띄운다
        bg_run(Path(a[0]))
        return 0
    if cmd == "fetch":
        print(fetch(Path(a[0]), a[1:]))
        return 0
    if cmd == "compare":         # compare <지운 원본.mp4> <결과 폴더> <a-b> [<a-b> …] [--tier basic] [--dry]
        dry = "--dry" in a
        a = [x for x in a if x != "--dry"]
        tier = "basic"
        if "--tier" in a:
            i = a.index("--tier")
            tier = a[i + 1]
            del a[i:i + 2]
        print(json.dumps(compare(Path(a[0]), Path(a[1]), [[float(x) for x in s.split("-")] for s in a[2:]], tier, dry), ensure_ascii=False))
        return 0
    if cmd == "log":
        p = Path(a[0]) / LEDGER
        print(p.read_text(encoding="utf-8") if p.exists() else "[]")
        return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
