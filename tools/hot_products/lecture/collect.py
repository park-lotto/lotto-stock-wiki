"""강의 영상 수집 — 네이버·쿠팡 상품/키워드 발굴 강의를 유튜브 검색어 여러 개로 모은다(키 불필요, yt-dlp).
실행: py -I collect.py  → videos.json (id·제목·채널·조회수·길이·찾은 검색어)"""
import json, os, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
QUERIES = [
    # 네이버
    "네이버 황금키워드 찾는법", "스마트스토어 키워드 분석", "스마트스토어 잘팔리는 상품 찾기", "네이버 쇼핑 키워드 찾기",
    "네이버 데이터랩 쇼핑인사이트 활용", "네이버 데이터랩 시즌 상품", "아이템스카우트 사용법", "아이템스카우트 키워드",
    "판다랭크 사용법", "셀러라이프 키워드", "블랙키위 키워드 분석", "네이버 검색광고 키워드도구 활용",
    "스마트스토어 시즌상품 미리 준비", "스마트스토어 대박 상품 찾는 방법",
    # 쿠팡
    "쿠팡 잘팔리는 상품 찾는법", "쿠팡 키워드 찾기", "쿠팡 소싱 아이템 찾기", "쿠팡 판매량 확인 방법",
    "쿠팡 로켓그로스 상품 선정", "쿠팡 위탁판매 상품 찾기", "쿠팡 파트너스 상품 선정", "쿠팡파트너스 쇼츠 상품 찾기",
    # 바이럴·시즌
    "바이럴 키워드 찾는법", "떡상 키워드 찾기", "급상승 키워드 상품", "트렌드 상품 찾는법 2026",
    "시즌 상품 키워드 찾기", "쇼핑쇼츠 상품 찾는법", "쇼핑쇼츠 키워드", "인스타 공구 아이템 찾기",
]
out = {}
path = os.path.join(HERE, "videos.json")
if os.path.exists(path):
    out = json.load(open(path, encoding="utf-8"))
for q in QUERIES:
    try:
        p = subprocess.run(["py", "-m", "yt_dlp", f"ytsearch25:{q}", "--flat-playlist", "--print",
                            "%(id)s\t%(view_count)s\t%(duration)s\t%(channel)s\t%(title)s"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))   # 윈도우 콘솔 cp949 출력 → 디코딩 실패 방지
    except Exception as e:
        print("ERR", q, e); continue
    n = 0
    for line in p.stdout.splitlines():
        f = line.split("\t", 4)
        if len(f) < 5: continue
        vid, views, dur, ch, title = f
        rec = out.setdefault(vid, {"id": vid, "title": title, "channel": ch,
                                   "views": int(views) if views.isdigit() else 0,
                                   "duration": int(float(dur)) if dur not in ("NA", "None", "") else 0, "queries": []})
        if q not in rec["queries"]: rec["queries"].append(q)
        n += 1
    print(f"{q}: {n}개 (누적 {len(out)})", flush=True)
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    time.sleep(1.5)
# 강의다운 것만: 4~90분, 조회수 3천+
keep = [v for v in out.values() if 240 <= v["duration"] <= 5400 and v["views"] >= 3000]
print("전체", len(out), "→ 강의 후보(4~90분·조회 3천+)", len(keep))
