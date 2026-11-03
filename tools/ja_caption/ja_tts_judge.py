"""일본어 TTS 발음 판정(관제 254, 2026-10-23 사장님 "tts도 여러개 해서 발음이 일본어 자연스러운지 확인").

index.json([{preset,i,sent,file}]) 의 mp3 마다 제미나이에게 ①받아쓰기 ②원어민 자연스러움 1~5 ③틀린 발음·억양을 묻는다.
기준 비교용으로 일본인 실제 쇼츠 소리(ref mp3)도 같은 질문으로 채점한다(채점기가 후한지 재는 눈금).

  py tools/ja_caption/ja_tts_judge.py <index.json> [ref.mp3 ...]
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SCHEMA = {"type": "object", "properties": {
    "heard": {"type": "string"}, "native_score": {"type": "integer"},
    "accent": {"type": "string"}, "issues": {"type": "array", "items": {"type": "string"}}},
    "required": ["heard", "native_score", "accent", "issues"]}


def judge(mp3, sent=""):
    from google.genai import types
    from shopping_shorts import script_generate
    q = ("あなたは日本語ネイティブの音声ディレクターです。この音声を厳しく評価してください。"
         "heard=聞こえた通りの書き起こし。native_score=日本人が聞いて自然か(5=ネイティブと区別不能、3=意味は分かるが外国人っぽい、1=聞き取れない)。"
         "accent=外国語なまり(韓国語なまり等)があれば具体的に、なければ「なし」。"
         "issues=読み間違い・不自然なアクセントやイントネーション・間の悪さを単語単位で。" +
         (f"\n台本: {sent}" if sent else ""))
    part = types.Part.from_bytes(data=Path(mp3).read_bytes(), mime_type="audio/mpeg")
    return script_generate._call_json([part, q], SCHEMA) or {}


def main(index, refs):
    rows = json.loads(Path(index).read_text(encoding="utf-8"))
    for r in refs:
        rows.append({"preset": "REF(일본인)", "i": Path(r).stem, "sent": "", "file": r})
    for r in rows:
        r["judge"] = judge(r["file"], r["sent"])
        j = r["judge"]
        print(f"{r['preset']:<20} {r['i']} 점수={j.get('native_score')} 사투리={j.get('accent','')[:40]} | {'; '.join(j.get('issues', []))[:120]}")
    Path(index).with_name("judge.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
