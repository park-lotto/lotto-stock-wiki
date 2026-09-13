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
    # ★슬롯으로 묶어서 보여준다. 예전엔 컷을 평평하게 나열해 **한 슬롯을 2~3컷이 나눠 쓴다는 것**이
    #   안 보였고, 그래서 컷마다 다른 장면을 요구해 그림이 자막을 못 따라갔다(실측 2026-09-13).
    by = {}
    for i, g in enumerate(script["groups"]):
        if isinstance(g.get("img"), int):
            by.setdefault(g["img"], []).append(f"컷{i + 1} «{g['text']}»")
    cuts = "\n".join(f"- 슬롯 {s} ({len(by[s])}컷 공유): " + " + ".join(by[s]) for s in sorted(by))
    return (
        "너는 뇌전구 채널의 이미지 디렉터다. 아래 대본의 이미지 슬롯마다 **어떤 사진을 쓸지**와 **영문 생성 프롬프트**를 정한다.\n"
        "\n"
        "[슬롯마다 셋 중 하나를 고른다]\n"
        "  real    실존 인물이 주인공이고 **좋은 얘기**(복귀·성과·봉사·미담)인 컷 → 실제 사진을 그대로 쓴다\n"
        "  variant 실존 인물이 주인공인데 **안 좋은 얘기**(논란·사고·비판·수사)인 컷 → 실제 사진을 참조로 변형한다\n"
        "  scene   인물이 아니라 **장소·사물**이 주인공인 컷 → 검색해서 실제 사진을 쓴다\n"
        "          (KTX 승강장·휠체어 경사로·슬럼가 골목처럼 '그 자리에 가면 있는' 것)\n"
        "  gen     장소·사물로 찍을 수 없는 **개념·감정** 컷 → 처음부터 생성한다\n"
        "          (침묵·여론·시간이 흐름처럼 눈에 안 보이는 것, 그리고 특정 개인이 나와야 하는데 검색이 안 될 때)\n"
        "  ★real·variant·scene을 고르면 `query`에 **한국어 이미지 검색어**를 쓴다.\n"
        "    real·variant는 인물 이름 + 상황(예: '박수홍 홈쇼핑'). scene은 장소·사물 이름(예: 'KTX 승강장').\n"
        "  ★인물 이름이 기사에 안 나오면 real·variant를 쓰지 마라. scene이나 gen으로 간다.\n"
        "  ★scene 검색어에 **사람을 넣지 마라** — '노트북 보는 사람' 같은 건 스톡사진이 와서 광고처럼 보인다.\n"
        "    장소·사물만 적어라. 사람이 꼭 필요하면 gen으로 만들어라.\n"
        "\n"
        "[프롬프트 규칙]\n"
        "- cast: 주인공 인상착의를 **한 문장으로 고정**한다(나이대·체형·머리·옷차림). 실명·유명인 이름은 쓰지 말고 외양만.\n"
        "  ★cast는 **주인공이 실제로 화면에 나오는 슬롯에만** 달아라. 슬롯 번호를 키로 쓴다.\n"
        "    실측: 볼케이노는 10슬롯 중 5개에만 달았다(편마다 5/10 · 3/9 · 6/9).\n"
        "    ✘ 전 슬롯에 달지 마라 — 장소·사물·행인 컷에까지 주인공이 그려진다\n"
        "      (실측 2026-09-13: 케냐 슬럼가·시장통·태권도장에 전부 휠체어 탄 남자가 나왔다).\n"
        "    주인공이 없는 컷은 cast를 **빼고** 그 장면만 써라: «공항 지상직원이 짐을 내린다»\n"
        "    «기내에서 시계를 보는 지친 승객들» «소파에 앉아 휴대폰을 엎어둔 부부».\n"
        "- ★places: 그 컷이 **어느 나라·도시**인지 슬롯마다 영문으로 적어라(«Kenya», «Nairobi slum», «Seoul»).\n"
        "  한 편 안에서도 나라가 갈린다 — KTX 사고는 한국, 케냐 봉사는 케냐다.\n"
        "  안 적으면 한국으로 그려진다: 실측 2026-09-13, 케냐 슬럼가 계단 장면에 장소를 안 적었더니\n"
        "  **한국 지하철 계단에서 파란 조끼 자원봉사자들이 휠체어를 드는 그림**이 나왔다.\n"
        "  국내 컷은 비워도 된다(기본이 한국).\n"
        "- 각 슬롯 프롬프트는 장면(장소·행동·구도·조명)을 구체적으로 영문 한 줄로.\n"
        "  ★한 슬롯을 2~3컷이 나눠 쓴다 — 그 컷들을 **한 장면으로 묶어** 그려라. 컷마다 다른 장면을 요구하지 마라.\n"
        "  ★첫 어구로 사진의 종류를 정해라: «Photorealistic wide shot of…» «Photorealistic medium shot of…»\n"
        "    «Documentary style photo of…». 슬롯마다 달라도 된다(실측: 편 B 8종·편 C 9종).\n"
        "  (real·variant 슬롯도 프롬프트를 반드시 써라 — 검색이 실패하면 그것으로 생성한다)\n"
        "- ★화면·계기판을 주문하지 마라: 유튜브 채널 화면·구독자 카운터·그래프·스마트폰 화면.\n"
        "  모델이 **없는 채널 이름과 숫자를 지어내 화면에 박는다**(실측 2026-09-13: 가짜 채널명 밑에\n"
        "  '1,000,000' 구독자 수, '글로벌 경기침체' 그래프가 그려졌다). 있지도 않은 기록을 진짜처럼 보여주는 것이다.\n"
        "  숫자는 자막이 말한다 — 그림은 **사람과 장소**를 보여줘라(빈 책상·창밖을 보는 뒷모습·문 닫힌 사무실).\n"
        "\n"
        "출력은 JSON 하나만:\n"
        '{"cast": {"<슬롯>": "..."}, "places": {"<슬롯>": "Kenya 또는 빈 문자열"}, '
        '"prompts": {"<슬롯>": "..."}, '
        '"sources": {"<슬롯>": {"kind": "real|variant|scene|gen", "query": "검색어 또는 빈 문자열"}}}\n\n'
        f"[슬롯 목록] {slots}\n[컷↔슬롯]\n{cuts}\n\n[소재]\n{source_text[:1500]}\n"
    )


