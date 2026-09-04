# -*- coding: utf-8 -*-
"""2단계 — 통과 채널의 **터진 영상**을 전사한다 (2026-09-05).

## 순서 (사장님 지적으로 바로잡은 것)

    ① 채널 발굴          harvest_sul_local.py      ← 판정기로 거른다
    ② 터진 영상 수집       이 스크립트 --collect      ← 조회수 순
    ③ ★전사             이 스크립트 --transcribe   ← 시간이 여기 다 든다
    ④ 스타일 분류         classify_scripts.py       ← ③ 없이는 못 한다
    ⑤ 뭉치는 덩어리 = 축
    ⑥ 축마다 문장틀

★③ 전에는 스타일을 정하지 않는다. 제목만 보고 축을 정하면 또 헛다리다
  (실측: 제목 기준 판정과 자막 기준 판정이 다르다).

## 토큰

전사는 **파일로만** 쌓는다(transcripts/*.json). 화면엔 진행 한 줄씩.
수천 편을 대화창에 띄우면 컨텍스트가 터진다.

## 재개 가능

이미 받은 영상은 건너뛴다. 중간에 끊겨도 다시 돌리면 이어서 한다.

실행:
    py scripts/transcribe_hits.py --collect            # 통과 채널의 쇼츠 목록
    py scripts/transcribe_hits.py --transcribe -n 300  # 조회수 상위 300편 전사
    py scripts/transcribe_hits.py --status
"""
import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = BASE / "out" / "sul_survey"
STATE = OUT / "state.json"
VIDEOS = OUT / "videos.json"
TDIR = OUT / "transcripts"
TDIR.mkdir(parents=True, exist_ok=True)


def _run(args, timeout=180):
    """yt-dlp 호출. ★bytes로 받아 errors='replace' — text=True면 cp949 섞여 죽는다(실측)."""
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout)
        return (r.stdout or b"").decode("utf-8", errors="replace")
    except Exception:
        return ""


def collect():
    """통과 채널마다 쇼츠 목록(조회수·id·제목)을 긁어 videos.json에 쌓는다.

    ⚠️★yt-dlp 제목은 **유튜브 자동번역 영어**로 온다 — 실측 2,707편 중 96%가 영어였다.
      그래서 이 제목으로 `categorize` 판정을 하면 **전부 '안 걸림'**이 나온다(실측 100%).
      판정에 쓸 제목은 반드시 **YouTube API**에서 받아라(발굴 루프가 그렇게 해서
      292편을 제대로 찾았다). 여기서 받은 제목은 **조회수·id 확보용**이고,
      축 판정은 state.json의 API 제목(sample_titles)이나 API 재조회로 한다.
      (같은 함정 3번째 — memory: 정적문자열검사_기능오판)
    """
    st = json.loads(STATE.read_text(encoding="utf-8"))
    have = {}
    if VIDEOS.exists():
        have = {v["video_id"]: v for v in json.loads(VIDEOS.read_text(encoding="utf-8"))}
    chans = list(st["passed"].items())
    print("통과 %d채널에서 쇼츠 목록 수집" % len(chans))
    for i, (cid, rec) in enumerate(chans, 1):
        out = _run(["yt-dlp", "--flat-playlist", "--playlist-end", "40",
                    "--print", "%(view_count)s\t%(id)s\t%(title)s",
                    "https://www.youtube.com/channel/%s/shorts" % cid])
        n = 0
        for ln in out.splitlines():
            p = ln.split("\t")
            if len(p) < 3:
                continue
            try:
                views = int(p[0])
            except ValueError:
                continue
            vid = p[1]
            if vid in have:
                continue
            have[vid] = {"video_id": vid, "views": views, "title": "\t".join(p[2:]).strip(),
                         "channel": rec["name"], "channel_id": cid}
            n += 1
        print("[%3d/%d] %-20s +%d편 (누적 %d)" % (i, len(chans), rec["name"][:18], n, len(have)),
              flush=True)
        VIDEOS.write_text(json.dumps(list(have.values()), ensure_ascii=False, indent=1),
                          encoding="utf-8")
    print("\n총 %d편" % len(have))


