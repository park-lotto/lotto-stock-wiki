# -*- coding: utf-8 -*-
"""카드뉴스 원문 모으기·카드 쓰기 — **수강생 자기 agy(구독)** 로 (2026-10-08).

■ 왜 (쇼츠대폭발 10-08 «로컬호스트에서 디자인만 고르면, 사용자가 원하는 링크나 주제를 가지고 로컬에서 LLM(agy)이
  찾아와서 만들어 주는 것»)
    전에는 원문을 «MCP 를 부른 AI 가 알아서» 가져오고 카드 문구도 그 AI 가 썼다. 이 파일이 그 두 일을 agy 로 한다.
    ★질문(무엇을 어떻게 물을지)·쓰는 법·답 모양은 **서버가 준다** — 여기에는 agy 부르기·파일 받기 같은 일반 기술만 있다.

■ 소재별
    topic        agy search_web(서버 질문) → 사실 자료 + 출처 주소
    news·instagram  agy read_url_content → 본문
    youtube      yt-dlp 자막(무료·AI 없음) → 없으면 360p 로 내려받아 agy 가 view_file 로 직접(전역 규칙 6-1 — 유튜브 링크를
                 API 에 넣지 않는다)
    local_video·pdf·document  agy 가 view_file 로 직접(100MB 넘는 영상은 ffmpeg 으로 줄인 사본 — 줄이기에만 ffmpeg)
    text         그대로

■ 거부·한도
    agy 가 한도·로그인·속도 거부를 알리면 `agy_transport_client.invoke` 가 이 실행을 멈추는 예외를 올린다(재시도 없음 · 6-2).
"""

import json
import os
import re
import shutil
import subprocess
import tempfile

#: view_file 한도 — 파일당 100MB(전역 규칙 6-1 · agy 공식 변경 기록 «larger than 100 MB … rejected»). 1억 바이트로 막는다.
VIEW_LIMIT = 100_000_000


class SourceError(RuntimeError):
    """원문을 못 모음. 사유는 사람이 읽을 말로."""


def _agy(prompt, *, kind, files=(), schema=None, model=None, timeout_s=600, cwd=None):
    import agy_transport_client as AGY                              # noqa: PLC0415
    res = AGY.invoke(prompt, kind=kind, files=list(files), schema=schema, model=model, timeout_s=timeout_s, cwd=cwd)
    if not res.get("ok"):
        raise SourceError(f"agy 실패({res.get('code')}): {str(res.get('message') or '')[:200]}")
    return res


_URL_PREFACE = ("RunCommand·셸·ffmpeg·파일 도구를 쓰지 마라. 쓸 수 있는 도구는 read_url_content 하나뿐이다.")


def _vtt_text(path):
    """VTT 자막 → 평문(시각·태그·연속 중복 줄 제거). 롤링 겹침은 서버 ingest 가 접는다."""
    out, prev = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line or line.isdigit():
                continue
            line = re.sub(r"<[^>]+>", "", line).strip()
            if line and line != prev:
                out.append(line)
                prev = line
    return " ".join(out)


def _argv(prompts, key, **fill):
    """서버가 준 명령 틀에 자리만 채운다(실행기는 명령을 짓지 않는다). 맨 앞 실행 파일은 PATH 에서 찾는다 — 없으면 사람 말로."""
    tpl = ((prompts or {}).get("argv") or {}).get(key)
    if not tpl:
        raise SourceError(f"서버가 준 명령({key})이 없습니다 — 서버 응답의 prompts.argv 를 그대로 넘기세요.")
    exe = shutil.which(str(tpl[0]))
    if not exe:
        raise SourceError(f"{tpl[0]} 가 이 PC 에 없습니다 — 설치한 뒤 다시 하세요(유튜브: python3 -m pip install yt-dlp).")
    out = [exe]
    for a in tpl[1:]:
        a = str(a)
        for k, v in fill.items():
            a = a.replace("{" + k + "}", str(v))
        out.append(a)
    return out


