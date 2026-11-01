# -*- coding: utf-8 -*-
"""렌더 전 관문 ② — 합성한 나레를 **줄마다 받아써서 그 줄 대본 글과** 맞춘다(2026-10-25 전 편 감사 → 사장님 "뿌리·렌더 전").

왜: 소리는 길이(말속도 ±35%)로만 봤다 — 반 줄짜리 되풀이(잇템로그 08 blurtest N2b, 평균의 0.686×)는 그 자로 안 걸리고,
    완성본 받아쓰기 대조(손 도구)는 줄 글을 '아무 데서나' 찾아 되풀이·밀림을 구조적으로 못 잡았다(98 #74·#75·#82).
무엇을: ① 대본 단계(TTS 돈 쓰기 전) tts 글에 영문이 있으면 반려 — 타입캐스트가 'AI'·'LED' 를 건너뛴다(감사 7곳)
        ② 합성 직후 줄 조각 s_<줄>.wav 마다 스피치매틱스(낱말 시각) ↔ 그 줄 글: 되풀이·빠뜨림·앞뒤 줄 섞임(밀림)·머리/꼬리 잘림 = '확정'이면 반려.
        전체 소리(narr_full)도 한 번 받아써 줄 사이 되풀이를 잡는다. 받아쓰기는 wav md5 캐시라 다시 렌더하면 돈 0.
판정 자 = 감사에서 검증한 그대로(알려진 불량 4/4 잡음 · 고친 소리 0건 · 135렌더 확정 1건 = 진짜 결함). 판단 주인 = classify() 한 곳.
부르는 곳 = render_bench.render(계획 --plan 과 렌더 둘 다, 영상 굽기 전).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

CACHE = Path("C:/숏템_칼카피/_cache/asr_sm")

KEEP = re.compile(r"[가-힣A-Za-z0-9]")
DIG = "영일이삼사오육칠팔구"


def _read_num(n: str) -> str:
    n = n.lstrip("0") or "0"
    if len(n) > 12:
        return "".join(DIG[int(c)] for c in n)
    out = ""
    units = ["", "만", "억"]
    groups = []
    while n:
        groups.append(n[-4:]); n = n[:-4]
    for gi in range(len(groups) - 1, -1, -1):
        g = groups[gi].rjust(4, "0")
        s = ""
        for k, c in enumerate(g):
            d = int(c)
            if d == 0: continue
            place = ["천", "백", "십", ""][k]
            s += ("" if (d == 1 and place) else DIG[d]) + place
        if s:
            out += ("" if (s == "일" and gi == 1) else s) + units[gi]
    return out or "영"


def num_to_ko(t: str) -> str:
    t = re.sub(r"(\d),(\d{3})", r"\1\2", t)
    t = re.sub(r"(\d+)\.(\d+)", lambda m: _read_num(m.group(1)) + "점" + "".join(DIG[int(c)] for c in m.group(2)), t)
    return re.sub(r"\d+", lambda m: _read_num(m.group()), t)


def norm(t: str) -> str:
    t = (t or "").replace("%", "퍼센트")
    return "".join(KEEP.findall(num_to_ko(t))).lower()


def has_risky(t: str) -> list:
    """TTS 가 잘못 읽기 쉬운 토막: 영문·약어·숫자·기호."""
    r = []
    r += re.findall(r"[A-Za-z][A-Za-z0-9\-]*", t)
    r += re.findall(r"\d[\d,\.]*\s*[%a-zA-Z가-힣]?", t)
    r += re.findall(r"[~/%&+*#@]", t)
    return r


def _best_window(s: str, ref: str, lo: int, hi: int):
    """s 와 가장 닮은 ref[lo:hi] 안 같은 길이 창 → (ratio, start)."""
    best = (0.0, -1)
    L = len(s)
    lo = max(0, lo); hi = min(len(ref), hi)
    for a in range(lo, max(lo, hi - L) + 1):
        w = ref[a:a + L]
        if not w: continue
        r = SequenceMatcher(None, s, w, autojunk=False).ratio()
        if r > best[0]: best = (r, a)
    return best


def diff_ops(ref: str, hyp: str, rep_min=4, drop_min=2, sub_min=2):
    """ref(보낸 글, norm) vs hyp(들린 소리, norm) → 이상 목록. 위치는 ref/hyp 글자 번호."""
    sm = SequenceMatcher(None, ref, hyp, autojunk=False)
    ops = sm.get_opcodes()
    out = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal": continue
        r, h = ref[i1:i2], hyp[j1:j2]
        extra = h if tag == "insert" else (h if tag == "replace" and len(h) - len(r) >= rep_min else "")
        if extra and len(extra) >= rep_min:
            # 되풀이: 덧붙은 소리가 앞뒤 60자 안 글과 닮았나
            ratio, at = _best_window(extra, ref, i1 - 80, i1 + 40)
            kind = "repeat" if ratio >= 0.7 else "extra"
            out.append({"type": kind, "ref_at": i1, "hyp_at": j1, "ref": r, "heard": h, "sim": round(ratio, 2),
                        "like": ref[at:at + len(extra)] if at >= 0 else ""})
            continue
        if tag == "delete" and len(r) >= drop_min:
            out.append({"type": "drop", "ref_at": i1, "hyp_at": j1, "ref": r, "heard": ""}); continue
        if tag == "replace" and max(len(r), len(h)) >= sub_min:
            if len(r) - len(h) >= 3:
                out.append({"type": "drop", "ref_at": i1, "hyp_at": j1, "ref": r, "heard": h}); continue
            out.append({"type": "subst", "ref_at": i1, "hyp_at": j1, "ref": r, "heard": h}); continue
        out.append({"type": "minor", "tag": tag, "ref_at": i1, "hyp_at": j1, "ref": r, "heard": h})
    return out, sm.ratio()


def char_map(ref: str, hyp: str):
    """ref 글자 번호 → hyp 글자 번호(같은 글자 묶음만, 없으면 None)."""
    m = [None] * len(ref)
    for a, b, n in SequenceMatcher(None, ref, hyp, autojunk=False).get_matching_blocks():
        for k in range(n): m[a + k] = b + k
    return m


def words_chars(words):
    """받아쓴 낱말 목록 → (norm 글, 글자마다 (시작,끝) 초)."""
    s, ts = "", []
    for w in words:
        n = norm(w["w"])
        if not n: continue
        d = (w["e"] - w["s"]) / len(n)
        for k, c in enumerate(n):
            s += c; ts.append((w["s"] + d * k, w["s"] + d * (k + 1)))
    return s, ts


def slice_check(line: str, heard: str, prev: str = "", nxt: str = ""):
    """한 줄 조각: line(그 줄 글 norm) vs heard(조각 소리 norm). prev/nxt = 앞뒤 줄 글(norm)."""
    res = []
    sm = SequenceMatcher(None, line, heard, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= 2]
    if not blocks:
        return [{"type": "nomatch", "ref": line, "heard": heard}], 0.0
    first, last = blocks[0], blocks[-1]
    head_miss = line[:first.a]; head_extra = heard[:first.b]
    tail_miss = line[last.a + last.size:]; tail_extra = heard[last.b + last.size:]
    if len(head_extra) >= 2:
        frm = "prev" if prev and prev.endswith(head_extra[-min(len(head_extra), 6):][-3:]) or (prev and SequenceMatcher(None, head_extra, prev[-len(head_extra):]).ratio() >= 0.6) else "?"
        res.append({"type": "head_extra", "heard": head_extra, "from": frm})
    if len(tail_extra) >= 6 and _best_window(tail_extra, line, 0, len(line))[0] >= 0.7:
        res.append({"type": "repeat", "heard": tail_extra, "like": line, "where": "tail"})
        tail_extra = ""
    if len(tail_extra) >= 2:
        frm = "next" if nxt and SequenceMatcher(None, tail_extra, nxt[:len(tail_extra)]).ratio() >= 0.6 else "?"
        res.append({"type": "tail_extra", "heard": tail_extra, "from": frm})
    if len(head_miss) >= 2:
        res.append({"type": "head_miss", "ref": head_miss, "heard_head": head_extra})
    if len(tail_miss) >= 2:
        res.append({"type": "tail_miss", "ref": tail_miss, "heard_tail": tail_extra})
    inner, ratio = diff_ops(line[first.a:last.a + last.size], heard[first.b:last.b + last.size])
    for o in inner:
        if o["type"] != "minor": res.append(o)
    return res, ratio


# ---------------------------------------------------------------- 받아쓰기(스피치매틱스 · 낱말 시각 · 캐시) — 위스퍼로 떨어지지 않는다(위스퍼 단독 판정 금지)
def _md5(p) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def heard_words(path, lang: str = "ko") -> list[dict]:
    """[{s, e, w, conf}] — 키는 asr_local.speechmatics_key() 한 곳(값은 어디에도 찍지 않는다)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    c = CACHE / f"{_md5(path)}_{lang}.json"
    if c.exists():
        return json.loads(c.read_text(encoding="utf-8"))["words"]
    import requests
    from tools.calcopy.engine.asr_local import speechmatics_key
    key = speechmatics_key()
    if not key:
        raise RuntimeError("스피치매틱스 키 없음 — 줄별 받아쓰기 관문을 못 돈다")
    H = {"Authorization": f"Bearer {key}"}
    cfg = {"type": "transcription", "transcription_config": {"language": lang, "operating_point": "enhanced"}}
    for attempt in range(3):
        try:
            with open(path, "rb") as f:
                r = requests.post("https://asr.api.speechmatics.com/v2/jobs", headers=H, files={"data_file": f}, data={"config": json.dumps(cfg)}, timeout=120)
            r.raise_for_status()
            break
        except Exception as e:  # noqa: BLE001 — 3번 실패면 관문이 멈춘다(조용히 넘기지 않음)
            if attempt == 2:
                raise RuntimeError(f"스피치매틱스 올리기 실패 {type(e).__name__}")
            time.sleep(5)
    jid = r.json()["id"]
    for _ in range(200):
        time.sleep(2)
        s = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}", headers=H, timeout=30).json()["job"]["status"]
        if s == "done":
            break
        if s in ("rejected", "deleted"):
            raise RuntimeError(f"스피치매틱스 {s}")
    t = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}/transcript?format=json-v2", headers=H, timeout=60).json()
    words = [{"s": it["start_time"], "e": it["end_time"], "w": it["alternatives"][0]["content"], "conf": it["alternatives"][0].get("confidence")}
             for it in t.get("results", []) if it.get("type") == "word"]
    c.write_text(json.dumps({"file": str(path), "words": words}, ensure_ascii=False), encoding="utf-8")
    return words


