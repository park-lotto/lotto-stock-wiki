# -*- coding: utf-8 -*-
"""이미지 — ① 슬롯별 영문 프롬프트+cast(LLM) ② EvoLink gpt-image-2 생성(과금) ③ 다운로드.

호출 형식은 볼케이노 실행기 `cardnews_images.generate_gpt_image2`와 같다(POST /v1/images/generations → 작업 id → /v1/tasks/{id} 폴링).
프롬프트 형식은 실제 편 payload.prompts 를 따른다: 접두(다큐 사진·한국) + cast(인물 인상착의 고정) + 장면.
생성기는 주입한다(imagegen(prompt, out_path) -> None) — 테스트는 단색 PNG를 만드는 가짜로 돈다.
"""
import hashlib
import json
import os
import time

import requests

from . import spec, prompt as _prompt


def build_prompt_request(script, source_text):
    slots = sorted({g["img"] for g in script["groups"] if isinstance(g.get("img"), int)})
    cuts = "\n".join(f"- 슬롯 {g['img']}: 컷{i + 1} «{g['text']}»" for i, g in enumerate(script["groups"]) if isinstance(g.get("img"), int))
    return (
        "너는 뇌전구 채널의 이미지 디렉터다. 아래 대본의 이미지 슬롯마다 **영문** 생성 프롬프트를 쓴다.\n"
        "규칙:\n"
        "- cast: 등장 인물마다 인상착의를 한 문장으로 고정해 모든 슬롯에 같은 문구를 그대로 쓴다(컷 간 같은 인물로 나오게). 실명·유명인 이름은 쓰지 말고 외양만.\n"
        "- 각 슬롯 프롬프트는 장면(장소·행동·구도·조명)을 구체적으로. 사진처럼(documentary photo). 'illustration', 'cartoon' 금지. 글자·자막·워터마크가 나오게 하지 마라.\n"
        "- 출력은 JSON 하나만: {\"cast\": {\"<슬롯>\": \"...\"}, \"prompts\": {\"<슬롯>\": \"...\"}}. 슬롯 키는 문자열 숫자.\n\n"
        f"[슬롯 목록] {slots}\n[컷↔슬롯]\n{cuts}\n\n[소재]\n{source_text[:1500]}\n"
    )


def make_prompts(script, source_text, call, *, log=print):
    raw = call(build_prompt_request(script, source_text))
    d = _prompt.parse_any(raw)
    cast = {str(k): v for k, v in (d.get("cast") or {}).items()}
    # cast 키가 슬롯 번호면 그 슬롯 것만, 아니면('protagonist' 같은 이름 — 실측) 전부를 모든 프롬프트 앞에 붙인다.
    # 안 붙이면 프롬프트에 "the protagonist"만 남아 컷마다 다른 사람이 나온다.
    cast_all = "; ".join(f"{k}: {v}" for k, v in cast.items())
    prompts = {}
    for k, v in (d.get("prompts") or {}).items():
        k = str(k)
        c = cast.get(k) or cast_all
        body = (c + ". " if c and c.lower() not in v.lower() else "") + v
        prompts[k] = spec.IMAGE_PROMPT_PREFIX + body + spec.IMAGE_PROMPT_SUFFIX
    slots = sorted({g["img"] for g in script["groups"] if isinstance(g.get("img"), int)})
    missing = [s for s in slots if str(s) not in prompts]
    if missing:
        raise RuntimeError(f"images: 프롬프트가 없는 슬롯 {missing}")
    log(f"[brainbulb.prompts] 슬롯 {len(prompts)}개 프롬프트")
    return {"cast": cast, "prompts": prompts}


# ── EvoLink ──────────────────────────────────────────────────────────────────────
def evolink_key(key_file=None):
    v = os.environ.get("EVOLINK_API_KEY", "").strip()
    if v:
        return v
    p = key_file or os.path.expanduser("~/.volcano/keys/evolink")
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def _extract_urls(payload):
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


