import { continueRender, delayRender } from 'remotion';

const handle = delayRender('Loading fonts');

const link = document.createElement('link');
link.rel = 'stylesheet';
// Noto Sans KR(본문) + Noto Serif KR / Fraunces(Claude 세리프 디스플레이)
link.href =
  'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&family=Noto+Serif+KR:wght@500;600;700;900&family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Archivo:wght@700;800;900&family=Space+Mono:wght@400;700&display=swap';
link.onload = () => continueRender(handle);
link.onerror = () => continueRender(handle);
document.head.appendChild(link);
