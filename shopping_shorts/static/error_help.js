/* 에러 설명 정본 (2026-09-05 신설) — "고객이 에러를 만나는 그 화면에서 뭐가 잘못된 건지 알려준다"
 *
 * 왜 한 파일인가: 같은 설명을 화면 여러 곳에 각각 적으면 반드시 어긋난다(CLAUDE.md 0순위-B).
 * 문구를 고칠 곳은 **여기 한 곳**이고, 화면은 부르기만 한다.
 *
 * 항목은 지어내지 않았다 — 전부 실제 고객·사장님 제보에서 왔고, 각 항목의 src에
 * 그 제보 기록(wiki/log.d, handoff)을 적어 뒀다. 새 제보가 오면 여기에 한 줄 추가한다.
 *
 * 각 항목 3칸 (60대 고객 기준: 원인 → 지금 할 일 순서로 읽히게):
 *   title : 무엇이 막혔는지 한 줄 (원문 에러를 그대로 던지지 않는다)
 *   why   : 왜 이런 일이 생기는지 (고객 말로)
 *   todo  : 지금 당장 뭘 하면 되는지 (기다리면 되는지 / 안 되는지를 반드시 가른다)
 */
(function (g) {
  'use strict';

  var E = {
    /* ── 통신·서버 ─────────────────────────────────────────────── */
    network: {
      title: '인터넷 연결이 잠깐 끊겼어요',
      why: '화면이 서버에 말을 걸었는데 답이 오지 않았습니다. 작업 내용은 서버에 그대로 있어요.',
      todo: '와이파이를 확인하고 새로고침(F5) 해 주세요. 새로고침해도 그대로면 오류 신고를 눌러 주세요.'
    },
    server_500: {
      title: '서버가 이 요청을 처리하다 멈췄어요',
      why: '고객님 잘못이 아닙니다. 서버 쪽 문제라 같은 버튼을 다시 눌러도 대개 똑같습니다.',
      todo: '오류 신고를 눌러 주세요 — 어느 화면에서 났는지 자동으로 저장됩니다. 기다린다고 풀리지 않습니다.',
      src: 'log.d/대본UI2단계 08-17 "네트워크 오류=실은 서버 500(NameError)"'
    },
    login_expired: {
      title: '로그인이 풀렸어요',
      why: '오래 켜 두면 보안을 위해 자동으로 로그아웃됩니다.',
      todo: '다시 로그인해 주세요. 작업물은 사라지지 않습니다.'
    },
    not_approved: {
      title: '아직 사용 승인 전이에요',
      why: '가입은 됐지만 관리자 승인이 나야 제작 기능이 열립니다.',
      todo: '승인되면 알려드립니다. 급하시면 문의를 남겨 주세요.'
    },

    /* ── 대본 생성(AI) ─────────────────────────────────────────── */
    gen_no_keys: {
      title: 'AI를 부를 수 있는 자리가 지금 하나도 없어요',
      why: '오늘 쓸 수 있는 AI 사용량을 다 썼거나, AI 열쇠가 잠겼습니다.',
      todo: '조금 기다리면 자동으로 풀립니다(하루 한도는 한국시간 오후 4~5시경 초기화). 급하면 문의해 주세요.'
    },
    gen_exhausted: {
      title: '오늘 AI 사용량을 다 썼어요',
      why: 'AI는 하루에 쓸 수 있는 양이 정해져 있습니다.',
      todo: '잠시 후 다시 눌러 주세요. 계속 같으면 문의해 주세요.'
    },
    gen_rate_limit: {
      title: '지금 한꺼번에 몰렸어요',
      why: '짧은 시간에 요청이 많이 몰리면 AI가 잠깐 받아주지 않습니다. 고장이 아닙니다.',
      todo: '1~2분만 기다렸다가 다시 눌러 주세요.'
    },
    gen_api_error: {
      title: 'AI가 이상한 답을 보냈어요',
      why: '사용량 문제가 아닙니다. 기다린다고 풀리지 않으니 계속 기다리지 마세요.',
      todo: '다시 한 번 눌러 보시고, 두 번 이상 같으면 오류 신고를 눌러 주세요.',
      src: 'log.d 08-22 "429가 없는데 키 소진이라 떠서 계속 기다리게 만든 사고"'
    },
    gen_empty: {
      title: 'AI가 조건에 맞는 문장을 못 만들었어요',
      why: '담긴 영상(재료)이 적거나, 고른 스타일이 이 상품과 안 맞으면 생깁니다.',
      todo: '영상을 2~3개 더 담거나 다른 스타일을 골라 다시 만들어 주세요.'
    },
    gen_style_mismatch: {
      title: '고른 스타일로는 만들 대본이 없어요',
      why: '고른 스타일이 이 카테고리에 맞지 않아 서버가 전부 걸러냈습니다.',
      todo: '스타일을 다른 것으로 바꿔서 다시 만들어 주세요.',
      src: 'log.d/대본UI2단계 08-17 "2개 골랐는데 1안만 나옴"'
    },

    /* ── 영상 담기·분석(1단계) ─────────────────────────────────── */
    src_login_required: {
      title: '그 사이트가 로그인을 요구해서 영상을 못 받았어요',
      why: '인스타·틱톡 등은 비로그인 접근을 막을 때가 있습니다. 영상 자체는 멀쩡합니다.',
      todo: '다른 영상으로 담아 주세요. 같은 사이트가 계속 막히면 알려 주세요 — 서버 쪽에서 풀어야 합니다.'
    },
    src_private: {
      title: '원본이 비공개이거나 삭제됐어요',
      why: '올린 분이 영상을 내렸거나 비공개로 바꿨습니다.',
      todo: '그 영상은 쓸 수 없습니다. 다른 영상을 담아 주세요.'
    },
    src_download: {
      title: '영상을 내려받지 못했어요',
      why: '원본 사이트가 잠시 응답하지 않거나 형식이 특이한 경우입니다.',
      todo: '자동으로 몇 번 더 시도합니다. 3번 넘게 실패하면 다른 영상으로 바꿔 주세요.'
    },
    src_timeout: {
      title: '시간이 너무 걸려 중단했어요',
      why: '긴 영상이거나 원본 사이트가 느릴 때 생깁니다.',
      todo: '다시 담아 보시고, 계속 같으면 더 짧은 영상으로 바꿔 주세요.'
    },
    src_ai_busy: {
      title: 'AI 분석 서버가 답을 안 줬어요',
      why: '영상 문제가 아니라 분석 서버가 붐빈 것입니다.',
      todo: '자동으로 다시 시도합니다. 그대로 두셔도 됩니다.',
      src: 'log.d 08-27 "영상 탓처럼 읽히던 문구"'
    },
    yt_blocked: {
      title: '유튜브가 서버 접속을 막았어요',
      why: '고객님 인터넷 문제가 아니라, 우리 서버 주소를 유튜브가 차단한 것입니다.',
      todo: '유튜브 대신 인스타·틱톡·샤오홍슈 영상을 담아 주세요. 서버 쪽에서 조치 중입니다.',
      src: 'memory reference_youtube_shorts_datacenter_block / log.d/유튜브추출장애 08-30'
    },

    /* ── 미리보기 ─────────────────────────────────────────────── */
    preview_black: {
      title: '미리보기가 검게 보여요',
      why: '영상 파일은 정상인데 브라우저가 첫 그림을 아직 못 그린 상태입니다.',
      todo: '▶를 한 번 눌러 보세요. 그래도 검으면 새로고침(F5) 해 주세요 — 결과물에는 영향이 없습니다.',
      src: 'log.d/미리보기검정 09-01'
    },
    preview_frozen: {
      title: '영상인데 사진처럼 멈춰 보여요',
      why: '컷을 넘길 때 쓰는 정지 그림이 지워지지 않고 남은 경우입니다. 실제 영상은 정상입니다.',
      todo: '다음 컷으로 넘겼다가 돌아오거나 새로고침해 주세요. 최종 결과물은 멀쩡합니다.',
      src: 'log.d/미리보기정지 09-02 고객 제보'
    },
    preview_stale: {
      title: '방금 고친 게 미리보기에 아직 안 보여요',
      why: '미리보기는 새로 만드는 데 몇 초 걸립니다. 옛 화면이 잠깐 남습니다.',
      todo: '5~10초 뒤 다시 보시거나 새로고침해 주세요.'
    },

    /* ── 제작·렌더 ────────────────────────────────────────────── */
    render_fail: {
      title: '영상 만들기가 중간에 실패했어요',
      why: '만드는 도중에 멈췄습니다. 만들던 내용은 그대로 남아 있습니다.',
      todo: '다시 만들기를 눌러 주세요. 두 번 이상 실패하면 오류 신고를 눌러 주세요.'
    },
    tts_silent: {
      title: '목소리가 안 입혀졌어요(무음)',
      why: '음성 만드는 서버가 응답하지 않아 소리 없는 구간이 생겼습니다.',
      todo: '그 칸의 목소리 다시 만들기를 눌러 주세요. 계속 무음이면 다른 목소리로 바꿔 보세요.',
      src: 'handoff/API관측판 — silent_fallback 관측'
    },
    caption_remove_fail: {
      title: '원본 자막 지우기가 안 됐어요',
      why: '자막 위치를 못 찾았거나 지우기 서버가 붐빈 경우입니다.',
      todo: '자막 지울 구간을 직접 지정해서 다시 시도해 주세요.',
      src: 'log.d/자막제거문구 08-26 "오늘도 자막제거 실패"'
    },
    capcut_bat: {
      title: '캡컷 자동설정 파일에서 한글이 깨져요',
      why: '내려받은 파일이 옛 버전이면 생깁니다. 지금은 고쳐져 있습니다.',
      todo: '자동설정 파일을 다시 내려받아 실행해 주세요.',
      src: 'log.d/내보내기캡컷 09-03'
    },
    save_fail: {
      title: '편집 내용이 저장되지 않았어요',
      why: '저장 중 통신이 끊기면 생깁니다. 방금 만진 내용이 서버에 안 갔을 수 있습니다.',
      todo: '새로고침하지 마시고, 잠시 뒤 저장을 다시 눌러 주세요.'
    }
  };

  /* 서버가 보낸 원문·사유를 항목으로 잇는다.
     ★서버가 코드를 주면 그걸 쓰고, 옛 문구만 오면 여기서 알아본다(옛 화면도 설명이 뜨게). */
  function pick(codeOrText, status) {
    var t = String(codeOrText == null ? '' : codeOrText);
    if (E[t]) return E[t];
    if (status === 500 || status === 502 || status === 503) return E.server_500;
    if (status === 401) return E.login_expired;
    if (status === 403) return E.not_approved;
    var s = t.toLowerCase();
    if (/키 소진|소진됐|exhausted/.test(t)) return E.gen_exhausted;
    if (/분당|rate limit|429/.test(s)) return E.gen_rate_limit;
    if (/네트워크|failed to fetch|networkerror/.test(s)) return E.network;
    if (/렌더 실패|만들기 실패/.test(t)) return E.render_fail;
    if (/로그인/.test(t)) return E.src_login_required;
    if (/비공개|삭제/.test(t)) return E.src_private;
    if (/내려받|다운로드/.test(t)) return E.src_download;
    if (/시간이 초과|timeout/.test(s)) return E.src_timeout;
    if (/AI 분석 서버|AI 서버/.test(t)) return E.src_ai_busy;
    return null;
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* 화면에 붙일 HTML 한 덩이. 설명이 없으면 원문만 돌려준다(숨기지 않는다). */
  function html(codeOrText, status) {
    var e = pick(codeOrText, status);
    var raw = String(codeOrText == null ? '' : codeOrText);
    if (!e) return '<div class="errHelp"><b>' + esc(raw || '알 수 없는 오류') + '</b></div>';
    return '<div class="errHelp">'
      + '<b>' + esc(e.title) + '</b>'
      + '<div class="errWhy">' + esc(e.why) + '</div>'
      + '<div class="errTodo">👉 ' + esc(e.todo) + '</div>'
      + '</div>';
  }

  function text(codeOrText, status) {
    var e = pick(codeOrText, status);
    return e ? (e.title + ' — ' + e.todo) : String(codeOrText || '');
  }

  g.ErrorHelp = { map: E, pick: pick, html: html, text: text };
})(window);
