"""감정짤 뷰어 실측 — 진짜 브라우저로 지우기·되살리기·이동·묶음 이동·재생을 눌러 보고 state.json 저장까지 확인한다.

    py tools/meme_pack/check_viewer.py <작업폴더> [스크린샷 경로]

검사 동안 바꾼 state.json 은 끝나면 원래대로 되돌린다(검사가 사장님이 고른 것을 건드리지 않는다).
실패가 하나라도 있으면 종료코드 1.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

PORT = 8766
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    work = os.path.abspath(sys.argv[1])
    shot = sys.argv[2] if len(sys.argv) > 2 else None
    state_path = os.path.join(work, "state.json")
    before = open(state_path, "rb").read() if os.path.exists(state_path) else None
    srv = subprocess.Popen([sys.executable, os.path.join(HERE, "serve.py"), work, "--port", str(PORT), "--no-open"])
    fails, url, touched = [], f"http://127.0.0.1:{PORT}/", []

    def check(name, cond, detail=""):
        print(("  통과 " if cond else "  실패 ") + name + (f" — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    def state():
        return json.load(open(state_path, encoding="utf-8")) if os.path.exists(state_path) else {}

    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(url + "api/items", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page(viewport={"width": 1400, "height": 1000})
            pg.goto(url)
            pg.wait_for_selector("figure")

            def counts():
                return {b.get_attribute("data-cat"): int(b.inner_text().split()[-1]) for b in pg.query_selector_all("#tabs button")}

            c0 = counts()
            cats = [c for c in c0 if c != "휴지통"]
            api = json.load(urllib.request.urlopen(url + "api/items"))
            check("카테고리 탭 수 = 서버 목록 + 휴지통", len(c0) == len(api["categories"]) + 1, f"{len(c0)}탭")
            check("탭 숫자 합 = 전체 영상 수", sum(c0.values()) == len(api["items"]), f"{sum(c0.values())} / {len(api['items'])}")
            first = cats[0]
            thumbs_ok = pg.evaluate("Promise.all([...document.querySelectorAll('figure video')].map(v=>new Promise(r=>{const i=new Image();i.onload=()=>r(1);i.onerror=()=>r(0);i.src=v.poster;}))).then(a=>a.reduce((x,y)=>x+y,0))")
            n_fig = len(pg.query_selector_all("figure"))
            check("첫 탭 표지 그림 전부 뜸", thumbs_ok == n_fig, f"{thumbs_ok}/{n_fig}")

            # 재생: 마우스 올리면 실제로 시간이 흐르나
            v = pg.query_selector("figure video")
            v.hover()
            pg.wait_for_timeout(1200)
            # 2초 짤은 되감기며 돌아 currentTime 만으로는 못 잰다 → 0.4초 간격 두 번 재서 시간이 움직였는지 본다
            t1 = v.evaluate("v=>v.currentTime")
            pg.wait_for_timeout(400)
            t2, paused = v.evaluate("v=>[v.currentTime, v.paused]")
            check("마우스 올리면 재생", (not paused) and t1 != t2, f"{t1:.2f}→{t2:.2f}")

            # 2초 하이라이트: 잘린 클립이 걸려 있나 + '0.5초 뒤' 를 누르면 클립 파일이 실제로 바뀌나
            hl_items = [it for it in api["items"] if it.get("hl") and not it["deleted"]]
            if hl_items:
                over = [it["id"] for it in hl_items if it["hl"]["dur"] > 2.3]
                check("하이라이트 길이 전부 2.3초 이하", not over, f"{len(hl_items)}개 중 초과 {len(over)}")
                h0 = next((it for it in hl_items if it["emotion"] == first), None)
                if h0:
                    clip = os.path.join(work, "library", "clips", h0["id"] + ".mp4")
                    hl_path = os.path.join(work, "highlights.json")
                    keep_clip, keep_hl = open(clip, "rb").read(), open(hl_path, "rb").read()
                    sel_v = f'figure[data-id="{h0["id"]}"]'
                    check("카드가 잘린 클립을 재생", "/library/clips/" in pg.get_attribute(sel_v + " video", "src"))
                    pg.click(sel_v + ' .nd button[data-d="0.5"]')
                    pg.wait_for_function(f"document.querySelector('{sel_v} video').src.includes('s={h0['hl']['start'] + 0.5}') || true")
                    pg.wait_for_timeout(2500)
                    now = json.load(open(hl_path, encoding="utf-8"))[h0["id"]]["start"]
                    changed = open(clip, "rb").read() != keep_clip
                    check("0.5초 뒤: 시작점 저장·클립 파일 바뀜", changed and now != h0["hl"]["start"], f'{h0["hl"]["start"]}→{now}')
                    open(clip, "wb").write(keep_clip)          # 검사 흔적 원복
                    cur = json.load(open(hl_path, encoding="utf-8"))
                    cur[h0["id"]] = json.loads(keep_hl)[h0["id"]]
                    json.dump(cur, open(hl_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                    pg.reload()
                    pg.wait_for_selector("figure")

            # 국내/해외·실사/애니: 필터를 누르면 그 구분만 남나 + 카드 표시를 누르면 바뀌어 저장되나
            tagged = [it for it in api["items"] if it.get("region") and it.get("kind") and not it["deleted"]]
            if tagged:
                for label, key, vals in (("지역", "region", api["regions"]), ("종류", "kind", api["kinds"])):
                    for val in vals:
                        # 자동 구분이 도는 중이면 숫자가 계속 는다 → 화면과 서버를 같은 순간에 다시 받아 견준다
                        pg.reload()
                        pg.wait_for_selector("#filters button")
                        now = json.load(urllib.request.urlopen(url + "api/items"))["items"]
                        pg.click(f'#filters button[data-f="{label}:{val}"]')
                        want = sum(1 for it in now if not it["deleted"] and it[key] == val)
                        shown = sum(n for c, n in counts().items() if c != "휴지통")
                        check(f"필터 {label}={val}: 탭 합계 = 그 구분 수", shown == want, f"{shown}/{want}")
                    pg.click(f'#filters button[data-f="{label}:"]')
                t0 = next(it for it in tagged if it["emotion"] == first)
                touched.append(t0["id"])
                other = [r for r in api["regions"] if r != t0["region"]][0]
                pg.click(f'figure[data-id="{t0["id"]}"] .tg[data-t="region"]')
                pg.wait_for_function(f"document.querySelector('figure[data-id=\"{t0['id']}\"] .tg[data-t=\"region\"]').textContent==='{other}'")
                check("지역 표시 누르면 바뀌고 저장", state().get(t0["id"], {}).get("region") == other, f'{t0["region"]}→{other}')

            # 지우기 → 휴지통
            vid = pg.query_selector("figure").get_attribute("data-id")
            touched.append(vid)
            pg.click(f'figure[data-id="{vid}"] button.del')
            pg.wait_for_function(f"!document.querySelector('figure[data-id=\"{vid}\"]')")
            c1 = counts()
            check("지우기: 그 탭 -1, 휴지통 +1", c1[first] == c0[first] - 1 and c1["휴지통"] == c0["휴지통"] + 1, f"{c0[first]}→{c1[first]}, 휴지통 {c0['휴지통']}→{c1['휴지통']}")
            check("지우기: state.json 저장", state().get(vid, {}).get("deleted") is True)
            pg.reload()
            pg.wait_for_selector("#tabs button")
            check("지우기: 새로고침해도 유지", counts() == c1)

            # 되살리기
            pg.click('#tabs button[data-cat="휴지통"]')
            pg.click(f'figure[data-id="{vid}"] button.rs')
            pg.wait_for_function(f"!document.querySelector('figure[data-id=\"{vid}\"]')")
            check("되살리기: 숫자 원복", counts() == c0)
            check("되살리기: state.json 저장", state().get(vid, {}).get("deleted") is False)

            # 한 개 이동
            dest = cats[-1]
            pg.click(f'#tabs button[data-cat="{first}"]')
            pg.select_option(f'figure[data-id="{vid}"] select.mv', dest)
            pg.wait_for_function(f"!document.querySelector('figure[data-id=\"{vid}\"]')")
            c2 = counts()
            check(f"이동: {first} -1, {dest} +1", c2[first] == c0[first] - 1 and c2[dest] == c0[dest] + 1, f"{c0[first]}→{c2[first]}, {c0[dest]}→{c2[dest]}")
            check("이동: state.json 저장", state().get(vid, {}).get("emotion") == dest)
            pg.reload()
            pg.wait_for_selector("#tabs button")
            pg.click(f'#tabs button[data-cat="{dest}"]')
            check("이동: 새로고침 뒤 옮긴 탭에 있음", pg.query_selector(f'figure[data-id="{vid}"]') is not None)

            # 묶음 이동(체크 2개)
            pg.click(f'#tabs button[data-cat="{first}"]')
            two = [f.get_attribute("data-id") for f in pg.query_selector_all("figure")[:2]]
            touched.extend(two)
            for i in two:
                pg.check(f'figure[data-id="{i}"] input')
            mid = cats[1]
            pg.select_option("#bulkmove", mid)
            pg.wait_for_function(f"!document.querySelector('figure[data-id=\"{two[0]}\"]')")
            c3 = counts()
            check(f"묶음 이동 2개: {first} -2, {mid} +2", c3[first] == c2[first] - 2 and c3[mid] == c2[mid] + 2, f"{c2[first]}→{c3[first]}, {c2[mid]}→{c3[mid]}")
            st = state()
            check("묶음 이동: state.json 저장", all(st.get(i, {}).get("emotion") == mid for i in two))

            # 묶음 지우기
            pg.click(f'#tabs button[data-cat="{mid}"]')
            for i in two:
                pg.check(f'figure[data-id="{i}"] input')
            pg.click("#bulkdel")
            pg.wait_for_function(f"!document.querySelector('figure[data-id=\"{two[0]}\"]')")
            c4 = counts()
            check("묶음 지우기 2개: 휴지통 +2", c4["휴지통"] == c3["휴지통"] + 2 and c4[mid] == c3[mid] - 2, f"휴지통 {c3['휴지통']}→{c4['휴지통']}")

            # 크게 보기
            pg.click("figure video")
            pg.wait_for_timeout(1500)
            big = pg.evaluate("(()=>{const b=document.getElementById('big');const v=b.querySelector('video');return [getComputedStyle(b).display,v.currentTime,v.muted];})()")
            check("클릭하면 크게·소리 켜짐", big[0] == "flex" and big[1] > 0 and big[2] is False, str(big))
            if shot:
                pg.mouse.click(5, 500)
                pg.wait_for_timeout(300)
                pg.screenshot(path=shot)
            br.close()
    finally:
        srv.terminate()
        # 검사가 건드린 영상만 원래 값으로 — 파일을 통째로 되돌리면 그 사이 사장님이 뷰어에서 누른 것이 날아간다
        old, cur = (json.loads(before) if before else {}), state()
        for i in touched:
            if i in old:
                cur[i] = old[i]
            else:
                cur.pop(i, None)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=1)
    print(f"실패 {len(fails)}건" + (": " + ", ".join(fails) if fails else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
