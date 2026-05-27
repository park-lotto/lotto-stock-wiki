import { continueRender, delayRender } from 'remotion';

const handle = delayRender('Loading Noto Sans KR');

const link = document.createElement('link');
link.rel = 'stylesheet';
link.href = 'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap';
link.onload = () => continueRender(handle);
link.onerror = () => continueRender(handle);
document.head.appendChild(link);
