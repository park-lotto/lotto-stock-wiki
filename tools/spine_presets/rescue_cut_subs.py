"""잘린 유튜브 자막을 Whisper로 다시 떠서 원문을 통째로 갈아끼운다 (2026-09-21 사장님: "다시살려야지").

★왜 필요한가: 원문형 스파인의 마지막 칸이 "근데"·"올해 장맞철 오기"처럼 중간에 끊겨 있었다.
  우리가 자른 게 아니라 **유튜브 자동자막(src=ytsub)이 거기서 멈춘 것**이다.
  실측 2026-09-21: 유튜브 601편 중 483편(80%) 미완결 / 인스타 641편 중 32편(5%).
  히트작 200편 원본(hits_subs.json)만 재도 185/200(92%).

★왜 '뒤꿈치만 이어붙이기'가 아니라 통째 교체인가(사장님 확정):
  Whisper 전사는 끝만 살리는 게 아니라 **전체가 더 정확**하다. 실측 iu3Yq04q2Ws:
    자막  "[음악] … 설계에 무려의 방풍 뼈대 … 자랑한다고 올해 장맞철 오기"      ← 끊김+오탈자
    전사  "… 설계해 무려 96개의 방풍표대 … 자랑한다고 올해 장마철 오기 전에
           무조건 하나 장만해둬야겠네"                                        ← 끝까지+교정
  그래서 전사본으로 **칸을 다시 자른다**(templatize_hits와 같은 모델·같은 검증을 재사용 — 0순위-B).

쓰기(서버에서, env 필수 — 없으면 GROQ/제미니 키가 안 잡혀 조용히 0건이 된다):
  cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a
  python3 tools/spine_presets/rescue_cut_subs.py --ids azDE6caCwjU        # 시험(미리보기)
  python3 tools/spine_presets/rescue_cut_subs.py --apply                  # 전체 적용
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 종결 판정 — reviewpage.reject와 같은 기준(0순위-B: 같은 판단 두 벌 금지)
ENDS = re.compile(r"(다|요|임|음|죠|네|야|함|거|까|래|워|해|고요|든요)[.!?~]*$|[.!?]$")
YT_TYPES = {"발명품형", "오용형", "제품정체형"}


def origin(row_tpl):
    try:
        t = json.loads(row_tpl or "{}")
    except Exception:                      # noqa: BLE001
        return None
    o = t.get("_origin")
    return o if isinstance(o, dict) and o.get("cells") else None


def is_cut(o):
    """마지막 칸이 종결되지 않았나 = 자막이 중간에 끊긴 지문."""
    cells = [c for c in (o.get("cells") or []) if (c.get("text") or "").strip()]
    return bool(cells) and not ENDS.search(cells[-1]["text"].strip())


def to_mp3(mp4, out):
    """음성만 뽑는다 — Whisper는 영상이 필요 없고 업로드가 가벼워야 한다."""
    subprocess.run(["ffmpeg", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000",
                    "-b:a", "64k", out], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def fetch_full_text(vid, workdir):
    """영상 받아 → mp3 → Whisper 전사. 실패는 (None, 사유)."""
    from shopping_shorts.media_download import download_any
    from shopping_shorts import asr_check
    mp4 = None
    try:
        mp4, _cap = download_any("https://www.youtube.com/watch?v=" + vid, workdir)
    except Exception as e:                 # noqa: BLE001
        return None, "download:%s" % type(e).__name__
    if not mp4 or not os.path.exists(mp4):
        return None, "download:없음"
    try:
        mp3 = to_mp3(mp4, os.path.join(workdir, vid + ".mp3"))
    except Exception as e:                 # noqa: BLE001
        return None, "ffmpeg:%s" % type(e).__name__
    txt = asr_check.transcribe(mp3)
    for p in (mp4, mp3):                   # 디스크를 비운다 — /tmp가 차 라이브가 멈춘 사고가 있었다
        try:
            os.remove(p)
        except OSError:
            pass
    if not txt or not txt.strip():
        return None, "whisper:빈결과"
    return re.sub(r"\s+", " ", txt).strip(), ""


def resplit(text):
    """전사본을 칸으로 다시 자른다 — templatize_hits의 모델·프롬프트를 그대로 쓴다.

    ★검증은 **'원문에 실제로 있는 문장인가'만** 본다(th.check 전체가 아니라).
      th.check는 빈칸 템플릿(`{제품군}`)까지 검사하는데, 우리는 빈칸이 필요 없다 —
      원문형 스파인은 `cells[].text`에 **원문 그대로**를 담고 빈칸을 안 쓴다(spine_origin 계약).
      실측 2026-09-21 azDE6caCwjU: 7칸 중 6칸 통과·1칸만 '복원 불일치'였는데 그 칸도
      원문에는 멀쩡히 있었다(모델이 values를 덜 적었을 뿐) → 전체를 버리면 한 편을 통째로 잃는다.
      지어낸 문장만 막으면 충분하다."""
    import templatize_hits as th
    from shopping_shorts import script_generate as sg
    out = sg._call_json(th.prompt(text), th.SCHEMA) or {}
    cells = []
    for c in out.get("cells") or []:
        orig_txt = (c.get("original") or "").strip()
        if not orig_txt or th.norm(orig_txt) not in th.norm(text):
            continue                       # ★원문에 없는 문장 = 모델이 지어낸 것. 이것만 버린다
        cells.append({"role": c["role"], "text": orig_txt})
    return cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    ap.add_argument("--ids", default="", help="시험용: 이 영상ID만(쉼표)")
    ap.add_argument("--apply", action="store_true", help="DB에 실제로 쓴다(기본은 미리보기)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--yt-only", action="store_true",
                    help="발명품·오용·제품정체형만(기본은 원문형 전체 — 같은 병이 인스타형에도 있다)")
    a = ap.parse_args()

    c = sqlite3.connect(a.db)
    todo = []
    for sid, name, tpl, fj in c.execute(
            "SELECT id, name, templates_json, fit_categories_json FROM spine"):
        o = origin(tpl)
        if not o:
            continue
        try:
            fits = set(json.loads(fj or "[]"))
        except Exception:                  # noqa: BLE001
            fits = set()
        if a.yt_only and not (fits & YT_TYPES):
            continue
        if not is_cut(o):
            continue
        if a.ids and o.get("hit_id") not in a.ids.split(","):
            continue
        todo.append((sid, name, o))
    if a.limit:
        todo = todo[:a.limit]
    print("대상 %d개%s\n" % (len(todo), "" if a.apply else "  (미리보기 — 쓰려면 --apply)"))

    work = tempfile.mkdtemp(prefix="rescue_")
    ok = skip = fail = 0
    for sid, _name, o in todo:
        vid = o.get("hit_id")
        full, why = fetch_full_text(vid, work)
        if not full:
            print("  #%-4d FAIL %-12s %s" % (sid, vid, why), flush=True)
            fail += 1
            continue
        cells = resplit(full)
        if len(cells) < 4:                 # 칸이 너무 적으면 자르기가 실패한 것
            print("  #%-4d SKIP %-12s 칸 %d개만 통과" % (sid, vid, len(cells)), flush=True)
            skip += 1
            continue
        if is_cut({"cells": cells}):
            print("  #%-4d SKIP %-12s 다시 잘라도 미완결" % (sid, vid), flush=True)
            skip += 1
            continue
        old_last = (o["cells"][-1].get("text") or "")[:24]
        print("  #%-4d OK   %-12s 칸 %d개  끝: %r → %r"
              % (sid, vid, len(cells), old_last, cells[-1]["text"][-30:]), flush=True)
        ok += 1
        if a.apply:
            tpl = json.loads(c.execute("SELECT templates_json FROM spine WHERE id=?",
                                       (sid,)).fetchone()[0] or "{}")
            tpl["_origin"]["cells"] = cells
            tpl["_origin"]["rescued"] = "whisper"      # 되살린 것임을 남긴다
            c.execute("UPDATE spine SET templates_json=? WHERE id=?",
                      (json.dumps(tpl, ensure_ascii=False), sid))
            c.commit()                     # 한 편씩 커밋 — 중간에 끊겨도 앞선 성과가 남는다
    print("\n살림 %d · 건너뜀 %d · 실패 %d%s"
          % (ok, skip, fail, "" if a.apply else "  (아직 DB 안 씀)"))


if __name__ == "__main__":
    main()