def evolink_imagegen(*, quality=None, size=None, key_file=None, poll_max=120, poll_sec=3, log=print):
    key = evolink_key(key_file)
    if not key:
        raise RuntimeError("images: EvoLink 키가 없습니다 (~/.volcano/keys/evolink 또는 EVOLINK_API_KEY)")
    H = {"Authorization": f"Bearer {key}"}

    def gen(prompt, out_path):
        body = {"model": spec.IMAGE_MODEL, "prompt": prompt, "size": size or spec.IMAGE_SIZE, "quality": quality or spec.IMAGE_QUALITY}
        r = requests.post(f"{spec.IMAGE_API}/v1/images/generations", headers={**H, "Content-Type": "application/json"}, json=body, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"evolink {r.status_code}: {r.text[:200]}")     # 4xx는 되풀이하지 않는다(실행기 주석: 어뷰징 신호)
        created = r.json()
        task = created.get("id") or created.get("task_id")
        urls = _extract_urls(created) if not task else []
        for _ in range(poll_max):
            if urls:
                break
            time.sleep(poll_sec)
            d = requests.get(f"{spec.IMAGE_API}/v1/tasks/{task}", headers=H, timeout=60).json()
            st = str(d.get("status") or d.get("state") or "").lower()
            if st in ("completed", "succeeded", "success"):
                urls = _extract_urls(d)
                if not urls:
                    raise RuntimeError("evolink: 완료인데 이미지 주소가 없습니다")
            elif st in ("failed", "error"):
                raise RuntimeError(f"evolink: 생성 실패 {d.get('fail_reason') or st}")
        if not urls:
            raise RuntimeError("evolink: 시간 안에 안 끝났습니다")
        raw = requests.get(urls[0], headers={"User-Agent": "Mozilla/5.0"}, timeout=90).content
        if len(raw) < 1024:
            raise RuntimeError(f"evolink: 이미지가 너무 작습니다 {len(raw)}B")
        with open(out_path, "wb") as fh:
            fh.write(raw)
    return gen


_SAFE_SUFFIX = ("wide establishing shot from behind, no faces visible, "
                "no weapons in frame, neutral documentary scene")


def _soften(prompt):
    """거부된 프롬프트를 순화 — 사람·무기 묘사를 빼고 장소 위주로.

    실측 2026-09-12(테이저건 편 슬롯7): 미성년자 + 테이저건이 한 장면에 있으면 gpt-image-2가
    `failed`로 거부한다. 한 슬롯이 막혀 **편 전체가 멈추면** 안 되므로 ①순화 재시도 ②그래도 실패면
    그 슬롯만 비우고(검은 슬롯) 진행한다.
    """
    head = spec.IMAGE_PROMPT_PREFIX
    body = prompt[len(head):] if prompt.startswith(head) else prompt
    body = body.split(". ")[-1] if ". " in body else body        # cast 설명(인물 인상착의)을 떨군다
    return head + body.replace(spec.IMAGE_PROMPT_SUFFIX, "") + ", " + _SAFE_SUFFIX


def generate_all(prompts, workdir, imagegen, *, log=print):
    """prompts {slot: text} → img/<slot>.png. 같은 프롬프트(해시)면 재사용 — 재과금 없음.

    한 슬롯이 실패해도 편 전체를 멈추지 않는다(순화 재시도 → 그래도 실패면 그 슬롯 없이 진행).
    """
    d = os.path.join(workdir, "img")
    os.makedirs(d, exist_ok=True)
    out, made, failed = {}, 0, []
    for slot, p in sorted(prompts.items(), key=lambda kv: int(kv[0])):
        path = os.path.join(d, f"{int(slot):02d}.png")
        h = hashlib.sha256(p.encode("utf-8")).hexdigest()[:16]
        side = path + ".json"
        ok = os.path.exists(path) and os.path.exists(side) and json.load(open(side, encoding="utf-8")).get("hash") == h
        if not ok:
            used = p
            try:
                imagegen(p, path)
            except Exception as e1:  # noqa: BLE001 — 거부·일시오류 모두 순화 재시도 대상
                used = _soften(p)
                log(f"[brainbulb.images] 슬롯 {slot} 거부({e1!r:.80}) → 순화 재시도")
                try:
                    imagegen(used, path)
                except Exception as e2:  # noqa: BLE001
                    log(f"[brainbulb.images] 슬롯 {slot} 재시도도 실패({e2!r:.80}) — 이 슬롯 없이 진행")
                    failed.append(str(slot))
                    continue
            json.dump({"hash": h, "prompt": used}, open(side, "w", encoding="utf-8"), ensure_ascii=False)
            made += 1
        out[str(slot)] = path
    log(f"[brainbulb.images] {len(out)}장 중 {made}장 새로 생성" + (f" · 실패 슬롯 {failed}" if failed else ""))
    return out
