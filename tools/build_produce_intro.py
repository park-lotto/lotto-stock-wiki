#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""체험판 제작소 소개 페이지 생성기 (2026-08-20)

사장님 지시(2차, 스크린샷 2장과 함께):
  "단계별로 이런 목업스타일로 보여주고 너가 코멘트를 주석으로 달아주면 안 되냐."
→ 글로 설명하는 페이지가 아니라 **진짜 제작소 화면을 그대로 재현한 목업**에
  주석(말풍선)을 얹는다. 9단계 오브 바 · 담은 영상 카드 · 구조 스트립 ·
  대본 스타일 카드 · 비트 행 — 실제 화면에 있는 것들을 같은 모양으로 만든다.

★왜 진짜 produce.html을 안 띄우고 목업인가
  `/api/produce/*`는 체험 등급에 전부 402(과금 기능이라 여는 게 위험). 진짜 화면은
  열리자마자 API를 여러 개 부르므로 곳곳에 402 에러가 뜨고, 그걸 막으려면 58만자짜리
  화면의 버튼을 전부 찾아 잠가야 하는데 **빠뜨린 버튼 하나가 곧 과금**이다.
  목업은 API를 0개 부르므로 그 위험이 원천적으로 없다.

★디자인은 베끼지 않고 **theme.css를 그대로 쓴다**(0순위-B: 같은 판단을 두 번 적지 않는다).
  오브 바(.orbbar/.orb/.ball/.lb)는 실제 화면과 같은 CSS를 타므로 색·크기가 자동으로 일치한다.
  theme.css가 바뀌면 이 페이지도 같이 바뀐다 — 따로 관리할 일이 없다.
  `/static/`은 체험 등급에도 열려 있다(실측: _ranking_only_blocked('/static/theme.css')==False).

쓰는 법(샘플을 바꾸고 싶을 때만):
    py tools/build_produce_intro.py --json <sample.json>
  sample.json은 produce_works.state_json에서 뽑은 것. 인자 없이 돌리면 내장 기본값으로 굽는다.
