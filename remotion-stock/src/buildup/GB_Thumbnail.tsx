// GB_Thumbnail — 국민성장펀드 유튜브 썸네일 (1280×720 정적)
// 텍스트: "국민성장펀드 놓쳤죠? / 2차 전에 이것만 보세요"
import { AbsoluteFill } from 'remotion';
import { C, FONT, GLOW } from '../constants';

export const GB_Thumbnail = () => (
  <AbsoluteFill style={{ background: '#000', fontFamily: FONT, overflow: 'hidden' }}>

    {/* ── 배경 글로우 레이어 ── */}
    {/* 좌상단: 빨간 (완판/긴박감) */}
    <div style={{ position: 'absolute', top: -120, left: -80, width: 600, height: 500, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,67,54,0.22) 0%, transparent 70%)', pointerEvents: 'none' }} />
    {/* 우하단: 민트 (기회) */}
    <div style={{ position: 'absolute', bottom: -80, right: -60, width: 500, height: 400, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,255,208,0.18) 0%, transparent 70%)', pointerEvents: 'none' }} />

    {/* ── 완판 스탬프 (우상단) ── */}
    <div style={{
      position: 'absolute', top: 36, right: 48,
      width: 148, height: 148, borderRadius: '50%',
      border: '5px solid #FF4336',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      transform: 'rotate(15deg)',
      boxShadow: '0 0 24px rgba(255,67,54,0.6)',
    }}>
      <div style={{ fontSize: 13, fontWeight: 900, color: '#FF4336', letterSpacing: 3 }}>6,000억</div>
      <div style={{ fontSize: 34, fontWeight: 900, color: '#FF4336', lineHeight: 1, letterSpacing: 1 }}>완판</div>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#FF4336', letterSpacing: 2, marginTop: 2 }}>SOLD OUT</div>
    </div>

    {/* ── 메인 콘텐츠 ── */}
    <div style={{
      position: 'absolute', inset: 0,
      display: 'flex', flexDirection: 'column',
      justifyContent: 'center',
      paddingLeft: 64, paddingRight: 220,
      gap: 0,
    }}>
      {/* 라벨 */}
      <div style={{
        fontSize: 28, fontWeight: 700, color: C.textSub,
        letterSpacing: 4, marginBottom: 12,
      }}>
        국민성장펀드
      </div>

      {/* 메인 텍스트 1: 놓쳤죠? */}
      <div style={{
        fontSize: 148, fontWeight: 900, color: '#FF4336', lineHeight: 0.95,
        textShadow: '0 0 40px rgba(255,67,54,0.5)',
        letterSpacing: -2,
      }}>
        놓쳤죠?
      </div>

      {/* 구분선 */}
      <div style={{
        width: 560, height: 3,
        background: 'linear-gradient(90deg, #FF4336 0%, #00FFD0 60%, transparent 100%)',
        margin: '18px 0',
        borderRadius: 2,
      }} />

      {/* 메인 텍스트 2 */}
      <div style={{
        fontSize: 68, fontWeight: 900, color: C.textPrimary, lineHeight: 1.15,
        letterSpacing: -1,
      }}>
        2차 전에<br />
        <span style={{ color: C.main, textShadow: GLOW.mid.text }}>이것만 보세요</span>
      </div>

      {/* 서브 텍스트 */}
      <div style={{
        marginTop: 20, fontSize: 30, fontWeight: 600,
        color: '#aaa', letterSpacing: 1,
      }}>
        진짜 수혜주는 따로 있습니다
      </div>

      {/* 수혜주 태그 */}
      <div style={{ display: 'flex', gap: 14, marginTop: 22 }}>
        {[
          { name: '엘앤에프', tag: '🔴 1군', color: '#FF4336' },
          { name: '에코프로비엠', tag: '🟠 2군', color: '#FF9800' },
        ].map(({ name, tag, color }) => (
          <div key={name} style={{
            background: `${color}18`, border: `2px solid ${color}80`,
            borderRadius: 40, padding: '8px 22px',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <span style={{ fontSize: 18, fontWeight: 800, color, letterSpacing: 1 }}>{tag}</span>
            <span style={{ fontSize: 20, fontWeight: 900, color: '#fff' }}>{name}</span>
          </div>
        ))}
      </div>
    </div>

    {/* ── 우측 큰 이모지 ── */}
    <div style={{
      position: 'absolute', right: 56, bottom: 60,
      fontSize: 220, lineHeight: 1,
      filter: 'drop-shadow(0 0 30px rgba(0,255,208,0.4))',
    }}>
      💰
    </div>

    {/* ── 채널 워터마크 ── */}
    <div style={{
      position: 'absolute', bottom: 22, left: 64,
      fontSize: 20, color: '#444', fontWeight: 600, letterSpacing: 2,
    }}>
      로또의 주식인사이트
    </div>

  </AbsoluteFill>
);
