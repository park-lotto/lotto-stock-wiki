"""도우인(douyin.com) 영상 서버 다운로드 — 2026-08-16 서버 실측으로 확정한 유일한 경로.

왜 이 모양인가 (전부 서버 실측, 추측 아님):
- yt-dlp는 최신(2026.7.4)·master 둘 다 "Fresh cookies are needed"로 실패.
  playwright가 얻은 쿠키를 Netscape로 넘겨도 동일 실패(선행 세션 실측).
- 플레인 curl로 페이지를 받으면 2.4KB acrawler 챌린지 셸만 온다(SSR 없음).
- ★headless chromium으로 `https://www.douyin.com/discover?modal_id={id}`를 열면
  챌린지를 통과한 뒤 /jingxuan?modal_id= 로 리다이렉트되고, 그 페이지의 SSR 상태에
  이 영상의 playAddr 전 화질 목록(서명 포함 zjcdn CDN URL, URL인코딩)이 그대로 박혀 있다.
  (`/video/{id}` 직행은 로드 중 다른 곳으로 navigate돼 못 쓴다 — modal_id 경로만 된다)
- 그 URL을 Referer+UA 붙여 GET하면 서버(AWS IP)에서도 200으로 받아진다.
  실측: 1080x1920 h264/aac 50.5s 9.18MB, ffprobe 정상.

CDN URL엔 만료 서명이 있으므로 **뽑자마자 바로 받는다**(저장해두고 나중에 쓰지 않는다).

단독 실행(서브프로세스용): python -m shopping_shorts.douyin_fetch <url> <dest_dir>
→ 마지막 줄에 JSON {"path": "...mp4"} 출력. media_download가 서브프로세스로 부르는
이유: 호출부(FastAPI 백그라운드)가 asyncio 루프 위라 sync_playwright가 못 돈다.
"""
import json
import re
import subprocess
import sys
import urllib.parse
import uuid
from pathlib import Path

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# dataSize·해상도·playAddr src가 붙어 다니는 SSR JSON 조각(URL디코드 후 기준)
_PLAY_RE = re.compile(
    r'"dataSize":(\d+),"width":(\d+),"height":(\d+),"playAddr":\[\{"src":"(https://[^"]+)"')


def video_id_from_url(url):
    """douyin.com/video/{id} · iesdouyin share/video/{id} · modal_id={id} → id ("" if none)."""
    m = re.search(r"(?:/video/|modal_id=)(\d{5,})", url or "")
    return m.group(1) if m else ""