"""
import argparse
import html
import json
import pathlib
import sys
from urllib.parse import quote

HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "shopping_shorts" / "static" / "produce_intro.html"

# 실제 화면의 9단계(produce.html 오브 바와 같은 순서·이름).
STEPS = ["영상추출/분석", "대본생성", "영상대본MIX", "고품질 자막제거", "TTS음성",
         "자막꾸미기", "썸네일", "SEO해시태크", "최종렌더"]

# 실제 라이브 작업(work_id 7b0491f0de…, step 8=최종렌더)에서 뽑은 값.
# 손으로 지어낸 숫자가 하나도 없다.
_SAMPLE = {
    "product": "미세 노즐 실란트 주사기",
    "sources": [
        {"chars": 114, "head": "만원이면 가구 틈새 실리콘 마감이 뚝딱이여 기존 실리콘건은 너무 크잖아?"},
        {"chars": 205, "head": "이런 거 하나 있으면 든든하죠! 집이 오래돼서 보수할 데가 많았는데 인테…"},
        {"chars": 915, "head": "¿Sabías que la humedad del ambiente dete…"},
    ],
    "scene_points": 14,
    "styles": ["단정 명령형", "가족갈등 반전형"],
    "beats": [
        {"role": "hook", "label": "미끼", "sec": 3.9,
         "text": "여러분, 집안 틈새 보수할 때 실리콘 건 덩치 큰 거 쓰지 마세요. 이게 진짜 난리예요!"},
        {"role": "before", "label": "찔림", "sec": 6.6,
         "text": "저도 예전엔 큰 건으로 쏘다가 다 삐져나와서 닦느라 고생만 했거든요. "
                 "인테리어 망치고 나면 수습도 안 돼서 얼마나 짜증나던지 몰라요."},
        {"role": "reveal", "label": "반전", "sec": 7.3,
         "text": "근데 인테리어 하는 친구가 이 미세 노즐 실란트 주사기를 슥 내밀더라고요. "
                 "주사기처럼 생겨서 필요한 만큼만 딱 짜니까 힘 안 줘도 일정하게 쫙 나와요."},
        {"role": "after", "label": "증거", "sec": 6.9,
         "text": "덕분에 가구 모서리 틈새가 싹 메워지니까 곰손인 저도 전문가처럼 깔끔하게 끝냈거든요. "
                 "남은 거 굳어서 버릴 일도 없어서 진짜 경제적이에요."},
        {"role": "cta", "label": "약속", "sec": 4.3,
         "text": "어디서 샀냐고들 물어봐서 댓글에 '실리콘' 남겨주시면 구매한 링크 바로 보내 드릴게요."},
    ],
    "sources_thumbs": [],
}

# 비트 역할 → 구조 스트립 색(실제 화면의 훅/주변인물등장/제품소개/결과/CTA 띠와 같은 결)
_ROLE_COLOR = {"hook": "#f0c674", "before": "#c39bf0", "reveal": "#7fb3f5",
               "after": "#5fe0b4", "cta": "#f0a875"}
_ROLE_HELP = {
    "hook": "첫 3초. 여기서 못 잡으면 뒤를 아무리 잘 만들어도 안 봅니다.",
    "before": "보는 사람이 겪은 불편을 먼저 말해 '내 얘기네' 하고 붙잡는 자리.",
    "reveal": "제품이 처음 나옵니다. 광고가 아니라 '해결책'으로 들어와요.",
    "after": "쓰고 나서 뭐가 달라졌는지. 사고 싶어지는 건 대개 이 대목입니다.",
    "cta": "댓글·링크로 이어지는 마무리. 채널마다 문구가 다릅니다.",
}


def _thumb(url):
    """인스타 CDN 주소는 직접 못 읽는다(403) → 서버 프록시를 태운다."""
    return ("/api/thumb?url=" + quote(url, safe="")) if url else ""


def _e(s):
    return html.escape(str(s or ""))


def _orbbar(cur=1):
    """실제 화면과 같은 9단계 오브 바. 클래스는 theme.css 것을 그대로 쓴다."""
    pct = int((cur - 1) / (len(STEPS) - 1) * 100)
    orbs = []
    for i, name in enumerate(STEPS, 1):
        cls = "orb done" if i < cur else ("orb cur" if i == cur else "orb")
        ball = "✓" if i < cur else str(i)
        orbs.append(f'<div class="{cls}"><div class="ball">{ball}</div>'
                    f'<div class="lb">{_e(name)}</div></div>')
    return (f'<div class="orbbar"><div class="orbline">'
            f'<div class="orbfill" style="width:{pct}%"></div></div>{"".join(orbs)}</div>')


def _note(text, kind=""):
    """★주석(말풍선) — 사장님이 요청한 '내가 다는 코멘트'. 목업 위에 얹힌다."""
    k = f" note-{kind}" if kind else ""
    return f'<div class="note{k}"><span class="note-pin">💬</span><div>{text}</div></div>'


def _sources_cards(sample):
    thumbs = [t for t in (sample.get("sources_thumbs") or []) if t]
    cards = []
    for i, t in enumerate(thumbs[:5]):
        badge = '<span class="aipick">AI PICK</span>' if i == 0 else '<span class="chk">✓</span>'
        cards.append(f'<div class="vcard">{badge}'
                     f'<img src="{_e(_thumb(t))}" alt="담은 영상 {i+1}" loading="lazy" '
                     f'onerror="this.parentElement.classList.add(\'noimg\')">'
                     f'<span class="play">▶</span></div>')
    if not cards:
        cards = ['<div class="vcard noimg"><span class="play">▶</span></div>' for _ in range(5)]
    return "".join(cards)


def _strip(beats):
    """구조 스트립 — 대본이 어떤 색 띠로 나뉘는지(실제 화면 그대로)."""
    total = sum(b["sec"] for b in beats) or 1
    segs = []
    for b in beats:
        w = b["sec"] / total * 100
        segs.append(f'<span style="width:{w:.1f}%;background:{_ROLE_COLOR.get(b["role"], "#888")}">'
                    f'{_e(b["label"])}</span>')
    return f'<div class="strip">{"".join(segs)}</div>'


def _beat_rows(beats):
    rows = []
    icons = {"hook": "🎣", "before": "😣", "reveal": "💡", "after": "✨", "cta": "📣"}
    for b in beats:
        rows.append(f"""
        <div class="brow">
          <div class="bk"><span class="bi">{icons.get(b['role'], '•')}</span>
            <span class="bl">{_e(b['label'])}</span></div>
          <div class="bt">{_e(b['text'])}
            <div class="bhelp">💬 {_e(_ROLE_HELP.get(b['role'], ''))} <span class="bsec">· {b['sec']}초</span></div>
          </div>
          <div class="bbtn">바꾸기</div>
        </div>""")
    return "".join(rows)


def _src_rows(sources):
    out = []
    for i, s in enumerate(sources, 1):
        out.append(f"""
        <div class="scard">
          <div class="stag">영상 {i}</div>
          <div class="schips"><span class="chip2">말 있음 {s['chars']}자</span></div>
          <p class="stext">{_e(s['head'])}</p>
        </div>""")
    return "".join(out)


def build(sample):
    total = round(sum(b["sec"] for b in sample["beats"]), 1)
    return f"""<!doctype html>
