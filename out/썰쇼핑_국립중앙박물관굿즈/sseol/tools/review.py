# -*- coding: utf-8 -*-
"""굽기 전 판정 — 구독 AGY 가 **작은 미리보기 한 파일**(완성본과 같은 그림·같은 시각을 540x960·8fps·소리 없이)을 한 번 보고,
코드가 판정한다. 결과는 프로젝트 폴더의 `review.json`(판정한 대본·타이밍 sha256 · 소재 파일 크기/수정 시각).

    python preset.py review <프로젝트>          (tts 뒤 · render **전에**)

왜 굽기 전인가: 전역 규칙 «렌더 뒤 AGY 금지 — 판정은 굽기 전, 렌더 뒤는 프로그램 측정만»(2026-10-17 · 이 팩 2026-10-22 반영).
  옛 순서 안내 7번은 완성본(out.mp4)을 agy 가 보고 걸린 컷을 고쳐 다시 굽게 했다 — 렌더 뒤 AGY · 고침 → 재렌더 → 재검수 고리다.
  이제 render 가 이 판정이 «지금 대본·타이밍·소재로 통과» 일 때만 굽고, 그 요약을 렌더 영수증(영상 SHA 에 묶임)에 싣는다.
  check 3번이 그 칸을 본다. 완성본은 AGY 에 가지 않는다.
무엇을 AGY 가 보고 무엇을 코드가 정하나(AGY 는 한 번 묻는다 — 반려 재질문 고리 없음):
  - 컷마다(영상 칸): 원래 영상에 박힌 자막·뉴스 띠·로고·워터마크 · 우리 자막과 안 맞는 장면 · 검은/멈춘 화면
  → 코드: 전부 보고 컷마다 답했고 하나도 걸리지 않아야 pass. 걸리면 fail(걸린 컷을 고치면 대본·소재 지문이 바뀌어 새 판정이 된다).
  한 색 화면(흰/검은 전환)·소재 시작 초 넘침은 미리보기를 만드는 렌더 코드가 잰다(그때는 AGY 를 부르지 않는다).
  그림 이상(글자·손·얼굴·다른 사람)은 순서 안내 4번에서 그림을 만들 때 이미 본다 — 여기서 다시 보지 않는다.
  소리 크기·움직임은 렌더 상수다 — AGY 말로 바꾸지 않는다.
한 컷은 한 번만 묻는다(2026-10-23 신고 «컷 하나 바꿔도 전체 컷을 처음부터 다시 물어 답이 매번 달라 7번 반복»):
  컷마다 지문(소재 칸·파일 크기/수정 시각·소재 종류·그 컷의 자막 줄·제목·미리보기 프레임으로 잰 길이와 컷 안 줄 바뀜 자리)을 한 번 계산해
  review.json 의 judged 에 그 컷의 판정과 함께 남긴다. 다음 review 는 judged 에 없는 지문의 컷만 묻는다 — 통과한 컷은 다시 묻지 않으니
  답이 흔들려도 다시 걸리지 않고, 걸린 컷도 그대로면 다시 묻지 않는다(고친 컷만 새 지문). 컷 위치(절대 시각)는 지문에 넣지 않는다 —
  앞 카드 길이가 바뀌어 뒤로 밀린 컷은 보이는 그림이 같다. AGY 가 답하지 않은(또는 보지 못한 구간의) 컷만 다음 review 에서 한 번 더 묻고,
  ASK_MAX 번 넘게 답이 없으면 묻지 않고 그 컷을 바꾸라고 한다(재판정 고리 상한).
같은 대본·타이밍·소재이고 물을 컷이 없으면 AGY 도 미리보기도 다시 만들지 않는다(통과면 그대로 · 실패면 걸린 곳을 고치라고 멈춤).
AGY 는 볼케이노 실행기의 agy 통로(runner/agy_transport_client.invoke — 셸 권한 없음 · 이 미리보기 하나만 읽게)로 부른다.
  거부(한도·로그인·도구 거부)면 이 실행의 agy 요청을 모두 멈춘다(전역 6-2 · 자동 재시도 없음).
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

REVIEW = "review.json"
SCHEMA = "sseol-review-v2"         # v2 = 컷 지문별 판정(judged) · v1 기록은 같은 입력이면 그대로 쓰고, 바뀌면 한 번 전부 묻는다
OLD_SCHEMAS = ("sseol-review-v1",)
ASK_MAX = 2                         # 답이 없던 컷을 묻는 횟수 상한 — 안내 문구 «한 번 다시» 와 같은 수(처음 + 한 번 더)
PW, PH, PFPS = 540, 960, 8          # 완성본(1080x1920·30fps)의 절반 크기 · 8fps — 45초 편이 몇 MB
QUALITY = ("veryfast", 28)
LIMIT = 15_000_000                  # 한 대화 = 한 파일 상한(AGY 대화 누적 한도 — 공식 숫자 없음 · 철멍뭉 미리보기와 같은 값). 넘으면 부르지 않는다
TIMEOUT = 600                       # agy 한 번 상한(초) — 무한 대기 없음
VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".m4v")

PROMPT = """Do not run commands, do not edit or create files, do not open any other file or folder.
Use your file-reading tool (read_file; older builds call it view_file) to open ONLY this file, once, and watch all of it from 0s to the end (about {dur:.1f}s): {name}
It is a small silent preview of a Korean vertical short video BEFORE the final render (same pictures and timing as the final, smaller).
Layout: a navy header bar at the top with the channel name, then a white box with OUR OWN Korean captions, then the footage area
(from about 35% to 81% of the height) showing each cut's video or picture. During the first {intro:.1f}s the title is drawn over the
top and the footage fills the lower part of the screen. The header, the title and our own captions are part of the design - never report them.
Topic: {title}
Report ONLY the cuts listed below (other parts of the file were already checked).
Cuts (seconds in this file; source type; our caption lines shown during the cut):
{cuts}
For each cut report only what you see inside the footage area:
- burned_text: subtitles, news tickers or bands, channel logos or watermarks that belong to the ORIGINAL footage
- mismatch: the picture clearly does not fit our caption lines or the topic
- blank: black, empty or frozen picture
Answer with ONE JSON object only:
{{"watched_seconds": <number>, "cuts": [{{"i": <cut number>, "ok": true|false, "problem": "<burned_text|mismatch|blank>: <what you saw>"}}]}}
"cuts" must have one entry for every cut number listed above."""

# 아래 find_agy_runner 는 정본 volcano-mcp tools/agy_lookup.py 를 글자 그대로 복사한 것(tests/test_agy_lookup.py 가 대조) — 여기서 고치지 않는다.


def find_agy_runner(module="agy_transport_client"):
    """(실행기 폴더 Path, 모듈) — 실행기 agy 통로(와 그 위 부품 module)를 읽는다 · 못 찾으면 사유를 보이고 멈춘다 · 정본 volcano-mcp tools/agy_lookup.py · 글자 그대로 복사."""
    import importlib.util
    import os
    import sys
    from pathlib import Path
    folder = Path(os.environ.get("VOLCANO_RUNNER_DIR") or Path.home() / ".volcano" / "runner")
    names = ("agy_transport_codes", "agy_transport_proc", "agy_transport_refusal", "agy_transport_pc_env", "agy_transport_client")
    for name in names + tuple(n for n in (module,) if n not in names):
        if name in sys.modules:
            continue
        path = folder / f"{name}.py"
        if not path.is_file():
            raise SystemExit(f"볼케이노 실행기의 agy 부품이 없습니다: {path}\n"
                             "볼케이노 실행기(작업 폴더의 runner/volcano_drive.py)를 한 번 돌리면(사전 점검 단계) 이 자리에 설치됩니다. "
                             "그 뒤 같은 명령을 다시 실행하세요.")
        spec = importlib.util.spec_from_file_location(name, str(path))
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[name] = loaded
        try:
            spec.loader.exec_module(loaded)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return folder, sys.modules[module]


def agy_model():
    """이 팩의 agy 모델(review · scenes · aiimg 모두) — 실행기 agy 모델 한 자리 agy_transport_pc_env.agy_model(env INFO3D_AGY_MODEL 이 먼저,
    없으면 실행기 기본 gemini-3.8-flash-high). 팩 안에 모델 이름을 따로 적지 않는다(2026-10-23 — 세 곳에 따로 적혀 있었다)."""
    return find_agy_runner("agy_transport_pc_env")[1].agy_model()


def _spec(m):
    return {"path": m} if isinstance(m, str) else m


def media_specs(script):
    """[(이름, 소재 칸)] — 도입 소재 + 카드마다 소재(하나 또는 목록). 렌더(Renderer.get_media)가 읽는 것과 같은 칸."""
    out = []
    if script.get("intro_media"):
        out.append(("intro", _spec(script["intro_media"])))
    for ci, card in enumerate(script.get("cards") or []):
        med = card.get("media")
        lst = med if isinstance(med, list) else ([med] if med else [])
        out += [(f"{ci + 1}-{k + 1}", _spec(m)) for k, m in enumerate(lst)]
    return out


def fingerprint(proj):
    """(지문, 대본, 타이밍) — 대본·타이밍은 파일을 한 번 읽어 지문과 내용에 같이 쓴다(같은 파일을 두 번 재지 않는다 · 6-00).
    소재는 크기·수정 시각(영상 수백 MB 를 해시하지 않는다 — 바꾸면 둘 중 하나가 바뀐다)."""
    def read(name, why):
        p = os.path.join(proj, name)
        if not os.path.isfile(p):
            raise SystemExit(f"{name} 이 없습니다 — {why}")
        with open(p, "rb") as fh:
            raw = fh.read()
        return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()
    script, s_sha = read("script.json", "순서 안내 2번(대본)부터")
    timing, t_sha = read("timing.json", f"먼저 `python preset.py tts {proj}`(음성·자막 시각)")
    media = {}
    for _name, m in media_specs(script):
        p = os.path.join(proj, m["path"])
        try:
            st = os.stat(p)
        except OSError:
            raise SystemExit(f"소재 파일이 없습니다: {m['path']}")
        media[m["path"]] = [st.st_size, st.st_mtime_ns]
    return {"script_sha256": s_sha, "timing_sha256": t_sha, "media": media}, script, timing


def cuts(script, timing):
    """[(번호, 이름, 시작, 끝, 소재 종류, 그 컷 동안 보이는 자막 줄, 소재 칸, 컷 안에서 새 줄이 나오는 자리(컷 시작부터 초))] — 렌더 frame_at 과 같은 규칙:
    소재 하나면 카드 내내 · 목록이면 k번째 줄부터 k번째 컷(마지막 컷이 남은 줄까지). 카드는 시각 순 — 한 번 훑기.
    컷 안 줄 자리는 렌더가 그 자리에서 확대(PUNCH)하고 자막을 늘리는 곳이라 보이는 그림의 일부다."""
    rows, tm = [], timing["cards"]
    end = timing["end"]
    def kind(m):
        p = m["path"].replace("\\", "/")
        return "generated picture" if "/ai/" in "/" + p else ("video" if os.path.splitext(p)[1].lower() in VIDEO_EXT else "picture")
    if script.get("intro_media"):
        im = _spec(script["intro_media"])
        rows.append(("intro", 0.0, timing["intro_end"], kind(im), [script.get("title", "")], im, []))
    for ci, card in enumerate(script.get("cards") or []):
        med = card.get("media")
        if not med:
            continue
        t1 = tm[ci + 1]["start"] if ci + 1 < len(tm) else end
        ls, lines = tm[ci]["line_starts"], card["lines"]
        if not isinstance(med, list):
            a = tm[ci]["start"]
            rows.append((f"{ci + 1}", a, t1, kind(_spec(med)), lines, _spec(med), [x - a for x in ls if a < x < t1]))
            continue
        for k, m in enumerate(med):
            a = ls[min(k, len(ls) - 1)]
            last = k + 1 == len(med)
            b = ls[k + 1] if k + 1 < len(ls) and not last else t1
            rows.append((f"{ci + 1}-{k + 1}", a, b, kind(_spec(m)), lines[k:] if last else lines[k:k + 1], _spec(m),
                         [x - a for x in ls[k + 1:] if x < b] if last else []))
    return [(i, *r) for i, r in enumerate(rows, 1)]


def cut_key(script, row, media):
    """컷 지문 — 그 컷이 미리보기에서 어떻게 보이고 AGY 에게 무엇이라 묻는지를 정하는 것만(한 번 계산해 judged 의 열쇠로 쓴다).
    소재 칸(경로·시작 초·크롭·초점) · 그 파일의 크기/수정 시각(fingerprint 가 이미 잰 값) · 소재 종류 · 자막 줄 · 제목(주제 · 도입이면 훅도)
    · 길이와 컷 안 줄 자리는 미리보기 프레임(PFPS) 단위 — AGY 가 보는 해상도 그대로. 컷 번호·절대 시각은 넣지 않는다(밀려도 같은 그림)."""
    _i, name, a, b, kind, lines, spec, inner = row
    body = {"kind": kind, "spec": spec, "file": media.get(spec["path"]), "lines": list(lines), "title": script.get("title", ""),
            "hook": script.get("hook") if name == "intro" else None,
            "frames": int(round((b - a) * PFPS)), "inner": [int(round(x * PFPS)) for x in inner]}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load(proj):
    p = os.path.join(proj, REVIEW)
    try:
        with open(p, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) and rec.get("schema") in (SCHEMA,) + OLD_SCHEMAS else None


def same(rec, fp):
    return rec is not None and all(rec.get(k) == v for k, v in fp.items())


def require_pass(proj):
    """render 가 굽기 전에 부른다 — 지금 대본·타이밍·소재로 통과한 판정이 있어야 한다. 돌려줌: 영수증에 실을 요약."""
    fp, _s, _t = fingerprint(proj)
    rec = load(proj)
    if rec is None:
        raise SystemExit(f"굽기 전 판정({REVIEW})이 없습니다 — 먼저 `python preset.py review {proj}` (agy 가 미리보기를 한 번 본다)")
    if not same(rec, fp):
        raise SystemExit(f"굽기 전 판정이 지금 대본·타이밍·소재와 다릅니다(판정 뒤에 바뀜) — `python preset.py review {proj}` 를 다시")
    if rec.get("verdict") != "pass":
        raise SystemExit("굽기 전 판정이 통과가 아닙니다 — 걸린 컷을 고친 뒤 review 를 다시:\n  - " + "\n  - ".join(rec.get("issues") or ["(사유 없음)"]))
    return dict(fp, verdict="pass", file=REVIEW, model=rec.get("model"))


def where(name):
    return "도입" if name == "intro" else f"카드 {name}"


def take(body, todo, keys, judged, model):
    """AGY 답 → judged 갱신(물은 컷만) · 돌려줌: 이번 답에 대한 알림. 판정은 코드가 한다:
    답이 있고 AGY 가 그 컷 끝까지 봤다고 한 컷만 판정으로 받는다(ok 가 true 여야 통과). 나머지는 «답 없음» 으로 묻은 횟수를 센다."""
    notes = []
    try:
        seen = float(body.get("watched_seconds") or 0)
    except (TypeError, ValueError):
        seen = 0.0
    need = max(r[3] for r in todo)
    if seen < need - 1:
        notes.append(f"AGY 가 미리보기 전체를 보지 못했다고 답했습니다(본 시간 {seen:g}초 / {need:.1f}초) — 보지 못한 구간의 컷은 판정으로 받지 않았습니다")
    got = {}
    for r in body.get("cuts") or []:
        try:
            got[int(r["i"])] = r
        except (KeyError, TypeError, ValueError):
            continue
    for i, _name, _a, b, *_rest in todo:
        ans, k = got.get(i), keys[i]
        if ans is not None and b <= seen + 1:
            judged[k] = {"ok": ans.get("ok") is True, "problem": str(ans.get("problem") or ""), "model": model}
        else:
            judged[k] = {"ok": None, "asks": int((judged.get(k) or {}).get("asks") or 0) + 1}
    return notes


def pending(entry):
    """이 컷을 (다시) 물어야 하나 — 판정이 없거나, 답이 없었고 아직 ASK_MAX 번 안 물었을 때만."""
    return entry is None or (entry.get("ok") is None and int(entry.get("asks") or 0) < ASK_MAX)


def cut_issues(rows, keys, judged):
    issues = []
    for i, name, *_rest in rows:
        e = judged.get(keys[i]) or {}
        if e.get("ok") is True:
            continue
        if e.get("ok") is False:
            issues.append(f"컷 {i}({where(name)}): {e.get('problem') or '문제'}")
        elif int(e.get("asks") or 0) < ASK_MAX:
            issues.append(f"컷 {i}({where(name)}) 을 AGY 가 판정하지 않았습니다 — 다음 review 에서 이 컷만 한 번 더 묻습니다")
        else:
            issues.append(f"컷 {i}({where(name)}) 을 AGY 가 판정하지 않았습니다 — {ASK_MAX}번 물어도 답이 없었습니다. 이 컷의 소재·구간을 바꾼 뒤 review 를 다시")
    return issues


def ask(clip, prompt, model):
    """미리보기 하나를 실행기 agy 통로로 한 번 묻는다 → 답 JSON. 답이 없거나 파일을 안 연 답이면 판정을 남기지 않고 멈춘다."""
    _folder, agy = find_agy_runner()
    path = agy.plain_path(str(clip))
    try:
        res = agy.invoke(prompt, kind="view", files=[path], model=model, timeout_s=TIMEOUT, cwd=os.path.dirname(path))
    except agy.RUN_REFUSAL.RunServiceRefused as e:
        code = (getattr(e, "provider_result", None) or {}).get("code") or e.code
        raise SystemExit(f"agy 가 거부했습니다({code} — 한도·로그인·도구 거부). 이 실행의 agy 요청을 모두 멈췄습니다(자동 재시도 없음). "
                         "원인을 확인한 뒤(한도면 풀리는 시각 뒤) 같은 review 명령을 다시 하세요.") from e
    if not res.get("ok"):
        raise SystemExit(f"agy 가 답하지 않았습니다({res.get('code')}: {str(res.get('message') or '')[:200]}) — 판정을 남기지 않았습니다. "
                         "잠시 뒤 같은 review 명령을 한 번 다시 하세요.")
    why, _used = agy.opened_exactly(res.get("tools"), [path])
    if why:
        raise SystemExit(f"agy 가 미리보기를 연 기록이 맞지 않습니다({why}) — 판정을 남기지 않았습니다. 같은 review 명령을 한 번 다시 하세요.")
    text = str(res.get("text") or "")
    try:
        body = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except ValueError:
        raise SystemExit(f"agy 답을 JSON 으로 못 읽었습니다: {text[:200]!r} — 판정을 남기지 않았습니다. 같은 review 명령을 한 번 다시 하세요.")
    if not isinstance(body, dict):
        raise SystemExit(f"agy 답이 JSON 객체가 아닙니다: {text[:200]!r}")
    return body


def again(old):
    """같은 입력 · 물을 컷 없음 — AGY 도 미리보기도 다시 만들지 않고 지난 판정을 그대로 말한다."""
    if old.get("verdict") == "pass":
        print(json.dumps({"verdict": "pass", "again": False, "review": old.get("_path")}, ensure_ascii=False))
        return 0
    raise SystemExit("이 대본·타이밍·소재로 이미 판정했고 걸린 컷이 있습니다 — 그 컷(소재·구간·자막)을 고친 뒤 review 를 다시:\n  - "
                     + "\n  - ".join(old.get("issues") or ["(사유 없음)"]))


def review(proj):
    proj = os.path.abspath(proj)
    fp, script, timing = fingerprint(proj)
    old = load(proj)
    rows = cuts(script, timing)
    keys = {r[0]: cut_key(script, r, fp["media"]) for r in rows}
    v2 = old is not None and old.get("schema") == SCHEMA
    judged = dict(old.get("judged") or {}) if v2 else {}
    todo = [r for r in rows if pending(judged.get(keys[r[0]]))]
    if same(old, fp) and (not v2 or old.get("preview_error") or not todo):   # 옛 기록 · 코드가 잰 실패 · 물을 컷 없음(반려 재질문 고리 없음 · 6-00)
        return again(dict(old, _path=os.path.join(proj, REVIEW)))
    rec = dict(fp, schema=SCHEMA, stage="before_render", reviewer="agy", model=agy_model(), verdict="fail", issues=[])
    notes = []
    if todo:
        import render                       # 같은 그림 코드로 작게 — 미리보기와 완성본이 갈리지 않는다
        box = tempfile.mkdtemp(prefix="agy-review-", dir=proj)   # 한 대화 = 한 파일: 미리보기 하나만 든 새 폴더를 연다
        try:
            clip = os.path.join(box, "preview.mp4")
            try:
                render.Renderer(proj).render(clip, None, size=(PW, PH), fps=PFPS, quality=QUALITY)
            except SystemExit as e:         # 빈 화면 컷 · 소재 시작 초 넘침 — 코드가 잰 판정(AGY 를 부르지 않는다)
                rec["preview_error"] = f"미리보기를 만들다 멈춤: {e}"
            if "preview_error" not in rec:
                dur = timing["end"]
                size = os.path.getsize(clip)
                rec.update(preview_seconds=round(dur, 3), preview_bytes=size)
                if size > LIMIT:
                    rec["preview_error"] = f"미리보기 {size} 바이트가 AGY 한 대화 상한 {LIMIT} 을 넘습니다 — 편 길이를 확인하세요"
                else:
                    cut_txt = "\n".join(f"{i}. {a:.2f}-{b:.2f}s {kind} - " + " / ".join(lines) for i, _n, a, b, kind, lines, *_r in todo)
                    body = ask(clip, PROMPT.format(name=os.path.basename(clip), dur=dur, intro=timing["intro_end"],
                                                   title=script.get("title", ""), cuts=cut_txt), rec["model"])
                    rec["asked"] = [r[0] for r in todo]
                    rec["answer"] = body
                    notes = take(body, todo, keys, judged, rec["model"])
        finally:
            shutil.rmtree(box, ignore_errors=True)
    rec["judged"] = judged
    rec["cuts"] = [{"i": i, "where": where(name), "key": keys[i]} for i, name, *_r in rows]
    if rec.get("preview_error"):
        rec["issues"] = [rec["preview_error"]]
    else:
        rec["issues"] = notes + cut_issues(rows, keys, judged)
        rec["verdict"] = "pass" if not rec["issues"] else "fail"
    with open(os.path.join(proj, REVIEW), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"verdict": rec["verdict"], "asked": rec.get("asked", []), "issues": rec["issues"],
                      "review": os.path.join(proj, REVIEW)}, ensure_ascii=False, indent=1))
    return 0 if rec["verdict"] == "pass" else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("사용법: python preset.py review <프로젝트>")
    sys.exit(review(sys.argv[1]))
