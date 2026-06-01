# -*- coding: utf-8 -*-
"""
viewtrap_missions.py — 강의별 미션/노트 텍스트 전체 수집
저장: raw/viewtrap/미션_전체.md
"""
import sys, io, json, time, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

BASE    = Path(__file__).parent
OUT_DIR = BASE / 'raw' / 'viewtrap'
OUT_DIR.mkdir(parents=True, exist_ok=True)

CURRICULUM_ID = '69c49d3474de71e13f64ea7b'

def clean(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    page = ctx.new_page()

    # ── 강의 목록 로드 ──────────────────────────────────────
    with open(BASE / 'viewtrap_api_dump.json', encoding='utf-8') as f:
        d = json.load(f)

    item     = d['data'][0]
    chapters = item['chapters']

    all_results = []
    total = sum(len(ch['videos']) for ch in chapters)
    done  = 0

    for ch in chapters:
        ch_title = f"{ch.get('label','')} {ch.get('title','')}".strip()
        ch_results = []
        print(f"\n{'='*55}")
        print(f"[{ch_title}]")

        for video in ch['videos']:
            v_title = video['title']
            v_key   = video.get('videoKey','')
            done   += 1
            print(f"\n  [{done}/{total}] {v_title}")

            if not v_key:
                print("    videoKey 없음, 스킵")
                ch_results.append({'title': v_title, 'mission': '', 'page_text': ''})
                continue

            # 해당 강의 페이지 이동
            url = f"https://viewtrap.com/business/lectures?curriculumId={CURRICULUM_ID}&videoKey={v_key}"
            try:
                page.goto(url, wait_until='networkidle', timeout=25000)
                time.sleep(2)
            except Exception as e:
                print(f"    페이지 로드 실패: {e.__class__.__name__}")
                ch_results.append({'title': v_title, 'mission': '', 'page_text': ''})
                continue

            # ── 미션 버튼 탐색 ─────────────────────────────
            missions = []

            # 현재 강의에 해당하는 미션 버튼 찾기
            # 강의 제목 버튼이 active 상태인 것 바로 옆 "미션 보기" 버튼
            mission_btns = page.query_selector_all('button:has-text("미션 보기")')

            # active 강의 찾아서 해당 미션만 클릭
            # 구조: 강의버튼(active) + 미션버튼이 같은 부모 안에 있음
            active_mission = page.query_selector(
                '.text-primary ~ button:has-text("미션 보기"), '
                'button.text-primary + button:has-text("미션 보기")'
            )

            # 그냥 현재 페이지의 모든 미션 버튼 클릭
            btn_count = len(mission_btns)
            print(f"    미션 버튼 {btn_count}개")

            for i, btn in enumerate(mission_btns):
                try:
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    time.sleep(1.2)

                    # 모달 내용 추출
                    modal = page.query_selector('[role=dialog], [class*=modal], [class*=Modal]')
                    if modal:
                        txt = clean(modal.inner_text())
                        # "Close" 버튼 텍스트 제거
                        txt = re.sub(r'^Close\n?', '', txt).strip()
                        if txt and len(txt) > 20:
                            missions.append(txt)
                            print(f"    미션{i+1}: {txt[:60]}...")

                    # 모달 닫기
                    close = page.query_selector('[role=dialog] button:has-text("Close"), [role=dialog] button[aria-label*="close"], [role=dialog] button[aria-label*="닫기"]')
                    if close:
                        close.click()
                    else:
                        page.keyboard.press('Escape')
                    time.sleep(0.8)

                except Exception as e:
                    print(f"    미션 클릭 오류: {e.__class__.__name__}")

            # ── 강의 노트/설명 영역 ─────────────────────────
            # 미션 버튼 없는 강의는 페이지 본문 텍스트
            page_note = ''
            note_sel = '[class*=note], [class*=Note], [class*=description], [class*=content-text], [class*=lecture-detail]'
            note_el = page.query_selector(note_sel)
            if note_el:
                page_note = clean(note_el.inner_text())

            ch_results.append({
                'title':     v_title,
                'mission':   '\n\n---\n\n'.join(missions) if missions else '',
                'page_text': page_note,
            })

            if missions:
                print(f"    ✅ 미션 {len(missions)}개 수집")
            elif page_note:
                print(f"    📝 노트 {len(page_note)}자")
            else:
                print(f"    - 수집 내용 없음")

        all_results.append({'chapter': ch_title, 'videos': ch_results})

    # ── 마크다운 저장 ────────────────────────────────────────
    lines = ['# 비즈니스PT 2025 — 미션 & 노트 전체\n']

    for ch_data in all_results:
        lines.append(f"## {ch_data['chapter']}\n")
        for v in ch_data['videos']:
            lines.append(f"### {v['title']}\n")
            if v['mission']:
                lines.append(v['mission'])
                lines.append('')
            elif v['page_text']:
                lines.append(v['page_text'])
                lines.append('')
            else:
                lines.append('*(수집 내용 없음)*\n')

    md = '\n'.join(lines)
    out_path = OUT_DIR / '미션_전체.md'
    out_path.write_text(md, encoding='utf-8')

    print(f"\n{'='*55}")
    print(f"✅ 저장 완료: {out_path}")
    print(f"   총 {sum(len(c['videos']) for c in all_results)}강")
    print(f"   미션 있는 강의: {sum(1 for c in all_results for v in c['videos'] if v['mission'])}개")

    page.close()
    browser.close()
