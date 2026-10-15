# -*- coding: utf-8 -*-
"""숏템 컨셉 스튜디오 MCP — 고객 Claude 데스크톱이 부르는 도구(Claude형, 관제 213).

도구는 core 를 부르기만 한다(판단은 core 한 곳). 무거운 일은 core 가 따로 띄운 작업 프로세스가 한다.
실행: python -m shopping_shorts.concept_studio.mcp_server   (stdio)

★허용 창 줄이기(사장님 2026-10-15 "허용 계속 뜨는 거 막고"):
  - 확장이 허용을 대신 눌러 줄 수는 없다(호스트의 안전장치). 그래서 **부르는 횟수**를 줄이고
    읽기만 하는 도구에 읽기 전용 표시를 달아 한 번에 묶어 허용할 수 있게 한다.
  - studio_make 하나로 받기+시작+대본 요청까지, 넣기·확정도 다음 멈출 자리까지 기다렸다 돌려준다.
"""
import time

from mcp.server.mcpserver import Image, MCPServer
from mcp.types import ToolAnnotations

from shopping_shorts.concept_studio import core

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)
STOPS = ("need_script", "confirm_script", "failed", "done")

mcp = MCPServer(
    "shottem-studio",
    instructions=(
        "숏템 컨셉 스튜디오. 고객이 'OO 만들어줘'라고 하면 studio_make(concept, seed) 한 번으로 시작한다"
        "(웹 스튜디오 설정 받기·시작·대본 요청까지 한 번에). "
        "need_script 면 prompt 지시대로 **요청한 JSON만** 써서 studio_submit_script 로 넣는다(사실은 prompt 안 자료에서만). "
        "반려가 오면 지적된 곳만 고쳐 다시 넣는다. confirm_script 면 대본을 고객에게 보여 주고 확인을 받아 studio_confirm. "
        "running 이면 '10~20분 걸린다, 다 되면 물어봐 달라'고 말하고 끝낸다. 고객이 물을 때만 studio_status 로 본다. "
        "★예약 작업·알림·스케줄을 만들지 마라(만들 때마다 고객에게 허용 창이 뜬다). 짧은 간격으로 반복 호출하지 마라. "
        "alive 가 true 면 멈춘 게 아니다 — studio_resume 을 부르지 마라. "
        "done 이면 studio_result 로 검수 시트 그림을 **직접 보고** 컷마다 화면이 자막과 맞는지 스스로 판단해 결과와 함께 알린다 "
        "— 고객에게 '확인해 달라'고 떠넘기지 마라. failed 면 이유를 그대로 전한다. 앱을 껐다 켜서 멈췄으면 studio_resume. "
        "사람 확인은 대본 1회뿐이다 — 그 밖에는 고객에게 중간 확인을 묻지 말고 끝까지 진행한다."),
)


def _wait(job_id, sec=50):
    """다음 멈출 자리(대본 요청·대본 확인·실패·완료)까지 최대 sec 초 기다린 상태 — 호출(=허용 창) 수를 줄인다."""
    end = time.time() + sec
    st = core.status(job_id)
    while st.get("state") not in STOPS and time.time() < end:
        time.sleep(2)
        st = core.status(job_id)
    return st


@mcp.tool(annotations=WRITE)
def studio_make(concept: str, seed: str) -> dict:
    """한 번에: 웹 스튜디오 설정·팩 받기 → 작업 시작 → 대본 요청(need_script)까지. seed 는 컨셉의 source_hint 형식."""
    synced = core.sync() if all(core.studio_conn()) else {"ok": False, "why": "스튜디오 연결 정보 없음 — 동봉 컨셉으로"}
    jid = core.start_job(concept, seed)
    return {"job_id": jid, "sync": {k: synced.get(k) for k in ("ok", "downloaded", "unchanged", "why")}, **_wait(jid)}


@mcp.tool(annotations=WRITE)
def studio_sync() -> dict:
    """웹 컨셉 스튜디오의 컨셉·내 설정·팩만 다시 받는다(고객이 웹에서 설정을 바꿨을 때)."""
    return core.sync()


@mcp.tool(annotations=READ)
def studio_concepts() -> list:
    """쓸 수 있는 컨셉 목록(이름·필요한 소재 형식)."""
    return core.list_concepts()


@mcp.tool(annotations=WRITE)
def studio_start(concept: str, seed: str) -> dict:
    """(설정 받기 없이) 작업만 시작한다. 보통은 studio_make 를 쓴다."""
    jid = core.start_job(concept, seed)
    return {"job_id": jid, **_wait(jid)}


@mcp.tool(annotations=READ)
def studio_status(job_id: str) -> dict:
    """작업 상태. state: queued|running|need_script|confirm_script|failed|done."""
    return core.status(job_id)


@mcp.tool(annotations=WRITE)
def studio_submit_script(job_id: str, text: str) -> dict:
    """need_script 일 때 prompt 에 맞춰 쓴 대본(요청한 JSON)을 넣고, 검사 결과(반려·확인 요청)까지 기다려 돌려준다."""
    core.submit_script(job_id, text)
    return _wait(job_id)


@mcp.tool(annotations=WRITE)
def studio_confirm(job_id: str, ok: bool = True, note: str = "") -> dict:
    """대본 확인. ok=False 면 note(고칠 점)를 붙여 다시 쓰게 한다."""
    core.confirm_script(job_id, ok, note)
    return _wait(job_id, 20)


@mcp.tool(annotations=WRITE)
def studio_resume(job_id: str) -> dict:
    """멈춘 작업(앱을 껐다 켰거나 진행이 없을 때)을 이어서 돌린다."""
    r = core.resume(job_id)
    return r if r.get("alive") and r.get("note", "").startswith("이미") else _wait(job_id, 20)


@mcp.tool(annotations=READ)
def studio_result(job_id: str) -> list:
    """완성된 작업의 결과 — 영상 경로·길이와 검수 시트(컷마다 화면+자막) 그림. Claude 가 그림을 직접 보고 판단한다."""
    st = core.status(job_id)
    if st.get("state") != "done":
        return [f"아직 완성 전: {st.get('state')} ({st.get('step')})"]
    out = [f"영상: {st.get('final')} · {st.get('duration')}초"]
    if st.get("sheet"):
        out.append(Image(path=st["sheet"]))
    return out


if __name__ == "__main__":
    mcp.run()