ASR_PAR = 4      # 동시 받아쓰기 상한(스피치매틱스 작업 동시 수 — 10-26 검수 단축 ⑥: 렌더 전 ② 9작업이 순차로 56초)


def prefetch(paths, lang: str = "ko", workers: int = ASR_PAR) -> dict:
    """여러 소리를 동시에 받아쓰기해 캐시(CACHE)에 채운다 — 판정은 그대로(뒤 순차 heard_words 가 캐시를 읽는다).
    실패한 것은 {경로: 오류 이름}으로 돌려주고, 같은 파일을 뒤 순차 호출이 다시 겪어 그 자리에서 멈춘다(조용히 넘기지 않음)."""
    from concurrent.futures import ThreadPoolExecutor
    todo, seen = [], set()
    for p in paths:
        if not p or not Path(p).exists():
            continue
        m = _md5(p)
        if m in seen or (CACHE / f"{m}_{lang}.json").exists():
            continue
        seen.add(m)
        todo.append(p)
    if len(todo) < 2:
        return {}
    errs = {}
    with ThreadPoolExecutor(max_workers=min(workers, len(todo))) as ex:
        futs = [(p, ex.submit(heard_words, p, lang)) for p in todo]
        for p, f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001 — 뒤 순차 호출이 같은 파일로 다시 겪는다(여기선 기록만)
                errs[str(p)] = type(e).__name__
    return errs


