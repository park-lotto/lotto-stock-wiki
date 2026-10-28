#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""긴 소재를 **통째로 보고** 「몇 편이 나오는가」를 제안한다.

■ 왜 (2026-08-16 사장님 질문)
  「이렇게 긴 영상은 하이라이트로 쓸 만한 것들이 많잖아? 구간이 기니까?
   네가 사용자에게 이 영상에서 몇 편을 뽑을 수 있다고 제안하는 게 가장 좋을 것 같은데?」

  맞다. 51분짜리 회차에서 우리는 지금 **구간을 손으로 찍어** 주고 있었다
  (`--from 3400 --to 4300`). 그 손이 곧 「어디가 좋은지 사람이 안다」는 전제다.
  그런데 어디가 좋은지야말로 **눈이 봐야 아는 것**이다.

■ 어떻게
  ① 구간별 실제 영상·음성을 보존해 현재 클라이언트에 전달한다.
     같은 원본·구간·질문의 완료 답은 영수증에서 읽고, 미완료 자료만 인계한다.
     명시 유료 정책에만 기존 요청 원장으로 한 번의 HTTP 요청을 허용한다.
  ② 「한 편으로 설 이야기」의 후보 구간을 받는다. 각 구간마다
     시작·끝 · 무슨 이야기인지 · 왜 한 편이 되는지 · 세기(1~5).
  ③ **코드가 감사한다** — 겹치지 않는가 · 소재 안인가 · 그 자리에 말이 있는가 ·
     정본 편 길이를 채울 만큼 긴가. 통과한 것만 제안한다.

■ 이 파일이 하지 않는 것
  편을 만들지 않는다. **어디를 만들지 고르는 일**만 한다. 만드는 것은 `make_auto` 다.
  제안은 사장님이 고르시라고 내놓는 것이지 저절로 돌지 않는다.

    사용: python3 _engine/survey.py <소재.mp4> [--ch 린박스] [--sm <색인.json>]
                                    [--from 3400 --to 4300]

■ 긴 소재는 **나눠 훑는다** (2026-08-17)
  한 번에 담을 수 없는 긴 원본은 겹치는 구간으로 나눠 전체를 훑는다.
  API 키의 존재로 제공자·창 크기를 바꾸거나 Google Files API로 전환하지 않는다.
  구간마다 한 번만 분석하며, 이전 구간의 완료·실패·대기 기록을 유지한다.
  눈이 답한 시각은 사본의 0초 기준이므로 코드가 절대초로 되돌린다.
