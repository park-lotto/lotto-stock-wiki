// ==UserScript==
// @name         로또 소통 · 인스타 댓글 자동채우기
// @namespace    lotto.shopping_shorts
// @version      1.3.1
// @description  소통큐에서 넘어온 댓글을 인스타 게시물 댓글칸에 자동으로 채운다. 전송·팔로우는 사용자가 직접(안전).
// @match        https://www.instagram.com/*
// @run-at       document-start
// @grant        none
// @downloadURL  https://shoppingshorts.duckdns.org/insta_fill_comment.user.js
// @updateURL    https://shoppingshorts.duckdns.org/insta_fill_comment.user.js
// ==/UserScript==
// ⚠️ @grant는 반드시 none 유지! GM_* 를 넣으면 Tampermonkey가 샌드박스 컨텍스트로
//    전환돼 페이지 React에 값 주입(댓글 채우기)이 깨진다. 서버 완료기록은 no-cors fetch로 처리.
(function () {
  "use strict";

  /* ===================== CONFIG (인스타 DOM 바뀌면 여기만 수선) ===================== */
  const CONFIG = {
    DEBUG: true, // 진단 모드: 각 단계를 화면 토스트로 보여줌. 정상화되면 false로.
    // 댓글 입력창 후보 셀렉터 — 위에서부터 먼저 잡히는 것 사용
    COMMENT_SELECTORS: [
      'textarea[aria-label*="댓글"]',
      'textarea[aria-label*="comment" i]',
      'textarea[placeholder*="댓글"]',
      'textarea[placeholder*="comment" i]',
      'form[method="POST"] textarea',
      'form textarea',
      'div[contenteditable="true"][role="textbox"][aria-label*="댓글"]',
      'div[contenteditable="true"][role="textbox"][aria-label*="comment" i]',
      'div[contenteditable="true"][role="textbox"]',
      "textarea", // 최후: 페이지에 보이는 아무 textarea
    ],
    WAIT_TIMEOUT_MS: 20000, // 댓글창 대기 최대
    WAIT_POLL_MS: 300,
    HUMANLIKE_TYPING: false, // true면 한 글자씩 랜덤 딜레이 타이핑(기본 off — 붙여넣기와 동일)
  };
  /* ================================================================================ */

  // ⚠️ document-start에서 해시를 "즉시" 붙잡는다 — 인스타 SPA가 나중에 URL을 정리하며
  //    #lotto_fill 을 날려버려도, 이 시점에 이미 확보해 두면 안전하다(경계 B 방어).
  const RAW_HASH = location.hash || "";
  const PATHNAME = location.pathname;

  log("loaded · path=" + PATHNAME + " · hash길이=" + RAW_HASH.length);

  const IS_POST = /^\/(p|reel|reels)\/[^/]+/.test(PATHNAME);
  const payload = readPayload(RAW_HASH);

  if (!payload || !payload.c) {
    // 신호 없음 → 평소 인스타 사용. (설치 확인용으로 DEBUG일 때만 알림)
    dbg(RAW_HASH.indexOf("lotto_fill") >= 0
      ? "⚠️ 해시는 있는데 파싱 실패 — 인코딩 확인 필요"
      : "신호(해시) 없음 → 대기(스크립트는 정상 설치·동작 중)");
    return;
  }
  dbg("✅ 페이로드 수신 — 댓글: " + preview(payload.c));

  if (!IS_POST) {
    dbg("⚠️ 게시물/릴스 URL 아님(" + PATHNAME + ") → 종료");
    return;
  }

  // 중복 발사 가드: 세션 플래그 + 해시 소거
  const guardKey = "lottoFilled:" + (payload.sc || PATHNAME);
  try {
    if (sessionStorage.getItem(guardKey)) { dbg("이미 채운 건 → 스킵"); return; }
    sessionStorage.setItem(guardKey, "1");
  } catch (_) {}
  try { history.replaceState(null, "", PATHNAME + location.search); } catch (_) {}

  // DOM 준비되면 실행 (document-start라 아직 body 없을 수 있음 → 폴링이 알아서 대기)
  run(payload.c).catch((e) => toast("❌ 자동채우기 실패: " + e.message, "#c0392b"));

  /* ------------------------------------------------------------------ */

  function readPayload(hash) {
    const m = /(?:^|#)lotto_fill=([^&]+)/.exec(hash);
    if (!m) return null;
    try {
      const json = decodeURIComponent(escape(atob(decodeURIComponent(m[1]))));
      return JSON.parse(json);
    } catch (e) {
      log("payload 파싱 오류: " + e.message);
      return null;
    }
  }

  async function run(text) {
    const box = await waitForCommentBox();
    if (!box) {
      toast("⚠️ 댓글창을 못 찾음 — 직접 붙여넣기(Ctrl+V) 하세요", "#b9770e");
      log("댓글창 탐색 실패. 시도한 셀렉터: " + CONFIG.COMMENT_SELECTORS.join(" | "));
      return;
    }
    dbg("댓글창 발견: <" + box.tagName.toLowerCase() +
        (box.getAttribute("aria-label") ? ' aria-label="' + box.getAttribute("aria-label") + '"' : "") + ">");
    box.focus();
    // 일부 레이아웃은 클릭해야 입력창이 활성화됨
    try { box.click(); } catch (_) {}
    if (CONFIG.HUMANLIKE_TYPING) {
      await typeHumanlike(box, text);
    } else {
      fillAtOnce(box, text);
    }
    // 검증: 실제로 값이 들어갔나
    const ok = (getVal(box) || "").indexOf(text.slice(0, 4)) >= 0;
    toast(ok ? "✅ 댓글 채워둠 — 전송하면 소통큐에서 자동 완료 (팔로우는 직접)"
             : "⚠️ 채우기 반영 안 됨 — 직접 붙여넣기(Ctrl+V) 하세요",
          ok ? "#1e7e34" : "#b9770e");
    if (ok) armDoneDetector(box);
  }

  function getVal(el) {
    return (el.tagName === "TEXTAREA" || el.tagName === "INPUT") ? el.value : el.textContent;
  }

  // 사용자가 "게시(전송)"를 누른 걸 감지 → 소통큐(window.opener)에 완료 신호를 보낸다.
  // 실제 전송 행위(Enter 또는 게시 버튼 클릭)만 잡아 오탐을 줄인다.
  function armDoneDetector(box) {
    let fired = false;
    const fire = () => {
      if (fired) return; fired = true;
      dbg("✅ 전송 감지 → 완료처리 시도");
      // (a) opener(소통큐) 살아있으면 즉시 알림 (COOP로 끊겼을 수 있으니 보너스)
      try {
        if (window.opener && !window.opener.closed)
          window.opener.postMessage({ type: "lotto_done", sc: payload.sc }, payload.o || "*");
      } catch (_) {}
      // (b) 서버에 직접 완료기록 — opener가 끊겨도 확실. 소통큐는 탭 복귀 시 반영.
      //     no-cors POST(단순요청이라 프리플라이트 없음). /api/comment/done은 무인증 허용목록.
      const base = payload.o || "https://shoppingshorts.duckdns.org";
      try {
        fetch(base + "/api/comment/done?shortcode=" + encodeURIComponent(payload.sc),
              { method: "POST", mode: "no-cors", keepalive: true });
        dbg("✅ 서버 완료기록 요청 전송 — 소통큐 복귀 시 감춰짐");
      } catch (e) { dbg("⚠️ 완료기록 예외: " + e.message); }
    };
    // 1) Enter 키로 전송
    box.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) setTimeout(fire, 900);
    });
    // 2) 게시/Post 버튼 클릭
    document.addEventListener("click", (e) => {
      const t = e.target && e.target.closest && e.target.closest('div[role="button"],button,[type="submit"]');
      if (!t) return;
      if (/^(게시|게시하기|Post)$/i.test((t.textContent || "").trim())) setTimeout(fire, 900);
    }, true);
    // 3) 폴백(가장 확실): 채웠던 댓글칸이 비워지면 = 전송된 것. Enter·버튼 못 잡아도 커버.
    let ticks = 0;
    const iv = setInterval(() => {
      if (fired || ticks++ > 600) { clearInterval(iv); return; } // 최대 ~5분 감시
      const cur = findCommentBox();
      if (cur && !(getVal(cur) || "").trim()) { clearInterval(iv); setTimeout(fire, 300); }
    }, 500);
  }

  function waitForCommentBox() {
    return new Promise((resolve) => {
      const deadline = Date.now() + CONFIG.WAIT_TIMEOUT_MS;
      (function poll() {
        const el = document.body ? findCommentBox() : null;
        if (el) return resolve(el);
        if (Date.now() > deadline) return resolve(null);
        setTimeout(poll, CONFIG.WAIT_POLL_MS);
      })();
    });
  }

  function findCommentBox() {
    for (const sel of CONFIG.COMMENT_SELECTORS) {
      for (const el of document.querySelectorAll(sel)) {
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
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      el.focus();
      const sel = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(el);
      sel.removeAllRanges();
      sel.addRange(range);
      document.execCommand("insertText", false, text);
    }
  }

  async function typeHumanlike(el, text) {
    let mu = rand(55, 160);
    const pauseP = rand(0.04, 0.08);
    for (const ch of text) {
      appendChar(el, ch);
      mu = clamp(mu + rand(-15, 15), 40, 200);
      let delay = clamp(mu * rand(0.6, 1.4), 20, 400);
      if (ch === " ") delay += rand(20, 120);
      if (Math.random() < pauseP) delay += rand(300, 900);
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
  function preview(s) { s = String(s); return s.length > 24 ? s.slice(0, 24) + "…" : s; }
  function log(msg) { try { console.log("[로또소통] " + msg); } catch (_) {} }
  function dbg(msg) { log(msg); if (CONFIG.DEBUG) toast("🔧 " + msg, "#334155"); }

  function toast(msg, color) {
    const show = () => {
      const d = document.createElement("div");
      d.textContent = msg;
      d.style.cssText =
        "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:2147483647;" +
        "background:" + (color || "#1e7e34") + ";color:#fff;padding:12px 18px;border-radius:10px;" +
        "font:600 14px/1.4 'Malgun Gothic',system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.35);max-width:80vw";
      document.body.appendChild(d);
      setTimeout(() => { d.style.transition = "opacity .4s"; d.style.opacity = "0"; }, 4200);
      setTimeout(() => d.remove(), 4800);
    };
    if (document.body) show();
    else document.addEventListener("DOMContentLoaded", show, { once: true });
  }
})();