def _dur(path) -> float | None:
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return None


def full_check(lines, narr_path):
    """lines = [{id,text}] (보낸 글 기준). 전체 소리 받아쓰기와 정렬해 줄별 이상."""
    words = heard_words(narr_path)
    hyp, ts = words_chars(words)
    refs = [norm(l["text"]) for l in lines]
    ref = "".join(refs)
    ops, ratio = diff_ops(ref, hyp)
    bounds, x = [], 0
    for r in refs:
        bounds.append((x, x + len(r))); x += len(r)

    def line_of(i):
        for k, (a, b) in enumerate(bounds):
            if a <= i < b: return k
        return len(bounds) - 1
    out = []
    for o in ops:
        if o["type"] == "minor": continue
        k = line_of(o["ref_at"])
        t = ts[o["hyp_at"]][0] if o["hyp_at"] < len(ts) else (ts[-1][1] if ts else None)
        out.append({**o, "line": lines[k]["id"], "t": round(t, 2) if t is not None else None})
    return {"ratio": round(ratio, 3), "heard": " ".join(w["w"] for w in words), "issues": out, "n_words": len(words)}


def slice_checks(lines, paths):
    """paths = {id: wav}. 줄 조각마다 slice_check + 말속도(글자/초, 조각 길이 기준)."""
    res, rates = {}, {}
    ids = [l["id"] for l in lines]
    N = {l["id"]: norm(l["text"]) for l in lines}
    for k, l in enumerate(lines):
        p = paths.get(l["id"])
        if not p: continue
        words = heard_words(p)
        h, ts = words_chars(words)
        prev = N[ids[k - 1]] if k > 0 else ""
        nxt = N[ids[k + 1]] if k + 1 < len(ids) else ""
        iss, ratio = slice_check(N[l["id"]], h, prev, nxt)
        d = _dur(p)
        if words:
            talk = max(0.1, words[-1]["e"] - words[0]["s"])
        else:
            talk = d or 0.1
        rates[l["id"]] = len(N[l["id"]]) / talk
        res[l["id"]] = {"wav": str(p), "dur": d, "heard": " ".join(w["w"] for w in words), "ratio": round(ratio, 3), "issues": iss,
                        "talk": round(talk, 2), "words": words}
    if rates:
        mean = sum(rates.values()) / len(rates)
        for i, r in rates.items():
            res[i]["rate"] = round(r, 2); res[i]["rate_rel"] = round(r / mean, 2)
    # 이웃 조각과 맞물림: 줄 k 꼬리 빠짐이 줄 k+1 머리 덧붙음이면 shift 확정
    for k in range(len(ids) - 1):
        a, b = res.get(ids[k]), res.get(ids[k + 1])
        if not a or not b: continue
        tm = [x for x in a["issues"] if x["type"] == "tail_miss"]
        he = [x for x in b["issues"] if x["type"] == "head_extra"]
        if tm and he:
            from difflib import SequenceMatcher
            r = SequenceMatcher(None, tm[0]["ref"], he[0]["heard"]).ratio()
            if r >= 0.5:
                a["issues"].append({"type": "shift_out", "to": ids[k + 1], "ref": tm[0]["ref"], "heard_in_next": he[0]["heard"], "sim": round(r, 2)})
        te = [x for x in a["issues"] if x["type"] == "tail_extra"]
        hm = [x for x in b["issues"] if x["type"] == "head_miss"]
        if te and hm:
            from difflib import SequenceMatcher
            r = SequenceMatcher(None, te[0]["heard"], hm[0]["ref"]).ratio()
            if r >= 0.5:
                b["issues"].append({"type": "shift_in_prev", "from": ids[k], "ref": hm[0]["ref"], "heard_in_prev": te[0]["heard"], "sim": round(r, 2)})
    return res


