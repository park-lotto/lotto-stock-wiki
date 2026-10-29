# -*- coding: utf-8 -*-
"""카드뉴스 이미지 조달 — **정본 조달기를 그대로 쓴다.** 새로 짜지 않는다.

■ 처음에 틀렸던 것 (2026-08-17, 실측으로 잡았다)
    이 파일의 1차 판은 볼케이노 앱(네이티브 런타임)의 **로컬 HTTP 엔드포인트**를
    부르게 돼 있었다 — `/api/browser-google-search` 같은 것들. 코드에 그 라우트가
    있는 것은 사실이지만(`server.rs:1491·1525·1557`), **앱을 실제로 켜서 재 보니
    그 HTTP 서버가 안 뜬다.** 켠 뒤 열린 포트는 `9879` 하나였고 그것은
    `{"ok":true,"service":"tunnel-serve","port":9879}` 였다. 게다가 후보 목록
    (`legacyLoopbackUrl.ts:19`)에는 9879 가 **아예 없다**(9878 다음이 9882 다).
    즉 그 길로는 못 간다.

    그리고 **정답은 이미 저장소 안에 있었다** — `volcano_run.fetch_images` 가
    전용 프로필 크롬을 CDP 로 몰아 그림을 받는다. 앱이 꺼져 있어도 돌고,
    로그인·키·비용이 0 이며, 워터마크 도메인 차단·속도 제한·재시도 정책·
    같은 그림 재사용 방지까지 이미 들어 있다(2026-08-16 이관에서 고친 것들).

    §4 *"옮겨 적을 때는 호출부까지 읽어라"* 를 내가 어긴 자리다. 있는 것을 안 보고
    새로 만들었고, 그 새 길은 실제로 막혀 있었다.

■ 그래서 이 파일이 하는 일은 둘뿐이다
    ① 서버가 준 카드 계획을 `fetch_images` 가 먹는 **job 모양**으로 바꾼다
    ② 무료로 한 장도 못 구했을 때만 **유료 생성**으로 물러난다 (사용자 본인 키)

    검색어도 소스도 **서버가 정한다.** 실행기는 던지고 받아 저장할 뿐이다.
"""

import json
import os
import time
import urllib.error
import urllib.request


class ImageError(RuntimeError):
    """조달 실패. 사유는 사람이 읽을 말로."""


# ── 무료 조달 (정본 위임) ───────────────────────────────────


def build_jobs(plan, outdir):
    """서버 계획 → `volcano_run.fetch_images` 가 먹는 job 목록.

    ★job 의 칸 이름을 여기서 지어내지 않는다. 정본이 읽는 이름 그대로다 —
      `index · out · queries · sources · min_px · deny_domains ·
       prefer_domains · low_signal_domains`."""
    jobs = []
    for card in plan.get("cards") or []:
        queries = [q for q in (card.get("queries") or [card.get("query")]) if q]
        if not queries:
            continue
        idx = int(card["index"])
        jobs.append({
            "index": idx,
            "out": os.path.join(outdir, f"card_{idx:02d}.jpg"),
            "queries": queries,
            # 소스도 서버가 준다 — 러너에 박으면 서버가 고쳐도 안 따라온다
            "sources": plan.get("sources") or [],
            "min_px": int(plan.get("min_px") or 600),
            "deny_domains": plan.get("deny_domains") or [],
            "prefer_domains": plan.get("prefer_domains") or [],
            "low_signal_domains": plan.get("low_signal_domains") or [],
        })
    return jobs


