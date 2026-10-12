(function (root) {
  'use strict';
  // 썸네일·장면꾸미기 공용 글자 그림자. 글자 크기(em)를 기준으로 같은 비율을 쓴다.
  root.TEXT_LOOK_CONTRACT = Object.freeze({
    shadowX: 0.10,
    shadowY: 0.13,
    shadowBlur: 0.06,
    shadowPasses: 3,
  });
})(window);
