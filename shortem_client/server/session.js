// 접속 자리(관제 296) — 켜져 있는 동안 서버에 이 PC 가 쓰고 있다고 알린다. 판정 주인은 서버 claude_portal._guard_session.
//   실패는 무시한다: 막혔으면 다음 라이선스·제작 호출이 이유를 고객에게 알린다.
import { api } from './api.js';

export const holdNow = () => api.session({ action: 'hold' }).catch(() => {});

export function holdSession({ everyMs = 60000 } = {}) {
  holdNow();
  const timer = setInterval(holdNow, Number(process.env.SHORTEM_HB_MS) || everyMs);
  if (timer.unref) timer.unref();
  const bye = () => { clearInterval(timer); api.session({ action: 'release' }).catch(() => {}); };
  process.stdin.once('end', bye);
  process.once('SIGTERM', bye);
}