def _locale(script, slot_place=None):
    """이미지에 붙일 로케일 한 줄 — 슬롯이 장소를 적었으면 그것, 아니면 대본의 region/place.

    ★로케일을 "한국"으로 박으면 **해외 장면이 한국으로 그려진다**(실측 2026-09-13 v7 슬롯4:
      케냐 슬럼가 계단인데 한국 지하철 계단에 파란 조끼 봉사자들이 나왔다).
      볼케이노도 편마다 region을 정한다(보르네오 편 region=해외 · place=인도네시아 보르네오).
      우리 대본도 region/place를 만들고 있었는데 **이미지 쪽이 안 쓰고 있었다** — 배선 누락.
      게다가 한 편 안에서도 나라가 갈린다(KTX=한국 · 슬럼가=케냐) → 슬롯이 적은 장소를 우선한다.
    """
    if slot_place:
        return f"In {slot_place}"
    r = script.get("region") or {}
    place = (r.get("place") or "").strip()
    if r.get("region") == "해외" and place:
        return f"In {place}"
    return spec.IMAGE_LOCALE_DEFAULT


def _needs_person(script, slot):
    """그 슬롯 자막이 **사람의 행동**을 말하나 — 그러면 장소 검색으로는 못 채운다.

    실측 2026-09-13(v5): «사람들 도움을 받음»·«휠체어 타고 찾았음»에 장소만 검색해
      빈 골목·지붕 사진이 왔다. 사람이 나와야 하는 컷은 생성으로 보낸다.
    """
    txt = " ".join(g.get("text", "") for g in script.get("groups") or []
                   if str(g.get("img")) == str(slot))
    return any(w in txt for w in spec.PROMPT_PERSON_WORDS)


