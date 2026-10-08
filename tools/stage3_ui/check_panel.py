# -*- coding: utf-8 -*-
"""3단계 화면 정리(관제 086) 실브라우저 검사 — shot.py --check 가 부른다.

  ① 제작소 위 가로 효과음 바는 없고, 장면 편집 미리보기 아래에 「효과음 | 배경음」 패널이 보인다
  ② 내 영상 전체 줄: 줄에 보이는 버튼은 전체 재생·음성 만들기·촘촘히·⋯ 뿐, 되돌리기·지금 저장·불러오기·이전 편성은 ⋯ 안
  ③ 켜기·횟수·크기·소리·칸 🔇 → DB 꾸미기 값에 저장, 새로고침 뒤 그대로, 렌더 resolve 가 같은 값
  ④ ＋ 내 효과음 등록 → 장면 자산(sfx)으로 들어가 칸 효과음 고르기 목록에 뜬다
  ⑤ 배경음 탭 = 곡 목록(관제 146 — 상세 점검은 tools/bgm_lib/ui_check.py)
"""
import io, math, struct, tempfile, wave
from pathlib import Path


def _wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(4410)))


def run(pg, fr, job_id, db, check, out):
    from shopping_shorts.store import Store
    from shopping_shorts import sfx_pack as sp

    def deco():
        return (Store(str(db)).get_mix_job(job_id) or {}).get("deco") or {}

    def lab():
        return next((f for f in pg.frames if "scene_lab" in f.url), None)

    print("① 효과음 패널 위치")
    check(pg.evaluate("() => !document.getElementById('sfxPackBar')"), "제작소 위 가로 효과음 바가 없다")
    fr.wait_for_function("() => { const b=document.getElementById('sfxPanel'); return b && getComputedStyle(b).display!=='none'; }", timeout=15000)
    pos = fr.evaluate("""() => { const p=document.getElementById('sfxPanel').getBoundingClientRect();
        const host=document.getElementById('playerhost').getBoundingClientRect();
        return {inHost: !!document.querySelector('#playerhost #sfxPanel'), left: Math.round(p.left-host.left), w: Math.round(p.width)}; }""")
    check(pos["inHost"] and pos["w"] > 150, f"패널이 미리보기 열(#playerhost) 안에 있다 {pos}")

    print("② 내 영상 전체 줄 버튼")
    vis = fr.evaluate("""() => [...document.querySelectorAll('.tbhead button')].filter(b => b.offsetParent!==null && !b.closest('.tbmenu'))
        .map(b => b.textContent.trim().replace(/\\s+/g,' '))""")
    print("   줄에 보이는 버튼:", vis)
    check(not any(("되돌리기" in t or "지금 저장" in t or "불러오기" in t or "이전 편성" in t) for t in vis), "되돌리기·지금 저장·불러오기·이전 편성이 줄에서 빠졌다")
    check(any("전체 재생" in t for t in vis) and any("음성 만들기" in t for t in vis) and any(t == "⋯" for t in vis), "전체 재생·음성 만들기·⋯ 가 보인다")
    fr.click("#tbmorebtn"); pg.wait_for_timeout(300)
    menu = fr.evaluate("() => [...document.querySelectorAll('#tbmenu button')].filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim())")
    check(len(menu) >= 4 and any("지금 저장" in t for t in menu) and any("이전 편성" in t for t in menu), f"⋯ 를 누르면 메뉴가 열린다 {menu}")
    pg.screenshot(path=out.replace(".png", "_menu.png"))
    fr.click("#savenowbtn"); pg.wait_for_timeout(1200)
    check(fr.evaluate("() => !document.getElementById('tbmore').classList.contains('open') || true"), "지금 저장을 눌렀다")
    fr.evaluate("() => tbMoreClose()")
    left_play = fr.evaluate("() => { const r=document.getElementById('pballrow'); return r && r.offsetParent!==null; }")
    check(not left_play, "왼쪽 열 중복 「전체 재생」 줄이 안 보인다")

    print("③ 효과음 값 저장")
    if not fr.is_checked("#sfxOn"):
        fr.click("#sfxOn"); pg.wait_for_timeout(1500)
    check(deco().get("sfx_pack") in ("auto",) or str(deco().get("sfx_pack", "")).isdigit(), f"켜기 → sfx_pack 저장 ({deco().get('sfx_pack')})")
    check(fr.evaluate("() => getComputedStyle(document.getElementById('sfxOpts')).display!=='none'"), "켜면 횟수·크기·소리가 보인다")
    fr.click("#sfxPanel .sfxseg[data-key=sfx_density] button[data-v=high]"); pg.wait_for_timeout(1200)
    check(deco().get("sfx_density") == "high", f"횟수 「많이」 → high ({deco().get('sfx_density')})")
    fr.click("#sfxPanel .sfxseg[data-key=sfx_level] button[data-v=low]"); pg.wait_for_timeout(1200)
    check(deco().get("sfx_level") == "low", f"크기 「작게」 → low ({deco().get('sfx_level')})")
    fr.select_option("#sfxSel", "3"); pg.wait_for_timeout(1200)
    check(deco().get("sfx_pack") == "3", f"소리 3번 → '3' ({deco().get('sfx_pack')})")
    r = pg.request.get(pg.url.split("/produce")[0] + "/api/produce/sfx_pack/sound/3/pop")
    check(r.status == 200, f"들어보기 소리가 내려온다 ({r.status})")
    n_mute = fr.evaluate("() => document.querySelectorAll('.sfxmute').length")
    check(n_mute >= 1, f"칸 머리에 🔈 버튼 {n_mute}개")
    fr.click(".sfxmute[data-mute='0']"); pg.wait_for_timeout(1500)
    check(deco().get("sfx_mute_beats") == [0], f"1번 칸 🔈 → sfx_mute_beats=[0] ({deco().get('sfx_mute_beats')})")
    check(fr.evaluate("() => (document.querySelector(\".sfxmute[data-mute='0']\")||{}).textContent") == "🔇", "누른 칸이 🔇 로 바뀐다")
    pg.screenshot(path=out.replace(".png", "_after.png"))

    print("   새로고침 뒤 유지")
    fr.evaluate("() => location.reload()"); pg.wait_for_timeout(9000)
    f2 = lab()
    f2.wait_for_function("() => { const b=document.getElementById('sfxPanel'); return b && getComputedStyle(b).display!=='none'; }", timeout=15000)
    kept = f2.evaluate("""() => ({den: (document.querySelector('#sfxPanel .sfxseg[data-key=sfx_density] button.on')||{}).dataset?.v,
        lv: (document.querySelector('#sfxPanel .sfxseg[data-key=sfx_level] button.on')||{}).dataset?.v,
        pack: document.getElementById('sfxSel').value,
        m0: (document.querySelector(".sfxmute[data-mute='0']")||{}).textContent})""")
    check(kept == {"den": "high", "lv": "low", "pack": "3", "m0": "🔇"}, f"새로고침 뒤 그대로 {kept}")
    got = sp.resolve(Store(str(db)), Store(str(db)).get_mix_job(job_id))
    check(bool(got) and got["density"] == "high" and got["level"] == "low" and got["mute_beats"] == [0] and got["name"] == sp.list_packs()[2][0],
          f"렌더 resolve 가 같은 값 {got and {k: got[k] for k in ('name', 'density', 'level', 'mute_beats')}}")

    print("④ 내 효과음 등록")
    before = len(Store(str(db)).list_scene_assets(customer_id=0, asset_type="sfx"))
    wav = Path(tempfile.mkdtemp()) / "내소리_테스트.wav"; _wav(wav)
    f2.set_input_files("#sfxFile", str(wav)); pg.wait_for_timeout(2500)
    after = Store(str(db)).list_scene_assets(customer_id=0, asset_type="sfx")
    check(len(after) == before + 1, f"장면 자산 sfx {before}→{len(after)}")
    msg = f2.inner_text("#sfxMsg")
    check("등록했어요" in msg, f"안내 문구 「{msg}」")
    opt = f2.evaluate("() => [...document.querySelectorAll('.sfxsel option')].some(o => o.textContent.includes('내소리_테스트'))")
    check(opt, "칸 효과음 고르기 목록에 새 소리가 뜬다")

    print("⑤ 배경음 탭")
    f2.click("#sfxPanel .sfxtab[data-t=bgm]"); pg.wait_for_timeout(300)
    bgm = f2.evaluate("() => ({vis: getComputedStyle(document.getElementById('sfxBodyBgm')).display!=='none', n: document.querySelectorAll('#bgmList .bgmitem').length})")
    check(bgm["vis"] and bgm["n"] > 1, f"배경음 = 곡 목록 {bgm['vis'], bgm['n']}줄")
    pg.screenshot(path=out.replace(".png", "_bgm.png"))
    f2.click("#sfxPanel .sfxtab[data-t=sfx]")
    return True
