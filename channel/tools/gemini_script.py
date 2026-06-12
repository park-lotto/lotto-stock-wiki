"""
yt-gemini-pipeline STEP 2 실행기
브리프 파일 → Gemini API (Google Search grounding 딥리서치+스토리+대본) → 결과 저장

사용법:
  python channel/tools/gemini_script.py --brief channel/yt/brief_순환매_20260604.md
  python channel/tools/gemini_script.py --brief channel/yt/brief_순환매_20260604.md --output channel/yt/script_순환매_gemini.md
"""
import sys, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.yt_agents.gemini_client import call_with_grounding

SYSTEM_PROMPT_PATH = ROOT / '.agents/skills/yt-gemini-pipeline/gemini_system_prompt.md'


def load_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.exists():
        raw = SYSTEM_PROMPT_PATH.read_text(encoding='utf-8')
        lines = raw.splitlines()
        start = next((i for i, l in enumerate(lines) if l.startswith('[당신의 역할]')), 0)
        return '\n'.join(lines[start:])
    return ''


def run(brief_path: str, output_path: str = None, model: str = 'gemini-3-flash-preview') -> str:
    brief_file = Path(brief_path)
    if not brief_file.exists():
        print(f"[error] 브리프 파일 없음: {brief_path}")
        sys.exit(1)

    brief_text = brief_file.read_text(encoding='utf-8')
    system = load_system_prompt()

    print(f"[brief] {brief_file.name}")
    print(f"[model] {model}")
    print("[search] Google Search grounding 활성화")
    print("[running] Gemini 딥리서치 + 대본 작성 중... (2~5분 소요)")

    result, sources = call_with_grounding(brief_text, system=system, model=model, temperature=0.7)

    # ── 검수: 실제 검색 사용 여부 확인 ──────────────────────────
    print("\n[검수] Google Search grounding 실제 사용 여부:")
    if sources:
        print(f"  [PASS] 실제 검색 {len(sources)}건 확인됨")
        for i, s in enumerate(sources[:5], 1):
            title = s.get('title', '제목없음')[:60]
            url   = s.get('url', '')[:80]
            print(f"  [{i}] {title}")
            print(f"       {url}")
        if len(sources) > 5:
            print(f"  ... 외 {len(sources)-5}건")
    else:
        print("  [WARN] 검색 출처 없음 - Gemini가 학습 데이터만 사용했을 수 있음")
        print("         모델이 grounding을 지원하지 않거나 검색이 필요 없다고 판단한 것")

    # ── 출처 목록을 대본 하단에 추가 저장 ─────────────────────
    output_content = result
    if sources:
        source_lines = ["\n\n---\n## [검색 출처 — Gemini Grounding]\n"]
        for i, s in enumerate(sources, 1):
            source_lines.append(f"{i}. [{s.get('title','')}]({s.get('url','')})")
        output_content += '\n'.join(source_lines)

    if not output_path:
        stem = brief_file.stem.replace('brief_', 'script_') + '_gemini'
        output_path = str(brief_file.parent / f"{stem}.md")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(output_content, encoding='utf-8')

    print(f"\n[done] 완료 -> {out_file}")
    return result


def main():
    parser = argparse.ArgumentParser(description='Gemini 대본 생성기 (Google Search grounding)')
    parser.add_argument('--brief',  required=True, help='브리프 파일 경로')
    parser.add_argument('--output', default=None,  help='출력 파일 경로')
    parser.add_argument('--model',  default='gemini-3-flash-preview', help='Gemini 모델')
    args = parser.parse_args()
    run(args.brief, args.output, args.model)


if __name__ == '__main__':
    main()