def _no_screen(prompt, hit):
    """화면·계기판을 주문한 프롬프트를 **사람·장소 장면으로** 바꾼다.

    ★왜 지우는 게 아니라 바꾸나: 문장에서 화면만 빼면 "…를 보여주는"처럼 목적어가 사라져
      모델이 아무거나 그린다. 대신 같은 감정을 사람·장소로 옮긴 문장을 통째로 쓴다
      (볼케이노 실측도 «소파에 앉아 휴대폰을 엎어둔 부부»처럼 화면 대신 사람을 쓴다).
    """
    return spec.IMAGE_PROMPT_PREFIX + spec.PROMPT_SCREEN_FALLBACK + spec.IMAGE_PROMPT_SUFFIX


def make_prompts(script, source_text, call, *, log=print):
    raw = call(build_prompt_request(script, source_text))
    d = _prompt.parse_any(raw)
    cast = {str(k): v for k, v in (d.get("cast") or {}).items()}
    # 슬롯별 장소 — 한 편 안에서 나라가 갈릴 때 쓴다(KTX=한국 · 슬럼가=케냐). 없으면 대본 region/place.
    places = {str(k): (v or "").strip() for k, v in (d.get("places") or {}).items()}
    prompts = {}
    for k, v in (d.get("prompts") or {}).items():
        k = str(k)
        # ★cast는 **그 슬롯에 지정된 것만** 붙인다. 예전엔 지정이 없으면 전체 cast를 붙였는데
        #   (`cast.get(k) or cast_all`), 그 탓에 **인물이 안 나오는 컷에도 주인공이 그려졌다**
        #   — 케냐 슬럼가·시장통에 휠체어 탄 남자가 나온 직접 원인(사장님 2026-09-13 "전혀 다른 게 나온다").
        #   실측: 볼케이노는 주인공이 화면에 나오는 슬롯에만 붙인다(편 A 5/10 · B 3/9 · C 6/9).
        c = cast.get(k) or ""
        body = (c + ", " if c and c.lower() not in v.lower() else "") + v
        # ★cast는 프롬프트 안에 두 번 들어간다 — 장면 앞과 접미 직전(실측 볼케이노 전 슬롯).
        tail = (", " + c if c else "") + spec.IMAGE_PROMPT_SUFFIX
        prompts[k] = _locale(script, places.get(k)) + ", " + body + tail
    slots = sorted({g["img"] for g in script["groups"] if isinstance(g.get("img"), int)})
    missing = [s for s in slots if str(s) not in prompts]
    if missing:
        raise RuntimeError(f"images: 프롬프트가 없는 슬롯 {missing}")
    # ★화면·계기판 주문을 **판정으로** 막는다 — 지시문에 적어놨는데도 모델이 어겼다
    #   (실측 2026-09-13 v5 슬롯9: "computer screen showing a social media profile with a
    #    downward trend line" → 가짜 그래프 화면이 그려졌다. 접미 금지어 16개도 못 막았다).
    #   지시만 있고 판정이 없으면 언젠가 샌다 — 오늘 다섯 번째 같은 병이다.
    for k, v in list(prompts.items()):
        # ★**접미를 뺀 본문만** 검사한다 — 접미에 "no legible numbers"가 들어 있어
        #   그대로 검사하면 모든 프롬프트가 "numbers"에 걸려 전부 빈 방이 된다(시험이 잡았다).
        #   ★접두 길이로 자르지 마라 — 로케일이 «In Kenya»처럼 짧아지면 잘림이 어긋나
        #   접미 일부가 본문에 남아 다시 "numbers"에 걸린다(실측 2026-09-13, 내가 만든 회귀).
        low = v.split(spec.IMAGE_PROMPT_SUFFIX)[0].lower()
        hit = next((w for w in spec.PROMPT_SCREEN_WORDS if w in low), None)
        if hit:
            prompts[k] = _no_screen(v, hit)
            log(f"[brainbulb.prompts] 슬롯 {k} 화면 주문(«{hit}») — 사람·장소로 바꿈")
    # 사진 종류·검색어 — 없거나 이상하면 gen으로 (판정은 여기 한 곳)
    sources = {}
    for k in prompts:
        v = (d.get("sources") or {}).get(k) or {}
        kind = str(v.get("kind") or "gen").lower()
        query = (v.get("query") or "").strip()
        if kind not in spec.PHOTO_KINDS or (kind in ("real", "variant", "scene") and not query):
            kind, query = "gen", ""
        # ★자막이 **사람의 행동**을 말하는 컷은 scene(장소 검색)으로 보내지 않는다.
        #   실측 2026-09-13 v5: «휠체어 타고 케냐 슬럼가를 찾았음»에 «케냐 슬럼가 골목»으로 검색해
        #   지붕만 찍힌 사진이 왔고, «사람들 도움을 받음»에는 깜깜한 빈 골목이 왔다.
        #   지시문에 "사람이 필요하면 gen으로"가 있었는데도 안 지켜졌다 — 판정으로 막는다.
        if kind == "scene" and _needs_person(script, k):
            kind, query = "gen", ""
            log(f"[brainbulb.prompts] 슬롯 {k} 자막이 사람의 행동 — 장소검색 대신 생성")
        sources[k] = {"kind": kind, "query": query}
    from collections import Counter
    c = Counter(v["kind"] for v in sources.values())
    log(f"[brainbulb.prompts] 슬롯 {len(prompts)}개 — 실물 {c['real']} · 변형 {c['variant']} · 장소 {c['scene']} · 생성 {c['gen']}")
    return {"cast": cast, "prompts": prompts, "sources": sources}


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


