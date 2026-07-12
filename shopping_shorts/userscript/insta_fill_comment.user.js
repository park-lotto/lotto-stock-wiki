// ==UserScript==
// @name         로또 소통 · 인스타 댓글 자동채우기
// @namespace    lotto.shopping_shorts
// @version      1.0.0
// @description  소통큐에서 넘어온 댓글을 인스타 게시물 댓글칸에 자동으로 채운다. 전송·팔로우는 사용자가 직접(안전).
// @match        https://www.instagram.com/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==
(function () {
  "use strict";

  /* ===================== CONFIG (인스타 DOM 바뀌면 여기만 수선) ===================== */
  const CONFIG = {
    // 댓글 입력창 후보 셀렉터 — 위에서부터 먼저 잡히는 것 사용
    COMMENT_SELECTORS: [
      'textarea[aria-label*="댓글"]',
      'textarea[aria-label*="comment" i]',
      'form[method="POST"] textarea',
      'div[contenteditable="true"][role="textbox"][aria-label*="댓글"]',
      'div[contenteditable="true"][role="textbox"][aria-label*="comment" i]',
      'div[contenteditable="true"][role="textbox"]',
    ],
    WAIT_TIMEOUT_MS: 15000, // 댓글창 대기 최대
    WAIT_POLL_MS: 250,
    HUMANLIKE_TYPING: false, // true면 한 글자씩 랜덤 딜레이 타이핑(사용자가 직접 전송하므로 기본 off — 붙여넣기와 동일)
  };
  /* ================================================================================ */

  // 게시물/릴스 페이지에서만 동작
  const IS_POST = /^\/(p|reel|reels)\/[^/]+/.test(location.pathname);
  if (!IS_POST) return;

  // 해시 페이로드 파싱: #lotto_fill=<urlencoded base64(JSON)>
  const payload = readPayload();
  if (!payload || !payload.c) return; // 신호 없으면 평소 인스타 사용에 무영향

  // 중복 발사 가드: 해시 즉시 소거 + 세션 플래그
  const guardKey = "lottoFilled:" + (payload.sc || location.pathname);
  try {
    if (sessionStorage.getItem(guardKey)) return;
    sessionStorage.setItem(guardKey, "1");
  } catch (_) {}
  history.replaceState(null, "", location.pathname + location.search);

  run(payload.c).catch((e) => toast("❌ 자동채우기 실패: " + e.message, "#c0392b"));

  /* ------------------------------------------------------------------ */

  function readPayload() {
    const m = /(?:^|#)lotto_fill=([^&]+)/.exec(location.hash);
    if (!m) return null;
    try {
      const json = decodeURIComponent(escape(atob(decodeURIComponent(m[1]))));
      return JSON.parse(json);
    } catch (_) {
      return null;
    }
  }

  async function run(text) {
    const box = await waitForCommentBox();
    if (!box) {
      toast("⚠️ 댓글창을 못 찾음 — 직접 붙여넣기(Ctrl+V) 하세요", "#b9770e");
      return;
    }
    box.focus();
    if (CONFIG.HUMANLIKE_TYPING) {
      await typeHumanlike(box, text);
    } else {
      fillAtOnce(box, text);
    }
    toast("✅ 댓글 채워둠 — 확인 후 직접 전송·팔로우 하세요", "#1e7e34");
  }

  function waitForCommentBox() {
    return new Promise((resolve) => {
      const deadline = Date.now() + CONFIG.WAIT_TIMEOUT_MS;
      (function poll() {
        const el = findCommentBox();
        if (el) return resolve(el);
        if (Date.now() > deadline) return resolve(null);
        setTimeout(poll, CONFIG.WAIT_POLL_MS);
      })();
    });
  }

  function findCommentBox() {
    for (const sel of CONFIG.COMMENT_SELECTORS) {
      const nodes = document.querySelectorAll(sel);
      for (const el of nodes) {
        if (isVisible(el)) return el;
      }
    }
    return null;
  }

  function isVisible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== "hidden" && st.display !== "none";
  }

  // React가 관리하는 필드에 값을 한 번에 주입(붙여넣기 동일). textarea/input과 contenteditable 모두 대응.
  function fillAtOnce(el, text) {
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      setter.call(el, text);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      // contenteditable: 기존 내용 비우고 insertText — React onInput 트리거
      el.focus();
      const sel = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(el);
      sel.removeAllRanges();
      sel.addRange(range);
      document.execCommand("insertText", false, text);
    }
  }

  // 옵션: 한 글자씩 사람처럼(건별 페르소나 μ + 키별 지터 + 문장내 드리프트)
  async function typeHumanlike(el, text) {
    let mu = rand(55, 160); // 건별 기준속도
    const pauseP = rand(0.04, 0.08); // 생각멈칫 확률
    for (const ch of text) {
      appendChar(el, ch);
      mu = clamp(mu + rand(-15, 15), 40, 200); // 문장 내 드리프트
      let delay = clamp(mu * rand(0.6, 1.4), 20, 400); // 키별 지터
      if (ch === " ") delay += rand(20, 120); // 단어경계
      if (Math.random() < pauseP) delay += rand(300, 900); // 생각멈칫
      await sleep(delay);
    }
  }

  function appendChar(el, ch) {
    if (el.tagName === "TEXTAREA" || el.tagName === "INPUT") {
      const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      setter.call(el, el.value + ch);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      document.execCommand("insertText", false, ch);
    }
  }

  /* ------------------------------- utils ------------------------------- */
  function rand(a, b) { return a + Math.random() * (b - a); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

  function toast(msg, color) {
    const d = document.createElement("div");
    d.textContent = msg;
    d.style.cssText =
      "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:2147483647;" +
      "background:" + (color || "#1e7e34") + ";color:#fff;padding:12px 18px;border-radius:10px;" +
      "font:600 14px/1.4 'Malgun Gothic',system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.35);max-width:80vw";
    document.body.appendChild(d);
    setTimeout(() => { d.style.transition = "opacity .4s"; d.style.opacity = "0"; }, 3600);
    setTimeout(() => d.remove(), 4200);
  }
})();