def harvest(plan, outdir):
    """카드별 그림을 채운다. 무료 → (필요하면) 유료 순서다.

    ★정본 `fetch_images` 는 **한 장이라도 못 구하면 멈춘다** — 빈 컷을 다른
      그림으로 메우면 그 컷만 조용히 틀린 화면이 되기 때문이다(영상 쪽 교훈).
      카드뉴스는 사정이 다르다: 사진이 없으면 **색면 배경**이라는 설계된 갈래가
      있다(정본 주석: 고정 검정이던 시절 사용자가 '고장난 화면' 으로 읽었다).
      그래서 카드마다 따로 부르고, 못 구한 것은 **그대로 보고한다** —
      서버가 그 카드를 색면으로 그리라고 지시한다.
    """
    import volcano_run                                            # noqa: PLC0415

    # ★숫자를 여기 박지 않는다. `retry`·`min_bytes` 는 **명세 값**이고, 러너에
    #   기본값을 두면 서버가 고쳐도 안 따라온다. 검사 [명세 숫자가 배급 코드에
    #   박혀 있지 않다] 가 실제로 잡았다 — 기본값을 달아 뒀었다.
    #   ★그 숫자를 이 주석에 다시 적지 마라. 검사는 문자열이 아니라 **값**을 보고,
    #     주석에 적힌 값도 똑같이 잡는다(저장소가 이미 겪은 부류다).
    retry = int(plan.get("retry") or 0)
    min_bytes = int(plan.get("min_bytes") or 0)
    if not retry or not min_bytes:
        raise ImageError("조달 계획에 retry·min_bytes 가 없습니다 — 서버가 주는 값입니다.")

    # ★배경으로 못 쓰는 그림을 거르는 선도 **서버가 준다**. 없으면 안 거른다 —
    #   러너가 기본값을 지어내면 서버가 고쳐도 안 따라온다.
    max_white = plan.get("max_white")

    os.makedirs(outdir, exist_ok=True)
    # ★구글 이미지(agy · 10-08) — 영수증 자리(cache_dir)는 이 PC 의 산출 폴더 아래다. 서버는 이 PC 의 경로를 모른다.
    #   같은 검색어는 영수증을 다시 쓴다(구독 한도를 아낀다 · `volcano_run._agy_google_path`).
    plan = dict(plan)
    plan["sources"] = [dict(s, cache_dir=s.get("cache_dir") or os.path.join(outdir, "_agy_google"))
                       if str(s.get("kind") or "").lower() == "agy_google" else s
                       for s in (plan.get("sources") or [])]
    jobs = build_jobs(plan, outdir)
    got, notes = {}, []
    if jobs and any(str(s.get("kind") or "").lower() == "agy_google" for s in plan["sources"]):
        # 카드마다 agy 를 줄 세우지 않고(한 번 30~40초) 첫 검색어를 모아 **동시에** 먼저 찾는다 — 인물형과 같은 부품.
        try:
            volcano_run.agy_google_plan_prefetch(jobs, tuple(plan.get("backoff") or ()), float(plan.get("pace") or 0.0))
        except volcano_run.PhotoSourceError as e:
            notes.append(f"구글 사진(agy) 미리 찾기를 못 했습니다 — 다음 출처로 갑니다: {str(e).splitlines()[0][:120]}")
    if jobs and plan.get("sources"):
        for job in jobs:
            try:
                res = volcano_run.fetch_images(
                    [job], retry=retry, min_bytes=min_bytes,
                    pace=float(plan.get("pace") or 0.0),
                    backoff=tuple(plan.get("backoff") or ()),
                    headers=plan.get("headers"),
                    retry_policy=plan.get("retry_policy"))
                if job["index"] in res:
                    # ★받은 뒤에 **배경으로 쓸 수 있는 그림인지** 본다.
                    #   차트·고지서 스캔·앱 화면은 크고 허용 도메인이라
                    #   min_px·deny_domains 로는 안 걸린다(2026-08-17 실측:
                    #   4장 중 3장이 그랬다). 걸리면 **못 구한 것으로 본다** —
                    #   그 카드는 색면 배경으로 그려진다(설계된 갈래다).
                    w = white_ratio(job["out"]) if max_white else None
                    if w is not None and w > float(max_white):
                        notes.append(f"{job['index']}번 카드: 배경으로 쓰기 어려운 "
                                     f"그림이라 뺐습니다(흰 바탕 비율 {w:.2f}) — "
                                     "차트·문서 스캔·앱 화면일 수 있습니다.")
                        try:
                            os.remove(job["out"])
                        except OSError:
                            pass
                    else:
                        got[job["index"]] = {"path": job["out"], "source": "search",
                                             "size": res[job["index"]]}
            except Exception as e:                                # noqa: BLE001
                notes.append(f"{job['index']}번 카드: {str(e).splitlines()[0][:110]}")
    elif jobs:
        notes.append("검색 소스가 없어 무료 조달을 건너뜁니다 (색면 배경으로 그립니다).")

    paid_count = 0
    paid = plan.get("paid")
    if paid:
        for card in plan.get("cards") or []:
            idx = int(card["index"])
            if idx in got:
                continue
            try:
                # ★서버가 준 말꼬리를 그대로 붙인다. 안 붙이면 그림 레퍼런스인데
                #   사진풍이 나온다. ★그 낱말을 여기 적지 마라 — 명세에서 오는 값이고,
                #   베껴 적으면 서버가 바꿔도 안 따라오며 검사 [20] 에 걸린다(실제로 걸렸다).
                prompt = card.get("bgPrompt") or (card.get("query") or "")
                if paid.get("styleSuffix"):
                    prompt = f"{prompt}, {paid['styleSuffix']}"
                urls = generate_gpt_image2(
                    prompt,
                    paid.get("apiKey"),
                    size=paid.get("size") or "2:3",
                    quality=paid.get("quality"),
                    base_url=paid.get("baseUrl") or "https://api.evolink.ai")
                out = os.path.join(outdir, f"card_{idx:02d}.jpg")
                download(urls[0], out)
                got[idx] = {"path": out, "source": "gpt-image-2"}
                paid_count += 1
            except Exception as e:                                # noqa: BLE001
                notes.append(f"{idx}번 카드 생성 실패: {str(e)[:110]}")

    return {"images": got, "paidCount": paid_count, "notes": notes}


