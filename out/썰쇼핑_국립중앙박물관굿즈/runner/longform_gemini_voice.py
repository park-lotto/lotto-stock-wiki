"""Gemini TTS narration for 인물형 롱폼 via Volcano Kit (2026-10-22 사장님 승인 · 요청 82).

The author may pick Gemini (subscription, made by the Volcano Kit Chrome extension on AI Studio) instead of Typecast.
Nothing new downstream: a Gemini block becomes exactly what an author-supplied voice already is —
existing_voice {format: external-wav-v1, path, sha256} — so its caption/breath/cut times are measured by the same
word-timing ladder (longform_external_voice · server asr_plan: Speechmatics first). This module only makes the WAV.

The maker is the shared Volcano Kit client, not a new one: <workdir>/volcanokit_flow/volcanokit/agent/{vk_update,vk_client}
(the same three steps as storytoon voices._gemini and podcast voice_engines._volcanokit_whole: auto-update → tts →
install note on failure). The kit's agent splits long text, joins the parts and checks each part for truncation (0.3.45).

One WAV per (text, voice, model): a finished file is kept with a receipt and never requested again (resume/restart reuse
it). A failure stops the job (no automatic retry · rule 6-2); the next run asks again only for blocks without a file.
"""
import json
import sys
from pathlib import Path

from longform_state import ProductionError, digest_file as file_digest, replace as publish

ENGINE = 'gemini'
FORMAT = 'external-wav-v1'


def _digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def settings(cfg):
    """The selected Gemini voice settings from the job config, or None (Typecast — the default)."""
    chosen = (cfg or {}).get('voice_engine')
    if not isinstance(chosen, dict) or chosen.get('name') != ENGINE:
        return None
    if not all(isinstance(chosen.get(k), str) and chosen[k] for k in ('voice', 'model', 'pack')):
        raise ProductionError('voice_engine_contract', '제미나이 TTS 설정(voice·model·pack)이 작업 설정에 없습니다. longform_seed 를 다시 부르세요.',
                              action='resume')
    return chosen


def _folder(root, text, chosen):
    return Path(root) / 'gemini-voice' / _digest({'text': text, 'voice': chosen['voice'], 'model': chosen['model']})


def made(root, text, chosen):
    """The finished WAV for this text, or None (receipt and file fingerprint must agree)."""
    folder = _folder(root, text, chosen)
    out, receipt = folder / 'voice.wav', folder / 'receipt.json'
    if not (out.is_file() and receipt.is_file()):
        return None
    try:
        data = json.loads(receipt.read_text('utf-8'))
    except ValueError:
        return None
    if data.get('text') != text or data.get('sha256') != file_digest(out):
        return None
    return out, data['sha256']


def _kit(pack):
    agent = Path(pack) / 'volcanokit' / 'agent'
    if not (agent / 'vk_client.py').is_file():
        raise ProductionError('volcanokit_pack_missing', f'볼케이노킷 팩이 작업 폴더에 없습니다({agent}). assets 단계를 다시 부르면 받습니다.',
                              action='restore_asset')
    if str(agent) not in sys.path:
        sys.path.insert(0, str(agent))
    import vk_client, vk_update  # noqa: E401,PLC0415 — the shared kit copy shipped in the pack
    return vk_client, vk_update


_UPDATED = []


def make(root, text, chosen, log=None):
    """WAV for one block's text → (path, sha256). Reuses a finished file; otherwise one Volcano Kit request."""
    found = made(root, text, chosen)
    if found:
        return found
    log = log or (lambda message: print(message, file=sys.stderr, flush=True))
    vk_client, vk_update = _kit(chosen['pack'])
    if not _UPDATED:                       # once per process, like storytoon/podcast
        _UPDATED.append(True)
        try:
            vk_update.auto_update(log=log)
        except (OSError, RuntimeError) as error:   # keep going with the installed kit; the reason is logged
            log(f'볼케이노킷 자동 갱신을 못 했다(지금 판으로 계속): {error}')
    folder = _folder(root, text, chosen)
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / 'voice.part.wav'
    try:
        result = vk_client.tts(text, str(part), chosen['voice'], chosen['model'], timeout_s=600, log=log)
    except vk_client.VkError as error:
        raise ProductionError('gemini_tts_failed', f'제미나이 TTS(볼케이노킷)가 음성을 만들지 못했습니다: {error}\n{vk_update.install_note()}',
                              action='repair_environment') from None
    if not part.is_file() or part.stat().st_size <= 44:
        raise ProductionError('gemini_tts_empty', '제미나이 TTS(볼케이노킷)가 빈 음성을 돌려줬습니다.', action='repair_environment')
    out = folder / 'voice.wav'
    publish(part, out)
    sha = file_digest(out)
    tmp = folder / 'receipt.part.json'
    tmp.write_text(json.dumps({'text': text, 'voice': chosen['voice'], 'model': chosen['model'], 'sha256': sha,
                               'chunks': result.get('chunks') if isinstance(result, dict) else None}, ensure_ascii=False), 'utf-8')
    publish(tmp, folder / 'receipt.json')
    return out, sha


def with_voices(plan, cfg, root):
    """The plan with every not-yet-voiced block given its Gemini WAV as an external voice (a copy · authored plan untouched).
    Typecast jobs get the same object back."""
    chosen = settings(cfg)
    if chosen is None:
        return plan
    import copy
    voiced = copy.deepcopy(plan)
    for block in voiced['blocks']:
        if block.get('existing_voice'):
            continue
        path, sha = make(root, block['text'], chosen)
        block['existing_voice'] = {'format': FORMAT, 'path': str(path), 'sha256': sha}
    return voiced