def _youtube(url, prompts, model, work):
    subs = os.path.join(work, "subs")
    os.makedirs(subs, exist_ok=True)
    subprocess.run(_argv(prompts, "ytdlp_subs", dir=subs, url=url),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    vtts = sorted(x for x in os.listdir(subs) if x.endswith(".vtt"))
    ko = [x for x in vtts if ".ko" in x] or vtts
    if ko:
        text = _vtt_text(os.path.join(subs, ko[0]))
        if len(text) >= 80:
            return {"sourceText": text, "sources": [url], "notes": [f"유튜브 자막({ko[0]})"]}
    # 자막이 없다 — 작은 사본을 내려받아 agy 가 직접 본다(규칙 6-1: 링크를 API 에 넣지 않는다)
    vid = os.path.join(work, "video.mp4")
    subprocess.run(_argv(prompts, "ytdlp_video", out=vid, url=url),
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if not os.path.exists(vid):
        raise SourceError("유튜브 영상을 내려받지 못했습니다(자막도 없음).")
    return _media(vid, prompts, model, work, note="유튜브 자막 없음 → 내려받아 agy 가 직접 봄", url=url)


def _shrink(src, dst, prompts):
    """100MB 넘는 영상 → 서버가 준 줄이기 명령(전역 규칙 6-1 — ffmpeg 은 줄이기에만)."""
    subprocess.run(_argv(prompts, "ffmpeg_shrink", src=src, dst=dst), check=True)
    return dst


def _media(path, prompts, model, work, note="", url=None):
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise SourceError(f"파일이 없습니다: {path}")
    target = path
    if os.path.getsize(path) > VIEW_LIMIT:
        if path.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")):
            target = _shrink(path, os.path.join(work, "small.mp4"), prompts)
        if os.path.getsize(target) > VIEW_LIMIT:
            raise SourceError("파일이 100MB 를 넘어 agy 가 읽을 수 없습니다 — 더 짧게 잘라 주세요.")
    q = prompts["media"].replace("{name}", os.path.basename(target))
    res = _agy(q, kind="view", files=[target], model=model, cwd=os.path.dirname(target), timeout_s=900)
    text = (res.get("text") or "").strip()
    return {"sourceText": text, "sources": [url or path], "notes": [n for n in (note, "agy view_file") if n]}


def gather(source, prompts, model, workdir=None):
    """소재 → {sourceText, sources, notes}. 질문(prompts)·모델은 서버가 준다."""
    kind = (source or {}).get("kind")
    work = workdir or tempfile.mkdtemp(prefix="cardnews-src-")
    os.makedirs(work, exist_ok=True)
    if kind == "text":
        return {"sourceText": str(source.get("text") or ""), "sources": [], "notes": []}
    if kind == "topic":
        q = prompts["topic"].replace("{topic}", str(source.get("text") or "").strip())
        res = _agy(q, kind="search", model=model, timeout_s=600)
        text = (res.get("text") or "").strip()
        urls = re.findall(r"https?://\S+", text.split("출처:", 1)[-1]) if "출처:" in text else []
        return {"sourceText": text, "sources": urls, "notes": ["agy search_web"]}
    if kind in ("news", "instagram"):
        q = _URL_PREFACE + "\n\n" + prompts["url"].replace("{url}", str(source.get("url") or ""))
        res = _agy(q, kind=None, model=model, timeout_s=600)
        text = (res.get("text") or "").strip()
        if text.startswith("읽지 못함"):
            raise SourceError(f"agy 가 주소를 읽지 못했습니다 — {text[:200]}")
        return {"sourceText": text, "sources": [source.get("url")], "notes": ["agy read_url_content"]}
    if kind == "youtube":
        return _youtube(str(source.get("url") or ""), prompts, model, work)
    if kind in ("local_video", "pdf", "document"):
        return _media(str(source.get("path") or ""), prompts, model, work)
    raise SourceError(f"모르는 소재 종류입니다: {kind}")


def write(brief, source_text, card_count, schema, model):
    """서버가 준 쓰는 법(brief)·답 모양(schema)으로 agy 가 카드 문구·캡션·해시태그·분류를 쓴다 → 그 JSON.

    ★검사는 서버가 한다(script·render 단계의 audit) — 여기서 고치지 않는다. 반려되면 그 사유를 붙여 다시 쓰게 하면 된다.
    """
    prompt = ("아래 «쓰는 법» 대로 «원문» 을 카드뉴스로 다시 써라. 원문에 없는 사실을 지어내지 마라. "
              "JSON 하나로만 답하라.\n\n«쓰는 법»\n" + json.dumps(brief, ensure_ascii=False, indent=1)
              + f"\n\n카드 수: {int(card_count)}장\n\n«원문»\n" + str(source_text))
    res = _agy(prompt, kind="text", schema=schema, model=model, timeout_s=600)
    got = res.get("json")
    if not isinstance(got, dict):
        raise SourceError("agy 가 카드 JSON 을 주지 않았습니다.")
    return unescape_cards(got)


def unescape_cards(got):
    """agy 가 JSON 안 글자에 줄 바꿈을 «\\n» 두 글자로 **한 번 더 이스케이프**해 줄 때가 있다(10-08 실측 @anavocado12345 본문 —
    카드에 «\n» 글자가 그대로 찍혔다). 모양만 푼다: 글자 «\\n» → 줄 바꿈, «\\t» → 빈칸. 그 밖의 글자는 고치지 않는다
    (남은 역슬래시·제어 문자는 서버 검사 `audit_cards` 가 반려한다)."""
    def fix(v):
        return v.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", " ") if isinstance(v, str) else v
    for c in got.get("cards") or []:
        if isinstance(c, dict):
            for k in list(c):
                c[k] = fix(c[k])
    if isinstance(got.get("caption"), str):
        got["caption"] = fix(got["caption"])
    return got
