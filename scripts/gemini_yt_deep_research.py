"""
Gemini 딥리서치 → 유튜브 대본 생성
- Gemini Interactions API (deep-research-preview-04-2026) 사용
- brief 파일을 입력받아 대본 생성 후 channel/yt/에 저장

사용:
  python scripts/gemini_yt_deep_research.py brief_A_gemini리서치.md
  python scripts/gemini_yt_deep_research.py brief_순환매_20260604.md --max 모델명
"""
import sys, os, time, argparse
from datetime import date
from pathlib import Path
from google import genai
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
ENV  = ROOT / '.env'

env = {}
if ENV.exists():
    for line in ENV.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('❌ GEMINI_API_KEY 없음 (.env 또는 환경변수 설정 필요)'); sys.exit(1)

TODAY = date.today().strftime('%Y-%m-%d')
YT_DIR = ROOT / 'channel' / 'yt'

SCRIPT_SYSTEM = f"""오늘 날짜는 {TODAY}이야.
너는 한국 주식 유튜브 채널 "로또의 스탁브레인"의 전문 대본 작가야.

[채널 원칙]
- 70% 순수 정보 (내 시스템·서비스 언급 절대 금지)
- 20% 간접 노출 (방법론만, 광고 X)
- 10% CTA (마지막 씬 S8에서만 딱 한 번)

[대본 형식]
- S1~S8 씬 구조로 작성
- 각 씬: [씬번호] [씬제목] | 분량: XX초
- 훅(S1)은 첫 3초 안에 시청자를 잡아야 함
- 전문 용어는 비유로 풀어서 설명
- 구체적 숫자·날짜·사건 반드시 포함
- 총 영상 길이: 8~10분

[리서치 기준]
- 실제 계약·공시·수치로만 근거 제시
- 모르는 건 모른다고 해 (허수 금지)
- 한국 상장사 기준"""


def run_deep_research(brief_text: str, model: str) -> str:
    client = genai.Client(api_key=API_KEY)

    prompt = f"""{SCRIPT_SYSTEM}

아래 브리프를 기반으로 유튜브 대본을 작성해줘.
딥리서치로 최신 데이터·사건·수치를 충분히 조사한 뒤 대본에 반영해.

=== BRIEF ===
{brief_text}
=============

대본 형식 그대로 완성본으로 줘."""

    print(f"🔬 Gemini 딥리서치 시작 (모델: {model})")
    print("⏳ 완료까지 3~20분 소요될 수 있습니다...")

    import warnings
    warnings.filterwarnings('ignore')

    interaction = client.interactions.create(
        input=prompt,
        agent=model,
        background=True,
    )
    print(f"📡 작업 ID: {interaction.id}")

    dots = 0
    while interaction.status == "in_progress":
        time.sleep(15)
        interaction = client.interactions.get(interaction.id)
        dots += 1
        print(f"\r⏳ 리서치 진행 중... {dots * 15}초 경과", end='', flush=True)

    print()
    if interaction.status == "failed":
        print(f"❌ 딥리서치 실패: {interaction.to_dict()}")
        sys.exit(1)

    return interaction.output_text or ""


def main():
    parser = argparse.ArgumentParser(description='Gemini 딥리서치 → 유튜브 대본')
    parser.add_argument('brief', help='브리프 파일명 (channel/yt/ 안의 파일)')
    parser.add_argument('--max', action='store_true', help='최고 성능 모델 사용 (기본: preview)')
    args = parser.parse_args()

    model = 'deep-research-max-preview-04-2026' if args.max else 'deep-research-preview-04-2026'

    brief_path = YT_DIR / args.brief
    if not brief_path.exists():
        brief_path = ROOT / args.brief
    if not brief_path.exists():
        print(f'❌ 브리프 파일 없음: {args.brief}')
        sys.exit(1)

    brief_text = brief_path.read_text(encoding='utf-8')
    print(f"📄 브리프 읽기: {brief_path.name}")

    result = run_deep_research(brief_text, model)

    stem = brief_path.stem.replace('brief_', '')
    out_name = f"script_{stem}_gemini.md"
    out_path = YT_DIR / out_name

    header = f"# 대본: {stem}\n> 생성일: {TODAY} | 모델: {model}\n> 원본 브리프: {brief_path.name}\n\n---\n\n"
    out_path.write_text(header + result, encoding='utf-8')

    print(f"\n✅ 대본 저장 완료: channel/yt/{out_name}")
    return out_path


if __name__ == '__main__':
    main()