"""
import json
import math
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vision as V   # noqa: E402

TEMPS = (0.2,)
AUD_KBPS, MIN_V_KBPS = 24.0, 20.0
MIN_GAP = 5.0        # 후보끼리 이만큼은 떨어져야 다른 이야기로 본다
# ★소재 구간 ÷ 편 길이 — 정답지 린박스 실측 (3440~3644 = 203초 → 편 56초)
#   소재에서 실제로 쓰는 것은 말이 있는 자리뿐이고 침묵·연결샷은 버린다.
SRC_RATIO = 3.7

PROMPT = (
    "너는 이 채널의 편집자다. **긴 영상 한 편**을 통째로 보여준다.\n"
    "여기서 **숏폼 한 편으로 설 대목**을 골라라.\n\n"
    "{guide}\n\n"
    "[고르는 기준]\n"
    "· 한 대목은 그 자체로 **처음-중간-끝**이 있어야 한다. 잘라 놓고 보면\n"
    "  무슨 일인지 알 수 있어야 한다.\n"
    "· ★한 대목은 **{want:.0f}초 안팎**으로 잡아라. 완성될 숏폼은 그보다 짧다 —\n"
    "  말이 있는 자리만 쓰고 침묵·연결샷은 버리기 때문이다(정답지 실측 3.7배).\n"
    "  짧게 잡으면 편이 안 채워져 그 대목은 통째로 버려진다.\n"
    "· 대목끼리 겹치지 마라. 같은 사건을 두 번 내지 마라.\n"
    "· 이 영상은 {mins:.0f}분이다 — 대목 {want:.0f}초씩이면 **{n_hint}개쯤** 나올 만하다.\n"
    "  그 언저리를 목표로 **끝까지 훑어라.** 앞부분만 보고 하나 찾고 멈추지 마라 —\n"
    "  영상 중반·후반에도 한 편이 될 대목이 있다.\n"
    "· 그렇다고 억지로 개수를 채우지는 마라 — 약한 것을 넣느니 적게 내는 게 낫다.\n\n"
    "[각 대목마다 적을 것]\n"
    "    t0, t1  이 영상 시작을 0초로 한 **초 단위**\n"
    "    what    무슨 이야기인가 (한 문장)\n"
    "    why     왜 한 편이 되는가 (한 문장)\n"
    "    power   얼마나 센가 1~5 (5가 가장 셈)\n\n"
    '출력은 JSON 만: {{"picks":[{{"t0":120.0,"t1":210.0,"what":"…","why":"…","power":4}}]}}'
)


def _dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float((r.stdout or "0").strip() or 0)


def _enc_argv(enc, which, ss, t, src, out, vb, fps, ab):
    """훑기 사본을 굽는 argv. **서버가 준 꼴**에 잰 값을 끼운다.

    ★실행기는 ffmpeg 명령을 **스스로 짓지 않는다** — 이 저장소의 불변식이고
      검사 [`실행기가 ffmpeg 명령을 짓지 않는다`] 가 매번 잰다. 화질을 정하는
      숫자(폭·fps·비트레이트 배수)는 명세에서 와야 한다. 여기서 지으면 서버가
      값을 바꿔도 배급본이 안 따라온다(2026-08-18 에 내가 그렇게 어겼다).
    ★끼우는 값은 **실행기가 잰 것**이다(소재 길이·실제 크기) — 서버는 그것을 모른다.
      「무엇을 굽나」는 서버, 「지금 이 파일이 얼마나 크냐」는 실행기. 자리가 다르다.
    """
    tpl = (enc or {}).get(which) or (enc or {}).get("primary")
    if not tpl:
        # ★**뼈대조차 여기 두지 않는다.** 못 받았으면 굽지 않고 **말한다** —
        #   실행기가 명령을 지으면 서버가 값을 바꿔도 배급본이 안 따라온다.
        raise RuntimeError(
            "[훑기] 서버가 사본 굽는 명령(`enc`)을 주지 않았다. 실행기는 ffmpeg "
            "명령을 스스로 짓지 않는다 — 서버·실행기 판이 어긋났다. "
            "`assets` 단계를 다시 지나 실행기를 새로 받아라.")
    sub = {"ss": f"{ss:.3f}", "t": f"{t:.3f}", "src": src, "out": out,
           "w": str(int((enc or {}).get("width") or 320)),
           "fps": str(int(fps)), "vb": f"{vb:.0f}",
           "vmax": f"{vb * float((enc or {}).get('max_mult') or 1.5):.0f}",
           "vbuf": f"{vb * float((enc or {}).get('buf_mult') or 4):.0f}",
           "ab": f"{ab:.0f}"}
    return [str(x).format(**sub) for x in tpl]


class _SourceDigest:
    """한 invocation의 실제 원본 해시. 디스크 메타데이터 캐시로 대체하지 않는다."""
    def __init__(self, src):
        from contextlib import ExitStack
        from volcano_run import _FileBody
        self.guards = ExitStack()
        try:
            self.body = self.guards.enter_context(_FileBody(src))
            with open(src, "rb") as source:
                self.changed_ns = os.fstat(source.fileno()).st_ctime_ns
            self.sha256 = V._media_digest(self.body).hex()
            self.check()
        except BaseException:
            self.guards.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self.guards.__exit__(*exc)

    def check(self):
        # 구간마다 실제 경로를 다시 열어 교체/삭제/접근 실패도 감지한다.
        with open(self.body.path, "rb") as source:
            st = os.fstat(source.fileno())
            if (self.body._stamp(st) != self.body.stat or st.st_ctime_ns != self.changed_ns):
                raise OSError("[훑기] 원본 파일이 해시 확인 뒤 바뀌었습니다")


def _proxy(src, work, log=print, t0=None, t1=None, enc=None, _source=None):
    """훑기용 **가벼운 사본**. 원본 1.4GB 를 그대로 보내지 않는다.

    ★`t0`/`t1` 을 주면 그 구간만 훑는다 (2026-08-17 실측으로 넣었다)
      124.2분 소재는 어떤 비트레이트로도 18MB 인라인에 안 들어간다(어림 42MB).
      그러면 Files API 로 가고, 그 길은 **구글 순정 키 전용**이라 쿼터에 걸린다 —
      실제로 세 온도 전부 `429 Too Many Requests` 로 떨어졌다.
      두 시간짜리 영화를 한 번에 보여줄 방법이 없으면 **나눠 보여주면 된다.**
      사람이 하는 일도 그렇다. 구간을 주면 그 안에서 대목을 고른다.

    ★크기를 **목표에 맞춰 정한다** (2026-08-16 실측으로 고쳤다)
      처음엔 `crf 34` 로 만들었더니 51.6분이 **25.9MB** 가 나왔다. 그러면
      인라인 상한(18MB)을 넘어 Files API 업로드 경로로 가고, 그 길은 **구글 순정
      키 전용**이라 순정 키 쿼터(429)에 걸리면 훑기 자체가 못 돈다.
      품질을 먼저 정하고 크기가 따라오게 두면 이렇게 된다. 순서를 뒤집는다 —
      **크기를 먼저 정하고** 비트레이트를 거기서 역산한다.
      그러면 Evolink 인라인으로 들어가 순정 키가 아예 필요 없다.
    ★훑기는 「무슨 장면인가」만 알면 된다. 대사 문구·편집점은 뒤 단계(`editplan`)가
      **구간을 잘라 다시** 본다. 여기서 화질을 아낄 수 있는 이유가 그것이다.
    """
    if _source is None:
        with _SourceDigest(src) as source:
            return _proxy(src, work, log=log, t0=t0, t1=t1, enc=enc, _source=source)
    os.makedirs(work, exist_ok=True)
    full = max(1.0, _dur(src))
    a = 0.0 if t0 is None else max(0.0, float(t0))
    z = full if t1 is None else min(full, float(t1))
    dur = max(1.0, z - a)
    from volcano_run import _FileBody, _asr_save, TranscriptionPending
    _source.check()
    source_sha = _source.sha256
    recipe = hashlib.sha256(json.dumps(
        {"version": 1, "from": a, "to": z, "enc": enc, "inline_bytes": V.INLINE_MAX,
         "audio_kbps": AUD_KBPS, "min_video_kbps": MIN_V_KBPS},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    _sid = hashlib.sha256((source_sha + recipe).encode()).hexdigest()[:20]
    out = os.path.join(
        work,
        f"_survey_proxy_{_sid}.mp4" if (t0 is None and t1 is None)
        else f"_survey_proxy_{_sid}_{int(a)}_{int(z)}.mp4")
    # ★목표의 **75%** 를 노린다 (2026-08-16 실측)
    #   90% 로 잡았더니 18.35MB 가 나와 상한(18.0MB)을 **간발로** 넘었다.
    #   x264 는 목표 비트레이트를 정확히 맞추지 않는다(장면에 따라 넘친다).
    #   상한에 붙여 놓으면 소재가 바뀔 때마다 이 실패가 되풀이된다 — 여유를 둔다.
    #   그리고 만든 뒤 **실제로 재서**, 넘으면 한 번 더 줄인다(짐작하지 않는다).
    # ★소리를 예산에 안 넣고 있었다 (2026-08-17 실측으로 고쳤다)
    #   `vb = max(20.0, budget - 32.0)` 였다. 두 군데가 틀렸다:
    #     ① 소리 32kbps 를 **빼기만 하고 총합에 다시 안 더했다** — 실제로 나가는
    #        것은 vb + 32 다.
    #     ② `max(20.0, …)` 바닥이 예산을 **조용히 이긴다.** 124.2분 소재에서
    #        예산은 19.8kbps 인데 바닥 20 이 이겨 vb=20 이 되고, 거기에 소리 32 가
    #        붙어 52kbps → **48MB**. 상한 18MB 의 2.7배다(실측 40MB 시점에 잡았다).
    #   「크기를 먼저 정하고 비트레이트를 역산한다」는 이 함수의 규칙인데,
    #   바닥이 그 규칙을 무효로 만들고 있었다. **바닥이 이기면 크기를 못 지킨다고
    #   말해야 한다** — 지킨 척하면 부르는 쪽이 429 를 맞고서야 안다.
    budget_kbps = V.INLINE_MAX * 8 / 1024 / dur * 0.75
    vb = max(MIN_V_KBPS, budget_kbps - AUD_KBPS)
    # ★「담을 수 있나」는 **어림 크기**로 판정한다 — 비트레이트 바닥으로 판정하면
    #   실제로는 들어가는 소재까지 못 담는다고 말한다(51.6분 = 어림 17.4MB 는 들어간다).
    proj = (vb + AUD_KBPS) * 1024 * dur / 8
    over = proj > V.INLINE_MAX
    receipt = out + ".verified.json"
    try:
        with open(receipt, encoding="utf-8") as saved:
            verified = json.load(saved)
        with _FileBody(out) as output:
            reusable = (isinstance(verified, dict) and verified.get("source_sha256") == source_sha
                        and verified.get("recipe") == recipe and os.path.getsize(out) > 0
                        and verified.get("output_sha256") == V._media_digest(output).hex())
    except (OSError, ValueError):
        reusable = False
    if reusable:
        _source.check()
        return out
    log(f"  [훑기] 가벼운 사본을 만든다 — {dur / 60:.1f}분 "
        f"(영상 {vb:.0f} + 소리 {AUD_KBPS:.0f}kbps → 어림 {proj / 1e6:.1f}MB)")
    if over:
        log(f"  ★[훑기] {dur / 60:.1f}분은 {V.INLINE_MAX / 1e6:.0f}MB 인라인에 못 담는다 "
            f"(예산 {budget_kbps:.1f}kbps < 알아볼 수 있는 최소 "
            f"{MIN_V_KBPS + AUD_KBPS:.0f}kbps).\n"
            f"     알아볼 수 있는 최소로 만들고 분석 전에 구간을 나눕니다. "
            f"추가 제공자로 전환하지 않습니다.")
    # 긴 소재에서는 **초당 장수를 줄여** 같은 비트레이트로 한 장을 더 또렷하게 만든다.
    # 훑기가 알아야 할 것은 「무슨 장면인가」이지 움직임이 아니다.
    _fps = 8 if dur <= 1800 else (5 if dur <= 3600 else 3)
    r = subprocess.run(_enc_argv(enc, "primary", a, dur, src, out, vb, _fps, AUD_KBPS),
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        from volcano_run import err_gist
        raise RuntimeError(f"[훑기] 사본을 못 만들었다: {err_gist(r.stderr, 400)}")
    n = os.path.getsize(out)
    # ★넘었으면 **한 번 더 줄인다** — 짐작이 아니라 잰 값으로 다시 정한다.
    #   단 애초에 담을 수 없다고 말한 경우(`over`)에는 다시 굽지 않는다 —
    #   같은 벽에 두 번 부딪히는 것이고, 어차피 올려서 가리킬 파일이다.
    if n > V.INLINE_MAX and not over:
        vb2 = max(16.0, vb * (V.INLINE_MAX / n) * 0.85)
        log(f"  [훑기] {n / 1e6:.1f}MB 로 상한을 넘었다 → {vb2:.0f}kbps 로 다시 만든다")
        r = subprocess.run(_enc_argv(enc, "retry", a, dur, src, out, vb2, 6, 24.0),
                           capture_output=True, text=True)
        if r.returncode or not os.path.exists(out):
            from volcano_run import err_gist
            raise RuntimeError(f"[훑기] 사본을 못 만들었다: {err_gist(r.stderr, 400)}")
        n = os.path.getsize(out)
    log(f"  [훑기] 사본 {n / 1e6:.1f}MB "
        + ("(인라인)" if n <= V.INLINE_MAX else "★상한 초과 — 분석 전에 구간을 나눕니다"))
    if n <= 0:
        raise RuntimeError("[훑기] 프록시 파일이 비어 있습니다")
    with _FileBody(out) as output:
        output_sha = V._media_digest(output).hex()
    _source.check()
    try:
        _asr_save(receipt, {"source_sha256": source_sha, "recipe": recipe,
                            "output_sha256": output_sha})
    except TranscriptionPending as exc:
        raise RuntimeError("[훑기] 프록시 검증 기록을 저장하지 못했습니다. 폴더 권한·여유 공간을 확인하세요.") from exc
    return out


def audit(picks, src_dur, channel, word_index=None, dur_range=None):
    """제안을 사실로 검사한다 → (통과한 것, 버린 사유들).

    ★`editplan` 은 **여기서 안 쓴다** — 원본에도 쓰이지 않는 import 였다(2026-08-17).
      배급본에는 그 모듈이 없어 그대로 두면 멈춘다. 지운다.
    ★`preset` 도 없을 수 있다. 그때는 `dur_range` 인자로 받는다 — 서버가 준다.
    """
    dr = dur_range
    if dr is None:
        try:
            import preset as P
            node = P.channel_node(channel) or {}
            dr = node.get("duration_range_sec")
            dr = dr.get("value") if isinstance(dr, dict) else dr
        except Exception:
            dr = None
    ok, bad = [], []
    for p in sorted(picks, key=lambda x: float(x.get("t0", 0))):
        try:
            a, z = float(p["t0"]), float(p["t1"])
        except Exception:
            bad.append((p, "시각이 숫자가 아니다"))
            continue
        if not (0 <= a < z <= src_dur + 1):
            bad.append((p, f"구간이 소재 밖이거나 뒤집혔다 {a:.0f}~{z:.0f}"))
            continue
        # ★소재 구간은 **편 길이보다 훨씬 길어야 한다** (2026-08-16 실측)
        #   나는 편 길이(47.2초)를 그대로 하한으로 걸었다. 그래서 눈이 54초짜리를
        #   제안했고, 그걸로 짜니 **어림 23~37초**밖에 안 나와 전부 떨어졌다.
        #   당연하다 — 소재 구간에서 실제로 쓰는 것은 **말이 있는 자리**뿐이고
        #   침묵·연결샷은 버린다. 정답지 린박스가 그 비를 말해 준다:
        #       소재 3440~3644 = 203초 → 편 56초 = **3.7배**
        #   그러니 하한은 편 길이가 아니라 **편 길이 x 3.7** 이다.
        if dr and (z - a) < float(dr[0]) * SRC_RATIO:
            bad.append((p, f"{z - a:.0f}초는 소재로 짧다 — 정본은 편({dr[0]}초)의 "
                           f"{SRC_RATIO}배({float(dr[0]) * SRC_RATIO:.0f}초)를 쓴다"))
            continue
        if ok and a < ok[-1]["t1"] + MIN_GAP:
            bad.append((p, f"앞 대목({ok[-1]['t0']:.0f}~{ok[-1]['t1']:.0f})과 겹친다"))
            continue
        if word_index is not None:
            n = len(word_index.between(a, z, pad=0.0, min_frac=0.5, min_abs=0.12))
            if n < 20:
                bad.append((p, f"그 구간에 말이 {n}단어뿐이다"))
                continue
            p["_words"] = n
        ok.append(p)
    return ok, bad


# ★배급본은 `editplan`·`preset`·등록부 JSON 을 갖고 있지 않다 (2026-08-17)
#   원본 `survey` 는 `editplan._guide(channel)` 로 채널 안내문을 만드는데, 그 함수는
#   `preset.channel_node` 와 `cutlen_canon.json` 같은 저장소 파일을 읽는다 —
#   수강생 기계엔 없다. 실제로 여기서 `ModuleNotFoundError` 로 멈췄다.
#   ★그런데 **그 값들은 MCP 서버가 이미 갖고 있다**(PRESETS·CHANNEL_RHYTHM·TONES).
#   그러니 안내문은 서버가 만들어 주고 배급본은 **받아 쓴다.** 값을 두 곳에서
#   따로 만들면 갈린다 — 이 저장소가 반복해 겪은 형태다.
def _valid_answer(answer, duration):
    if not isinstance(answer, dict) or not isinstance(answer.get('picks'), list):
        return False
    for p in answer['picks']:
        if not isinstance(p, dict): return False
        a, z, power = p.get('t0'), p.get('t1'), p.get('power')
        if (type(a) not in (int, float) or type(z) not in (int, float)
                or not math.isfinite(a) or not math.isfinite(z) or not 0 <= a < z <= duration + 1
                or type(power) is not int or not 1 <= power <= 5
                or not isinstance(p.get('what'), str) or not p['what'].strip()
                or not isinstance(p.get('why'), str) or not p['why'].strip()):
            return False
    return True


def _review_window(src, proxy, work, prompt, duration, binding, enc, api, auth=None):
    """One semantic request; reuse the shared client and paid receipt transports."""
    import copy
    import volcano_run as R
    key = hashlib.sha256(json.dumps(dict(binding, prompt=prompt), sort_keys=True,
                                   ensure_ascii=False).encode()).hexdigest()
    directory = os.path.join(work, '_survey_review', key)
    os.makedirs(directory, exist_ok=True)
    output = os.path.join(directory, 'answer.json')
    validator = lambda answer: _valid_answer(answer, duration)
    if R.resolve_review_policy()['provider'] == 'client':
        audio = R.cached_client_video_audio({'path':src, 'out':proxy,
            'shrink_argv':[(enc or {}).get('primary', ['ffmpeg'])[0]]}, directory)
        return R.client_review(dict(out=output, qc_contract='survey_picks_v1', prompt=prompt,
            video=proxy, binding=binding, **audio), validator=validator)
    if not isinstance(api, dict) or not api.get('endpoint') or api.get('body_kind') != 'gemini_video':
        raise R.StepError('서버의 영상 분석 API 규약이 없습니다. 기존 자료와 답을 보존하세요.')
    item = copy.deepcopy(api)
    item['body']['contents'][0]['parts'] = [{'text':prompt}]
    _, media, size = R._video_request_body(item, proxy, encode=False)
    if ((item.get('max_media_bytes') and media > item['max_media_bytes'])
            or (item.get('max_request_bytes') and size > item['max_request_bytes'])):
        raise R.StepError('영상 분석 자료가 서버의 요청 크기 상한을 넘었습니다. 새 API 요청은 보내지 않았습니다.')
    body, _, _ = R._video_request_body(item, proxy)
    # Bind source/window identity even when distinct windows happen to encode identically.
    item.update(out=output, qc_contract='survey_picks_v1:' + key)
    def headers():
        if auth:
            import contextlib
            from volcano_drive import auth_headers
            with contextlib.redirect_stdout(sys.stderr):
                resolved = auth_headers({'auth':auth})
            value = resolved[auth['header']]
            scheme = auth.get('scheme') or ''
            if not value.startswith(scheme): raise R.StepError('훑기 인증 헤더가 서버의 인증 규약과 다릅니다')
            value = value[len(scheme):]
        else:
            value = os.environ.get('EVOLINK_API_KEY')
        return {'x-goog-api-key':value} if value else None
    return R._paid_review_json(item, body, headers, validator=validator,
        parse=lambda raw:R._json_object(R._vision_text(raw, item.get('pluck'))))


def _survey_windows(src, channel, work, cache_dir, word_index, temps, off, hi,
                    log, guide, want, dur_range, enc, window, _source, api, auth):
    """기존 구간 훑기를 이어 전체를 덮는다. 각 구간의 캐시와 절대 시각을 유지한다."""
    if window <= want:
        raise RuntimeError("[훑기] 요청 대목을 담을 인라인 구간을 만들 수 없습니다. "
                           "더 짧은 선택 구간이 필요합니다. 이미 완료한 분석은 보존하세요.")
    combined, start = [], off
    while start < hi:
        end = min(start + window, hi)
        log(f"  [훑기 구간] {start:.1f}~{end:.1f}초 · 원본 시각으로 합칩니다")
        combined.extend(survey(src, channel, work=work, cache_dir=cache_dir,
                               word_index=word_index, temps=temps, t0=start, t1=end,
                               log=log, guide=guide, want=want, dur_range=dur_range, enc=enc,
                               _source=_source, api=api, auth=auth))
        if end == hi:
            break
        start = end - want
    _source.check()
    good, _ = audit(combined, _dur(src), channel, word_index, dur_range=dur_range)
    return sorted(good, key=lambda p: -int(p.get("power") or 0))


def survey(src, channel, work=None, cache_dir=None, word_index=None, temps=TEMPS,
           t0=None, t1=None, log=print, guide=None, want=None, dur_range=None, enc=None,
           _source=None, api=None, auth=None):
    """소재 -> 제안 목록. 감사를 통과한 것만 돌려준다.

    `t0`/`t1` 을 주면 그 구간만 훑는다. 눈이 답하는 시각은 **보여준 사본의 0초**
    기준이므로, 돌려줄 때 `t0` 을 더해 **소재 절대초**로 되돌린다.
    """
    if tuple(temps) != TEMPS:
        raise ValueError('[훑기] 구간마다 한 번 분석합니다. 온도별 자동 반복은 지원하지 않습니다.')
    if _source is None:
        with _SourceDigest(src) as source:
            return survey(src, channel, work=work, cache_dir=cache_dir, word_index=word_index,
                          temps=temps, t0=t0, t1=t1, log=log, guide=guide, want=want,
                          dur_range=dur_range, enc=enc, _source=source, api=api, auth=auth)
    # ★`guide`·`want` 를 받았으면 `editplan` 이 필요 없다 — 그 둘이 유일한 쓰임이다.
    #   배급본에는 그 모듈이 없으므로 여기서 무조건 부르면 멈춘다(실측 2회).
    EP = None
    if guide is None or want is None:
        import editplan as EP
    work = work or os.path.dirname(os.path.abspath(src))
    full = _dur(src)
    off = 0.0 if t0 is None else max(0.0, float(t0))
    hi = full if t1 is None else min(full, float(t1))
    dur = max(1.0, hi - off)
    log(f"■ 훑기 — {os.path.basename(src)} "
        + (f"{full / 60:.1f}분" if t0 is None and t1 is None
           else f"{off:.0f}~{hi:.0f}s ({dur / 60:.1f}분 · 전체 {full / 60:.1f}분)"))
    try:
        import preset as P
        _node = P.channel_node(channel) or {}
        _dr = _node.get("duration_range_sec")
        _dr = _dr.get("value") if isinstance(_dr, dict) else _dr
    except Exception:
        _dr = None
    _want = (float(_dr[0]) + float(_dr[1])) / 2 * SRC_RATIO if _dr else 200.0
    want = float(want) if want is not None else _want
    guide = guide if guide is not None else EP._guide(channel)
    if not all(math.isfinite(v) for v in (full, off, hi, want)) or not (0 <= off < hi <= full and want > 0):
        raise ValueError("[훑기] 원본 길이·구간·요청 대목 길이가 유효하지 않습니다")
    _source.check()
    inline_span = V.INLINE_MAX * 8 / 1024 / (AUD_KBPS + MIN_V_KBPS)
    if dur > inline_span:
        return _survey_windows(src, channel, work, cache_dir, word_index, temps, off, hi,
                               log, guide, want, dur_range, enc, inline_span * .75, _source, api, auth)
    proxy = _proxy(src, work, log=log, t0=t0, t1=t1, enc=enc, _source=_source)
    if os.path.getsize(proxy) > V.INLINE_MAX:
        # 실제 압축본도 확인한다. 같은 크기 벽을 세 온도로 재호출하지 않는다.
        return _survey_windows(src, channel, work, cache_dir, word_index, temps, off, hi,
                               log, guide, want, dur_range, enc, min(inline_span * .75, dur / 2), _source, api, auth)
    pr = PROMPT.format(
        guide=(guide if guide is not None else EP._guide(channel)),
        want=(float(want) if want else _want),
        mins=dur / 60.0,
        n_hint=max(1, int(dur // (float(want) if want else _want))))
    binding = {'version':1, 'source_sha256':_source.sha256, 'from':off, 'to':hi,
               'channel':channel, 'duration_range':dur_range, 'temperature':float(temps[0])}
    answer = _review_window(src, proxy, work, pr, dur, binding, enc, api, auth)
    if not _valid_answer(answer, dur):
        raise RuntimeError('[훑기] 이 구간을 분석하지 못했습니다. 대목 목록의 형식이나 시각을 확인하세요.')
    _source.check()
    picks = [dict(p, t0=p['t0'] + off, t1=p['t1'] + off) for p in answer['picks']]
    good, bad = audit(picks, full, channel, word_index, dur_range=dur_range)
    log(f"  [훑기] 제안 {len(picks)}개 → 통과 {len(good)}개 · 버림 {len(bad)}개")
    return sorted(good, key=lambda p: -p['power'])


def report(picks, log=print):
    log("")
    log(f"■ 이 소재에서 **{len(picks)}편**을 뽑을 수 있습니다 (센 것부터)")
    log("")
    for i, p in enumerate(picks, 1):
        a, z = float(p["t0"]), float(p["t1"])
        log(f"  {i}. {a / 60:5.1f}분~{z / 60:.1f}분 ({z - a:.0f}초) · 세기 {p.get('power')}")
        log(f"     {p.get('what')}")
        log(f"     └ {p.get('why')}")
        log(f"     선택한 {a:.1f}~{z:.1f}초 구간을 새 소재로 잘라 회차를 시작하세요.")
        log("")


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="서버가 준 지침으로 긴 소재 대목을 고릅니다.")
    parser.add_argument("source")
    parser.add_argument("--ch", required=True)
    parser.add_argument("--guide", required=True)
    parser.add_argument("--want", type=float, required=True)
    parser.add_argument("--enc-json", required=True)
    parser.add_argument("--dur-range-json")
    parser.add_argument("--review-json")
    parser.add_argument("--review-file")
    parser.add_argument("--api-json")
    parser.add_argument("--auth-json")
    parser.add_argument("--work")
    parser.add_argument("--sm")
    parser.add_argument("--from", dest="t0", type=float)
    parser.add_argument("--to", dest="t1", type=float)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    enc = json.loads(args.enc_json)
    if not isinstance(enc, dict):
        parser.error("--enc-json은 서버가 준 명령 묶음입니다")
    idx = None
    if args.sm and os.path.exists(args.sm):
        from utterance import WordIndex
        idx = WordIndex.load(args.sm)
    work = args.work or os.path.dirname(os.path.abspath(args.source))
    log = (lambda *a: print(*a, file=sys.stderr)) if args.json else print
    import volcano_run as R
    if args.review_file:
        with open(args.review_file, encoding='utf-8') as stream: review = json.load(stream)
    else:
        review = json.loads(args.review_json) if args.review_json else {}
    review['budget'] = review.get('budget') or os.path.join(work, 'review-budget.sqlite3')
    try:
        with R.review_context(**review):
            picks = survey(args.source, args.ch, work=work, cache_dir=os.path.join(work, "_survey_vision"),
                word_index=idx, t0=args.t0, t1=args.t1, guide=args.guide, want=args.want,
                enc=enc, dur_range=json.loads(args.dur_range_json) if args.dur_range_json else None,
                api=json.loads(args.api_json) if args.api_json else None,
                auth=json.loads(args.auth_json) if args.auth_json else None, log=log)
    except R.ClientReviewPending as pending:
        print(json.dumps({'status':'client_review_pending','review_requests':[pending.request]},ensure_ascii=False))
        return 3
    except Exception as exc:
        stopped = {'status':'review_stopped','code':getattr(exc,'code','survey_analysis_failed'),
                   'why':str(exc)[:1200]}
        if isinstance(exc,R.ProviderRefusalError):
            stopped.update(origin=exc.origin,reason_code=exc.reason_code,reason=exc.reason)
        print(json.dumps(stopped,ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(picks, ensure_ascii=False))
    else:
        report(picks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
