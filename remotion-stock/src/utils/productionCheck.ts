/**
 * Production Rules 자동 점검 시스템
 * 컴포넌트 빌드 시 자동 실행 — 위반 시 렌더 중단
 */

interface TextSpec {
  label_size: number;
  subtitle_size: number;
  body_size: number;
  title_size: number;
  number_size: number;
}

interface LayoutSpec {
  canvas_w: number;
  canvas_h: number;
  pip_w: number;
  pip_h: number;
  pip_right: number;
  pip_bottom: number;
  panel_right_x: number;
  panel_right_max_width: number;
  panel_right_max_y: number;
  subtitle_height_pct: number;
}

export function runProductionCheck(text: TextSpec, layout: LayoutSpec): void {
  const errors: string[] = [];
  const warns: string[] = [];

  // ── R1: 텍스트 최소 크기
  if (text.label_size < 16)
    errors.push(`R1 ✗ label_size=${text.label_size}px — 최소 16px 필요`);
  if (text.subtitle_size < 36)
    errors.push(`R1 ✗ subtitle_size=${text.subtitle_size}px — 최소 36px 필요`);
  if (text.body_size < 18)
    errors.push(`R1 ✗ body_size=${text.body_size}px — 최소 18px 필요`);
  if (text.title_size < 24)
    errors.push(`R1 ✗ title_size=${text.title_size}px — 최소 24px 필요`);

  // ── R2: PiP ↔ 우측 패널 겹침
  const pip_left_x = layout.canvas_w - layout.pip_right - layout.pip_w;  // PiP 좌측 x
  const pip_top_y  = layout.canvas_h - layout.pip_bottom - layout.pip_h; // PiP 상단 y
  const panel_right_left = layout.canvas_w - layout.panel_right_x - layout.panel_right_max_width;

  const x_overlap = panel_right_left < pip_left_x;
  const y_overlap = layout.panel_right_max_y > pip_top_y;

  if (x_overlap && y_overlap)
    errors.push(
      `R2 ✗ 우측 패널(x=${panel_right_left}) + PiP(x=${pip_left_x}) 겹침 — ` +
      `패널 max_width 줄이거나 panel_right_max_y(${layout.panel_right_max_y}) < pip_top(${pip_top_y}) 확인`
    );

  // ── R4: PiP ↔ 자막 안전 여백
  const pip_bottom_y      = layout.canvas_h - layout.pip_bottom;        // PiP 하단 y
  const subtitle_top_y    = layout.canvas_h * (1 - layout.subtitle_height_pct / 100);
  const pip_subtitle_gap  = subtitle_top_y - pip_bottom_y;

  if (pip_subtitle_gap < 20)
    errors.push(
      `R4 ✗ PiP 하단(${pip_bottom_y}px) ↔ 자막 상단(${subtitle_top_y}px) 간격 ${pip_subtitle_gap}px — 최소 20px 필요`
    );
  else if (pip_subtitle_gap < 40)
    warns.push(`R4 ⚠ PiP ↔ 자막 간격 ${Math.round(pip_subtitle_gap)}px — 촘촘함 (권장 40px+)`);

  // ── R3: 이미지 비율 (수동 체크 리마인더)
  warns.push('R3 — 이미지/로고 objectFit:cover 또는 contain 코드에서 직접 확인 필요');

  // ── 결과 출력
  if (errors.length > 0) {
    console.error('\n🚨 PRODUCTION RULES 위반 — 렌더 중단\n' +
      errors.map(e => `  ${e}`).join('\n') + '\n');
    throw new Error('Production check failed. Fix before rendering.');
  }

  if (warns.length > 0)
    warns.forEach(w => console.warn(`  ⚠ ${w}`));

  console.log('✅ Production Rules 전체 통과');
}

// ── S5 Claude Live 전용 스펙 점검 (좌측 윈도우 + 우측 컬럼 레이아웃)
export function checkS5ClaudeLiveSpec(): void {
  const errors: string[] = [];
  const warns: string[] = [];

  // R1 텍스트 최소 크기
  const text = { label: 18, subtitle: 44, body: 20, title: 32, number: 64, display: 56 };
  if (text.label < 18)    errors.push(`R1 ✗ label=${text.label}px < 18`);
  if (text.subtitle < 36) errors.push(`R1 ✗ subtitle=${text.subtitle}px < 36`);
  if (text.body < 18)     errors.push(`R1 ✗ body=${text.body}px < 18`);
  if (text.title < 24)    errors.push(`R1 ✗ title=${text.title}px < 24`);

  // R2 윈도우(좌) ↔ 우측 컬럼 겹침
  const window_right = 70 + 1120;     // 1190
  const right_col_x  = 1230;
  if (right_col_x < window_right)
    errors.push(`R2 ✗ 우측컬럼(x=${right_col_x}) < 윈도우 우단(${window_right}) — 겹침`);
  const gap = right_col_x - window_right;
  if (gap < 24) warns.push(`R2 ⚠ 윈도우↔컬럼 간격 ${gap}px (권장 24px+)`);

  // R2 우측 컬럼 우단 ↔ 안전 여백
  const right_col_right = 1230 + 650; // 1880
  if (right_col_right > 1920 - 32)
    errors.push(`R2 ✗ 우측컬럼 우단(${right_col_right}) > 안전선(1888)`);

  // R4 윈도우 하단 ↔ 자막
  const window_bottom = 170 + 630;            // 800
  const subtitle_top  = 1080 * (1 - 16 / 100); // 907.2
  const wsGap = subtitle_top - window_bottom;
  if (wsGap < 20) errors.push(`R4 ✗ 윈도우 하단(${window_bottom}) ↔ 자막(${Math.round(subtitle_top)}) 간격 ${Math.round(wsGap)}px < 20`);

  if (errors.length > 0) {
    console.error('\n🚨 [S5 Claude Live] PRODUCTION RULES 위반 — 렌더 중단\n' +
      errors.map(e => `  ${e}`).join('\n') + '\n');
    throw new Error('S5 Claude Live production check failed.');
  }
  if (warns.length > 0) warns.forEach(w => console.warn(`  ⚠ ${w}`));
  console.log('✅ [S5 Claude Live] Production Rules 전체 통과 (윈도우↔컬럼 40px, 윈도우↔자막 107px)');
}

// ── S5 Activation 전용 스펙 점검
export function checkS5Spec() {
  runProductionCheck(
    {
      label_size:    16,  // R1 ✓
      subtitle_size: 38,  // R1 ✓
      body_size:     20,  // R1 ✓
      title_size:    32,  // R1 ✓
      number_size:   56,  // R1 ✓
    },
    {
      canvas_w:             1920,
      canvas_h:             1080,
      pip_w:                340,
      pip_h:                191,
      pip_right:            36,
      pip_bottom:           210,   // R4: PiP 하단=870px, 자막 상단=907px → gap=37px ✓
      panel_right_x:        32,
      panel_right_max_width:360,   // R2: panel_left=1528, pip_left=1544 → x겹침 있으나 max_y=640<pip_top=679 ✓
      panel_right_max_y:    640,   // R2: pip_top=1080-210-191=679 → 39px 여유
      subtitle_height_pct:  16,
    }
  );
}
