// GB_Thumb_C — 좌우 분할 / 텍스트 좌 + 비주얼 우 (대담한 타이포그래피)
import { AbsoluteFill } from 'remotion';
import { C, FONT } from '../constants';

export const GB_Thumb_C = () => (
  <AbsoluteFill style={{ background: '#000', fontFamily: FONT, overflow: 'hidden' }}>

    {/* 우측 패널 배경 */}
    <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 380, background: 'rgba(0,255,208,0.04)', borderLeft: '1px solid rgba(0,255,208,0.12)' }} />

    {/* 배경 노이즈 텍스처 (큰 반투명 "기회" 워터마크) */}
    <div style={{
      position: 'absolute', left: -30, top: 20,
      fontSize: 440, fontWeight: 900, color: 'rgba(255,255,255,0.02)',
      lineHeight: 1, userSelect: 'none', letterSpacing: -20,
    }}>
      기회
    </div>

    {/* 좌측 메인 텍스트 */}
    <div style={{ position: 'absolute', left: 60, top: 0, bottom: 0, width: 840, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6 }}>

      {/* 내일부터 — 작은 라벨 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <div style={{ width: 40, height: 3, background: C.main, borderRadius: 2 }} />
        <div style={{ fontSize: 30, fontWeight: 800, color: C.main, letterSpacing: 6 }}>내일부터</div>
      </div>

      {/* 국민성장펀드 */}
      <div style={{ fontSize: 100, fontWeight: 900, color: '#fff', lineHeight: 1, letterSpacing: -2 }}>
        국민성장
      </div>
      <div style={{ fontSize: 100, fontWeight: 900, color: '#fff', lineHeight: 1, letterSpacing: -2, marginTop: -8 }}>
        펀드
      </div>

      {/* 구분선 */}
      <div style={{ width: '100%', height: 3, background: 'linear-gradient(90deg, #FF4336 0%, #FF9800 40%, #00FFD0 70%, transparent 100%)', margin: '14px 0', borderRadius: 2 }} />

      {/* 이것 때문에 기회입니다 */}
      <div style={{ fontSize: 56, fontWeight: 900, lineHeight: 1.2 }}>
        <span style={{ color: '#888' }}>이것 때문에</span><br />
        <span style={{ color: '#FF4336', fontSize: 80 }}>기회입니다.</span>
      </div>

    </div>

    {/* 우측 비주얼 패널 */}
    <div style={{
      position: 'absolute', right: 0, top: 0, bottom: 0, width: 380,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      gap: 20,
    }}>
      {/* 메인 이모지 */}
      <div style={{ fontSize: 130, lineHeight: 1 }}>💰</div>

      {/* 6/15 카운트 */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 20, color: '#555', letterSpacing: 3, marginBottom: 4 }}>STARTS</div>
        <div style={{ fontSize: 64, fontWeight: 900, color: C.main, lineHeight: 1, textShadow: '0 0 20px rgba(0,255,208,0.5)' }}>6/15</div>
        <div style={{ fontSize: 18, color: '#555', marginTop: 4, letterSpacing: 2 }}>실제 집행</div>
      </div>

      {/* 수혜주 태그 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '80%' }}>
        {[
          { name: '엘앤에프', color: '#FF4336' },
          { name: '에코프로비엠', color: '#FF9800' },
        ].map(({ name, color }) => (
          <div key={name} style={{ background: `${color}15`, border: `1px solid ${color}50`, borderRadius: 8, padding: '7px 16px', textAlign: 'center', fontSize: 18, fontWeight: 700, color }}>
            {name}
          </div>
        ))}
      </div>
    </div>

    {/* 채널명 */}
    <div style={{ position: 'absolute', bottom: 22, left: 60, fontSize: 18, color: '#333', fontWeight: 600, letterSpacing: 2 }}>
      로또의 주식인사이트
    </div>

  </AbsoluteFill>
);