def classify(full, slices):
    """확정 / 의심 갈라 목록으로."""
    sure, maybe = [], []
    for o in (full or {}).get("issues", []):
        t = o["type"]
        e = {"line": o["line"], "src": "full", "type": t, "ref": o.get("ref"), "heard": o.get("heard"), "t": o.get("t")}
        if t == "repeat" and len(o["heard"]) >= 6:
            sure.append({**e, "type": "TTS 되풀이", "like": o.get("like"), "sim": o.get("sim")})
        elif t == "repeat":
            maybe.append({**e, "type": "TTS 되풀이(짧음)", "like": o.get("like")})
        elif t == "drop" and len(o["ref"]) >= 5:
            sure.append({**e, "type": "TTS 빠뜨림"})
        elif t == "drop":
            maybe.append({**e, "type": "빠짐(짧음)"})
        elif t == "extra" and len(o["heard"]) >= 6:
            maybe.append({**e, "type": "덧붙은 소리"})
        elif t == "subst":
            maybe.append({**e, "type": "발음/읽기 다름"})
    for lid, s in (slices or {}).items():
        for o in s["issues"]:
            t = o["type"]
            e = {"line": lid, "src": "slice", "heard_slice": s["heard"]}
            if t in ("shift_out", "shift_in_prev"):
                sure.append({**e, "type": "줄 경계 밀림", **{k: v for k, v in o.items() if k != "type"}})
            elif t == "tail_extra" and o.get("from") == "next" and len(o["heard"]) >= 3:
                sure.append({**e, "type": "다음 줄 머리가 이 조각에", "heard": o["heard"]})
            elif t == "head_extra" and o.get("from") == "prev" and len(o["heard"]) >= 3:
                sure.append({**e, "type": "앞 줄 꼬리가 이 조각에", "heard": o["heard"]})
            elif t == "tail_miss" and len(o["ref"]) >= 4:
                sure.append({**e, "type": "줄 꼬리 안 들림", "ref": o["ref"], "heard": o.get("heard_tail")})
            elif t == "head_miss" and len(o["ref"]) >= 4:
                sure.append({**e, "type": "줄 머리 안 들림", "ref": o["ref"], "heard": o.get("heard_head")})
            elif t in ("tail_miss", "head_miss", "head_extra", "tail_extra"):
                maybe.append({**e, "type": t, **{k: v for k, v in o.items() if k != "type"}})
            elif t == "repeat" and len(o["heard"]) >= 6:
                sure.append({**e, "type": "TTS 되풀이(조각)", "heard": o["heard"], "like": o.get("like")})
            elif t == "drop" and len(o["ref"]) >= 5:
                sure.append({**e, "type": "빠뜨림(조각)", "ref": o["ref"], "heard": o.get("heard")})
            elif t in ("repeat", "drop", "extra", "subst", "nomatch"):
                maybe.append({**e, "type": t + "(조각)", "ref": o.get("ref"), "heard": o.get("heard")})
        rr = s.get("rate_rel")
        if rr is not None and not (0.65 <= rr <= 1.35):
            maybe.append({"line": lid, "src": "slice", "type": "말속도 이상", "rate_rel": rr, "rate": s.get("rate")})
    return sure, maybe