def white_ratio(path):
    """흰 화소 비율(0~1). 못 읽으면 **None** — 못 잰 것을 0 으로 치지 않는다.

    ★작게 줄여서 센다. 원본 그대로 세면 4608×6912 한 장에 3천만 화소다.
      줄여도 배경이 흰지 아닌지는 그대로 보인다(실측에서 같은 값이 나왔다)."""
    try:
        from PIL import Image                                      # noqa: PLC0415
    except ImportError:
        return None
    try:
        im = Image.open(path).convert("RGB")
        im.thumbnail((220, 220))
        px = list(im.getdata())
    except Exception:                                              # noqa: BLE001
        return None
    if not px:
        return None
    n = sum(1 for r, g, b in px if r >= 225 and g >= 225 and b >= 225)
    return n / len(px)


# ── 유료 (마지막 수단) ──────────────────────────────────────


def generate_gpt_image2(prompt, api_key, size="2:3", quality=None,
                        base_url="https://api.evolink.ai",
                        poll_max=120, poll_sec=3):
    """GPT Image 2 — **사용자 본인 키**로 나간다.

    ★화질은 `low`/`medium`/`high` 뿐이다. 다른 값을 보내면 공급자가 400 으로
      **직접 그렇게 답한다**(`invalid quality parameter: 2K (gpt-image-2 only
      supports quality=[low medium high])`). 서버가 미리 막지만 여기서도 안 지어낸다.

    ★실단가(2026-08-17 · size 2:3 · 각 1회 · `usage.cost` 원문):
        low $0.0037(출력토큰 134·16초) · medium $0.0320(1,167·28초) ·
        high $0.1270(4,667·82초) — low 가 high 보다 **34배** 싸다.
      앱 상수 `EVOLINK_GPT_IMAGE_2_PER_IMAGE = 0.020` 은 등급을 **안 보낼 때**의 값이다.

    ★4:5 는 지원 목록에 없다(auto/1:1/16:9/9:16/3:2/2:3) → 2:3 으로 받아 중앙 크롭한다.
    ★기본값을 여기 두지 않는다 — 서버가 정한 값을 그대로 싣는다."""
    if not api_key:
        raise ImageError("이미지 생성 키가 없습니다.")
    body = {"model": "gpt-image-2", "prompt": prompt, "size": size}
    if quality:
        body["quality"] = quality
    req = urllib.request.Request(
        f"{base_url}/v1/images/generations", method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            created = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # ★4xx 는 사람이 고칠 일이다 — 되풀이하지 않는다.
        #   429·403 에 되풀이하는 것이 어뷰징 신호이고, 실제로 그것 때문에
        #   수강생 구글 계정 5개가 정지됐다(2026-08-15).
        raise ImageError(f"이미지 생성 실패 HTTP {e.code}: "
                         f"{e.read().decode('utf-8', 'replace')[:200]}")

    task_id = created.get("id") or created.get("task_id")
    if not task_id:
        urls = _extract_urls(created)
        if urls:
            return urls
        raise ImageError(f"응답에 작업 id 가 없습니다: {str(created)[:200]}")

    for _ in range(poll_max):
        time.sleep(poll_sec)
        with urllib.request.urlopen(urllib.request.Request(
                f"{base_url}/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"}), timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        state = str(data.get("status") or data.get("state") or "").lower()
        if state in ("completed", "succeeded", "success"):
            urls = _extract_urls(data)
            if urls:
                return urls
            raise ImageError("완료라는데 이미지 주소가 없습니다.")
        if state in ("failed", "error"):
            raise ImageError(f"이미지 생성 실패: {data.get('fail_reason') or state}")
    raise ImageError("이미지 생성이 시간 안에 끝나지 않았습니다.")


def _extract_urls(payload):
    """응답에서 이미지 주소를 긁는다.

    ★키 이름이 공급자마다 다르다 — `data` 하나만 보다가 완료 응답을 못 읽어
      **이미 과금된 작업 8건이 버려질 뻔한 사고**가 있었다(앱, 2026-08-11).
      실측 응답은 `results` / `result_data` 에 들어온다."""
    out = []
    for key in ("results", "result_data", "data", "images", "image_urls", "output"):
        v = payload.get(key)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str) and item.startswith("http"):
                    out.append(item)
                elif isinstance(item, dict):
                    for k in ("url", "image_url"):
                        if isinstance(item.get(k), str) and item[k].startswith("http"):
                            out.append(item[k])
        elif isinstance(v, dict):
            out.extend(_extract_urls(v))
    return out


def download(url, path, timeout=90, min_bytes=1024):
    """이미지 한 장 저장. 너무 작으면 실패로 본다 — 0바이트·오류 페이지 방어."""
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if len(raw) < min_bytes:
        raise ImageError(f"이미지가 너무 작습니다({len(raw)}B): {url[:80]}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(raw)
    return path
