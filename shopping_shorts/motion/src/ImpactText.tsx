import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

// 임팩트 텍스트: 대사 강조어를 화면 상단에 민트로 슬램. 단어는 inputProps로 주입.
// 좌표를 안 타는(화면 고정) 효과라 대사 텍스트만으로 자동 발사해도 안전한 계열.
export type ImpactTextProps = {word: string; position?: 'top' | 'bottom'};

export const ImpactText: React.FC<ImpactTextProps> = ({word, position = 'top'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  // 살짝 오버슈트하는 슬램: 작게+기울어져 들어와 튕겼다가 자리잡음.
  const enter = spring({frame, fps, config: {damping: 10, stiffness: 220, mass: 0.7}});
  const scale = interpolate(enter, [0, 1], [0.4, 1]);
  const rot = interpolate(enter, [0, 1], [-6, 0]);
  const opacity = interpolate(frame, [0, 4], [0, 1], {extrapolateRight: 'clamp'});
  // 릴스 중앙대(30~45%)엔 자체 자막이 박혀 있어 상/하단만 쓴다.
  const marginTop = position === 'bottom' ? '76%' : '10%';
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center', backgroundColor: 'transparent'}}>
      <div
        style={{
          marginTop,
          maxWidth: '86%',
          textAlign: 'center',
          fontFamily: '"Malgun Gothic","맑은 고딕",system-ui,sans-serif',
          fontWeight: 900,
          fontSize: 92,
          lineHeight: 1.1,
          letterSpacing: '-0.03em',
          wordBreak: 'keep-all',
          opacity,
          transform: `scale(${scale}) rotate(${rot}deg)`,
          // 어두운 요리 화면 위 가시성: 민트 그라데이션 + 짙은 외곽선 + 민트 글로우.
          backgroundImage: 'linear-gradient(180deg,#c9fff2,#2ee6c5,#12b39a)',
          WebkitBackgroundClip: 'text',
          backgroundClip: 'text',
          color: 'transparent',
          WebkitTextStroke: '3px #06302a',
          paintOrder: 'stroke fill',
          textShadow: '0 4px 18px #000, 0 0 34px #2ee6c5aa, 0 0 64px #2ee6c566',
        }}
      >
        {word}
      </div>
    </AbsoluteFill>
  );
};