# ---------------------------------------------------------------- 관문
def latin_lines(S: dict) -> list[tuple[str, list[str]]]:
    """대본 단계(TTS 전): 읽는 글에 영문이 든 줄 — 판단 주인 = hybrid/script_audit.latin_in(관문 G-1, 10-25 한 벌로 모음). 여기는 문만."""
    from tools.calcopy.hybrid import script_audit as SA
    return SA.latin_in(S)


def verify(lines: list[dict], paths: dict, narr=None, out: Path | None = None) -> dict:
    """lines = [{id, text(보낸 tts 글)}] · paths = {id: 줄 조각 wav} · narr = 전체 소리(있으면). 반환 {ok, sure, maybe}. out 이 있으면 json 저장."""
    prefetch(([narr] if narr else []) + [v for v in paths.values() if v])      # 9작업 동시(상한 ASR_PAR) — 뒤 순차 판정은 캐시를 읽는다
    full = full_check(lines, narr) if narr and Path(narr).exists() else None
    sl = slice_checks(lines, {k: v for k, v in paths.items() if v and Path(v).exists()})
    sure, maybe = classify(full, sl)
    rep = {"ok": not sure, "sure": sure, "maybe": maybe,
           "heard": {k: v["heard"] for k, v in sl.items()}, "full_heard": (full or {}).get("heard")}
    if out:
        Path(out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


NAME_GAP_MAX = 0.15      # 인물 이름 글자 사이 쉼 상한(초) — 넘으면 '최 은경'처럼 끊겨 들린다(관제 266 키치잇 04: 쉼표 표기 '최, 은경' 틈 0.16초)


def name_breaks(S: dict, align: dict | None) -> list[str]:
    """렌더 전 관문(이름 끊김) — 합성 글자 시각(align, 줄을 이은 전체)에서 인물 이름(대본 celeb + 발음 사전 이름) 글자 사이 쉼이 NAME_GAP_MAX 를 넘는 자리.
    이름 글자 사이에 쉼표·띄어쓰기가 끼어 있어도(사전 표기 '최, 은경') 같은 이름으로 찾는다. 글자 시각이 없으면 판정 못 함 → 빈 목록(부른 쪽이 로그)."""
    import re as _re
    from tools.calcopy.engine import name_dict as ND
    if not align or not align.get("characters"):
        return []
    ch = align["characters"]
    st, en = align["character_start_times_seconds"], align["character_end_times_seconds"]
    names = sorted({n for n in ([S.get("celeb")] + list(ND.load()["names"])) if n and len(n) >= 2}, key=len, reverse=True)
    txt = "".join(ch)
    out = []
    for n in names:
        for m in _re.finditer(r"[\s,]*".join(map(_re.escape, n)), txt):
            idx = [i for i in range(m.start(), m.end()) if ch[i] not in " ,"]
            for a, b in zip(idx, idx[1:]):
                gap = st[b] - en[a]
                if gap > NAME_GAP_MAX:
                    out.append(f"이름 '{n}' {ch[a]}↔{ch[b]} 쉼 {gap:.2f}초(>{NAME_GAP_MAX}) @{st[a]:.2f}s — 읽는 글 '{txt[m.start():m.end()]}' 를 끊김 없는 표기로(사전 name_dict 목소리별 표기)")
    return out


def gate_sent(S: dict, sent: list[dict], R: Path, log=print) -> list[str]:
    """(판단 주인 — 렌더 전 관문 ②) make_sentences 결과(sent: id·wav)로 줄별 대조. 문제 목록(빈 목록 = 통과). 결과 = R/narr_verify.json."""
    txt = {l["id"]: l["tts"] for l in S["lines"] if l.get("kind") == "tts"}
    lines = [{"id": s["id"], "text": txt[s["id"]]} for s in sent if s["id"] in txt]
    rep = verify(lines, {s["id"]: s.get("wav") for s in sent}, Path(R) / "narr_full.mp3", Path(R) / "narr_verify.json")
    log(f"[줄별 받아쓰기] 확정 {len(rep['sure'])} · 의심 {len(rep['maybe'])} → {Path(R) / 'narr_verify.json'}")
    return [f"{x['line']} {x['type']}: 들림 '{x.get('heard') or x.get('heard_slice') or ''}'" + (f" · 글 '{x['ref']}'" if x.get("ref") else "")
            for x in rep["sure"]]
