"""
유튜브 영상제작 에이전트 시스템
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사용법:
  python make_yt_video.py --idea "AI 자동화 시스템으로 주식 분석하는 법"
  python make_yt_video.py --idea "수급 빈집 찾는 법" --mode step   # 단계별 컨펌
  python make_yt_video.py --resume yt_20260531_120000               # 이어하기
  python make_yt_video.py --resume yt_20260531_120000 --from whisper  # 특정 단계부터

파이프라인:
  [1] 기획 직원    → 기획 검수
  [2] 대본 직원    → 대본 검수
  [3] Remotion 직원 → 영상 검수 (TSC + 연출)
  [4] 녹음 (사용자)
  [5] Whisper 싱크  → 싱크 검수
  [6] 렌더링 직원   → 배포 검수
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys, argparse
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.yt_agents.pipeline import run, load_state

def main():
    parser = argparse.ArgumentParser(
        description='YouTube 영상제작 에이전트 시스템',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--idea',   type=str, help='영상 아이디어 한 줄')
    parser.add_argument('--resume', type=str, help='이어하기: 파이프라인 ID')
    parser.add_argument('--from',   dest='start_from', type=str,
                        choices=['plan','script','remotion','record','whisper','render'],
                        help='특정 단계부터 시작')
    parser.add_argument('--mode',   type=str, default='auto',
                        choices=['auto','step'],
                        help='auto: 전자동 / step: 단계마다 컨펌')
    args = parser.parse_args()

    if args.resume:
        state = load_state(args.resume)
        if not state:
            print(f"파이프라인 {args.resume} 를 찾을 수 없습니다.")
            sys.exit(1)
        idea = state.get('idea', '')
        print(f"이어하기: {args.resume} | 아이디어: {idea}")
        run(idea, start_from=args.start_from, pipeline_id=args.resume, mode=args.mode)

    elif args.idea:
        run(args.idea, start_from=args.start_from, mode=args.mode)

    else:
        print(__doc__)
        print("\n아이디어를 입력하세요:")
        idea = input("  > ").strip()
        if not idea:
            sys.exit(0)
        run(idea, mode=args.mode)

if __name__ == '__main__':
    main()
