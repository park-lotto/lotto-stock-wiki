// B3 — 06:00 위키 마크다운 자동 추가
// VSCode/Obsidian 스타일 마크다운 에디터 UI
// stock_SK하이닉스.md 파일이 열려있고, Claude의 분석 결과가 새 행으로 자동 추가됨
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { C, FONT, GLOW } from '../constants';

const DUR = 360;

// VSCode 다크 모드 컬러
const VS = {
  bg:       '#1E1E1E',
  side:     '#252526',
  tabBar:   '#2D2D30',
  tabActive:'#1E1E1E',
  text:     '#D4D4D4',
  textSub:  '#858585',
  accent:   '#0E639C',     // VSCode 블루
  green:    '#6A9955',     // 마크다운 헤더
  red:      '#CE9178',     // 문자열
  yellow:   '#DCDCAA',     // 함수
  highlight:'#264F78',     // 선택 영역 (파랑)
  newLine:  '#1F3A28',     // 새 행 추가 (어두운 초록)
};

// 파일 트리
const FILES = [
  { name: '📁 wiki', open: true, indent: 0 },
  { name: '📁 L5_섹터', open: true, indent: 1 },
  { name: '📁 반도체', open: true, indent: 2 },
  { name: '📁 stock', open: true, indent: 3 },
  { name: '📄 stock_SK하이닉스.md', indent: 4, active: true, modified: true },
  { name: '📄 stock_삼성전자.md', indent: 4 },
  { name: '📄 stock_한미반도체.md', indent: 4 },
  { name: '📄 sector_반도체.md', indent: 3 },
  { name: '📁 조선', indent: 2 },
  { name: '📁 방산', indent: 2 },
];

// 기존 라인 (회색으로 이미 있음)
const OLD_LINES = [
  '# SK하이닉스 (000660)',
  '> 섹터: 반도체 / 서브섹터: HBM',
  '',
  '## 종합 스토리',
  '> 2026-05-26 기준: HBM4 슈퍼사이클 초입. 외인 4일 연속 매수.',
  '',
  '## 최신 이벤트',
  '| 날짜       | 내용                          | 출처            | 신호 |',
  '|------------|-------------------------------|-----------------|------|',
  '| 2026-05-26 | 1Q 실적 어닝서프 +18%        | report/NH       | 🔴   |',
  '| 2026-05-25 | NVDA HBM4 Vera Rubin 언급    | news/blog      | 🔴   |',
];

// 새로 추가되는 라인 (한 줄씩 등장)
const NEW_LINES = [
  '| 2026-05-27 | HBM4 베이스다이 95% 독점 확실 | telegram/반도체 | 🔴   |',
];

