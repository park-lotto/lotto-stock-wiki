# -*- coding: utf-8 -*-
"""뇌전구 전용 단계 — prompts(그림 지시) · images(생성+검수 재시도) · frames(프레임 합성).
channelkit.pipeline 은 spec.STEP_HANDLERS 로 여기를 부른다. 계약: fn(job, d, wd, kw) -> None | 응답 dict.
본문은 2026-09-25 channelkit/pipeline.py 에서 글자 그대로 옮겼다(동작 변경 없음).
끝의 `_invalidate_after(job, <단계>)` 는 pipeline 핸들러 분기가 None 반환 뒤 대신 부른다.
"""
# ★import는 전부 함수 안에서 한다 — 이 모듈은 brainbulb.spec 맨 아래에서 불리는데,
#   맨 위에서 channelkit.pipeline·images를 부르면 prompt→lint가 모듈 로드 중에 spec 값을 읽고
#   → registry가 brainbulb.spec을 다시 부르고 → 반쯤 만든 이 모듈에서 HANDLERS를 못 찾는다
#   (실측 2026-09-25: `import ...brainbulb.steps`를 맨 먼저 하면 AttributeError: partially initialized).


def prompts(job, d, wd, kw):
    from . import images as _images
    llm, imagegen, log = kw["llm"], kw["imagegen"], kw["log"]
    if llm is None or imagegen is None:
        d["prompts"] = {"skipped": True, "why": "llm 또는 imagegen 없음 — 사진 없이(검은 슬롯) 진행"}
    else:
        s = dict(d["script"]["script"]); s["groups"] = d["layout"]["groups"]
        d["prompts"] = _images.make_prompts(s, d["setup"]["source_text"], llm, log=log)


def images(job, d, wd, kw):
    from shopping_shorts.channelkit import spec, pipeline as _pl
    from . import images as _images, photocheck as _photocheck
    imagegen, reviewer, log = kw["imagegen"], kw["reviewer"], kw["log"]
    if d["prompts"].get("skipped") or imagegen is None:
        d["images"] = {"files": {}, "skipped": True}
    else:
        files = _images.generate_all(d["prompts"]["prompts"], wd, imagegen,
                                     sources=d["prompts"].get("sources"), log=log)
        # ★만든 그림을 **실제로 보고** 판정한다 — 프롬프트 낱말 차단은 계속 샌다
        #   (실측 2026-09-13: computer screen을 막으니 digital sign으로, 그걸 막으니 또 다른
        #    표현으로 나왔다. 검수는 «종합주가지수 -2,886.83 신한투자증권»을 읽어내 반려했다).
        #   볼케이노도 같은 구조다 — review_policy={"provider":"client"}.
        if reviewer is not None:
            topic = ((d["script"]["script"].get("title") or {}).get("h1") or "")
            searched = _images.searched_map(files)   # 「검색 진짜 됐나」 — 기록만 한다
            subs = _pl._subtitles_by_slot(d["script"]["script"])
            # ★그 자리에 **무엇을 넣으려 했는지**도 함께 보낸다 — 이게 없으면 검수가
            #   사진만 보고 "사람이 말하고 있으니 말이 되네" 하고 넘긴다
            #   (실측 2026-09-14: 검색어 「1980년대 어음 용지」 자리에 한복 할머니
            #    인터뷰 캡처가 왔는데 matches_subtitle=true 로 통과했다).
            wants = {}
            for k, s in (d["prompts"].get("sources") or {}).items():
                q = (s or {}).get("query") or ""
                wants[str(k)] = f"검색: {q}" if q else "생성 이미지"
            # ★반려 → 사유를 붙여 다시 만들기를 **최대 PHOTO_RETRY_MAX 회** 반복한다
            #   (2026-09-16 사장님 지시). 종전엔 한 번 다시 만들고 그 결과가
            #   좋든 나쁘든 그냥 다음 단계로 갔다 — 재생성분이 또 틀려도 아무도 안 봤다.
            rounds = []
            chk = _photocheck.check(files, subs, reviewer=reviewer, log=log, wants=wants,
                                    topic=topic, searched=searched)
            for n in range(spec.PHOTO_RETRY_MAX):
                if not chk["retry"]:
                    break
                reasons = {r["slot"]: _photocheck.fail_reason(r["review"])
                           for r in chk["reviewed"] if r.get("review", {}).get("failed")}
                rounds.append({"round": n + 1, "retry": list(chk["retry"]),
                               "reasons": reasons})
                log(f"[brainbulb.images] 재시도 {n + 1}/{spec.PHOTO_RETRY_MAX} — 슬롯 {chk['retry']}")
                files = _images.regenerate(chk["retry"], d["prompts"]["prompts"], wd,
                                           imagegen, files, log=log, reasons=reasons)
                chk = _photocheck.check({k: files[k] for k in chk["retry"] if k in files},
                                        subs, reviewer=reviewer, log=log, wants=wants,
                                        topic=topic, searched=searched)
            chk["rounds"] = rounds
            chk["unresolved"] = list(chk["retry"])   # 끝까지 못 고친 슬롯 — 기록에 남긴다
            if chk["unresolved"]:
                log(f"[brainbulb.images] ★{spec.PHOTO_RETRY_MAX}회에도 못 고친 슬롯: {chk['unresolved']}"
                    f" — 그대로 쓴다(편을 멈추지 않는다)")
            d["photo_check"] = chk
        d["images"] = {"files": files}


def frames(job, d, wd, kw):
    from shopping_shorts.channelkit import frames as _frames
    meme_dir, log = kw["meme_dir"], kw["log"]
    s = dict(d["script"]["script"]); s["groups"] = d["layout"]["groups"]
    d["frames"] = _frames.build(wd, d["timing"], s, d["images"]["files"], meme_dir=meme_dir, log=log,
                                card_img=d["script"]["script"].get("card_img"))


HANDLERS = {"prompts": prompts, "images": images, "frames": frames}