<meta charset="utf-8">
<title>숏템 제작소 — 이렇게 만들어집니다</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/theme.css">
<style>
  /* ★색·오브 바는 theme.css 것을 그대로 쓴다(0순위-B). 여기선 목업 전용 뼈대만 얹는다. */
  :root{{--bg:#070b14;--card:#0f1522;--card2:#141b2a;--txt:#e8eaf0;--sub:#8b95a8;
        --line:#1e2635;--mint:#3ee0bf}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--txt);line-height:1.6;
       font-family:system-ui,-apple-system,"Malgun Gothic",sans-serif}}
  .wrap{{max-width:1080px;margin:0 auto;padding:22px 16px 70px}}

  .ribbon{{background:linear-gradient(90deg,rgba(62,224,191,.14),rgba(62,224,191,.03));
          border:1px solid rgba(62,224,191,.4);border-radius:11px;padding:12px 16px;
          margin-bottom:20px;font-size:14px}}
  .ribbon b{{color:var(--mint)}}
  h1{{font-size:24px;margin:0 0 4px;letter-spacing:-.4px}}
  .lead{{color:var(--sub);margin:0 0 20px;font-size:14.5px}}

  /* 목업 판 — 진짜 화면처럼 보이는 카드 */
  .mock{{background:var(--card);border:1px solid var(--line);border-radius:14px;
        padding:18px 20px;margin:0 0 16px;position:relative}}
  .mock h3{{font-size:17px;margin:0 0 3px}}
  .mock .sub{{color:var(--sub);font-size:13px;margin:0 0 14px}}
  .stage{{font-size:12px;font-weight:800;color:var(--mint);letter-spacing:.4px;
         display:block;margin-bottom:2px}}

  /* ★주석 말풍선 */
  .note{{display:flex;gap:9px;background:rgba(62,224,191,.09);
        border-left:3px solid var(--mint);border-radius:0 9px 9px 0;
        padding:10px 13px;margin:13px 0 0;font-size:13.5px;color:#cfe4de}}
  .note b{{color:#fff}}
  .note-pin{{flex:0 0 auto}}
  .note-warn{{background:rgba(245,166,35,.10);border-left-color:#f5a623;color:#ecd9b6}}

  /* 담은 영상 카드 */
  .vcards{{display:flex;gap:10px;flex-wrap:wrap}}
  .vcard{{position:relative;width:104px;height:139px;border-radius:9px;overflow:hidden;
         background:var(--card2);border:1px solid var(--line);flex:0 0 auto}}
  .vcard img{{width:100%;height:100%;object-fit:cover;display:block}}
  .vcard.noimg img{{display:none}}
  .vcard .play{{position:absolute;inset:0;margin:auto;width:30px;height:30px;
               background:rgba(0,0,0,.5);border-radius:50%;display:flex;
               align-items:center;justify-content:center;font-size:12px;color:#fff}}
  .aipick{{position:absolute;top:5px;left:5px;z-index:2;background:#f5b53f;color:#3a2800;
          font-size:9px;font-weight:800;padding:2px 6px;border-radius:4px}}
  .chk{{position:absolute;top:5px;right:5px;z-index:2;background:var(--mint);color:#062;
       width:16px;height:16px;border-radius:50%;font-size:10px;display:flex;
       align-items:center;justify-content:center;font-weight:800}}

  /* 분석 카드 */
  .scards{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
  .scard{{flex:1 1 240px;background:var(--card2);border:1px solid var(--line);
         border-radius:10px;padding:12px 14px;min-width:0}}
  .stag{{display:inline-block;background:rgba(62,224,191,.16);color:var(--mint);
        font-size:11px;font-weight:800;padding:2px 9px;border-radius:20px;margin-bottom:7px}}
  .chip2{{display:inline-block;border:1px solid var(--line);border-radius:20px;
         padding:2px 9px;font-size:11.5px;color:var(--sub);margin-right:5px}}
  .stext{{margin:8px 0 0;font-size:13px;color:#c3ccdb}}

  /* 구조 스트립 */
  .strip{{display:flex;height:26px;border-radius:6px;overflow:hidden;margin:12px 0 0}}
  .strip span{{display:flex;align-items:center;justify-content:center;font-size:11px;
              font-weight:800;color:#10151f;overflow:hidden;white-space:nowrap}}

  /* 스타일 카드 */
  .stcards{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
  .stcard{{flex:1 1 210px;background:var(--card2);border:1px solid var(--line);
          border-radius:10px;padding:13px 15px;min-width:0}}
  .stcard.on{{border-color:var(--mint);box-shadow:0 0 0 1px rgba(62,224,191,.35) inset}}
  .stname{{font-weight:800;font-size:14.5px;margin-bottom:3px}}
  .stname .ok{{float:right;font-size:11px;color:var(--mint)}}
  .stdesc{{font-size:12.5px;color:var(--sub)}}

  /* 비트 행 */
  .brow{{display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-top:1px solid var(--line)}}
  .brow:first-of-type{{border-top:0}}
  .bk{{flex:0 0 76px;display:flex;align-items:center;gap:6px}}
  .bi{{font-size:14px}}
  .bl{{font-size:13px;font-weight:800;color:#cbd4e3}}
  .bt{{flex:1;font-size:14px;min-width:0}}
  .bhelp{{font-size:12.5px;color:var(--sub);margin-top:4px}}
  .bsec{{color:#6f7a8d}}
  .bbtn{{flex:0 0 auto;border:1px solid var(--line);border-radius:7px;padding:5px 12px;
        font-size:12px;color:#5c6678;background:#111827}}

  .cta{{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px}}
  .btn{{display:inline-block;padding:12px 20px;border-radius:9px;text-decoration:none;
       font-weight:800;font-size:14.5px}}
  .btn.primary{{background:linear-gradient(90deg,#3ee0bf,#14b8a6);color:#062}}
  .btn.ghost{{border:1px solid var(--line);color:var(--txt)}}
  .foot{{margin-top:16px;font-size:13px;color:var(--sub)}}
  @media(max-width:640px){{
    .orbbar{{overflow-x:auto;justify-content:flex-start;gap:6px}}
    .orb{{flex:0 0 auto;min-width:62px}}
    .vcard{{width:84px;height:112px}}
    .bk{{flex-basis:60px}} .bbtn{{display:none}}
  }}
</style>
<div class="wrap">

  <div class="ribbon">
    👀 <b>미리보기입니다.</b> 아래는 실제로 완성된 영상 한 편이 <b>어떻게 만들어졌는지</b>를
    화면 그대로 펼쳐놓은 것이라 <b>누르거나 고칠 수는 없습니다.</b>
    이용권을 시작하면 이 화면을 직접 돌릴 수 있어요.
  </div>

  <h1>🛠 숏템 제작소는 이렇게 돌아갑니다</h1>
  <p class="lead">영상 몇 개를 담으면 → 대본이 나오고 → 장면이 붙고 → 한 편이 완성됩니다.
     지금 보시는 건 실제 완성작 <b>{_e(sample['product'])}</b> 편이에요.</p>

  {_orbbar(1)}
  {_note("<b>9단계짜리 한 줄</b>입니다. 담기부터 최종 영상까지 이 순서로 흘러가고, "
         "각 단계는 <b>앞 단계 결과를 받아서</b> 이어집니다. 아래에서 주요 단계를 하나씩 보여드릴게요.")}

  <div class="mock">
    <span class="stage">1단계</span>
    <h3>영상추출 / 분석</h3>
    <p class="sub">쓸 영상을 담으면 AI가 영상마다 무엇을 보여주는지 분석합니다.</p>
    <div class="vcards">{_sources_cards(sample)}</div>
    {_note("담아둔 영상의 <b>말(자막)을 전부 받아적고</b> 화면에 뭐가 나오는지까지 읽습니다. "
           "왼쪽 첫 칸의 <b>AI PICK</b>은 그중 대표로 뽑힌 영상이에요.")}
    <div class="scards">{_src_rows(sample['sources'])}</div>
    {_note("영상마다 <b>받아적은 글자 수</b>가 보입니다. "
           "<b>자막이 아예 없는 영상도</b> 화면만 보고 알아내고, 외국어(스페인어)도 그대로 읽어요. "
           "여기서 모인 게 <b>대본의 재료</b>가 됩니다.")}
  </div>

  <div class="mock">
    <span class="stage">2단계</span>
    <h3>대본생성 — 어떤 말투로 쓸지 고릅니다</h3>
    <p class="sub">훅·전개·CTA가 한 몸 · 고른 만큼 안이 나옵니다.</p>
    <div class="stcards">
      <div class="stcard on"><div class="stname">{_e(sample['styles'][0])}<span class="ok">✓ 선택</span></div>
        <div class="stdesc">아는 전문가가 알려준 걸 단정적으로 알려준다</div></div>
      <div class="stcard"><div class="stname">{_e(sample['styles'][1])}</div>
        <div class="stdesc">가족에게 혼났는데 알고 보니 그 물건 덕분</div></div>
      <div class="stcard"><div class="stname">물건 발견형</div>
        <div class="stdesc">권위 있는 출처에서 화제가 된 신기한 물건을 발견해 소개한다</div></div>
    </div>
    {_note("잘 터진 채널들의 <b>말하는 방식</b>을 미리 학습해둔 틀입니다. "
           "같은 제품이라도 틀을 바꾸면 <b>완전히 다른 영상</b>이 나와요. "
           "이번 편은 <b>{}</b>으로 뽑았습니다.".format(_e(sample['styles'][0])))}
  </div>

  <div class="mock">
    <span class="stage">2단계 결과</span>
    <h3>대본이 나옵니다 — 통째로가 아니라 <em>역할별</em>로</h3>
    <p class="sub">전체 {total}초 · 다섯 토막</p>
    {_strip(sample['beats'])}
    {_note("위 <b>색 띠</b>가 대본의 뼈대입니다. 띠 하나가 한 토막이고, "
           "<b>폭이 곧 그 토막의 길이(초)</b>예요. 훅이 짧고 제품 설명이 긴 게 한눈에 보입니다.")}
    {_beat_rows(sample['beats'])}
    {_note("토막마다 <b>몇 초짜리인지</b> 정해져 있어서, 다음 단계에서 장면을 그 길이에 맞춰 "
           "잘라 붙일 수 있습니다. 마음에 안 드는 토막은 <b>그 줄만</b> 다시 뽑아요 "
           "(오른쪽 <b>바꾸기</b>) — 대본 전체를 새로 쓸 필요가 없습니다.")}
  </div>

  <div class="mock">
    <span class="stage">3단계</span>
    <h3>영상대본MIX — 대사에 맞는 장면을 붙입니다</h3>
    <p class="sub">쓸 만한 장면 {sample['scene_points']}곳을 찾아뒀습니다.</p>
    {_strip(sample['beats'])}
    {_note("담은 영상들에서 쓸 만한 장면 <b>{}곳</b>을 찾아두고, 대사 내용과 맞는 자리에 "
           "자동으로 배치합니다. \"주사기처럼 생겨서\"라고 말할 때 "
           "<b>실제로 그 장면이 나오게</b> 맞추는 일이에요.".format(sample['scene_points']))}
  </div>

  <div class="mock">
    <span class="stage">4~9단계</span>
    <h3>자막 지우고 · 목소리 입히고 · 꾸며서 · 한 편으로</h3>
    <p class="sub">고품질 자막제거 → TTS음성 → 자막꾸미기 → 썸네일 → SEO해시태그 → 최종렌더</p>
    {_note("남의 영상에 박혀 있던 <b>자막을 지우고</b> 내 대본으로 새 자막을 답니다. "
           "성우 목소리를 얹고, 썸네일과 해시태그까지 만들어 "
           "<b>바로 올릴 수 있는 영상 파일</b>로 내보냅니다.")}
    {_note("여기까지가 <b>한 편</b>입니다. 사람이 하는 건 '어떤 영상을 담을지' 고르는 것과 "
           "'마음에 안 드는 곳을 바꾸기' 두 가지예요.", "warn")}
  </div>

  <div class="cta">
    <a class="btn primary" href="/pricing">이용권 보기</a>
    <a class="btn ghost" href="/">← 레퍼런스 랭킹으로</a>
  </div>
  <p class="foot">체험 기간에는 <b>레퍼런스 랭킹</b>과 <b>영상 즐겨찾기</b>를 자유롭게 쓰실 수 있어요.
     마음에 드는 영상을 미리 담아두시면, 이용권을 시작할 때 <b>그대로 이어서</b> 만들 수 있습니다.</p>
</div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="produce_works에서 뽑은 샘플 JSON(없으면 내장 기본값)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    sample = dict(_SAMPLE)
    if a.json:
        raw = json.loads(pathlib.Path(a.json).read_text(encoding="utf-8"))
        if raw.get("sources"):
            sample["sources"] = raw["sources"]
        if raw.get("scene_points"):
            sample["scene_points"] = raw["scene_points"]
        if raw.get("styles"):
            sample["styles"] = raw["styles"]
        drafts = raw.get("drafts") or []
        if drafts and drafts[0].get("beats"):
            labels = {"hook": "미끼", "before": "찔림", "reveal": "반전",
                      "after": "증거", "cta": "약속"}
            sample["beats"] = [
                {"role": b.get("role", ""), "label": labels.get(b.get("role", ""), b.get("role", "")),
                 "sec": b.get("sec", 0), "text": b.get("text", "")}
                for b in drafts[0]["beats"]]
        sample["sources_thumbs"] = [h.get("thumbnail") for h in (raw.get("handoff") or [])
                                    if h.get("thumbnail")]

    out = pathlib.Path(a.out)
    out.write_text(build(sample), encoding="utf-8")
    print(f"생성 완료: {out} ({out.stat().st_size:,} bytes)")

    body = out.read_text(encoding="utf-8")
    # 자가검증 — 이 페이지는 API를 하나도 부르면 안 된다(체험 등급은 전부 402라서).
    for bad in ("fetch(", "XMLHttpRequest", "<script", "onclick="):
        assert bad not in body, f"★{bad} 가 들어있다 — 이 페이지는 정적·비대화식이어야 한다"
    assert "/api/produce" not in body, "★/api/produce 를 부르면 402가 뜬다"
    print("자가검증 통과: script/fetch/onclick 0건, /api/produce 0건")


if __name__ == "__main__":
    sys.exit(main())