export const B3_Wiki = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const prog = interpolate(f, [15, DUR - 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const timeOp = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });

  // 새 라인 등장 — prog 0.30~0.50
  const newLineProg = interpolate(prog, [0.30, 0.50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 새 라인 글자 수 (타이핑)
  const newLineLen = Math.floor(newLineProg * NEW_LINES[0].length);
  const newLineText = NEW_LINES[0].substring(0, newLineLen);

  // 새 라인 하이라이트 펄스 (등장 후)
  const highlightPulse = newLineProg > 0.95
    ? Math.sin(f * 0.08) * 0.4 + 0.6
    : 0;

  // 저장 인디케이터 (점선 → 원) — prog 0.60~0.70
  const savedProg = interpolate(prog, [0.60, 0.70], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 우측 가이드
  const guideOp = interpolate(prog, [0.40, 0.50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // 통계 — 누적 노드 카운트
  const counterOp = interpolate(prog, [0.65, 0.78], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const counterNum = Math.floor(interpolate(prog, [0.65, 0.85], [1247, 1248], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));

  // 마크다운 라인 렌더 (간단 신택스 하이라이트)
  const renderMd = (line: string, key: number, isNew = false) => {
    let color = VS.text;
    let weight = 400;
    if (line.startsWith('# ')) { color = VS.green; weight = 700; }
    else if (line.startsWith('## ')) { color = VS.green; weight = 700; }
    else if (line.startsWith('> ')) { color = VS.textSub; weight = 500; }

    // 표 셀 강조
    if (line.startsWith('|') && line.includes('🔴')) {
      // 🔴 부분만 강조
      return (
        <div key={key} style={{
          color, fontWeight: weight, fontSize: 16, lineHeight: 1.7,
          fontFamily: '"Consolas", "Menlo", "Cascadia Code", monospace',
          whiteSpace: 'pre',
          background: isNew ? `rgba(106, 153, 85, ${0.15 + highlightPulse * 0.15})` : 'transparent',
          paddingLeft: isNew ? 6 : 0, marginLeft: isNew ? -6 : 0,
          borderLeft: isNew ? `2px solid ${VS.green}` : 'none',
        }}>{line}</div>
      );
    }

    return (
      <div key={key} style={{
        color, fontWeight: weight, fontSize: 16, lineHeight: 1.7,
        fontFamily: '"Consolas", "Menlo", "Cascadia Code", monospace',
        whiteSpace: 'pre',
      }}>{line || ' '}</div>
    );
  };

  return (
    <AbsoluteFill style={{ background: '#000000', opacity: fadeIn, fontFamily: FONT }}>

      {/* 우상단 샘플 라벨 */}
      <div style={{
        position: 'absolute', top: 30, right: 50,
        color: C.textSub, fontSize: 18, fontWeight: 600, letterSpacing: 3,
        opacity: timeOp, zIndex: 100,
      }}>SAMPLE B3 · 06:00 WIKI</div>

      {/* 좌상단 시간 */}
      <div style={{
        position: 'absolute', top: 40, left: 60,
        opacity: timeOp, zIndex: 100,
      }}>
        <div style={{ color: C.textSub, fontSize: 16, fontWeight: 500, letterSpacing: 4, marginBottom: 4 }}>NOW</div>
        <div style={{
          color: C.main, fontSize: 72, fontWeight: 900,
          fontFamily: '"Consolas", "Menlo", monospace',
          textShadow: GLOW.mid.text, letterSpacing: 2, lineHeight: 1,
        }}>06:00</div>
      </div>

      {/* === VSCode 본체 === */}
      <div style={{
        position: 'absolute', left: 380, top: 80, width: 1200, height: 900,
        background: VS.bg, borderRadius: 8, overflow: 'hidden',
        boxShadow: '0 30px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.05)',
        display: 'flex', flexDirection: 'column',
      }}>
        {/* 타이틀바 */}
        <div style={{
          height: 32, background: '#3C3C3C', display: 'flex', alignItems: 'center',
          paddingInline: 14, gap: 8, borderBottom: `1px solid #2D2D30`,
        }}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FF5F57' }} />
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FEBC2E' }} />
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#28C840' }} />
          <div style={{
            flex: 1, textAlign: 'center', color: VS.textSub, fontSize: 12, fontWeight: 500,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            stock_SK하이닉스.md — 로또의 주식
            {savedProg > 0.5 && (
              <span style={{ color: VS.green, fontSize: 10, opacity: savedProg }}>● saved</span>
            )}
          </div>
        </div>

        {/* 메인 영역 */}
        <div style={{ flex: 1, display: 'flex' }}>
          {/* 좌측 사이드바 */}
          <div style={{
            width: 50, background: '#333333', borderRight: `1px solid #2D2D30`,
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, paddingTop: 14,
          }}>
            {['📁', '🔍', '⎇', '🔌', '⚙'].map((icon, i) => (
              <div key={i} style={{
                fontSize: 18, opacity: i === 0 ? 1 : 0.5,
                borderLeft: i === 0 ? `2px solid #fff` : '2px solid transparent',
                width: '100%', textAlign: 'center', paddingBlock: 2,
              }}>{icon}</div>
            ))}
          </div>

          {/* 파일 탐색기 */}
          <div style={{
            width: 280, background: VS.side, borderRight: `1px solid #2D2D30`,
            padding: '14px 0', overflow: 'hidden',
          }}>
            <div style={{
              color: VS.textSub, fontSize: 11, fontWeight: 700, letterSpacing: 2,
              paddingInline: 18, marginBottom: 8,
            }}>EXPLORER</div>
            {FILES.map((file, i) => (
              <div key={i} style={{
                paddingInline: 18 + file.indent * 14, paddingBlock: 3,
                color: file.active ? VS.text : VS.textSub,
                fontSize: 13, fontWeight: file.active ? 600 : 400,
                background: file.active ? '#37373D' : 'transparent',
                display: 'flex', alignItems: 'center', gap: 6,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {file.name}
                {file.modified && (
                  <div style={{
                    width: 6, height: 6, borderRadius: '50%', background: '#fff',
                    flexShrink: 0, opacity: savedProg < 0.5 ? 1 : 0,
                  }} />
                )}
              </div>
            ))}
          </div>

          {/* 에디터 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            {/* 탭 */}
            <div style={{
              height: 36, background: VS.tabBar, display: 'flex', alignItems: 'center',
              borderBottom: `1px solid #2D2D30`,
            }}>
              <div style={{
                height: '100%', display: 'flex', alignItems: 'center', gap: 8,
                paddingInline: 16, background: VS.tabActive,
                color: VS.text, fontSize: 13, fontWeight: 500,
                borderRight: `1px solid #2D2D30`,
              }}>
                📄 stock_SK하이닉스.md
                <span style={{
                  color: VS.text, opacity: savedProg < 0.5 ? 1 : 0,
                  fontSize: 16, fontWeight: 900,
                }}>●</span>
              </div>
              <div style={{
                paddingInline: 16, color: VS.textSub, fontSize: 13,
              }}>📄 sector_반도체.md</div>
            </div>

            {/* 코드 영역 */}
            <div style={{
              flex: 1, padding: '20px 24px', overflow: 'hidden',
              display: 'flex',
            }}>
              {/* 라인 번호 */}
              <div style={{
                color: VS.textSub, fontSize: 16, lineHeight: 1.7, paddingRight: 16,
                fontFamily: '"Consolas", "Menlo", monospace',
                textAlign: 'right', userSelect: 'none', opacity: 0.5,
                minWidth: 36,
              }}>
                {Array.from({ length: OLD_LINES.length + (newLineLen > 0 ? 1 : 0) }).map((_, i) => (
                  <div key={i}>{i + 1}</div>
                ))}
              </div>

              {/* 코드 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {OLD_LINES.map((line, i) => renderMd(line, i))}
                {newLineLen > 0 && renderMd(newLineText, OLD_LINES.length, true)}
              </div>
            </div>

            {/* 상태바 */}
            <div style={{
              height: 26, background: VS.accent,
              display: 'flex', alignItems: 'center',
              paddingInline: 16, gap: 16,
              color: '#fff', fontSize: 12, fontWeight: 500,
            }}>
              <span>⎇ main</span>
              <span>● {savedProg < 0.5 ? 'modifying...' : 'auto-saved'}</span>
              <div style={{ flex: 1 }} />
              <span>Markdown</span>
              <span>Ln {OLD_LINES.length + (newLineLen > 0 ? 1 : 0)}, Col {newLineLen}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 우측 가이드 */}
      <div style={{
        position: 'absolute', left: 1620, top: 280, width: 280,
        opacity: guideOp,
      }}>
        <div style={{
          color: C.main, fontSize: 22, fontWeight: 800, letterSpacing: 3,
          marginBottom: 12, textShadow: GLOW.weak.text,
        }}>지금 일어나는 일</div>
        <div style={{
          color: C.textPrimary, fontSize: 26, fontWeight: 700,
          lineHeight: 1.5, marginBottom: 18,
        }}>
          Claude가 분류한 정보가<br />
          종목 페이지에<br />
          새 행으로 누적
        </div>
        <div style={{ color: C.textSub, fontSize: 18, fontWeight: 500, lineHeight: 1.6 }}>
          내가 기억할 필요 없음<br />
          위키가 평생 기억
        </div>

        {/* 누적 노드 카운터 */}
        <div style={{ marginTop: 32, opacity: counterOp }}>
          <div style={{
            color: C.textSub, fontSize: 14, fontWeight: 600, letterSpacing: 3, marginBottom: 6,
          }}>누적 노드</div>
          <div style={{
            color: C.main, fontSize: 64, fontWeight: 900,
            textShadow: GLOW.mid.text, lineHeight: 1,
            fontFamily: '"Consolas", "Menlo", monospace',
          }}>{counterNum.toLocaleString()}</div>
          <div style={{ color: C.textSub, fontSize: 16, marginTop: 4 }}>
            오늘 새벽 +312 추가
          </div>
        </div>
      </div>

      {/* 하단 자막 */}
      <div style={{
        position: 'absolute', bottom: 30, left: 0, right: 0,
        textAlign: 'center', opacity: timeOp,
      }}>
        <div style={{ color: C.textPrimary, fontSize: 28, fontWeight: 700, opacity: 0.7 }}>
          STAGE 3 · 누적
        </div>
      </div>

    </AbsoluteFill>
  );
};