def _from_photo(slot, src, path, kind, workdir, log):
    """검색 사진 → real이면 그대로 복사, variant면 참조 변형. 성공하면 True."""
    from . import photos
    if kind in ("real", "scene"):          # scene도 찾은 사진을 그대로 쓴다(변형 안 함)
        from PIL import Image
        Image.open(src["path"]).convert("RGB").save(path, "PNG")
        return True
    photos.variant(src["path"], path, spec.VARIANT_PROMPT, log=log)
    return True


def generate_all(prompts, workdir, imagegen, *, sources=None, log=print):
    """prompts {slot: text} → img/<slot>.png.

    사진 조달 순서(사장님 2026-09-13): 실물/변형 지정 슬롯은 **검색 먼저**, 안 되면 생성으로 폴백.
    같은 프롬프트·같은 종류(해시)면 재사용 — 재과금 없음. 한 슬롯이 실패해도 편 전체를 멈추지 않는다.
    """
    d = os.path.join(workdir, "img")
    os.makedirs(d, exist_ok=True)
    sources = sources or {}
    out, made, failed, by_kind = {}, 0, [], {"real": 0, "variant": 0, "scene": 0, "gen": 0}
    seen_photos = set()          # ★같은 사진이 두 컷에 들어가는 걸 막는다(편 하나에서 돌려 쓴다)
    for slot, p in sorted(prompts.items(), key=lambda kv: int(kv[0])):
        path = os.path.join(d, f"{int(slot):02d}.png")
        src = sources.get(str(slot)) or {"kind": "gen", "query": ""}
        kind, query = src["kind"], src.get("query", "")
        h = hashlib.sha256(f"{kind}|{query}|{p}".encode("utf-8")).hexdigest()[:16]
        side = path + ".json"
        if os.path.exists(path) and os.path.exists(side) and json.load(open(side, encoding="utf-8")).get("hash") == h:
            out[str(slot)] = path
            by_kind[kind] = by_kind.get(kind, 0) + 1
            continue
        done, used_kind = False, kind
        if kind in ("real", "variant", "scene") and query:
            from . import photos
            # ★scene은 얼굴을 보지 않는다 — 승강장·골목처럼 사람이 없는 게 정상이다
            hit = photos.pick_photo(query, workdir, slot, log=log, seen=seen_photos,
                                    want_face=(kind != "scene"),
                                    max_mark=(spec.POLICY_SCENE_MARK_MAX if kind == "scene" else None))
            if hit:
                try:
                    done = _from_photo(slot, hit, path, kind, workdir, log)
                except Exception as e:  # noqa: BLE001 — 변형 실패는 생성으로 폴백
                    log(f"[brainbulb.images] 슬롯 {slot} 변형 실패({e!r:.70}) — 생성으로")
            if not done:
                used_kind = "gen"
        if not done:
            used_kind = "gen"
            used = p
            try:
                imagegen(p, path)
                done = True
            except Exception as e1:  # noqa: BLE001 — 거부·일시오류 모두 순화 재시도 대상
                used = _soften(p)
                log(f"[brainbulb.images] 슬롯 {slot} 거부({e1!r:.80}) → 순화 재시도")
                try:
                    imagegen(used, path)
                    done = True
                except Exception as e2:  # noqa: BLE001
                    log(f"[brainbulb.images] 슬롯 {slot} 재시도도 실패({e2!r:.80}) — 이 슬롯 없이 진행")
                    failed.append(str(slot))
        if not done:
            continue
        json.dump({"hash": h, "kind": used_kind, "query": query, "prompt": p},
                  open(side, "w", encoding="utf-8"), ensure_ascii=False)
        made += 1
        by_kind[used_kind] = by_kind.get(used_kind, 0) + 1
        out[str(slot)] = path
    log(f"[brainbulb.images] {len(out)}장 (새로 {made}장) — 실물 {by_kind.get('real',0)} · 변형 {by_kind.get('variant',0)} · 장소 {by_kind.get('scene',0)} · 생성 {by_kind.get('gen',0)}"
        + (f" · 실패 슬롯 {failed}" if failed else ""))
    return out