def _fetch_modal_html(vid, timeout_ms=45000):
    """headless chromium으로 modal_id 페이지 SSR HTML을 받아온다."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            ctx = b.new_context(user_agent=_UA, locale="zh-CN",
                                viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            page.goto(f"https://www.douyin.com/discover?modal_id={vid}",
                      wait_until="domcontentloaded", timeout=timeout_ms)
            # SSR 상태가 DOM에 내려앉을 시간. playAddr가 보이면 조기 종료.
            # ★acrawler 챌린지가 로드 중 페이지를 통째로 재네비게이션시키므로(서버 실측:
            #   "Unable to retrieve content because the page is navigating") content()가
            #   그 순간 던진다 — 실패로 치지 말고 다음 폴에서 다시 읽는다.
            html = ""
            for _ in range(15):
                try:
                    html = page.content()
                    if "playAddr" in urllib.parse.unquote(html)[:2_000_000]:
                        return html
                except Exception:  # noqa: BLE001 — 네비게이션 중 일시 오류
                    pass
                page.wait_for_timeout(1000)
            return html
        finally:
            b.close()


#: 우리 결과물 높이. 이 위는 렌더에서 어차피 버려지는 화소다(_normalize와 같은 기준).
_TARGET_H = 1920


def best_play_url(html):
    """SSR HTML → 받을 playAddr URL. 없으면 "".

    ★**최고 해상도가 아니라 '우리 규격에 맞는 것 중 최고'를 고른다**(2026-08-17 서버 실측).

    왜 바꿨나 — 도우인은 같은 영상을 여러 화질로 내놓는데, 그 목록에 **이미 1080x1920
    h264가 들어 있다.** 그런데 종전 코드는 무조건 최댓값을 골라 **2160x3840 hevc**를
    받아왔고, `_normalize()`가 그걸 다시 1080x1920 h264로 되돌리느라 **141초**를 썼다.
    즉 공짜로 받을 수 있는 결과물을 141초 들여 만들고 있었다(서버 4코어·GPU 없음).

    실측(54초 영상, `7662301406170830245` — SSR이 준 화질 목록):
        2160x3840 hevc 20.1MB  ← 종전 선택. 받은 뒤 변환 141초
        1440x2560       11.5MB
        1080x1920 h264 14.5MB  ← 지금 선택. 변환 0초(_normalize가 그대로 통과)
         720x1280 …

    화질 손해는 0이다 — 최종 렌더가 1080x1920이라 그 위는 어차피 버린다.
    2160만 있는(=1920 이하가 하나도 없는) 영상은 종전대로 최댓값을 받아 `_normalize`가
    변환한다 → 받지 못하는 영상은 생기지 않는다(회귀 0).
    """
    best_fit = None      # 높이 <= _TARGET_H 중 최고 (변환 없이 바로 쓸 후보)
    best_any = None      # 전체 최고 (위가 하나도 없을 때의 폴백)
    for m in _PLAY_RE.finditer(urllib.parse.unquote(html)):
        size, w, h, src = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        key = (w * h, size)
        if best_any is None or key > best_any[0]:
            best_any = (key, src)
        if h <= _TARGET_H and (best_fit is None or key > best_fit[0]):
            best_fit = (key, src)
    chosen = best_fit or best_any
    return chosen[1] if chosen else ""


def download(url, dest_dir):
    """도우인 페이지 URL → dest_dir/{uuid}.mp4 경로. 실패 시 RuntimeError."""
    import requests
    vid = video_id_from_url(url)
    if not vid:
        raise RuntimeError(f"도우인 영상 ID를 URL에서 못 찾음: {url}")
    html = _fetch_modal_html(vid)
    play = best_play_url(html)
    if not play:
        raise RuntimeError(
            f"도우인 SSR에서 playAddr를 못 찾음(챌린지 통과 실패 가능): {url}")
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{uuid.uuid4().hex[:8]}.mp4"
    r = requests.get(play, stream=True, timeout=120,
                     headers={"User-Agent": _UA, "Referer": "https://www.douyin.com/"})
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    if path.stat().st_size < 50_000:   # 챌린지 HTML 등 쓰레기 응답 방지
        raise RuntimeError(f"도우인 다운로드 산출물이 비정상적으로 작음({path.stat().st_size}B)")
    return _normalize(path)


def _normalize(path):
    """도우인 원본 → 우리 파이프라인이 안심하고 쓸 수 있는 mp4로 맞춘다.

    ★왜 필요한가(2026-08-16 실측): 도우인이 주는 최고화질은 **hevc(H.265) 2160x2880**이었다.
      · hevc는 **크롬에서 재생될 수도, 안 될 수도 있다** — OS·하드웨어 지원에 달렸다.
        고객마다 갈리는 성질이라, 어떤 고객은 3단계 장면 편집에서 화면이 통째로 검게 뜬다.
      · 2160x2880은 세로 4K다. 우리 결과물은 1080x1920이라 그 위는 버려지는 화소인데
        미리보기·편집 내내 그 무게를 브라우저가 진다(이 파일로 실제 브라우저가 두 번 얼었다).
    그래서 **h264 + 높이 1920 상한**으로 맞춘다. 화질 손해는 결과물 기준으로 0이다
    (어차피 1080x1920으로 렌더된다).

    ffmpeg가 없거나 변환이 실패하면 **원본을 그대로 쓴다** — 받아 온 것을 잃지 않는다.
    """
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,height", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=60)
        info = (probe.stdout or "").strip().split(",")
        codec = info[0] if info else ""
        height = int(info[1]) if len(info) > 1 and info[1].isdigit() else 0
    except Exception:  # noqa: BLE001 — ffprobe가 없으면 손대지 않는다
        return str(path)
    if codec == "h264" and height <= 1920:
        return str(path)                      # 이미 안전한 모양이면 그대로
    out = path.with_name(path.stem + "_h264.mp4")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path),
             "-vf", "scale=-2:'min(1920,ih)'", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", str(out)],
            capture_output=True, text=True, timeout=600, check=True)
    except Exception:  # noqa: BLE001 — 변환 실패는 치명적이지 않다(원본으로 간다)
        out.unlink(missing_ok=True)
        return str(path)
    if not out.exists() or out.stat().st_size < 10000:
        out.unlink(missing_ok=True)
        return str(path)
    path.unlink(missing_ok=True)
    return str(out)


def main():
    url, dest_dir = sys.argv[1], sys.argv[2]
    path = download(url, dest_dir)
    print(json.dumps({"path": path}))


if __name__ == "__main__":
    main()
