// 접속 자리(관제 296) — 켜져 있는 동안 서버에 이 PC 가 쓰고 있다고 알린다. 판정 주인은 서버 claude_portal._guard_session.
//   실패는 무시한다: 막혔으면 다음 라이선스·제작 호출이 이유를 고객에게 알린다.
//   onBeat = 신호와 함께 할 일(숏클 팀 메시지 받기·멈춤 알리기, 관제 304 — 내용은 index.js → live.js). 스스로 실패를 처리한다.
import { api } from './api.js';

export const holdNow = () => api.session({ action: 'hold' }).catch(() => {});

export function holdSession({ everyMs = 60000, onBeat = null } = {}) {
  const beat = () => holdNow().then(() => (onBeat ? onBeat() : null)).catch(() => {});
  beat();
  const timer = setInterval(beat, Number(process.env.SHORTEM_HB_MS) || everyMs);
  if (timer.unref) timer.unref();
  const bye = () => { clearInterval(timer); api.session({ action: 'release' }).catch(() => {}); };
  process.stdin.once('end', bye);
  process.once('SIGTERM', bye);
}