def regenerate(slots, prompts, workdir, imagegen, files, *, log=print):
    """검수에서 반려된 슬롯만 **안전한 장면으로 바꿔** 다시 만든다. → 갱신된 files

    ★같은 프롬프트로 다시 만들면 같은 것이 나온다(실측: 가짜 간판을 두 번 그렸다).
      반려 사유가 대개 '읽히는 글자'이므로 글자가 나올 여지를 없앤 장면으로 바꾼다.
      그래도 실패하면 그 슬롯은 그대로 둔다 — 편이 멈추면 안 된다.
    """
    out = dict(files)
    d = os.path.join(workdir, "img")
    for slot in slots:
        path = os.path.join(d, f"{int(slot):02d}.png")
        safe = spec.IMAGE_PROMPT_PREFIX + spec.PROMPT_SCREEN_FALLBACK + spec.IMAGE_PROMPT_SUFFIX
        try:
            imagegen(safe, path)
            out[str(slot)] = path
            side = path + ".json"
            with open(side, "w", encoding="utf-8") as fh:
                json.dump({"kind": "gen", "hash": hashlib.sha256(safe.encode("utf-8")).hexdigest()[:16],
                           "regenerated": True, "why": "검수 반려"}, fh, ensure_ascii=False)
            log(f"[brainbulb.images] 슬롯 {slot} 검수 반려 → 안전한 장면으로 다시 만듦")
        except Exception as e:  # noqa: BLE001 — 재생성 실패가 편을 멈추면 안 된다
            log(f"[brainbulb.images] 슬롯 {slot} 재생성 실패({e!r:.60}) — 그대로 둔다")
    return out
