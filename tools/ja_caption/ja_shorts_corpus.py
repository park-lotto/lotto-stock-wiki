"""일본 쇼핑 쇼츠 실물 말투 모음(관제 254, 2026-10-23 사장님 "일본 쇼츠 10편 받아서 어투 비교").

해시태그 쇼츠 목록(유튜브) → 조회수 높은 순으로 소리만 받기 → 제미나이 받아쓰기 → 내레이션 있는 것만 N편 저장.

  py tools/ja_caption/ja_shorts_corpus.py <저장폴더> [편수=10]
  → <저장폴더>/corpus.json  [{id, views, title, lines:[...]}]
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TAGS = ["便利グッズ", "買ってよかった", "神アイテム", "楽天購入品", "Amazon購入品", "キッチングッズ"]
PROMPT = ("この動画の音声に入っている日本語のナレーション(人の話し声)を、聞こえた通りに一字一句書き起こしてください。"
          "文ごとに1行。BGMや効果音だけで話し声がなければ lines は空配列。字幕の文字ではなく音声だけ。")


def candidates(per=25):
    seen = {}
    for t in TAGS:
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "-I", f"1:{per}", "--print",
                            "%(id)s\t%(view_count)s\t%(title)s", f"https://www.youtube.com/hashtag/{t}/shorts"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        for ln in r.stdout.splitlines():
            vid, views, title = (ln.split("\t") + ["", ""])[:3]
            if views.isdigit():
                seen.setdefault(vid, (int(views), title))
    return sorted(seen.items(), key=lambda kv: -kv[1][0])


def transcribe(mp3):
    """번역과 같은 깔때기(script_generate._call_json: Vertex → 키풀)로 소리를 받아쓴다."""
    from google.genai import types
    from shopping_shorts import script_generate
    part = types.Part.from_bytes(data=Path(mp3).read_bytes(), mime_type="audio/mpeg")
    got = script_generate._call_json([part, PROMPT], {
        "type": "object", "properties": {"lines": {"type": "array", "items": {"type": "string"}}}}) or {}
    return [x.strip() for x in got.get("lines", []) if x.strip()]


def main(out, n=10):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    got = []
    for vid, (views, title) in candidates():
        if len(got) >= n:
            break
        mp3 = out / f"{vid}.mp3"
        if not mp3.exists():
            subprocess.run([sys.executable, "-m", "yt_dlp", "-q", "-x", "--audio-format", "mp3", "--audio-quality", "9",
                            "--match-filter", "duration<=75", "-o", str(out / f"{vid}.%(ext)s"),
                            f"https://www.youtube.com/shorts/{vid}"], capture_output=True)
        if not mp3.exists():
            continue
        lines = transcribe(mp3)
        jp = "".join(lines)
        # 내레이션 판정: 일본어 가나가 40자 이상
        if sum(1 for ch in jp if "぀" <= ch <= "ヿ") < 40:
            print("말소리 없음", vid); continue
        got.append({"id": vid, "views": views, "title": title, "lines": lines})
        print(len(got), vid, views, title[:40])
    (out / "corpus.json").write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10)