_TAG = re.compile(r"<[^>]+>")


def _clean_vtt(p):
    seen, last = [], ""
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or "-->" in ln or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        ln = _TAG.sub("", ln).strip()
        if ln and ln != last:
            seen.append(ln)
            last = ln
    txt = " ".join(seen)
    w, out = txt.split(), []
    for x in w:                      # 롤링 자막이 만드는 중복 낱말 제거
        if not out or out[-1] != x:
            out.append(x)
    return " ".join(out)


def transcribe(n, use_pick=True):
    """★pick.json이 있으면 그걸 쓴다 — 판정기에 **안 걸린** 영상이 우선이다.

    그냥 조회수 순으로 전사하면 이미 아는 축(오용형 등)만 잔뜩 받게 된다.
    새 축은 판정기가 모르는 영상에 있다(pick_unknown.py 주석 참조).
    """
    pick = OUT / "pick.json"
    if use_pick and pick.exists():
        vids = json.loads(pick.read_text(encoding="utf-8"))
        print("pick.json 사용 — unknown %d · known %d"
              % (sum(1 for v in vids if v.get("group") == "unknown"),
                 sum(1 for v in vids if v.get("group") == "known")))
    else:
        vids = json.loads(VIDEOS.read_text(encoding="utf-8"))
        vids.sort(key=lambda v: -v["views"])
    todo = [v for v in vids if not (TDIR / ("%s.json" % v["video_id"])).exists()][:n]
    print("전사 대상 %d편 (이미 받은 것 %d편)"
          % (len(todo), len(list(TDIR.glob("*.json")))))
    ok = fail = 0
    for i, v in enumerate(todo, 1):
        vid = v["video_id"]
        tmp = TDIR / vid
        _run(["yt-dlp", "--skip-download", "--write-auto-sub", "--sub-lang", "ko",
              "--sub-format", "vtt", "-o", str(tmp),
              "https://www.youtube.com/watch?v=%s" % vid], timeout=120)
        vtt = TDIR / ("%s.ko.vtt" % vid)
        if not vtt.exists():
            fail += 1
            (TDIR / ("%s.json" % vid)).write_text(
                json.dumps({**v, "text": "", "ok": False}, ensure_ascii=False),
                encoding="utf-8")
        else:
            txt = _clean_vtt(vtt)
            dur = _run(["yt-dlp", "--skip-download", "--print", "%(duration)s",
                        "https://www.youtube.com/watch?v=%s" % vid], timeout=60).strip()
            try:
                dur = int(float(dur.splitlines()[0]))
            except Exception:
                dur = 0
            (TDIR / ("%s.json" % vid)).write_text(
                json.dumps({**v, "text": txt, "duration": dur, "ok": bool(txt)},
                           ensure_ascii=False), encoding="utf-8")
            vtt.unlink(missing_ok=True)
            ok += 1
        if i % 10 == 0 or i == len(todo):
            print("  %d/%d  성공%d 실패%d" % (i, len(todo), ok, fail), flush=True)
    print("\n끝 — 성공 %d · 자막없음 %d" % (ok, fail))


def status():
    n_ch = len(json.loads(STATE.read_text(encoding="utf-8"))["passed"]) if STATE.exists() else 0
    n_v = len(json.loads(VIDEOS.read_text(encoding="utf-8"))) if VIDEOS.exists() else 0
    files = list(TDIR.glob("*.json"))
    good = sum(1 for f in files if json.loads(f.read_text(encoding="utf-8")).get("ok"))
    print("채널 %d · 영상목록 %d편 · 전사시도 %d · 자막확보 %d"
          % (n_ch, n_v, len(files), good))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--transcribe", action="store_true")
    ap.add_argument("-n", type=int, default=300)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.collect:
        collect()
    elif a.transcribe:
        transcribe(a.n)
    else:
        status()
